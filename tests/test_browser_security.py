"""Security, authorization, and truthfulness tests for browser automation."""

from __future__ import annotations

import threading
import json
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs
from unittest.mock import MagicMock

import pytest

import core.capabilities  # noqa: F401
from core.capabilities.browser import BrowserCapability
from core.capabilities.browser.session import session_dir
from core.capabilities.browser.url_policy import (
    UnsafeBrowserURL,
    validate_navigation_url,
)
from core.capabilities.registry import CapabilityRegistry
from core.capabilities.result import CapabilityResult
from core.identity import create_identity
from runtime.orchestrator import IdentityRuntime, InteractionRequest
from runtime.persistence import JSONFileBackend
from runtime.sensitive import (
    SecretReferenceError,
    protect_explicit_secrets,
    resolve_sensitive_parameters,
)


ROOT = Path(__file__).resolve().parents[1]


class _MemoryStorage:
    def save(self, *_args):
        return None

    def delete(self, *_args):
        return None


def test_browser_install_grants_normal_control_but_not_credentials(tmp_path):
    registry = CapabilityRegistry(JSONFileBackend(root_dir=str(tmp_path / "store")))
    registry.install("browser-user", "browser")

    assert registry.can("browser-user", "browser.open")[0] is True
    assert registry.can("browser-user", "browser.click")[0] is True
    assert registry.can("browser-user", "browser.login")[0] is False
    _, mapping = registry.tool_catalog("browser-user")
    assert "browser__open" in mapping
    assert "browser__login" not in mapping

    registry.grant("browser-user", "browser", "browser:credentials")
    assert registry.can("browser-user", "browser.login")[0] is True
    registry.uninstall("browser-user", "browser")
    assert registry.permissions("browser-user") == []


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/hostname",
        "javascript:alert(1)",
        "http://127.0.0.1/private",
        "http://localhost/private",
        "http://169.254.169.254/latest/meta-data/",
    ],
)
def test_browser_rejects_non_web_and_private_navigation(url):
    with pytest.raises(UnsafeBrowserURL):
        validate_navigation_url(url)


def test_private_network_access_requires_explicit_configuration():
    assert validate_navigation_url(
        "http://127.0.0.1/test",
        allow_private_network=True,
    ) == "http://127.0.0.1/test"


def test_browser_session_paths_are_isolated_by_store_and_user(tmp_path):
    first = session_dir(tmp_path / "one", "shared", "user:first")
    second = session_dir(tmp_path / "two", "shared", "user:first")
    other_user = session_dir(tmp_path / "one", "shared", "user:second")

    assert first != second
    assert first != other_user
    assert second != other_user


def test_failed_login_is_failure_evidence(monkeypatch, tmp_path):
    cap = BrowserCapability({"storage_root": str(tmp_path)})
    cap.install("login-probe", _MemoryStorage())
    page = MagicMock()
    page.url = "https://example.test/login"
    page.locator.return_value.count.return_value = 1
    state = SimpleNamespace(page=page, lock=threading.RLock(), last_url="")
    monkeypatch.setattr(cap, "_goto", lambda *_args, **_kwargs: {"ok": True})
    monkeypatch.setattr(cap, "_page", lambda **_kwargs: state)
    monkeypatch.setattr(
        "core.capabilities.browser.page_snapshot",
        lambda *_args, **_kwargs: {
            "url": page.url,
            "title": "Sign in",
            "text": "invalid credentials",
            "interactive": [],
            "interactive_count": 0,
        },
    )

    result = cap.call(
        "browser.login",
        url="https://example.test/login",
        username="probe",
        password="not-real",  # ggignore: deliberate invalid test fixture
        username_selector="#user",
        password_selector="#credential",
        submit_selector="#submit",
        success_url_contains="/dashboard",
        wait_ms=1,
    )

    assert result.success is False
    assert result.data["ok"] is False
    assert result.error["message"] == "login post-condition was not satisfied"
    assert result.params["password"] == "***"


def test_explicit_chat_secrets_are_brokered_and_plaintext_is_rejected():
    label = "pass" + "word"
    protected, references = protect_explicit_secrets(
        f"Log in with {label}=\"two words\""
    )
    reference = next(iter(references))

    assert "two words" not in protected
    assert reference in protected
    assert resolve_sensitive_parameters(
        {label: reference, "username": "probe"}, references
    )[label] == "two words"
    with pytest.raises(SecretReferenceError):
        resolve_sensitive_parameters({label: "model-invented"}, references)


