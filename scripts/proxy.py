#!/usr/bin/env python3
"""
OpenCode Responses Bridge — local adapter: OpenAI Chat Completions <-> Responses API.

Why it exists:
  Many agent clients' custom-model channels only speak OpenAI *Chat Completions*.
  Some upstreams (e.g. OpenCode Go, model gpt-5.6-luna) only expose the OpenAI
  *Responses API*. This bridge accepts Chat Completions requests on
  http://127.0.0.1:8787/v1/chat/completions, translates them to the Responses
  API, forwards to the upstream, and translates the reply back to Chat
  Completions (streaming SSE supported). Works with ANY Responses API endpoint
  (set OPENCODE_UPSTREAM).

Features:
  - Text + streaming (SSE)
  - Tool calls: single- and multi-round, multiple concurrent calls
    (function_call <-> tool_calls), tool_choice mapping
  - Reasoning passthrough: upstream reasoning text -> reasoning_content
  - Multimodal input: user image_url parts -> input_image parts
  - Upstream URL / host / port configurable via environment variables
  - API key relayed from the incoming Authorization header, so the key lives
    in exactly one place (the client's model config)

Usage:
  python proxy.py                              # defaults 127.0.0.1:8787
  PROXY_PORT=9000 python proxy.py              # custom port
  OPENCODE_UPSTREAM=https://... python proxy.py  # custom upstream

Smoke test:
  curl http://127.0.0.1:8787/v1/chat/completions \
    -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
    -d '{"model":"gpt-5.6-luna","messages":[{"role":"user","content":"hi"}],"stream":false}'
"""

import json
import os
import time
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

UPSTREAM = os.environ.get("OPENCODE_UPSTREAM", "https://opencode.ai/zen/go/v1/responses")
LISTEN_HOST = os.environ.get("PROXY_HOST", "127.0.0.1")
LISTEN_PORT = int(os.environ.get("PROXY_PORT", "8787"))

# Cloudflare rejects Python-urllib's default UA (error 1010); spoof a browser UA.
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "proxy-requests.log")
FULL_REQ_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "proxy-last-request.json")
FULL_UP_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "proxy-last-upstream.json")
FULL_ERR_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "proxy-last-error.txt")


def _log(msg):
    """Append a line to proxy-requests.log (best-effort, never raises)."""
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:
        pass


def _dump(path, text):
    """Overwrite a debug dump file (best-effort, never raises)."""
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
    except Exception:
        pass


# --------------------------------------------------------------------------
# Chat Completions -> Responses API
# --------------------------------------------------------------------------
def _convert_tool(tool):
    """OpenAI chat 'function' tool -> Responses API function tool."""
    if tool.get("type") == "function":
        fn = tool.get("function", {})
        return {
            "type": "function",
            "name": fn.get("name"),
            "description": fn.get("description", ""),
            "parameters": fn.get("parameters", {}),
        }
    return tool


def _convert_tool_choice(tc):
    if tc is None:
        return None
    if isinstance(tc, str):
        return tc  # "auto" / "required" / "none"
    if tc.get("type") == "function":
        return {"type": "function", "name": tc.get("function", {}).get("name")}
    return tc


def _content_to_parts(content, target_type="input_text"):
    """Convert Chat Completions content (str or parts list) into Responses API parts.

    Chat Completions uses part types 'text'/'image_url'; the Responses API uses
    'input_text'/'output_text'/'input_image'. Passing 'text' parts through raw
    makes the upstream return invalid_prompt, so every part is re-typed here.
    target_type is the text part type to emit ('input_text' for user, 'output_text'
    for assistant). Images are always emitted as 'input_image' (assistant history
    normally has no images).
    """
    if isinstance(content, str):
        return [{"type": target_type, "text": content}]
    parts = []
    if isinstance(content, list):
        for p in content:
            if isinstance(p, str):
                parts.append({"type": target_type, "text": p})
                continue
            if not isinstance(p, dict):
                continue
            t = p.get("type")
            if t in ("text", "input_text", "output_text"):
                txt = p.get("text")
                if txt:
                    parts.append({"type": target_type, "text": txt})
            elif t == "image_url":
                url = p.get("image_url")
                if isinstance(url, dict):
                    url = url.get("url")
                if url:
                    parts.append({"type": "input_image", "image_url": url})
    return parts or None


def _messages_to_input(messages):
    """Convert a Chat Completions message list into a Responses API input list."""
    items = []
    for m in messages:
        role = m.get("role")
        content = m.get("content")

        if role == "system":
            # system messages are folded into top-level 'instructions' at call site
            continue

        if role == "user":
            conv = _content_to_parts(content, target_type="input_text")
            if conv:
                items.append({"role": "user", "content": conv})
            continue

        if role == "assistant":
            for tc in m.get("tool_calls", []) or []:
                fn = tc.get("function", {})
                items.append(
                    {
                        "type": "function_call",
                        "call_id": tc.get("id"),
                        "name": fn.get("name"),
                        "arguments": fn.get("arguments", ""),
                    }
                )
            if content:
                conv = _content_to_parts(content, target_type="output_text")
                if conv:
                    items.append({"role": "assistant", "content": conv})
            continue

        if role == "tool":
            items.append(
                {
                    "type": "function_call_output",
                    "call_id": m.get("tool_call_id"),
                    "output": content if isinstance(content, str) else json.dumps(content),
                }
            )
            continue

    return items


