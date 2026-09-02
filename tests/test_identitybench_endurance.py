import json

from core.goals import Goal
from core.identity import create_identity
from core.memory import MemoryFragment, MemoryType
from core.relationships import EdgeType
from identitybench.endurance import EnduranceMonitor
from runtime.debugger import persist_debug_record
from runtime.orchestrator import IdentityRuntime
from runtime.persistence import JSONFileBackend


def build_persisted_identity(path):
    storage = JSONFileBackend(root_dir=str(path))
    runtime = IdentityRuntime(storage=storage)
    identity = create_identity("Endurance Bot", identity_id="endurance-bot")
    runtime.register(identity)

    memory = MemoryFragment(
        identity_id=identity.id,
        user_id=identity.id,
        content="persistent evidence",
        memory_type=MemoryType.SEMANTIC,
    )
    runtime.memory_store.add(memory)
    runtime._persist_memory(memory)
    goal = Goal(title="Survive restart", metadata={"identity_id": identity.id})
    goal.mark_completed("verified")
    runtime.goal_engine.add(goal)
    runtime._persist_goals(identity.id)
    runtime.identity_graph.interact_or_connect(identity.id, "operator", EdgeType.PEER)
    runtime._persist_relationships(identity.id)
    runtime._persist_timeline(identity.id)
    persist_debug_record(storage, {
        "identity_id": identity.id,
        "request_id": "observed-request",
        "recorded_at": "2026-09-01T00:00:00+00:00",
        "prompt": {"token_estimate": 321},
        "latency_ms": {"total": 123.0},
    })
    return runtime


def benchmark_run(score=85.0, honesty=80.0):
    return {
        "timestamp": "2026-09-01T00:00:00+00:00",
        "overall_score": score,
        "worlds": [{"metrics": {"hallucination_rate": honesty}}],
    }


def test_endurance_sample_measures_and_restart_verifies_real_state(tmp_path):
    identity_store = tmp_path / "identities"
    benchmark_dir = tmp_path / "benchmarks"
    build_persisted_identity(identity_store)
    monitor = EnduranceMonitor(str(benchmark_dir), str(identity_store))

    sample = monitor.record("endurance-bot", benchmark_run())
    assert sample["identity_consistency_pct"] == 100.0
    assert sample["memory_count"] == 1
    assert sample["goal_completion_pct"] == 100.0
    assert sample["relationship_stability_pct"] == 100.0
    assert sample["prompt_tokens"] == 321
    assert sample["latency_ms"] == 123.0
    assert sample["hallucination_rate_pct"] == 20.0
    assert sample["restart_recovery_pct"] == 100.0
    assert all(sample["restart_evidence"]["checks"].values())

    document = json.loads((benchmark_dir / "endurance/endurance-bot.json").read_text())
    assert len(document["samples"]) == 1
    assert any(alert["metric"] == "hallucination_rate_pct" for alert in document["alerts"])


def test_endurance_report_has_graphs_thresholds_and_multiple_samples(tmp_path):
    identity_store = tmp_path / "identities"
    benchmark_dir = tmp_path / "benchmarks"
    build_persisted_identity(identity_store)
    monitor = EnduranceMonitor(str(benchmark_dir), str(identity_store))
    monitor.record("endurance-bot", benchmark_run())
    monitor.record("endurance-bot", benchmark_run(score=60.0, honesty=100.0))

    document = monitor.load("endurance-bot")
    assert len(document["samples"]) == 2
    assert any(alert["metric"] == "benchmark_score" for alert in document["alerts"])
    report = monitor.report("endurance-bot")
    assert "xychart-beta" in report
    assert "Restart recovery" in report
    assert "CRITICAL" in report