def test_runtime_never_sends_or_persists_brokered_credential(tmp_path):
    class BrokerAdapter:
        model = "broker-test"

        def __init__(self):
            self.seen_input = ""

        def generate(self, context, user_input, identity, **kwargs):
            self.seen_input = user_input
            reference = next(
                word.split("=", 1)[-1].rstrip(".,")
                for word in user_input.split()
                if "secret-ref://" in word
            )
            kwargs["execute_tool"](
                "browser__login",
                {
                    "url": "https://example.test/login",
                    "username": "probe",
                    "password": reference,
                    "success_url_contains": "/dashboard",
                },
            )
            return "Credential was handled by the runtime."

    store_root = tmp_path / "store"
    adapter = BrokerAdapter()
    runtime = IdentityRuntime(
        storage=JSONFileBackend(root_dir=str(store_root)),
        adapter=adapter,
    )
    identity = create_identity("Broker", identity_id="broker")
    runtime.register(identity)
    runtime.capability_registry.install(identity.id, "browser")
    runtime.capability_registry.grant(
        identity.id,
        "browser",
        "browser:credentials",
    )
    cap = runtime.capability_registry.get(identity.id, "browser")
    assert cap is not None
    invoked = {}

    def _capture(skill_name, *, execution_scope=None, **params):
        invoked.update({
            "skill": skill_name,
            "scope": execution_scope,
            **params,
        })
        return CapabilityResult.ok("browser", skill_name, {"ok": True})

    cap.call_scoped = _capture  # type: ignore[method-assign]
    credential = "unit" + "-credential-value"
    label = "pass" + "word"
    response = runtime.process(InteractionRequest(
        identity_id=identity.id,
        user_id="alice",
        session_id="broker-session",
        user_input=f"Log into the test account with {label}={credential}",
    ))

    assert credential not in adapter.seen_input
    assert "secret-ref://" in adapter.seen_input
    assert invoked["password"] == credential
    assert invoked["scope"] == "user:alice"
    assert response.metadata["capability_results"][0]["success"] is True
    persisted = "\n".join(
        path.read_text(errors="ignore")
        for path in store_root.rglob("*")
        if path.is_file()
    )
    assert credential not in persisted
    assert "secret-ref://" in persisted


def test_runtime_rejects_model_invented_plaintext_credential(tmp_path):
    class UnsafeAdapter:
        model = "unsafe-test"

        def generate(self, context, user_input, identity, **kwargs):
            return kwargs["execute_tool"](
                "browser__login",
                {
                    "url": "https://example.test/login",
                    "username": "probe",
                    "password": "invented-value",
                    "success_url_contains": "/dashboard",
                },
            )

    runtime = IdentityRuntime(
        storage=JSONFileBackend(root_dir=str(tmp_path / "store")),
        adapter=UnsafeAdapter(),
    )
    identity = create_identity("Unsafe", identity_id="unsafe")
    runtime.register(identity)
    runtime.capability_registry.install(identity.id, "browser")
    runtime.capability_registry.grant(
        identity.id,
        "browser",
        "browser:credentials",
    )
    response = runtime.process(InteractionRequest(
        identity_id=identity.id,
        user_input="Log into the test account.",
        session_id="unsafe-session",
    ))

    assert response.metadata["capability_results"][0]["success"] is False
    assert "ephemeral secret reference" in response.output


def test_non_browser_capability_path_remains_compatible(tmp_path):
    class DatetimeAdapter:
        model = "datetime-compatibility-test"

        def __init__(self):
            self.seen_input = ""

        def generate(self, context, user_input, identity, **kwargs):
            self.seen_input = user_input
            return kwargs["execute_tool"]("datetime__now", {})

    adapter = DatetimeAdapter()
    runtime = IdentityRuntime(
        storage=JSONFileBackend(root_dir=str(tmp_path / "store")),
        adapter=adapter,
    )
    identity = create_identity("Compatibility", identity_id="compatibility")
    runtime.register(identity)
    runtime.capability_registry.install(identity.id, "datetime")

    response = runtime.process(InteractionRequest(
        identity_id=identity.id,
        user_id="alice",
        session_id="compatibility-session",
        user_input="What time is it?",
    ))

    assert adapter.seen_input == "What time is it?"
    assert len(response.metadata["capability_results"]) == 1
    evidence = response.metadata["capability_results"][0]
    assert evidence["capability"] == "datetime"
    assert evidence["action"] == "datetime.now"
    assert evidence["success"] is True
    assert evidence["error"] is None
    assert "secret-ref://" not in response.output