def build_responses_payload(req):
    messages = req.get("messages", [])
    system_texts = []
    for m in messages:
        if m.get("role") == "system" and m.get("content"):
            c = m["content"]
            if isinstance(c, str):
                system_texts.append(c)
            elif isinstance(c, list):
                for p in c:
                    if isinstance(p, str):
                        system_texts.append(p)
                    elif isinstance(p, dict) and p.get("text"):
                        system_texts.append(p["text"])
    payload = {
        "model": req.get("model", "gpt-5.6-luna"),
        "input": _messages_to_input(messages),
        "stream": bool(req.get("stream", False)),
    }
    if system_texts:
        payload["instructions"] = "\n\n".join(system_texts)
    if "max_tokens" in req:
        payload["max_output_tokens"] = req["max_tokens"]
    elif "max_completion_tokens" in req:
        payload["max_output_tokens"] = req["max_completion_tokens"]
    if req.get("tools"):
        payload["tools"] = [_convert_tool(t) for t in req["tools"]]
    if req.get("tool_choice"):
        payload["tool_choice"] = _convert_tool_choice(req["tool_choice"])
    for k in ("temperature", "top_p"):
        if k in req:
            payload[k] = req[k]
    return payload


# --------------------------------------------------------------------------
# Responses API -> Chat Completions
# --------------------------------------------------------------------------
def _extract_text_tools_reasoning(resp):
    text_parts, tool_calls, reasoning_parts = [], [], []
    for item in resp.get("output", []) or []:
        t = item.get("type")
        if t == "message":
            for c in item.get("content", []) or []:
                if c.get("type") == "output_text":
                    text_parts.append(c.get("text", ""))
        elif t == "function_call":
            tool_calls.append(
                {
                    "id": item.get("call_id") or item.get("id"),
                    "type": "function",
                    "function": {
                        "name": item.get("name"),
                        "arguments": item.get("arguments", ""),
                    },
                }
            )
        elif t == "reasoning":
            for s in item.get("summary", []) or []:
                reasoning_parts.append(s.get("text", ""))
    return "".join(text_parts), tool_calls, "".join(reasoning_parts)


def build_chat_response(resp, model):
    text, tool_calls, reasoning = _extract_text_tools_reasoning(resp)
    message = {"role": "assistant", "content": text if text else None}
    if reasoning:
        message["reasoning_content"] = reasoning
    if tool_calls:
        message["tool_calls"] = tool_calls
    usage = resp.get("usage", {}) or {}
    return {
        "id": "chatcmpl-" + str(resp.get("id", "local")),
        "object": "chat.completion",
        "created": int(resp.get("created_at") or time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": message,
                "finish_reason": "tool_calls" if tool_calls else "stop",
            }
        ],
        "usage": {
            "prompt_tokens": usage.get("input_tokens", 0),
            "completion_tokens": usage.get("output_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
        },
    }


# --------------------------------------------------------------------------
# Streaming
# --------------------------------------------------------------------------
def _sse(obj):
    return "data: " + json.dumps(obj, ensure_ascii=False) + "\n\n"


def _chunk(model, delta, finish=None):
    return {
        "id": "chatcmpl-local",
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model,
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
    }


def _stream_from_responses(upstream_body, model, wfile):
    """Read Responses API SSE and write Chat Completions SSE to wfile."""
    wfile.write(_sse(_chunk(model, {"role": "assistant"})).encode("utf-8"))
    wfile.flush()

    call_map = {}  # item_id -> {id, name, arguments}
    call_order = []

    for raw in upstream_body:
        line = raw.decode("utf-8", "replace").strip()
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if data == "[DONE]":
            continue
        try:
            evt = json.loads(data)
        except json.JSONDecodeError:
            continue
        etype = evt.get("type")

        if etype == "response.output_text.delta":
            delta = evt.get("delta", "")
            if delta:
                wfile.write(_sse(_chunk(model, {"content": delta})).encode("utf-8"))
                wfile.flush()

        elif etype == "response.reasoning_summary_text.delta":
            delta = evt.get("delta", "")
            if delta:
                wfile.write(_sse(_chunk(model, {"reasoning_content": delta})).encode("utf-8"))
                wfile.flush()

        elif etype == "response.output_item.added":
            item = evt.get("item", {})
            if item.get("type") == "function_call":
                iid = item.get("id")
                call_map[iid] = {
                    "id": item.get("call_id") or iid,
                    "name": item.get("name"),
                    "arguments": item.get("arguments") or "",
                }
                call_order.append(iid)

        elif etype == "response.function_call_arguments.delta":
            iid = evt.get("item_id")
            if iid in call_map:
                call_map[iid]["arguments"] += evt.get("delta", "")

        elif etype == "response.output_item.done":
            item = evt.get("item", {})
            if item.get("type") == "function_call":
                iid = item.get("id")
                if iid in call_map:
                    call_map[iid]["name"] = item.get("name", call_map[iid]["name"])
                    call_map[iid]["arguments"] = item.get("arguments", call_map[iid]["arguments"])

    if call_order:
        tool_calls = [
            {
                "index": i,
                "id": call_map[k]["id"],
                "type": "function",
                "function": {
                    "name": call_map[k]["name"],
                    "arguments": call_map[k]["arguments"],
                },
            }
            for i, k in enumerate(call_order)
        ]
        wfile.write(_sse(_chunk(model, {"tool_calls": tool_calls})).encode("utf-8"))
        wfile.flush()

    finish = "tool_calls" if call_order else "stop"
    wfile.write(_sse(_chunk(model, {}, finish)).encode("utf-8"))
    wfile.write(b"data: [DONE]\n\n")
    wfile.flush()


