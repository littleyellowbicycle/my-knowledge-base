<div align="center">

#  四层认知引擎

**收藏不是终点，遗忘才是 —— 把散落各处的收藏夹，炼成可问答的知识体系**

![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![MCP](https://img.shields.io/badge/MCP-6E56CF?logo=anthropic&logoColor=white)
![LiteLLM](https://img.shields.io/badge/LiteLLM-4F4F8F?logo=litellm&logoColor=white)
![Pydantic](https://img.shields.io/badge/Pydantic-E9209E?logo=pydantic&logoColor=white)
![License-MIT](https://img.shields.io/badge/License-MIT-green.svg)

[快速开始](#-快速开始) · [核心特性](#-核心特性) · [使用流程](#-使用流程) · [文档](docs/architecture.md)

</div>

收藏即遗忘？把微信、知乎、网页书签里的资料统一归档，LLM 自动加工为结构化笔记，关联引擎编织双链网络，最终变成一座可问答的知识体系。

## ✨ 核心特性

- **统一归档** — 微信/知乎/GitHub/网页，一个命令收编所有平台的收藏
- **自动加工** — LLM 提炼 2-3 句核心结论，长文不必从头读
- **双链关联** — 标签+标题分词打分，确定性算法自动建立笔记链接
- **碎片→综述** — ≥3 篇关联笔记自动编译为 Wiki 综述，无需手动整理
- **直接问答** — 问"我学过什么"，从你的收藏里精准检索，带来源引用
- **AI Agent 原生** — MCP 协议支持，Claude/Cursor 可直接操作知识库
- **Obsidian 就绪** — `my_kb/` 直接当仓库打开，双链/图谱开箱即用

## 🚀 快速开始

```bash
# 克隆项目
git clone https://github.com/littleyellowbicycle/oh-my-knowledge.git
cd oh-my-knowledge

# 安装依赖
pip install -r requirements.txt

# 配置 API Key
cp .env.example .env
# 编辑 .env 填入至少一个模型供应商的 Key

# 一键全流程: 录入 → 加工 → 索引 → Wiki
python kb.py workflow -u "https://github.com/..."
python kb.py qa "你的问题"
```

### 配置模型

编辑 `.env` 填入 API Key（至少一个）：

| 提供商 | 模型示例 | 用途 |
|--------|----------|------|
| MiniMax | `minimax/MiniMax-M3` | 加工/编译/问答 |
| DeepSeek | `deepseek/deepseek-chat` | 问答 |
| 智谱 GLM | `zhipu/glm-4-flash` | 加工层 |
| 月之暗面 Kimi | `moonshot/moonshot-v1-128k` | 编译层 |
| Ollama | `ollama/qwen2.5:7b` | 断网兜底 |

## 📖 使用流程

```
录入原料 → LLM 加工 → 关联引擎自动建链 → 索引重建 → 问答 / Wiki 编译
```

| 命令 | 作用 |
|------|------|
| `kb workflow [-u URL]` | **一键全流程**: 录入 → 加工 → 索引 → Wiki |
| `kb ingest -u URL` | 抓取 URL 归档到原料层 |
| `kb ingest -t TEXT` | 手动录入文本 |
| `kb process --all` | 加工所有 pending 原料 |
| `kb index` | 重建索引层 |
| `kb qa QUESTION` | 基于知识库问答 |
| `kb wiki --all` | 编译所有达标 Wiki 簇 |
| `kb serve` | 启动 API 服务 (供 Obsidian 对接) |
| `kb mcp` | 启动 MCP 服务 (供 AI Agent 调用) |

详细使用说明见 [`docs/Implementation_plan.md`](docs/Implementation_plan.md)。

### MCP 对接

```bash
python kb.py mcp
```

AI Agent 可直接调用 `ingest_and_process(url)` 一键完成采集+加工全文流，或手动分步调用。

MCP 配置示例（Claude Desktop / Cursor / Opencode）：

<details>
<summary>展开配置示例</summary>

**Claude Desktop** — 编辑 `claude_desktop_config.json`：
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

**Cursor** — `Settings → Features → MCP Servers → Add new`：
| 字段 | 值 |
|------|-----|
| Name | `oh-my-knowledge` |
| Type | `command` |
| Command | `python` |
| Args | `D:\project\oh-my-knowledge\kb.py mcp` |

</details>

### Obsidian 对接

将 `my_kb/` 作为 Obsidian 仓库打开，安装 Copilot 插件并将 API Base 设为 `http://localhost:8000`。详见 [`docs/ob-plugin.md`](docs/ob-plugin.md)。

## 🧪 测试

```bash
pytest tests/ -v
```

## 📚 文档

| 文档 | 说明 |
|------|------|
| [系统架构](docs/architecture.md) | 架构总览与四层设计原则 |
| [技术选型](docs/technology_selection.md) | 各层级技术栈与选型理由 |
| [实施路线图](docs/Implementation_plan.md) | 分步实施计划与产出定义 |
| [Obsidian 对接](docs/ob-plugin.md) | 插件配置与全流程对接指南 |

## 📜 License

MIT License

**如果这个项目对你有帮助，请给个 ⭐ Star！**
