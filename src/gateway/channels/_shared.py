"""通道共享工具: cookie 加载、HTML→Markdown 转换、通用 Crawl4AI 调用。"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from src.config import settings

logger = logging.getLogger(__name__)

_REQUEST_TIMEOUT = 60


def load_cookies(channel_name: str | None = None, explicit: dict | None = None) -> dict:
    """多级 cookie 优先级加载。

    优先级 (从高到低):
        1. 显式参数 explicit (调用方传入)
        2. 通道专属文件 cookies_{channel}.json (如 cookies_zhihu.json)
        3. 全局文件 cookies.json
        4. 无 cookie (返回空 dict)
    """
    if explicit:
        return explicit

    root = Path(settings.PROJECT_ROOT)

    if channel_name:
        ch_path = root / f"cookies_{channel_name}.json"
        cookies = _load_cookie_file(ch_path)
        if cookies:
            return cookies

    global_path = root / "cookies.json"
    return _load_cookie_file(global_path)


def _load_cookie_file(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        cookies_list = json.loads(path.read_text(encoding="utf-8"))
        return {c["name"]: c["value"] for c in cookies_list}
    except Exception as e:  # noqa: BLE001
        logger.warning("cookie 文件解析失败 %s: %s", path.name, e)
        return {}


def html_to_markdown(html: str, url: str) -> str:
    """极简 HTML → Markdown 转换 (兜底用，不做精细处理)。"""
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.S | re.I)
    html = re.sub(
        r"<h(\d)[^>]*>(.*?)</\1>",
        lambda m: f"\n{'#' * int(m.group(1))} {m.group(2)}\n",
        html,
        flags=re.S | re.I,
    )
    html = re.sub(r"<br\s*/?>", "\n", html, flags=re.I)
    html = re.sub(r"<p[^>]*>", "\n\n", html, flags=re.I)
    html = re.sub(r"</p>", "", html, flags=re.I)
    html = re.sub(
        r"<a[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>",
        r"[\2](\1)",
        html,
        flags=re.S | re.I,
    )
    text = re.sub(r"<[^>]+>", "", html)
    import html as _html

    text = _html.unescape(text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return f"URL: {url}\n\n{text}"


def crawl4ai_fetch(url: str, cookies: dict | None = None) -> str:
    """Crawl4AI 异步抓取，支持 cookie 注入到浏览器会话。

    Args:
        url: 目标链接
        cookies: 可选登录态 dict
    """
    import asyncio

    try:
        from crawl4ai import AsyncWebCrawler
    except ImportError as e:
        raise RuntimeError("未安装 crawl4ai") from e

    async def _run() -> str:
        async with AsyncWebCrawler(verbose=False) as crawler:
            kwargs = {"url": url}
            if cookies:
                kwargs["headers"] = {"Cookie": "; ".join(f"{k}={v}" for k, v in cookies.items())}
            result = await crawler.arun(**kwargs)
            return result.markdown or result.cleaned_html or ""

    return asyncio.run(_run())