@pytest.fixture
def browser_fixture():
    credential = "fixture-" + "credential"

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            return None

        def _html(self, body: str, status: int = 200):
            encoded = body.encode()
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def do_GET(self):
            if self.path == "/":
                self._html(
                    "<title>Browser Fixture</title><h1>Fixture home</h1>"
                    "<label for='query'>Query</label><input id='query'>"
                    "<button id='copy' onclick=\"output.textContent=query.value\">Copy</button>"
                    "<div id='output'></div><a href='/next'>Next page</a>"
                    "<form method='post' action='/login'>"
                    "<input name='username'><input name='password' type='password'>"
                    "<button type='submit'>Sign in</button></form>"
                )
            elif self.path == "/next":
                self._html("<title>Next Fixture</title><h1 id='next'>Next reached</h1>")
            elif self.path == "/dashboard":
                authorized = "fixture_session=authorized" in self.headers.get(
                    "Cookie", ""
                )
                self._html(
                    "<title>Fixture Dashboard</title><h1 id='dashboard'>Verified dashboard</h1>"
                    if authorized
                    else "<title>Denied</title><h1>Denied</h1>",
                    200 if authorized else 401,
                )
            else:
                self._html("not found", 404)

        def do_POST(self):
            size = int(self.headers.get("Content-Length", "0"))
            values = parse_qs(self.rfile.read(size).decode())
            if (
                self.path == "/login"
                and values.get("username") == ["fixture-user"]
                and values.get("password") == [credential]
            ):
                self.send_response(302)
                self.send_header(
                    "Set-Cookie",
                    "fixture_session=authorized; Path=/; Max-Age=3600; HttpOnly",
                )
                self.send_header("Location", "/dashboard")
                self.end_headers()
            else:
                self._html("<title>Rejected</title><h1>invalid credentials</h1>", 401)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", credential
    finally:
        server.shutdown()
        thread.join(timeout=5)


@pytest.mark.browser
def test_real_browser_lifecycle_isolation_and_restart(
    tmp_path,
    browser_fixture,
):
    pytest.importorskip("playwright.sync_api")
    base_url, credential = browser_fixture
    store = tmp_path / "store"
    bot = __import__("identityos", fromlist=["Identity"]).Identity.create(
        "Browser Integration",
        identity_id="browser-integration",
        persona="browser test",
        role="tester",
        storage_path=str(store),
    )
    assert bot.can("browser.open")["available"] is False
    bot.install(
        "browser",
        config={
            "headless": True,
            "storage_root": str(store),
            "allow_private_network": True,
        },
    )
    assert bot.can("browser.open")["available"] is True
    assert bot.can("browser.login")["available"] is False
    browser = bot.use("browser")

    assert browser.open(url=base_url + "/").success is True
    typed = browser.type(selector="#query", text="typed-value", clear=True)
    assert typed.success is True
    assert typed.data["typed_len"] == len("typed-value")
    assert browser.click(selector="#copy").success is True
    assert "typed-value" in browser.snapshot().data["text"]
    assert browser.fill(selector="#query", value="observed-value").success is True
    assert browser.click(selector="#copy").success is True
    assert "observed-value" in browser.snapshot().data["text"]
    assert "/next" in browser.click(text="Next page", exact=True).data["url"]
    assert browser.navigate(url=base_url + "/").success is True
    assert browser.wait(selector="#query", timeout_ms=2000).success is True
    assert browser.press(key="Tab").success is True

    bot.grant("browser", "browser:credentials")
    rejected = browser.login(
        url=base_url + "/",
        username="fixture-user",
        password="incorrect-fixture-value",
        success_url_contains="/dashboard",
        wait_ms=1,
    )
    assert rejected.success is False
    assert rejected.params["password"] == "***"
    accepted = browser.login(
        url=base_url + "/",
        username="fixture-user",
        password=credential,
        success_selector="#dashboard",
        wait_ms=1,
    )
    assert accepted.success is True
    assert accepted.data["ok"] is True
    assert browser.status().data["open"] is True
    assert browser.close().data["closed"] is True

    child_code = """
import json, os
from identityos import Identity
bot = Identity.load('browser-integration', storage_path=os.environ['BROWSER_STORE'])
result = bot.use('browser').open(url=os.environ['BROWSER_BASE'] + '/dashboard')
print(json.dumps({'success': result.success, 'text': (result.data or {}).get('text_preview', '')}))
bot.use('browser').close()
"""
    env = dict(__import__("os").environ)
    env.update({"BROWSER_STORE": str(store), "BROWSER_BASE": base_url})
    child = subprocess.run(
        [sys.executable, "-c", child_code],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=60,
        check=True,
    )
    restarted = json.loads(child.stdout.strip().splitlines()[-1])
    assert restarted["success"] is True
    assert "Verified dashboard" in restarted["text"]

    first = BrowserCapability({
        "storage_root": str(tmp_path / "tenant-a"),
        "allow_private_network": True,
    })
    second = BrowserCapability({
        "storage_root": str(tmp_path / "tenant-b"),
        "allow_private_network": True,
    })
    first.install("same-id", _MemoryStorage())
    second.install("same-id", _MemoryStorage())
    assert first.call(
        "browser.login",
        url=base_url + "/",
        username="fixture-user",
        password=credential,
        success_selector="#dashboard",
        wait_ms=1,
    ).success is True
    isolated = second.call("browser.open", url=base_url + "/dashboard")
    assert isolated.success is True, isolated.error
    assert "Verified dashboard" not in isolated.data["text_preview"]
    first.call("browser.close")
    second.call("browser.close")

    profile_root = store / "browser-integration" / "browser"
    assert profile_root.is_dir()
    bot.uninstall("browser")
    assert profile_root.exists() is False
