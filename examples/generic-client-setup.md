# Example: generic OpenAI-compatible client

Any client that supports a "custom OpenAI-compatible model base URL" (Cursor, Open WebUI,
LobeChat, NextChat, one-api-style gateways, ...) can connect to this proxy:

1. Start the proxy: `python3 proxy.py` (default `http://127.0.0.1:8787`).
2. Configure a custom model in the client:
   - **Base URL / API URL**: `http://127.0.0.1:8787/v1`
   - **Model name**: the actual upstream model ID (e.g. `gpt-5.6-luna`)
   - **API Key**: your upstream API key (required; the proxy relays it to the upstream)
   - **Capability toggles**: enable tool calling / vision / reasoning according to the upstream
     model's actual capabilities

How it works: the client sends Chat Completions requests to
`http://127.0.0.1:8787/v1/chat/completions` following the OpenAI-compatible protocol; the proxy
translates them to the Responses API, forwards to the upstream, and translates the reply back
to Chat Completions for the client.

Notes:

- The client must be able to reach `127.0.0.1`; if the client and the proxy are on different
  machines, use the LAN address instead and assess listening security yourself (`PROXY_HOST`
  binds to localhost only by default).
- Clients that only speak the Anthropic Messages protocol (e.g. Claude Code direct mode) cannot
  be used directly — they need an extra Anthropic↔Responses adapter layer.
