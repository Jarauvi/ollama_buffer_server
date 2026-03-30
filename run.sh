CONFIG_FILE=/data/config.json

if [ -f "$CONFIG_FILE" ]; then
    cp "$CONFIG_FILE" /app/config.json
fi

exec uvicorn server:app --host 0.0.0.0 --port 8000