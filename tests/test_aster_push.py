"""Tests for first-party Web Push: Aster Control private iPhone PWA.

Deterministic only: mocked push transport proves the machinery, never real
iPhone delivery. The acceptance criterion (visible iPhone push confirmed by
Arsène) is a human step outside this file.
"""

from __future__ import annotations

import http.client
import json
import os
import threading
import urllib.request
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path

from core.operations import (
    ControlState,
    NotificationManager,
    NotifyImportance,
    NotifyKind,
    OperationsEngine,
    OperatorConfig,
    PresenceStore,
)
from core.operations.notify import reconcile
from runtime.persistence import InMemoryBackend, JSONFileBackend


# ── helpers ───────────────────────────────────────────────────────────────


def _engine(tmp_path, storage=None, *, secret_store=None):
    storage = storage or InMemoryBackend()
    root = tmp_path / "project"
    root.mkdir(exist_ok=True)
    (root / "README.md").write_text("# Sample Project\n", encoding="utf-8")
    config = OperatorConfig(
        identity_id="aster",
        project_root=str(root),
        project_name="IdentityOS",
        sender_name="Aster",
        purpose="IdentityOS outreach",
        need_rules=[],
        candidate_sources=[],
        required_skills=[],
    )
    presence = PresenceStore(storage, "aster", display_name="Aster")
    engine = OperationsEngine(storage, config, transport=None, adapter=None,
                              presence=presence, secret_store=secret_store)
    engine.store.set_controls(ControlState(outbound_mode="autonomous"))
    return engine


