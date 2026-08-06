---
name: opencode-responses-bridge
version: 1.1.0
description: "Local stdlib-only proxy that adapts OpenAI Chat Completions to/from the Responses API so any OpenAI-compatible agent client (WorkBuddy, Cursor, Open WebUI, LobeChat, ...) can use Responses-API-only models such as OpenCode Go gpt-5.6-luna. Use when: setting up a Chat Completions to Responses API bridge, local proxy for responses-only models, fixing 'model only supports responses API', 'invalid_prompt' HTTP 400, 'custom model error 10000', or protocol transcoding for any Responses API endpoint (OPENCODE_UPSTREAM). 使用场景：协议转接/本地代理/把只支持 Responses API 的模型接入 OpenAI 兼容客户端/模型报 invalid_prompt 或自定义模型错误 10000。"
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
    emoji: "🔄"
    homepage: https://github.com/ANDYPENG09/opencode-responses-bridge
    os:
      - windows
      - macos
      - linux
---

# OpenCode Responses Bridge（Responses API ↔ Chat Completions 本地转接）

## Overview

许多 AI 客户端的自定义模型通道只发 OpenAI **Chat Completions** 请求，而部分上游模型
（典型：OpenCode Go 的 `gpt-5.6-luna`）只暴露 OpenAI **Responses API**，直接配置必然不可用
（典型报错：`invalid_prompt` / `Invalid Responses API request` / WorkBuddy「自定义模型错误 10000」）。

本技能提供**零依赖本地转接代理**：客户端把 Chat Completions 打到本机代理，代理翻译成
Responses API 转发给上游，再把返回翻回 Chat Completions（含流式 SSE、工具调用、reasoning、
多模态输入）。任何能配置 OpenAI 兼容模型地址的客户端都可以接入。

## 快速开始

### 1. 获取代理脚本
从本技能 `scripts/` 复制两个文件到任意稳定目录（例如 `~/responses-bridge/`）：
- `proxy.py`（纯 Python 标准库，Python 3.8+，无需安装依赖）
- `start_proxy.bat`（Windows 一键启动，双击即可；macOS/Linux 直接 `python3 proxy.py`）

### 2. 启动代理
```
python3 proxy.py        # 默认监听 http://127.0.0.1:8787
```
可选环境变量：`OPENCODE_UPSTREAM`（上游 Responses 端点，默认 OpenCode Go）、
`PROXY_HOST`（默认 127.0.0.1）、`PROXY_PORT`（默认 8787）。代理从入站请求的
`Authorization: Bearer <key>` 头取上游密钥透传，密钥只在客户端配置里维护一份。

### 3. 冒烟测试（不经客户端）
```
curl http://127.0.0.1:8787/v1/chat/completions \
	-H "Authorization: Bearer YOUR_API_KEY" -H "Content-Type: application/json" \
	-d '{"model":"gpt-5.6-luna","messages":[{"role":"user","content":"hi"}],"stream":false}'
```
返回 HTTP 200 且为 `chat.completion` 结构即通过。

### 4. 配置客户端
把客户端的自定义模型 URL 指向 `http://127.0.0.1:8787/v1/chat/completions`，模型名填上游
实际模型 ID（OpenCode Go 网关的模型 ID **不带前缀**，如 `gpt-5.6-luna`）。
分客户端示例见 `examples/`（WorkBuddy `models.json`、通用 OpenAI 兼容客户端、curl）。

### 5. 验证
在客户端发送一条消息，正常流式返回即成功。

## 核心能力

- **文本与流式**：非流式返回标准 `chat.completion`；流式输出标准 SSE（role 开头 → content 增量 → `[DONE]`）。
- **工具调用**：`tools`/`tool_choice` 双向映射；多轮 tool 循环（assistant `tool_calls` → `function_call`，tool 消息 → `function_call_output`）；流式多函数并发按 `item_id` 累积不丢参。
- **Reasoning**：上游 reasoning 摘要 → `reasoning_content`（流式与非流式均支持）。
- **多模态输入**：user 消息 `image_url` part → `input_image` part（base64 data URL 原样透传）。
- **可配置上游**：`OPENCODE_UPSTREAM` 指向任意 OpenAI Responses API 兼容端点，不限于 OpenCode Go。

