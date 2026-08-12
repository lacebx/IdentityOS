from __future__ import annotations

from typing import Any, Optional

import httpx
import os

from core.capabilities.base import Capability, Skill
from core.capabilities.registry import register
from core.capabilities.result import CapabilityResult

GITHUB_API = "https://api.github.com"


@register
class GithubCapability(Capability):
    id = "github"
    name = "GitHub Integration"
    version = "1.0.0"
    author = "IdentityOS"
    license = "MIT"
    homepage = "https://github.com/lacebx/IdentityOS"
    description = "Search repositories, review code, find beginner issues, summarize releases"
    permissions = ["public"]

    _client: httpx.Client

    def __init__(self, config: Optional[dict] = None) -> None:
        super().__init__(config)
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "IdentityOS/1.0",
        }
        token = self._config.get("token", "") or os.environ.get("GITHUB_TOKEN", "")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._client = httpx.Client(base_url=GITHUB_API, headers=headers, timeout=15)

    # ── Lifecycle ──────────────────────────────────────────────────────

    def install(self, identity_id: str, storage: Any) -> None:
        storage.save(identity_id, "capability.github", {"installed_at": None})

    def uninstall(self, identity_id: str, storage: Any) -> None:
        storage.delete(identity_id, "capability.github")

    # ── Prompts ────────────────────────────────────────────────────────

    def prompts(self, identity_id: str) -> list[str]:
        return [
            "## GitHub Skills (MANDATORY — use for GitHub operations)",
            "When the user asks about GitHub repositories, PRs, issues, or commits, you MUST use the skills below.",
            "Do NOT say you cannot access GitHub. You CAN. Use the skills.",
        ]

    # ── Skills ─────────────────────────────────────────────────────────

    _SKILLS = [
        Skill(
            name="github.search_repositories",
            description="Search GitHub repositories by keyword",
            permission="public",
        ),
        Skill(
            name="github.get_repository",
            description="Get details about a specific repository",
            permission="public",
        ),
        Skill(
            name="github.review_pull_request",
            description="Review a pull request — fetches details, diff summary, and status",
            permission="public",
        ),
        Skill(
            name="github.find_beginner_issue",
            description="Find beginner-friendly issues (tagged 'good first issue')",
            permission="public",
        ),
        Skill(
            name="github.summarize_release",
            description="Summarize recent changes since the latest release tag",
            permission="public",
        ),
        Skill(
            name="github.list_commits",
            description="List recent commits for a repository",
            permission="public",
        ),
        Skill(
            name="github.list_branches",
            description="List all branches in a repository",
            permission="public",
        ),
    ]

    def skills(self) -> list[Skill]:
        return list(self._SKILLS)

    # ── Execution ──────────────────────────────────────────────────────

    def call(self, skill_name: str, **params: Any) -> CapabilityResult:
        import time as _time
        _t0 = _time.monotonic()
        try:
            dispatch = {
                "github.search_repositories": self._search_repos,
                "github.get_repository": self._get_repo,
                "github.review_pull_request": self._review_pr,
                "github.find_beginner_issue": self._find_beginner_issue,
                "github.summarize_release": self._summarize_release,
                "github.list_commits": self._list_commits,
                "github.list_branches": self._list_branches,
            }
            handler = dispatch.get(skill_name)
            if handler is None:
                return CapabilityResult.fail("github", skill_name, "unknown_skill", f"Unknown skill: {skill_name}")
            data = handler(**params)
            return CapabilityResult.from_data("github", skill_name, data, source="GitHub REST API", duration_ms=(_time.monotonic() - _t0) * 1000)
        except Exception as e:
            return CapabilityResult.fail("github", skill_name, type(e).__name__, str(e), source="GitHub REST API", duration_ms=(_time.monotonic() - _t0) * 1000)

    # ── Core API methods ───────────────────────────────────────────────

    def _search_repos(self, query: str = "", **kwargs: Any) -> list[dict[str, Any]]:
        resp = self._client.get("/search/repositories", params={"q": query, "per_page": 5})
        resp.raise_for_status()
        data = resp.json()
        return [
            {
                "name": item["full_name"],
                "description": item.get("description", ""),
                "stars": item.get("stargazers_count", 0),
                "url": item["html_url"],
            }
            for item in data.get("items", [])
        ]

    def _get_repo(self, owner: str = "", repo: str = "", **kwargs: Any) -> dict[str, Any]:
        resp = self._client.get(f"/repos/{owner}/{repo}")
        resp.raise_for_status()
        d = resp.json()
        return {
            "name": d["full_name"],
            "description": d.get("description", ""),
            "stars": d.get("stargazers_count", 0),
            "forks": d.get("forks_count", 0),
            "language": d.get("language"),
            "url": d["html_url"],
        }

    def _review_pr(self, owner: str = "", repo: str = "", number: int = 0, **kwargs: Any) -> dict[str, Any]:
        resp = self._client.get(f"/repos/{owner}/{repo}/pulls/{number}")
        resp.raise_for_status()
        d = resp.json()
        files_resp = self._client.get(f"/repos/{owner}/{repo}/pulls/{number}/files", params={"per_page": 10})
        files = []
        if files_resp.status_code == 200:
            files = [
                {"filename": f["filename"], "additions": f["additions"], "deletions": f["deletions"], "status": f["status"]}
                for f in files_resp.json()
            ]
        total_additions = sum(f.get("additions", 0) for f in files)
        total_deletions = sum(f.get("deletions", 0) for f in files)
        return {
            "number": d["number"],
            "title": d["title"],
            "state": d["state"],
            "author": d["user"]["login"],
            "body": (d.get("body") or "")[:500],
            "files_changed": len(files),
            "total_additions": total_additions,
            "total_deletions": total_deletions,
            "url": d["html_url"],
        }

    def _find_beginner_issue(self, owner: str = "", repo: str = "", **kwargs: Any) -> list[dict[str, Any]]:
        resp = self._client.get(
            f"/repos/{owner}/{repo}/issues",
            params={"labels": "good first issue", "state": "open", "per_page": 5},
        )
        resp.raise_for_status()
        return [
            {
                "number": i["number"],
                "title": i["title"],
                "body": (i.get("body") or "")[:300],
                "url": i["html_url"],
            }
            for i in resp.json()
        ]

    def _summarize_release(self, owner: str = "", repo: str = "", **kwargs: Any) -> dict[str, Any]:
        tags_resp = self._client.get(f"/repos/{owner}/{repo}/tags", params={"per_page": 5})
        tags = tags_resp.json() if tags_resp.status_code == 200 else []
        if not tags:
            commits_resp = self._client.get(f"/repos/{owner}/{repo}/commits", params={"per_page": 5})
            commits_resp.raise_for_status()
            recent = [
                {"sha": c["sha"][:7], "message": c["commit"]["message"].split("\n")[0], "author": c["commit"]["author"]["name"]}
                for c in commits_resp.json()
            ]
            return {"tag": None, "commits_since_last_tag": recent, "total": len(recent)}
        latest_tag = tags[0]["name"]
        compare_resp = self._client.get(
            f"/repos/{owner}/{repo}/compare/{latest_tag}...HEAD"
        )
        commits = []
        if compare_resp.status_code == 200:
            data = compare_resp.json()
            commits = [
                {"sha": c["sha"][:7], "message": c["commit"]["message"].split("\n")[0], "author": c["commit"]["author"]["name"]}
                for c in data.get("commits", [])
            ]
        return {
            "tag": latest_tag,
            "commits_since_last_tag": commits,
            "total": len(commits),
        }

    def _list_commits(self, owner: str = "", repo: str = "", **kwargs: Any) -> list[dict[str, Any]]:
        resp = self._client.get(f"/repos/{owner}/{repo}/commits", params={"per_page": 5})
        resp.raise_for_status()
        return [
            {
                "sha": c["sha"][:7],
                "message": c["commit"]["message"].split("\n")[0],
                "author": c["commit"]["author"]["name"],
                "date": c["commit"]["author"]["date"],
            }
            for c in resp.json()
        ]

    def _list_branches(self, owner: str = "", repo: str = "", **kwargs: Any) -> list[dict[str, Any]]:
        resp = self._client.get(f"/repos/{owner}/{repo}/branches", params={"per_page": 10})
        resp.raise_for_status()
        return [
            {"name": b["name"], "sha": b["commit"]["sha"][:7]}
            for b in resp.json()
        ]
