# 示例：curl 输入/输出对

以下请求直接打向本地代理 `http://127.0.0.1:8787/v1/chat/completions`，密钥放在
`Authorization: Bearer <你的上游key>` 头。返回均为标准 OpenAI Chat Completions 结构。

## 1. 文本（非流式）

```
curl http://127.0.0.1:8787/v1/chat/completions \
	-H "Authorization: Bearer YOUR_API_KEY" -H "Content-Type: application/json" \
	-d '{"model":"gpt-5.6-luna","messages":[{"role":"user","content":"What is 2+3? Answer in one short sentence."}],"max_tokens":80,"stream":false}'
```

期望输出（节选）：
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

## 2. 流式（SSE）

```
curl -N http://127.0.0.1:8787/v1/chat/completions \
	-H "Authorization: Bearer YOUR_API_KEY" -H "Content-Type: application/json" \
	-d '{"model":"gpt-5.6-luna","messages":[{"role":"user","content":"Count 1 to 5, one per line."}],"max_tokens":80,"stream":true}'
```

期望输出（节选）：
```
data: {"choices":[{"delta":{"role":"assistant"},"finish_reason":null}]}
data: {"choices":[{"delta":{"content":"1\n2\n3\n4\n5"},"finish_reason":null}]}
data: {"choices":[{"delta":{},"finish_reason":"stop"}]}
data: [DONE]
```

## 3. 工具调用

```
curl http://127.0.0.1:8787/v1/chat/completions \
	-H "Authorization: Bearer YOUR_API_KEY" -H "Content-Type: application/json" \
	-d '{"model":"gpt-5.6-luna",
		"messages":[{"role":"user","content":"What is the weather in Shanghai? Use the get_weather tool."}],
		"tools":[{"type":"function","function":{"name":"get_weather","description":"Get weather for a city",
			"parameters":{"type":"object","properties":{"city":{"type":"string"}},"required":["city"]}}}],
		"tool_choice":"auto","stream":false}'
```

期望输出（节选）：
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

## 4. 多模态输入（图片）

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

期望输出（节选）：`content` 为模型对图片的回答（如 "Gray"），上游推理摘要出现在
`reasoning_content` 字段。
