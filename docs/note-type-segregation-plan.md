# 笔记类型区分方案：索引型 vs 内容型

## 问题诊断

当前流水线存在三类"伪内容笔记"，它们有入口但无实质论点：

| 类型 | 来源 | 特征 | 现有数量 |
|------|------|------|----------|
| **抓取失败占位** | 网关返回 `<!-- 抓取失败 -->` 或"需要登录态" | 正文是错误说明，无原文论点 | ~16 篇 |
| **收藏夹索引页** | `save_collection()` 保存的目录页 | 正文是链接列表，无单篇内容 | 1 篇 |
| **Example/测试页** | 测试 URL（如 example.com） | 正文是模板说明 | 1 篇 |

这些笔记被 LLM 加工后看似有结论，但结论是"该源未获取"的元描述，并非知识本身。Wiki 编译器把它们当真实素材喂给 LLM，导致综述页出现"待补全"的空洞。

## 修改方案

### 改动总览

```
schemas.py      新增 NoteType 枚举 + ProcessedNote.note_type 字段
gateway/        抓取失败/索引页时在 raw_text 头部插入标记
processor.py    检测标记 → 设置 note_type → 写入 frontmatter
indexer.py      读取 frontmatter note_type → 记入 summaries.json
wiki_compiler   过滤 note_type != "content" 的笔记
cli.py          新增 `kb list stubs` 命令
```

### Step 1: schemas.py — 新增类型枚举

```python
class NoteType(str, Enum):
    CONTENT = "content"   # 内容型：含实质论点
    INDEX = "index"       # 索引型：仅链接列表/目录页
    STUB = "stub"         # 占位型：抓取失败/待补全
```

`ProcessedNote` 增加字段：

```python
class ProcessedNote(BaseModel):
    title: str
    conclusion: str
    body_markdown: str
    tags: list[str]
    related: list[str]
    note_type: NoteType = NoteType.CONTENT  # 新增，默认内容型
```

### Step 2: gateway — 原料层插入类型标记

在 `_shared.py` 新增标记函数：

```python
STUB_MARKERS = [
    "<!-- 抓取失败",
    "需要登录态",
    "HTTP 403",
    "HTTP 401",
]

def detect_raw_type(raw_text: str) -> str:
    """检测原料类型，返回 'stub' | 'index' | 'normal'。"""
    # 1. 抓取失败标记
    for marker in STUB_MARKERS:
        if marker in raw_text:
            return "stub"
    # 2. 收藏夹索引页（全是链接列表，无正文段落）
    if raw_text.startswith("URL:") and "\n\n[" in raw_text[:200]:
        # 链接密度高且无实质段落
        lines = [l for l in raw_text.split("\n") if l.strip()]
        link_lines = sum(1 for l in lines if "](" in l or l.startswith("http"))
        if link_lines > len(lines) * 0.6:
            return "index"
    return "normal"
```

各 channel 在 `fetch()` 返回前调用，将类型写入 raw 文件头部：

```
<!-- raw_type: stub -->
URL: https://...
<!-- 抓取失败: ... -->
```

`raw_store.save_link()` / `save_collection()` 在落盘前自动插入标记。

### Step 3: processor.py — 加工时识别并传播类型

`_build_prompt()` 前检测原料类型：

```python
def process_note(raw_id, ...):
    entry = load_raw(raw_id)
    raw_type = detect_raw_type(entry.original_text)

    if raw_type == "stub":
        # 直接生成占位笔记，不调 LLM（省 token）
        note = ProcessedNote(
            title=_stub_title(entry),
            conclusion=f"> 原始来源未获取，待补全。来源: {entry.source_url}",
            body_markdown=f"## 状态\n\n⚠️ 待补全 — 原始内容抓取失败。\n\n## 来源\n{entry.source_url}",
            tags=["待补全", "抓取失败"],
            related=[],
            note_type=NoteType.STUB,
        )
    elif raw_type == "index":
        note = ProcessedNote(
            title=_index_title(entry),
            conclusion=f"> 收藏夹索引页，包含 {link_count} 篇文章链接。",
            body_markdown=entry.original_text,  # 保留链接列表
            tags=["索引页", "收藏夹"],
            related=[],
            note_type=NoteType.INDEX,
        )
    else:
        # 正常 LLM 加工
        note = llm.chat_json(...)
        note.note_type = NoteType.CONTENT
```

