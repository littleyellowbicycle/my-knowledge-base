"""pytest fixtures — 临时知识库目录。

通过 monkeypatch 替换 src.config.settings 的各层路径，
使被测试模块在临时目录下运行，不污染真实知识库。
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Iterator

import frontmatter
import pytest

from src.config import settings


@pytest.fixture
def tmp_kb(monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """创建临时知识库，返回 tmp 根目录。monkeypatch 各层路径。"""
    with tempfile.TemporaryDirectory() as root:
        root_p = Path(root)
        raw = root_p / "my_kb" / "raw"
        processed = root_p / "my_kb" / "processed"
        wiki = root_p / "my_kb" / "wiki"
        index = root_p / "my_kb" / "index"
        for d in (raw, processed, wiki, index):
            d.mkdir(parents=True, exist_ok=True)

        for attr, val in [("RAW_DIR", raw), ("PROCESSED_DIR", processed),
                          ("WIKI_DIR", wiki), ("INDEX_DIR", index),
                          ("KB_ROOT", root_p / "my_kb")]:
            monkeypatch.setattr(settings, attr, val)
        yield root_p


@pytest.fixture
def note_in(tmp_kb: Path) -> Path:
    """在临时 processed/ 创建一篇样本笔记，返回其路径。"""
    from tests.helpers import make_note
    proc = tmp_kb / "my_kb" / "processed"
    return make_note(proc, "agent-note", "AI Agent 架构", ["AI", "Agent", "架构"])
