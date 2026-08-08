# OpenCode Responses Bridge（Responses API ↔ Chat Completions 本地转接）

## 简介

一个零依赖的本地协议转换代理，解决「AI 客户端的自定义模型通道只支持 OpenAI Chat
Completions，而部分上游模型（如 OpenCode Go 的 gpt-5.6-luna）只暴露 Responses API」的
兼容问题。

代理把客户端发出的 Chat Completions 请求翻译成 Responses API 转发给上游，再把响应转回
Chat Completions，支持：
- 文本生成与流式 SSE
- 工具调用（tool_calls ↔ function_call，含多轮 tool 循环与多函数并发）
- reasoning 摘要透传（reasoning_content）
- 多模态图片输入（image_url → input_image）
- 任意 Responses API 端点（OPENCODE_UPSTREAM 可配置）

## 使用场景

- 在 OpenAI 兼容客户端中使用仅支持 Responses API 的模型
- 任何需要 Chat Completions ↔ Responses API 协议转换的本地兼容层

## 安装与使用

1. 复制 `scripts/proxy.py`（纯 Python 标准库，Python 3.8+，无需安装依赖）。
2. 运行 `python3 proxy.py`（默认监听 `127.0.0.1:8787`），或双击 `scripts/start_proxy.bat`。
3. 在客户端把模型 URL 指向 `http://127.0.0.1:8787/v1/chat/completions`，模型 ID 填上游实际 ID。
4. 冒烟测试与分客户端示例见 `README.md` 与 `examples/`。

详细接入步骤与排障见 `SKILL.md`；协议字段映射见 `references/protocol-mapping.md`。

## 依赖

- Python 3.8+（仅标准库）
- 无任何第三方包

## 作者

- **ANDYPENG09**

## 版本

- v1.2.0（2026-08-08）：安全加固——日志默认仅摘要并移至系统临时目录，新增 `BRIDGE_DEBUG` 开关控制正文记录与调试 dump，技能目录零运行时写入；文档如实披露日志行为。
- v1.1.0（2026-08-06）：通用化改造——任意 Responses API 上游可配置、示例与排障完善、适配 WorkBuddy/ClawHub/GitHub 多平台发布。
- v1.0.0（2026-08-06）：首个版本，已在 OpenCode Go `gpt-5.6-luna` / `deepseek-v4-flash` 上实测通过。
