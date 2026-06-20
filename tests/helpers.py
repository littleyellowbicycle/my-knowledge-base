"""测试辅助函数 (不与 pytest conftest 耦合)。"""
from __future__ import annotations

import json
from pathlib import Path

import frontmatter


def make_note(directory: Path, stem: str, title: str, tags: list[str],
              body: str = "", related: list[str] | None = None) -> Path:
    """在 directory 下创建一篇 processed 笔记。"""
    content = body or (
        f"# {title}\n\n"
        f"## 核心结论\n> 这是 {title} 的核心结论。\n\n"
        f"## 详细内容\n内容占位。\n\n"
        f"## 相关笔记\n"
    )
    post = frontmatter.Post(
        content=content,
        title=title,
        source=f"raw_{stem}",
        source_url="",
        created="2026-01-01",
        updated="2026-01-01",
        tags=tags,
        status="processed",
        related=related or [],
    )
    path = directory / f"{stem}.md"
    path.write_text(frontmatter.dumps(post, sort_keys=False), encoding="utf-8")
    return path


def make_links_json(index_dir: Path, data: dict) -> Path:
    """在 index_dir 下创建 links.json。"""
    path = index_dir / "links.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path
