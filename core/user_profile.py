"""
core/user_profile.py

User Knowledge — structured profiles about the user maintained by the runtime.

IdentityOS should never need to "remember" user facts via memory retrieval.
Instead, it maintains canonical user profile objects that are updated in
real-time as the user reveals information about themselves.

Example:
  user.preferences.favorite_color = "red"
  user.name = "Alice"
  user.preferences.drink = "coffee"

The runtime answers from structured knowledge, not luck.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class EvidenceRecord:
    value: Any
    source_turn: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    turn_index: int = 0


@dataclass
class UserFact:
    fact_id: str
    field: str                           # e.g. "preferences.favorite_color"
    value: Any                           # e.g. "red" — the winner (or None if uncertain)
    confidence: float = 0.7
    source_conversation: str = ""        # most recent source
    last_confirmed: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    first_seen: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    times_mentioned: int = 1
    evidence: List[EvidenceRecord] = field(default_factory=list)
    contradictions: int = 0              # count of contradictory reports
    uncertain: bool = False              # True when evidence is contradictory

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fact_id": self.fact_id,
            "field": self.field,
            "value": self.value,
            "confidence": self.confidence,
            "source_conversation": self.source_conversation,
            "last_confirmed": self.last_confirmed,
            "first_seen": self.first_seen,
            "times_mentioned": self.times_mentioned,
            "evidence": [
                {"value": e.value, "source_turn": e.source_turn,
                 "timestamp": e.timestamp, "turn_index": e.turn_index}
                for e in self.evidence
            ],
            "contradictions": self.contradictions,
            "uncertain": self.uncertain,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserFact":
        evidence = [
            EvidenceRecord(
                value=e["value"],
                source_turn=e.get("source_turn", ""),
                timestamp=e.get("timestamp", ""),
                turn_index=e.get("turn_index", 0),
            )
            for e in data.get("evidence", [])
        ]
        return cls(
            fact_id=data.get("fact_id", str(uuid.uuid4())),
            field=data.get("field", ""),
            value=data.get("value"),
            confidence=data.get("confidence", 0.7),
            source_conversation=data.get("source_conversation", ""),
            last_confirmed=data.get("last_confirmed",
                                    datetime.now(timezone.utc).isoformat()),
            first_seen=data.get("first_seen",
                                datetime.now(timezone.utc).isoformat()),
            times_mentioned=data.get("times_mentioned", 1),
            evidence=evidence,
            contradictions=data.get("contradictions", 0),
            uncertain=data.get("uncertain", False),
        )


class UserProfile:
    """
    Structured knowledge about the user, maintained by the runtime.

    Separately persisted from identity facts so user knowledge survives
    identity package updates.
    """

    def __init__(self, user_id: str = "default"):
        self.user_id = user_id
        self._facts: Dict[str, UserFact] = {}

    def _compute_confidence(self, evidence: List[EvidenceRecord]) -> float:
        """Bayesian-ish: evidence weight increases confidence, contradictions reduce it."""
        n = len(evidence)
        if n == 0:
            return 0.3
        unique_values = len(set(str(e.value) for e in evidence))
        if unique_values > 1:
            decay = 0.15 * (unique_values - 1)
            return max(0.1, 0.7 - decay)
        # Reinforcement: each additional confirmation increases confidence
        # First evidence starts at 0.7, each reinforcement adds 0.05
        return min(1.0, 0.65 + (0.05 * n))

    def add_or_update(self, field: str, value: Any,
                      source: str = "", confidence: Optional[float] = None) -> UserFact:
        existing = self._facts.get(field)
        now = datetime.now(timezone.utc).isoformat()
        evidence_record = EvidenceRecord(
            value=value,
            source_turn=source,
            timestamp=now,
            turn_index=len(self._facts),
        )
        if existing:
            existing.evidence.append(evidence_record)
            existing.times_mentioned += 1
            existing.last_confirmed = now
            unique_values = set(str(e.value) for e in existing.evidence)
            if len(unique_values) > 1:
                existing.contradictions += 1
                existing.uncertain = True
                existing.confidence = self._compute_confidence(existing.evidence)
                if source:
                    existing.source_conversation = source
                return existing
            # All evidence agrees
            existing.value = value
            existing.uncertain = False
            existing.confidence = self._compute_confidence(existing.evidence)
            if source:
                existing.source_conversation = source
            return existing
        computed = self._compute_confidence([evidence_record])
        fact = UserFact(
            fact_id=str(uuid.uuid4()),
            field=field,
            value=value,
            confidence=confidence if confidence is not None else computed,
            source_conversation=source,
            evidence=[evidence_record],
        )
        self._facts[field] = fact
        return fact

    def get(self, field: str) -> Optional[UserFact]:
        return self._facts.get(field)

    def get_value(self, field: str) -> Any:
        fact = self._facts.get(field)
        return fact.value if fact else None

    def all_facts(self) -> List[UserFact]:
        return list(self._facts.values())

    def has_field(self, field: str) -> bool:
        return field in self._facts

    def to_prompt_block(self) -> str:
        if not self._facts:
            return ""
        lines = ["## User Profile"]
        for fact in self._facts.values():
            label = fact.field.replace("_", " ").replace(".", " → ")
            if fact.uncertain:
                lines.append(f"  User's {label}: (uncertain — contradictory reports)")
            else:
                certainty = " (high confidence)" if fact.confidence > 0.85 else ""
                lines.append(f"  User's {label}: {fact.value}{certainty}")
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "facts": [f.to_dict() for f in self._facts.values()],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserProfile":
        profile = cls(user_id=data.get("user_id", "default"))
        for fd in data.get("facts", []):
            fact = UserFact.from_dict(fd)
            profile._facts[fact.field] = fact
        return profile

    def __len__(self) -> int:
        return len(self._facts)


# ─── User knowledge extraction from conversation ──────────────────────────────

import re

# Patterns for user self-disclosure
USER_MY_PREFERENCE = re.compile(
    r"""my\s+(?:favorite\s+)?(\w[\w\s]*?)\s+is\s+(.+?)(?=\s+and\s+(?:my|I)|[.,!?]|$)""",
    re.IGNORECASE,
)

USER_MY_NAME = re.compile(
    r"""my\s+name\s+is\s+(.+?)(?=\s+and\s+my|[.,!?]|$)""",
    re.IGNORECASE,
)

USER_I_LIKE = re.compile(
    r"""I\s+(?:really\s+|definitely\s+)?
        (?:like|love|prefer|enjoy|favor|am\s+into|am\s+fond\s+of)
        \s+(.+?)(?=\s+and\s+I|[.,!?]|$)""",
    re.IGNORECASE | re.VERBOSE,
)

USER_I_DISLIKE = re.compile(
    r"""I\s+don't\s+(?:like|enjoy|prefer|love)
        \s+(.+?)(?=\s+and\s+I|[.,!?]|$)""",
    re.IGNORECASE | re.VERBOSE,
)

USER_MY_RELATIONSHIP = re.compile(
    r"""(\w[\w\s]*?)\s+is\s+my\s+(nephew|niece|son|daughter|brother|sister|mother|father|parent|aunt|uncle|cousin|grandmother|grandfather|friend|colleague|boss|manager|coworker|neighbor|roommate|partner|spouse|husband|wife|boyfriend|girlfriend|roommate|teammate|classmate)\b""",
    re.IGNORECASE | re.VERBOSE,
)

USER_PERSON_RELATIONSHIP = re.compile(
    r"""(\w[\w\s]*?)\s+is\s+(\w[\w\s]*?)'s\s+(nephew|niece|son|daughter|brother|sister|mother|father|parent|aunt|uncle|cousin|grandmother|grandfather|friend|colleague|spouse|husband|wife|partner|boyfriend|girlfriend|roommate|neighbor|classmate)\b""",
    re.IGNORECASE | re.VERBOSE,
)

