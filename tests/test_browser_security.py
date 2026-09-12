"""Security, authorization, and truthfulness tests for browser automation."""

from __future__ import annotations

import threading
from types import SimpleNamespace
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
