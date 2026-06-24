"""微信通道 — Jina Reader API (绕过公众号反爬)。

支持 URL 模式:
    - https://mp.weixin.qq.com/s/...  → 公众号文章
"""
from __future__ import annotations

import logging
from urllib.parse import urlparse

import requests

from src.config import settings
from src.gateway.channels._shared import _REQUEST_TIMEOUT

logger = logging.getLogger(__name__)

JINA_READER_BASE = "https://r.jina.ai/"


class WeixinChannel:
    name = "weixin"
    supports_expand = False  # 微信不支持展开

    def match(self, url: str) -> bool:
        host = (urlparse(url).netloc or "").lower()
        return "mp.weixin.qq.com" in host

    def fetch(self, url: str, cookies: dict | None = None) -> str:
        headers = {}
        if settings.JINA_API_KEY:
            headers["Authorization"] = f"Bearer {settings.JINA_API_KEY}"
        try:
            r = requests.get(JINA_READER_BASE + url, timeout=_REQUEST_TIMEOUT, headers=headers)
            r.raise_for_status()
            return r.text
        except Exception as e:  # noqa: BLE001
            logger.warning("Jina Reader 抓取失败: %s", e)
            from src.gateway.channels.generic import GenericChannel
            return GenericChannel().fetch(url, cookies=cookies)

    def fetch_items(self, url: str, cookies: dict | None = None) -> list[dict] | None:
        return None  # 微信不支持展开
