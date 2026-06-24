"""瘦路由 — 遍历通道列表，第一个 match() 命中的负责处理。

generic 通道永远排最后 (兜底)，其余按注册顺序匹配。
新增平台只需在 channels/__init__.py 注册，不改此文件。
"""
from __future__ import annotations

import logging

from src.gateway.base import Channel

logger = logging.getLogger(__name__)

# 通道注册顺序: 优先级从高到低，generic 必须最后
_channels: list[Channel] = []


def _register(channel: Channel) -> None:
    """注册通道 (按调用顺序排序)。"""
    _channels.append(channel)


def fetch_url(url: str, cookies: dict | None = None) -> str:
    """路由分发: 遍历通道，第一个 match() 命中的负责抓取。

    Args:
        url: 目标链接
        cookies: 可选登录态 dict (优先级高于通道文件读取)
    """
    for ch in _channels:
        if ch.match(url):
            logger.info("路由命中: %s -> %s", url[:80], ch.name)
            return ch.fetch(url, cookies=cookies)
    # 理论上 generic 兜底不会走到这
    raise RuntimeError(f"无通道匹配 URL: {url}")


def fetch_manual(text: str) -> str:
    """手动输入: 原样返回 (归一化在 raw_store 完成)。"""
    return text


def is_expandable(url: str) -> bool:
    """判断 URL 是否为展开型 (如收藏夹)，只做 URL 模式匹配，不触发抓取。"""
    for ch in _channels:
        if ch.match(url):
            # 通道声明支持展开时，再检查 URL 是否为展开型子模式
            if not getattr(ch, "supports_expand", False):
                return False
            # 调用通道的 is_expandable_url 做精细 URL 匹配 (如只匹配 /collection/)
            return getattr(ch, "is_expandable_url", lambda u: False)(url)
    return False


def fetch_items(url: str, cookies: dict | None = None) -> list[dict] | None:
    """展开型通道: 返回文章列表 [{url, title}]，非展开型返回 None。"""
    for ch in _channels:
        if ch.match(url):
            return ch.fetch_items(url, cookies=cookies)
    return None


# ---------- 通道注册 (导入即注册) ----------
from src.gateway.channels import all_channels  # noqa: E402

for _ch in all_channels:
    _register(_ch)
