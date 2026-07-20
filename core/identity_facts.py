"""
core/identity_facts.py

Canonical Identity Knowledge — the foundational data model for all identity state.

Instead of storing identity as English sentences in memory, every preference,
belief, trait, value, habit, and goal is a structured IdentityFact with
full metadata: value, confidence, reasons, evidence references, timestamps,
reinforcement count, and status.

Identity is structured knowledge, not accumulated text.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class FactStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    CONTESTED = "contested"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class FactSource(str, Enum):
    ASSISTANT_SELF = "assistant_self"
    USER_INFERRED = "user_inferred"
    CREATOR_DEFINED = "creator_defined"
    RUNTIME_INFERRED = "runtime_inferred"
    EVALUATION = "evaluation"
    IMPORTED = "imported"


class FactDomain(str, Enum):
    PREFERENCE = "preference"
    BELIEF = "belief"
    TRAIT = "trait"
    VALUE = "value"
    HABIT = "habit"
    GOAL = "goal"
    RELATIONSHIP = "relationship"
    COMMUNICATION = "communication"
    USER_KNOWLEDGE = "user_knowledge"
    EXPERIENCE = "experience"


@dataclass
class IdentityFact:
    """
    A single canonical identity fact with full provenance metadata.

    This is the atom of identity knowledge. Every identity fact:
    - Has a unique ID for traceability
    - Knows its domain and field path
    - Stores its value with typed metadata
    - Tracks confidence (how sure are we?)
    - Lists reasons (why does this fact exist?)
    - References evidence (which conversations proved it?)
    - Counts reinforcements (how many times has it been confirmed?)
    - Tracks lifecycle (first seen, last confirmed, status)
    - Maintains version_history for full audit trail
    """

    fact_id: str
    domain: FactDomain
    field: str                           # e.g. "preferences.favorite_color"
    value: Any                           # e.g. "blue"
    value_type: str = "string"           # "string", "number", "boolean", "list", "dict"
    confidence: float = 0.5
    reasons: List[str] = field(default_factory=list)
    source: FactSource = FactSource.RUNTIME_INFERRED
    evidence_ids: List[str] = field(default_factory=list)
    first_seen: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_confirmed: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    times_reinforced: int = 0
    status: FactStatus = FactStatus.PENDING
    superseded_by: Optional[str] = None
    version_history: List[Dict[str, Any]] = field(default_factory=list)

    def _record_version(self, event_type: str, reason: str = "") -> None:
        entry = {
            "version": len(self.version_history) + 1,
            "event_type": event_type,
            "confidence": self.confidence,
            "times_reinforced": self.times_reinforced,
            "status": self.status.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if reason:
            entry["reason"] = reason
        self.version_history.append(entry)

    def reinforce(self, reason: str = "") -> None:
        self.times_reinforced += 1
        self.last_confirmed = datetime.now(timezone.utc).isoformat()
        if reason and reason not in self.reasons:
            self.reasons.append(reason)
        if self.status == FactStatus.PENDING:
            self.status = FactStatus.ACTIVE
        self._record_version("reinforced", reason)

    def contest(self, reason: str) -> None:
        self.status = FactStatus.CONTESTED
        self.reasons.append(f"Contested: {reason}")
        self._record_version("contested", reason)

    def supersede(self, new_fact_id: str) -> None:
        self.status = FactStatus.SUPERSEDED
        self.superseded_by = new_fact_id
        self._record_version("superseded", f"Superseded by {new_fact_id[:8]}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fact_id": self.fact_id,
            "domain": self.domain.value,
            "field": self.field,
            "value": self.value,
            "value_type": self.value_type,
            "confidence": self.confidence,
            "reasons": self.reasons,
            "source": self.source.value,
            "evidence_ids": self.evidence_ids,
            "first_seen": self.first_seen,
            "last_confirmed": self.last_confirmed,
            "times_reinforced": self.times_reinforced,
            "status": self.status.value,
            "superseded_by": self.superseded_by,
            "version_history": self.version_history,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IdentityFact":
        return cls(
            fact_id=data.get("fact_id", str(uuid.uuid4())),
            domain=FactDomain(data.get("domain", "preference")),
            field=data.get("field", ""),
            value=data.get("value"),
            value_type=data.get("value_type", "string"),
            confidence=data.get("confidence", 0.5),
            reasons=data.get("reasons", []),
            source=FactSource(data.get("source", "runtime_inferred")),
            evidence_ids=data.get("evidence_ids", []),
            first_seen=data.get("first_seen", datetime.now(timezone.utc).isoformat()),
            last_confirmed=data.get("last_confirmed", datetime.now(timezone.utc).isoformat()),
            times_reinforced=data.get("times_reinforced", 0),
            status=FactStatus(data.get("status", "pending")),
            superseded_by=data.get("superseded_by"),
            version_history=data.get("version_history", []),
        )

    def versions(self) -> List[Dict[str, Any]]:
        return list(self.version_history)


# ─── FactStore ────────────────────────────────────────────────────────────────


class FactStore:
    """
    In-memory store for canonical identity facts.

    Supports CRUD, query by domain/field/status, and reinforcement.
    """

    def __init__(self) -> None:
        self._facts: Dict[str, IdentityFact] = {}
        self._event_log: List[FactEvent] = []

    def add(self, fact: IdentityFact, reason: str = "") -> None:
        self._facts[fact.fact_id] = fact

    def get(self, fact_id: str) -> Optional[IdentityFact]:
        return self._facts.get(fact_id)

    def remove(self, fact_id: str) -> bool:
        removed = bool(self._facts.pop(fact_id, None))
        if removed:
            self.log_event("removed", None, fact_id=fact_id, reason="Fact removed")
        return removed

    def all(self) -> List[IdentityFact]:
        return list(self._facts.values())

    def by_domain(self, domain: FactDomain) -> List[IdentityFact]:
        return [f for f in self._facts.values() if f.domain == domain]

    def by_field(self, field: str) -> List[IdentityFact]:
        return [f for f in self._facts.values() if f.field == field]

    def by_status(self, status: FactStatus) -> List[IdentityFact]:
        return [f for f in self._facts.values() if f.status == status]

    def active(self) -> List[IdentityFact]:
        return [f for f in self._facts.values() if f.status == FactStatus.ACTIVE]

    def find(self, field: str) -> Optional[IdentityFact]:
        """Return the most recent active fact for a field."""
        matches = [f for f in self._facts.values()
                   if f.field == field and f.status == FactStatus.ACTIVE]
        if not matches:
            return None
        return max(matches, key=lambda f: f.last_confirmed)

    def all_versions_for_field(self, field: str) -> List[IdentityFact]:
        """Return all facts (active + superseded) for a field, sorted by first_seen desc."""
        matches = [f for f in self._facts.values() if f.field == field]
        return sorted(matches, key=lambda f: f.first_seen, reverse=True)

    def log_event(
        self, event_type: str, fact: Optional[IdentityFact] = None,
        fact_id: str = "", reason: str = "",
    ) -> None:
        """Public method to log a fact event (for use by contradiction engine, mutation engine, etc.)."""
        event = FactEvent(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            fact_id=fact.fact_id if fact else fact_id,
            field=fact.field if fact else "",
            value=fact.value if fact else None,
            confidence=fact.confidence if fact else 0.0,
            reason=reason,
        )
        self._event_log.append(event)

    def event_log(self) -> List[FactEvent]:
        return list(self._event_log)

    def replay(self) -> List[FactEvent]:
        """Replay all events for audit/inspection."""
        return self._event_log

    def merge_or_reinforce(
        self,
        field: str,
        value: Any,
        confidence: float,
        reasons: List[str],
        source: FactSource,
        evidence_id: str = "",
        domain: Optional[FactDomain] = None,
    ) -> IdentityFact:
        """
        If an active fact exists for this field with the same value, reinforce it.
        Otherwise create a new fact.
        Returns the fact (new or reinforced).

        If domain is None, it is inferred from the field prefix
        (e.g. "preferences.favorite_color" → FactDomain.PREFERENCE).
        """
        if domain is None:
            domain = self._infer_domain(field)

        existing = self.find(field)
        if existing and existing.value == value:
            old_confidence = existing.confidence
            existing.reinforce()
            if evidence_id and evidence_id not in existing.evidence_ids:
                existing.evidence_ids.append(evidence_id)
            existing.confidence = max(existing.confidence, confidence)
            self.log_event("reinforced", existing,
                            reason=f"Confidence {old_confidence:.2f} → {existing.confidence:.2f}")
            return existing
        elif existing and existing.value != value:
            new_fact = IdentityFact(
                fact_id=str(uuid.uuid4()),
                domain=domain,
                field=field,
                value=value,
                confidence=confidence,
                reasons=reasons,
                source=source,
                evidence_ids=[evidence_id] if evidence_id else [],
            )
            existing.supersede(new_fact.fact_id)
            self.log_event("superseded", existing,
                            reason=f"Superseded by {new_fact.fact_id[:8]}")
            self.log_event("created", new_fact, reason=f"Replaces {existing.fact_id[:8]}")
            self.add(new_fact)
            return new_fact
        fact = IdentityFact(
            fact_id=str(uuid.uuid4()),
            domain=domain,
            field=field,
            value=value,
            confidence=confidence,
            reasons=reasons,
            source=source,
            evidence_ids=[evidence_id] if evidence_id else [],
            status=FactStatus.ACTIVE,
        )
        self.log_event("created", fact)
        self.add(fact)
        return fact

    @staticmethod
    def _infer_domain(field: str) -> FactDomain:
        prefix = field.split(".")[0] if "." in field else field
        domain_map = {
            "preferences": FactDomain.PREFERENCE,
            "beliefs": FactDomain.BELIEF,
            "traits": FactDomain.TRAIT,
            "values": FactDomain.VALUE,
            "habits": FactDomain.HABIT,
            "goals": FactDomain.GOAL,
            "relationships": FactDomain.RELATIONSHIP,
            "communication": FactDomain.COMMUNICATION,
            "user": FactDomain.USER_KNOWLEDGE,
            "experience": FactDomain.EXPERIENCE,
            "likes": FactDomain.PREFERENCE,
            "dislikes": FactDomain.PREFERENCE,
        }
        return domain_map.get(prefix, FactDomain.PREFERENCE)

    def to_dict_list(self) -> List[Dict[str, Any]]:
        return [f.to_dict() for f in self._facts.values()]

    def to_dict_full(self) -> Dict[str, Any]:
        return {
            "facts": self.to_dict_list(),
            "event_log": [e.to_dict() for e in self._event_log],
        }

    @classmethod
    def from_dict_list(cls, data: List[Dict[str, Any]]) -> "FactStore":
        store = cls()
        for d in data:
            store.add(IdentityFact.from_dict(d))
        return store

    @classmethod
    def from_dict_full(cls, data: Dict[str, Any]) -> "FactStore":
        store = cls()
        for d in data.get("facts", []):
            store.add(IdentityFact.from_dict(d))
        for e in data.get("event_log", []):
            store._event_log.append(FactEvent.from_dict(e))
        return store

    def __len__(self) -> int:
        return len(self._facts)


# ─── FactEvent — Event Sourcing Log ───────────────────────────────────────────


@dataclass
class FactEvent:
    """
    An immutable record of a fact lifecycle event.

    Every mutation (create, reinforce, reject, supersede, contest, contradict)
    produces an event. The event log is replayable and provides full audit trail
    independent of the fact store's current state.
    """

    event_id: str
    event_type: str  # "created", "reinforced", "rejected", "superseded", "contested", "contradicted"
    fact_id: str
    field: str
    value: Any
    old_value: Optional[Any] = None
    confidence: float = 0.5
    reason: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "fact_id": self.fact_id,
            "field": self.field,
            "value": self.value,
            "old_value": self.old_value,
            "confidence": self.confidence,
            "reason": self.reason,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FactEvent":
        return cls(
            event_id=data.get("event_id", str(uuid.uuid4())),
            event_type=data.get("event_type", ""),
            fact_id=data.get("fact_id", ""),
            field=data.get("field", ""),
            value=data.get("value"),
            old_value=data.get("old_value"),
            confidence=data.get("confidence", 0.5),
            reason=data.get("reason", ""),
            timestamp=data.get("timestamp", datetime.now(timezone.utc).isoformat()),
        )


# ─── Evolution Thresholds ──────────────────────────────────────────────────────


class EvolutionThresholds:
    """
    Controls when a candidate mutation becomes a stable identity fact.

    Identity evolves through evidence, not single conversations.
    Each candidate accumulates confidence through reinforcement.
    """

    def __init__(
        self,
        min_confidence_first: float = 0.5,
        accept_confidence: float = 0.80,
        stable_confidence: float = 0.90,
        min_reinforcements: int = 2,
        reinforce_boost: float = 0.06,
    ):
        self.min_confidence_first = min_confidence_first
        self.accept_confidence = accept_confidence
        self.stable_confidence = stable_confidence
        self.min_reinforcements = min_reinforcements
        self.reinforce_boost = reinforce_boost

    def should_accept(self, fact: IdentityFact) -> bool:
        """A fact can be accepted if it meets the confidence or reinforcement bar."""
        if fact.confidence >= self.accept_confidence:
            return True
        if fact.times_reinforced >= self.min_reinforcements:
            return True
        return fact.confidence >= self.min_confidence_first

    def should_promote_to_stable(self, fact: IdentityFact) -> bool:
        return (fact.confidence >= self.stable_confidence
                and fact.times_reinforced >= self.min_reinforcements)

    def compute_accumulated_confidence(
        self, base_confidence: float, reinforcements: int
    ) -> float:
        c = base_confidence + (reinforcements * self.reinforce_boost)
        return min(1.0, c)

    def compute_reinforcement_boost(self, proposal_confidence: float,
                                    existing_confidence: float) -> float:
        return min(self.reinforce_boost, (proposal_confidence + existing_confidence) / 2)


# ─── Contradiction Engine ──────────────────────────────────────────────────────


class ContradictionResult(str, Enum):
    OVERWRITE_ACCEPTED = "overwrite_accepted"
    REJECTED_KEEP_EXISTING = "rejected_keep_existing"
    PENDING_REVIEW = "pending_review"
    MERGED = "merged"


class ContradictionEngine:
    """
    Sophisticated contradiction resolution.

    When a new fact conflicts with a stable fact, instead of blindly
    overwriting, compare confidence, recency, reinforcement, and stability.
    """

    def __init__(self, thresholds: Optional[EvolutionThresholds] = None) -> None:
        self.thresholds = thresholds or EvolutionThresholds()
        self._conflict_log: List[Dict[str, Any]] = []

    def resolve(
        self,
        new_fact: IdentityFact,
        existing_fact: IdentityFact,
    ) -> ContradictionResult:
        """
        Resolve a contradiction between a proposed fact and an existing fact.

        Decision matrix:
        - If existing is stable (high confidence, reinforced) → reject change
        - If new has significantly higher confidence → accept overwrite
        - If comparable → pend for later review
        - If values are reconcilable → merge
        """
        record = {
            "field": new_fact.field,
            "existing_value": existing_fact.value,
            "existing_confidence": existing_fact.confidence,
            "existing_reinforcements": existing_fact.times_reinforced,
            "new_value": new_fact.value,
            "new_confidence": new_fact.confidence,
            "new_reinforcements": new_fact.times_reinforced,
            "resolution": None,
            "reason": "",
        }

        existing_stable = self.thresholds.should_promote_to_stable(existing_fact)
        new_more_confident = new_fact.confidence > existing_fact.confidence + 0.15
        confidence_gap = abs(new_fact.confidence - existing_fact.confidence)

        if existing_stable and not new_more_confident:
            record["resolution"] = ContradictionResult.REJECTED_KEEP_EXISTING
            record["reason"] = (
                f"Existing fact is stable (confidence={existing_fact.confidence:.2f}, "
                f"reinforced={existing_fact.times_reinforced}x). "
                f"New confidence ({new_fact.confidence:.2f}) insufficient to override."
            )
        elif new_more_confident:
            record["resolution"] = ContradictionResult.OVERWRITE_ACCEPTED
            record["reason"] = (
                f"New fact has significantly higher confidence "
                f"({new_fact.confidence:.2f} vs {existing_fact.confidence:.2f}). "
                f"Existing fact superseded."
            )
        elif confidence_gap < 0.1:
            record["resolution"] = ContradictionResult.PENDING_REVIEW
            record["reason"] = (
                f"Both facts have comparable confidence "
                f"({new_fact.confidence:.2f} vs {existing_fact.confidence:.2f}). "
                f"Pending review."
            )
        else:
            record["resolution"] = ContradictionResult.REJECTED_KEEP_EXISTING
            record["reason"] = (
                f"Existing fact has higher confidence and comparable reinforcement."
            )

        self._conflict_log.append(record)
        return record["resolution"]

    def conflict_log(self) -> List[Dict[str, Any]]:
        return list(self._conflict_log)
