"""从 GitHub API 拉一份仓库快照。

单独抽出来，是为了让 checks 保持纯函数——测试里不联网也能跑。
"""

from __future__ import annotations

import base64
import os
from typing import Any

import requests

API = "https://api.github.com"


class GitHubError(RuntimeError):
    pass


class GitHubClient:
    def __init__(self, token: str | None = None, session: requests.Session | None = None):
        self.token = token or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        self.session = session or requests.Session()

    def _headers(self) -> dict[str, str]:
        h = {"User-Agent": "repo-doctor/0.1", "Accept": "application/vnd.github+json"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        resp = self.session.get(f"{API}{path}", params=params, headers=self._headers(), timeout=25)
        if resp.status_code == 404:
            raise GitHubError(f"找不到：{path}")
        if resp.status_code == 403:
            raise GitHubError("触发 GitHub 限流，配置 GITHUB_TOKEN 可提高到 5000 次/小时")
        if resp.status_code != 200:
            raise GitHubError(f"GitHub 返回 {resp.status_code}：{resp.text[:160]}")
        return resp.json()

    def snapshot(self, full_name: str) -> dict[str, Any]:
        repo = self._get(f"/repos/{full_name}")
        branch = repo.get("default_branch") or "main"

        files: list[str] = []
        try:
            tree = self._get(f"/repos/{full_name}/git/trees/{branch}", {"recursive": "1"})
            files = [t["path"] for t in tree.get("tree", []) if t.get("type") == "blob"]
        except GitHubError:
            files = []

        readme = None
        try:
            data = self._get(f"/repos/{full_name}/readme")
            readme = base64.b64decode(data.get("content", "")).decode("utf-8", errors="replace")
        except GitHubError:
            readme = None

        try:
            releases = len(self._get(f"/repos/{full_name}/releases", {"per_page": 5}))
        except GitHubError:
            releases = 0

        lic = repo.get("license") or {}
        return {
            "full_name": repo.get("full_name", full_name),
            "description": repo.get("description"),
            "topics": repo.get("topics") or [],
            "license": lic.get("spdx_id") if lic.get("spdx_id") not in (None, "NOASSERTION") else None,
            "pushed_at": repo.get("pushed_at"),
            "created_at": repo.get("created_at"),
            "stars": repo.get("stargazers_count", 0),
            "forks": repo.get("forks_count", 0),
            "archived": bool(repo.get("archived")),
            "language": repo.get("language"),
            "html_url": repo.get("html_url"),
            "files": files,
            "readme": readme,
            "releases": releases,
        }
