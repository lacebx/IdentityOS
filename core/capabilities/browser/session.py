"""Persistent Playwright browser sessions keyed by identity.

Playwright's sync API cannot run inside an asyncio event loop (common under
pytest-asyncio / FastAPI). All sync Playwright work is confined to a dedicated
daemon thread with its own event loop semantics.
"""

from __future__ import annotations

import atexit
import hashlib
import queue
import re
import threading
from contextvars import copy_context
from concurrent.futures import Future
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional, TypeVar

from .url_policy import allow_browser_request

T = TypeVar("T")


class BrowserUnavailable(RuntimeError):
    """Raised when Playwright / Chromium is not installed."""


@dataclass
class SessionState:
    session_key: str
    identity_id: str
    execution_scope: str = "sdk"
    headless: bool = True
    allow_private_network: bool = False
    user_data_dir: Optional[Path] = None
    playwright: Any = None
    browser: Any = None
    context: Any = None
    page: Any = None
    started: bool = False
    last_url: str = ""
    history: list[str] = field(default_factory=list)
    lock: threading.RLock = field(default_factory=threading.RLock)
    # Profile support
    browser_type: str = "chromium"  # chromium, firefox, webkit
    user_profile_dir: Optional[Path] = None  # Path to existing browser profile


_SESSIONS: dict[str, SessionState] = {}
_GLOBAL_LOCK = threading.RLock()
_PLAYWRIGHT: Any = None

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
    context = copy_context()
    _JOBS.put((lambda: context.run(fn), fut))
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


def _shared_playwright() -> Any:
    """Return the worker thread's single Playwright driver instance.

    The synchronous Playwright API owns an asyncio loop internally and cannot
    be started a second time on the same thread while another driver is live.
    Browser contexts remain independent; only the process-level driver is
    shared.
    """
    global _PLAYWRIGHT
    if _PLAYWRIGHT is None:
        _PLAYWRIGHT = _import_playwright()().start()
    return _PLAYWRIGHT


def _stop_shared_playwright() -> None:
    global _PLAYWRIGHT
    driver, _PLAYWRIGHT = _PLAYWRIGHT, None
    if driver is not None:
        try:
            driver.stop()
        except Exception:
            pass


