"""Tests for operator live presence (core/operations/presence.py).

Presence must describe REAL runtime state, never generated status theater.
Every test below exercises actual execution against real storage backends.
"""

from __future__ import annotations

import json
import os
import subprocess
import threading
import urllib.request
from datetime import datetime, timedelta, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path

from core.capabilities.email.backends import FileMailboxBackend, MailboxTransport
from core.operations import (
    Candidate,
    ControlState,
    OperationsEngine,
    OperatorConfig,
    PresenceStatus,
    PresenceStore,
    RequirementRule,
    StaticCandidateSource,
)
from core.operations.presence import format_presence_card
from runtime.persistence import InMemoryBackend, JSONFileBackend


# ── helpers ───────────────────────────────────────────────────────────────


def _project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    root.mkdir(exist_ok=True)
    (root / "README.md").write_text(
        "# Sample Project\n\nA small experiment in distributed systems.\n", encoding="utf-8"
    )
    (root / "pyproject.toml").write_text(
        '[project]\nname = "sample"\nversion = "0.1.0"\n', encoding="utf-8"
    )
    return root


def _candidate(**overrides):
    base = dict(
        target_name="Alice Example",
        organization="Example Foundation",
        contact_email="alice@example.org",
        category="funding",
        relevant_work=["distributed identity systems research"],
        evidence=["directory:example-fund"],
        fit_reason="works on distributed identity systems research",
        value_proposition="an open identity runtime with durable state",
        potential_ask="a short conversation about your program",
        confidence=0.5,
    )
    base.update(overrides)
    return Candidate(**base)


class _CountingAdapter:
    """Adapter that counts model calls; generate() falls back to template."""

    def __init__(self):
        self.generate_calls = 0

    def generate(self, context: str, user_input: str, identity, **kwargs):
        self.generate_calls += 1
        return None


def _engine(tmp_path, storage=None, *, controls=None, candidate=None,
            required_skills=None, adapter=None, transport=None, presence=None):
    storage = storage or InMemoryBackend()
    backend = FileMailboxBackend(tmp_path / "mailbox", mailbox="aster")
    transport = transport if transport is not None else MailboxTransport(backend)
    config = OperatorConfig(
        identity_id="aster",
        project_root=str(_project(tmp_path)),
        project_name="IdentityOS",
        sender_name="Aster",
        sender_email="aster@identityos.local",
        signature="— Aster",
        transparency="I am an AI operator.",
        purpose="IdentityOS outreach",
        need_rules=[
            RequirementRule(
                category="funding",
                description="Secure funding or sponsorship to sustain the project",
                probe=r"\b(fund|grant|sponsor|invest)\b",
                expect="absent",
                urgency=0.8,
                impact=0.9,
            ),
        ],
        candidate_sources=[StaticCandidateSource([candidate or _candidate()])],
        required_skills=[] if required_skills is None else required_skills,
        pursue_threshold=0.45,
        hold_threshold=0.3,
    )
    if presence is None:
        presence = PresenceStore(storage, "aster", display_name="Aster", objective=config.purpose)
    engine = OperationsEngine(
        storage, config, transport=transport,
        adapter=_CountingAdapter() if adapter is None else adapter,
        presence=presence,
    )
    controls = ControlState(outbound_mode="autonomous") if controls is None else controls
    engine.store.set_controls(controls)
    return engine, backend, presence


def _dead_pid() -> int:
    proc = subprocess.Popen(["true"])
    proc.wait()
    return proc.pid


def _age(record: dict, field: str) -> float:
    ts = datetime.fromisoformat(record[field])
    return (datetime.now(timezone.utc) - ts).total_seconds()


# ── lifecycle: running service → ONLINE ────────────────────────────────────


def test_running_service_is_online(tmp_path):
    engine, _, presence = _engine(tmp_path)
    presence.start_run(pid=os.getpid())
    engine.tick()
    presence.heartbeat()
    view = presence.public_view()
    assert view["health"] == "online"
    assert view["identity_id"] == "aster"
    assert view["heartbeat_age_seconds"] is not None
    assert view["heartbeat_age_seconds"] < 60


