"""输入网关 (模块 A) — 通道分层架构 V2.2。

对外暴露:
    fetch_url(url, cookies=None)                  -> str           抓取单个 URL
    fetch_manual(text)                            -> str           手动输入原样返回
    is_expandable(url)                            -> bool          是否展开型 URL
    fetch_items(url, cookies=None)                -> list[dict]|None  展开型文章列表

通道架构:
    src/gateway/
    ├── base.py        # Channel 协议
    ├── router.py      # 瘦路由
    └── channels/
        ├── github.py  # gh CLI + REST API
        ├── zhihu.py   # 收藏夹 items API + Crawl4AI 单篇
        ├── weixin.py  # Jina Reader
        └── generic.py # Crawl4AI 兜底
"""
from __future__ import annotations

from src.gateway.router import (
    fetch_url,
    fetch_manual,
    is_expandable,
    fetch_items,
)

__all__ = ["fetch_url", "fetch_manual", "is_expandable", "fetch_items"]
