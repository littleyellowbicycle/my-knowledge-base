"""通道自动注册 — 按优先级排序，generic 必须最后。"""
from __future__ import annotations

from src.gateway.base import Channel
from src.gateway.channels.github import GitHubChannel
from src.gateway.channels.zhihu import ZhihuChannel
from src.gateway.channels.weixin import WeixinChannel
from src.gateway.channels.generic import GenericChannel

# 优先级: github > zhihu > weixin > generic(兜底)
all_channels: list[Channel] = [
    GitHubChannel(),
    ZhihuChannel(),
    WeixinChannel(),
    GenericChannel(),
]
