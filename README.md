<div align="center">

#  四层认知引擎

**收藏不是终点，遗忘才是 —— 把散落各处的收藏夹，炼成可问答的知识体系**

![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![LiteLLM](https://img.shields.io/badge/LiteLLM-4F4F8F?logo=litellm&logoColor=white)
![Pydantic](https://img.shields.io/badge/Pydantic-E9209E?logo=pydantic&logoColor=white)
![License-MIT](https://img.shields.io/badge/License-MIT-green.svg)

[快速开始](#-快速开始) · [核心特性](#-核心特性) · [架构](#-架构) · [文档](#-文档)

</div>

_试问，你收藏过的那些"好文章"，上一次翻开是什么时候？_

<details>
<summary>展开设计宣言</summary>

以归档之名，我拒绝让收藏夹沦为知识的坟墓。
散落在微信、微博、知乎、浏览器书签里的"好内容"，不过是信息熵增的注脚；
未经结构化加工的收藏，终将在算法的信息流里沉没；
直接堆砌的链接，绝非知识库，而是数字时代的仓鼠囤积；
真正的知识体系，从不诞生于一次"收藏"的恩赐，而只能发端于归档、加工、关联的严谨流转。

我不会让收藏即遗忘。我只让原料层忠实归档，加工层提炼结论，关联引擎编织脉络，
而把"我学过什么"的答案，随时可被问答唤起。

**—— 现在，去唤醒你沉睡的收藏夹吧。🎓**
</details>

## 为什么需要四层认知引擎？

你的"好内容"散落在微信收藏、微博、知乎、浏览器书签、聊天记录里——收藏时觉得"以后一定用得上"，回头却再也找不到，甚至忘了收藏过。四层认知引擎就是为了终结这种"收藏即遗忘"——**把散落各处的资料统一归档，加工成结构化笔记，自动编织关联，最终变成一座可问答的知识体系**。

它是一套分层隔离的认知架构：原料层不可变地归档每一次收藏，加工层用 LLM 提炼核心结论，关联引擎用标签与标题分词打分自动建立双链，编译层把碎片编译成综述，索引层支撑随时问答——让每一条收藏都不再沉睡。

## ✨ 核心特性

### 1. 确定性关联，而非 LLM 随意联想

- 标签重合 +3 分/个，标题分词重合 +1 分/个，分数 ≥ 阈值才建立双链。
- 关联关系完全由算法决定，LLM 不参与，结果可复现、可解释。
- 双向自动写回 Frontmatter `related` 字段与 `## 相关笔记` 段。

### 2. 四层隔离，数据单向流动

- 原料层（raw/）只读不变，Hash 命名归档，永远可溯源。
- 加工层（processed/）可迭代，LLM 结构化产出带核心结论的笔记。
- 编译层（wiki/）把关联簇编译成系统性综述，确定性双链覆盖 LLM 幻觉。
- 索引层（index/）可随时重建，支撑标签/反向链接/快速检索。

### 3. LLM 无关，一行切换国产模型

- 基于 LiteLLM SDK，原生支持 DeepSeek / GLM / Kimi / Ollama。
- 按层指定模型：加工用 GLM-4-Flash，编译用 Kimi 128k，问答用 DeepSeek。
- 断网或调试时，本地 Ollama 零成本兜底。

### 4. Karpathy Wiki 编译，碎片变综述

- 连通分量算法检测关联簇（≥3 篇笔记触发编译）。
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
git clone https://github.com/littleyellowbicycle/my-knowledge-base.git
cd my-knowledge-base

# 安装依赖
pip install -r requirements.txt

# 配置 API Key
cp .env.example .env
# 编辑 .env 填入至少一个模型供应商的 Key

# 录入 → 加工 → 索引 → 问答
python kb.py ingest -t "你的第一篇笔记"
python kb.py process --all
python kb.py index
python kb.py qa "你的问题"
```

### 配置模型

首次使用请编辑 `.env` 填入 API Key（至少一个，留空则使用 Ollama 兜底）：

| 提供商       | 模型示例                  | 配置方式        | 推荐用途   |
| --------- | --------------------- | ----------- | ------ |
| DeepSeek  | deepseek/deepseek-chat | API Key     | 问答流    |
| 智谱 GLM   | zhipu/glm-4-flash     | API Key     | 加工层    |
| 月之暗面 Kimi | moonshot/moonshot-v1-128k | API Key     | 编译层    |
| Ollama    | ollama/qwen2.5:7b      | 本地部署        | 断网兜底   |

---

## 📖 使用流程

```
录入原料 → LLM 加工 → 关联引擎自动建链 → 索引重建 → 问答 / Wiki 编译
   ↓           ↓            ↓              ↓            ↓
 URL/文本   JSON Mode     标签+标题打分    可重建      综述/检索
```

### 命令一览

| 命令                  | 作用                       |
| ------------------- | ------------------------ |
| `kb ingest -t TEXT`  | 录入文本原料                  |
| `kb ingest -u URL`   | 抓取 URL（GitHub/微信/网页自动路由） |
| `kb process --all`   | 加工所有 pending 原料为结构化笔记    |
| `kb index`           | 重建索引层                    |
| `kb qa QUESTION`     | 基于知识库问答                 |
| `kb wiki`            | 编译 Wiki 综述               |
| `kb serve`           | 启动 API 服务（供 Obsidian 对接） |

### Obsidian 对接

将 `my_kb/` 作为 Obsidian 仓库打开，安装 Shell Commands / Obsidian Git / Templater / Copilot 插件，配置快捷键后即可在 Obsidian 内完成 **知识收集 → 加工 → 问答** 全流程。

API 服务启动后，在 Copilot 插件中将 Base URL 设为 `http://localhost:8000`，即可使用知识库问答。

详细配置见 [`docs/ob-plugin.md`](docs/ob-plugin.md)。

---

## 📚 文档

| 文档                                         | 说明                  |
| ------------------------------------------ | ------------------- |
| [系统架构](docs/architecture.md)               | 架构总览与四层设计原则         |
| [技术选型表](docs/technology_selection.md)     | 各层级技术栈与选型理由         |
| [实施路线图](docs/Implementation_plan.md)      | 分步实施计划与产出定义         |
| [Obsidian 对接](docs/ob-plugin.md)           | 插件配置与全流程对接指南        |

---

## 🧭 路线图

- ✅ Step 0 — 项目基建与 LiteLLM 适配层
- ✅ Step 1 — 输入网关与原料层（多平台路由）
- ✅ Step 2 — 加工引擎与结构化产出（JSON Mode + Pydantic）
- ✅ Step 3 — 确定性关联引擎（标签 + 标题分词打分）
- ✅ Step 4 — 索引层与 QA 问答流
- ✅ Step 5 — Wiki 编译层（Karpathy 理念 + 连通分量）
- ✅ Step 6 — FastAPI 服务与 Obsidian 对接
- 🔜 Step 7 — V2/V3 源定时抓取与音视频处理
- 🔜 Step 8 — 多学生协作与学习分析

---

## 🧪 测试

```bash
pytest tests/ -v
```

覆盖关联算法、Wiki 编译、完整流水线（录入→加工→索引→问答）的 37 个单元测试。

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
