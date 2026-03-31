from fastapi import FastAPI, HTTPException, Request, Depends
from pydantic import BaseModel
from typing import Optional
import sqlite3
import json
import random
import httpx
import asyncio
import uvicorn
from datetime import datetime, timezone

# ---------------- Config ----------------
import os

CONFIG_PATH = "/data/options.json" if os.path.exists("/data/options.json") else "config.json"

with open(CONFIG_PATH) as f:
    config = json.load(f)

ENDPOINT_URL = config["endpoint_address"]
AUTH_TOKEN = config["auth_token"]
MAX_CONCURRENT = config["max_concurrent_requests"]
TIMEOUT = config["timeout"]
raw_endpoints = config.get("endpoints", [])
if isinstance(raw_endpoints, list):
    ENDPOINTS = {item["name"]: item for item in raw_endpoints if "name" in item}
else:
    ENDPOINTS = raw_endpoints
DB_FILE = config.get("database_file", "/data/buffer.db")

semaphore = asyncio.Semaphore(MAX_CONCURRENT)

def init_db():
    conn = sqlite3.connect(DB_FILE, timeout=10)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS buffer (
            endpoint TEXT,
            reply TEXT,
            timestamp TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

import logging

# ---------------- Logging ----------------
log_level = getattr(logging, config.get("log_level", "INFO").upper(), logging.INFO)
logging.basicConfig(
    level=log_level,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
)
logger = logging.getLogger(__name__)
logger.info(f"Using config file: {CONFIG_PATH}")

# ---------------- Helper functions ----------------

def get_fallback(endpoint: str):
    endpoint_cfg = ENDPOINTS.get(endpoint, {})
    return random.choice(endpoint_cfg.get("fallback_replies", ["No reply"]))

async def auto_fill_buffer(endpoint: str, count: int):
    prompt = ENDPOINTS[endpoint].get("prompt_for_buffer", "Generate a reply")
    model = ENDPOINTS[endpoint].get("model", "")
    temperature = ENDPOINTS[endpoint].get("temperature", 0.7)

    async with semaphore:
        async with httpx.AsyncClient(verify=False, timeout=TIMEOUT) as client:
            for _ in range(count):
                try:
                    response = await client.post(
                        ENDPOINT_URL,
                        json={
                            "prompt": prompt,
                            "temperature": temperature,
                            "model": model,
                            "stream": False
                        }
                    )
                    data = response.json()
                    text = data.get("response") or data.get("text") or ""
                    if not text:
                        text = get_fallback(endpoint)
                except Exception as e:
                    logger.error(f"Auto-fill error for '{endpoint}': {e}", exc_info=True)
                    text = get_fallback(endpoint)

                add_to_buffer(endpoint, text)
                enforce_max_buffer(endpoint)
                logger.info(f"Auto-filled reply for '{endpoint}': {text[:100]}{'...' if len(text)>100 else ''}")

def add_to_buffer(endpoint: str, reply: str):
    conn = sqlite3.connect(DB_FILE, timeout=10)
    c = conn.cursor()
    c.execute(
        "INSERT INTO buffer (endpoint, reply, timestamp) VALUES (?, ?, ?)",
        (endpoint, reply, datetime.utcnow().isoformat())
    )
    conn.commit()
    conn.close()
    logger.debug(f"Added reply to buffer for endpoint '{endpoint}': {reply[:50]}{'...' if len(reply)>50 else ''}")

def read_from_buffer(endpoint: str, remove: bool = True):
    conn = sqlite3.connect(DB_FILE, timeout=10)
    c = conn.cursor()
    c.execute("SELECT rowid, reply, timestamp FROM buffer WHERE endpoint=? ORDER BY rowid ASC", (endpoint,))
    rows = c.fetchall()
    if not rows:
        conn.close()
        logger.info(f"No replies in buffer for endpoint '{endpoint}'")
        return None
    rowid, reply, timestamp = rows[0]
    if remove:
        c.execute("DELETE FROM buffer WHERE rowid=?", (rowid,))
        conn.commit()
        logger.debug(f"Removed reply from buffer for endpoint '{endpoint}' (rowid={rowid})")
    conn.close()
    logger.debug(f"Read reply from buffer for endpoint '{endpoint}': {reply[:50]}{'...' if len(reply)>50 else ''}")
    return {"reply": reply, "timestamp": timestamp}

def enforce_max_buffer(endpoint: str):
    max_size = ENDPOINTS.get(endpoint, {}).get("max_buffer_size")
    if not max_size:
        return
    conn = sqlite3.connect(DB_FILE, timeout=10)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM buffer WHERE endpoint=?", (endpoint,))
    count = c.fetchone()[0]
    if count > max_size:
        to_delete = count - max_size
        c.execute("""
            DELETE FROM buffer 
            WHERE rowid IN (
                SELECT rowid FROM buffer 
                WHERE endpoint=? 
                ORDER BY rowid ASC 
                LIMIT ?
            )
        """, (endpoint, to_delete))
        logger.info(f"Trimmed {to_delete} oldest replies from buffer for endpoint '{endpoint}' to enforce max_buffer_size={max_size}")
    conn.commit()
    conn.close()

# ---------------- Request Models ----------------
class WriteBufferRequest(BaseModel):
    name: str
    count: int
    prompt: str
    temperature: float = 0.7
    model: str = ""
    clear: bool = False

class ReadBufferRequest(BaseModel):
    name: str
    remove_from_buffer: bool = True

# ---------------- Authentication ----------------
async def verify_token(request: Request):
    token = request.headers.get("Authorization")
    if token != f"Bearer {AUTH_TOKEN}":
        raise HTTPException(status_code=401, detail="Unauthorized")

# ---------------- App ----------------
app = FastAPI()

@app.on_event("startup")
async def prefill_buffers_sequential():
    logger.info("Prefilling buffers sequentially on startup...")
    for endpoint, cfg in ENDPOINTS.items():
        if cfg.get("maintain_max_buffer") and cfg.get("max_buffer_size", 0) > 0:
            # Count current entries in DB
            conn = sqlite3.connect(DB_FILE, timeout=10)
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM buffer WHERE endpoint=?", (endpoint,))
            current_count = c.fetchone()[0]
            conn.close()

            to_generate = max(cfg["max_buffer_size"] - current_count, 0)
            if to_generate > 0:
                logger.info(f"Generating {to_generate} replies for endpoint '{endpoint}'...")
                asyncio.create_task(auto_fill_buffer(endpoint, to_generate))
                await asyncio.sleep(0.1)
            else:
                logger.info(f"Buffer for endpoint '{endpoint}' already full ({current_count} entries), skipping generation.")
                
# --------- Write Buffer  ---------
@app.post("/write_buffer", dependencies=[Depends(verify_token)])
async def write_buffer(req: WriteBufferRequest):
    logger.info(f"Write buffer request: endpoint={req.name}, count={req.count}, clear={req.clear}")
    async with semaphore:
        if req.clear:
            conn = sqlite3.connect(DB_FILE, timeout=10)
            c = conn.cursor()
            c.execute("DELETE FROM buffer WHERE endpoint=?", (req.name,))
            conn.commit()
            conn.close()
            logger.info(f"Cleared buffer for endpoint '{req.name}'")
        
        model = req.model or ENDPOINTS.get(req.name, {}).get("model", "")
        temperature = req.temperature or ENDPOINTS.get(req.name, {}).get("temperature", 0.7)
        results = []
        
        async with httpx.AsyncClient(verify=False, timeout=TIMEOUT) as client:
            for i in range(req.count):
                try:
                    response = await client.post(
                        ENDPOINT_URL,
                        json={
                            "prompt": req.prompt,
                            "temperature": temperature,
                            "model": model,
                            "stream": False  # make sure single JSON
                        }
                    )
                    data = response.json()
                    text = data.get("response") or data.get("text") or ""
                    if not text:
                        # log raw response for debugging
                        logger.warning(f"Ollama returned empty reply for endpoint '{req.name}', using fallback. Raw response:\n{response.text}")
                        text = get_fallback(req.name)
                    else:
                        logger.info(f"Ollama reply used for endpoint '{req.name}': {text[:200]}{'...' if len(text)>200 else ''}")
                except Exception as e:
                    logger.error(f"Error calling Ollama for endpoint '{req.name}': {e}. Raw response:\n{response.text if 'response' in locals() else 'no response'}")
                    text = get_fallback(req.name)
                
                add_to_buffer(req.name, text)
                enforce_max_buffer(req.name)
                results.append(text)
        
        logger.info(f"Write buffer completed for endpoint '{req.name}', added {len(results)} replies")
        return {"added": len(results), "replies": results}
    
# --------- Read Buffer ---------  
    
@app.post("/read_buffer", dependencies=[Depends(verify_token)])
async def read_buffer_endpoint(req: ReadBufferRequest):
    logger.info(f"Read buffer request: endpoint={req.name}, remove_from_buffer={req.remove_from_buffer}")
    async with semaphore:
        entry = read_from_buffer(req.name, remove=req.remove_from_buffer)

        # auto-refill if enabled
        endpoint_cfg = ENDPOINTS.get(req.name, {})
        if endpoint_cfg.get("maintain_max_buffer") and req.remove_from_buffer:
            conn = sqlite3.connect(DB_FILE, timeout=10)
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM buffer WHERE endpoint=?", (req.name,))
            current_count = c.fetchone()[0]
            conn.close()
            to_generate = endpoint_cfg.get("max_buffer_size", 5) - current_count
            if to_generate > 0:
                asyncio.create_task(auto_fill_buffer(req.name, to_generate))
                await asyncio.sleep(0.1)

        if entry is None:
            # fallback
            asyncio.create_task(auto_fill_buffer(req.name, 1))
            await asyncio.sleep(0.1)
            text = get_fallback(req.name)
            timestamp = datetime.now(timezone.utc).isoformat()
            logger.warning(f"No entry in buffer for '{req.name}', returning fallback.")
            return {"reply": text, "timestamp": timestamp, "fallback": True}

        return {**entry, "fallback": False}

# --------- Clear Buffer ---------

class ClearBufferRequest(BaseModel):
    buffer_name: Optional[str] = "all" 

@app.post("/clear_buffer", dependencies=[Depends(verify_token)])
async def clear_buffer(req: ClearBufferRequest):
    async with semaphore:
        conn = sqlite3.connect(DB_FILE, timeout=10)
        c = conn.cursor()

        if not req.buffer_name or req.buffer_name.lower() == "all":
            c.execute("DELETE FROM buffer")
            deleted = c.rowcount
            logger.info(f"Cleared ALL buffers, deleted {deleted} entries")
            result = {"buffer": "all", "deleted_entries": deleted}
        else:
            c.execute("DELETE FROM buffer WHERE endpoint=?", (req.buffer_name,))
            deleted = c.rowcount
            logger.info(f"Cleared buffer '{req.buffer_name}', deleted {deleted} entries")
            result = {"buffer": req.buffer_name, "deleted_entries": deleted}

        conn.commit()
        conn.close()
        return result
    
# --------- List Buffer ---------
    
class ListBufferRequest(BaseModel):
    buffer_name: str
    
@app.post("/list_buffer", dependencies=[Depends(verify_token)])
async def list_buffer(req: ListBufferRequest):
    async with semaphore:
        conn = sqlite3.connect(DB_FILE, timeout=10)
        c = conn.cursor()
        c.execute(
            "SELECT rowid, reply, timestamp FROM buffer WHERE endpoint=? ORDER BY rowid ASC",
            (req.buffer_name,)
        )
        rows = c.fetchall()
        conn.close()
        logger.info(f"Listed {len(rows)} entries from buffer '{req.buffer_name}'")
        return {
            "buffer": req.buffer_name,
            "entries": [{"id": rowid, "reply": reply, "timestamp": timestamp} for rowid, reply, timestamp in rows]
        }
    
# only for local testing, in production use uvicorn command directly
    
if __name__ == "__main__":
    logger.info("Starting AI buffer server...")
    logger.info(f"Using Ollama endpoint: {ENDPOINT_URL}")
    logger.info(f"Max concurrent requests: {MAX_CONCURRENT}")
    logger.info(f"Timeout: {TIMEOUT}s")
    logger.info(f"Database file: {DB_FILE}")
    logger.info(f"Endpoints configured: {list(ENDPOINTS.keys())}")
    
    uvicorn.run("server:app",
                host="0.0.0.0", 
                port=8000, 
                log_level="info")