"""测试: 确定性关联打分引擎 (relations.py)。"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.relations import (
    _tokenize,
    compute_relations,
    apply_relations,
    compute_and_apply,
)
from src.config import settings

from tests.helpers import make_note


class TestTokenize:
    """_tokenize: jieba 分词 + 停用词过滤。"""

    def test_simple_keywords(self):
        tokens = _tokenize("AI Agent 架构设计")
        assert "AI" in tokens or "ai" in tokens
        # jieba 可能将"架构设计"作为一个复合词
        assert "架构设计" in tokens or "架构" in tokens

    def test_stopwords_removed(self):
        tokens = _tokenize("的 了 是 Agent")
        assert "的" not in tokens
        assert "了" not in tokens
        assert "是" not in tokens
        assert "Agent" in tokens or "agent" in tokens

    def test_empty_input(self):
        assert _tokenize("") == set()
        assert _tokenize("   ") == set()

    def test_digits_removed(self):
        tokens = _tokenize("2024 年 Agent 架构")
        assert "2024" not in tokens


class TestComputeRelations:
    """compute_relations: 标签/标题打分。"""

    def test_tag_overlap_scores(self, tmp_kb: Path, note_in: Path):
        """标签重合 2 个 (AI, 架构) → +6 分，应 >= 阈值 4。"""
        proc = tmp_kb / "my_kb" / "processed"
        make_note(proc, "other", "其他笔记", ["AI", "架构", "设计"])
        hits = compute_relations(note_in)
        assert len(hits) >= 1
        hit = [h for h in hits if h.filename == "other.md"]
        assert hit
        # 标签重合: AI, 架构 → 2*3=6; 标题: "AI Agent 架构" ∩ "其他笔记" → 可能 0
        assert hit[0].score >= 6

    def test_title_token_overlap(self, tmp_kb: Path, note_in: Path):
        """标题分词重合 (Agent) → +1 分，标签无重合 → 总分 1，低于阈值 → 不命中。"""
        proc = tmp_kb / "my_kb" / "processed"
        make_note(proc, "other", "Agent 框架对比", ["框架"])
        hits = compute_relations(note_in)
        # Agent 是英文词, 在 new_title_tokens 中应为 lower "agent"
        # 但也可能在 jieba 分词后被切分
        hit = [h for h in hits if h.filename == "other.md"]
        if hit:
            # 标签: [AI,Agent,架构] ∩ [框架] = 0 → 0 分
            # 标题: 可能重合 0-1 个词 → 0-1 分，小于阈值
            assert hit[0].score < 4

    def test_no_other_notes(self, tmp_kb: Path, note_in: Path):
        """无老笔记时结果为空列表。"""
        hits = compute_relations(note_in)
        assert hits == []

    def test_score_ordering(self, tmp_kb: Path, note_in: Path):
        """多个老笔记，高分优先。"""
        proc = tmp_kb / "my_kb" / "processed"
        make_note(proc, "high-score", "高相关笔记", ["AI", "Agent", "架构", "设计"])
        make_note(proc, "low-score", "低相关笔记", ["前端"])
        hits = compute_relations(note_in)
        high = [h for h in hits if h.filename == "high-score.md"]
        low = [h for h in hits if h.filename == "low-score.md"]
        assert high
        if low:
            assert high[0].score > low[0].score


class TestApplyRelations:
    """apply_relations: 双向写入 related 字段 + 相关笔记段。"""

    def test_bidirectional_update(self, tmp_kb: Path, note_in: Path):
        """新笔记和老笔记相互写入相关字段。"""
        from src.schemas import RelationHit

        proc = tmp_kb / "my_kb" / "processed"
        other = make_note(proc, "older", "老笔记", ["AI", "Agent"])

        # 处理新笔记时不应从配置文件读取旧的文件
        hits = [
            RelationHit(filename="older.md", score=6),
        ]
        apply_relations(note_in, hits)

        # 验证新笔记的 related 包含老笔记
        import frontmatter
        post_new = frontmatter.loads(note_in.read_text(encoding="utf-8"))
        assert "older" in post_new.metadata.get("related", [])
        body = post_new.content
        assert "[[older]]" in body

        # 验证老笔记的 related 包含新笔记
        post_old = frontmatter.loads(other.read_text(encoding="utf-8"))
        assert note_in.stem in post_old.metadata.get("related", [])
        assert f"[[{note_in.stem}]]" in post_old.content

    def test_no_hits_no_change(self, tmp_kb: Path, note_in: Path):
        """空命中列表不修改任何文件。"""
        apply_relations(note_in, [])
        content_before = note_in.read_text(encoding="utf-8")
        # 再次调用
        apply_relations(note_in, [])
        assert note_in.read_text(encoding="utf-8") == content_before


class TestComputeAndApply:
    """端到端: compute_relations + apply_relations。"""

    def test_full_pipeline(self, tmp_kb: Path, note_in: Path):
        """完整 pipeline 执行不抛异常。"""
        proc = tmp_kb / "my_kb" / "processed"
        make_note(proc, "other", "其他笔记", ["AI", "架构"])
        # 不应抛异常
        compute_and_apply(note_in)


class TestEdgeCases:
    """边界情况: 文件名含特殊字符、标签为空等。"""

    def test_different_case_tags(self, tmp_kb: Path, note_in: Path):
        """标签大小写不同应统一匹配（_normalize_tag 转小写）。"""
        from src.relations import compute_relations

        proc = tmp_kb / "my_kb" / "processed"
        make_note(proc, "lowercase", "小写标签笔记", ["ai", "架构"])
        hits = compute_relations(note_in)
        hit = [h for h in hits if h.filename == "lowercase.md"]
        assert hit
        assert hit[0].score >= 6
