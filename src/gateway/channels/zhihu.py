"""知乎通道 — 收藏夹 items API + Crawl4AI 单篇渲染。

支持 URL 模式:
    - https://www.zhihu.com/collection/{id}          → 收藏夹 (展开型)
    - https://www.zhihu.com/question/{qid}/answer/{aid}  → 单回答
    - https://zhuanlan.zhihu.com/p/{id}              → 专栏文章

抓取策略:
    列表: requests + items API (JSON, 分页) — 需 cookie
    正文: Crawl4AI (Playwright + cookie 注入) → requests + bs4 → answers API 兜底
"""
from __future__ import annotations

import logging
import re
import time
from urllib.parse import urlparse

import requests

from src.gateway.channels._shared import (
    _REQUEST_TIMEOUT,
    crawl4ai_fetch,
    detect_raw_type,
    html_to_markdown,
    load_cookies,
    mark_raw_type,
)

logger = logging.getLogger(__name__)

_ZHIHU_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
    "Connection": "keep-alive",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": "https://www.zhihu.com/",
}

_ZHIHU_API_HEADERS = {
    "User-Agent": _ZHIHU_HEADERS["User-Agent"],
    "Accept": "*/*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "https://www.zhihu.com/",
    "x-requested-with": "fetch",
}


class ZhihuChannel:
    name = "zhihu"
    supports_expand = True  # 支持展开型 URL (收藏夹)

    def match(self, url: str) -> bool:
        host = (urlparse(url).netloc or "").lower()
        return "zhihu.com" in host

    @staticmethod
    def is_expandable_url(url: str) -> bool:
        """只有收藏夹 URL 才支持展开。"""
        return bool(re.search(r"zhihu\.com/collection/\d+", url))

    def fetch(self, url: str, cookies: dict | None = None) -> str:
        ck = load_cookies("zhihu", cookies)
        if "/collection/" in url:
            return mark_raw_type(self._fetch_collection_index(url, ck), "index")
        if "/answer/" in url:
            text = self._fetch_answer(url, ck)
        elif "zhuanlan" in url or "/p/" in url:
            text = self._fetch_article(url, ck)
        else:
            from src.gateway.channels.generic import GenericChannel
            text = GenericChannel().fetch(url, cookies=ck)
        return mark_raw_type(text, detect_raw_type(text))

    def fetch_items(self, url: str, cookies: dict | None = None) -> list[dict] | None:
        if not re.search(r"zhihu\.com/collection/\d+", url):
            return None
        ck = load_cookies("zhihu", cookies)
        return self._fetch_collection_items(url, ck)

    # ---------- 收藏夹列表 ----------
    @staticmethod
    def _collection_id(url: str) -> str | None:
        m = re.search(r"zhihu\.com/collection/(\d+)", url)
        return m.group(1) if m else None

    def _fetch_collection_items(self, url: str, cookies: dict) -> list[dict]:
        cid = self._collection_id(url)
        if not cid:
            raise ValueError(f"无法从 URL 提取收藏夹 ID: {url}")

        items: list[dict] = []
        offset, limit = 0, 20

        while True:
            api_url = (
                f"https://www.zhihu.com/api/v4/collections/{cid}/items"
                f"?offset={offset}&limit={limit}"
            )
            logger.info("收藏夹 API: offset=%d limit=%d", offset, limit)
            r = requests.get(api_url, headers=_ZHIHU_HEADERS,
                             cookies=cookies, timeout=_REQUEST_TIMEOUT)
            if r.status_code == 401:
                raise RuntimeError(
                    "知乎 items API 需要登录态 (401)。"
                    "请在项目根目录放置 cookies.json 或 cookies_zhihu.json (格式 [{name,value}])"
                )
            r.raise_for_status()
            data = r.json()
            for el in data.get("data", []):
                content = el.get("content", {})
                item_url = content.get("url", "")
                if not item_url:
                    continue
                if content.get("type") == "answer":
                    title = content.get("question", {}).get("title", "")
                else:
                    title = content.get("title", "")
                items.append({"url": item_url, "title": title})

            paging = data.get("paging", {})
            if paging.get("is_end", True) or not data.get("data"):
                break
            offset += limit
            time.sleep(1)

        logger.info("收藏夹 %s 共获取 %d 篇文章", cid, len(items))
        return items

    def _fetch_collection_index(self, url: str, cookies: dict) -> str:
        items = self._fetch_collection_items(url, cookies)
        lines = [f"# 知乎收藏夹\n\nURL: {url}\n\n共 {len(items)} 篇文章\n"]
        for i, item in enumerate(items, 1):
            lines.append(f"{i}. [{item['title']}]({item['url']})")
        return "\n".join(lines)

    # ---------- 单篇正文 ----------
    def _fetch_answer(self, url: str, cookies: dict) -> str:
        # 策略1: Crawl4AI (Playwright + cookie 注入, 解决 JS 渲染)
        try:
            md = crawl4ai_fetch(url, cookies=cookies)
            if md and len(md) > 200:
                return f"URL: {url}\n\n{md}"
        except Exception as e:  # noqa: BLE001
            logger.warning("Crawl4AI 抓取回答失败，回退 requests: %s", e)

        # 策略2: requests + bs4
        r = requests.get(url, headers=_ZHIHU_HEADERS, cookies=cookies, timeout=_REQUEST_TIMEOUT)

        # 策略3: 403 → answers API 兜底
        if r.status_code == 403:
            m = re.search(r"/answer/(\d+)", url)
            if m:
                aid = m.group(1)
                api_url = f"https://www.zhihu.com/api/v4/answers/{aid}?include=content"
                logger.info("回答 403 → API 兜底: %s", api_url)
                r2 = requests.get(api_url, headers=_ZHIHU_API_HEADERS,
                                  cookies=cookies, timeout=_REQUEST_TIMEOUT)
                if r2.status_code == 200:
                    content_html = r2.json().get("content", "")
                    if content_html:
                        return f"URL: {url}\n\n{html_to_markdown(content_html, url)}"
                logger.warning("API 兜底也失败: %d", r2.status_code)

        if r.status_code in (401, 403):
            return f"URL: {url}\n\n<!-- 知乎需要登录态 (HTTP {r.status_code})。请放置 cookies.json -->"
        r.raise_for_status()
        return self._parse_html(r.text, url, kind="answer")

    def _fetch_article(self, url: str, cookies: dict) -> str:
        # 策略1: Crawl4AI
        try:
            md = crawl4ai_fetch(url, cookies=cookies)
            if md and len(md) > 200:
                return f"URL: {url}\n\n{md}"
        except Exception as e:  # noqa: BLE001
            logger.warning("Crawl4AI 抓取专栏失败，回退 requests: %s", e)

        # 策略2: requests + bs4
        r = requests.get(url, headers=_ZHIHU_HEADERS, cookies=cookies, timeout=_REQUEST_TIMEOUT)
        if r.status_code in (401, 403):
            return f"URL: {url}\n\n<!-- 知乎需要登录态 (HTTP {r.status_code})。请放置 cookies.json -->"
        r.raise_for_status()
        return self._parse_html(r.text, url, kind="article")

    # ---------- HTML 解析 ----------
    @staticmethod
    def _parse_html(html: str, url: str, kind: str) -> str:
        try:
            from bs4 import BeautifulSoup
            from markdownify import markdownify as md_convert
        except ImportError:
            logger.warning("bs4/markdownify 未安装，回退通用 HTML 清理")
            return html_to_markdown(html, url)

        soup = BeautifulSoup(html, "lxml")

        if kind == "answer":
            selectors = [
                "div.RichContent-inner",
                "div.QuestionAnswer-content .RichContent-inner",
                "div.RichText",
            ]
        else:
            selectors = [
                "div.Post-RichText",
                "div.RichContent-inner",
                "div.ztext",
                "div.Article-RichText",
                "div.RichText",
            ]

        content_el = None
        for sel in selectors:
            content_el = soup.select_one(sel)
            if content_el:
                break

        if not content_el:
            logger.warning("知乎页面未找到正文容器，回退通用清理: %s", url)
            return html_to_markdown(html, url)

        for el in content_el.find_all("style"):
            el.extract()
        for el in content_el.select('img[src*="data:image/svg+xml"]'):
            el.extract()
        for el in content_el.find_all("a"):
            cls = el.get("class")
            if isinstance(cls, list) and "LinkCard" in cls:
                el.string = el.get("data-text") or el.get("href") or ""

        body_md = md_convert(str(content_el), heading_style="ATX")
        return f"URL: {url}\n\n{body_md}"
