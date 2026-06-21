"""集成测试: 全链路冒烟测试 (ingest -> process -> index -> qa -> wiki)。

所有 LLM 调用通过 monkeypatch 模拟返回固定 JSON，不依赖真实 API。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import frontmatter
import pytest

from src.config import settings
from tests.helpers import make_note


# ===================================================================
#  Mock 工厂
# ===================================================================

def _fake_process_json(prompt: str, *, schema: type, **kwargs: Any) -> Any:
    """模拟 process_note 用 llm.chat_json 返回 ProcessedNote。"""
    return schema(
        title="AI Agent 入门指南",
        conclusion="AI Agent 是自主决策的智能体。本文介绍了基础概念。",
        body_markdown="## 什么是 AI Agent\n\nAI Agent 能够感知环境并采取行动。参见 [[强化学习]]。",
        tags=["AI", "Agent", "入门"],
        related=[],
    )


def _fake_select_json(prompt: str, *, schema: type, **kwargs: Any) -> Any:
    """模拟 QA 选笔记用 llm.chat_json 返回 NoteSelection。"""
    from src.qa_engine import NoteSelection
    return NoteSelection(
        top_filenames=["agent-note.md"],
        reasons=["直接讨论了 AI Agent 架构"],
    )


def _fake_qa_chat(prompt: str, **kwargs: Any) -> str:
    """模拟 QA 综合回答用 llm.chat 返回固定答案。"""
    return (
        "AI Agent 的架构包括感知层、决策层和执行层。"
        "\n\n来源:\n- [[agent-note]]"
    )


def _fake_wiki_chat(prompt: str, **kwargs: Any) -> str:
    """模拟 wiki compiler 用 llm.chat 返回综述。"""
    return (
        "# AI Agent 知识综述\n\n"
        "## 概述\nAI Agent 是人工智能领域的核心概念。\n\n"
        "## 核心内容\n"
        "AI Agent 能够自主决策。参见 [[强化学习]]。\n\n"
        "## 应用场景\n广泛应用于自动化、机器人等领域。\n\n"
        "## 相关笔记\n- [[agent-note]]\n"
    )


# ===================================================================
#  测试类
# ===================================================================

class TestPipelineIngestProcessIndex:
    """验证 ingest → process → index 全链路。"""

    def test_ingest_manual_text(self, tmp_kb: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.raw_store import save_manual

        entry = save_manual("AI Agent 是一种能够自主决策的智能体程序。")
        assert entry.source_type == "manual"
        assert entry.status == "pending"
        assert entry.original_text == "AI Agent 是一种能够自主决策的智能体程序。"
        # 验证文件落盘
        meta_path = settings.RAW_DIR / f"{entry.id}.meta.json"
        assert meta_path.exists()
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        assert meta["id"] == entry.id
        assert meta["status"] == "pending"

    def test_ingest_then_process_then_index(
        self, tmp_kb: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src.raw_store import save_manual
        from src.processor import process_note
        from src.indexer import rebuild_index

        monkeypatch.setattr("src.processor.llm.chat_json", _fake_process_json)

        # Ingest
        entry = save_manual("AI Agent 是一种能够自主决策的智能体程序。")

        # Process
        note_path = process_note(entry.id)
        assert note_path.exists()
        assert note_path.suffix == ".md"

        post = frontmatter.loads(note_path.read_text(encoding="utf-8"))
        assert post.metadata["title"] == "AI Agent 入门指南"
        assert post.metadata["status"] == "processed"
        assert "AI" in post.metadata["tags"]
        assert "## 核心结论" in post.content
        assert "AI Agent 是自主决策的智能体" in post.content

        # 验证原料状态推进到 processed
        meta = json.loads(
            (settings.RAW_DIR / f"{entry.id}.meta.json").read_text(encoding="utf-8")
        )
        assert meta["status"] == "processed"

        # Index
        from src.indexer import load_summaries
        stats = rebuild_index()
        assert stats["notes"] >= 1

        summaries = load_summaries()
        assert isinstance(summaries, dict)

        # 找到刚加工的笔记
        key = f"{note_path.stem}.md"
        assert key in summaries, f"summaries 中应包含 {key}，实际有 {list(summaries.keys())}"
        assert summaries[key]["title"] == "AI Agent 入门指南"
        assert "AI" in summaries[key]["tags"]

        # 验证索引文件落盘
        assert (settings.INDEX_DIR / "summaries.json").exists()
        assert (settings.INDEX_DIR / "tags.json").exists()
        assert (settings.INDEX_DIR / "links.json").exists()
        assert (settings.INDEX_DIR / "moc.json").exists()

    def test_ingest_url_uses_gateway(
        self, tmp_kb: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src.raw_store import save_link

        def _fake_fetch(url: str) -> str:
            return "模拟的网页抓取内容。AI Agent 是热门话题。"

        monkeypatch.setattr("src.gateway.fetch_url", _fake_fetch)

        entry = save_link("https://example.com/ai-agent")
        assert entry.source_type == "link"
        assert entry.source_url == "https://example.com/ai-agent"
        assert "模拟的网页抓取内容" in entry.original_text


class TestPipelineQa:
    """验证索引就绪后的 QA 流。"""

    def test_qa_with_indexed_notes(
        self, tmp_kb: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src.qa_engine import qa
        from src.indexer import rebuild_index

        # 准备: 创建一篇加工笔记
        proc_dir = settings.PROCESSED_DIR
        make_note(proc_dir, "agent-note", "AI Agent 架构", ["AI", "Agent"],
                  body="# AI Agent 架构\n\n## 核心结论\n> AI Agent 的架构包括感知、决策、执行三层。\n\n## 详细内容\n感知层负责环境理解。\n\n## 相关笔记\n")

        # 重建索引
        rebuild_index()

        # Mock QA 的 LLM 调用 (选笔记 + 综合回答)
        monkeypatch.setattr("src.qa_engine.llm.chat_json", _fake_select_json)
        monkeypatch.setattr("src.qa_engine.llm.chat", _fake_qa_chat)

        # 执行 QA
        answer = qa("AI Agent 的架构是什么？")
        assert isinstance(answer, str)
        assert len(answer) > 20
        assert "[[" in answer, f"回答应包含 [[]] 来源链接: {answer}"
        assert "agent-note" in answer or "agent" in answer.lower(), (
            f"回答应提及 agent-note: {answer}"
        )

    def test_qa_empty_index_returns_hint(
        self, tmp_kb: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src.qa_engine import qa

        # 索引为空 → 应返回提示信息
        answer = qa("AI Agent 是什么？")
        assert "索引为空" in answer or "请先" in answer

    def test_qa_auto_rebuild(
        self, tmp_kb: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src.qa_engine import qa
        from src.indexer import rebuild_index

        # 先有笔记和索引，然后清空索引模拟 "重建后可用"
        proc_dir = settings.PROCESSED_DIR
        make_note(proc_dir, "agent-note", "AI Agent 架构", ["AI", "Agent"],
                  body="# AI Agent\n\n## 核心结论\n> AI Agent 架构。\n\n## 详细内容\n内容。\n\n## 相关笔记\n")
        rebuild_index()

        monkeypatch.setattr("src.qa_engine.llm.chat_json", _fake_select_json)
        monkeypatch.setattr("src.qa_engine.llm.chat", _fake_qa_chat)

        answer = qa("AI Agent 架构？", auto_rebuild=True)
        assert "[[" in answer
        assert "agent-note" in answer or "agent" in answer.lower()


class TestPipelineRelations:
    """验证关联引擎在加工后自动触发。"""

    def test_relations_fire_on_process(
        self, tmp_kb: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src.raw_store import save_manual
        from src.processor import process_note
        from src.indexer import rebuild_index

        monkeypatch.setattr("src.processor.llm.chat_json", _fake_process_json)

        # 先创建一篇已有笔记 (含 "AI" 标签，与新笔记重叠)
        make_note(settings.PROCESSED_DIR, "existing-note", "Existing AI Note",
                  ["AI", "机器学习"],
                  body="# Existing\n\n## 核心结论\n> 已有笔记核心结论。\n\n## 详细内容\n内容。\n\n## 相关笔记\n")

        # 此时 processed/ 有两篇: existing-note.md 和 ai-agent-guide.md
        # 但我们需要 process_note 生成第二篇
        entry = save_manual("AI Agent 相关内容。")
        note_path = process_note(entry.id)

        # 读取新笔记，验证 related 字段非空 (关联引擎自动触发)
        post = frontmatter.loads(note_path.read_text(encoding="utf-8"))
        related = post.metadata.get("related", [])
        # "AI" 标签重叠 → +3，关联打分阈值 4，可能 token 也有得分
        assert len(related) >= 1, (
            f"新笔记 related 应为非空。现有 related: {related}"
        )

        # 验证双向: 老笔记也关联了新笔记
        existing_path = settings.PROCESSED_DIR / "existing-note.md"
        existing_post = frontmatter.loads(existing_path.read_text(encoding="utf-8"))
        existing_related = existing_post.metadata.get("related", [])
        assert any(note_path.stem in r for r in existing_related), (
            f"老笔记 related 应包含 {note_path.stem}。现有: {existing_related}"
        )


class TestPipelineWiki:
    """验证 Wiki 编译流。"""

    def test_wiki_compile_cluster(
        self, tmp_kb: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src.indexer import rebuild_index
        from src.wiki_compiler import compile_all_wiki

        monkeypatch.setattr("src.wiki_compiler.llm.chat", _fake_wiki_chat)

        # 创建 3 篇互相关联的笔记 (满足簇大小 ≥3)
        proc = settings.PROCESSED_DIR
        make_note(proc, "ai-intro", "AI 简介", ["AI", "Agent"],
                  related=["agent-arch", "ml-basics"],
                  body="# AI 简介\n\n## 核心结论\n> AI 是计算机科学的分支。\n\n## 详细内容\nAI 涵盖多个子领域。\n\n## 相关笔记\n- [[agent-arch]]\n- [[ml-basics]]\n")
        make_note(proc, "agent-arch", "Agent 架构", ["AI", "Agent", "架构"],
                  related=["ai-intro", "ml-basics"],
                  body="# Agent 架构\n\n## 核心结论\n> Agent 架构包括感知、决策、执行。\n\n## 详细内容\n详见 [[强化学习]]。\n\n## 相关笔记\n- [[ai-intro]]\n- [[ml-basics]]\n")
        make_note(proc, "ml-basics", "机器学习基础", ["AI", "机器学习"],
                  related=["ai-intro", "agent-arch"],
                  body="# 机器学习基础\n\n## 核心结论\n> 机器学习是 AI 的核心方法。\n\n## 详细内容\n监督学习、无监督学习等。\n\n## 相关笔记\n- [[ai-intro]]\n- [[agent-arch]]\n")

        # 重建索引
        rebuild_index()

        # Wiki 编译
        results = compile_all_wiki(force_llm=True)
        assert len(results) >= 1, f"应有至少 1 篇 wiki 产出: {results}"

        # 验证 wiki 文件落盘
        for path in results:
            assert path.exists()
            assert path.suffix == ".md"
            # 验证 frontmatter 字段
            post = frontmatter.loads(path.read_text(encoding="utf-8"))
            assert "title" in post.metadata
            assert post.metadata["type"] == "wiki"

    def test_wiki_compile_requires_min_three(
        self, tmp_kb: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """< 3 篇关联笔记 → 不应编译新 wiki。"""
        from src.indexer import rebuild_index
        from src.wiki_compiler import compile_all_wiki

        monkeypatch.setattr("src.wiki_compiler.llm.chat", _fake_wiki_chat)

        proc = settings.PROCESSED_DIR
        make_note(proc, "note-a", "笔记 A", ["tag1"],
                  related=["note-b"])
        make_note(proc, "note-b", "笔记 B", ["tag2"],
                  related=["note-a"])

        rebuild_index()
        results = compile_all_wiki(force_llm=True)
        # 2 篇互相关联但不满足 ≥3 → 无 wiki 产出
        assert len(results) == 0, f"簇大小应 < 3，无 wiki 产出: {results}"
