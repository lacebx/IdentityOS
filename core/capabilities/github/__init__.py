from __future__ import annotations

from typing import Any, Optional

import httpx

from core.capabilities.base import Capability, Skill
from core.capabilities.registry import register

GITHUB_API = "https://api.github.com"


@register
class GithubCapability(Capability):
    id = "github"
    name = "GitHub Integration"
    version = "1.0.0"
    author = "IdentityOS"
    license = "MIT"
    homepage = "https://github.com/lacebx/IdentityOS"
    description = "Search repositories, read code, list commits and branches, inspect pull requests"
    permissions = ["public"]

    _client: httpx.Client

    def __init__(self, config: Optional[dict] = None) -> None:
        super().__init__(config)
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "IdentityOS/1.0",
        }
        token = self._config.get("token", "")
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
            "## Available GitHub Skills",
            "You can search for repositories, read repository details, "
            "list commits and branches, and inspect pull requests.",
            'Use the `call` function to invoke a skill, e.g. `call("github.search_repositories", query="my project")`.',
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
            name="github.list_commits",
            description="List recent commits for a repository",
            permission="public",
        ),
        Skill(
            name="github.list_branches",
            description="List all branches in a repository",
            permission="public",
        ),
        Skill(
            name="github.read_pull_request",
            description="Get details of a pull request",
            permission="public",
        ),
    ]

    def skills(self) -> list[Skill]:
        return list(self._SKILLS)

    # ── Execution ──────────────────────────────────────────────────────

    def call(self, skill_name: str, **params: Any) -> Any:
        dispatch = {
            "github.search_repositories": self._search_repos,
            "github.get_repository": self._get_repo,
            "github.list_commits": self._list_commits,
            "github.list_branches": self._list_branches,
            "github.read_pull_request": self._read_pr,
        }
        handler = dispatch.get(skill_name)
        if handler is None:
            raise ValueError(f"Unknown skill: {skill_name}")
        return handler(**params)

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

    def _read_pr(self, owner: str = "", repo: str = "", number: int = 0, **kwargs: Any) -> dict[str, Any]:
        resp = self._client.get(f"/repos/{owner}/{repo}/pulls/{number}")
        resp.raise_for_status()
        d = resp.json()
        return {
            "number": d["number"],
            "title": d["title"],
            "state": d["state"],
            "author": d["user"]["login"],
            "body": d.get("body", "")[:500],
            "url": d["html_url"],
        }
