"""Browser capability — person-like web surfing for IdentityOS identities.

Comet-inspired agentic browsing: search, judge usefulness, navigate,
interact with pages (click/type/login), and keep a persistent session so
logged-in work continues across skill calls.
"""

from __future__ import annotations

import re
import shutil
import time
from contextvars import ContextVar
from typing import Any, Optional
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

import httpx

from core.capabilities.base import Capability, Skill, object_schema
from core.capabilities.registry import register
from core.capabilities.result import CapabilityResult

from .session import (
    BrowserUnavailable,
    close_identity_sessions,
    close_session,
    ensure_session,
    get_session,
    identity_browser_dir,
    page_snapshot,
    run_in_browser_thread,
)
from .url_policy import validate_navigation_url

_SECRET_KEYS = {"password", "passwd", "pass", "secret", "token", "api_key"}
_EXECUTION_SCOPE: ContextVar[str] = ContextVar(
    "identityos_browser_execution_scope",
    default="sdk",
)


def _redact(params: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in params.items():
        if k.lower() in _SECRET_KEYS or "password" in k.lower():
            out[k] = "***"
        else:
            out[k] = v
    return out


def _score_result(task: str, title: str, snippet: str, url: str) -> dict[str, Any]:
    """Heuristic usefulness score for a search hit against a task."""
    task_l = (task or "").lower()
    blob = f"{title} {snippet} {url}".lower()
    tokens = [t for t in re.findall(r"[a-z0-9]{3,}", task_l) if t not in {
        "the", "and", "for", "with", "from", "that", "this", "into", "about",
        "open", "find", "search", "please", "using", "what", "when", "where",
    }]
    if not tokens:
        tokens = re.findall(r"[a-z0-9]{3,}", task_l)[:8]

    hits = sum(1 for t in tokens if t in blob)
    coverage = hits / max(len(tokens), 1)
    # Prefer primary sources / docs / official pages slightly
    bonus = 0.0
    if any(x in url.lower() for x in ("docs.", "github.com", "wikipedia.org", "gov", "edu")):
        bonus += 0.08
    if any(x in blob for x in ("login", "sign in", "account")) and "login" in task_l:
        bonus += 0.1
    score = min(1.0, round(coverage * 0.85 + bonus, 3))
    # Short tasks / strong title hits still count as useful
    if coverage >= 0.25 and hits >= 1:
        score = max(score, 0.36)
    title_l = (title or "").lower()
    if any(t in title_l for t in tokens[:4]) and hits >= 1:
        score = max(score, 0.4)
    useful = score >= 0.35
    reason_parts = []
    if hits:
        matched = [t for t in tokens if t in blob][:6]
        reason_parts.append(f"matched terms: {', '.join(matched)}")
    else:
        reason_parts.append("no task keywords matched")
    if bonus:
        reason_parts.append("trusted/domain bonus applied")
    return {
        "useful": useful,
        "score": score,
        "reason": "; ".join(reason_parts),
        "matched_terms": [t for t in tokens if t in blob],
    }


@register
class BrowserCapability(Capability):
    id = "browser"
    name = "Browser"
    version = "1.0.0"
    author = "IdentityOS"
    license = "MIT"
    homepage = "https://github.com/lacebx/IdentityOS"
    description = (
        "Person-like web surfing: search, judge result usefulness, open pages, "
        "click/type/login, and act inside authenticated sessions (Comet-style)."
    )
    permissions = ["browser:read", "browser:write", "browser:credentials"]
    default_grants = ["browser:read", "browser:write"]

    def __init__(self, config: Optional[dict] = None) -> None:
        super().__init__(config)
        self._storage_root = (config or {}).get("storage_root", ".identity_store")
        self._headless = bool((config or {}).get("headless", True))
        self._allow_private_network = bool(
            (config or {}).get("allow_private_network", False)
        )
        self._identity_id = ""
        self._http = httpx.Client(
            timeout=20,
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                )
            },
        )

    def install(self, identity_id: str, storage: Any) -> None:
        self._identity_id = identity_id
        storage.save(
            identity_id,
            "capability.browser",
            {"installed_at": time.time(), "headless": self._headless},
        )

    def uninstall(self, identity_id: str, storage: Any) -> None:
        close_identity_sessions(identity_id, storage_root=self._storage_root)
        profile_root = identity_browser_dir(self._storage_root, identity_id)
        if profile_root.is_dir():
            shutil.rmtree(profile_root)
        storage.delete(identity_id, "capability.browser")

    def on_identity_loaded(self, identity_id: str) -> None:
        self._identity_id = identity_id

    def prompts(self, identity_id: str) -> list[str]:
        return [
            "## Browser Skills (MANDATORY for web tasks)",
            "You can surf the web like a person using browser.* skills.",
            "Workflow for research:",
            "1) browser.search(query, task=...) to get results with usefulness scores",
            "2) Prefer results marked useful=true / higher score for the given task",
            "3) browser.open or browser.navigate to visit a promising URL",
            "4) browser.snapshot to read the page and see clickable elements",
            "5) browser.click / browser.type / browser.fill / browser.press to interact",
            "6) browser.login only after browser:credentials is explicitly granted",
            "7) Keep using browser.snapshot after each action to verify what changed",
            "Do NOT claim you cannot browse, search, or log in. You CAN — use these skills.",
            "Never invent page content. Only report what browser.snapshot / search returned.",
            "Chat credentials must use password=<value>; the runtime replaces the value with an ephemeral reference.",
            "Never invent or echo passwords. Preserve secret-ref:// values exactly in tool arguments.",
            "Only log into sites the user explicitly authorized with credentials they provided.",
        ]

    _SKILLS = [
        Skill(
            name="browser.open",
            description="Open a URL in a persistent browser session (starts browser if needed)",
            permission="browser:read",
            effect="write",
            input_schema=object_schema(
                {
                    "url": {"type": "string", "minLength": 1},
                    "headless": {"type": "boolean"},
                    "wait_until": {"type": "string"},
                },
                required=("url",),
            ),
        ),
        Skill(
            name="browser.navigate",
            description="Navigate the current tab to a URL",
            permission="browser:write",
            effect="write",
            input_schema=object_schema(
                {
                    "url": {"type": "string", "minLength": 1},
                    "wait_until": {"type": "string"},
                },
                required=("url",),
            ),
        ),
        Skill(
            name="browser.search",
            description=(
                "Search the web and return ranked results. Pass task= so each result "
                "includes a usefulness score relative to the user's goal."
            ),
            permission="browser:read",
            effect="read",
            input_schema=object_schema(
                {
                    "query": {"type": "string", "minLength": 1},
                    "task": {"type": "string"},
                    "max_results": {"type": "integer"},
                    "engine": {"type": "string"},
                },
                required=("query",),
            ),
        ),
        Skill(
            name="browser.evaluate_results",
            description=(
                "Score previously obtained search results against a task and recommend "
                "which URLs are worth opening."
            ),
            permission="browser:read",
            effect="read",
            input_schema=object_schema(
                {
                    "task": {"type": "string", "minLength": 1},
                    "results": {"type": "array"},
                    "min_score": {"type": "number"},
                },
                required=("task", "results"),
            ),
        ),
        Skill(
            name="browser.snapshot",
            description="Read the current page: URL, title, visible text, and interactive elements",
            permission="browser:read",
            effect="read",
            input_schema=object_schema(
                {"max_chars": {"type": "integer"}},
            ),
        ),
        Skill(
            name="browser.click",
            description="Click an element by CSS selector, visible text, or role+name",
            permission="browser:write",
            effect="write",
            input_schema=object_schema(
                {
                    "selector": {"type": "string"},
                    "text": {"type": "string"},
                    "role": {"type": "string"},
                    "name": {"type": "string"},
                    "exact": {"type": "boolean"},
                },
            ),
        ),
        Skill(
            name="browser.type",
            description="Type text into a focused or selected input (optionally clear first)",
            permission="browser:write",
            effect="write",
            input_schema=object_schema(
                {
                    "text": {"type": "string"},
                    "selector": {"type": "string"},
                    "clear": {"type": "boolean"},
                    "press_enter": {"type": "boolean"},
                },
                required=("text",),
            ),
        ),
        Skill(
            name="browser.fill",
            description="Fill a form field by selector (clears existing value)",
            permission="browser:write",
            effect="write",
            input_schema=object_schema(
                {
                    "selector": {"type": "string", "minLength": 1},
                    "value": {"type": "string"},
                },
                required=("selector", "value"),
            ),
        ),
        Skill(
            name="browser.login",
            description=(
                "Log into a site with user-provided credentials. Optionally pass "
                "username_selector/password_selector/submit_selector; otherwise auto-detect."
            ),
            permission="browser:credentials",
            effect="write",
            input_schema=object_schema(
                {
                    "url": {"type": "string", "minLength": 1},
                    "username": {"type": "string", "minLength": 1},
                    "password": {
                        "type": "string",
                        "minLength": 1,
                        "description": "Opaque secret-ref:// value supplied by the runtime",
                    },
                    "username_selector": {"type": "string"},
                    "password_selector": {"type": "string"},
                    "submit_selector": {"type": "string"},
                    "success_url_contains": {"type": "string"},
                    "success_selector": {"type": "string"},
                    "wait_ms": {"type": "integer"},
                },
                required=("url", "username", "password"),
            ),
        ),
        Skill(
            name="browser.press",
            description="Press a keyboard key (Enter, Tab, Escape, etc.)",
            permission="browser:write",
            effect="write",
            input_schema=object_schema(
                {"key": {"type": "string", "minLength": 1}},
                required=("key",),
            ),
        ),
        Skill(
            name="browser.wait",
            description="Wait for a selector, URL substring, or fixed milliseconds",
            permission="browser:read",
            effect="read",
            input_schema=object_schema(
                {
                    "selector": {"type": "string"},
                    "url_contains": {"type": "string"},
                    "ms": {"type": "integer"},
                    "timeout_ms": {"type": "integer"},
                },
            ),
        ),
        Skill(
            name="browser.status",
            description="Report whether a browser session is open and the current URL/title",
            permission="browser:read",
            effect="read",
            input_schema=object_schema({}),
        ),
        Skill(
            name="browser.close",
            description="Close the browser session (cookies in profile may persist on disk)",
            permission="browser:write",
            effect="write",
            input_schema=object_schema({}),
        ),
    ]

    def skills(self) -> list[Skill]:
        return list(self._SKILLS)

    def call(self, skill_name: str, **params: Any) -> CapabilityResult:
        return self._call(skill_name, **params)

    def call_scoped(
        self,
        skill_name: str,
        *,
        execution_scope: Optional[str] = None,
        **params: Any,
    ) -> CapabilityResult:
        token = _EXECUTION_SCOPE.set(execution_scope or "sdk")
        try:
            return self._call(skill_name, **params)
        finally:
            _EXECUTION_SCOPE.reset(token)

    def _call(self, skill_name: str, **params: Any) -> CapabilityResult:
        t0 = time.monotonic()
        safe = _redact(params)
        try:
            dispatch = {
                "browser.open": self._open,
                "browser.navigate": self._navigate,
                "browser.search": self._search,
                "browser.evaluate_results": self._evaluate_results,
                "browser.snapshot": self._snapshot,
                "browser.click": self._click,
                "browser.type": self._type,
                "browser.fill": self._fill,
                "browser.login": self._login,
                "browser.press": self._press,
                "browser.wait": self._wait,
                "browser.status": self._status,
                "browser.close": self._close,
            }
            handler = dispatch.get(skill_name)
            if handler is None:
                return CapabilityResult.fail(
                    "browser", skill_name, "unknown_skill", f"Unknown skill: {skill_name}",
                    params=safe,
                )
            data = handler(**params)
            return CapabilityResult.from_data(
                "browser",
                skill_name,
                data,
                source="browser session",
                duration_ms=(time.monotonic() - t0) * 1000,
                params=safe,
            )
        except BrowserUnavailable as e:
            return CapabilityResult.fail(
                "browser", skill_name, "BrowserUnavailable", str(e),
                source="browser session",
                duration_ms=(time.monotonic() - t0) * 1000,
                params=safe,
            )
        except Exception as e:
            return CapabilityResult.fail(
                "browser", skill_name, type(e).__name__, str(e),
                source="browser session",
                duration_ms=(time.monotonic() - t0) * 1000,
                params=safe,
            )

    # ── helpers ────────────────────────────────────────────────────────

    def _require_identity(self) -> str:
        if self._identity_id:
            return self._identity_id
        # Fallback for direct calls before on_identity_loaded
        return "default"

    def _page(self, *, headless: Optional[bool] = None):
        identity_id = self._require_identity()
        state = ensure_session(
            identity_id,
            storage_root=self._storage_root,
            headless=self._headless if headless is None else headless,
            execution_scope=_EXECUTION_SCOPE.get(),
            allow_private_network=self._allow_private_network,
        )
        return state

    def _session(self):
        return get_session(
            self._require_identity(),
            storage_root=self._storage_root,
            execution_scope=_EXECUTION_SCOPE.get(),
        )

    def _goto(self, url: str, wait_until: str = "domcontentloaded") -> dict[str, Any]:
        url = validate_navigation_url(
            url,
            allow_private_network=self._allow_private_network,
        )
        allowed = {"load", "domcontentloaded", "networkidle", "commit"}
        wu = (wait_until or "domcontentloaded").strip().lower()
        # Models sometimes emit Puppeteer names (networkidle0/2).
        if wu in {"networkidle0", "networkidle2"}:
            wu = "networkidle"
        if wu not in allowed:
            wu = "domcontentloaded"

        def _do() -> dict[str, Any]:
            state = self._page()
            with state.lock:
                page = state.page
                page.goto(url, wait_until=wu, timeout=45000)
                state.last_url = page.url
                state.history.append(page.url)
                snap = page_snapshot(page, max_chars=4000)
                return {
                    "ok": True,
                    "url": page.url,
                    "title": snap["title"],
                    "text_preview": snap["text"][:1500],
                    "interactive_count": snap["interactive_count"],
                }

        return run_in_browser_thread(_do)

    # ── skills ─────────────────────────────────────────────────────────

    def _open(self, url: str = "", headless: Optional[bool] = None, wait_until: str = "domcontentloaded", **_: Any) -> dict[str, Any]:
        if not url:
            return {"error": "url is required"}
        if headless is not None:
            self._headless = bool(headless)
        return self._goto(url, wait_until=wait_until)

    def _navigate(self, url: str = "", wait_until: str = "domcontentloaded", **_: Any) -> dict[str, Any]:
        if not url:
            return {"error": "url is required"}
        state = self._session()
        if state is None or not state.started:
            return self._goto(url, wait_until=wait_until)
        return self._goto(url, wait_until=wait_until)

    def _search(
        self,
        query: str = "",
        task: str = "",
        max_results: int = 8,
        engine: str = "duckduckgo",
        **_: Any,
    ) -> dict[str, Any]:
        if not query:
            return {"error": "query is required"}
        max_results = max(1, min(int(max_results or 8), 15))
        task = task or query
        engine = (engine or "duckduckgo").lower()

        results = self._search_duckduckgo(query, max_results=max_results)
        if not results and engine != "html":
            # Fallback: open DDG in real browser and scrape links
            results = self._search_browser(query, max_results=max_results)

        scored = []
        for r in results:
            judgment = _score_result(task, r.get("title", ""), r.get("snippet", ""), r.get("url", ""))
            scored.append({**r, **judgment})

        scored.sort(key=lambda x: x.get("score", 0), reverse=True)
        useful = [r for r in scored if r.get("useful")]
        return {
            "query": query,
            "task": task,
            "engine": "duckduckgo",
            "result_count": len(scored),
            "useful_count": len(useful),
            "recommended": useful[:3] or scored[:2],
            "results": scored,
            "guidance": (
                "Open recommended URLs with browser.open / browser.navigate, "
                "then browser.snapshot to verify content before acting."
            ),
        }

    def _search_duckduckgo(self, query: str, max_results: int) -> list[dict[str, Any]]:
        url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
        resp = self._http.get(url)
        resp.raise_for_status()
        html = resp.text
        results: list[dict[str, Any]] = []

        anchors = re.findall(
            r'<a[^>]*class="[^"]*result__a[^"]*"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
            html,
            flags=re.I | re.S,
        )
        if not anchors:
            anchors = re.findall(
                r'<a[^>]*href="([^"]+)"[^>]*class="[^"]*result__a[^"]*"[^>]*>(.*?)</a>',
                html,
                flags=re.I | re.S,
            )

        snippets = re.findall(
            r'class="result__snippet"[^>]*>(.*?)</(?:a|td|div)',
            html,
            flags=re.I | re.S,
        )

        for idx, (href, title_html) in enumerate(anchors):
            if len(results) >= max_results:
                break
            title = re.sub(r"<[^>]+>", "", title_html).strip()
            snippet = ""
            if idx < len(snippets):
                snippet = re.sub(r"<[^>]+>", "", snippets[idx]).strip()
            final_url = self._unwrap_ddg(href)
            if not final_url or "duckduckgo.com" in final_url:
                continue
            results.append({"title": title, "url": final_url, "snippet": snippet[:400]})
        return results

    def _unwrap_ddg(self, href: str) -> str:
        href = href.replace("&amp;", "&")
        if "uddg=" in href:
            qs = parse_qs(urlparse(href).query)
            if "uddg" in qs:
                return unquote(qs["uddg"][0])
        if href.startswith("//"):
            href = "https:" + href
        return href

    def _search_browser(self, query: str, max_results: int) -> list[dict[str, Any]]:
        def _do() -> list[dict[str, Any]]:
            state = self._page()
            with state.lock:
                page = state.page
                page.goto(
                    f"https://html.duckduckgo.com/html/?q={quote_plus(query)}",
                    wait_until="domcontentloaded",
                    timeout=45000,
                )
                results: list[dict[str, Any]] = []
                anchors = page.query_selector_all("a.result__a")
                for a in anchors[:max_results]:
                    try:
                        title = (a.inner_text() or "").strip()
                        href = a.get_attribute("href") or ""
                        url = self._unwrap_ddg(href)
                        results.append({"title": title, "url": url, "snippet": ""})
                    except Exception:
                        continue
                state.last_url = page.url
                return results

        return run_in_browser_thread(_do)

    def _evaluate_results(
        self,
        task: str = "",
        results: Optional[list] = None,
        min_score: float = 0.35,
        **_: Any,
    ) -> dict[str, Any]:
        if not task:
            return {"error": "task is required"}
        results = results or []
        if not isinstance(results, list):
            return {"error": "results must be a list of {title,url,snippet} objects"}

        scored = []
        for r in results:
            if not isinstance(r, dict):
                continue
            judgment = _score_result(
                task,
                str(r.get("title", "")),
                str(r.get("snippet", r.get("description", ""))),
                str(r.get("url", r.get("link", ""))),
            )
            item = {
                "title": r.get("title", ""),
                "url": r.get("url", r.get("link", "")),
                "snippet": r.get("snippet", r.get("description", "")),
                **judgment,
            }
            scored.append(item)
        scored.sort(key=lambda x: x.get("score", 0), reverse=True)
        useful = [r for r in scored if r.get("score", 0) >= float(min_score)]
        return {
            "task": task,
            "min_score": min_score,
            "useful_count": len(useful),
            "recommended_urls": [r["url"] for r in useful[:5] if r.get("url")],
            "results": scored,
            "verdict": (
                f"{len(useful)} of {len(scored)} results look useful for the task"
                if scored else "no results to evaluate"
            ),
        }

    def _snapshot(self, max_chars: int = 12000, **_: Any) -> dict[str, Any]:
        def _do() -> dict[str, Any]:
            state = self._session()
            if state is None or not state.started or state.page is None:
                return {"error": "no open browser session — call browser.open first"}
            with state.lock:
                snap = page_snapshot(state.page, max_chars=int(max_chars or 12000))
                snap["history_len"] = len(state.history)
                return snap

        return run_in_browser_thread(_do)

    def _resolve_locator(self, page: Any, *, selector: str = "", text: str = "", role: str = "", name: str = "", exact: bool = False):
        if selector:
            return page.locator(selector).first
        if role and name:
            return page.get_by_role(role, name=name, exact=exact).first
        if text:
            return page.get_by_text(text, exact=exact).first
        if name:
            return page.get_by_label(name, exact=exact).first
        raise ValueError("Provide selector, text, or role+name")

    def _click(
        self,
        selector: str = "",
        text: str = "",
        role: str = "",
        name: str = "",
        exact: bool = False,
        **_: Any,
    ) -> dict[str, Any]:
        def _do() -> dict[str, Any]:
            state = self._session()
            if state is None or state.page is None:
                return {"error": "no open browser session — call browser.open first"}
            with state.lock:
                page = state.page
                loc = self._resolve_locator(page, selector=selector, text=text, role=role, name=name, exact=exact)
                loc.click(timeout=15000)
                try:
                    page.wait_for_load_state("domcontentloaded", timeout=10000)
                except Exception:
                    pass
                state.last_url = page.url
                snap = page_snapshot(page, max_chars=3000)
                return {
                    "ok": True,
                    "clicked": {"selector": selector, "text": text, "role": role, "name": name},
                    "url": page.url,
                    "title": snap["title"],
                    "text_preview": snap["text"][:1200],
                }

        return run_in_browser_thread(_do)

    def _type(
        self,
        text: str = "",
        selector: str = "",
        clear: bool = False,
        press_enter: bool = False,
        **_: Any,
    ) -> dict[str, Any]:
        if text is None:
            return {"error": "text is required"}

        def _do() -> dict[str, Any]:
            state = self._session()
            if state is None or state.page is None:
                return {"error": "no open browser session — call browser.open first"}
            with state.lock:
                page = state.page
                if selector:
                    loc = page.locator(selector).first
                    if clear:
                        loc.fill("")
                    loc.type(str(text), delay=20)
                else:
                    if clear:
                        page.keyboard.press("Control+A")
                        page.keyboard.press("Backspace")
                    page.keyboard.type(str(text), delay=20)
                if press_enter:
                    page.keyboard.press("Enter")
                    try:
                        page.wait_for_load_state("domcontentloaded", timeout=10000)
                    except Exception:
                        pass
                state.last_url = page.url
                return {"ok": True, "url": page.url, "typed_len": len(str(text)), "pressed_enter": press_enter}

        return run_in_browser_thread(_do)

    def _fill(self, selector: str = "", value: str = "", **_: Any) -> dict[str, Any]:
        if not selector:
            return {"error": "selector is required"}

        def _do() -> dict[str, Any]:
            state = self._session()
            if state is None or state.page is None:
                return {"error": "no open browser session — call browser.open first"}
            with state.lock:
                page = state.page
                page.locator(selector).first.fill(str(value), timeout=15000)
                return {"ok": True, "selector": selector, "value_len": len(str(value)), "url": page.url}

        return run_in_browser_thread(_do)

    def _login(
        self,
        url: str = "",
        username: str = "",
        password: str = "",
        username_selector: str = "",
        password_selector: str = "",
        submit_selector: str = "",
        success_url_contains: str = "",
        success_selector: str = "",
        wait_ms: int = 2500,
        **_: Any,
    ) -> dict[str, Any]:
        if not url or not username or not password:
            return {"error": "url, username, and password are required"}
        if not success_url_contains and not success_selector:
            return {
                "error": (
                    "login requires success_url_contains or success_selector so the "
                    "runtime can verify authentication"
                )
            }

        # Navigate first (already worker-threaded)
        nav = self._goto(url)
        if nav.get("error"):
            return nav

        def _do() -> dict[str, Any]:
            state = self._page()
            with state.lock:
                page = state.page

                user_sel = username_selector or self._autodetect_username(page)
                pass_sel = password_selector or self._autodetect_password(page)
                if not user_sel or not pass_sel:
                    snap = page_snapshot(page, max_chars=2000)
                    return {
                        "error": "Could not auto-detect login fields; pass username_selector and password_selector",
                        "url": page.url,
                        "interactive": snap.get("interactive", [])[:20],
                    }

                page.locator(user_sel).first.fill(username, timeout=15000)
                page.locator(pass_sel).first.fill(password, timeout=15000)

                submitted = False
                if submit_selector:
                    page.locator(submit_selector).first.click(timeout=15000)
                    submitted = True
                else:
                    for cand in (
                        "button[type='submit']",
                        "input[type='submit']",
                        "button:has-text('Log in')",
                        "button:has-text('Sign in')",
                        "button:has-text('Login')",
                        "[type='submit']",
                    ):
                        try:
                            loc = page.locator(cand).first
                            if page.locator(cand).count() > 0:
                                loc.click(timeout=3000)
                                submitted = True
                                break
                        except Exception:
                            continue
                    if not submitted:
                        page.locator(pass_sel).first.press("Enter")
                        submitted = True

                page.wait_for_timeout(int(wait_ms or 2500))
                try:
                    page.wait_for_load_state("networkidle", timeout=15000)
                except Exception:
                    pass

                state.last_url = page.url
                snap = page_snapshot(page, max_chars=4000)
                success = True
                if success_url_contains:
                    success = success and success_url_contains in page.url
                if success_selector:
                    try:
                        success = success and (
                            page.locator(success_selector).count() > 0
                            and page.locator(success_selector).first.is_visible()
                        )
                    except Exception:
                        success = False

                body = (snap.get("text") or "").lower()
                failure_hints = [
                    "incorrect password",
                    "invalid credentials",
                    "login failed",
                    "sign in failed",
                    "wrong password",  # ggignore: authentication failure text, not a credential
                    "authentication failed",
                ]
                if any(h in body for h in failure_hints):
                    success = False

                safe_text = (snap.get("text") or "").replace(password, "***")

                if not success:
                    return {
                        "ok": False,
                        "error": "login post-condition was not satisfied",
                        "submitted": submitted,
                        "url": page.url,
                        "title": snap.get("title"),
                        "text_preview": safe_text[:1500],
                    }

                return {
                    "ok": success,
                    "submitted": submitted,
                    "username_selector": user_sel,
                    "password_selector": pass_sel,  # ggignore: selector name, never a credential
                    "url": page.url,
                    "title": snap.get("title"),
                    "text_preview": safe_text[:1500],
                    "note": (
                        "Login attempt finished. Verify with browser.snapshot before continuing "
                        "authenticated tasks. Password was not stored in the result."
                    ),
                }

        return run_in_browser_thread(_do)

    def _autodetect_username(self, page: Any) -> str:
        candidates = [
            "input[type='email']",
            "input[name='email']",
            "input[id='email']",
            "input[name='username']",
            "input[id='username']",
            "input[autocomplete='username']",
            "input[name='login']",
            "input[type='text']",
        ]
        for sel in candidates:
            try:
                if page.locator(sel).count() > 0:
                    return sel
            except Exception:
                continue
        return ""

    def _autodetect_password(self, page: Any) -> str:
        candidates = [
            "input[type='password']",
            "input[name='password']",
            "input[id='password']",
            "input[autocomplete='current-password']",
        ]
        for sel in candidates:
            try:
                if page.locator(sel).count() > 0:
                    return sel
            except Exception:
                continue
        return ""

    def _press(self, key: str = "", **_: Any) -> dict[str, Any]:
        if not key:
            return {"error": "key is required"}

        def _do() -> dict[str, Any]:
            state = self._session()
            if state is None or state.page is None:
                return {"error": "no open browser session — call browser.open first"}
            with state.lock:
                state.page.keyboard.press(key)
                return {"ok": True, "key": key, "url": state.page.url}

        return run_in_browser_thread(_do)

    def _wait(
        self,
        selector: str = "",
        url_contains: str = "",
        ms: int = 0,
        timeout_ms: int = 15000,
        **_: Any,
    ) -> dict[str, Any]:
        def _do() -> dict[str, Any]:
            state = self._session()
            if state is None or state.page is None:
                return {"error": "no open browser session — call browser.open first"}
            with state.lock:
                page = state.page
                if selector:
                    page.wait_for_selector(selector, timeout=int(timeout_ms or 15000))
                if url_contains:
                    page.wait_for_url(f"**/*{url_contains}*", timeout=int(timeout_ms or 15000))
                if ms:
                    page.wait_for_timeout(int(ms))
                if not selector and not url_contains and not ms:
                    page.wait_for_timeout(500)
                state.last_url = page.url
                return {"ok": True, "url": page.url}

        return run_in_browser_thread(_do)

    def _status(self, **_: Any) -> dict[str, Any]:
        def _do() -> dict[str, Any]:
            state = self._session()
            if state is None or not state.started or state.page is None:
                return {"open": False, "identity_id": self._require_identity()}
            with state.lock:
                try:
                    title = state.page.title()
                    url = state.page.url
                except Exception:
                    title, url = "", state.last_url
                return {
                    "open": True,
                    "identity_id": self._require_identity(),
                    "url": url,
                    "title": title,
                    "history_len": len(state.history),
                    "headless": state.headless,
                }

        return run_in_browser_thread(_do)

    def _close(self, **_: Any) -> dict[str, Any]:
        closed = close_session(
            self._require_identity(),
            storage_root=self._storage_root,
            execution_scope=_EXECUTION_SCOPE.get(),
        )
        return {"closed": closed, "identity_id": self._require_identity()}
