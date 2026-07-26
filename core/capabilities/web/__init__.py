from __future__ import annotations

import re
from typing import Any, Optional

import httpx

from core.capabilities.base import Capability, Skill
from core.capabilities.registry import register


@register
class WebCapability(Capability):
    id = "web"
    name = "Web"
    version = "1.0.0"
    author = "IdentityOS"
    license = "MIT"
    homepage = "https://github.com/lacebx/IdentityOS"
    description = "Fetch web pages, extract text content, and resolve URLs"
    permissions = ["public"]

    _client: httpx.Client

    def __init__(self, config: Optional[dict] = None) -> None:
        super().__init__(config)
        self._client = httpx.Client(timeout=15, follow_redirects=True)

    def install(self, identity_id: str, storage: Any) -> None:
        storage.save(identity_id, "capability.web", {"installed_at": None})

    def uninstall(self, identity_id: str, storage: Any) -> None:
        storage.delete(identity_id, "capability.web")

    def prompts(self, identity_id: str) -> list[str]:
        return [
            "## Web Skills (MANDATORY — use for URL content)",
            "When the user asks you to fetch a URL or check a web page, you MUST use the skills below.",
            "Do NOT say you cannot browse the web. You CAN. Use the skills.",
        ]

    _SKILLS = [
        Skill(name="web.fetch", description="Fetch a URL and return its content as text", permission="public"),
        Skill(name="web.extract", description="Fetch a URL and extract clean text from HTML", permission="public"),
    ]

    def skills(self) -> list[Skill]:
        return list(self._SKILLS)

    def call(self, skill_name: str, **params: Any) -> Any:
        dispatch = {
            "web.fetch": self._fetch,
            "web.extract": self._extract,
        }
        handler = dispatch.get(skill_name)
        if handler is None:
            raise ValueError(f"Unknown skill: {skill_name}")
        return handler(**params)

    def _fetch(self, url: str = "", **kwargs: Any) -> dict[str, Any]:
        if not url:
            return {"error": "url is required"}
        resp = self._client.get(url)
        resp.raise_for_status()
        return {
            "url": url,
            "status": resp.status_code,
            "content_type": resp.headers.get("content-type", ""),
            "content_length": len(resp.text),
            "text": resp.text[:5000],
        }

    def _extract(self, url: str = "", **kwargs: Any) -> dict[str, Any]:
        if not url:
            return {"error": "url is required"}
        resp = self._client.get(url)
        resp.raise_for_status()
        text = resp.text
        text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        text = text[:5000]
        return {
            "url": url,
            "extracted_text": text,
            "character_count": len(text),
        }
