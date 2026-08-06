# Responses API <-> Chat Completions 协议映射参考

本文件记录代理 `scripts/proxy.py` 的协议转换细节，供排障或扩展时查阅。
映射遵循 OpenAI 官方 Responses API / Chat Completions 规范，适用于任意 OpenAI 兼容上游；
文中结论来自 2026-08-06 对 OpenCode Go 网关的实测（模型 `gpt-5.6-luna`、`deepseek-v4-flash`）。

## 1. 端点到模型能力对照（OpenCode Go，实测）

| 模型 | 端点 | 协议 | WorkBuddy 是否可直接用 |
|---|---|---|---|
| `deepseek-v4-flash` | `https://opencode.ai/zen/go/v1/chat/completions` | Chat Completions | ✅ 直接配置即可 |
| `gpt-5.6-luna` | `https://opencode.ai/zen/go/v1/responses` | Responses API | ❌ 需本代理转接 |

## 2. 关键坑

- **模型 ID 不带前缀**：Go 网关模型 ID 是 `gpt-5.6-luna` / `deepseek-v4-flash`。
  加 `opencode-go/` 前缀会返回 **HTTP 401**（网关按模型名做权限判定，误以为无权限）。
- **Cloudflare 拦截**：urllib 默认 UA 会触发 Cloudflare `error code: 1010`（403）。
  代理已内置浏览器 UA + `Accept: application/json, text/event-stream`。
- **鉴权**：`Authorization: Bearer <key>`，Go 与 Zen 共用控制台同一把 API key；
  订阅 Go 后该 key 对 Go 端点生效。
- **assistant/content 数组必须转换（重要 bug，2026-08-06 修复）**：WorkBuddy 的会话历史
  会把 assistant 消息的 `content` 序列化成数组（`[{"type":"text","text":...}]`）。
  Chat Completions 的 part 类型 `text` 在 Responses API 里**不存在**，原样透传会被网关判
  `HTTP 400 invalid_prompt`（`Invalid Responses API request`）。代理必须把所有文本 part
  统一重写为 `input_text`（user）或 `output_text`（assistant），图片 part → `input_image`。
  症状：新会话第一条能用，一旦对话有历史（含 assistant 数组消息）就报
  `自定义模型 xxx 错误 10000`（Trace ID 只出现在 WorkBuddy 侧）。

## 3. 请求转换（Chat Completions -> Responses API）

| Chat Completions | Responses API |
|---|---|
| `messages[]` role=system | 顶层 `instructions`（多条拼接；content 为数组时拼接其文本 part） |
| `messages[]` role=user content=string | `{"role":"user","content":[{"type":"input_text","text":...}]}` |
| user content part `{"type":"text","text":...}` | `{"type":"input_text","text":...}` |
| user content part `{"type":"image_url","image_url":{"url":...}}` | `{"type":"input_image","image_url":...}` |
| assistant content=string | `{"role":"assistant","content":[{"type":"output_text","text":...}]}` |
| assistant content=数组 `[{"type":"text",...}]` | `{"role":"assistant","content":[{"type":"output_text","text":...}]}`（**必须重写类型，否则 invalid_prompt**） |
| assistant `tool_calls[]` | `{"type":"function_call","call_id","name","arguments"}`（arguments 为 JSON 字符串） |
| role=tool 消息 | `{"type":"function_call_output","call_id","output"}` |
| `tools[]` `{type:function,function:{name,description,parameters}}` | `{type:function,name,description,parameters}` |
| `tool_choice` `{type:function,function:{name}}` | `{type:function,name}` |
| `max_tokens` / `max_completion_tokens` | `max_output_tokens` |

## 4. 响应转换（Responses API -> Chat Completions）

| Responses API | Chat Completions |
|---|---|
| `output[].type=message` + `content[].type=output_text` | `choices[0].message.content` |
| `output[].type=function_call`（含 `call_id`/`name`/`arguments`） | `choices[0].message.tool_calls[]`，`finish_reason=tool_calls` |
| `output[].type=reasoning` + `summary[].text` | `message.reasoning_content` |
| `usage.input_tokens/output_tokens/total_tokens` | `usage.prompt_tokens/completion_tokens/total_tokens` |

## 5. 流式（SSE）事件映射

| Responses 事件 | Chat Completions 输出 |
|---|---|
| `response.created` | （隐式）首个 `delta.role=assistant` chunk |
| `response.output_text.delta` | `delta.content` chunk |
| `response.reasoning_summary_text.delta` | `delta.reasoning_content` chunk |
| `response.output_item.added` (function_call) | 开始累积调用（按 `item_id` 缓存） |
| `response.function_call_arguments.delta` | 追加 `arguments` |
| `response.output_item.done` | 固化 arguments |
| 流结束 | 一次性输出全部 `tool_calls` delta，然后 `finish_reason` + `[DONE]` |

多函数并发时按 `item_id` 区分，不丢参数。

## 6. 实测返回样例

`gpt-5.6-luna` 非流式（节选）：
```
{"id":"gen-...","object":"response","model":"gpt-5.6-luna",
	"output":[{"type":"message","content":[{"type":"output_text","text":"2 + 3 equals 5."}]}],
	"usage":{"input_tokens":19,"output_tokens":12,"total_tokens":31}}
```

`deepseek-v4-flash` 非流式（节选）：
```
{"id":"...","object":"chat.completion","model":"deepseek-v4-flash",
	"choices":[{"message":{"role":"assistant","content":"2 + 3 = 5","reasoning_content":"..."}}]}
```

## 7. 扩展指引

- 更换上游：设置环境变量 `OPENCODE_UPSTREAM`（默认 `https://opencode.ai/zen/go/v1/responses`）。
- 更换端口：`PROXY_PORT`（默认 8787）；绑定地址 `PROXY_HOST`（默认 127.0.0.1）。
- 代理从入站 `Authorization` 头取 key 透传，key 只维护在客户端模型配置一处。
