"""Tests for the in-chat slash-command dispatcher (cli/main.py).

Covers model/adapter/temperature switching without killing the session,
status reporting, snapshot/history, and session reset.  Uses fake adapters
and an in-memory runtime so no network or LLM calls are made.
"""

from cli.main import (
    ChatContext,
    _dispatch_chat_command,
    _set_adapter_model,
    _set_adapter_temperature,
)
from core.snapshot import SnapshotManager
from runtime.persistence import JSONFileBackend


class FakeAdapter:
    def __init__(self, model="default"):
        self.model = model
        self.temperature = 0.7


class FakeMemoryStore:
    def __init__(self):
        self._memories = []

    def by_identity(self, identity_id):
        return self._memories


class FakeGoalEngine:
    def by_scope(self, scope):
        return []


class FakeCapabilityRegistry:
    def list(self, identity_id):
        return []


class FakeRuntime:
    """Minimal stand-in for IdentityRuntime — no network, no LLM."""

    def __init__(self):
        self.adapter = FakeAdapter("groq-test")
        self.memory_store = FakeMemoryStore()
        self.goal_engine = FakeGoalEngine()
        self.capability_registry = FakeCapabilityRegistry()
        self._fact_stores = {}
        self.sessions = []

    def get_session_mode(self, session_id):
        return None

    def end_session(self, session_id):
        pass

    def start_session(self, identity_id):
        sid = f"session-{len(self.sessions)}"
        self.sessions.append(sid)
        return sid


def _make_ctx(runtime=None, tmp_path=None):
    storage = JSONFileBackend(root_dir=str(tmp_path))
    manager = SnapshotManager(storage, "gabe")
    manager.capture({"identity": {"id": "gabe", "name": "Gabriel"}}, label="initial")
    return ChatContext(runtime or FakeRuntime(), manager, storage, "gabe", "session-1")


class TestModelSwitching:
    def test_single_adapter_model_switch(self):
        a = FakeAdapter("old-model")
        _set_adapter_model(a, "openai/gpt-oss-120b")
        assert a.model == "openai/gpt-oss-120b"

    def test_chain_adapter_model_switch_updates_all_leaf_adapters(self):
        from adapters import ChainAdapter
        a = FakeAdapter("m1")
        b = FakeAdapter("m2")
        chain = ChainAdapter([a, b])
        _set_adapter_model(chain, "openai/gpt-oss-120b")
        assert a.model == "openai/gpt-oss-120b"
        assert b.model == "openai/gpt-oss-120b"
        assert chain.model == "openai/gpt-oss-120b"

    def test_temperature_switch(self):
        from adapters import ChainAdapter
        a = FakeAdapter("m1")
        b = FakeAdapter("m2")
        _set_adapter_temperature(ChainAdapter([a, b]), 1.1)
        assert a.temperature == 1.1
        assert b.temperature == 1.1

    def test_dispatch_model_without_arg_shows_current(self, capsys):
        ctx = _make_ctx()
        status = _dispatch_chat_command("/model", ctx)
        assert status == "handled"
        assert "groq-test" in capsys.readouterr().out

    def test_dispatch_model_with_arg_switches(self, capsys):
        ctx = _make_ctx()
        status = _dispatch_chat_command("/model openai/gpt-oss-120b", ctx)
        assert status == "handled"
        assert ctx.runtime.adapter.model == "openai/gpt-oss-120b"
        assert "Model switched" in capsys.readouterr().out

    def test_dispatch_temperature_valid_and_invalid(self, capsys):
        ctx = _make_ctx()
        assert _dispatch_chat_command("/temperature 1.5", ctx) == "handled"
        assert ctx.runtime.adapter.temperature == 1.5
        assert _dispatch_chat_command("/temperature 9", ctx) == "handled"
        assert ctx.runtime.adapter.temperature == 1.5  # unchanged


