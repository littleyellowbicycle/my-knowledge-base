"""Channel 协议定义 — 每个平台通道需实现此接口。

通道是网关的可插拔单元，负责特定平台的 URL 匹配与内容抓取。
新增平台只需在 channels/ 下加一个文件实现此协议，不改已有代码 (开闭原则)。
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Channel(Protocol):
    """通道协议: 每个平台通道需实现。"""

    name: str
    """通道唯一标识 (如 "zhihu" / "weixin" / "github")。"""

    def match(self, url: str) -> bool:
        """判断 URL 是否归本通道处理。"""
        ...

    def fetch(self, url: str, cookies: dict | None = None) -> str:
        """抓取单个 URL，返回 markdown 文本。

        Args:
            url: 目标链接
            cookies: 可选登录态 (优先级高于文件读取)
        """
        ...

    def fetch_items(self, url: str, cookies: dict | None = None) -> list[dict] | None:
        """展开型通道: 返回文章列表 [{url, title}]。

        用于"一个 URL 包含多篇内容"的场景 (如知乎收藏夹)。
        返回 None 表示该通道不支持展开 (单篇型通道默认行为)。
        """
        ...
