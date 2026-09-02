"""Chronological reconstruction of durable IdentityOS state changes."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict

from runtime.orchestrator import IdentityRuntime


ROOT = Path(__file__).resolve().parents[1]


def _event(
    *,
    timestamp: str,
    track: str,
    event_type: str,
    title: str,
    details: Dict[str, Any],
    evidence: list[str] | None = None,
) -> Dict[str, Any]:
    return {
        "timestamp": timestamp,
        "track": track,
        "type": event_type,
        "title": title,
        "details": details,
        "evidence": evidence or [],
    }


def _amendment_events() -> list[dict]:
    events = []
    for path in sorted((ROOT / "docs" / "amendments").glob("AMEND-*.md")):
        text = path.read_text(encoding="utf-8")
        fields = {}
        for key in ("Amendment ID", "Status", "Date", "Laws Affected"):
            match = re.search(rf"\*\*{re.escape(key)}:\*\*\s*`?([^`\n]+)", text)
            fields[key] = match.group(1).strip() if match else ""
        summary_match = re.search(r"## Summary\s+(.+?)(?:\n##|\Z)", text, re.DOTALL)
        summary = " ".join(summary_match.group(1).split()) if summary_match else ""
        events.append(
            _event(
                timestamp=fields["Date"],
                track="constitution",
                event_type="amendment",
                title=fields["Amendment ID"] or path.stem,
                details={
                    "status": fields["Status"],
                    "laws_affected": fields["Laws Affected"],
                    "summary": summary,
                    "source": str(path.relative_to(ROOT)),
                },
            )
        )
    return events


def build_identity_replay(storage: Any, identity_id: str) -> Dict[str, Any]:
    """Build a replay strictly from persisted/runtime-observed records."""
    runtime = IdentityRuntime(storage=storage, adapter=None)
    identity = runtime.load(identity_id)
    if identity is None:
        raise ValueError(f"Identity '{identity_id}' not found")

    events: list[dict] = []
    timeline = runtime.timeline_registry.get(identity_id)
    if timeline:
        for item in timeline.events():
            events.append(
                _event(
                    timestamp=item.occurred_at.isoformat(),
                    track="timeline",
                    event_type=item.event_type.value,
                    title=item.title,
                    details={
                        "description": item.description,
                        "significance": item.significance,
                        "metadata": item.metadata,
                    },
                    evidence=[item.linked_entity_id] if item.linked_entity_id else [],
                )
            )

    facts = runtime._fact_stores.get(identity_id)
    fact_by_id = {fact.fact_id: fact for fact in facts.all()} if facts else {}
    confidence_series: Dict[str, list[dict]] = {}
    if facts:
        for item in facts.event_log():
            fact = fact_by_id.get(item.fact_id)
            domain = fact.domain.value if fact else "fact"
            evidence_ids = list(fact.evidence_ids) if fact else []
            events.append(
                _event(
                    timestamp=item.timestamp,
                    track=domain,
                    event_type=item.event_type,
                    title=item.field or item.fact_id,
                    details={
                        "fact_id": item.fact_id,
                        "field": item.field,
                        "value": item.value,
                        "old_value": item.old_value,
                        "confidence": item.confidence,
                        "reason": item.reason,
                    },
                    evidence=evidence_ids,
                )
            )
            confidence_series.setdefault(item.field or item.fact_id, []).append(
                {"timestamp": item.timestamp, "confidence": item.confidence}
            )

    for goal in runtime.goal_engine.all():
        events.append(
            _event(
                timestamp=goal.created_at.isoformat(),
                track="goal",
                event_type="created",
                title=goal.title,
                details={
                    "goal_id": goal.id,
                    "status": goal.status.value,
                    "priority": goal.priority.name.lower(),
                    "progress": goal.progress,
                    "success_criteria": goal.success_criteria,
                },
            )
        )
        if goal.updated_at != goal.created_at:
            events.append(
                _event(
                    timestamp=goal.updated_at.isoformat(),
                    track="goal",
                    event_type=goal.status.value,
                    title=goal.title,
                    details={
                        "goal_id": goal.id,
                        "status": goal.status.value,
                        "progress": goal.progress,
                        "metadata": goal.metadata,
                    },
                )
            )

    for edge in runtime.identity_graph.get_relationships(identity_id):
        events.append(
            _event(
                timestamp=edge.established_at.isoformat(),
                track="relationship",
                event_type="formed",
                title=f"{edge.edge_type.value}: {edge.target_id}",
                details={
                    "relationship_id": edge.id,
                    "target_id": edge.target_id,
                    "trust_level": edge.trust_level.value,
                    "strength": edge.strength,
                    "context": edge.context,
                },
            )
        )
        if edge.last_interaction:
            events.append(
                _event(
                    timestamp=edge.last_interaction.isoformat(),
                    track="relationship",
                    event_type="interaction",
                    title=f"Interaction with {edge.target_id}",
                    details={
                        "relationship_id": edge.id,
                        "interaction_count": edge.interaction_count,
                        "trust_level": edge.trust_level.value,
                        "strength": edge.strength,
                    },
                )
            )

    for version in identity.version_history:
        events.append(
            _event(
                timestamp=version.created_at.isoformat(),
                track="version",
                event_type="version",
                title=f"Identity version {version.version}",
                details={
                    "version": version.version,
                    "fingerprint": version.fingerprint,
                    "changelog": version.changelog,
                    "branch": version.branch,
                },
            )
        )

    events.extend(_amendment_events())
    events.sort(key=lambda item: (item["timestamp"], item["track"], item["title"]))
    track_counts: Dict[str, int] = {}
    for item in events:
        track_counts[item["track"]] = track_counts.get(item["track"], 0) + 1

    return {
        "schema_version": "1.0.0",
        "identity_id": identity_id,
        "identity_name": identity.name,
        "current_version": identity.version,
        "event_count": len(events),
        "tracks": track_counts,
        "confidence_series": confidence_series,
        "events": events,
    }

