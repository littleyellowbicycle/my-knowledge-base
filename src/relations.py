"""确定性关联打分引擎 (核心算法，替代 LLM 随意生成双链)。

职责 (对应 Implementation_plan Step 3):
    1. jieba 分词 + 内置停用词表，提取标题/标签中的关键词
    2. compute_relations(new_note_path):
       遍历老笔记，标签重合 +3/个，标题分词重合 +1/个，计算总分
    3. 筛选分数 >= 阈值的笔记，apply_relations() 双向更新:
       - 双方 Frontmatter 的 related 字段
       - 文末 ## 相关笔记 段的 [[]] 双链
       - updated 字段
    4. compute_and_apply() 作为钩子挂到 processor 末尾自动执行

设计原则: "确定性优先" —— 关联关系完全由算法决定，LLM 不参与。
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
from pathlib import Path
from typing import Iterable

import frontmatter
import jieba

from src.config import settings
from src.schemas import RelationHit

logger = logging.getLogger(__name__)

# ---------- 内置停用词表 (精简，覆盖常见虚词/代词/量词) ----------
_STOPWORDS: set[str] = {
    "的", "了", "和", "与", "及", "或", "是", "在", "为", "对", "由", "从",
    "把", "被", "将", "给", "向", "于", "以", "其", "之", "等", "这", "那",
    "我", "你", "他", "她", "它", "们", "着", "过", "地", "得", "也", "又",
    "都", "就", "还", "已", "将", "能", "可", "应", "要", "会", "让", "使",
    "但", "而", "则", "若", "如", "因", "故", "所", "即", "并", "且", "或者",
    "一", "二", "三", "四", "五", "六", "七", "八", "九", "十", "百", "千",
    "个", "些", "种", "类", "项", "条", "篇", "本", "份", "组", "批", "次",
    "上", "下", "中", "内", "外", "前", "后", "左", "右", "里", "间", "边",
    "什么", "怎么", "为什么", "如何", "哪里", "哪个", "怎样", "多少",
    "这个", "那个", "这些", "那些", "这样", "那样",
    "可以", "需要", "应该", "可能", "或者", "以及", "但是", "因为", "所以",
    "使用", "通过", "进行", "实现", "包括", "包含", "具有", "属于", "作为",
    "关于", "对于", "至于", "由于", "基于", "根据",
    "a", "an", "the", "of", "to", "in", "on", "for", "and", "or", "is", "are",
    "with", "by", "as", "at", "from", "that", "this", "it", "be",
}

# 只保留长度>=2 的词，或纯英文字母词
_TOKEN_MIN_LEN = 2


def _tokenize(text: str) -> set[str]:
    """jieba 分词 -> 过滤停用词/纯数字/单字。返回词集合 (确定性)。"""
    if not text:
        return set()
    tokens: set[str] = set()
    for tok in jieba.cut(text, cut_all=False):
        tok = tok.strip()
        if not tok or tok in _STOPWORDS:
            continue
        if tok.isdigit():
            continue
        # 纯英文字母词允许长度 1 (如 RAG 中的 R 不常见，但保险)
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", tok):
            tokens.add(tok.lower())
            continue
        # 中文词要求长度 >=2
        if len(tok) >= _TOKEN_MIN_LEN:
            tokens.add(tok)
    return tokens


def _normalize_tag(tag: str) -> str:
    return tag.strip().lower()


# ---------- 笔记读取/解析 ----------
def _load_note(path: Path) -> frontmatter.Post:
    text = path.read_text(encoding="utf-8")
    return frontmatter.loads(text)


def _note_stem(path: Path) -> str:
    """文件名去扩展名，作为 [[]] 双链目标 (与 Obsidian 一致)。"""
    return path.stem


def _iter_other_notes(exclude: Path) -> Iterable[Path]:
    """遍历 processed/ 下除 exclude 外的所有 .md。"""
    for p in settings.PROCESSED_DIR.glob("*.md"):
        if p.resolve() != exclude.resolve():
            yield p


# ---------- 打分 ----------
def compute_relations(new_note_path: Path) -> list[RelationHit]:
    """对新笔记计算与所有老笔记的关联分数，返回 >= 阈值的命中列表 (降序)。

    打分规则:
        标签重合  +3 / 个
        标题分词重合 +1 / 个
    """
    new_post = _load_note(new_note_path)
    new_tags = {_normalize_tag(t) for t in new_post.metadata.get("tags", [])}
    new_title_tokens = _tokenize(new_post.metadata.get("title", ""))

    hits: list[RelationHit] = []
    for other in _iter_other_notes(new_note_path):
        try:
            other_post = _load_note(other)
        except Exception as e:  # noqa: BLE001
            logger.warning("解析失败 %s: %s", other.name, e)
            continue
        other_tags = {_normalize_tag(t) for t in other_post.metadata.get("tags", [])}
        other_title_tokens = _tokenize(other_post.metadata.get("title", ""))

        tag_overlap = len(new_tags & other_tags)
        token_overlap = len(new_title_tokens & other_title_tokens)
        score = tag_overlap * 3 + token_overlap * 1

        if score >= settings.RELATION_SCORE_THRESHOLD:
            hits.append(RelationHit(filename=other.name, score=score))

    hits.sort(key=lambda h: h.score, reverse=True)
    return hits[: settings.RELATION_TOP_N]


# ---------- 双向写回 ----------
_RELATED_SECTION_RE = re.compile(
    r"(## 相关笔记\s*\n)(.*?)(?=\n## |\Z)", re.DOTALL
)


def _rewrite_related_section(body: str, links: list[str]) -> str:
    """重写正文中的 ## 相关笔记 段。若无此段则追加到文末。"""
    lines = "\n".join(f"- [[{name}]]" for name in links)
    section = f"## 相关笔记\n{lines}\n"

    if _RELATED_SECTION_RE.search(body):
        return _RELATED_SECTION_RE.sub(
            lambda m: m.group(1) + lines + "\n", body
        )
    # 无该段，追加
    if not body.endswith("\n"):
        body += "\n"
    return body + "\n" + section


