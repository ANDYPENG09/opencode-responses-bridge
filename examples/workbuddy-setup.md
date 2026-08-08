# Example: wire into WorkBuddy (custom model)

1. Start the proxy: double-click `scripts/start_proxy.bat`, or run `python3 proxy.py`.
2. Edit the WorkBuddy custom-model config file `~/.workbuddy/models.json`, add/update an entry.

```
{
	"id": "gpt-5.6-luna",
	"name": "gpt-5.6-luna (via proxy)",
	"vendor": "Custom",
	"url": "http://127.0.0.1:8787/v1/chat/completions",
	"apiKey": "sk-your-upstream-key",
	"supportsToolCall": true,
	"supportsImages": true,
	"supportsReasoning": true,
	"useCustomProtocol": false
}
```

Key points:

- `url` must point at the proxy's Chat Completions endpoint (do **not** hit the upstream
  `/responses` directly).
- `apiKey` is the upstream (e.g. OpenCode Go) API key; the proxy relays it from the inbound
  `Authorization` header.
- The model ID must be the actual upstream ID (OpenCode Go gateway has **no prefix**, e.g.
  `gpt-5.6-luna`).
- Fully quit and restart WorkBuddy (quit from the system tray, not just close the window), then
  select the model in the model picker.

Known symptoms and handling:

- If "the first message works but 10000 appears once there is history": upgrade to the latest
  `scripts/proxy.py` (assistant history message content array type conversion issue).
- If the proxy is not running, the client cannot connect; first run `python3 proxy.py`, then
  `curl http://127.0.0.1:8787/health` should return `{"status":"ok"}`.
