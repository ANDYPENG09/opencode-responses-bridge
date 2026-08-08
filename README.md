# OpenCode Responses Bridge (Chat Completions ↔ Responses API local adapter)

> **🌏 Languages:** [English](README.md) · [中文](README.zh-CN.md)

> **Skill Overview**
>
> **OpenCode Responses Bridge** is a zero-dependency local proxy that adapts OpenAI
> **Chat Completions** ↔ **Responses API**. It lets any OpenAI-compatible agent client
> (WorkBuddy, Cursor, Open WebUI, LobeChat, ...) use Responses-API-only models such as
> OpenCode Go `gpt-5.6-luna` — with streaming SSE, tool calls, reasoning passthrough and
> multimodal input. Python 3.8+, standard library only, no installs.
>
> **How to install**
>
> - **WorkBuddy / SkillHub:** install the skill from SkillHub (zip or CLI), then copy
>   `scripts/proxy.py` + `scripts/start_proxy.bat` to a stable folder and run it.
> - **ClawHub:** `clawhub install opencode-responses-bridge-skill`
> - **GitHub:** `git clone https://github.com/ANDYPENG09/opencode-responses-bridge-skill`
>
> **How to invoke**
>
> - Start the proxy: `python3 proxy.py` (defaults to `http://127.0.0.1:8787`).
> - Point your client's custom model URL at `http://127.0.0.1:8787/v1/chat/completions`.
> - Smoke test: `curl http://127.0.0.1:8787/v1/chat/completions -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" -d '{"model":"gpt-5.6-luna","messages":[{"role":"user","content":"hi"}],"stream":false}'`

---

## What problem does it solve

Custom-model channels in AI agent clients typically only speak the OpenAI **Chat Completions**
protocol, while some upstream models (typically OpenCode Go's `gpt-5.6-luna`) only expose the
OpenAI **Responses API**. Direct configuration always fails, with common errors:

- `HTTP 400 invalid_prompt` / `Invalid Responses API request`
- WorkBuddy "custom model error 10000"
- First message works, but **any message after history fails** (assistant history message
  `content` arrays are not converted)

This proxy performs a **local protocol translation**: client → Chat Completions → proxy →
Responses API → upstream → and back.

## Features

- **Zero dependencies**: pure Python standard library, Python 3.8+, no pip install
- **Streaming SSE**: fully translated (role first → content deltas → `[DONE]`)
- **Tool calls**: `tools`/`tool_choice` bidirectional mapping, multi-round tool loops,
  concurrent streaming function calls with no lost arguments
- **Reasoning**: upstream reasoning summaries → `reasoning_content` passthrough
- **Multimodal**: `image_url` (URL / base64 data URL) → `input_image`
- **Configurable upstream**: `OPENCODE_UPSTREAM` points to any Responses API endpoint,
  not limited to OpenCode Go
- **Single-point key management**: the proxy relays the key from the inbound `Authorization`
  header; it never writes keys to disk or code

## Quick start

```
# 1. Start the proxy (on Windows, double-click scripts/start_proxy.bat)
python3 proxy.py                      # defaults to http://127.0.0.1:8787
# 2. Smoke test
curl http://127.0.0.1:8787/v1/chat/completions \
	-H "Authorization: Bearer YOUR_API_KEY" -H "Content-Type: application/json" \
	-d '{"model":"gpt-5.6-luna","messages":[{"role":"user","content":"hi"}],"stream":false}'
# 3. Point your client's custom model URL at:
# http://127.0.0.1:8787/v1/chat/completions
```

## Configuration

| Env var | Default | Description |
|---|---|---|
| `OPENCODE_UPSTREAM` | `https://opencode.ai/zen/go/v1/responses` | Upstream Responses API endpoint |
| `PROXY_HOST` | `127.0.0.1` | Listen address (do not expose publicly) |
| `PROXY_PORT` | `8787` | Listen port |

> Note: OpenCode Go gateway model IDs have **no prefix** (`gpt-5.6-luna`, not
> `opencode-go/gpt-5.6-luna`); a prefix returns 401.

## Platform & agent client compatibility

| Client | Compatibility | Notes |
|---|---|---|
| WorkBuddy | ✅ Verified | Point custom model `url` at the proxy, use upstream model ID |
| Any OpenAI-compatible client (Cursor / Open WebUI / LobeChat / NextChat ...) | ✅ Protocol-level | Any client that can point a model base URL at the proxy |
| OpenClaw / Claw / QClaw | ⚠️ Config-dependent | Point the OpenAI-compatible endpoint at the proxy |
| Claude Code (Anthropic Messages protocol) | ❌ Not supported | Requires an Anthropic↔Responses adapter layer, out of scope |

| OS | Compatibility | Notes |
|---|---|---|
| Windows | ✅ Verified | `start_proxy.bat` or `python proxy.py` |
| macOS / Linux | ✅ | `python3 proxy.py`; mind firewall/port |

## Per-client examples

- `examples/basic.md` — curl input/output pairs (text, streaming, tool calls, multimodal)
- `examples/workbuddy-setup.md` — WorkBuddy `models.json` integration
- `examples/generic-client-setup.md` — generic OpenAI-compatible client integration

## Debugging

By default the proxy appends a one-line **summary** per request (method, path, model, status,
latency) to `proxy-requests.log` under the system temp directory
(`%TEMP%/opencode-responses-bridge/` on Windows, `/tmp/opencode-responses-bridge/` elsewhere);
the Authorization header is redacted and **no files are ever created inside the skill folder**.
When "client errors but curl works", restart with `BRIDGE_DEBUG=1`:

- the log additionally records request headers (Authorization redacted) and the request body
  (first 8000 chars);
- debug dumps `proxy-last-upstream.json` (upstream request) and `proxy-last-error.txt`
  (upstream error) are written in overwrite mode to the same temp directory.

> Caution: with `BRIDGE_DEBUG=1`, request bodies (conversation content, tool arguments) are
> written to local files in plaintext — disable it after troubleshooting.

## Security

- Listens on `127.0.0.1` by default, not exposed to the network
- Keys are never written to disk or code; relayed only from the inbound header
- Logging is summary-only by default and lives in the system temp directory; request bodies
  are logged in plaintext only when `BRIDGE_DEBUG=1` is set — keep it off in production
- Upstream requests use a browser UA to bypass Cloudflare's default-UA block (`error code: 1010`)

## License

[MIT-0](./LICENSE) — anyone may freely use, modify, and redistribute (including commercially)
without attribution.

## Author

- **ANDYPENG09**