def _update_note_related(
    path: Path,
    add_links: list[str],
) -> bool:
    """把 add_links (文件名 stem 列表) 合并进笔记的 related 字段 + 相关笔记段。

    返回是否有变更。
    """
    post = _load_note(path)
    related: list[str] = list(post.metadata.get("related", []) or [])
    stem_self = _note_stem(path)

    changed = False
    for link in add_links:
        if link == stem_self:
            continue
        if link not in related:
            related.append(link)
            changed = True

    if changed:
        post.metadata["related"] = related
        post.metadata["updated"] = _dt.date.today().isoformat()
        post.content = _rewrite_related_section(post.content, related)
        path.write_text(frontmatter.dumps(post, sort_keys=False), encoding="utf-8")
    return changed


def apply_relations(new_note_path: Path, hits: list[RelationHit]) -> None:
    """双向更新: 新笔记 <-> 命中的老笔记。"""
    if not hits:
        return
    new_stem = _note_stem(new_note_path)
    target_stems = [Path(h.filename).stem for h in hits]

    # 1) 新笔记写入老笔记链接
    _update_note_related(new_note_path, target_stems)

    # 2) 反向: 每个老笔记写入新笔记链接
    for stem, hit in zip(target_stems, hits):
        other_path = settings.PROCESSED_DIR / hit.filename
        if other_path.exists():
            _update_note_related(other_path, [new_stem])
    logger.info("关联建立: %s <-> %d 篇", new_note_path.name, len(hits))


# ---------- 钩子入口 (供 processor 调用) ----------
def compute_and_apply(new_note_path: Path) -> None:
    """processor 加工完成后的钩子: 计算并双向写入关联。"""
    hits = compute_relations(new_note_path)
    if hits:
        names = ", ".join(f"{h.filename}({h.score})" for h in hits)
        logger.info("关联命中: %s", names)
    apply_relations(new_note_path, hits)
