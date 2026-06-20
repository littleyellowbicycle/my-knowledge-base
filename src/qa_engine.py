"""输出引擎 - 问答流 (模块 C1)。

流程 (严格遵循架构 V2.1 问答流约束):
    1. 查索引层 summaries.json
       -> 用 LLM 对所有 summary 做相关性判断 (全量塞入 prompt)
       -> 选出 Top-3 最相关笔记文件名
    2. 读加工层对应笔记的 ## 核心结论 段落 (不读全文，不读原料层)
    3. LLM 综合结论 + 用户问题 -> 生成回答，附带来源笔记 [[]] 链接

关键约束:
    - 禁止回头读原料层原文
    - 禁止读详细内容，只读核心结论
    - 回答必须标注来源笔记名

对外暴露:
    qa(question) -> str   问答主入口，返回带来源链接的回答
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
        ..., description=f"Top-{_TOP_K} 最相关笔记的文件名(含 .md 后缀)，按相关度降序"
    )
    reasons: list[str] = Field(
        default_factory=list, description="每篇一句相关性理由 (可选)"
    )


# ---------- 选笔记 ----------
def _build_selection_prompt(question: str, summaries: dict[str, dict]) -> str:
    lines = [f"用户问题: {question}", "", "可用笔记列表 (filename | 标题 | 标签 | 核心结论):"]
    for fname, s in summaries.items():
        title = s.get("title", fname)
        tags = ",".join(s.get("tags", []))
        conclusion = (s.get("conclusion") or "")[:_SUMMARY_CHAR_CAP]
        lines.append(f"- {fname} | {title} | [{tags}] | {conclusion}")
    lines.append("")
    lines.append(
        f"请从中选出与问题最相关的 Top-{_TOP_K} 篇笔记，按相关度降序返回文件名。"
        "若没有相关笔记，返回空数组。"
    )
    return "\n".join(lines)


def _select_notes(question: str, summaries: dict[str, dict]) -> list[str]:
    """让 LLM 从 summaries 选 Top-K 笔记文件名。"""
    if not summaries:
        return []
    prompt = _build_selection_prompt(question, summaries)
    selection = llm.chat_json(
        prompt,
        schema=NoteSelection,
        system="你是一名知识库检索器。只根据用户问题与笔记摘要判断相关性，不要编造笔记。",
        model=settings.MODEL_QA,
    )
    # 过滤掉不存在的文件名 (LLM 偶尔会幻觉)
    valid = [f for f in selection.top_filenames if f in summaries]
    # 不足 Top-K 不补齐 (诚实返回)
    return valid[:_TOP_K]


# ---------- 读核心结论 (从加工层/编译层文件) ----------
def _read_conclusion(filename: str, note_type: str = "note") -> str:
    """读取笔记的 ## 核心结论 段落。

    note="note"  从 processed/{filename} 读
    note="wiki"  从 wiki/{filename} 读
    严格遵循架构: 只读结论，不读全文，不读原料层。
    """
    base_dir = settings.WIKI_DIR if note_type == "wiki" else settings.PROCESSED_DIR
    path = base_dir / filename
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8")
    # 跳过 frontmatter
    try:
        post = frontmatter.loads(text)
        body = post.content
    except Exception:  # noqa: BLE001
        body = text
    m = _CONCLUSION_RE.search(body)
    if not m:
        return ""
    raw = m.group(1).strip()
    # 去 > 引用标记
    return re.sub(r"^\s*>\s?", "", raw, flags=re.MULTILINE).strip()


# ---------- 生成回答 ----------
_ANSWER_SYSTEM = (
    "你是一名知识库问答助手。只能根据提供的【核心结论】回答用户问题。"
    "若结论不足以回答，明确说明知识库中暂无相关信息，不要编造。"
    "回答末尾必须用 [[]] 标注来源笔记，每条来源单独一行。"
)


def _build_answer_prompt(question: str, contexts: list[tuple[str, str, str]]) -> str:
    """contexts: list of (filename, title, conclusion)。"""
    blocks = []
    for fname, title, conclusion in contexts:
        blocks.append(f"### 来源: [[{Path(fname).stem}]]\n标题: {title}\n核心结论:\n{conclusion}")
    ctx = "\n\n".join(blocks) if blocks else "(知识库中无相关笔记)"
    return (
        f"用户问题:\n{question}\n\n"
        f"知识库相关笔记的核心结论:\n{ctx}\n\n"
        "请基于上述结论回答。末尾列出来源笔记的 [[]] 双链。"
    )


def qa(question: str, *, auto_rebuild: bool = False) -> str:
    """问答主入口。

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

    # 1) 选笔记
    top_files = _select_notes(question, summaries)
    if not top_files:
        return "知识库中暂无与该问题相关的笔记。"

    # 2) 读核心结论 (wiki 综述从 wiki/ 读，普通笔记从 processed/ 读)
    contexts: list[tuple[str, str, str]] = []
    for fname in top_files:
        s = summaries.get(fname, {})
        note_type = s.get("type", "note")
        conclusion = _read_conclusion(fname, note_type) or s.get("conclusion", "")
        contexts.append((fname, s.get("title", fname), conclusion))

    # 3) 生成回答
    prompt = _build_answer_prompt(question, contexts)
    answer = llm.chat(prompt, system=_ANSWER_SYSTEM, model=settings.MODEL_QA)

    # 兜底: 若 LLM 忘记附来源，主动补上
    if "[[" not in answer:
        sources = "\n".join(f"- [[{Path(f).stem}]]" for f in top_files)
        answer = f"{answer}\n\n---\n来源:\n{sources}"
    return answer
