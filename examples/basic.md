# Example: curl input/output pairs

The requests below hit the local proxy `http://127.0.0.1:8787/v1/chat/completions` directly,
with the key in the `Authorization: Bearer <your-upstream-key>` header. All responses are
standard OpenAI Chat Completions structures.

## 1. Text (non-streaming)

```
curl http://127.0.0.1:8787/v1/chat/completions \
	-H "Authorization: Bearer YOUR_API_KEY" -H "Content-Type: application/json" \
	-d '{"model":"gpt-5.6-luna","messages":[{"role":"user","content":"What is 2+3? Answer in one short sentence."}],"max_tokens":80,"stream":false}'
```

Expected output (excerpt):
```
{
	"object": "chat.completion",
	"model": "gpt-5.6-luna",
	"choices": [
		{"index": 0, "message": {"role": "assistant", "content": "2 + 3 equals 5."}, "finish_reason": "stop"}
	],
	"usage": {"prompt_tokens": 19, "completion_tokens": 12, "total_tokens": 31}
}
```

## 2. Streaming (SSE)

```
curl -N http://127.0.0.1:8787/v1/chat/completions \
	-H "Authorization: Bearer YOUR_API_KEY" -H "Content-Type: application/json" \
	-d '{"model":"gpt-5.6-luna","messages":[{"role":"user","content":"Count 1 to 5, one per line."}],"max_tokens":80,"stream":true}'
```

Expected output (excerpt):
```
data: {"choices":[{"delta":{"role":"assistant"},"finish_reason":null}]}
data: {"choices":[{"delta":{"content":"1\n2\n3\n4\n5"},"finish_reason":null}]}
data: {"choices":[{"delta":{},"finish_reason":"stop"}]}
data: [DONE]
```

## 3. Tool calls

```
curl http://127.0.0.1:8787/v1/chat/completions \
	-H "Authorization: Bearer YOUR_API_KEY" -H "Content-Type: application/json" \
	-d '{"model":"gpt-5.6-luna",
		"messages":[{"role":"user","content":"What is the weather in Shanghai? Use the get_weather tool."}],
		"tools":[{"type":"function","function":{"name":"get_weather","description":"Get weather for a city",
			"parameters":{"type":"object","properties":{"city":{"type":"string"}},"required":["city"]}}}],
		"tool_choice":"auto","stream":false}'
```

Expected output (excerpt):
```
{
	"choices": [
		{"index": 0,
			"message": {"role": "assistant", "content": null,
				"tool_calls": [{"id": "call_...", "type": "function",
					"function": {"name": "get_weather", "arguments": "{\"city\":\"Shanghai\"}"}}]},
			"finish_reason": "tool_calls"}
	]
}
```

## 4. Multimodal input (image)

```
curl http://127.0.0.1:8787/v1/chat/completions \
	-H "Authorization: Bearer YOUR_API_KEY" -H "Content-Type: application/json" \
	-d '{"model":"gpt-5.6-luna",
		"messages":[{"role":"user","content":[
			{"type":"text","text":"What color is this image? Answer in one word."},
			{"type":"image_url","image_url":{"url":"data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="}}
		]}],
		"max_tokens":300,"stream":false}'
```

Expected output (excerpt): `content` is the model's answer about the image (e.g. "Gray"); the
upstream reasoning summary appears in the `reasoning_content` field.
