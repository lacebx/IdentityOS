"""Stable, read-only diagnostics for persisted IdentityOS state."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from runtime.debugger import load_debug_record
from runtime.orchestrator import IdentityRuntime
from runtime.persistence import JSONFileBackend


@dataclass(frozen=True)
class IdentityHealthEvidence:
    """Runtime-observed evidence used by health and endurance tooling."""

    identity_fingerprint: str
    counts: dict[str, int]
    relationship_signature: tuple[str, ...]
    goal_completion_pct: float
    prompt_tokens: int
    latency_ms: float
    restart_recovery_pct: float
    restart_evidence: dict


def _identity_fingerprint(spec) -> str:
    stable = {
        "id": spec.id,
        "identity_class": getattr(getattr(spec, "identity_class", None), "value", ""),
        "created_at": spec.created_at.isoformat() if spec.created_at else "",
    }
    return hashlib.sha256(json.dumps(stable, sort_keys=True).encode()).hexdigest()


def _state_counts(runtime: IdentityRuntime, identity_id: str) -> dict[str, int]:
    timeline = runtime.timeline_registry.get(identity_id)
    return {
        "memories": len(runtime.memory_store.by_identity(identity_id)),
        "goals": len([
            goal for goal in runtime.goal_engine.all()
            if goal.metadata.get("identity_id") in (None, identity_id)
        ]),
        "intentions": len([
            intention for intention in runtime.intention_engine.all()
            if intention.metadata.get("identity_id") in (None, identity_id)
        ]),
        "relationships": len(runtime.identity_graph.get_relationships(identity_id)),
        "timeline": len(timeline.events()) if timeline else 0,
    }


def _relationship_signature(runtime: IdentityRuntime, identity_id: str) -> tuple[str, ...]:
    return tuple(sorted(
        f"{edge.source_id}:{edge.target_id}:{edge.edge_type.value}"
        for edge in runtime.identity_graph.get_relationships(identity_id)
    ))


def _goal_completion(runtime: IdentityRuntime, identity_id: str) -> float:
    goals = [
        goal for goal in runtime.goal_engine.all()
        if goal.metadata.get("identity_id") in (None, identity_id)
    ]
    if not goals:
        return 100.0
    completed = sum(goal.status.value == "completed" for goal in goals)
    return round(completed / len(goals) * 100, 1)


class IdentityDiagnostics:
    """Inspect persisted state without exposing runtime internals to callers."""

    def __init__(self, identity_store: str = ".identity_store") -> None:
        self.identity_store = identity_store

    def inspect_health(self, identity_id: str) -> IdentityHealthEvidence:
        backend = JSONFileBackend(root_dir=self.identity_store)
        runtime = IdentityRuntime(storage=backend)
        spec = runtime.load(identity_id)
        if not spec:
            raise ValueError(f"Identity '{identity_id}' not found in {self.identity_store}")

        before = _state_counts(runtime, identity_id)
        relationships = _relationship_signature(runtime, identity_id)
        debug = load_debug_record(backend, identity_id) or {}
        timings = debug.get("latency_ms", {})
        latency = float(timings.get("total", sum(timings.values()) if timings else 0.0))

        restarted = IdentityRuntime(storage=JSONFileBackend(root_dir=self.identity_store))
        restarted_spec = restarted.load(identity_id)
        after = _state_counts(restarted, identity_id) if restarted_spec else {}
        checks = {key: after.get(key) == value for key, value in before.items()}
        checks["identity"] = restarted_spec is not None
        restart_score = round(sum(checks.values()) / len(checks) * 100, 1)

        return IdentityHealthEvidence(
            identity_fingerprint=_identity_fingerprint(spec),
            counts=before,
            relationship_signature=relationships,
            goal_completion_pct=_goal_completion(runtime, identity_id),
            prompt_tokens=int(debug.get("prompt", {}).get("token_estimate", 0)),
            latency_ms=round(latency, 1),
            restart_recovery_pct=restart_score,
            restart_evidence={"before": before, "after": after, "checks": checks},
        )
