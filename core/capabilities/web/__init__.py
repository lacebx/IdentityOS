from __future__ import annotations

import json
import re
from typing import Any, Optional
from urllib.parse import quote_plus, unquote

import httpx

from core.capabilities.base import Capability, Skill
from core.capabilities.registry import register
from core.capabilities.result import CapabilityResult

# Process-wide search cache so reinstall/new instances keep recent hits
_SEARCH_CACHE: dict[str, dict[str, Any]] = {}


@register
class WebCapability(Capability):
    id = "web"
    name = "Web"
    version = "1.2.0"
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
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            },
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
            "If search returns captcha/blocked, say so honestly and use whatever results were returned.",
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

        cache_key = q.lower().strip()
        # Exact cache hit
        if cache_key in _SEARCH_CACHE and _SEARCH_CACHE[cache_key].get("goal_ok"):
            cached = dict(_SEARCH_CACHE[cache_key])
            cached["cache_hit"] = True
            return cached
        # Fuzzy cache: if a prior successful query shares main tokens, reuse
        tokens = {t for t in re.findall(r"[a-z0-9]+", cache_key) if len(t) > 2}
        for prev_q, prev in _SEARCH_CACHE.items():
            if not prev.get("goal_ok"):
                continue
            prev_tokens = {t for t in re.findall(r"[a-z0-9]+", prev_q) if len(t) > 2}
            if tokens and prev_tokens and len(tokens & prev_tokens) >= max(1, len(tokens) - 1):
                cached = dict(prev)
                cached["cache_hit"] = True
                cached["cache_from_query"] = prev.get("query")
                cached["query"] = q
                return cached

        backends = [
            ("duckduckgo_html", self._search_ddg_html),
            ("duckduckgo_api", self._search_ddg_api),
            ("bing", self._search_bing),
            ("brave", self._search_brave),
            ("wikipedia", self._search_wikipedia),
        ]
        attempts: list[dict[str, Any]] = []
        all_results: list[dict[str, str]] = []
        for name, fn in backends:
            try:
                part = fn(q)
                attempts.append({"backend": name, "ok": True, "count": len(part)})
                for item in part:
                    key = (item.get("url") or "") + "|" + (item.get("title") or "")
                    if not any(
                        ((x.get("url") or "") + "|" + (x.get("title") or "")) == key
                        for x in all_results
                    ):
                        all_results.append(item)
                if len(all_results) >= 6:
                    break
            except Exception as e:
                attempts.append({"backend": name, "ok": False, "error": str(e)[:200]})

        # If empty and query is specific, broaden once
        if not all_results and len(q.split()) > 2:
            broad = " ".join(q.split()[:2])
            try:
                part = self._search_ddg_html(broad)
                attempts.append({"backend": "duckduckgo_html_broad", "ok": True, "count": len(part)})
                all_results.extend(part)
            except Exception as e:
                attempts.append({"backend": "duckduckgo_html_broad", "ok": False, "error": str(e)[:200]})

        ranked = self._rank_results(q, all_results)
        if not ranked:
            return {
                "query": q,
                "results": [],
                "count": 0,
                "attempts": attempts,
                "goal_ok": False,
                "error": "all search backends failed or returned captcha/empty",
            }
        payload = {
            "query": q,
            "results": ranked[:8],
            "count": min(len(ranked), 8),
            "attempts": attempts,
            "goal_ok": True,
        }
        _SEARCH_CACHE[cache_key] = payload
        return payload

    @staticmethod
    def _rank_results(query: str, results: list[dict[str, str]]) -> list[dict[str, str]]:
        tokens = [t.lower() for t in re.findall(r"[a-zA-Z0-9]+", query) if len(t) > 2]
        scored: list[tuple[float, dict[str, str]]] = []
        for item in results:
            blob = f"{item.get('title','')} {item.get('snippet','')} {item.get('url','')}".lower()
            score = 0.0
            for t in tokens:
                if t in blob:
                    score += 2.0
            if "linkedin.com" in blob:
                score += 1.5
            if "instagram.com" in blob or "youtube.com" in blob:
                score += 0.5
            # Penalize unrelated wikipedia people when query tokens missing
            if "wikipedia.org" in blob and score < 2.0:
                score -= 2.0
            if score > 0 or not tokens:
                scored.append((score, item))
        scored.sort(key=lambda x: -x[0])
        return [item for _, item in scored] or results

    def _search_bing(self, q: str) -> list[dict[str, str]]:
        url = f"https://www.bing.com/search?q={quote_plus(q)}&setlang=en-US"
        resp = self._client.get(url)
        resp.raise_for_status()
        html = resp.text
        if "captcha" in html.lower() and "challenge" in html.lower():
            raise RuntimeError("bing captcha")
        results: list[dict[str, str]] = []
        for m in re.finditer(
            r'<li class="b_algo".*?<h2>\s*<a[^>]+href="(https?://[^"]+)"[^>]*>(.*?)</a>.*?'
            r'(?:<p>|class="b_caption".*?<p[^>]*>)(.*?)</p>',
            html,
            flags=re.IGNORECASE | re.DOTALL,
        ):
            href = m.group(1)
            title = re.sub(r"<[^>]+>", "", m.group(2))
            sn = re.sub(r"<[^>]+>", "", m.group(3))
            title = re.sub(r"\s+", " ", title).strip()
            sn = re.sub(r"\s+", " ", sn).strip()
            results.append({"title": title[:200], "url": href[:500], "snippet": sn[:400]})
            if len(results) >= 5:
                break
        if not results:
            for m in re.finditer(
                r'<h2>\s*<a[^>]+href="(https?://[^"]+)"[^>]*>(.*?)</a>',
                html,
                flags=re.IGNORECASE | re.DOTALL,
            ):
                href = m.group(1)
                title = re.sub(r"<[^>]+>", "", m.group(2))
                title = re.sub(r"\s+", " ", title).strip()
                if "bing.com" in href or len(title) < 5:
                    continue
                results.append({"title": title[:200], "url": href[:500], "snippet": ""})
                if len(results) >= 5:
                    break
        return results
    def _search_ddg_api(self, q: str) -> list[dict[str, str]]:
        url = f"https://api.duckduckgo.com/?q={quote_plus(q)}&format=json&no_html=1&skip_disambig=1"
        resp = self._client.get(url)
        resp.raise_for_status()
        data = resp.json()
        results: list[dict[str, str]] = []
        abstract = (data.get("AbstractText") or "").strip()
        abs_url = data.get("AbstractURL") or ""
        abs_src = data.get("AbstractSource") or ""
        if abstract:
            results.append({
                "title": abs_src or "DuckDuckGo Abstract",
                "url": abs_url,
                "snippet": abstract[:500],
            })
        for topic in (data.get("RelatedTopics") or [])[:6]:
            if isinstance(topic, dict) and topic.get("Text"):
                results.append({
                    "title": (topic.get("Text") or "")[:120],
                    "url": topic.get("FirstURL") or "",
                    "snippet": (topic.get("Text") or "")[:400],
                })
            elif isinstance(topic, dict) and topic.get("Topics"):
                for sub in topic["Topics"][:3]:
                    if sub.get("Text"):
                        results.append({
                            "title": (sub.get("Text") or "")[:120],
                            "url": sub.get("FirstURL") or "",
                            "snippet": (sub.get("Text") or "")[:400],
                        })
        return results

    def _search_brave(self, q: str) -> list[dict[str, str]]:
        url = f"https://search.brave.com/search?q={quote_plus(q)}&source=web"
        resp = self._client.get(url)
        resp.raise_for_status()
        html = resp.text
        if "captcha" in html.lower() and "g-recaptcha" in html.lower():
            raise RuntimeError("brave captcha")
        results: list[dict[str, str]] = []
        # Brave result titles
        for m in re.finditer(
            r'<a[^>]+href="(https?://[^"]+)"[^>]*class="[^"]*result-title[^"]*"[^>]*>(.*?)</a>',
            html,
            flags=re.IGNORECASE | re.DOTALL,
        ):
            href, title = m.group(1), re.sub(r"<[^>]+>", "", m.group(2))
            title = re.sub(r"\s+", " ", title).strip()
            if href and title and "brave.com" not in href:
                results.append({"title": title[:200], "url": href[:500], "snippet": ""})
            if len(results) >= 5:
                break
        if not results:
            # fallback looser pattern
            for m in re.finditer(
                r'<a[^>]+href="(https?://(?!cdn\.|search\.brave)[^"]+)"[^>]*>(.*?)</a>',
                html,
                flags=re.IGNORECASE | re.DOTALL,
            ):
                href = m.group(1)
                title = re.sub(r"<[^>]+>", "", m.group(2))
                title = re.sub(r"\s+", " ", title).strip()
                if len(title) < 8 or "http" in title.lower():
                    continue
                results.append({"title": title[:200], "url": href[:500], "snippet": ""})
                if len(results) >= 5:
                    break
        return results

    def _search_wikipedia(self, q: str) -> list[dict[str, str]]:
        api = (
            "https://en.wikipedia.org/w/api.php"
            f"?action=opensearch&search={quote_plus(q)}&limit=5&namespace=0&format=json"
        )
        resp = self._client.get(api)
        resp.raise_for_status()
        data = resp.json()
        # [query, titles[], descriptions[], urls[]]
        titles = data[1] if len(data) > 1 else []
        descs = data[2] if len(data) > 2 else []
        urls = data[3] if len(data) > 3 else []
        results = []
        for i, title in enumerate(titles):
            results.append({
                "title": title,
                "url": urls[i] if i < len(urls) else "",
                "snippet": descs[i] if i < len(descs) else "",
            })
        return results

    def _search_ddg_html(self, q: str) -> list[dict[str, str]]:
        url = f"https://html.duckduckgo.com/html/?q={quote_plus(q)}"
        resp = self._client.get(url)
        resp.raise_for_status()
        html = resp.text
        if "anomaly" in html.lower() or "captcha" in html.lower() or "select all squares" in html.lower():
            raise RuntimeError("duckduckgo html captcha")
        results: list[dict[str, str]] = []
        for m in re.finditer(
            r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
            html,
            flags=re.IGNORECASE | re.DOTALL,
        ):
            href = unquote(m.group(1))
            # DDG redirect links often wrap uddg=
            um = re.search(r"uddg=([^&]+)", href)
            if um:
                href = unquote(um.group(1))
            title = re.sub(r"<[^>]+>", "", m.group(2))
            title = re.sub(r"\s+", " ", title).strip()
            if href and title:
                results.append({"title": title[:200], "url": href[:500], "snippet": ""})
            if len(results) >= 5:
                break
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
        return results

    @staticmethod
    def _html_to_text(html: str) -> str:
        text = re.sub(r"<script\b[^>]*>.*?</script\b[^>]*>", "", html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style\b[^>]*>.*?</style\b[^>]*>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:5000]
