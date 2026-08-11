"""Chat-path latency: ordinary process() must not block on Executive ticks."""

from __future__ import annotations

import time

import pytest

from core.evaluation import register_default_criteria
from core.identity import create_identity
from core.memory import MemoryType
from runtime.orchestrator import IdentityRuntime, InteractionRequest
from runtime.persistence import JSONFileBackend


class FakeAdapter:
    model = "fake-test"

    def __init__(self):
        self.calls = 0
        self.last_user_input = None

    def generate(self, context="", user_input="", identity=None, **kwargs):
        self.calls += 1
        self.last_user_input = user_input
        return f"Echo: {user_input}"


@pytest.fixture
def store(tmp_path):
    return JSONFileBackend(root_dir=str(tmp_path / "store"))


@pytest.fixture
def runtime(store):
    rt = IdentityRuntime(storage=store, adapter=FakeAdapter())
    register_default_criteria(rt.evaluation_engine)
    yield rt
    if rt.executive and rt.executive.scheduler:
        rt.executive.scheduler.stop()


@pytest.fixture
def identity(runtime):
    spec = create_identity(name="LatencyBot", identity_id="latency-bot")
    runtime.register(spec)
    return spec


def test_ordinary_chat_does_not_call_process_ready_synchronously(runtime, identity):
    """Ordinary chat must not run the old 50-tick Executive loop."""
    assert runtime.executive is not None
    # Prevent the background scheduler from racing the spy.
    runtime.executive.scheduler.start = lambda: None

    calls = []
    original = runtime.executive.process_ready

    def spy(*args, **kwargs):
        calls.append((args, kwargs))
        return original(*args, **kwargs)

    runtime.executive.process_ready = spy

    sid = runtime.start_session(identity.id)
    resp = runtime.process(InteractionRequest(
        identity_id=identity.id,
        user_input="Hello, how are you today?",
        session_id=sid,
    ))

    assert resp.policy_passed is True
    assert "Echo:" in resp.output
    assert calls == []


def test_ordinary_chat_reaches_adapter(runtime, identity):
    sid = runtime.start_session(identity.id)
    resp = runtime.process(InteractionRequest(
        identity_id=identity.id,
        user_input="Hi there",
        session_id=sid,
    ))
    assert runtime.adapter.calls == 1
    assert runtime.adapter.last_user_input == "Hi there"
    assert "Hi there" in resp.output


def test_capability_request_still_routes(runtime, identity):
    runtime.capability_registry.install(identity.id, "datetime")
    sid = runtime.start_session(identity.id)
    resp = runtime.process(InteractionRequest(
        identity_id=identity.id,
        user_input="What time is it right now?",
        session_id=sid,
    ))
    assert runtime.adapter.calls == 1
    assert resp.context_used is not None
    assert (
        "factual_skill_data" in resp.context_used.custom_blocks
        or "Evidence Sources" in resp.output
    )


def test_persistence_still_occurs(runtime, identity):
    sid = runtime.start_session(identity.id)
    runtime.process(InteractionRequest(
        identity_id=identity.id,
        user_input="Remember that my favorite color is teal.",
        session_id=sid,
    ))
    # Autouse conftest flushes deferred post-process before this assert.
    mems = runtime.memory_store.by_identity(identity_id=identity.id)
    episodic = [m for m in mems if m.memory_type == MemoryType.EPISODIC]
    assert len(episodic) >= 1
    assert any("teal" in m.content.lower() or "favorite" in m.content.lower() for m in mems)


def test_identity_mutations_still_occur(runtime, identity):
    sid = runtime.start_session(identity.id)
    runtime.process(InteractionRequest(
        identity_id=identity.id,
        user_input="My favorite color is blue.",
        session_id=sid,
    ))
    runtime.flush_post_process()
    fact_store = runtime._fact_stores.get(identity.id)
    assert fact_store is not None
    facts = fact_store.all()
    mems = runtime.memory_store.by_identity(identity_id=identity.id)
    semantic = [m for m in mems if m.memory_type == MemoryType.SEMANTIC]
    assert facts or semantic or any("blue" in m.content.lower() for m in mems)


def test_acquisition_commits_without_sync_tick_loop(runtime, identity, monkeypatch):
    """Capability-acquisition may create a task but must not tick 50 times inline."""
    assert runtime.executive is not None
    runtime.executive.scheduler.start = lambda: None

    tick_calls = []
    original = runtime.executive.process_ready

    def spy(*args, **kwargs):
        tick_calls.append(1)
        return original(*args, **kwargs)

    runtime.executive.process_ready = spy

    sid = runtime.start_session(identity.id)
    before = time.monotonic()
    resp = runtime.process(InteractionRequest(
        identity_id=identity.id,
        user_input="Please create a speech capability and install it",
        session_id=sid,
    ))
    elapsed = time.monotonic() - before

    assert resp.policy_passed is True
    assert runtime.adapter.calls == 1
    # No synchronous multi-tick execution on the chat path
    assert len(tick_calls) == 0
    # Creating/recovering a task should be fast without the 50-tick loop
    assert elapsed < 5.0
    active = runtime.executive.active_tasks(identity.id)
    assert len(active) >= 1


def test_deferred_post_process_runs_after_return(runtime, identity):
    """Without flush, reply returns before memory is written; flush then persists."""
    runtime._skip_test_post_process_flush = True
    sid = runtime.start_session(identity.id)
    resp = runtime.process(InteractionRequest(
        identity_id=identity.id,
        user_input="Hello deferred path",
        session_id=sid,
    ))
    assert "Hello deferred path" in resp.output
    # Immediately after return (no flush), episodic may not exist yet —
    # give a tiny moment then flush and verify.
    mems_before = runtime.memory_store.by_identity(identity_id=identity.id)
    # Race: worker may already have finished; either way flush must make it durable.
    runtime.flush_post_process()
    mems_after = runtime.memory_store.by_identity(identity_id=identity.id)
    episodic = [m for m in mems_after if m.memory_type == MemoryType.EPISODIC]
    assert len(episodic) >= 1
    assert resp.eval_score is not None
    # silence unused
    assert mems_before is not None