# --------------------------------------------------------------------------
# HTTP handler
# --------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass  # quiet

    def do_GET(self):
        if self.path.rstrip("/") == "/health":
            body = b'{"status":"ok"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path.rstrip("/") not in ("/v1/chat/completions", "/chat/completions"):
            self.send_error(404, "not found")
            return

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else b"{}"

        # --- debug logging (auth redacted) ---
        _log(f">>> {self.command} {self.path}")
        _log(
            "headers: "
            + json.dumps(
                {
                    k: (v if k.lower() != "authorization" else "Bearer ***")
                    for k, v in self.headers.items()
                }
            )
        )
        _log("body(first 8000): " + body.decode("utf-8", "replace")[:8000])

        try:
            req = json.loads(body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            _log("<<< 400 bad json")
            self.send_error(400, "bad json")
            return

        model = req.get("model", "gpt-5.6-luna")
        auth = self.headers.get("Authorization", "")
        token = auth.replace("Bearer ", "").replace("Bearer", "").strip()

        payload = build_responses_payload(req)
        data = json.dumps(payload).encode("utf-8")
        _dump(FULL_UP_PATH, data.decode("utf-8", "replace"))

        upstream_req = urllib.request.Request(UPSTREAM, data=data, method="POST")
        upstream_req.add_header("Content-Type", "application/json")
        upstream_req.add_header("User-Agent", BROWSER_UA)
        upstream_req.add_header("Accept", "application/json, text/event-stream")
        if token:
            upstream_req.add_header("Authorization", "Bearer " + token)

        try:
            with urllib.request.urlopen(upstream_req, timeout=180) as resp:
                status = resp.getcode()
                ctype = resp.headers.get("Content-Type", "")
                if status != 200:
                    err = resp.read().decode("utf-8", "replace")
                    _dump(FULL_ERR_PATH, err)
                    _log(f"<<< upstream HTTP {status}: {err[:500]}")
                    self.send_response(status)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(err.encode("utf-8"))))
                    self.end_headers()
                    self.wfile.write(err.encode("utf-8"))
                    return

                if payload.get("stream") or "text/event-stream" in ctype:
                    _log("<<< 200 streaming")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.send_header("Cache-Control", "no-cache")
                    self.send_header("Connection", "keep-alive")
                    self.end_headers()
                    _stream_from_responses(resp, model, self.wfile)
                else:
                    raw = resp.read().decode("utf-8", "replace")
                    try:
                        upstream = json.loads(raw)
                    except json.JSONDecodeError:
                        upstream = {"raw": raw}
                    out = build_chat_response(upstream, model)
                    out_bytes = json.dumps(out, ensure_ascii=False).encode("utf-8")
                    _log("<<< 200 json")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(out_bytes)))
                    self.end_headers()
                    self.wfile.write(out_bytes)
        except urllib.error.HTTPError as e:
            err = e.read().decode("utf-8", "replace")
            _dump(FULL_ERR_PATH, err)
            _log(f"<<< upstream HTTPError {e.code}: {err[:500]}")
            self.send_response(e.code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(err.encode("utf-8"))))
            self.end_headers()
            self.wfile.write(err.encode("utf-8"))
        except Exception as e:  # noqa
            _log(f"<<< exception: {str(e)[:500]}")
            msg = json.dumps({"error": str(e)}).encode("utf-8")
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(msg)))
            self.end_headers()
            self.wfile.write(msg)


def main():
    server = ThreadingHTTPServer((LISTEN_HOST, LISTEN_PORT), Handler)
    print(
        f"OpenCode Responses Bridge listening on "
        f"http://{LISTEN_HOST}:{LISTEN_PORT}/v1/chat/completions"
    )
    print(f"Upstream: {UPSTREAM}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
