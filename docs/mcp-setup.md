# MCP 对接指南

MCP（Model Context Protocol）是 Anthropic 推出的开放协议，让 AI Agent 通过标准接口直接操作你的知识库。

## 启动服务

```bash
python kb.py mcp
```

## 可用工具

| 工具 | 作用 |
|------|------|
| `ingest_url(url)` | 抓取 URL 并归档到原料层 |
| `ingest_text(text)` | 手动录入文本到原料层 |
| `process_pending()` | 批量加工所有 pending 原料为结构化笔记 |
| `run_pipeline()` | 自动管线: 加工 → 索引 → Wiki 编译 |
| `ingest_and_process(url)` | 一键全流程: 录入 → 加工 → 索引 → Wiki |
| `ask(question)` | 两步走问答（Wiki 优先 → 降级 Processed） |
| `compile_wiki(topic?)` | 编译 Wiki 综述（全量或按主题单簇） |
| `rebuild_index()` | 重建索引层 |
| `stats()` | 各层条目统计 |

## Claude Desktop

编辑 `claude_desktop_config.json`（Settings → Developer → Edit Config）：

```json
{
  "mcpServers": {
    "oh-my-knowledge": {
      "command": "python",
      "args": ["D:\\project\\oh-my-knowledge\\kb.py", "mcp"]
    }
  }
}
```

重启后，对话中会出现工具列表，Agent 会自动判断何时调用。

## Cursor

`Cursor Settings → Features → MCP Servers → Add new MCP server`：

| 字段 | 值 |
|------|-----|
| Name | `oh-my-knowledge` |
| Type | `command` |
| Command | `python` |
| Args | `D:\project\oh-my-knowledge\kb.py mcp` |

## Opencode

在 `opencode.json` 中添加：

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "oh-my-knowledge": {
      "type": "local",
      "command": ["python", "kb.py", "mcp"],
      "cwd": "D:\\project\\oh-my-knowledge",
      "enabled": true,
      "timeout": 30000
    }
  }
}
```

## 典型工作流

Agent 调用知识库时，典型工作流为 `ingest_and_process(url)` 一键完成，或手动分步 `ingest_url` → `run_pipeline` → `ask`。
