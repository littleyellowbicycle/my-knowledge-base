<div align="center">

# oh-my-knowledge

**收藏不是终点，遗忘才是 —— 把散落各处的收藏夹，炼成可问答的知识体系**

![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![LiteLLM](https://img.shields.io/badge/LiteLLM-4F4F8F?logo=litellm&logoColor=white)
![Pydantic](https://img.shields.io/badge/Pydantic-E9209E?logo=pydantic&logoColor=white)
![License-MIT](https://img.shields.io/badge/License-MIT-green.svg)

</div>

## 核心特性

- **统一归档** — 微信/知乎/GitHub/网页，一个命令收编所有平台的收藏
- **自动加工** — LLM 提炼 2-3 句核心结论，长文不必从头读
- **双链关联** — 标签+标题分词打分，确定性算法自动建立笔记链接
- **碎片→综述** — ≥3 篇关联笔记自动编译为 Wiki 综述，无需手动整理
- **直接问答** — 问"我学过什么"，从你的收藏里精准检索，带来源引用
- **AI Agent 原生** — MCP 协议支持，Claude/Cursor 可直接操作知识库
- **Obsidian 就绪** — `my_kb/` 直接当仓库打开，双链/图谱开箱即用

## 快速开始

```bash
# 克隆项目
git clone https://github.com/littleyellowbicycle/oh-my-knowledge.git
cd oh-my-knowledge

# 安装依赖
pip install -r requirements.txt

# 配置 API Key
cp .env.example .env
# 编辑 .env 填入至少一个模型供应商的 Key
```

给 AI Agent 发一条消息即可：

> "帮我看看这个链接并整理到知识库 https://..."
>
> "我收藏过关于 AI Agent 的东西吗？"
>
> "把知乎收藏夹 https://zhihu.com/collection/... 全部抓取并归档"

无需手动操作，Agent 会自动调用 `ingest_and_process` → `ask` 完成全流程。

## 文档

| 文档 | 说明 |
|------|------|
| [系统架构](docs/architecture.md) | 架构总览与四层设计原则 |
| [模型配置](docs/model-config.md) | 各层模型设置与供应商支持 |
| [MCP 对接](docs/mcp-setup.md) | Claude/Cursor/Opencode 配置 |
| [Obsidian 对接](docs/ob-plugin.md) | 插件配置与全流程对接指南 |
| [实施路线图](docs/Implementation_plan.md) | 分步实施计划 |
| [技术选型](docs/technology_selection.md) | 各层级技术栈与选型理由 |
