"""Persistent Playwright browser sessions keyed by identity.

Playwright's sync API cannot run inside an asyncio event loop (common under
pytest-asyncio / FastAPI). All sync Playwright work is confined to a dedicated
daemon thread with its own event loop semantics.
"""

from __future__ import annotations

import atexit
import queue
import threading
from concurrent.futures import Future
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional, TypeVar

T = TypeVar("T")


class BrowserUnavailable(RuntimeError):
    """Raised when Playwright / Chromium is not installed."""


@dataclass
class SessionState:
    identity_id: str
    headless: bool = True
    user_data_dir: Optional[Path] = None
    playwright: Any = None
    browser: Any = None
    context: Any = None
    page: Any = None
    started: bool = False
    last_url: str = ""
    history: list[str] = field(default_factory=list)
    lock: threading.RLock = field(default_factory=threading.RLock)


_SESSIONS: dict[str, SessionState] = {}
_GLOBAL_LOCK = threading.RLock()

# Dedicated worker so sync Playwright never touches a foreign asyncio loop.
_JOBS: queue.Queue = queue.Queue()
_WORKER_READY = threading.Event()


def _worker_main() -> None:
    _WORKER_READY.set()
    while True:
        item = _JOBS.get()
        if item is None:
            break
        fn, fut = item
        try:
            fut.set_result(fn())
        except BaseException as exc:  # noqa: BLE001 — propagate to caller
            fut.set_exception(exc)


_WORKER = threading.Thread(target=_worker_main, name="identityos-playwright", daemon=True)
_WORKER.start()
_WORKER_READY.wait(timeout=5)


def run_in_browser_thread(fn: Callable[[], T]) -> T:
    """Execute ``fn`` on the Playwright worker thread and return its result."""
    if threading.current_thread() is _WORKER:
        return fn()
    fut: Future = Future()
    _JOBS.put((fn, fut))
    return fut.result(timeout=120)


def _import_playwright():
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except ImportError as exc:
        raise BrowserUnavailable(
            "Playwright is not installed. Run: "
            'pip install "playwright>=1.40" && playwright install chromium'
        ) from exc
    return sync_playwright


def session_dir(storage_root: str | Path, identity_id: str) -> Path:
    root = Path(storage_root) / identity_id / "browser"
    root.mkdir(parents=True, exist_ok=True)
    return root


def get_session(identity_id: str) -> Optional[SessionState]:
    with _GLOBAL_LOCK:
        return _SESSIONS.get(identity_id)


def ensure_session(
    identity_id: str,
    *,
    storage_root: str | Path = ".identity_store",
    headless: bool = True,
    user_agent: Optional[str] = None,
) -> SessionState:
    """Start or reuse a browser session for this identity."""

    def _ensure() -> SessionState:
        with _GLOBAL_LOCK:
            existing = _SESSIONS.get(identity_id)
            if existing and existing.started and existing.page is not None:
                return existing

            sync_playwright = _import_playwright()
            state = SessionState(
                identity_id=identity_id,
                headless=headless,
                user_data_dir=session_dir(storage_root, identity_id),
            )
            state.playwright = sync_playwright().start()
            try:
                state.context = state.playwright.chromium.launch_persistent_context(
                    user_data_dir=str(state.user_data_dir / "profile"),
                    headless=headless,
                    viewport={"width": 1280, "height": 800},
                    locale="en-US",
                    user_agent=user_agent
                    or (
                        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                    ),
                    args=["--disable-blink-features=AutomationControlled"],
                )
                state.page = state.context.pages[0] if state.context.pages else state.context.new_page()
                state.started = True
                _SESSIONS[identity_id] = state
                return state
            except Exception:
                _safe_close(state)
                raise

    return run_in_browser_thread(_ensure)


def _safe_close(state: SessionState) -> None:
    with state.lock:
        for attr in ("context", "browser", "playwright"):
            obj = getattr(state, attr, None)
            if obj is None:
                continue
            try:
                if attr == "playwright":
                    obj.stop()
                else:
                    obj.close()
            except Exception:
                pass
            setattr(state, attr, None)
        state.page = None
        state.started = False


def close_session(identity_id: str) -> bool:
    def _close() -> bool:
        with _GLOBAL_LOCK:
            state = _SESSIONS.pop(identity_id, None)
        if state is None:
            return False
        _safe_close(state)
        return True

    return run_in_browser_thread(_close)


def close_all() -> None:
    with _GLOBAL_LOCK:
        ids = list(_SESSIONS.keys())
    for identity_id in ids:
        close_session(identity_id)


atexit.register(close_all)


def page_snapshot(page: Any, *, max_chars: int = 12000) -> dict[str, Any]:
    """Collect a person-usable page snapshot for agent reasoning."""
    title = ""
    url = ""
    try:
        title = page.title()
        url = page.url
    except Exception:
        pass

    text = ""
    try:
        text = page.inner_text("body")
    except Exception:
        try:
            text = page.content()
        except Exception:
            text = ""
    text = " ".join(text.split())
    if len(text) > max_chars:
        text = text[:max_chars] + "…"

    interactive: list[dict[str, Any]] = []
    try:
        elements = page.query_selector_all(
            "a[href], button, input, textarea, select, [role='button'], [role='link'], [contenteditable='true']"
        )
        for el in elements[:80]:
            try:
                tag = (el.evaluate("e => e.tagName") or "").lower()
                role = el.get_attribute("role") or tag
                name = (
                    el.get_attribute("aria-label")
                    or el.get_attribute("name")
                    or el.get_attribute("placeholder")
                    or el.get_attribute("title")
                    or (el.inner_text() or "")[:80]
                ).strip()
                itype = el.get_attribute("type") or ""
                href = el.get_attribute("href") or ""
                selector_hint = _selector_hint(el, tag)
                if not name and not href:
                    continue
                interactive.append(
                    {
                        "role": role,
                        "name": name[:120],
                        "type": itype,
                        "href": href[:300],
                        "selector": selector_hint,
                    }
                )
            except Exception:
                continue
    except Exception:
        pass

    return {
        "url": url,
        "title": title,
        "text": text,
        "interactive": interactive,
        "interactive_count": len(interactive),
    }


def _selector_hint(el: Any, tag: str) -> str:
    eid = el.get_attribute("id")
    if eid:
        return f"#{eid}"
    name = el.get_attribute("name")
    if name:
        return f'{tag}[name="{name}"]'
    aria = el.get_attribute("aria-label")
    if aria:
        return f'[aria-label="{aria[:60]}"]'
    placeholder = el.get_attribute("placeholder")
    if placeholder:
        return f'[placeholder="{placeholder[:60]}"]'
    return tag
