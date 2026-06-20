# 🗺️ V2.1 四层认知引擎 - 实施路线图

本文档基于定稿的 V2.1 架构（含确定性打分、LiteLLM 国产模型适配、Karpathy Wiki 编译理念）编制。开发遵循“自底向上、先跑通主链路再叠加智能化”的原则。

---

## Step 0: 项目基建与 LLM 适配层 (LiteLLM 集成)
* **目标**：搭建四层目录骨架，通过 LiteLLM SDK 跑通国产大模型（GLM/DeepSeek/Kimi等）的统一调用。
* **动作**：
  1. 创建标准目录：`my_kb/{raw, processed, wiki, index}` 和源码目录 `src/`。
  2. 初始化环境：`pip install litellm pydantic python-frontmatter jieba crawl4ai python-dotenv`。
  3. 配置 `.env`：填入 `DEEPSEEK_API_KEY`, `ZHIPUAI_API_KEY`, `MOONSHOT_API_KEY` 等。
  4. 编写 `src/llm_adapter.py`：基于 `litellm.completion` 封装 `chat()` 和 `chat_json()` 方法，支持通过字符串无缝切换模型。
* **产出**：一个统一的大模型调用入口，一行代码切换 DeepSeek/GLM/Kimi/Ollama。

## Step 1: 输入网关与原料层 (模块 A -> B1)
* **目标**：实现多平台路由抓取，将原始信息 immutable 地落盘到 `raw/`。
* **动作**：
  1. 编写路由分发函数 `fetch_url(url)`：识别 GitHub (走 `gh` CLI)、微信公众号 (走 Jina Reader)、其他网页 (走 `Crawl4AI`)。
  2. 实现 `normalize()`：将抓取内容封装为标准 `RawEntry` (含 id, source_url, original_text)。
  3. 实现 `save_raw()`：将文本存为 `raw/{id}.txt`，元数据存为 `raw/{id}.meta.json`。
* **产出**：输入一个 URL 或文本，自动在 `raw/` 目录生成归档文件。

## Step 2: 加工引擎与结构化产出 (模块 B2)
* **目标**：将原料层的纯文本，通过 LLM (JSON Mode) 加工为带 Frontmatter 的标准 Obsidian 笔记。
* **动作**：
  1. 定义 Pydantic Schema：约束 LLM 必须输出 `{title, conclusion, body_markdown, tags}`。
  2. 编写加工 Prompt：要求提炼 2-3 句核心结论，正文保留关键概念。
  3. 实现 `process_note(raw_id)`：读取 raw -> 调用 `llm.chat_json()` -> Pydantic 校验 -> 使用 `python-frontmatter` 拼装为 `.md` -> 写入 `processed/`。
* **产出**：`raw/` 中的长文本被提炼为结构化的 `processed/*.md`，包含 `## 核心结论`。

## Step 3: 确定性关联打分引擎 (核心算法)
* **目标**：替代 LLM 随意生成双链，用“标签+分词”算法建立精准的笔记关联。
* **动作**：
  1. 初始化 `jieba` 分词器，加载停用词表。
  2. 实现 `compute_relations(new_note_path)`：遍历老笔记，标签重合 +3/个，标题分词重合 +1/个，计算总分。
  3. 筛选分数 ≥ 4 的笔记，实现 `update_related_links()`：双向更新双方 Frontmatter 的 `related` 字段，并在文末追加 `## 相关笔记` 及 `[[]]` 双链。
  4. 将此步作为钩子，挂载到 Step 2 的加工流程末尾自动执行。
* **产出**：新笔记入库时，自动与老笔记建立干净的、确定性的双向关联。

## Step 4: 索引层构建 (模块 B3)
* **目标**：扫描加工层，生成用于快速检索的 JSON 索引文件。
* **动作**：
  1. 实现 `rebuild_index()`：遍历 `processed/` 所有 `.md`。
  2. 使用正则提取 Frontmatter、`## 核心结论` 段落、正文中的 `[[]]` 链接。
  3. 生成四个核心文件：`summaries.json` (摘要库), `tags.json` (标签倒排), `links.json` (正反向双链表), `moc.json` (主题目录)。
* **产出**：系统具备全量检索能力，为问答流和编译流提供数据基础。

## Step 5: 输出引擎 - 问答流 MVP (模块 C1)
* **目标**：跑通第一个业务闭环，验证“查索引->读结论->综合回答”链路。
* **动作**：
  1. 实现 `qa(question)` 方法。
  2. 将 `summaries.json` 全量塞入 Prompt，让 LLM 选出 Top-3 最相关笔记文件名。
  3. 使用文件 I/O 读取这 3 篇笔记的 `## 核心结论` 段落。
  4. 将结论作为 Context，再次调用 LLM 生成最终回答，并附上来源笔记的 `[[]]` 链接。
* **产出**：一个可以通过命令行提问，并基于你的个人知识库精准作答的 CLI 工具。

## Step 6: Wiki 编译层集成 (模块 B4 - 进阶)
* **目标**：引入 Karpathy 理念，将关联簇笔记自动编译为系统性的 Wiki 综述页。
* **动作**：
  1. `pip install llmwiki` 并研究其 Python API 调用方式。
  2. 编写胶水层 `compile_wiki(topic)`：
     * 扫描 `links.json`，找出节点数 ≥ 3 的关联簇。
     * 将簇内的 `processed/*.md` 复制到临时工作区，调用 `llmwiki` 进行编译（建议用 Kimi 128k 模型）。
     * 后处理：用 Step 3 算出的确定性关联，覆盖 LLM 生成的悬空双链。
     * 将最终综述页保存至 `wiki/` 目录，并更新索引层。
* **产出**：系统不仅能存碎片笔记，还能自动将碎片“编译”成结构完整的知识体系综述。