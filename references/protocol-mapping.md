# Responses API <-> Chat Completions protocol mapping reference

This file documents the protocol conversion details of the proxy `scripts/proxy.py` for
troubleshooting or extension. The mapping follows the official OpenAI Responses API / Chat
Completions specs and applies to any OpenAI-compatible upstream; findings were verified against
the OpenCode Go gateway on 2026-08-06 (models `gpt-5.6-luna`, `deepseek-v4-flash`).

## 1. Endpoint vs model capability (OpenCode Go, tested)

| Model | Endpoint | Protocol | Directly usable in WorkBuddy |
|---|---|---|---|
| `deepseek-v4-flash` | `https://opencode.ai/zen/go/v1/chat/completions` | Chat Completions | ✅ configure directly |
| `gpt-5.6-luna` | `https://opencode.ai/zen/go/v1/responses` | Responses API | ❌ needs this proxy |

## 2. Key pitfalls

- **No prefix on model IDs**: the Go gateway model IDs are `gpt-5.6-luna` / `deepseek-v4-flash`.
  Adding an `opencode-go/` prefix returns **HTTP 401** (the gateway judges permission by the
  model name and assumes no access).
- **Cloudflare blocking**: urllib's default UA triggers Cloudflare `error code: 1010` (403).
  The proxy ships a browser UA plus `Accept: application/json, text/event-stream`.
- **Auth**: `Authorization: Bearer <key>`; Go and Zen share the same console API key; once you
  subscribe to Go, the key works against the Go endpoint.
- **assistant/content arrays must be converted (important bug, fixed 2026-08-06)**: WorkBuddy
  serializes assistant message `content` as an array (`[{"type":"text","text":...}]`) in the
  conversation history. The `text` part type does **not** exist in the Responses API; passing it
  through raw makes the gateway return `HTTP 400 invalid_prompt` (`Invalid Responses API
  request`). The proxy must re-type every text part to `input_text` (user) or `output_text`
  (assistant), and image parts to `input_image`.
  Symptom: the first message of a session works; once the history contains an assistant array
  message, the client reports `custom model xxx error 10000` (the Trace ID only appears on the
  WorkBuddy side).

## 3. Request conversion (Chat Completions -> Responses API)

| Chat Completions | Responses API |
|---|---|
| `messages[]` role=system | top-level `instructions` (joined; when content is an array, join its text parts) |
| `messages[]` role=user content=string | `{"role":"user","content":[{"type":"input_text","text":...}]}` |
| user content part `{"type":"text","text":...}` | `{"type":"input_text","text":...}` |
| user content part `{"type":"image_url","image_url":{"url":...}}` | `{"type":"input_image","image_url":...}` |
| assistant content=string | `{"role":"assistant","content":[{"type":"output_text","text":...}]}` |
| assistant content=array `[{"type":"text",...}]` | `{"role":"assistant","content":[{"type":"output_text","text":...}]}` (**must re-type, else invalid_prompt**) |
| assistant `tool_calls[]` | `{"type":"function_call","call_id","name","arguments"}` (arguments is a JSON string) |
| role=tool message | `{"type":"function_call_output","call_id","output"}` |
| `tools[]` `{type:function,function:{name,description,parameters}}` | `{type:function,name,description,parameters}` |
| `tool_choice` `{type:function,function:{name}}` | `{type:function,name}` |
| `max_tokens` / `max_completion_tokens` | `max_output_tokens` |

## 4. Response conversion (Responses API -> Chat Completions)

| Responses API | Chat Completions |
|---|---|
| `output[].type=message` + `content[].type=output_text` | `choices[0].message.content` |
| `output[].type=function_call` (with `call_id`/`name`/`arguments`) | `choices[0].message.tool_calls[]`, `finish_reason=tool_calls` |
| `output[].type=reasoning` + `summary[].text` | `message.reasoning_content` |
| `usage.input_tokens/output_tokens/total_tokens` | `usage.prompt_tokens/completion_tokens/total_tokens` |

## 5. Streaming (SSE) event mapping

| Responses event | Chat Completions output |
|---|---|
| `response.created` | (implicit) first `delta.role=assistant` chunk |
| `response.output_text.delta` | `delta.content` chunk |
| `response.reasoning_summary_text.delta` | `delta.reasoning_content` chunk |
| `response.output_item.added` (function_call) | start accumulating the call (cached per `item_id`) |
| `response.function_call_arguments.delta` | append `arguments` |
| `response.output_item.done` | finalize arguments |
| stream end | emit all `tool_calls` deltas at once, then `finish_reason` + `[DONE]` |

Concurrent function calls are distinguished per `item_id` so no arguments are dropped.

## 6. Tested response samples

`gpt-5.6-luna` non-streaming (excerpt):
```
{"id":"gen-...","object":"response","model":"gpt-5.6-luna",
	"output":[{"type":"message","content":[{"type":"output_text","text":"2 + 3 equals 5."}]}],
	"usage":{"input_tokens":19,"output_tokens":12,"total_tokens":31}}
```

`deepseek-v4-flash` non-streaming (excerpt):
```
{"id":"...","object":"chat.completion","model":"deepseek-v4-flash",
	"choices":[{"message":{"role":"assistant","content":"2 + 3 = 5","reasoning_content":"..."}}]}
```

## 7. Extension guide

- Switch upstream: set `OPENCODE_UPSTREAM` (default `https://opencode.ai/zen/go/v1/responses`).
- Switch port: `PROXY_PORT` (default 8787); bind address: `PROXY_HOST` (default 127.0.0.1).
- The proxy relays the key from the inbound `Authorization` header; the key is maintained in
  exactly one place, the client's model config.
- Debug logging: set `BRIDGE_DEBUG=1` to log request headers (auth redacted) and request body
  (first 8000 chars), and to write `proxy-last-upstream.json` / `proxy-last-error.txt` under the
  system temp directory `opencode-responses-bridge/`. Default logs are summary-only.
