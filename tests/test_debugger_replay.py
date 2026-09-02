"""Durability and CLI contracts for Identity Debugger and Identity Replay."""

from __future__ import annotations

import json

from cli.main import build_parser, main
from core.evaluation import register_default_criteria
from core.goals import Goal
from core.identity import create_identity
from core.identity_facts import FactSource
from core.relationships import EdgeType, TrustLevel
from core.timeline import LifeEvent, LifeEventType
from runtime.debugger import load_debug_record
from runtime.orchestrator import IdentityRuntime, InteractionRequest
from runtime.persistence import JSONFileBackend
from runtime.replay import build_identity_replay


class _StaticAdapter:
    model = "static-test"

    def generate(self, context, user_input, identity, **kwargs):
        return "Verified test response."


def _runtime(tmp_path):
    storage = JSONFileBackend(root_dir=str(tmp_path / "store"))
    runtime = IdentityRuntime(storage=storage, adapter=_StaticAdapter())
    register_default_criteria(runtime.evaluation_engine)
    identity = create_identity("Debug Bot", identity_id="debug-bot")
    runtime.register(identity)
    return runtime, storage, identity


def test_debug_record_is_evidence_backed_and_survives_restart(tmp_path):
    runtime, storage, identity = _runtime(tmp_path)
    runtime.goal_engine.add(Goal(title="Inspect runtime behavior"))
    runtime._persist_goals(identity.id)
    runtime.identity_graph.connect(
        source_id=identity.id,
        target_id="debug-user",
        edge_type=EdgeType.COLLABORATOR,
        trust_level=TrustLevel.HIGH,
    )
    runtime._persist_relationships(identity.id)

    runtime.process(
        InteractionRequest(
            identity_id=identity.id,
            user_id="debug-user",
            session_id="first-session",
            user_input="Remember that the debugger needs evidence.",
        )
    )
    response = runtime.process(
        InteractionRequest(
            identity_id=identity.id,
            user_id="debug-user",
            session_id="second-session",
            user_input="What did I ask you to remember before?",
        )
    )

    assert response.metadata["debug_request_id"] == response.request_id
    record = load_debug_record(storage, identity.id, response.request_id)
    assert record is not None
    assert record["request_id"] == response.request_id
    assert record["decision_trace"][0]["stage"] == "identity_lookup"
    assert record["note"].endswith("not hidden model chain-of-thought")
    assert record["prompt"]["token_estimate"] > 0
    assert record["latency_ms"]["total"] >= 0
    assert record["retrieved_memories"]
    assert "memory" in record["laws_consulted"]
    assert "goals" in record["laws_consulted"]
    assert "relationships" in record["laws_consulted"]
    assert record["goals_consulted"][0]["title"] == "Inspect runtime behavior"
    assert record["relationships_consulted"][0]["target_id"] == "debug-user"

    restarted = JSONFileBackend(root_dir=str(tmp_path / "store"))
    assert load_debug_record(restarted, identity.id) == record


def test_replay_combines_persisted_evolution_tracks_and_exports_json(tmp_path):
    runtime, storage, identity = _runtime(tmp_path)
    fact_store = runtime._fact_stores[identity.id]
    fact = fact_store.merge_or_reinforce(
        field="preferences.editor",
        value="VS Code",
        confidence=0.8,
        reasons=["user stated"],
        source=FactSource.USER_INFERRED,
        evidence_id="memory-1",
    )
    fact_store.merge_or_reinforce(
        field="preferences.editor",
        value="VS Code",
        confidence=0.9,
        reasons=["user confirmed"],
        source=FactSource.USER_INFERRED,
        evidence_id="memory-2",
    )
    runtime._save_fact_store(identity.id)

    goal = Goal(title="Complete replay support")
    runtime.goal_engine.add(goal)
    goal.mark_completed("verified")
    runtime._persist_goals(identity.id)

    runtime.identity_graph.connect(
        source_id=identity.id,
        target_id="replay-user",
        edge_type=EdgeType.COLLABORATOR,
        trust_level=TrustLevel.HIGH,
        context="Replay test",
    )
    runtime._persist_relationships(identity.id)

    runtime.timeline_registry.record_event(
        identity.id,
        LifeEvent(
            identity_id=identity.id,
            event_type=LifeEventType.MILESTONE,
            title="Replay implemented",
            description="All tracks are visible.",
        ),
    )
    runtime._persist_timeline(identity.id)
    identity.bump_version("patch", "Added replay")
    runtime._persist_identity(identity)

    replay = build_identity_replay(storage, identity.id)
    tracks = replay["tracks"]
    assert tracks["timeline"] >= 1
    assert tracks["preference"] >= 2
    assert tracks["goal"] >= 1
    assert tracks["relationship"] >= 1
    assert tracks["version"] >= 1
    assert tracks["constitution"] >= 1
    assert replay["confidence_series"]["preferences.editor"]
    preference_event = next(
        event for event in replay["events"]
        if event["track"] == "preference" and event["details"]["fact_id"] == fact.fact_id
    )
    assert preference_event["evidence"] == ["memory-1", "memory-2"]
    assert replay["events"] == sorted(
        replay["events"],
        key=lambda item: (item["timestamp"], item["track"], item["title"]),
    )

    output = tmp_path / "replay.json"
    rc = main([
        "--store",
        str(tmp_path / "store"),
        "replay",
        "--id",
        identity.id,
        "--output",
        str(output),
    ])
    assert rc == 0
    assert json.loads(output.read_text())["identity_id"] == identity.id


def test_debugger_and_replay_cli_arguments_are_explicit():
    parser = build_parser()
    debug = parser.parse_args([
        "debug",
        "--id",
        "adam",
        "--interaction",
        "request-1",
        "--output",
        "debug.json",
    ])
    replay = parser.parse_args([
        "replay",
        "--id",
        "adam",
        "--output",
        "replay.json",
    ])
    assert (debug.command, debug.id, debug.interaction) == (
        "debug",
        "adam",
        "request-1",
    )
    assert (replay.command, replay.id, replay.output) == (
        "replay",
        "adam",
        "replay.json",
    )
