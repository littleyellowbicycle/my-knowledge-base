<div align="center">

# 🧠 四层认知引擎

**不依赖 LLM 的随机联想，而用确定性算法守护知识的脉络**

![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![LiteLLM](https://img.shields.io/badge/LiteLLM-4F4F8F?logo=litellm&logoColor=white)
![Pydantic](https://img.shields.io/badge/Pydantic-E9209E?logo=pydantic&logoColor=white)
![License-MIT](https://img.shields.io/badge/License-MIT-green.svg)

[快速开始](#-快速开始) · [核心特性](#-核心特性) · [架构](#-架构) · [文档](#-文档)

_试问，若关联皆由概率生灭，那些被 LLM 随手编织的"双链"，与噪声何异？_

</div>

<details>
<summary>展开设计宣言</summary>

以结构之名，我拒绝将知识的脉络交由随机性裁决。
未经确定性算法统摄的关联，不过是 LLM 的即兴幻觉；
不可变的原料被随意覆写，终将让溯源成为奢望；
直接由模型生成的双链，绝非知识图谱，而是思想碎片的随机粘连；
真正的知识体系，从不诞生于单次推理的恩赐，而只能发端于四层隔离的严谨流转。

我不会让 LLM 越俎代庖。我只让它在结构化产出中尽责，在 Wiki 编译中重组，
而把"谁与谁相关"的裁决权，牢牢握在确定性算法手中。

**—— 现在，去构建你的知识体系吧。🎓**
</details>

## 为什么需要四层认知引擎？

传统笔记工具要么把关联交给人工手动维护，要么交给 LLM 随机生成——前者繁琐易弃，后者看似智能实则不可控。四层认知引擎反其道而行——**关联关系由确定性算法计算，LLM 只负责内容生成与重组**。

这不是给笔记软件贴上"AI"标签。
它是一套分层隔离的认知架构：原料层不可变保证可溯源，加工层结构化产出，编译层把碎片编译成综述，索引层支撑精准问答，而贯穿四层的关联引擎用标签与标题分词打分，让每一条双链都有据可查。

## ✨ 核心特性

### 1. 确定性关联，而非 LLM 随意联想

- 标签重合 +3 分/个，标题分词重合 +1 分/个，分数 >= 阈值才建立双链。
- 关联关系完全由算法决定，LLM 不参与，结果可复现、可解释。
- 双向自动写回 Frontmatter `related` 字段与 `## 相关笔记` 段。

### 2. 四层隔离，数据单向流动

- 原料层（raw/）只读不变，Hash 命名归档，永远可溯源。
- 加工层（processed/）可迭代，LLM 结构化产出带核心结论的笔记。
- 编译层（wiki/）把关联簇编译成系统性综述，确定性双链覆盖 LLM 幻觉。
- 索引层（index/）可随时重建，支撑标签/反向链接/快速检索。

### 3. LLM 无关，一行切换国产模型

- 基于 LiteLLM SDK，原生支持 DeepSeek / GLM / Kimi / Ollama / MiniMax。
- 按层指定模型：加工用 GLM-4-Flash，编译用 Kimi 128k，问答用 DeepSeek。
- 断网或调试时，本地 Ollama 零成本兜底。

### 4. Karpathy Wiki 编译，碎片变综述

- 连通分量算法检测关联簇（>= 3 篇笔记触发编译）。
- 把多篇原子笔记编译成一篇系统性综述，消除断裂与重复。
- 后处理用确定性关联覆盖 LLM 生成的悬空双链，确保每条链接真实存在。

### 5. JSON Mode 强类型，格式绝对稳定

- LLM 输出强制走 JSON Mode，Pydantic 进行强类型校验。
- 拼装出的 Markdown 格式绝对稳定，Obsidian 可靠解析。
- 加工失败自动回滚，清理孤儿笔记与悬空双链，不留污染。

### 6. Obsidian 原生对接，API 兼容 Copilot

- `my_kb/` 直接作为 Obsidian 仓库打开，双链/标签/图谱开箱即用。
- FastAPI 服务提供 OpenAI 兼容接口，Copilot / Smart Connections 直接对接。
- 支持 SSE 流式响应，侧边栏聊天体验丝滑。

---

## 🏗️ 架构

```
原料层 (raw/)      →    加工层 (processed/)   →    编译层 (wiki/)      →    索引层 (index/)
   ↓                       ↓                        ↓                       ↓
 抓取归档              LLM 结构化              Wiki 综述                快速检索
 多平台路由            双链关联                确定性覆盖               QA 问答
 Hash 命名             核心结论                关联簇触发               可重建
```

**数据流向**：Raw → Processed → Wiki → Index，不可反向污染。

---

## 🚀 快速开始

### 环境要求

- Python 3.11+
- （可选）Ollama 本地推理引擎

### 源码运行

```bash
# 克隆项目
git clone https://github.com/littleyellowbicycle/oh-my-knowledge.git
cd oh-my-knowledge

# 安装依赖
pip install -r requirements.txt

# 配置 API Key
cp .env.example .env
# 编辑 .env 填入至少一个模型供应商的 Key（详见 docs/env-config.md）

# 录入 -> 加工 -> 索引 -> 问答
python kb.py ingest -t "你的第一篇笔记"
python kb.py process --all
python kb.py index
python kb.py qa "你的问题"
```

### 给 AI Agent 使用（MCP）

项目内置 MCP 服务，Claude / Cursor / Opencode 等 AI Agent 可直接调用知识库：

```bash
python kb.py mcp
```

Agent 会自动调用工具完成全流程——你只需发一条消息：

> "帮我看看这个链接并整理到知识库 https://..."
>
> "我收藏过关于 AI Agent 的东西吗？"
>
> "把知乎收藏夹 https://zhihu.com/collection/... 全部抓取并归档"

MCP 客户端配置详见 [`docs/mcp-setup.md`](docs/mcp-setup.md)。

---

## 📖 使用流程

```
录入原料 -> LLM 加工 -> 关联引擎自动建链 -> 索引重建 -> 问答 / Wiki 编译
   |            |              |               |             |
 URL/文本    JSON Mode     标签+标题打分      可重建      综述/检索
```

### 命令一览

| 命令 | 作用 |
|------|------|
| `kb ingest -t TEXT` | 录入文本原料 |
| `kb ingest -u URL` | 抓取 URL（GitHub/微信/知乎/网页自动路由） |
| `kb process --all` | 加工所有 pending 原料为结构化笔记 |
| `kb index` | 重建索引层 |
| `kb qa QUESTION` | 基于知识库问答 |
| `kb wiki` | 编译 Wiki 综述 |
| `kb serve` | 启动 API 服务（供 Obsidian 对接） |
| `kb mcp` | 启动 MCP 服务（stdio，供 AI Agent 调用） |

### Obsidian 对接

将项目根目录作为 Obsidian 仓库打开，安装相关插件后即可在 Obsidian 内完成 **知识收集 -> 加工 -> 问答** 全流程。API 服务启动后，在 Copilot 插件中将 Base URL 设为 `http://localhost:8000`，即可使用知识库问答。详见 [`docs/ob-plugin.md`](docs/ob-plugin.md)。

---

## 📚 文档

| 文档 | 说明 |
|------|------|
| [系统架构](docs/architecture.md) | 架构总览与四层设计原则 |
| [环境变量配置](docs/env-config.md) | API Key、模型、Cookie 等配置说明 |
| [实施路线图](docs/Implementation_plan.md) | 分步实施计划与进度追踪 |
| [MCP 对接](docs/mcp-setup.md) | Claude / Cursor / Opencode 配置 |
| [Obsidian 对接](docs/ob-plugin.md) | 插件配置与全流程对接指南 |
| [技术选型](docs/technology_selection.md) | 各层级技术栈与选型理由 |

---

## 🧪 测试

```bash
pytest tests/ -v
```

覆盖关联算法、Wiki 编译、完整流水线（录入->加工->索引->问答）的单元测试。

---

## 🙏 致谢

本项目的设计和实现受到了以下理念的启发：

- **Karpathy Wiki Compiler** — 把原子笔记编译成系统性综述的知识工程理念
- **LiteLLM** — 一套 SDK 屏蔽多模型差异的优雅设计
- **Obsidian** — 双链笔记与本地优先的知识管理哲学

---

## 📜 License

MIT License

**如果这个项目对你有帮助，请给个 ⭐ Star！**