## 输入输出规范

- **入站**（客户端 → 代理）：标准 OpenAI Chat Completions 请求（`POST /v1/chat/completions`），支持 `messages`（system/user/assistant/tool）、`tools`、`tool_choice`、`max_tokens`、`temperature`、`top_p`、`stream`。
- **出站**（代理 → 上游）：Responses API 请求（`input`/`instructions`/`tools`/`max_output_tokens`）。
- **响应**：标准 Chat Completions（非流式 JSON 或 SSE 流），含 `usage`、`reasoning_content`、`tool_calls`。
- 完整字段映射表见 `references/protocol-mapping.md`。

## 使用示例

**把 luna 接入 WorkBuddy（models.json）：**
```
{
	"id": "gpt-5.6-luna",
	"name": "gpt-5.6-luna (via proxy)",
	"vendor": "Custom",
	"url": "http://127.0.0.1:8787/v1/chat/completions",
	"apiKey": "sk-你的上游key",
	"supportsToolCall": true,
	"supportsImages": true,
	"supportsReasoning": true,
	"useCustomProtocol": false
}
```

**期望输出**（非流式）：
```
{"id":"chatcmpl-...","object":"chat.completion","model":"gpt-5.6-luna",
	"choices":[{"index":0,"message":{"role":"assistant","content":"2 + 3 equals 5."},"finish_reason":"stop"}]}
```

更多示例（含工具调用/流式/多模态输入输出对）见 `examples/`。

## 已知限制（能力边界）

1. **仅适配 OpenAI 协议族**：代理面向 OpenAI 兼容客户端；使用 Anthropic Messages 协议的客户端（如 Claude Code 直连）需要额外的 Anthropic↔Responses 适配层，不在本技能范围内。
2. **模型 ID 不带前缀**：OpenCode Go 网关模型 ID 是 `gpt-5.6-luna` 而非 `opencode-go/gpt-5.6-luna`，带前缀会返回 401。其他上游以各自文档为准。
3. **默认上游为 OpenCode Go**：`opencode.ai` 在大陆网络可能不可达，请按需设置 `OPENCODE_UPSTREAM` 到可达的 Responses API 端点。
4. **图片输入**：仅转换 `image_url` part（URL 或 base64 data URL）；多模态能力取决于上游模型是否支持 `input_image`。
5. **安全边界**：代理只监听 `127.0.0.1`（默认），不对外网开放；密钥不落盘、不进代码。

## 排障

| 症状 | 原因 | 处理 |
|---|---|---|
| 401 | 模型 ID 带了 `opencode-go/` 前缀 | 去掉前缀；见 `references/protocol-mapping.md` §2 |
| 403 `error code: 1010` | Cloudflare 拦截默认 UA | 代理已内置浏览器 UA；勿用裸 urllib 直连 |
| 400 `invalid_prompt`（客户端报「自定义模型错误 10000」） | 会话历史里 assistant 消息 content 是数组，part 类型 `text` 未转成 `output_text` | 升级到最新 `scripts/proxy.py`；新会话正常、有历史即报错是此 bug 的典型特征 |
| 返回 `response` 对象而非 `chat.completion` | 直连了 `/responses` 端点 | 必须经代理 `http://127.0.0.1:8787/v1/chat/completions` |
| 端口占用 | 代理重复启动 | 换 `PROXY_PORT` 或结束旧进程 |
| 客户端报错但 curl 正常 | 请求结构差异 | 看代理同目录 `proxy-requests.log`（摘要、auth 脱敏）及 `proxy-last-request.json` / `proxy-last-upstream.json` / `proxy-last-error.txt` |

## 资源

- `scripts/proxy.py` — 转接代理（唯一运行入口，零依赖）
- `scripts/start_proxy.bat` — Windows 启动脚本
- `references/protocol-mapping.md` — 完整字段映射、SSE 事件表、实测样例与扩展指引
- `examples/` — 各客户端接入示例（WorkBuddy / 通用 OpenAI 兼容 / curl 输入输出对）
