# 🛠️ V2.1 四层认知引擎 - 技术选型表

本文档基于定稿的 V2.1 架构，明确了系统各层级在 MVP 阶段所采用的技术栈、角色形态及选型理由。整体遵循“文件优先、零数据库依赖、LLM 无关、确定性优先”的核心原则。

---

## 一、核心基础栈

| 层级 / 模块 | 技术选型 | 角色 / 形态 | 选型理由 |
| --- | --- | --- | --- |
| **系统语言** | **Python 3.11+** | 主控语言 | LLM 生态最完善，原生支持异步，胶水编程首选 |
| **Web 框架** | **FastAPI** | 后续 Webhook / API 推送用 | 异步、轻量、自带 Swagger 文档 |
| **配置管理** | **python-dotenv** | 运行时依赖 | 通过 `.env` 管理各类 API Key，避免硬编码 |

---

## 二、LLM 适配与加工引擎

| 层级 / 模块 | 技术选型 | 角色 / 形态 | 选型理由 |
| --- | --- | --- | --- |
| **LLM 适配层** | **LiteLLM (SDK 模式)** | 运行时依赖 (`pip install litellm`) | **原生支持 DeepSeek / GLM / Kimi / MiniMax / Ollama**，一行代码切换模型，无需自建 Proxy 服务 |
| **结构化输出** | **JSON Mode + Pydantic** | 加工引擎约束 | 强制 LLM 输出合法 JSON，Pydantic 进行强类型校验，确保拼装出的 Markdown 格式绝对稳定 |
| **本地兜底** | **Ollama** | 本地推理引擎 | `litellm` 原生支持 (`ollama/qwen2.5:7b`)，断网或调试时零成本可用 |

---

## 三、输入网关 (通道分层架构 V2.2)

网关从单文件 `gateway.py` 重构为**通道 (Channel) 插件化架构**，每个平台一个独立通道，新增平台不改已有代码 (开闭原则)。

### 架构

| 层级 / 模块 | 技术选型 | 角色 / 形态 | 选型理由 |
| --- | --- | --- | --- |
| **通道协议** | **Channel (Protocol)** | `base.py` 定义 `match() + fetch() + fetch_items()` | 每个平台实现协议，路由器零逻辑遍历 |
| **瘦路由** | **router.py** | `fetch_url(url, cookies=None)` 遍历 channels 列表 | 第一个 `match()` 命中的通道负责处理，generic 永远兜底 |

### 通道清单

| 通道 | 列表/索引抓取 | 单篇正文抓取 | Cookie | HTML 解析 |
| --- | --- | --- | --- | --- |
| **GitHub** | — | gh CLI / REST API | 可选 | — |
| **知乎** | requests + items API (JSON, 分页) | Crawl4AI (Playwright+cookie注入) → requests+bs4 → API 兜底 | 必须 (items API 401) | bs4 + markdownify |
| **微信** | — | Jina Reader API → Crawl4AI | 免 cookie | Jina 直接输出 MD |
| **通用 (兜底)** | — | Crawl4AI → requests | 可选 | 内置正则清理 |
| **小红书** (规划) | requests + API | Crawl4AI (重JS+cookie) | 必须 | bs4 + markdownify |

### 新增依赖

| 技术 | 角色 | 选型理由 |
| --- | --- | --- |
| **Crawl4AI** | 网页抓取-主 (Playwright 渲染) | 自动判断 HTTP/浏览器模式，支持 cookie 注入到浏览器会话，解决 JS 渲染 + 登录态双重问题 |
| **BeautifulSoup4 + lxml** | HTML 解析 (知乎/小红书等) | 稳定的 CSS 选择器提取，配合 lxml 解析器高性能 |
| **markdownify** | HTML → Markdown 转换 | 保留标题/链接/列表语义，输出兼容 Obsidian |
| **requests** | JSON API 调用 (知乎 items API) | 轻量快速，纯 API 不需要浏览器渲染 |

### Cookie 管理机制

