# 示例：接入 WorkBuddy（自定义模型）

1. 启动代理：双击 `scripts/start_proxy.bat`，或 `python3 proxy.py`。
2. 编辑 WorkBuddy 自定义模型配置文件 `~/.workbuddy/models.json`，新增/修改条目。

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

要点：

- `url` 必须指向代理的 Chat Completions 端点（**不要**直连上游 `/responses`）。
- `apiKey` 填上游（如 OpenCode Go）的 API key；代理从入站 `Authorization` 头透传。
- 模型 ID 填上游实际 ID（OpenCode Go 网关**不带前缀**，如 `gpt-5.6-luna`）。
- 完全退出并重启 WorkBuddy（系统托盘右键退出，不是关窗口）后，在模型选择器选用该模型。

已知现象与处理：

- 若「新会话第一条能用、有历史后报 10000」：升级到最新版 `scripts/proxy.py`
  （assistant 历史消息 content 数组的类型转换问题）。
- 若代理未运行：客户端会连接失败；先跑 `python3 proxy.py`，`curl http://127.0.0.1:8787/health`
  应返回 `{"status":"ok"}`。
