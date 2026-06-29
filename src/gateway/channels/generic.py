"""通用通道 — Crawl4AI 优先，requests 兜底。永远最后匹配 (兜底)。"""
from __future__ import annotations

import logging

import requests

from src.gateway.channels._shared import (
    _REQUEST_TIMEOUT,
    crawl4ai_fetch,
    detect_raw_type,
    html_to_markdown,
    mark_raw_type,
)

logger = logging.getLogger(__name__)


class GenericChannel:
    name = "generic"
    supports_expand = False  # 通用不支持展开

    def match(self, url: str) -> bool:
        return True  # 兜底: 永远匹配

    def fetch(self, url: str, cookies: dict | None = None) -> str:
        try:
            text = crawl4ai_fetch(url, cookies=cookies)
        except Exception as e:  # noqa: BLE001
            logger.warning("Crawl4AI 抓取失败，回退 requests: %s", e)
            text = self._fetch_requests(url, cookies)
        return mark_raw_type(text, detect_raw_type(text))

    def fetch_items(self, url: str, cookies: dict | None = None) -> list[dict] | None:
        return None  # 通用不支持展开

    @staticmethod
    def _fetch_requests(url: str, cookies: dict | None = None) -> str:
        try:
            r = requests.get(
                url,
                timeout=_REQUEST_TIMEOUT,
                headers={"User-Agent": "Mozilla/5.0 (compatible; MyKB/0.1)"},
                cookies=cookies or {},
            )
            r.raise_for_status()
            return html_to_markdown(r.text, url)
        except Exception as e:  # noqa: BLE001
            logger.error("requests 兜底抓取失败: %s", e)
            return f"<!-- 抓取失败: {e} -->\nURL: {url}"
