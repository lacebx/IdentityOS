"""
core/operations/followups.py

Follow-up planning.

Follow-ups are thoughtful and bounded: a relationship that has gone quiet gets
at most ``max_follow_ups_per_target`` nudges, spaced by ``follow_up_after_hours``,
and never when the person has replied, declined, or opted out.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from .models import (
    FollowUp,
    FollowUpStatus,
    Relationship,
    RelationshipStatus,
    utcnow,
)
from .store import OperationsStore


def _parse(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


class FollowUpPlanner:
    def __init__(self, store: OperationsStore) -> None:
        self._store = store

    def due(self, now: Optional[datetime] = None) -> list[FollowUp]:
        return self._store.due_follow_ups(now)

    def plan(self, now: Optional[datetime] = None) -> list[FollowUp]:
        """Create follow-ups for quiet relationships that are due for a nudge."""
        now = now or datetime.now(timezone.utc)
        controls = self._store.controls()
        interval = timedelta(hours=controls.follow_up_after_hours)
        created: list[FollowUp] = []

        for rel in self._store.list_relationships():
            if rel.opted_out or rel.status in (RelationshipStatus.DECLINED, RelationshipStatus.OPTED_OUT):
                continue
            if rel.status not in (RelationshipStatus.OUTREACH_SENT, RelationshipStatus.ENGAGED):
                continue
            if rel.follow_up_count >= controls.max_follow_ups_per_target:
                # Exhausted reasonable attempts: stop pursuing unless new
                # context (a reply) appears — the relationship goes dormant.
                if rel.status is RelationshipStatus.OUTREACH_SENT:
                    rel.status = RelationshipStatus.DORMANT
                    self._store.update_relationship(rel)
                continue
            if self._has_scheduled(rel.id):
                continue
            last_out = _parse(rel.last_outbound_at)
            if last_out is None:
                continue
            last_in = _parse(rel.last_inbound_at)
            if last_in is not None and last_in > last_out:
                continue  # they replied; conversation is active
            if now < last_out + interval:
                continue
            reason = (
                f"no reply {controls.follow_up_after_hours:.0f}h after "
                f"outreach #{rel.follow_up_count + 1}"
            )
            follow_up = FollowUp(
                relationship_id=rel.id,
                due_at=now.isoformat(),
                reason=reason,
            )
            self._store.add_follow_up(follow_up)
            rel.follow_up_due_at = follow_up.due_at
            self._store.update_relationship(rel)
            created.append(follow_up)
        return created

    def complete(self, follow_up: FollowUp, *, now: Optional[datetime] = None) -> Relationship:
        follow_up.status = FollowUpStatus.SENT
        follow_up.completed_at = (now or datetime.now(timezone.utc)).isoformat()
        self._store.update_follow_up(follow_up)
        rel = self._store.get_relationship(follow_up.relationship_id)
        if rel is not None:
            rel.follow_up_count += 1
            rel.follow_up_due_at = None
            self._store.update_relationship(rel)
        return rel  # type: ignore[return-value]

    def cancel(self, relationship: Relationship, reason: str = "") -> None:
        for follow_up in self._store.list_follow_ups(status=FollowUpStatus.SCHEDULED):
            if follow_up.relationship_id == relationship.id:
                follow_up.status = FollowUpStatus.CANCELLED
                follow_up.reason = reason or follow_up.reason
                self._store.update_follow_up(follow_up)
        relationship.follow_up_due_at = None
        self._store.update_relationship(relationship)

    def _has_scheduled(self, relationship_id: str) -> bool:
        return any(
            f.relationship_id == relationship_id
            for f in self._store.list_follow_ups(status=FollowUpStatus.SCHEDULED)
        )


def next_follow_up_at(relationship: Relationship, hours: float) -> str:
    base = _parse(relationship.last_outbound_at) or datetime.now(timezone.utc)
    return (base + timedelta(hours=hours)).isoformat()
