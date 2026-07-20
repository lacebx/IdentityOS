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
class UserFact:
    fact_id: str
    field: str                           # e.g. "preferences.favorite_color"
    value: Any                           # e.g. "red"
    confidence: float = 0.7
    source_conversation: str = ""        # what the user said
    last_confirmed: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    first_seen: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    times_mentioned: int = 1

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
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserFact":
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

    def add_or_update(self, field: str, value: Any,
                      source: str = "", confidence: float = 0.7) -> UserFact:
        existing = self._facts.get(field)
        if existing:
            if existing.value == value:
                existing.times_mentioned += 1
                existing.last_confirmed = datetime.now(timezone.utc).isoformat()
                existing.confidence = min(1.0, existing.confidence + 0.05)
            else:
                existing.value = value
                existing.times_mentioned = 1
                existing.last_confirmed = datetime.now(timezone.utc).isoformat()
                existing.confidence = confidence
            if source:
                existing.source_conversation = source
            return existing
        fact = UserFact(
            fact_id=str(uuid.uuid4()),
            field=field,
            value=value,
            confidence=confidence,
            source_conversation=source,
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
            lines.append(f"  {label}: {fact.value}")
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
    r"""my\s+(?:favorite\s+)?(\w[\w\s]*?)\s+is\s+(.+?)(?:[.,!?]|$)""",
    re.IGNORECASE,
)

USER_I_LIKE = re.compile(
    r"""I\s+(?:really\s+|definitely\s+)?
        (?:like|love|prefer|enjoy|favor|am\s+into|am\s+fond\s+of)
        \s+(.+?)(?:[.,!?]|$)""",
    re.IGNORECASE | re.VERBOSE,
)

USER_I_DISLIKE = re.compile(
    r"""I\s+don't\s+(?:like|enjoy|prefer|love)
        \s+(.+?)(?:[.,!?]|$)""",
    re.IGNORECASE | re.VERBOSE,
)

USER_NAME = re.compile(
    r"""my\s+name\s+is\s+(.+?)(?:[.,!?]|$)""",
    re.IGNORECASE,
)

USER_COLOR_HINTS = {
    "red", "blue", "green", "yellow", "purple", "orange", "pink", "brown",
    "black", "white", "gray", "grey", "teal", "cyan", "magenta", "lime",
    "indigo", "violet", "gold", "silver", "navy", "turquoise", "coral",
}


def extract_user_facts(user_input: str) -> List[UserFact]:
    """
    Extract structured user facts from a user's message.
    Returns UserFact objects without storing them.
    """
    facts: List[UserFact] = []

    # "My name is X"
    for m in USER_NAME.finditer(user_input):
        facts.append(UserFact(
            fact_id=str(uuid.uuid4()),
            field="name",
            value=m.group(1).strip().rstrip(".,!?"),
            source_conversation=user_input,
        ))

    # "My favorite X is Y"
    for m in USER_MY_PREFERENCE.finditer(user_input):
        subject = m.group(1).strip().lower()
        value = m.group(2).strip()
        is_color = value.lower().rstrip(".,!?") in USER_COLOR_HINTS
        field = f"preferences.{subject}" if not is_color else "preferences.favorite_color"
        facts.append(UserFact(
            fact_id=str(uuid.uuid4()),
            field=field,
            value=value.rstrip(".,!?"),
            confidence=0.9,
            source_conversation=user_input,
        ))

    # "I like X"
    for m in USER_I_LIKE.finditer(user_input):
        value = m.group(1).strip().rstrip(".,!?")
        field = f"preferences.likes.{value.lower().replace(' ', '_')}"
        facts.append(UserFact(
            fact_id=str(uuid.uuid4()),
            field=field,
            value=value,
            confidence=0.8,
            source_conversation=user_input,
        ))

    # "I don't like X"
    for m in USER_I_DISLIKE.finditer(user_input):
        value = m.group(1).strip().rstrip(".,!?")
        field = f"preferences.dislikes.{value.lower().replace(' ', '_')}"
        facts.append(UserFact(
            fact_id=str(uuid.uuid4()),
            field=field,
            value=value,
            confidence=0.8,
            source_conversation=user_input,
        ))

    return facts
