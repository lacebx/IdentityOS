"""Tests for the browser capability — search scoring + live browsing."""

from __future__ import annotations

import pytest

from core.capabilities.browser import BrowserCapability, _score_result
from core.capabilities.browser.session import close_session
from identityos import Identity


class _MemStorage:
    def __init__(self) -> None:
        self._data: dict = {}

    def save(self, identity_id: str, namespace: str, data) -> None:
        self._data[(identity_id, namespace)] = data

    def load(self, identity_id: str, namespace: str):
        return self._data.get((identity_id, namespace))

    def delete(self, identity_id: str, namespace: str) -> None:
        self._data.pop((identity_id, namespace), None)


def test_score_result_marks_relevant_hits_useful():
    judgment = _score_result(
        "find official playwright python docs for browser automation",
        "Playwright for Python",
        "Reliable end-to-end testing and browser automation for Python",
        "https://playwright.dev/python/docs/intro",
    )
    assert judgment["useful"] is True
    assert judgment["score"] >= 0.35
    assert "playwright" in judgment["matched_terms"]


def test_score_result_rejects_unrelated_hits():
    judgment = _score_result(
        "login to my github account settings",
        "Best pizza recipes 2024",
        "How to make dough at home",
        "https://example.com/pizza",
    )
    assert judgment["useful"] is False
    assert judgment["score"] < 0.35


def test_evaluate_results_recommends_urls():
    cap = BrowserCapability()
    cap.install("test-browser", _MemStorage())
    result = cap.call(
        "browser.evaluate_results",
        task="learn playwright browser automation python",
        results=[
            {
                "title": "Playwright Python docs",
                "url": "https://playwright.dev/python/",
                "snippet": "Browser automation library for Python",
            },
            {
                "title": "Cat videos",
                "url": "https://example.com/cats",
                "snippet": "Funny cats",
            },
        ],
    )
    assert result.success is True
    assert "playwright.dev" in result.data["recommended_urls"][0]
    assert result.data["useful_count"] >= 1


def test_password_redacted_in_login_params():
    cap = BrowserCapability()
    cap.install("test-browser-redact", _MemStorage())
    # Force failure path before network by using empty url handled as error
    result = cap.call(
        "browser.login",
        url="",
        username="user@example.com",
        password="super-secret",
    )
    assert result.success is False
    assert result.params.get("password") == "***"
    assert "super-secret" not in str(result.params)


def test_browser_listed_in_marketplace():
    from core.capabilities.registry import available

    assert "browser" in available()


@pytest.mark.network
def test_search_returns_scored_results():
    cap = BrowserCapability()
    cap.install("test-browser-search", _MemStorage())
    result = cap.call(
        "browser.search",
        query="IdentityOS portable AI identity",
        task="learn what IdentityOS is",
        max_results=5,
    )
    assert result.success is True, result.error
    assert result.data["result_count"] >= 1
    assert "results" in result.data
    assert "recommended" in result.data


@pytest.mark.network
def test_open_example_and_snapshot():
    identity_id = "test-browser-open"
    cap = BrowserCapability(config={"headless": True, "storage_root": ".identity_store"})
    storage = _MemStorage()
    cap.install(identity_id, storage)
    try:
        opened = cap.call("browser.open", url="https://example.com")
        assert opened.success is True, opened.error
        assert "Example Domain" in (opened.data.get("title") or "")
        snap = cap.call("browser.snapshot")
        assert snap.success is True, snap.error
        assert "example" in (snap.data.get("text") or "").lower()
        status = cap.call("browser.status")
        assert status.data.get("open") is True
    finally:
        cap.call("browser.close")
        close_session(identity_id)


@pytest.mark.network
def test_sdk_identity_can_use_browser(tmp_path):
    store = str(tmp_path / "store")
    bot = Identity.create(
        "CometTest",
        identity_id="comet-test",
        persona="web surfing agent",
        role="browser operator",
        storage_path=store,
    )
    bot.install("browser", config={"headless": True, "storage_root": store})
    result = bot.use("browser").open(url="https://example.com")
    assert result.success is True, result.error
    snap = bot.use("browser").snapshot()
    assert snap.success is True
    bot.use("browser").close()
