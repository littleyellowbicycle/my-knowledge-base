"""GitHub 通道 — gh CLI + REST API。

支持 URL 模式:
    - https://github.com/{owner}/{repo}         → README
    - https://github.com/{owner}/{repo}/issues/{n}  → Issue 正文
    - https://github.com/{owner}/{repo}/pull/{n}    → PR 正文
"""
from __future__ import annotations

import base64
import logging
import re
import shutil
import subprocess
from urllib.parse import urlparse

import requests

from src.gateway.channels._shared import _REQUEST_TIMEOUT, html_to_markdown

logger = logging.getLogger(__name__)


class GitHubChannel:
    name = "github"
    supports_expand = False  # GitHub 不支持展开

    def match(self, url: str) -> bool:
        host = (urlparse(url).netloc or "").lower()
        return "github.com" in host

    def fetch(self, url: str, cookies: dict | None = None) -> str:
        if not shutil.which("gh"):
            logger.warning("未找到 gh CLI，回退到 GitHub REST API")
            return self._fetch_api(url)
        return self._fetch_gh_cli(url)

    def fetch_items(self, url: str, cookies: dict | None = None) -> list[dict] | None:
        return None  # GitHub 不支持展开

    # ---------- gh CLI ----------
    def _fetch_gh_cli(self, url: str) -> str:
        m = re.match(r"https?://github\.com/([^/]+)/([^/]+)/(issues|pull)/(\d+)", url)
        if m:
            owner, repo, kind, num = m.groups()
            kind_api = "issues" if kind == "issues" else "pulls"
            try:
                out = subprocess.run(
                    ["gh", "api", f"repos/{owner}/{repo}/{kind_api}/{num}", "--jq", ".title, .body"],
                    capture_output=True, text=True, timeout=30, check=True,
                )
                parts = out.stdout.split("\n", 1)
                title = parts[0].strip() or f"{owner}/{repo} #{num}"
                body = parts[1].strip() if len(parts) > 1 else ""
                return f"# {title}\n\nURL: {url}\n\n{body}"
            except Exception as e:  # noqa: BLE001
                logger.warning("gh Issue 抓取失败: %s", e)
                return self._fetch_api(url)

        m = re.match(r"https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?(?:[^/]+)?/?$", url)
        if m and "/issues/" not in url and "/pull/" not in url:
            owner, repo = m.group(1), m.group(2)
            try:
                out = subprocess.run(
                    ["gh", "api", f"repos/{owner}/{repo}/readme", "--jq", ".content"],
                    capture_output=True, text=True, timeout=30, check=True,
                )
                content = base64.b64decode(out.stdout.strip()).decode("utf-8", errors="replace")
                return f"# {owner}/{repo} README\n\n{content}"
            except subprocess.CalledProcessError as e:
                logger.warning("gh README 抓取失败: %s", e.stderr)
            except Exception as e:  # noqa: BLE001
                logger.warning("gh 调用异常: %s", e)

        return self._fetch_api(url)

    # ---------- REST API 兜底 ----------
    def _fetch_api(self, url: str) -> str:
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
                from src.gateway.channels.generic import GenericChannel
                return GenericChannel().fetch(url)

        m = re.match(r"https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?(?:[^/]+)?/?$", url)
        if m and "/issues/" not in url and "/pull/" not in url:
            owner, repo = m.group(1), m.group(2)
            api = f"https://api.github.com/repos/{owner}/{repo}/readme"
            try:
                r = requests.get(api, timeout=_REQUEST_TIMEOUT,
                                 headers={"Accept": "application/vnd.github.v3+json"})
                r.raise_for_status()
                content = base64.b64decode(r.json()["content"]).decode("utf-8", errors="replace")
                return f"# {owner}/{repo} README\n\n{content}"
            except Exception as e:  # noqa: BLE001
                logger.warning("GitHub REST API 失败，回退通用抓取: %s", e)
                from src.gateway.channels.generic import GenericChannel
                return GenericChannel().fetch(url)

        from src.gateway.channels.generic import GenericChannel
        return GenericChannel().fetch(url)
