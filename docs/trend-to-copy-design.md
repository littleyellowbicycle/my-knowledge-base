# trend-to-copy 设计文档

## 定位

独立 CLI 项目，复用 `my-knowledge-base` 的网关(gateway)/加工(processor)/LLM(adapter) 组件，实现「GitHub 热榜选题 → 社媒竞品调研 → 文案生成」的全自动化工作流。

## 架构

```
trend-to-copy/                    # 独立仓库
├── run.py                        # CLI 入口
├── src/
│   ├── github_trending.py        # 选题源
│   ├── social_research.py        # 竞品调研
│   ├── copywriter.py             # 文案生成
│   └── utils.py                  # 共享工具
├── output/                       # 文案输出目录
├── pyproject.toml                # 依赖声明
└── .env                          # API Key 等

依赖:
  my-knowledge-base               # pip install -e ../my-knowledge-base
  crawl4ai / requests + bs4       # 爬取
  litellm                         # LLM 调用 (复用 my-kb 的配置)
```

## 数据流

```
 ┌──────────────┐    ┌──────────────────┐    ┌──────────────┐
 │  Step 1      │    │  Step 2          │    │  Step 3      │
 │  选题        │ →  │  竞品调研        │ →  │  文案生成    │
 └──────────────┘    └──────────────────┘    └──────────────┘
        │                    │                       │
        ▼                    ▼                       ▼
 D:\my_kb\raw\trending  D:\my_kb\raw\research   output/copy_*.md
                               │
                               ▼
                        D:\my_kb\processed\
                        (按知识库加工流程处理)
```

## 模块设计

### 1. github_trending.py

**职责**: 获取 GitHub Trending 仓库列表，筛选与选题相关的仓库。

```python
def fetch_trending(language="", since="daily") -> list[TrendingRepo]:
    """爬取 github.com/trending 返回仓库列表。"""
    # 1. requests 爬取 https://github.com/trending/{lang}
    # 2. bs4 解析: repo name, description, stars, today_stars
    # 3. 返回 TrendingRepo 列表

def save_to_kb(repos: list[TrendingRepo]) -> list[str]:
    """将热榜写入 D:\my_kb\raw\trending_*.md，返回 raw_ids。"""
    # 调用 raw_store.save_raw() 落盘

def filter_by_topic(repos: list[TrendingRepo], keywords: list[str]) -> list[TrendingRepo]:
    """按关键词筛选仓库（标题 + 描述匹配）。"""
```

**产出**: 每篇 raw 包含:
```
# GitHub Trending: {repo_name}

stars: {stars} / today: {today_stars}
description: {description}
url: {url}

{README 摘要 / 代码分析}
```

### 2. social_research.py

**职责**: 针对一个选题，搜索 B站/小红书/头条 上同类内容，落盘后走知识库加工流水线。

```python
def search_platform(topic: str, platform: str) -> list[ResearchItem]:
    """搜索指定平台上的同类内容。

    platform: "bilibili" | "xiaohongshu" | "toutiao"
    """
    # 策略1: 搜索引擎 site:bilibili.com + topic
    # 策略2: 直接爬平台搜索页 (如 bilibili.com/search)
    # 返回 [{title, url, description}]

def research(topic: str, platforms=None) -> list[str]:
    """全平台调研 → 落盘到 D:\my_kb\raw\research_{topic}_*.md。"""
```

**落盘格式**:
```
# 竞品调研: {topic}

## B站
- [{title}]({url}) - {简介}
- ...

## 小红书
- [{title}]({url}) - {简介}
- ...

## 头条
- [{title}]({url}) - {简介}
- ...
```

### 3. copywriter.py

**职责**: 读取知识库中已落盘+加工的竞品数据，LLM 生成差异化文案。

```python
def generate_copy(topic: str) -> str:
    """生成一篇文案，输出到 output/copy_{topic}.md。"""

def _load_research(topic: str) -> list[str]:
    """从 D:\my_kb\processed\ 读取调研笔记。"""

def _build_prompt(topic: str, research_notes: list[str]) -> str:
    """构造 Prompt:
    1. 选题: {topic}
    2. 竞品分析: {existing_content_summary}
    3. 要求: 找出差异化角度，生成 [标题, 开头Hook, 正文, 结尾]
    """
```

**Prompt 设计**:
```
你是一名社交媒体内容策划。你的任务是为选题 "{topic}" 生成一份差异化文案。

【已有竞品内容】
{research_notes}

【要求】
1. 分析竞品内容，找出它们没覆盖到的角度
2. 按 AIDA 结构输出：标题 → 开头Hook → 正文 → 结尾引导
3. 输出格式: Markdown
```

### 4. run.py (CLI)

```bash
# 单命令全流程
trend-to-copy run --topic "AI Agent" --lang python

# 分步执行
trend-to-copy fetch-trending --lang python --save     # 拉热榜落盘
trend-to-copy research "AI Agent"                       # 调研竞品
trend-to-copy generate "AI Agent"                       # 生成文案
trend-to-copy run                                       # 交互式全流程
```

## 复用策略

以 git submodule 或 pip editable install 引用 `my-knowledge-base`：

```toml
# pyproject.toml
[project]
dependencies = [
    "my-knowledge-base @ file:///D:/project/my-knowledge-base",
]
```

显式复用以下组件：

| 组件 | 用法 |
|------|------|
| `src.gateway` | `fetch_url()` 爬取 GitHub/B站/头条 |
| `src.raw_store` | `save_raw()` 落盘原始数据 |
| `src.processor` | `process_pending()` 将调研数据加工为笔记 |
| `src.llm_adapter` | `chat()`/`chat_json()` 调用 LLM 生成文案 |
| `src.config.settings` | `KB_ROOT` 等路径/模型配置 |

## 与现有知识库的关系

```
trend-to-copy 负责:
  - 选题获取
  - 竞品搜索
  - 文案生成

知识库 负责:
  - 原始数据归档 (raw/)
  - 结构化加工 (processed/)
  - 索引/问答/关联

数据单向流动:
  trend-to-copy → D:\my_kb\raw\    (写入原始数据)
  trend-to-copy → D:\my_kb\processed\ (触发加工)
  trend-to-copy → output\          (文案产出)
```

## 后续可扩展

1. **视频生成**: 集成 Remotion / FFmpeg+TTS，文案→视频
2. **自动发布**: 浏览器自动化（DrissionPage）发布到 B站/小红书/头条
3. **选题推荐**: 基于历史热点 + LLM 评分推荐最优选题
4. **定时运行**: 接入 cron / GitHub Actions 每日自动跑
