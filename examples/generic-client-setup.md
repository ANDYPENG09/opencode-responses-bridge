# 示例：接入通用 OpenAI 兼容客户端

任何支持「自定义 OpenAI 兼容模型 base URL」的客户端（Cursor、Open WebUI、LobeChat、
NextChat、one-api 系网关等）都可以直接接入本代理：

1. 启动代理：`python3 proxy.py`（默认 `http://127.0.0.1:8787`）。
2. 在客户端配置自定义模型：
   - **Base URL / API 地址**：`http://127.0.0.1:8787/v1`
   - **模型名**：上游实际模型 ID（如 `gpt-5.6-luna`）
   - **API Key**：上游 API key（必填，代理会透传到上游）
   - **能力开关**：按上游实际能力勾选 工具调用 / 视觉 / 推理

原理：客户端按 OpenAI 兼容协议把 Chat Completions 请求发给 `http://127.0.0.1:8787/v1/chat/completions`，
代理翻译成 Responses API 转发上游，再把响应翻回 Chat Completions 返回给客户端。

注意事项：

- 客户端需能访问 `127.0.0.1`；若客户端与代理不在同一台机器，请改用局域网地址并
  自行评估监听安全性（`PROXY_HOST` 默认只绑定本机）。
- 不支持 Anthropic Messages 协议的客户端（如 Claude Code 直连模式）无法直接使用，
  需要额外的 Anthropic↔Responses 适配层。