USER_COLOR_HINTS = {
    "red", "blue", "green", "yellow", "purple", "orange", "pink", "brown",
    "black", "white", "gray", "grey", "teal", "cyan", "magenta", "lime",
    "indigo", "violet", "gold", "silver", "navy", "turquoise", "coral",
}


def extract_user_facts(user_input: str, turn_index: int = 0) -> List[UserFact]:
    """
    Extract structured user facts from a user's message.
    Returns UserFact objects without storing them.
    Deduplicates overlapping field matches (e.g. "my name is X" caught by both patterns).
    """
    seen_fields: set = set()
    facts: List[UserFact] = []

    def _add(field: str, value: str, confidence: float = 0.7, source: str = "") -> None:
        if field in seen_fields:
            return
        seen_fields.add(field)
        now = datetime.now(timezone.utc).isoformat()
        facts.append(UserFact(
            fact_id=str(uuid.uuid4()),
            field=field,
            value=value,
            confidence=confidence,
            source_conversation=source or user_input,
            evidence=[EvidenceRecord(
                value=value,
                source_turn=source or user_input,
                timestamp=now,
                turn_index=turn_index,
            )],
        ))

    # "My name is X"
    for m in USER_MY_NAME.finditer(user_input):
        _add(
            field="name",
            value=m.group(1).strip().rstrip(".,!?"),
            confidence=0.9,
        )

    # "My favorite X is Y" — skip if subject is "name" (handled above)
    for m in USER_MY_PREFERENCE.finditer(user_input):
        subject = m.group(1).strip().lower()
        if subject == "name":
            continue
        value = m.group(2).strip()
        is_color = value.lower().rstrip(".,!?") in USER_COLOR_HINTS
        field = f"preferences.{subject}" if not is_color else "preferences.favorite_color"
        _add(
            field=field,
            value=value.rstrip(".,!?"),
            confidence=0.9,
        )

    # "I like X"
    for m in USER_I_LIKE.finditer(user_input):
        value = m.group(1).strip().rstrip(".,!?")
        field = f"preferences.likes.{value.lower().replace(' ', '_')}"
        _add(field=field, value=value, confidence=0.8)

    # "I don't like X"
    for m in USER_I_DISLIKE.finditer(user_input):
        value = m.group(1).strip().rstrip(".,!?")
        field = f"preferences.dislikes.{value.lower().replace(' ', '_')}"
        _add(field=field, value=value, confidence=0.8)

    # "X is my Y" — direct relationships (e.g. "Alice is my sister")
    for m in USER_MY_RELATIONSHIP.finditer(user_input):
        name = m.group(1).strip().rstrip(".,!?")
        rel = m.group(2).strip().lower()
        field = f"relationships.{rel}"
        _add(field=field, value=name, confidence=0.9)

    # "X is Y's Z" — person-to-person relationships (e.g. "Bob is Alice's husband")
    for m in USER_PERSON_RELATIONSHIP.finditer(user_input):
        person_a = m.group(1).strip().rstrip(".,!?")
        person_b = m.group(2).strip().rstrip(".,!?")
        rel = m.group(3).strip().lower()
        field = f"relationships.{rel}.of_{person_b.lower()}"
        _add(field=field, value=person_a, confidence=0.85)

    return facts
