# Ollama Buffer Server

This app acts as a high-speed middleman between Home Assistant and your local Ollama server. It pre-generates and stores AI replies in a local SQLite database so your automations get instant responses without waiting for the LLM to think.

## Configuration

### Connection
- **Ollama API Endpoint**: The internal or external URL to your Ollama API. 
- **Authorization Token**: A secret key of your choice to secure the buffer API.

### Buffer Endpoints
You can define multiple "buffers" for different use cases (e.g., one for weather, one for house status).
- **Name**: The unique ID for this buffer.
- **Max Buffer Size**: How many replies to keep ready.
- **Prompt for Buffer**: The instruction used to generate the pre-filled replies.

## How to use
Once the app is running, you can fetch a reply using a REST command in Home Assistant:

```yaml
rest_command:
  get_ai_reply:
    url: "http://localhost:8000/read_buffer"
    method: post
    headers:
      Authorization: "Bearer YOUR_TOKEN"
    payload: '{"name": "weather"}'
```