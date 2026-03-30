# Ollama Buffer Server

This middleware acts as a **latency shock-absorber** between Home Assistant and local LLMs (like Ollama) with budget inference setups. Instead of making your smart home wait 30-300 seconds for a CPU/GPU to generate a response, this service pre-generates replies like reports or summaries in the background and stores them in a local SQLite database for instant retrieval.

---

## 📖 Chapter 1: Introduction
1.  **Instant Response:** Home Assistant gets a reply in 0ms because it's already sitting in a database.
2.  **Hardware Protection:** It uses a semaphore to ensure your GPU only handles one request at a time, preventing VRAM crashes.

---

## 🛠 Installation

Since this is a custom local add-on, follow these steps to add it to your Home Assistant instance:

Ah, you’re right! That’s the much "cleaner" way to do it. If you’ve hosted this on GitHub, the user just adds your repository URL to the "Repositories" list in the Add-on Store, and Home Assistant handles the rest.

Here is the updated README.md with the GitHub-style installation instructions.
Markdown

# 🧠 AI Buffer Server for Home Assistant

A high-performance middleware designed to eliminate LLM latency in your smart home. This add-on pre-generates AI responses in the background and stores them in a local SQLite database, allowing your automations to get instant, "thought-out" replies the millisecond a trigger occurs.

---

## 🛠 Installation

### 1. Add the Repository
1. In Home Assistant, navigate to **Settings** > **Add-ons**.
2. Click the **Add-on Store** button in the bottom right.
3. Click the **three dots** (top right) and select **Repositories**.
4. Paste your GitHub URL: `https://github.com/Jarauvi/ollama_buffer_server`
5. Click **Add**, then close the popup.

### 2. Install the Add-on
1. You should now see **AI Buffer Server** listed under your repository.
2. Click on it and select **Install**.
3. Once installed, go to the **Configuration** tab to set up your tokens and endpoints.
### 2. Install in Home Assistant
1. Go to **Settings** > **Add-ons**.
2. Click the **Add-on Store** button in the bottom right.
3. Click the **three dots** (top right) and select **Check for updates**.
4. Scroll down to the bottom. You should now see a section called **Local Add-ons**.
5. Select **AI Buffer Server** and click **Install**.

## ⚙️ Configuration

The add-on is configured natively through the Home Assistant UI.

### Global Settings
* **`endpoint_address`**: The full URL to your LLM API (e.g., `http://192.168.1.50:11434/api/generate` for Ollama).
* **`auth_token`**: A secret string you create. You must include this in your Home Assistant REST commands for security.
* **`max_concurrent_requests`**: How many generation tasks can run at once. 
* **`timeout`**: How long (in seconds) the server will wait for the AI to respond before giving up.
* **`log_level`**: Set to `INFO` for standard use, or `DEBUG` if you are troubleshooting your prompts.

### Endpoint Settings (The "Channels")
You can create multiple "endpoints" (e.g., `greeting`, `security_alert`, `weather`). Each has its own rules:
* **`max_buffer_size`**: How many replies to keep ready in the database.
* **`maintain_max_buffer`**: If `true`, the server will automatically generate a new reply every time you "consume" one from the buffer.
* **`prompt_for_buffer`**: The specific instruction sent to the AI (e.g., "Tell a joke about robots").
* **`model`**: The specific model name on your server (e.g., `llama3`, `mistral`, `phi3`).
* **`temperature`**: Controls creativity. `0.1` is very literal/robotic; `0.9` is very creative/random.
* **`fallback_replies`**: A list of simple text strings used if the AI server is offline or the buffer is empty.

### Example Endpoint:

```yaml
endpoints:
  blue_cat_poem:
    max_buffer_size: 10
    temperature: 0.9
    maintain_max_buffer: true
    prompt_for_buffer: "Write a short, 4-line whimsical poem about a mysterious blue cat."
    model: "llama3"
    fallback_replies:
      - "A sapphire cat with eyes so bright, slips through shadows in the night."
      - "Indigo fur and a silent tread, a blue cat sleeps on a velvet bed."
```

---

## 🤖 Home Assistant Integration

### REST Command Setup
Add this to your `configuration.yaml`:

```yaml
rest_command:
  get_ai_reply:
    url: "http://localhost:8000/read_buffer"
    method: POST
    headers:
      Authorization: "Bearer YOUR_SECRET_TOKEN"
      Content-Type: "application/json"
    payload: '{"name": "{{ buffer_name }}"}'
```

### Automation Example

```yaml
automation:
  - alias: "Instant AI Greeting"
    trigger:
      - platform: state
        entity_id: binary_sensor.front_door
        to: "on"
    action:
      - service: rest_command.get_ai_reply
        data:
          buffer_name: "example_reply"
        response_variable: ai_result
      - service: tts.google_say
        data:
          entity_id: media_player.living_room
          message: "{{ ai_result['reply'] }}"
```

## Example API References

**Read buffer:**
```
curl -X POST http://localhost:8000/read_buffer \
  -H "Authorization: Bearer YOUR_SECRET_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "blue_cat_poem",
    "remove_from_buffer": true
  }'
```

**Write to buffer:**
```
curl -X POST http://localhost:8000/write_buffer \
  -H "Authorization: Bearer YOUR_SECRET_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "blue_cat_poem",
    "count": 3,
    "prompt": "Write a funny poem about a blue cat eating cheese.",
    "clear": false
  }'
```

**List buffer:**
```
curl -X POST http://localhost:8000/list_buffer \
  -H "Authorization: Bearer YOUR_SECRET_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "buffer_name": "blue_cat_poem"
  }'
```

**Clear buffer:**
```
curl -X POST http://localhost:8000/clear_buffer \
  -H "Authorization: Bearer YOUR_SECRET_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "buffer_name": "blue_cat_poem"
  }'
```