# OpenCode Responses Bridge (Responses API ↔ Chat Completions local adapter)

## Overview

A zero-dependency local protocol-conversion proxy that solves: "AI clients' custom-model
channels only support OpenAI Chat Completions, while some upstream models (such as OpenCode
Go's gpt-5.6-luna) only expose the Responses API."

The proxy translates the client's Chat Completions request into the Responses API, forwards it
to the upstream, and translates the response back to Chat Completions. Supports:
- Text generation and streaming SSE
- Tool calls (tool_calls ↔ function_call, including multi-round tool loops and concurrent calls)
- Reasoning summary passthrough (reasoning_content)
- Multimodal image input (image_url → input_image)
- Any Responses API endpoint (configurable via OPENCODE_UPSTREAM)

## Use cases

- Use Responses-API-only models in OpenAI-compatible clients
- Any local compatibility layer that needs Chat Completions ↔ Responses API conversion

## Install & use

1. Copy `scripts/proxy.py` (pure Python standard library, Python 3.8+, no dependencies).
2. Run `python3 proxy.py` (default listens on `127.0.0.1:8787`), or double-click
   `scripts/start_proxy.bat`.
3. In the client, point the model URL at `http://127.0.0.1:8787/v1/chat/completions` and set the
   model ID to the actual upstream ID.
4. Smoke test and per-client examples: see `README.md` and `examples/`.

Detailed setup steps and troubleshooting: `SKILL.md`; protocol field mapping:
`references/protocol-mapping.md`.

## Dependencies

- Python 3.8+ (standard library only)
- No third-party packages

## Author

- **ANDYPENG09**

## Version

- v1.2.0 (2026-08-08): security hardening — logging is summary-only by default and moved to the
  system temp directory; new `BRIDGE_DEBUG` switch controls body logging and debug dumps; zero
  runtime writes inside the skill folder; docs now accurately disclose the logging behavior.
- v1.1.0 (2026-08-06): generalization — any Responses API upstream configurable, examples and
  troubleshooting improved, multi-platform publishing (WorkBuddy/ClawHub/GitHub).
- v1.0.0 (2026-08-06): first release, verified against OpenCode Go `gpt-5.6-luna` /
  `deepseek-v4-flash`.