def test_heartbeat_updates_without_model_call(tmp_path):
    engine, _, presence = _engine(tmp_path)
    adapter = engine._adapter
    before = adapter.generate_calls
    presence.start_run(pid=os.getpid())
    presence.heartbeat()
    presence.heartbeat(phase="idle")
    assert adapter.generate_calls == before, "heartbeat must never invoke the model"
    assert presence.record()["last_heartbeat"] is not None


# ── lifecycle: observation → OBSERVING ─────────────────────────────────────


def test_observation_transition(tmp_path):
    engine, _, presence = _engine(tmp_path)
    presence.start_run(pid=os.getpid())
    captured = {}

    original_observe = engine.observer.observe

    def spy_observe():
        captured["status"] = (presence.record() or {}).get("status")
        captured["activity"] = (presence.record() or {}).get("activity")
        return original_observe()

    engine.observer.observe = spy_observe
    engine.tick()
    assert captured["status"] == PresenceStatus.OBSERVING.value
    assert captured["activity"], "activity must be human-readable"


# ── lifecycle: reasoning → THINKING ────────────────────────────────────────


def test_thinking_transition(tmp_path):
    engine, _, presence = _engine(tmp_path)
    presence.start_run(pid=os.getpid())
    captured = {}

    original_detect = engine.detector.detect

    def spy_detect(store, state):
        captured["status"] = (presence.record() or {}).get("status")
        return original_detect(store, state)

    engine.detector.detect = spy_detect
    engine.tick()
    assert captured["status"] == PresenceStatus.THINKING.value


# ── lifecycle: action → ACTING ─────────────────────────────────────────────


def test_acting_transition_and_meaningful_action(tmp_path):
    engine, backend, presence = _engine(tmp_path)
    presence.start_run(pid=os.getpid())
    captured = {}

    transport = engine._transport
    original_send = transport.send

    def spy_send(**kwargs):
        captured["status"] = (presence.record() or {}).get("status")
        return original_send(**kwargs)

    transport.send = spy_send
    report = engine.tick()
    assert report.outreach_sent, "outreach must actually be sent for this test"
    assert captured["status"] == PresenceStatus.ACTING.value
    record = presence.record()
    assert "Alice Example" in (record.get("last_meaningful_action") or "")


# ── lifecycle: blocked → WAITING (budget) ──────────────────────────────────


def test_budget_blocked_is_waiting(tmp_path):
    engine, _, presence = _engine(tmp_path)
    presence.start_run(pid=os.getpid())
    controls = ControlState(outbound_mode="autonomous")
    controls.max_cold_outreach_per_day = 0
    engine.store.set_controls(controls)
    report = engine.tick()
    assert any(s.get("reason") == "daily_budget_exhausted" for s in report.skipped)
    record = presence.record()
    assert record["status"] == PresenceStatus.WAITING.value
    assert "budget" in (record.get("activity") or "").lower()


# ── lifecycle: blocked → WAITING (escalation) ──────────────────────────────


def test_escalation_is_waiting(tmp_path):
    engine, _, presence = _engine(
        tmp_path, controls=ControlState(outbound_mode="approval_required")
    )
    presence.start_run(pid=os.getpid())
    report = engine.tick()
    assert report.escalations, "approval_required must escalate for this test"
    record = presence.record()
    assert record["status"] == PresenceStatus.WAITING.value
    view = presence.public_view()
    assert view["status"] == "waiting"


# ── lifecycle: subsystem failure → DEGRADED ────────────────────────────────


class _FailTransport:
    def send(self, **kwargs):
        return {"ok": False, "error": "simulated send failure"}


def test_send_failure_is_degraded(tmp_path):
    engine, _, presence = _engine(tmp_path, transport=_FailTransport())
    presence.start_run(pid=os.getpid())
    report = engine.tick()
    assert report.errors, "send failure must surface in the tick report"
    view = presence.public_view()
    assert view["health"] == "degraded"
    assert view["status"] == "degraded"


def test_unresolved_capability_gap_is_degraded(tmp_path):
    engine, _, presence = _engine(tmp_path, required_skills=["nonexistent.skill.xyz"])
    presence.start_run(pid=os.getpid())
    report = engine.tick()
    assert report.capability_gaps, "the missing skill must be detected as a gap"
    assert not any(g.get("resolved") for g in report.capability_gaps)
    view = presence.public_view()
    assert view["health"] == "degraded"
    assert any("capabilit" in r for r in view["health_reasons"])