def _serve_once(presence):
    from runtime import health_server

    health_server._HealthHandler.presence_store = presence
    server = ThreadingHTTPServer(("127.0.0.1", 0), health_server._HealthHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, port


def _authed_env(monkeypatch, login="arsene@test.ts.net", host="idos.test.ts.net"):
    monkeypatch.setenv("ASTER_BUILDER_LOGIN", login)
    monkeypatch.setenv("ASTER_TAILNET_HOST", host)


def _authed_headers(*, login="arsene@test.ts.net", host="idos.test.ts.net", csrf=True):
    headers = {"Host": host, "Tailscale-User-Login": login}
    if csrf:
        headers["X-Requested-With"] = "AsterControl"
    return headers


def _request(port, method, path, body=None, *, headers=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=8)
    data = json.dumps(body).encode() if body is not None else None
    hdrs = dict(headers or {})
    host = hdrs.pop("Host", None)
    conn.putrequest(method, path, skip_host=bool(host))
    if host:
        conn.putheader("Host", host)
    if data is not None:
        conn.putheader("Content-Type", "application/json")
        conn.putheader("Content-Length", str(len(data)))
    for key, value in hdrs.items():
        conn.putheader(key, value)
    conn.endheaders(data)
    resp = conn.getresponse()
    raw = resp.read().decode()
    ctype = resp.headers.get("Content-Type", "")
    try:
        return resp.status, json.loads(raw), ctype
    except ValueError:
        return resp.status, {"raw": raw}, ctype


def _sub(endpoint="https://push.example.com/sub/abc123"):
    return {"endpoint": endpoint,
            "keys": {"p256dh": "p256dh-key-material", "auth": "auth-secret"}}


# ── manifest / service worker ─────────────────────────────────────────────


def test_manifest_valid_and_first_party(tmp_path):
    storage = InMemoryBackend()
    presence = PresenceStore(storage, "aster")
    presence.start_run(pid=os.getpid())
    server, port = _serve_once(presence)
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/manifest.json", timeout=8) as resp:
            assert resp.status == 200
            manifest = json.loads(resp.read().decode())
    finally:
        server.shutdown()
        server.server_close()
    assert manifest["name"] == "Aster"
    assert manifest["short_name"] == "Aster"
    assert manifest["display"] == "standalone"
    assert manifest["start_url"].startswith("/")
    assert manifest["scope"].startswith("/")
    assert manifest["theme_color"] and manifest["background_color"]
    for icon in manifest["icons"]:
        assert icon["src"].startswith("/"), "icons must be same-origin local assets"
        assert "http" not in icon["src"]


def test_service_worker_conservative(tmp_path):
    storage = InMemoryBackend()
    presence = PresenceStore(storage, "aster")
    server, port = _serve_once(presence)
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/sw.js", timeout=8) as resp:
            assert resp.status == 200
            assert "javascript" in resp.headers.get("Content-Type", "")
            body = resp.read().decode()
    finally:
        server.shutdown()
        server.server_close()
    assert "push" in body and "notificationclick" in body
    assert "showNotification" in body and "deep_link" in body
    assert "skipWaiting" in body  # present only as do-NOT documentation
    assert "clients.openWindow" in body or "openWindow" in body


# ── subscription lifecycle ────────────────────────────────────────────────


def test_subscribe_register_persist_replace_delete(tmp_path, monkeypatch):
    storage = InMemoryBackend()
    presence = PresenceStore(storage, "aster")
    presence.start_run(pid=os.getpid())
    _authed_env(monkeypatch)
    server, port = _serve_once(presence)
    try:
        code, payload, _ = _request(port, "POST", "/api/push/subscribe",
                                    {"subscription": _sub(), "device_label": "iPhone"},
                                    headers=_authed_headers())
        assert code == 201, payload
        assert payload["verified"] is True
        # Invalid shape rejected.
        code, _, _ = _request(port, "POST", "/api/push/subscribe",
                              {"subscription": {"endpoint": "http://insecure/x"}},
                              headers=_authed_headers())
        assert code == 400
        # Same endpoint re-registers (replace, not duplicate).
        code, _, _ = _request(port, "POST", "/api/push/subscribe",
                              {"subscription": _sub()}, headers=_authed_headers())
        assert code == 201
        manager = NotificationManager(storage, "aster")
        assert len(manager._load_subs()) == 1
        # Persistence across backend reload.
        manager2 = NotificationManager(storage, "aster")
        assert len(manager2.valid_subscriptions()) == 1
        # Deletion.
        code, payload, _ = _request(port, "POST", "/api/push/unsubscribe",
                                    {"endpoint": _sub()["endpoint"]},
                                    headers=_authed_headers())
        assert code == 200 and payload["removed"] is True
        assert manager.valid_subscriptions() == []
    finally:
        server.shutdown()
        server.server_close()


def test_subscribe_auth_and_csrf(tmp_path, monkeypatch):
    storage = InMemoryBackend()
    presence = PresenceStore(storage, "aster")
    presence.start_run(pid=os.getpid())
    _authed_env(monkeypatch)
    server, port = _serve_once(presence)
    try:
        code, _, _ = _request(port, "POST", "/api/push/subscribe",
                              {"subscription": _sub()},
                              headers=_authed_headers(login="mallory@evil.ts.net"))
        assert code == 403
        code, _, _ = _request(port, "POST", "/api/push/subscribe",
                              {"subscription": _sub()},
                              headers=_authed_headers(host="127.0.0.1"))
        assert code == 403
        code, _, _ = _request(port, "POST", "/api/push/subscribe",
                              {"subscription": _sub()},
                              headers=_authed_headers(csrf=False))
        assert code == 403
    finally:
        server.shutdown()
        server.server_close()


def test_stale_and_failing_subscriptions_excluded(tmp_path):
    manager = NotificationManager(InMemoryBackend(), "aster")
    manager.register_subscription(_sub("https://push.example.com/a"),
                                  principal_login="x", device_label="a")
    manager.register_subscription(_sub("https://push.example.com/b"),
                                  principal_login="x", device_label="b")
    assert len(manager.valid_subscriptions()) == 2
    manager.mark_push_result("https://push.example.com/a", False, expired=True)
    assert [s["endpoint"] for s in manager.valid_subscriptions()] == ["https://push.example.com/b"]
    for _ in range(3):
        manager.mark_push_result("https://push.example.com/b", False, detail="500")
    assert manager.valid_subscriptions() == []


# ── semantic events, policy, dedup, badge ─────────────────────────────────


def test_semantic_creation_dedup_and_policy(tmp_path):
    manager = NotificationManager(InMemoryBackend(), "aster")
    first = manager.create_event(NotifyKind.TEST, title="Aster", body="one",
                                 dedup_key="k1", requires_attention=True)
    again = manager.create_event(NotifyKind.TEST, title="Aster", body="two", dedup_key="k1")
    assert first.id == again.id
    assert len(manager.list_events()) == 1
    assert manager.policy_allows(NotifyKind.SECURITY_ALERT)
    assert manager.policy_allows("heartbeat_spam") is False
    assert manager.check_silent("heartbeat") is True
    assert manager.check_silent("tick") is True
    assert manager.check_silent("principal_decision_required") is False


def test_badge_counts_attention_and_clears(tmp_path):
    from core.operations.store import OperationsStore

    storage = InMemoryBackend()
    store = OperationsStore(storage, "aster")
    manager = NotificationManager(storage, "aster")
    assert manager.attention_count(store) == 0
    event = manager.create_event(NotifyKind.SECURITY_ALERT, title="Alert",
                                 requires_attention=True, dedup_key="s1")
    assert manager.attention_count(store) == 1
    manager.mark_read(event.id)
    assert manager.attention_count(store) == 1, "read is not resolved"
    manager.resolve(event.id, "handled")
    assert manager.attention_count(store) == 0


def test_deep_links_safe_and_stable(tmp_path):
    manager = NotificationManager(InMemoryBackend(), "aster")
    defaulted = manager.create_event(NotifyKind.TEST, title="t", deep_link="https://evil.example/x")
    assert defaulted.deep_link == "/status#/notifications"
    custom = manager.create_event(NotifyKind.EXTERNAL_REPLY, title="t",
                                  deep_link="/status#/messages", dedup_key="dl")
    assert custom.deep_link == "/status#/messages"


def test_payload_minimization(tmp_path):
    manager = NotificationManager(InMemoryBackend(), "aster")
    sneaky = manager.create_event(
        NotifyKind.SECURITY_ALERT, title="Aster",
        body="Rotate password hunter2 and api_key ABC123 now at https://ntfy.sh/secret-topic")
    payload = manager.push_payload(sneaky, badge=2)
    assert set(payload) == {"title", "body", "tag", "deep_link", "kind", "badge"}
    blob = json.dumps(payload)
    for forbidden in ("hunter2", "ABC123", "secret-topic", "password"):
        assert forbidden not in blob
    assert payload["badge"] == 2
    assert payload["tag"] == sneaky.id


# ── mocked transport outcomes ─────────────────────────────────────────────


def _vapid_env(tmp_path, monkeypatch):
    monkeypatch.setenv("IDENTITY_SECRET_STORE_DIR", str(tmp_path / "secrets"))


def test_push_submitted_mocked_and_recorded(tmp_path, monkeypatch):
    from core.secrets.store import SecretStore, default_secret_store_dir

    _vapid_env(tmp_path, monkeypatch)
    manager = NotificationManager(InMemoryBackend(), "aster")
    event = manager.create_event(NotifyKind.TEST, title="Aster", body="ok", dedup_key="m1")
    calls = []

    def fake_sender(subscription_info, data, **kwargs):
        calls.append((subscription_info["endpoint"], json.loads(data)["title"]))
        assert "vapid_private_key" in kwargs and "vapid_claims" in kwargs
        return True

    manager.register_subscription(_sub(), principal_login="x")
    secrets = SecretStore(default_secret_store_dir())
    outcome = manager.send_first_party(event, secret_store=secrets, badge=1, sender=fake_sender)
    assert outcome["result"] == "submitted" and outcome["accepted"] == 1
    assert len(calls) == 1
    stored = manager.get_event(event.id)
    assert any(c["channel"] == "webpush" and c["result"] == "submitted" for c in stored.channels)


def test_push_rejected_and_expired_mocked(tmp_path, monkeypatch):
    from core.secrets.store import SecretStore, default_secret_store_dir

    _vapid_env(tmp_path, monkeypatch)
    manager = NotificationManager(InMemoryBackend(), "aster")
    event = manager.create_event(NotifyKind.TEST, title="Aster", body="ok", dedup_key="m2")
    manager.register_subscription(_sub("https://push.example.com/gone"), principal_login="x")

    class Gone(Exception):
        def __init__(self):
            self.response = type("R", (), {"status_code": 410})()

    def gone_sender(*args, **kwargs):
        raise Gone()

    secrets = SecretStore(default_secret_store_dir())
    outcome = manager.send_first_party(event, secret_store=secrets, sender=gone_sender)
    assert outcome["result"] == "expired"
    assert manager.valid_subscriptions() == [], "expired endpoint must be retired, not hammered"


def test_ntfy_only_as_explicit_fallback(tmp_path, monkeypatch):
    from core.secrets.store import SecretStore, default_secret_store_dir

    _vapid_env(tmp_path, monkeypatch)
    manager = NotificationManager(InMemoryBackend(), "aster")
    event = manager.create_event(NotifyKind.TEST, title="Aster", body="ok", dedup_key="m3")
    manager.register_subscription(_sub(), principal_login="x")
    secrets = SecretStore(default_secret_store_dir())
    ntfy_calls = []

    class Result:
        success = True
        data = {"ntfy_id": "abc"}
        error = None

    def ok_push(*args, **kwargs):
        return True

    def ntfy_probe(*args, **kwargs):
        ntfy_calls.append(args)
        return Result()

    outcome = manager.send_first_party(event, secret_store=secrets, sender=ok_push)
    assert outcome["result"] == "submitted"
    assert ntfy_calls == [], "no duplicate ntfy when first-party succeeds"

    event2 = manager.create_event(NotifyKind.SECURITY_ALERT, title="Aster", body="bad",
                                  importance=NotifyImportance.HIGH, dedup_key="m4")
    outcome2 = manager.send_ntfy_fallback(event2, registry=None, sender=ntfy_probe)
    assert outcome2["result"] == "submitted"
    assert len(ntfy_calls) == 1
    channels = [c["channel"] for c in manager.get_event(event2.id).channels]
    assert "ntfy" in channels


# ── notification center API ───────────────────────────────────────────────


def test_notify_center_and_test_single_flight(tmp_path, monkeypatch):
    from core.secrets.store import SecretStore, default_secret_store_dir

    storage = InMemoryBackend()
    presence = PresenceStore(storage, "aster", display_name="Aster")
    presence.start_run(pid=os.getpid())
    _authed_env(monkeypatch)
    _vapid_env(tmp_path, monkeypatch)
    server, port = _serve_once(presence)
    try:
        # No subscriptions: first-party reports no_subscription, no ntfy sent.
        code, payload, _ = _request(port, "POST", "/api/notify/test", {},
                                    headers=_authed_headers())
        assert code == 502, payload
        assert payload["result"] == "no_subscription"
        first_id = payload["id"]
        # Single-flight: second call returns the same unresolved TEST.
        code, payload2, _ = _request(port, "POST", "/api/notify/test", {},
                                     headers=_authed_headers())
        assert payload2["id"] == first_id
        manager = NotificationManager(storage, "aster")
        assert len(manager.list_events()) == 1
        # Center lists it with badge.
        code, center, _ = _request(port, "GET", "/api/notify", headers=_authed_headers())
        assert code == 200
        assert center["badge"] >= 1
        assert any(n["id"] == first_id for n in center["notifications"])
        # Read + confirm Mark principal-confirmed.
        code, _, _ = _request(port, "POST", "/api/notify/read", {"id": first_id},
                              headers=_authed_headers())
        assert code == 200
        code, payload, _ = _request(port, "POST", "/api/notify/confirm", {"id": first_id},
                                    headers=_authed_headers())
        assert code == 200 and payload["confirmed"] is True
        assert manager.get_event(first_id).principal_confirmed_visible is True
    finally:
        server.shutdown()
        server.server_close()


# ── reconcile: real sources, no spam ──────────────────────────────────────


def test_reconcile_creates_decision_event_once(tmp_path):
    from core.operations.store import OperationsStore

    storage = InMemoryBackend()
    store = OperationsStore(storage, "aster")
    engine = _engine(tmp_path, storage=storage)
    engine._notify(kind="escalation", summary="outreach requires human authorization",
                   refs={"message_id": "msg-1"})
    first = reconcile(engine)
    assert len(first["created"]) == 1
    second = reconcile(engine)
    assert second["created"] == [], "same unread escalation must not respawn"
    manager = NotificationManager(storage, "aster")
    assert manager.attention_count(store) >= 1


def test_reconcile_skips_test_autosend(tmp_path):
    storage = InMemoryBackend()
    engine = _engine(tmp_path, storage=storage)
    manager = NotificationManager(storage, "aster")
    manager.create_event(NotifyKind.TEST, title="Aster", body="t", dedup_key="acceptance:test-push",
                         requires_attention=True)
    result = reconcile(engine)
    assert result["created"] == []
    assert result["sent"] == []


# ── restart persistence ───────────────────────────────────────────────────


def test_notify_history_and_subs_survive_restart(tmp_path):
    store_dir = str(tmp_path / "store")
    storage = JSONFileBackend(root_dir=store_dir)
    manager = NotificationManager(storage, "aster")
    event = manager.create_event(NotifyKind.TEST, title="Aster", body="persist me",
                                 dedup_key="r1", requires_attention=True)
    manager.register_subscription(_sub(), principal_login="x")
    reloaded = NotificationManager(JSONFileBackend(root_dir=store_dir), "aster")
    assert reloaded.get_event(event.id).title == "Aster"
    assert len(reloaded.valid_subscriptions()) == 1


# ── SSE + offline + zero model calls ──────────────────────────────────────


def test_sse_streams_state_and_reconnects(tmp_path):
    storage = InMemoryBackend()
    presence = PresenceStore(storage, "aster", display_name="Aster")
    presence.start_run(pid=os.getpid())
    presence.heartbeat()
    server, port = _serve_once(presence)
    try:
        import socket

        for _ in range(2):  # connect, read one frame, drop, reconnect
            sock = socket.create_connection(("127.0.0.1", port), timeout=10)
            sock.sendall(b"GET /api/events HTTP/1.0\r\nHost: x\r\n\r\n")
            sock.settimeout(10)
            chunks = b""
            while b"\n\n" not in chunks:
                part = sock.recv(4096)
                if not part:
                    break
                chunks += part
            text = chunks.decode()
            assert "text/event-stream" in text
            assert "event: state" in text
            frame = json.loads(text.split("data: ", 1)[1].split("\n")[0])
            assert {"presence", "messages", "badge"} <= set(frame)
            sock.close()
    finally:
        server.shutdown()
        server.server_close()


def test_new_endpoints_zero_model_calls_and_clean(tmp_path, monkeypatch):
    import sys
    import urllib.request

    storage = InMemoryBackend()
    presence = PresenceStore(storage, "aster", display_name="Aster")
    presence.start_run(pid=os.getpid())
    presence.heartbeat()
    monkeypatch.setitem(sys.modules, "adapters.configuration", None)
    for mod in [m for m in list(sys.modules) if m.startswith("adapters.")]:
        monkeypatch.delitem(sys.modules, mod, raising=False)
    server, port = _serve_once(presence)
    bodies = []
    try:
        for path in ("/api/notify", "/api/push/status", "/api/push/public-key",
                     "/manifest.json", "/icon.svg", "/sw.js", "/status"):
            with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=8) as resp:
                assert resp.status == 200, path
                bodies.append(resp.read().decode())
    finally:
        server.shutdown()
        server.server_close()
    blob = "\n".join(bodies)
    for forbidden in ("ntfy_topic", "phone_number", "api_key", "password", "credential"):
        assert forbidden not in blob
    assert "BEGIN PRIVATE KEY" not in blob, "VAPID private must never be served"


def test_offline_shell_markers(tmp_path):
    storage = InMemoryBackend()
    presence = PresenceStore(storage, "aster", display_name="Aster")
    server, port = _serve_once(presence)
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/status", timeout=8) as resp:
            body = resp.read().decode()
    finally:
        server.shutdown()
        server.server_close()
    assert "cannot currently reach IdentityOS" in body
    assert "LAST UPDATED" in body or "Last updated" in body
    assert "prefers-reduced-motion" in body
    assert "safe-area-inset" in body