| 优先级 | 来源 | 格式 | 说明 |
| --- | --- | --- | --- |
| 1 (最高) | 显式参数 `cookies={...}` | dict | `fetch_url(url, cookies={"z_c0":"..."})` 一次性传入 |
| 2 | 通道专属文件 `cookies_zhihu.json` | `[{name, value}]` | 各通道独立读取，互不干扰 |
| 3 | 全局文件 `cookies.json` | `[{name, value}]` | 通用兜底 |
| 4 (最低) | 无 | — | 公开内容能抓则抓，需登录返回清晰提示 |

### 抓取策略选型理由

| 决策 | 理由 |
| --- | --- |
| 知乎列表用 requests 而非 Crawl4AI | items API 返回纯 JSON，requests 一个 GET 即可，Crawl4AI 渲染 JSON API 浪费 10 倍时间 |
| 知乎正文用 Crawl4AI 而非 requests | 文章页面重 JS 渲染，`RichContent-inner` 动态填充，requests 只拿到空壳 |
| 微信用 Jina Reader 而非 Crawl4AI | 公众号反爬严格但 Jina 已完美绕过，Crawl4AI 反而慢 |
| 小红书用 Crawl4AI | 重 JS + 强反爬，requests 几乎拿不到内容，必须浏览器渲染 + cookie |

---

## 四、关联算法与索引层

| 层级 / 模块 | 技术选型 | 角色 / 形态 | 选型理由 |
| --- | --- | --- | --- |
| **中文分词** | **jieba** | 运行时依赖 | 确定性关联打分算法的基础，精准提取标题名词/专业词 |
| **Markdown解析** | **python-frontmatter** | 运行时依赖 | 稳定读写 YAML 头部的 `tags`、`related` 等元数据 |
| **双链提取** | **内置 `re` 正则** | 代码内逻辑 | 极简提取 `[[]]` 语法，构建 `links.json` 正反向链接表 |
| **索引存储** | **JSON 文件** | 本地文件系统 | 零数据库依赖、人类可读、可随时删除重建、可 Git 版本控制 |

---

## 五、Wiki 编译层 (Karpathy 理念落地)

| 层级 / 模块 | 技术选型 | 角色 / 形态 | 选型理由 |
| --- | --- | --- | --- |
| **Wiki 编译基座** | **Hosuke/llmwiki** | `pip` 包引入 | Python 原生、支持 CJK、无向量库依赖，契合 Karpathy 编译模式 |
| **Wiki 编译蓝图** | **atomicstrata/llm-wiki-compiler** | 参考实现 | 借鉴其两阶段编译流水线、SHA-256 增量编译、Claim 级行号溯源理念 |
| **胶水层逻辑** | **自研 Python 模块** | 代码内逻辑 | 负责格式转换、关联簇触发判定、双链确定性覆盖，确保图谱干净 |

---

## 六、存储与前端展示

| 层级 / 模块 | 技术选型 | 角色 / 形态 | 选型理由 |
| --- | --- | --- | --- |
| **文件存储** | **`pathlib` / `os`** | 本地文件系统 (`raw/`, `processed/`, `wiki/`, `index/`) | 零依赖、四层隔离、可 Git 版本控制 |
| **前端展示** | **Obsidian** | 挂载 `processed/` 与 `wiki/` 目录 | 开箱即用的双链图谱、MOC 视图、本地极速搜索，无需开发 Web UI |

---

## 附：V2.1 国产大模型路由策略推荐

基于 LiteLLM SDK，系统可实现“一层一模型”的零成本切换策略：

| 架构层 | 推荐模型 | LiteLLM 调用字符串 | 理由 |
| --- | --- | --- | --- |
| **B2 加工层** | 智谱 GLM-4-Flash | `zhipu/glm-4-flash` | 中文理解强、JSON Mode 稳定、成本低 |
| **B4 编译层** | 月之暗面 Kimi | `moonshot/moonshot-v1-128k` | 256K 长上下文，吃下多篇原子笔记生成综述 |
| **C1 问答流** | DeepSeek Chat | `deepseek/deepseek-chat` | 推理性价比极高，回答质量稳定 |
| **本地兜底** | Ollama Qwen | `ollama/qwen2.5:7b` | 零成本，离线可用，保护隐私 |
