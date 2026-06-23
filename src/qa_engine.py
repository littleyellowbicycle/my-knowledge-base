"""输出引擎 - 问答流 (模块 C1)。

流程 (严格遵循架构 V2.1 问答流约束):
    1. 优先查 Wiki 层 (type == "wiki"): 宏观综述回答宏观问题
    2. 未命中则降级查 Processed 层 (type == "note"): 原子笔记回答细节问题
    3. Wiki 命中时可拉取其 outgoing links 对应笔记的核心结论作为补充上下文
    4. 读加工层对应笔记的 ## 核心结论 段落 (不读全文，不读原料层)
    5. LLM 综合结论 + 用户问题 -> 生成回答，附带来源笔记 [[]] 链接

关键约束:
    - 禁止回头读原料层原文
    - 回答必须标注来源笔记名
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional

import frontmatter
from pydantic import BaseModel, Field

from src.config import settings
from src.indexer import load_summaries, rebuild_index
from src.llm_adapter import llm

logger = logging.getLogger(__name__)

# 单条 summary 在 prompt 中的最大字符数 (避免 token 爆炸)
_SUMMARY_CHAR_CAP = 300
_TOP_K = 3
_CONCLUSION_RE = re.compile(r"##\s*核心结论\s*\n(.*?)(?=\n##\s|\Z)", re.DOTALL)


class NoteSelection(BaseModel):
    """LLM 选笔记的强类型输出。"""

    top_filenames: list[str] = Field(
        ..., description="最相关笔记的文件名(含 .md 后缀)，按相关度降序"
    )
    reasons: list[str] = Field(
        default_factory=list, description="每篇一句相关性理由 (可选)"
    )


# ---------- 按类型过滤 ----------
def _filter_by_type(
    summaries: dict[str, dict], note_type: str
) -> dict[str, dict]:
    """从 summaries 中筛选指定 type 的子集。"""
    return {k: v for k, v in summaries.items() if v.get("type") == note_type}


# ---------- 选笔记 ----------
def _build_selection_prompt(
    question: str, summaries: dict[str, dict], label: str = "笔记"
) -> str:
    lines = [
        f"用户问题: {question}",
        "",
        f"可用{label}列表 (filename | 标题 | 标签 | 核心结论):",
    ]
    for fname, s in summaries.items():
        title = s.get("title", fname)
        tags = ",".join(s.get("tags", []))
        conclusion = (s.get("conclusion") or "")[:_SUMMARY_CHAR_CAP]
        lines.append(f"- {fname} | {title} | [{tags}] | {conclusion}")
    lines.append("")
    lines.append(
        "请从中选出与问题最相关的笔记文件名，按相关度降序返回。"
        "若没有相关笔记，返回空数组。"
    )
    return "\n".join(lines)


def _select_notes(
    question: str,
    summaries: dict[str, dict],
    *,
    top_k: int = _TOP_K,
    label: str = "笔记",
) -> list[str]:
    """让 LLM 从 summaries 选 Top-K 笔记文件名。"""
    if not summaries:
        return []
    prompt = _build_selection_prompt(question, summaries, label=label)
    selection = llm.chat_json(
        prompt,
        schema=NoteSelection,
        system="你是一名知识库检索器。只根据用户问题与笔记摘要判断相关性，不要编造笔记。",
        model=settings.MODEL_QA,
    )
    valid = [f for f in selection.top_filenames if f in summaries]
    return valid[:top_k]


# ---------- 读正文 (wiki 读全文，笔记只读结论) ----------
def _read_body_for_answer(filename: str, note_type: str) -> str:
    """读取笔记正文作为上下文。

    Wiki 综述: 返回全文 (综述本身已是宏观回答)
    普通笔记: 返回 ## 核心结论 段落
    """
    base_dir = settings.WIKI_DIR if note_type == "wiki" else settings.PROCESSED_DIR
    path = base_dir / filename
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8")
    try:
        post = frontmatter.loads(text)
        body = post.content
    except Exception:  # noqa: BLE001
        body = text

    if note_type == "wiki":
        return body.strip()
    # 普通笔记: 只读核心结论
    m = _CONCLUSION_RE.search(body)
    if not m:
        return ""
    raw = m.group(1).strip()
    return re.sub(r"^\s*>\s?", "", raw, flags=re.MULTILINE).strip()


def _read_conclusion(filename: str, note_type: str = "note") -> str:
    """兼容旧接口: 仅读取核心结论。"""
    return _read_body_for_answer(filename, note_type)


# ---------- 生成回答 ----------
_ANSWER_SYSTEM = (
    "你是一名知识库问答助手。只能根据提供的参考资料回答用户问题。"
    "若资料不足以回答，明确说明知识库中暂无相关信息，不要编造。"
    "回答末尾必须用 [[]] 标注来源笔记，每条来源单独一行。"
)


def _build_answer_prompt(
    question: str, contexts: list[tuple[str, str, str]]
) -> str:
    """contexts: list of (filename, title, body)。"""
    blocks = []
    for fname, title, body in contexts:
        blocks.append(
            f"### 来源: [[{Path(fname).stem}]]\n"
            f"标题: {title}\n参考资料:\n{body}"
        )
    ctx = "\n\n".join(blocks) if blocks else "(知识库中无相关笔记)"
    return (
        f"用户问题:\n{question}\n\n"
        f"知识库中的参考资料:\n{ctx}\n\n"
        "请基于上述参考资料回答。末尾列出来源笔记的 [[]] 双链。"
    )


def _generate_answer(
    question: str, contexts: list[tuple[str, str, str]]
) -> str:
    """根据 contexts 生成回答，自动补来源。"""
    prompt = _build_answer_prompt(question, contexts)
    answer = llm.chat(prompt, system=_ANSWER_SYSTEM, model=settings.MODEL_QA)
    if "[[" not in answer:
        sources = "\n".join(
            f"- [[{Path(f).stem}]]" for f, _, _ in contexts
        )
        answer = f"{answer}\n\n---\n来源:\n{sources}"
    return answer


def _enrich_with_outgoing(
    contexts: list[tuple[str, str, str]],
    wiki_files: list[str],
    all_summaries: dict[str, dict],
) -> list[tuple[str, str, str]]:
    """Wiki 命中时，附带拉取其 outgoing links 对应笔记的核心结论。"""
    added_stems: set[str] = set()
    extra: list[tuple[str, str, str]] = []
    for fname in wiki_files:
        s = all_summaries.get(fname, {})
        for link_stem in s.get("links", []):
            linked_fn = f"{link_stem}.md"
            linked_s = all_summaries.get(linked_fn)
            if linked_s and linked_s.get("type") != "wiki" and link_stem not in added_stems:
                body = _read_body_for_answer(linked_fn, "note")
                if body:
                    extra.append((linked_fn, linked_s.get("title", link_stem), body))
                    added_stems.add(link_stem)
    return contexts + extra


# ---------- 问答主入口 ----------
def qa(question: str, *, auto_rebuild: bool = False) -> str:
    """问答主入口 — 两步走检索。

    Args:
        question: 用户问题
        auto_rebuild: 索引不存在时是否自动重建 (默认 False，提示用户手动)
    Returns:
        带来源 [[]] 链接的回答文本
    """
    question = (question or "").strip()
    if not question:
        return "请输入问题。"

    summaries = load_summaries()
    if not summaries:
        if auto_rebuild:
            logger.info("索引为空，自动重建...")
            rebuild_index()
            summaries = load_summaries()
        if not summaries:
            return "知识库索引为空，请先 `kb ingest` 录入原料并 `kb process` 加工，再 `kb index` 重建索引。"

    # 按类型拆分
    wiki_sums = _filter_by_type(summaries, "wiki")
    note_sums = _filter_by_type(summaries, "note")

    contexts: list[tuple[str, str, str]] = []

    # ---- 第一步: 优先查 Wiki 层 ----
    if wiki_sums:
        logger.info("第一步: 检索 Wiki 综述层 (%d 篇)", len(wiki_sums))
        wiki_files = _select_notes(
            question, wiki_sums, top_k=2, label="综述"
        )
        if wiki_files:
            logger.info("Wiki 命中: %s", wiki_files)
            for fname in wiki_files:
                s = wiki_sums.get(fname, {})
                body = _read_body_for_answer(fname, "wiki")
                contexts.append((fname, s.get("title", fname), body))
            # 附带 outgoing links 的结论作为补充
            contexts = _enrich_with_outgoing(
                contexts, wiki_files, summaries
            )
            return _generate_answer(question, contexts)

    # ---- 第二步: 未命中，降级查 Processed 层 ----
    if note_sums:
        logger.info("第二步: 降级检索原子笔记层 (%d 篇)", len(note_sums))
        note_files = _select_notes(
            question, note_sums, top_k=_TOP_K, label="笔记"
        )
        if note_files:
            logger.info("原子笔记命中: %s", note_files)
            for fname in note_files:
                s = note_sums.get(fname, {})
                body = _read_body_for_answer(fname, "note")
                contexts.append((fname, s.get("title", fname), body))
            return _generate_answer(question, contexts)

    return "知识库中暂无与该问题相关的笔记。"
