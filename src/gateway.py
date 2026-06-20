"""输入网关 (模块 A) - 多平台路由抓取。

职责:
    根据 URL 平台路由到不同抓取器，输出干净 Markdown:
      * GitHub  -> gh CLI (拉 README/源码)
      * 微信公众号 -> Jina Reader API (绕过反爬)
      * 其他网页 -> Crawl4AI (HTTP/Playwright 自适应)，失败回退 requests

对外暴露:
    fetch_url(url)       -> str   抓取单个 URL，返回 markdown 文本
    fetch_manual(text)   -> str   手动输入原样返回 (归一化在 raw_store 层完成)

设计原则: 本模块只负责"抓文本"，不做归一化、不落盘。
归一化与落盘由 `raw_store.normalize_and_save()` 完成。
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
from urllib.parse import urlparse

import requests

from src.config import settings

logger = logging.getLogger(__name__)

# Jina Reader: GET https://r.jina.ai/<url> 返回 markdown 正文
JINA_READER_BASE = "https://r.jina.ai/"
_REQUEST_TIMEOUT = 60


# ---------- 路由判定 ----------
def _classify(url: str) -> str:
    """识别 URL 所属平台，决定抓取策略。"""
    host = (urlparse(url).netloc or "").lower()
    if "github.com" in host:
        return "github"
    if "mp.weixin.qq.com" in host:
        return "weixin"
    return "generic"


# ---------- GitHub: gh CLI ----------
def _fetch_github(url: str) -> str:
    """通过 gh CLI 抓取 GitHub 仓库 README 或 Issue/PR 正文。"""
    if not shutil.which("gh"):
        logger.warning("未找到 gh CLI，回退到 GitHub REST API")
        return _fetch_github_api(url)

    # Issue / PR URL 必须优先匹配，避免被仓库正则吞掉
    # https://github.com/{owner}/{repo}/issues/{n}  或 /pull/{n}
    m = re.match(r"https?://github\.com/([^/]+)/([^/]+)/(issues|pull)/(\d+)", url)
    if m:
        owner, repo, kind, num = m.groups()
        kind_api = "issues" if kind == "issues" else "pulls"
        try:
            out = subprocess.run(
                ["gh", "api", f"repos/{owner}/{repo}/{kind_api}/{num}",
                 "--jq", ".title, .body"],
                capture_output=True, text=True, timeout=30, check=True,
            )
            parts = out.stdout.split("\n", 1)
            title = parts[0].strip() or f"{owner}/{repo} #{num}"
            body = parts[1].strip() if len(parts) > 1 else ""
            return f"# {title}\n\nURL: {url}\n\n{body}"
        except Exception as e:  # noqa: BLE001
            logger.warning("gh Issue 抓取失败: %s", e)
            return _fetch_github_api(url)

    # 仓库 URL: https://github.com/{owner}/{repo}  (排除 issues/pull 子路径)
    m = re.match(r"https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?(?:[^/]+)?/?$", url)
    if m and "/issues/" not in url and "/pull/" not in url:
        owner, repo = m.group(1), m.group(2)
        try:
            out = subprocess.run(
                ["gh", "api", f"repos/{owner}/{repo}/readme",
                 "--jq", ".content"],
                capture_output=True, text=True, timeout=30, check=True,
            )
            import base64
            content = base64.b64decode(out.stdout.strip()).decode("utf-8", errors="replace")
            return f"# {owner}/{repo} README\n\n{content}"
        except subprocess.CalledProcessError as e:
            logger.warning("gh README 抓取失败: %s", e.stderr)
        except Exception as e:  # noqa: BLE001
            logger.warning("gh 调用异常: %s", e)

    return _fetch_github_api(url)


def _fetch_github_api(url: str) -> str:
    """无 gh CLI 时的兜底: 直接调用 GitHub REST API。"""
    # 同样: Issue/PR 优先
    m = re.match(r"https?://github\.com/([^/]+)/([^/]+)/(issues|pull)/(\d+)", url)
    if m:
        owner, repo, kind, num = m.groups()
        kind_api = "issues" if kind == "issues" else "pulls"
        api = f"https://api.github.com/repos/{owner}/{repo}/{kind_api}/{num}"
        try:
            r = requests.get(api, timeout=_REQUEST_TIMEOUT,
                             headers={"Accept": "application/vnd.github.v3+json"})
            r.raise_for_status()
            data = r.json()
            title = data.get("title", f"{owner}/{repo} #{num}")
            body = data.get("body") or ""
            return f"# {title}\n\nURL: {url}\n\n{body}"
        except Exception as e:  # noqa: BLE001
            logger.warning("GitHub Issue REST API 失败: %s", e)
            return _fetch_generic(url)

    # 仓库 README (排除 issues/pull)
    m = re.match(r"https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?(?:[^/]+)?/?$", url)
    if m and "/issues/" not in url and "/pull/" not in url:
        owner, repo = m.group(1), m.group(2)
        api = f"https://api.github.com/repos/{owner}/{repo}/readme"
        try:
            import base64
            r = requests.get(api, timeout=_REQUEST_TIMEOUT,
                             headers={"Accept": "application/vnd.github.v3+json"})
            r.raise_for_status()
            content = base64.b64decode(r.json()["content"]).decode("utf-8", errors="replace")
            return f"# {owner}/{repo} README\n\n{content}"
        except Exception as e:  # noqa: BLE001
            logger.warning("GitHub REST API 失败，回退通用抓取: %s", e)
            return _fetch_generic(url)
    return _fetch_generic(url)


# ---------- 微信公众号: Jina Reader ----------
def _fetch_weixin(url: str) -> str:
    """微信公众号 -> Jina Reader API，返回纯净 markdown。"""
    headers = {}
    if settings.JINA_API_KEY:
        headers["Authorization"] = f"Bearer {settings.JINA_API_KEY}"
    try:
        r = requests.get(JINA_READER_BASE + url,
                         timeout=_REQUEST_TIMEOUT, headers=headers)
        r.raise_for_status()
        return r.text
    except Exception as e:  # noqa: BLE001
        logger.warning("Jina Reader 抓取失败: %s", e)
        return _fetch_generic(url)


# ---------- 通用网页: Crawl4AI (优先) -> requests 兜底 ----------
def _fetch_generic(url: str) -> str:
    """通用网页抓取: 优先 Crawl4AI，未安装或失败则用 requests + 简单清理。"""
    try:
        return _fetch_crawl4ai(url)
    except Exception as e:  # noqa: BLE001
        logger.warning("Crawl4AI 抓取失败，回退 requests: %s", e)
        return _fetch_requests(url)


def _fetch_crawl4ai(url: str) -> str:
    """Crawl4AI 异步抓取，用 asyncio.run 包装为同步。"""
    import asyncio

    try:
        from crawl4ai import AsyncWebCrawler
    except ImportError as e:
        raise RuntimeError("未安装 crawl4ai") from e

    async def _run() -> str:
        async with AsyncWebCrawler(verbose=False) as crawler:
            result = await crawler.arun(url=url)
            return result.markdown or result.cleaned_html or ""

    return asyncio.run(_run())


def _fetch_requests(url: str) -> str:
    """最简兜底: requests + HTML 标签清理。"""
    try:
        r = requests.get(url, timeout=_REQUEST_TIMEOUT,
                         headers={"User-Agent": "Mozilla/5.0 (compatible; MyKB/0.1)"})
        r.raise_for_status()
        html = r.text
    except Exception as e:  # noqa: BLE001
        logger.error("requests 兜底抓取失败: %s", e)
        return f"<!-- 抓取失败: {e} -->\nURL: {url}"

    return _html_to_markdown(html, url)


def _html_to_markdown(html: str, url: str) -> str:
    """极简 HTML -> Markdown 转换 (兜底用，不做精细处理)。"""
    # 去 script/style
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.S | re.I)
    # 标题
    html = re.sub(r"<h(\d)[^>]*>(.*?)</h\1>",
                  lambda m: f"\n{'#' * int(m.group(1))} {m.group(2)}\n",
                  html, flags=re.S | re.I)
    # 段落/换行
    html = re.sub(r"<br\s*/?>", "\n", html, flags=re.I)
    html = re.sub(r"<p[^>]*>", "\n\n", html, flags=re.I)
    html = re.sub(r"</p>", "", html, flags=re.I)
    # 链接
    html = re.sub(r"<a[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>",
                  r"[\2](\1)", html, flags=re.S | re.I)
    # 去剩余标签
    text = re.sub(r"<[^>]+>", "", html)
    # HTML 实体
    import html as _html
    text = _html.unescape(text)
    # 压缩多余空行
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return f"URL: {url}\n\n{text}"


# ---------- 对外统一入口 ----------
def fetch_url(url: str) -> str:
    """路由分发: 根据 URL 平台调用对应抓取器，返回 markdown 文本。"""
    kind = _classify(url)
    logger.info("抓取路由: %s -> %s", url, kind)
    if kind == "github":
        return _fetch_github(url)
    if kind == "weixin":
        return _fetch_weixin(url)
    return _fetch_generic(url)


def fetch_manual(text: str) -> str:
    """手动输入: 原样返回 (归一化在 raw_store 完成)。"""
    return text