def _safe_component(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip(".-")
    if cleaned and cleaned == value and value not in {".", ".."}:
        return cleaned
    digest = hashlib.sha256(value.encode()).hexdigest()[:16]
    return f"identity-{digest}"


def session_dir(
    storage_root: str | Path,
    identity_id: str,
    execution_scope: str = "sdk",
) -> Path:
    root = identity_browser_dir(storage_root, identity_id)
    if execution_scope and execution_scope != "sdk":
        scope_hash = hashlib.sha256(execution_scope.encode()).hexdigest()
        root = root / "scopes" / scope_hash
    root.mkdir(parents=True, exist_ok=True)
    try:
        root.chmod(0o700)
    except OSError:
        pass
    return root


def identity_browser_dir(storage_root: str | Path, identity_id: str) -> Path:
    """Return the bounded browser-state directory without creating it."""
    return Path(storage_root).resolve() / _safe_component(identity_id) / "browser"


def _session_key(
    storage_root: str | Path,
    identity_id: str,
    execution_scope: str,
    browser_type: str = "chromium",
    user_profile_dir: Optional[Path] = None,
) -> str:
    base = str(session_dir(storage_root, identity_id, execution_scope).resolve())
    if browser_type != "chromium":
        base = f"{base}-{browser_type}"
    if user_profile_dir:
        profile_hash = hashlib.sha256(str(user_profile_dir).encode()).hexdigest()[:8]
        base = f"{base}-profile-{profile_hash}"
    return base


def get_session(
    identity_id: str,
    *,
    storage_root: str | Path = ".identity_store",
    execution_scope: str = "sdk",
    browser_type: str = "chromium",
    user_profile_dir: Optional[Path] = None,
) -> Optional[SessionState]:
    key = _session_key(storage_root, identity_id, execution_scope, browser_type, user_profile_dir)
    with _GLOBAL_LOCK:
        state = _SESSIONS.get(key)
        if state and state.browser_type == browser_type and state.user_profile_dir == user_profile_dir:
            return state
        return None


def ensure_session(
    identity_id: str,
    *,
    storage_root: str | Path = ".identity_store",
    headless: bool = True,
    user_agent: Optional[str] = None,
    execution_scope: str = "sdk",
    allow_private_network: bool = False,
    browser_type: str = "chromium",
    user_profile_dir: Optional[Path] = None,
) -> SessionState:
    """Start or reuse a browser session for this identity."""

    def _ensure() -> SessionState:
        with _GLOBAL_LOCK:
            key = _session_key(storage_root, identity_id, execution_scope, browser_type, user_profile_dir)
            existing = _SESSIONS.get(key)
            if existing and existing.started and existing.page is not None:
                if (
                    existing.headless == headless
                    and existing.allow_private_network == allow_private_network
                    and existing.browser_type == browser_type
                    and existing.user_profile_dir == user_profile_dir
                ):
                    return existing
                _SESSIONS.pop(key, None)
                _safe_close(existing)

            state = SessionState(
                session_key=key,
                identity_id=identity_id,
                execution_scope=execution_scope,
                headless=headless,
                allow_private_network=allow_private_network,
                user_data_dir=session_dir(storage_root, identity_id, execution_scope),
                browser_type=browser_type,
                user_profile_dir=user_profile_dir,
            )
            state.playwright = _shared_playwright()
            try:
                # Determine user data directory
                if state.user_profile_dir and state.user_profile_dir.exists():
                    # Use existing browser profile
                    profile_dir = state.user_profile_dir
                    state.user_profile_dir.mkdir(parents=True, exist_ok=True)
                else:
                    # Use internal profile directory
                    profile_dir = state.user_data_dir / "profile"
                    profile_dir.mkdir(parents=True, exist_ok=True)

                # Select browser type
                browser_launcher = getattr(state.playwright, state.browser_type)
                if browser_launcher is None:
                    raise BrowserUnavailable(f"Browser type '{state.browser_type}' not available")

                # Prepare launch arguments
                launch_args = ["--disable-blink-features=AutomationControlled"]
                if state.browser_type == "chromium":
                    # Additional Chromium args
                    pass
                elif state.browser_type == "firefox":
                    # Firefox specific args
                    launch_args = ["-headless"] if headless else []
                elif state.browser_type == "webkit":
                    # WebKit specific args
                    pass

                # Launch persistent context
                state.context = browser_launcher.launch_persistent_context(
                    user_data_dir=str(profile_dir),
                    headless=headless,
                    viewport={"width": 1280, "height": 800},
                    locale="en-US",
                    user_agent=user_agent
                    or (
                        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                    ),
                    args=launch_args,
                )
                state.context.route(
                    "**/*",
                    lambda route: route.continue_()
                    if allow_browser_request(
                        route.request.url,
                        allow_private_network=allow_private_network,
                    )
                    else route.abort("blockedbyclient"),
                )
                state.page = state.context.pages[0] if state.context.pages else state.context.new_page()
                state.started = True
                _SESSIONS[key] = state
                return state
            except Exception:
                _safe_close(state)
                raise

    return run_in_browser_thread(_ensure)


def _safe_close(state: SessionState) -> None:
    with state.lock:
        for attr in ("context", "browser"):
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
        state.playwright = None
        state.page = None
        state.started = False


def close_session(
    identity_id: str,
    *,
    storage_root: str | Path = ".identity_store",
    execution_scope: str = "sdk",
    browser_type: str = "chromium",
    user_profile_dir: Optional[Path] = None,
) -> bool:
    def _close() -> bool:
        key = _session_key(storage_root, identity_id, execution_scope, browser_type, user_profile_dir)
        with _GLOBAL_LOCK:
            state = _SESSIONS.pop(key, None)
        if state is None:
            return False
        _safe_close(state)
        return True

    return run_in_browser_thread(_close)


def close_identity_sessions(
    identity_id: str,
    *,
    storage_root: str | Path = ".identity_store",
) -> int:
    """Close every in-process session for an identity in one storage root."""
    root = Path(storage_root).resolve()

    def _close_all_matching() -> int:
        with _GLOBAL_LOCK:
            matches = [
                (key, state)
                for key, state in _SESSIONS.items()
                if state.identity_id == identity_id
                and state.user_data_dir is not None
                and root in state.user_data_dir.resolve().parents
            ]
            for key, _ in matches:
                _SESSIONS.pop(key, None)
        for _, state in matches:
            _safe_close(state)
        return len(matches)

    return run_in_browser_thread(_close_all_matching)


def close_all() -> None:
    with _GLOBAL_LOCK:
        states = list(_SESSIONS.values())
        _SESSIONS.clear()
    for state in states:
        run_in_browser_thread(lambda state=state: _safe_close(state))
    run_in_browser_thread(_stop_shared_playwright)


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
