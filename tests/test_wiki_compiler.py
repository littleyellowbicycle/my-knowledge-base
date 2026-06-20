"""测试: Wiki 编译层 (wiki_compiler.py) — 关联簇检测 + 后处理。"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.wiki_compiler import find_clusters, _build_graph, _post_process_wiki, _known_stems
from src.config import settings

from tests.helpers import make_links_json


class TestBuildGraph:
    """_build_graph: links.json → 无向图。"""

    def _setup(self, index_dir: Path):
        data = {
            "note-a": {"outgoing": ["note-b"], "incoming": []},
            "note-b": {"outgoing": ["note-a"], "incoming": ["note-a"]},
            "note-c": {"outgoing": [], "incoming": []},
        }
        make_links_json(index_dir, data)

    def test_graph_build(self, tmp_kb: Path):
        """links 正确转为无向图。"""
        index = tmp_kb / "my_kb" / "index"
        self._setup(index)
        from src.indexer import load_links
        links = load_links()
        g = _build_graph(links)
        assert "note-a" in g
        assert "note-b" in g["note-a"]
        assert "note-a" in g["note-b"]
        # isolated
        assert "note-c" in g
        assert len(g["note-c"]) == 0


class TestFindClusters:
    """find_clusters: 连通分量检测。"""

    def _setup(self, index_dir: Path):
        data = {
            "note-a": {"outgoing": ["note-b"], "incoming": []},
            "note-b": {"outgoing": ["note-a"], "incoming": ["note-a"]},
            "note-c": {"outgoing": ["note-d", "note-e"], "incoming": []},
            "note-d": {"outgoing": ["note-c"], "incoming": ["note-c"]},
            "note-e": {"outgoing": ["note-c", "note-f"], "incoming": ["note-c"]},
            "note-f": {"outgoing": ["note-e"], "incoming": ["note-e"]},
            "alone": {"outgoing": [], "incoming": []},
        }
        make_links_json(index_dir, data)

    def test_two_clusters(self, tmp_kb: Path):
        """两个连通分量: {a,b} 和 {c,d,e,f}, alone 被过滤。"""
        index = tmp_kb / "my_kb" / "index"
        self._setup(index)
        clusters = find_clusters(min_size=2)
        assert len(clusters) == 2
        # 更大的簇优先
        assert len(clusters[0]) == 4  # c,d,e,f
        assert len(clusters[1]) == 2  # a,b

    def test_min_size_filter(self, tmp_kb: Path):
        """min_size=4 只返回 >=4 的簇。"""
        index = tmp_kb / "my_kb" / "index"
        self._setup(index)
        clusters = find_clusters(min_size=4)
        assert len(clusters) == 1
        assert len(clusters[0]) == 4

    def test_empty_links(self, tmp_kb: Path):
        """links.json 不存在时返回空列表。"""
        clusters = find_clusters()
        assert clusters == []

    def test_single_node_cluster(self, tmp_kb: Path):
        """孤立节点 (无边) 且 min_size=1 返回单节点簇。"""
        index = tmp_kb / "my_kb" / "index"
        make_links_json(index, {"only": {"outgoing": [], "incoming": []}})
        clusters = find_clusters(min_size=1)
        assert len(clusters) == 1
        assert clusters[0] == ["only"]

    def test_reverse_edge_only(self, tmp_kb: Path):
        """只有反向边 (incoming) 也应连接。"""
        index = tmp_kb / "my_kb" / "index"
        data = {"a": {"outgoing": [], "incoming": ["b"]},
                "b": {"outgoing": [], "incoming": []}}
        make_links_json(index, data)
        clusters = find_clusters(min_size=2)
        assert len(clusters) == 1
        assert set(clusters[0]) == {"a", "b"}


class TestPostProcessWiki:
    """> _post_process_wiki: 确定性双链覆盖。"""

    def test_removes_dangling_md_links(self, tmp_kb: Path):
        """指向不存在笔记的 [[nonexistent.md]] → 清理为 nonexistent。"""
        content = "参考 [[nonexistent.md]] 的结论。\n"
        result = _post_process_wiki(content, ["note-a"])
        assert "[[nonexistent]]" not in result
        # nonexistent 仍在 known 外, 但 .md 后缀被清理掉了

    def test_keeps_known_links(self, tmp_kb: Path):
        """指向已知笔记的 [[note-a]] 保留。"""
        # 创建一个 known note
        known = tmp_kb / "my_kb" / "processed"
        (known / "note-a.md").write_text("# Note A\n", encoding="utf-8")
        content = "参考 [[note-a]] 的结论。\n"
        result = _post_process_wiki(content, ["note-a"])
        assert "[[note-a]]" in result

    def test_appends_related_section(self, tmp_kb: Path):
        """文末追加 ## 相关笔记 段。"""
        content = "# 测试综述\n\n正文内容。\n"
        result = _post_process_wiki(content, ["note-a", "note-b"])
        assert "## 相关笔记" in result
        assert "[[note-a]]" in result
        assert "[[note-b]]" in result

    def test_replaces_existing_related(self, tmp_kb: Path):
        """已有的 ## 相关笔记 段被替换。"""
        content = "# 测试\n\n## 相关笔记\n- [[old]]\n\n## 其他\n"
        result = _post_process_wiki(content, ["new"])
        assert "[[old]]" not in result
        assert "[[new]]" in result


class TestKnownStems:
    """> _known_stems: 同时扫描 processed/ 和 wiki/。"""

    def test_includes_both(self, tmp_kb: Path):
        proc = tmp_kb / "my_kb" / "processed"
        wiki = tmp_kb / "my_kb" / "wiki"
        (proc / "note-a.md").write_text("", encoding="utf-8")
        (wiki / "review-wiki.md").write_text("", encoding="utf-8")
        stems = _known_stems()
        assert "note-a" in stems
        assert "review-wiki" in stems

    def test_empty_dirs(self, tmp_kb: Path):
        assert _known_stems() == set()