# ── lifecycle: stale heartbeat / dead process → OFFLINE ────────────────────


def test_stale_heartbeat_is_offline(tmp_path):
    storage = InMemoryBackend()
    presence = PresenceStore(storage, "aster")
    presence.start_run(pid=os.getpid())
    raw = storage.load("aster", "operations.presence")
    raw["last_heartbeat"] = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    storage.save("aster", "operations.presence", raw)
    view = presence.public_view()
    assert view["health"] == "offline"
    assert view["status"] == "offline"
    assert any("stale" in r for r in view["health_reasons"])


def test_dead_process_is_offline(tmp_path):
    storage = InMemoryBackend()
    presence = PresenceStore(storage, "aster")
    dead = _dead_pid()
    presence.start_run(pid=dead)
    view = presence.public_view()
    assert view["health"] == "offline"
    assert any("not running" in r for r in view["health_reasons"])


def test_no_record_is_offline(tmp_path):
    presence = PresenceStore(InMemoryBackend(), "aster")
    view = presence.public_view()
    assert view["health"] == "offline"
    assert view["status"] == "offline"


def test_stopped_service_is_offline(tmp_path):
    storage = InMemoryBackend()
    presence = PresenceStore(storage, "aster")
    presence.start_run(pid=os.getpid())
    presence.mark_offline(reason="operator stopped for test")
    raw = storage.load("aster", "operations.presence")
    raw["operator_pid"] = _dead_pid()
    storage.save("aster", "operations.presence", raw)
    view = presence.public_view()
    assert view["health"] == "offline"


# ── lifecycle: restart survival ────────────────────────────────────────────


def test_restart_preserves_history_with_fresh_heartbeat(tmp_path):
    storage = InMemoryBackend()
    first = PresenceStore(storage, "aster", display_name="Aster")
    first.start_run(pid=os.getpid())
    first.heartbeat()
    first.mark_meaningful_action("Did a real thing before restart")
    first_hb = first.record()["last_heartbeat"]

    second = PresenceStore(storage, "aster", display_name="Aster")
    second.start_run(pid=os.getpid())
    record = second.record()
    assert record["identity_id"] == "aster"
    assert record["restart_count"] == 2
    assert record["previous_heartbeat"] == first_hb
    assert record["last_meaningful_action"] == "Did a real thing before restart"
    assert _age(record, "last_heartbeat") < 60
    view = second.public_view()
    assert view["health"] == "online"


def test_atomic_persistence_survives_store_reload(tmp_path):
    store_dir = str(tmp_path / "store")
    storage = JSONFileBackend(root_dir=store_dir)
    presence = PresenceStore(storage, "aster", display_name="Aster")
    presence.start_run(pid=os.getpid())
    presence.heartbeat()
    presence.mark_meaningful_action("Survives restart")

    reloaded = PresenceStore(JSONFileBackend(root_dir=store_dir), "aster")
    record = reloaded.record()
    assert record is not None
    assert record["last_meaningful_action"] == "Survives restart"

    from hashlib import sha256

    identity_dir = Path(store_dir) / f"identity-{sha256(b'aster').hexdigest()}"
    files = list(identity_dir.glob("*.json"))
    assert files, "presence must be persisted to disk"
    for path in files:
        json.loads(path.read_text(encoding="utf-8"))


# ── lifecycle: paused ──────────────────────────────────────────────────────


def test_paused_operator_records_paused(tmp_path):
    engine, _, presence = _engine(tmp_path)
    presence.start_run(pid=os.getpid())
    engine.pause(note="test pause")
    report = engine.tick()
    assert report.skipped, "paused tick must skip"
    record = presence.record()
    assert record["status"] == PresenceStatus.PAUSED.value


# ── sanitization: no secrets in the record ─────────────────────────────────


