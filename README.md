# OpenCode Responses Bridge（Responses API ↔ Chat Completions 本地转接）

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
> - **ClawHub:** `clawhub install opencode-responses-bridge`
> - **GitHub:** `git clone https://github.com/ANDYPENG09/opencode-responses-bridge`
>
> **How to invoke**
>
> - Start the proxy: `python3 proxy.py` (defaults to `http://127.0.0.1:8787`).
> - Point your client's custom model URL at `http://127.0.0.1:8787/v1/chat/completions`.
> - Smoke test: `curl http://127.0.0.1:8787/v1/chat/completions -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" -d '{"model":"gpt-5.6-luna","messages":[{"role":"user","content":"hi"}],"stream":false}'`

---

## 它解决什么问题

AI 客户端的自定义模型通道通常只发 OpenAI **Chat Completions** 请求；而部分上游模型
（典型：OpenCode Go 的 `gpt-5.6-luna`）只暴露 OpenAI **Responses API**。直接配置必然失败，
常见报错：

- `HTTP 400 invalid_prompt` / `Invalid Responses API request`
- WorkBuddy「自定义模型错误 10000」
- 对话第一条能通、**有历史后即报错**（assistant 历史消息的 content 数组类型未转换）

本代理在本地做**协议转接**：客户端 → Chat Completions → 代理 → Responses API → 上游 → 翻回。

## 特性

- **零依赖**：纯 Python 标准库，Python 3.8+，无需 pip install
- **流式 SSE**：完整转译（role 开头 → content 增量 → [DONE]）
- **工具调用**：`tools`/`tool_choice` 双向映射，多轮 tool 循环，流式多函数并发不丢参
- **Reasoning**：上游推理摘要 → `reasoning_content` 透传
- **多模态**：`image_url`（URL / base64 data URL）→ `input_image`
- **上游可配置**：`OPENCODE_UPSTREAM` 指向任意 Responses API 端点，不限于 OpenCode Go
- **密钥单点维护**：代理从入站 `Authorization` 头透传 key，不落盘、不进代码

## 快速开始

```
# 1. 启动代理（Windows 可双击 scripts/start_proxy.bat）
python3 proxy.py                      # 默认 http://127.0.0.1:8787
# 2. 冒烟测试
curl http://127.0.0.1:8787/v1/chat/completions \
	-H "Authorization: Bearer YOUR_API_KEY" -H "Content-Type: application/json" \
	-d '{"model":"gpt-5.6-luna","messages":[{"role":"user","content":"hi"}],"stream":false}'
# 3. 客户端自定义模型 URL 指向：
# http://127.0.0.1:8787/v1/chat/completions
```

## 配置

| 环境变量 | 默认值 | 说明 |
|---|---|---|
| `OPENCODE_UPSTREAM` | `https://opencode.ai/zen/go/v1/responses` | 上游 Responses API 端点 |
| `PROXY_HOST` | `127.0.0.1` | 监听地址（安全起见勿对外开放） |
| `PROXY_PORT` | `8787` | 监听端口 |

> 注意：OpenCode Go 网关的模型 ID **不带前缀**（`gpt-5.6-luna`，不是 `opencode-go/gpt-5.6-luna`），
> 带前缀会返回 401。

## 平台与 Agent 客户端兼容性

| 客户端 | 兼容性 | 说明 |
|---|---|---|
| WorkBuddy | ✅ 已验证 | 自定义模型 `url` 指向代理，模型 ID 填上游 ID |
| 任何 OpenAI 兼容客户端（Cursor / Open WebUI / LobeChat / NextChat ...） | ✅ 协议级兼容 | 只要能把模型 base URL 指向代理 |
| OpenClaw / Claw / QClaw | ⚠️ 配置相关 | 需要把 OpenAI 兼容端点指到代理 |
| Claude Code（Anthropic Messages 协议） | ❌ 不支持 | 需要 Anthropic↔Responses 适配层，不在本技能范围 |

| 操作系统 | 兼容性 | 说明 |
|---|---|---|
| Windows | ✅ 已验证 | `start_proxy.bat` 或 `python proxy.py` |
| macOS / Linux | ✅ | `python3 proxy.py`；注意防火墙/端口 |

## 分客户端示例

- `examples/basic.md` — curl 输入/输出对（文本、流式、工具调用、多模态）
- `examples/workbuddy-setup.md` — WorkBuddy `models.json` 接入
- `examples/generic-client-setup.md` — 通用 OpenAI 兼容客户端接入

## 调试

代理会把每次请求写入同目录 `proxy-requests.log`（摘要、auth 脱敏），并把完整入站请求 /
上游载荷 / 上游报错分别落盘：`proxy-last-request.json`、`proxy-last-upstream.json`、
`proxy-last-error.txt`（覆盖式）。排查「客户端报错但 curl 正常」时先看这几个文件。

## 安全

- 默认只监听 `127.0.0.1`，不对外网开放
- 密钥不落盘、不进代码；仅从入站请求头透传
- 上游请求已内置浏览器 UA 以绕过 Cloudflare 默认 UA 拦截（`error code: 1010`）

## License

[MIT-0](./LICENSE) — 任何人可自由使用、修改、再分发（含商用），无需署名。

## 作者

- **ANDYPENG09**
