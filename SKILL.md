---
name: opencode-responses-bridge-skill
version: 1.2.0
description: "Local stdlib-only proxy that adapts OpenAI Chat Completions to/from the Responses API so any OpenAI-compatible agent client (WorkBuddy, Cursor, Open WebUI, LobeChat, ...) can use Responses-API-only models such as OpenCode Go gpt-5.6-luna. Use when: setting up a Chat Completions to Responses API bridge, local proxy for responses-only models, fixing 'model only supports responses API', 'invalid_prompt' HTTP 400, 'custom model error 10000', or protocol transcoding for any Responses API endpoint (OPENCODE_UPSTREAM)."
agent_created: true
allowed-tools: python3, curl
metadata:
  openclaw:
    requires:
      bins:
        - python3
    envVars:
      - name: OPENCODE_UPSTREAM
        required: false
        description: Responses API endpoint to forward to (default https://opencode.ai/zen/go/v1/responses).
      - name: PROXY_HOST
        required: false
        description: Local listen host (default 127.0.0.1).
      - name: PROXY_PORT
        required: false
        description: Local listen port (default 8787).
      - name: BRIDGE_DEBUG
        required: false
        description: Set to 1 to log request headers (auth redacted) and body (first 8000 chars) and write debug dumps to the system temp dir; default off.
    emoji: "🔄"
    homepage: https://github.com/ANDYPENG09/opencode-responses-bridge-skill
    os:
      - windows
      - macos
      - linux
---

# OpenCode Responses Bridge (Responses API ↔ Chat Completions local adapter)

## Overview

Many AI clients' custom-model channels only send OpenAI **Chat Completions** requests, while
some upstream models (typically OpenCode Go's `gpt-5.6-luna`) only expose the OpenAI
**Responses API** — configuring them directly is bound to fail (typical errors:
`invalid_prompt` / `Invalid Responses API request` / WorkBuddy "custom model error 10000").

This skill provides a **zero-dependency local proxy**: the client sends Chat Completions to the
local proxy, the proxy translates them to the Responses API and forwards to the upstream, then
translates the reply back to Chat Completions (streaming SSE, tool calls, reasoning and
multimodal input included). Any client that supports a custom OpenAI-compatible model URL can
connect.

## Quick start

### 1. Get the proxy script
Copy the two files from `scripts/` to any stable directory (e.g. `~/responses-bridge/`):
- `proxy.py` (pure Python standard library, Python 3.8+, no dependencies)
- `start_proxy.bat` (Windows one-click launcher; on macOS/Linux run `python3 proxy.py`)

### 2. Start the proxy
```
python3 proxy.py        # listens on http://127.0.0.1:8787 by default
```
Optional env vars: `OPENCODE_UPSTREAM` (upstream Responses endpoint, defaults to OpenCode Go),
`PROXY_HOST` (default 127.0.0.1), `PROXY_PORT` (default 8787). The proxy relays the upstream key
from the inbound `Authorization: Bearer <key>` header, so the key is maintained in exactly one
place — the client's model config.

### 3. Smoke test (without a client)
```
curl http://127.0.0.1:8787/v1/chat/completions \
	-H "Authorization: Bearer YOUR_API_KEY" -H "Content-Type: application/json" \
	-d '{"model":"gpt-5.6-luna","messages":[{"role":"user","content":"hi"}],"stream":false}'
```
A HTTP 200 with a `chat.completion` structure means it works.

### 4. Configure the client
Point the client's custom-model URL at `http://127.0.0.1:8787/v1/chat/completions` and set the
model name to the actual upstream model ID (OpenCode Go gateway model IDs have **no prefix**,
e.g. `gpt-5.6-luna`). Per-client examples live in `examples/` (WorkBuddy `models.json`, generic
OpenAI-compatible client, curl).

### 5. Verify
Send a message from the client; a normal streaming reply means success.

## Core capabilities

- **Text & streaming**: non-streaming returns a standard `chat.completion`; streaming emits
  standard SSE (role opening → content deltas → `[DONE]`).
- **Tool calls**: `tools`/`tool_choice` mapped both ways; multi-round tool loops
  (assistant `tool_calls` → `function_call`, tool messages → `function_call_output`);
  concurrent streaming calls accumulate per `item_id` without dropping arguments.
- **Reasoning**: upstream reasoning summary → `reasoning_content` (streaming and non-streaming).
- **Multimodal input**: user `image_url` parts → `input_image` parts (base64 data URLs passed
  through as-is).
- **Configurable upstream**: `OPENCODE_UPSTREAM` can point at any OpenAI Responses
  API-compatible endpoint, not just OpenCode Go.

## Input / output contract

- **Inbound** (client → proxy): standard OpenAI Chat Completions request
  (`POST /v1/chat/completions`) with `messages` (system/user/assistant/tool), `tools`,
  `tool_choice`, `max_tokens`, `temperature`, `top_p`, `stream`.
- **Outbound** (proxy → upstream): Responses API request (`input`/`instructions`/`tools`/
  `max_output_tokens`).
- **Response**: standard Chat Completions (non-streaming JSON or SSE stream) including `usage`,
  `reasoning_content`, `tool_calls`.
- Full field mapping: `references/protocol-mapping.md`.

## Usage example

**Wire luna into WorkBuddy (`models.json`):**
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

**Expected output** (non-streaming):
```
{"id":"chatcmpl-...","object":"chat.completion","model":"gpt-5.6-luna",
	"choices":[{"index":0,"message":{"role":"assistant","content":"2 + 3 equals 5."},"finish_reason":"stop"}]}
```

More examples (tool calls / streaming / multimodal input-output pairs) in `examples/`.

## Known limitations

1. **OpenAI protocol family only**: the proxy targets OpenAI-compatible clients; clients that
   speak the Anthropic Messages protocol (e.g. Claude Code direct mode) need an extra
   Anthropic↔Responses adapter layer, out of scope for this skill.
2. **No prefix on model IDs**: OpenCode Go gateway model IDs are `gpt-5.6-luna`, not
   `opencode-go/gpt-5.6-luna`; a prefixed ID returns 401. Follow each upstream's own docs.
3. **Default upstream is OpenCode Go**: `opencode.ai` may be unreachable from mainland China;
   set `OPENCODE_UPSTREAM` to a reachable Responses API endpoint as needed.
4. **Image input**: only `image_url` parts are converted (URL or base64 data URL); multimodal
   capability depends on the upstream model supporting `input_image`.
5. **Security boundary**: the proxy listens on `127.0.0.1` (default) and is not exposed to the
   network; keys never touch disk or code. By default only a summary log is written, located in
   the system temp directory (zero runtime writes inside the skill folder); setting
   `BRIDGE_DEBUG=1` records request bodies (first 8000 chars) and debug dumps in the temp
   directory — request bodies may contain sensitive conversation content, so turn it off after
   troubleshooting.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| 401 | model ID carries `opencode-go/` prefix | drop the prefix; see `references/protocol-mapping.md` §2 |
| 403 `error code: 1010` | Cloudflare blocks the default UA | the proxy ships a browser UA; don't hit the endpoint with bare urllib |
| 400 `invalid_prompt` (client reports "custom model error 10000") | assistant messages in the conversation history have array `content` whose `text` parts weren't re-typed to `output_text` | upgrade to the latest `scripts/proxy.py`; "first message works, fails once there is history" is the signature of this bug |
| returns a `response` object instead of `chat.completion` | hit `/responses` directly | go through the proxy `http://127.0.0.1:8787/v1/chat/completions` |
| port already in use | proxy started twice | change `PROXY_PORT` or kill the old process |
| client errors but curl works | request-shape difference | default log is summary-only (system temp dir `%TEMP%/opencode-responses-bridge/`); with `BRIDGE_DEBUG=1` the log records headers and the first 8000 chars of the body, plus `proxy-last-upstream.json` / `proxy-last-error.txt` |

## Resources

- `scripts/proxy.py` — the adapter proxy (only runtime entry, zero dependencies)
- `scripts/start_proxy.bat` — Windows launcher
- `references/protocol-mapping.md` — full field mapping, SSE event table, tested samples and
  extension guide
- `examples/` — per-client integration examples (WorkBuddy / generic OpenAI-compatible / curl
  input-output pairs)