def test_no_secrets_in_presence_record(tmp_path):
    storage = InMemoryBackend()

    def scrub(text: str) -> str:
        return text.replace("SECRET-TOKEN-123", "[redacted]")

    presence = PresenceStore(storage, "aster", scrub_fn=scrub)
    presence.start_run(pid=os.getpid())
    presence.set_status(
        PresenceStatus.OBSERVING,
        activity="Observing with SECRET-TOKEN-123 in text",
    )
    record = presence.record()
    blob = json.dumps(record)
    assert "SECRET-TOKEN-123" not in blob
    for forbidden in ("ntfy_topic", "phone_number", "api_key", "password", "credential"):
        assert forbidden not in blob


# ── CLI: zero model calls ──────────────────────────────────────────────────


def test_status_command_performs_zero_model_calls(tmp_path, capsys, monkeypatch):
    from cli import aster_cmds

    store_dir = str(tmp_path / "store")
    storage = JSONFileBackend(root_dir=store_dir)
    presence = PresenceStore(storage, "aster", display_name="Aster")
    presence.start_run(pid=os.getpid())
    presence.heartbeat()

    adapter_holder = {}
    real_builder = aster_cmds._build_engine

    def counting_build(args):
        eng = real_builder(args)
        adapter = getattr(eng, "_adapter", None)
        if adapter is not None and hasattr(adapter, "generate"):
            original = adapter.generate

            def counting_generate(*a, **k):
                adapter_holder["calls"] = adapter_holder.get("calls", 0) + 1
                return original(*a, **k)

            adapter.generate = counting_generate
        return eng

    monkeypatch.setattr(aster_cmds, "_build_engine", counting_build)

    import argparse

    args = argparse.Namespace(
        store=store_dir,
        backend="json",
        project_root=".",
        mailbox_root=None,
        json=False,
    )
    rc = aster_cmds.cmd_aster_status(args)
    assert rc == 0
    assert adapter_holder.get("calls", 0) == 0, "status must not invoke the model"
    out = capsys.readouterr().out
    assert "Aster" in out
    assert "heartbeat" in out.lower()


def test_status_json_output_is_machine_readable(tmp_path, capsys):
    from cli import aster_cmds
    import argparse

    store_dir = str(tmp_path / "store")
    args = argparse.Namespace(
        store=store_dir,
        backend="json",
        project_root=".",
        mailbox_root=None,
        json=True,
    )
    rc = aster_cmds.cmd_aster_status(args)
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert "presence" in payload
    assert payload["presence"]["health"] in ("online", "degraded", "offline")


# ── health endpoint: zero model calls ──────────────────────────────────────


def _serve_once(presence):
    from runtime import health_server

    health_server._HealthHandler.presence_store = presence
    server = ThreadingHTTPServer(("127.0.0.1", 0), health_server._HealthHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, port


def test_health_endpoint_no_model_calls(tmp_path, monkeypatch):
    import sys

    storage = InMemoryBackend()
    presence = PresenceStore(storage, "aster", display_name="Aster")
    presence.start_run(pid=os.getpid())
    presence.heartbeat()

    monkeypatch.setitem(sys.modules, "adapters.configuration", None)

    server, port = _serve_once(presence)
    try:
        for path in ("/health", "/status"):
            with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=5) as resp:
                assert resp.status == 200
                payload = json.loads(resp.read().decode())
                assert payload["identity_id"] == "aster"
                assert payload["health"] in ("online", "degraded", "offline")
                assert "last_heartbeat" in payload
    finally:
        server.shutdown()
        server.server_close()


def test_health_endpoint_unknown_path_404(tmp_path):
    storage = InMemoryBackend()
    presence = PresenceStore(storage, "aster")
    server, port = _serve_once(presence)
    try:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/nope", timeout=5)
            raise AssertionError("expected HTTP 404")
        except urllib.request.HTTPError as exc:
            assert exc.code == 404
    finally:
        server.shutdown()
        server.server_close()


# ── card rendering ─────────────────────────────────────────────────────────


def test_card_reflects_real_state(tmp_path):
    storage = InMemoryBackend()
    presence = PresenceStore(
        storage, "aster", display_name="Aster", objective="IdentityOS outreach"
    )
    presence.start_run(pid=os.getpid())
    presence.set_status(PresenceStatus.IDLE, activity="No meaningful environmental changes")
    view = presence.public_view()
    card = format_presence_card(view)
    assert "Aster" in card
    assert "ONLINE" in card
    assert "No meaningful environmental changes" in card
    assert "IdentityOS outreach" in card