class TestCommandLifecycle:
    def test_exit_returns_exit(self):
        ctx = _make_ctx()
        assert _dispatch_chat_command("/exit", ctx) == "exit"
        assert _dispatch_chat_command("/quit", ctx) == "exit"

    def test_help_returns_handled(self, capsys):
        ctx = _make_ctx()
        assert _dispatch_chat_command("/help", ctx) == "handled"
        assert "Chat commands" in capsys.readouterr().out

    def test_bare_slash_shows_menu(self, capsys):
        ctx = _make_ctx()
        assert _dispatch_chat_command("/", ctx) == "handled"
        assert "Chat commands" in capsys.readouterr().out

    def test_unknown_command_handled_not_exit(self, capsys):
        ctx = _make_ctx()
        assert _dispatch_chat_command("/bogus", ctx) == "handled"
        assert "Unknown command" in capsys.readouterr().out

    def test_non_command_returns_none(self):
        ctx = _make_ctx()
        assert _dispatch_chat_command("just a normal message", ctx) is None

    def test_status_reports_adapter_and_session(self, capsys):
        ctx = _make_ctx()
        assert _dispatch_chat_command("/status", ctx) == "handled"
        out = capsys.readouterr().out
        assert "FakeAdapter(groq-test)" in out
        assert "session-1" in out

    def test_clear_resets_session(self, capsys):
        ctx = _make_ctx()
        old = ctx.session_id
        assert _dispatch_chat_command("/clear", ctx) == "handled"
        assert ctx.session_id != old
        assert ctx.turns == 0
        assert "Session reset" in capsys.readouterr().out


class TestSnapshotCommands:
    def test_snapshot_captures_state(self, capsys, tmp_path):
        ctx = _make_ctx(runtime=FakeRuntime(), tmp_path=tmp_path)
        assert _dispatch_chat_command("/snapshot", ctx) == "handled"
        assert "snapshot saved" in capsys.readouterr().out
        assert len(ctx.manager.history()) == 2  # initial + new

    def test_colon_snapshot_alias_still_works(self, capsys, tmp_path):
        ctx = _make_ctx(runtime=FakeRuntime(), tmp_path=tmp_path)
        assert _dispatch_chat_command(":snapshot", ctx) == "handled"
        assert "snapshot saved" in capsys.readouterr().out

    def test_history_lists_snapshots(self, capsys, tmp_path):
        ctx = _make_ctx(runtime=FakeRuntime(), tmp_path=tmp_path)
        assert _dispatch_chat_command("/history", ctx) == "handled"
        out = capsys.readouterr().out
        assert "Snapshot" in out
        assert "initial" in out

    def test_snapshot_handles_register_format_state(self, capsys, tmp_path):
        """Identities stored in register() format (no snapshot_id) must not crash.

        Regression: manager.latest() raises KeyError when latest_snapshot is
        ``{"modules": {...}}``; /snapshot must fall back and still checkpoint.
        """
        storage = JSONFileBackend(root_dir=str(tmp_path))
        manager = SnapshotManager(storage, "gabe")
        storage.save("gabe", "latest_snapshot", {"modules": {"identity": {"id": "gabe"}}})
        ctx = ChatContext(FakeRuntime(), manager, storage, "gabe", "session-1")
        assert _dispatch_chat_command("/snapshot", ctx) == "handled"
        assert "snapshot saved" in capsys.readouterr().out
        assert len(manager.history()) == 1


class TestRuntimeUnavailable:
    def test_only_help_and_exit_allowed(self, capsys, tmp_path):
        storage = JSONFileBackend(root_dir=str(tmp_path))
        manager = SnapshotManager(storage, "gabe")
        manager.capture({"identity": {"id": "gabe", "name": "Gabriel"}}, label="initial")
        ctx = ChatContext(None, manager, storage, "gabe", "session-1")
        assert _dispatch_chat_command("/status", ctx) == "handled"
        assert "Runtime unavailable" in capsys.readouterr().out
        assert _dispatch_chat_command("/exit", ctx) == "exit"