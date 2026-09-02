"""Durable, evidence-backed interaction diagnostics for IdentityOS."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional


DEBUG_INDEX_NAMESPACE = "debug.index"
DEBUG_NAMESPACE_PREFIX = "debug.interaction:"
MAX_DEBUG_RECORDS = 100

_STAGE_ORDER = (
    "identity_lookup",
    "session_resolution",
    "input_policy",
    "executive",
    "prometheus_pre",
    "context_composition",
    "model",
    "prometheus_post",
    "output_policy",
    "evaluation",
    "state_commit",
    "completion_event",
)


def _serialize_violation(violation: Any) -> Dict[str, Any]:
    return {
        "policy_id": getattr(violation, "policy_id", ""),
        "policy_name": getattr(violation, "policy_name", ""),
        "effect": getattr(getattr(violation, "effect", None), "value", ""),
        "reason": getattr(violation, "reason", ""),
    }


def _policy_result(result: Any) -> Dict[str, Any]:
    return {
        "allowed": bool(getattr(result, "allowed", False)),
        "applied": list(getattr(result, "applied_policies", []) or []),
        "violations": [
            _serialize_violation(item)
            for item in (getattr(result, "violations", []) or [])
        ],
    }


def _context_sections(context: Any) -> Dict[str, Dict[str, Any]]:
    sections: Dict[str, Dict[str, Any]] = {}
    for name in (
        "runtime_directives",
        "identity",
        "identity_evolution",
        "user_knowledge",
        "emotion",
        "session_mode",
        "memory",
        "skills",
        "goals",
        "intentions",
        "relationships",
        "motivations",
        "timeline",
        "synthesis",
        "time_awareness",
        "evidence_footer",
    ):
        content = getattr(context, f"{name}_block", "") or ""
        if content:
            sections[name] = {"chars": len(content), "content": content}
    for name, content in (getattr(context, "custom_blocks", {}) or {}).items():
        if content:
            sections[f"custom:{name}"] = {
                "chars": len(content),
                "content": content,
            }
    return sections


def _laws_consulted(sections: Dict[str, Dict[str, Any]], evidence: list[dict]) -> list[str]:
    mappings = {
        "identity": "identity",
        "identity_evolution": "identity",
        "memory": "memory",
        "goals": "goals",
        "intentions": "intentions",
        "relationships": "relationships",
        "timeline": "timeline",
    }
    laws = {law for section, law in mappings.items() if section in sections}
    if evidence:
        laws.update({"evidence", "confidence"})
    return sorted(laws)


def _matching_memories(runtime: Any, identity_id: str, user_id: str, memory_block: str) -> list[dict]:
    if not memory_block:
        return []
    matches = []
    for memory in runtime.memory_store.by_user(identity_id, user_id):
        if memory.content and memory.content in memory_block:
            matches.append(
                {
                    "id": memory.id,
                    "type": memory.memory_type.value,
                    "content": memory.content,
                    "importance": memory.importance,
                    "created_at": memory.created_at.isoformat(),
                    "tags": list(memory.tags),
                }
            )
    return matches


def _evaluation_records(report: Any) -> list[dict]:
    records = []
    for item in getattr(report, "records", []) or []:
        records.append(
            {
                "criterion": getattr(item, "criterion_name", ""),
                "score": getattr(item, "score", 0.0),
                "outcome": getattr(getattr(item, "outcome", None), "value", ""),
                "reason": getattr(item, "reason", ""),
            }
        )
    return records


def build_debug_record(
    runtime: Any,
    *,
    request_id: str,
    identity_id: str,
    user_id: str,
    session_id: str,
    user_input: str,
    output: str,
    context: Any,
    timings_ms: Dict[str, float],
    input_policy: Any,
    output_policy: Any,
    evaluation_report: Any,
    evidence_results: Iterable[dict],
    mutation_proposals: Iterable[Any],
) -> Dict[str, Any]:
    """Build a trace from runtime-observed state, never model narration."""
    evidence = [dict(item) for item in evidence_results]
    sections = _context_sections(context)
    fact_store = runtime._fact_stores.get(identity_id)
    conflicts = []
    for proposal in mutation_proposals:
        status = getattr(getattr(proposal, "status", None), "value", "")
        if status == "conflict":
            conflicts.append(
                {
                    "field": getattr(proposal, "field", ""),
                    "old_value": getattr(proposal, "old_value", None),
                    "new_value": getattr(proposal, "new_value", None),
                    "confidence": getattr(proposal, "confidence", 0.0),
                    "reason": getattr(proposal, "reason", ""),
                }
            )
    if fact_store:
        for event in fact_store.event_log():
            if event.event_type in {"contested", "contradicted"}:
                conflicts.append(event.to_dict())

    goals = [
        {"id": goal.id, "title": goal.title, "status": goal.status.value}
        for goal in runtime.goal_engine.active()
        if goal.title and goal.title in sections.get("goals", {}).get("content", "")
    ]
    intentions = [
        {
            "id": intention.id,
            "description": intention.description,
            "status": intention.status.value,
        }
        for intention in runtime.intention_engine.active()
        if intention.description
        and intention.description in sections.get("intentions", {}).get("content", "")
    ]
    relationships = [
        {
            "id": edge.id,
            "target_id": edge.target_id,
            "type": edge.edge_type.value,
            "trust": edge.trust_level.value,
        }
        for edge in runtime.identity_graph.get_relationships(identity_id)
        if edge.target_id
        and edge.target_id in sections.get("relationships", {}).get("content", "")
    ]
    trace = [
        {"stage": stage, "duration_ms": timings_ms[stage]}
        for stage in _STAGE_ORDER
        if stage in timings_ms
    ]

    return {
        "schema_version": "1.0.0",
        "request_id": request_id,
        "identity_id": identity_id,
        "user_id": user_id,
        "session_id": session_id,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "input": user_input,
        "output": output,
        "decision_trace": trace,
        "policies": {
            "input": _policy_result(input_policy),
            "output": _policy_result(output_policy),
        },
        "laws_consulted": _laws_consulted(sections, evidence),
        "retrieved_memories": _matching_memories(
            runtime,
            identity_id,
            user_id,
            sections.get("memory", {}).get("content", ""),
        ),
        "evidence": evidence,
        "confidence": {
            "overall": getattr(evaluation_report, "overall_score", 0.0),
            "passed": getattr(evaluation_report, "passed", False),
            "criteria": _evaluation_records(evaluation_report),
        },
        "prompt": {
            "token_estimate": context.token_estimate(),
            "sections": sections,
        },
        "latency_ms": dict(timings_ms),
        "relationships_consulted": relationships,
        "goals_consulted": goals,
        "intentions_consulted": intentions,
        "conflicts": conflicts,
        "note": "decision_trace contains runtime stages and observed decisions, not hidden model chain-of-thought",
    }


def persist_debug_record(storage: Any, record: Dict[str, Any]) -> None:
    identity_id = record["identity_id"]
    request_id = record["request_id"]
    storage.save(identity_id, f"{DEBUG_NAMESPACE_PREFIX}{request_id}", record)
    index = storage.load(identity_id, DEBUG_INDEX_NAMESPACE) or {"request_ids": []}
    request_ids = [item for item in index.get("request_ids", []) if item != request_id]
    request_ids.append(request_id)
    stale = request_ids[:-MAX_DEBUG_RECORDS]
    request_ids = request_ids[-MAX_DEBUG_RECORDS:]
    for stale_id in stale:
        storage.delete(identity_id, f"{DEBUG_NAMESPACE_PREFIX}{stale_id}")
    storage.save(
        identity_id,
        DEBUG_INDEX_NAMESPACE,
        {"request_ids": request_ids, "updated_at": record["recorded_at"]},
    )


def load_debug_record(
    storage: Any,
    identity_id: str,
    request_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    if request_id is None:
        index = storage.load(identity_id, DEBUG_INDEX_NAMESPACE) or {}
        request_ids = index.get("request_ids", [])
        if not request_ids:
            return None
        request_id = request_ids[-1]
    return storage.load(identity_id, f"{DEBUG_NAMESPACE_PREFIX}{request_id}")

