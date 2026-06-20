"""索引层 (模块 B3) - 衍生数据，可随时从加工层重建。

职责 (对应 Implementation_plan Step 4):
    rebuild_index() 扫描 processed/*.md，提取 Frontmatter、## 核心结论、
    正文中的 [[]] 双链，生成四个 JSON 索引文件:
        summaries.json  - 摘要卡片库 (问答流唯一读取入口)
        tags.json       - 标签 -> 笔记文件名 倒排索引
        links.json      - 正反向双链表 (stem -> {outgoing, incoming})
        moc.json        - 主题目录 (标签作为主题 + 共现子主题)

对外暴露:
    rebuild_index()              -> dict   全量重建四个索引文件
    incremental_index(note_path) -> None   单篇笔记变更后增量更新 (MVP 可直接 rebuild)
    load_summaries() / load_tags() / load_links() / load_moc()
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

import frontmatter

from src.config import settings

logger = logging.getLogger(__name__)

# 文件名常量
F_SUMMARIES = "summaries.json"
F_TAGS = "tags.json"
F_LINKS = "links.json"
F_MOC = "moc.json"

# [[]] 双链提取
_LINK_RE = re.compile(r"\[\[([^\]]+?)\]\]")
# ## 核心结论 段落提取 (到下一个 ## 或文末)
_CONCLUSION_RE = re.compile(
    r"##\s*核心结论\s*\n(.*?)(?=\n##\s|\Z)", re.DOTALL
)
# MOC 子主题共现 Top-N
_MOC_SUBTOPIC_TOPN = 3


# ---------- 单篇笔记解析 ----------
def _parse_note(path: Path, note_type: str = "note") -> dict[str, Any] | None:
    """解析单篇笔记，返回索引所需字段。失败返回 None。

    Args:
        path:      processed/ 或 wiki/ 下的 .md 文件
        note_type: "note" (加工层) 或 "wiki" (编译层综述)
    """
    try:
        text = path.read_text(encoding="utf-8")
        post = frontmatter.loads(text)
    except Exception as e:  # noqa: BLE001
        logger.warning("解析失败 %s: %s", path.name, e)
        return None

    body = post.content
    title = str(post.metadata.get("title") or path.stem)
    tags = [str(t).strip() for t in (post.metadata.get("tags") or []) if str(t).strip()]
    source = post.metadata.get("source")
    updated = post.metadata.get("updated")
    # Wiki 综述页有 topic 字段；普通笔记无
    topic = post.metadata.get("topic")

    # 核心结论段
    m = _CONCLUSION_RE.search(body)
    conclusion_raw = m.group(1).strip() if m else ""
    # 去掉每行开头的 > 引用标记
    conclusion = re.sub(r"^\s*>\s?", "", conclusion_raw, flags=re.MULTILINE).strip()
    if not conclusion:
        # 兜底: 取正文前 200 字
        conclusion = re.sub(r"\s+", " ", body)[:200]

    # 正文中的所有 [[]] 双链
    links: list[str] = []
    seen: set[str] = set()
    for lm in _LINK_RE.finditer(body):
        target = lm.group(1).strip()
        # Obsidian 支持 [[target|alias]]，取 | 左侧
        target = target.split("|", 1)[0].strip()
        if target and target not in seen:
            seen.add(target)
            links.append(target)

    return {
        "filename": path.name,
        "stem": path.stem,
        "title": title,
        "conclusion": conclusion,
        "tags": tags,
        "links": links,
        "source": source,
        "updated": updated,
        "type": note_type,
        "topic": topic,
    }


# ---------- 四个索引构建 ----------
def _build_summaries(parsed: list[dict]) -> dict[str, dict]:
    return {
        p["filename"]: {
            "title": p["title"],
            "conclusion": p["conclusion"],
            "tags": p["tags"],
            "links": p["links"],
            "source": p["source"],
            "updated": p["updated"],
            "type": p.get("type", "note"),
            "topic": p.get("topic"),
        }
        for p in parsed
    }


def _build_tags(parsed: list[dict]) -> dict[str, list[str]]:
    inv: dict[str, list[str]] = defaultdict(list)
    for p in parsed:
        for tag in p["tags"]:
            key = tag
            inv[key].append(p["filename"])
    # 排序保证确定性
    return {k: sorted(v) for k, v in sorted(inv.items())}


def _build_links(parsed: list[dict]) -> dict[str, dict[str, list[str]]]:
    """正反向双链表: stem -> {outgoing, incoming}。

    outgoing: 该笔记正文 [[]] 指向的目标 stem 列表
    incoming: 其他笔记 [[]] 指向该笔记 stem 的来源列表
    """
    # 收集所有存在的 stem 集合，用于区分悬空双链
    known_stems = {p["stem"] for p in parsed}

    outgoing_map: dict[str, list[str]] = {p["stem"]: list(p["links"]) for p in parsed}
    incoming_map: dict[str, list[str]] = defaultdict(list)

    for p in parsed:
        for target in p["links"]:
            # 仅当目标是已知笔记时计入 incoming (悬空双链不建反向)
            if target in known_stems and target != p["stem"]:
                incoming_map[target].append(p["stem"])

    result: dict[str, dict[str, list[str]]] = {}
    for p in parsed:
        stem = p["stem"]
        result[stem] = {
            "outgoing": sorted(set(outgoing_map.get(stem, []))),
            "incoming": sorted(set(incoming_map.get(stem, []))),
        }
    return dict(sorted(result.items()))


def _build_moc(parsed: list[dict]) -> dict[str, Any]:
    """MOC: 每个标签作为主题，notes = 带该标签的笔记；subtopics = 共现 Top-N 标签。"""
    # tag -> [filename]
    tag_notes: dict[str, list[str]] = defaultdict(list)
    # tag -> co-occur tag -> count
    co_occur: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for p in parsed:
        tags = p["tags"]
        for t in tags:
            tag_notes[t].append(p["filename"])
        # 共现
        for i, t1 in enumerate(tags):
            for t2 in tags[i + 1:]:
                if t1 != t2:
                    co_occur[t1][t2] += 1
                    co_occur[t2][t1] += 1

    topics: dict[str, dict[str, Any]] = {}
    for tag, notes in tag_notes.items():
        subs = sorted(co_occur.get(tag, {}).items(),
                      key=lambda kv: kv[1], reverse=True)[:_MOC_SUBTOPIC_TOPN]
        topics[tag] = {
            "notes": sorted(set(notes)),
            "subtopics": [s[0] for s in subs],
            "note_count": len(set(notes)),
        }
    # 按 note_count 降序排
    topics = dict(sorted(topics.items(),
                         key=lambda kv: kv[1]["note_count"], reverse=True))
    return {
        "topics": topics,
        "last_rebuilt": _dt.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
    }


# ---------- 落盘 / 读取 ----------
def _write_json(name: str, data: Any) -> Path:
    settings.ensure_dirs()
    p = settings.INDEX_DIR / name
    p.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return p


def rebuild_index() -> dict[str, Any]:
    """全量重建四个索引文件。同时扫描 processed/ 与 wiki/。返回简要统计。"""
    settings.ensure_dirs()
    parsed: list[dict] = []
    # 加工层笔记
    for md in sorted(settings.PROCESSED_DIR.glob("*.md")):
        item = _parse_note(md, note_type="note")
        if item:
            parsed.append(item)
    # 编译层 Wiki 综述 (纳入索引，使问答流可检索综述)
    for md in sorted(settings.WIKI_DIR.glob("*.md")):
        item = _parse_note(md, note_type="wiki")
        if item:
            parsed.append(item)

    summaries = _build_summaries(parsed)
    tags = _build_tags(parsed)
    links = _build_links(parsed)
    moc = _build_moc(parsed)

    _write_json(F_SUMMARIES, summaries)
    _write_json(F_TAGS, tags)
    _write_json(F_LINKS, links)
    _write_json(F_MOC, moc)

    wiki_n = sum(1 for p in parsed if p.get("type") == "wiki")
    note_n = len(parsed) - wiki_n
    stats = {
        "notes": note_n,
        "wiki": wiki_n,
        "tags": len(tags),
        "topics": len(moc["topics"]),
        "rebuilt_at": moc["last_rebuilt"],
    }
    logger.info("索引重建完成: %s", stats)
    return stats


def incremental_index(note_path: Path) -> None:
    """单篇笔记变更后的增量更新 (MVP 阶段直接全量重建，保证一致性)。"""
    rebuild_index()


# ---------- 读取便利方法 ----------
def _load(name: str) -> Any:
    p = settings.INDEX_DIR / name
    if not p.exists():
        return {} if name != F_MOC else {"topics": {}, "last_rebuilt": None}
    return json.loads(p.read_text(encoding="utf-8"))


def load_summaries() -> dict[str, dict]:
    return _load(F_SUMMARIES)


def load_tags() -> dict[str, list[str]]:
    return _load(F_TAGS)


def load_links() -> dict[str, dict[str, list[str]]]:
    return _load(F_LINKS)


def load_moc() -> dict[str, Any]:
    return _load(F_MOC)