`_assemble_markdown()` 写入 frontmatter：

```yaml
---
title: ...
note_type: stub   # 新增字段
status: processed
---
```

### Step 4: indexer.py — 索引层记录类型

`_parse_note()` 读取 frontmatter 的 `note_type`：

```python
def _parse_note(path, note_type="note"):
    ...
    raw_note_type = post.metadata.get("note_type", "content")
    return {
        ...
        "note_type": raw_note_type,  # 新增
    }
```

`summaries.json` 每条增加 `note_type` 字段，供问答流和 Wiki 编译器查询。

### Step 5: wiki_compiler.py — 编译时过滤

`compile_wiki()` 读取簇内笔记时跳过非 content 类型：

```python
def compile_wiki(...):
    ...
    notes = [_read_note_full(s) for s in stems]
    # 新增：只保留内容型笔记
    notes = [n for n in notes
             if n["body"] and n.get("note_type", "content") == "content"]
    if len(notes) < settings.WIKI_CLUSTER_MIN_NOTES:
        logger.info("有效内容笔记不足 (%d 篇 stub/index 已过滤)，跳过", ...)
        return None
```

`_read_note_full()` 增加返回 `note_type` 字段：

```python
def _read_note_full(stem):
    ...
    note_type = post.metadata.get("note_type", "content")
    return {..., "note_type": note_type}
```

`find_clusters()` 同样过滤，避免 stub/index 笔记污染连通分量：

```python
def find_clusters(...):
    ...
    summaries = load_summaries()
    excluded_stems = {
        Path(f).stem for f, s in summaries.items()
        if s.get("note_type") in ("stub", "index")
    }
    # BFS 时跳过 excluded_stems
```

### Step 6: cli.py — 新增管理命令

```bash
# 列出所有 stub/index 笔记
kb list stubs

# 输出示例:
# stub  (16 篇):
#   - 知乎素材抓取失败待补充.md
#   - ...
# index (1 篇):
#   - 知乎理财收藏夹.md
```

实现：扫描 `processed/` 读 frontmatter `note_type` 字段。

### Step 7: 存量笔记回填

对已有 211 篇笔记做一次性迁移：

```bash
kb migrate note-types
```

脚本逻辑：
1. 遍历 `processed/*.md`
2. 读 `source` 字段 → 找对应 raw 文件
3. 对 raw 文件跑 `detect_raw_type()`
4. 无 frontmatter `note_type` 的，按检测结果回写
5. 无 raw 对应的，按正文启发式判断（含"待补全/抓取失败"→ stub）

## 改动文件清单

| 文件 | 改动量 | 说明 |
|------|--------|------|
| `src/schemas.py` | +10 行 | NoteType 枚举 + ProcessedNote 字段 |
| `src/gateway/channels/_shared.py` | +25 行 | `detect_raw_type()` + STUB_MARKERS |
| `src/gateway/channels/zhihu.py` | +3 行 | fetch 返回前插入标记 |
| `src/gateway/channels/generic.py` | +2 行 | fetch 返回前插入标记 |
| `src/processor.py` | +40 行 | stub/index 分支 + frontmatter 写入 |
| `src/indexer.py` | +5 行 | _parse_note 读 note_type |
| `src/wiki_compiler.py` | +15 行 | find_clusters + compile_wiki 过滤 |
| `src/cli.py` | +20 行 | `kb list stubs` + `kb migrate note-types` |

总计约 **120 行**新增代码，无破坏性改动（`note_type` 默认 `content`，旧笔记无字段时按 content 处理）。

## 验收标准

1. `kb list stubs` 正确列出 16 篇 stub + 1 篇 index
2. `kb wiki --all` 编译时日志显示"已过滤 N 篇 stub/index"
3. 生成的 Wiki 综述不再包含"待补全"类笔记作为素材
4. 旧笔记运行 `kb migrate note-types` 后 frontmatter 出现 `note_type` 字段
5. 问答流 `ask()` 可选过滤 stub（后续需求，本次不实现）
