from __future__ import annotations

import re
from typing import Any, Optional
from urllib.parse import quote_plus

import httpx

from core.capabilities.base import Capability, Skill
from core.capabilities.registry import register
from core.capabilities.result import CapabilityResult


@register
class WebCapability(Capability):
    id = "web"
    name = "Web"
    version = "1.1.0"
    author = "IdentityOS"
    license = "MIT"
    homepage = "https://github.com/lacebx/IdentityOS"
    description = "Fetch URLs, extract text, and search the web from a natural-language query"
    permissions = ["public"]

    _client: httpx.Client

    def __init__(self, config: Optional[dict] = None) -> None:
        super().__init__(config)
        self._client = httpx.Client(
            timeout=20,
            follow_redirects=True,
            headers={"User-Agent": "IdentityOS-WebCapability/1.1"},
        )

    def install(self, identity_id: str, storage: Any) -> None:
        storage.save(identity_id, "capability.web", {"installed_at": None})

    def uninstall(self, identity_id: str, storage: Any) -> None:
        storage.delete(identity_id, "capability.web")

    def prompts(self, identity_id: str) -> list[str]:
        return [
            "## Web Skills (MANDATORY — use for URL content AND query search)",
            "When the user asks you to fetch a URL or check a web page, use web.fetch / web.extract.",
            "When the user asks you to search / browse / look someone or something up WITHOUT a URL, "
            "you MUST use web.search(query=...). Do NOT say you cannot browse or need a link first.",
            "Do NOT invent search results. Only report what web.search / web.fetch returned.",
        ]

    _SKILLS = [
        Skill(name="web.fetch", description="Fetch a URL and return its content as text", permission="public"),
        Skill(name="web.extract", description="Fetch a URL and extract clean text from HTML", permission="public"),
        Skill(name="web.search", description="Search the web from a natural-language query and return top result snippets", permission="public"),
    ]

    def skills(self) -> list[Skill]:
        return list(self._SKILLS)

    def call(self, skill_name: str, **params: Any) -> CapabilityResult:
        import time as _time
        _t0 = _time.monotonic()
        try:
            dispatch = {
                "web.fetch": self._fetch,
                "web.extract": self._extract,
                "web.search": self._search,
            }
            handler = dispatch.get(skill_name)
            if handler is None:
                return CapabilityResult.fail("web", skill_name, "unknown_skill", f"Unknown skill: {skill_name}")
            data = handler(**params)
            return CapabilityResult.ok(
                "web",
                skill_name,
                data,
                source="HTTP fetch",
                duration_ms=(_time.monotonic() - _t0) * 1000,
            )
        except Exception as e:
            return CapabilityResult.fail(
                "web",
                skill_name,
                type(e).__name__,
                str(e),
                source="HTTP fetch",
                duration_ms=(_time.monotonic() - _t0) * 1000,
            )

    def _fetch(self, url: str = "", **kwargs: Any) -> dict[str, Any]:
        if not url:
            return {"error": "url is required", "goal_ok": False}
        resp = self._client.get(url)
        resp.raise_for_status()
        return {
            "url": url,
            "status": resp.status_code,
            "content_type": resp.headers.get("content-type", ""),
            "content_length": len(resp.text),
            "text": resp.text[:5000],
            "goal_ok": True,
        }

    def _extract(self, url: str = "", **kwargs: Any) -> dict[str, Any]:
        if not url:
            return {"error": "url is required", "goal_ok": False}
        resp = self._client.get(url)
        resp.raise_for_status()
        text = self._html_to_text(resp.text)
        return {
            "url": url,
            "extracted_text": text,
            "character_count": len(text),
            "goal_ok": True,
        }

    def _search(self, query: str = "", text: str = "", **kwargs: Any) -> dict[str, Any]:
        q = (query or text or kwargs.get("message") or "").strip()
        if not q:
            return {"error": "query is required", "goal_ok": False}
        # DuckDuckGo HTML endpoint (no API key). Best-effort snippet extraction.
        url = f"https://html.duckduckgo.com/html/?q={quote_plus(q)}"
        resp = self._client.get(url)
        resp.raise_for_status()
        html = resp.text
        results: list[dict[str, str]] = []
        # Result links
        for m in re.finditer(
            r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
            html,
            flags=re.IGNORECASE | re.DOTALL,
        ):
            href = m.group(1)
            title = re.sub(r"<[^>]+>", "", m.group(2))
            title = re.sub(r"\s+", " ", title).strip()
            if href and title:
                results.append({"title": title[:200], "url": href[:500]})
            if len(results) >= 5:
                break
        # Snippets
        snippets = []
        for m in re.finditer(
            r'class="result__snippet"[^>]*>(.*?)</(?:a|td|div)',
            html,
            flags=re.IGNORECASE | re.DOTALL,
        ):
            sn = re.sub(r"<[^>]+>", "", m.group(1))
            sn = re.sub(r"\s+", " ", sn).strip()
            if sn:
                snippets.append(sn[:400])
            if len(snippets) >= 5:
                break
        for i, sn in enumerate(snippets):
            if i < len(results):
                results[i]["snippet"] = sn
            else:
                results.append({"title": "", "url": "", "snippet": sn})
        if not results:
            # Fallback: plain text extract of page
            plain = self._html_to_text(html)[:2000]
            return {
                "query": q,
                "search_url": url,
                "results": [],
                "fallback_text": plain,
                "goal_ok": bool(plain),
                "note": "No structured results parsed; fallback text included",
            }
        return {
            "query": q,
            "search_url": url,
            "results": results,
            "count": len(results),
            "goal_ok": True,
        }

    @staticmethod
    def _html_to_text(html: str) -> str:
        text = re.sub(r"<script\b[^>]*>.*?</script\b[^>]*>", "", html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style\b[^>]*>.*?</style\b[^>]*>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:5000]
