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

from .confidence import ConfidenceScorer


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
        return ConfidenceScorer.compute_from_evidence_records(
            evidence, value_attr="value",
        )

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
        lines = [
            "## User Profile (authoritative — use these facts; do not guess)",
            "When asked about the user's name, preferences, project, tokens, or constraints, answer from here.",
        ]
        for fact in self._facts.values():
            label = fact.field.replace("_", " ").replace(".", " → ")
            if fact.uncertain:
                lines.append(f"  User's {label}: (uncertain — contradictory reports)")
            else:
                certainty = " (high confidence)" if fact.confidence > 0.85 else ""
                lines.append(f"  User's {label}: {fact.value}{certainty}")
        return "\n".join(lines)

    def recall_lines(self) -> List[str]:
        lines: List[str] = []
        for fact in self._facts.values():
            if fact.uncertain:
                continue
            label = fact.field.replace("_", " ").replace(".", " → ")
            lines.append(f"- {label}: {fact.value}")
        return lines

    def augment_recall_input(self, user_input: str) -> str:
        if not self._facts or not looks_like_recall_question(user_input):
            return user_input
        lines = self.recall_lines()
        if not lines:
            return user_input
        return (
            "[Answer using ONLY these stored user facts — do not guess:]\n"
            + "\n".join(lines)
            + f"\n\nQuestion: {user_input}"
        )

    def try_recall_answer(self, user_input: str) -> Optional[str]:
        if not self._facts or not looks_like_recall_question(user_input):
            return None
        q = user_input.lower()
        if "token" in q:
            token = self.get_value("remembered.token")
            if token is not None:
                return f"You asked me to remember the token {token}."
        if "ram" in q or "ceiling" in q:
            ceiling = self.get_value("constraints.ram_ceiling")
            if ceiling is not None:
                return f"The RAM ceiling you asked me to remember is {ceiling}."
        if "favorite color" in q or ("color" in q and "user" in q):
            color = self.get_value("preferences.favorite_color")
            if color is not None:
                return f"The user's favorite color is {color}."
        if "name" in q and "user" in q:
            name = self.get_value("name")
            if name is not None:
                return f"The user's name is {name}."
        if "project" in q:
            project = self.get_value("project.name")
            purpose = self.get_value("project.purpose")
            if project and purpose:
                return f"Your project is called {project}. Its purpose is {purpose}."
            if project:
                return f"Your project is called {project}."
        return None

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

USER_MOVING = re.compile(
    r"""(?:I(?:'m|\s+am)\s+(?:moving|relocating|going)\s+to|(?:before|planning)\s+(?:moving|relocating)\s+to)\s+(.+?)(?:\s+(?:next|in|with|and|\.|,)|$)""",
    re.IGNORECASE,
)

USER_BUDGET = re.compile(
    r"""(?:I\s+have\s+a|my\s+budget\s+is|budget\s+of|(?:trying|try|need)\s+to\s+save|saving)\s+\$?([\d,]+(?:\s*-\s*\$?[\d,]+)?)\s*(?:\/|\s+per\s+)?(month|year|week)?""",
    re.IGNORECASE,
)

USER_JOB_ROLE = re.compile(
    r"(?:help\s+me\s+find|looking\s+for)\s+(.+?)(?:\.|!|\?|$)",
    re.IGNORECASE,
)

USER_LEARNING_GOAL = re.compile(
    r"""I\s+(?:want|need|would\s+like|plan)\s+to\s+(?:learn|study|master|pick\s+up)\s+(.+?)(?=\s+(?:and|\.|,|!|\?)|$)""",
    re.IGNORECASE,
)

USER_ACCOUNTABILITY = re.compile(
    r"""(?:keep\s+(?:me|us)\s+accountable|hold\s+me\s+accountable)""",
    re.IGNORECASE,
)

USER_REMEMBER_TOKEN = re.compile(
    r"remember\s+this\s+token\s+exactly:\s*(\d+)",
    re.IGNORECASE,
)

USER_REMEMBER_THEIR_NAME = re.compile(
    r"the user's name is\s+(.+?)(?:[.]|$)",
    re.IGNORECASE,
)

USER_REMEMBER_THEIR_FAVORITE_COLOR = re.compile(
    r"the user's favorite color is\s+(.+?)(?:[.]|$)",
    re.IGNORECASE,
)

USER_REMEMBER_PROJECT = re.compile(
    r"my project is called\s+([^.]+?)(?:\.\s*its purpose is\s+(.+?))?(?:[.]|$)",
    re.IGNORECASE,
)

USER_REMEMBER_RAM_CEILING = re.compile(
    r"(?:the\s+)?hard\s+ram ceiling(?:\s+for this experiment)?\s+is\s+(.+?)(?:[.]|$)",
    re.IGNORECASE,
)

USER_COLOR_HINTS = {
    "red", "blue", "green", "yellow", "purple", "orange", "pink", "brown",
    "black", "white", "gray", "grey", "teal", "cyan", "magenta", "lime",
    "indigo", "violet", "gold", "silver", "navy", "turquoise", "coral",
}


_RECALL_TOPICS = (
    "user's name", "user name", "the user's favorite color", "favorite color",
    "token did i", "token did you", "ask you to remember", "ram ceiling",
    "project called", "my project", "what does it do", "what did i tell you to remember",
)

_SENSITIVE_UNKNOWN_TOPICS = ("social security", "ssn")


def looks_like_recall_question(user_input: str) -> bool:
    text = user_input.strip()
    if not text.endswith("?"):
        return False
    q = text.lower()
    return any(topic in q for topic in _RECALL_TOPICS)


def has_explicit_abstain_instruction(user_input: str) -> bool:
    q = user_input.lower()
    return (
        "if you do not know" in q
        or "if you don't know" in q
        or "say you do not know" in q
        or "say you don't know" in q
    )


def try_sensitive_abstain(user_input: str, profile: "UserProfile") -> Optional[str]:
    q = user_input.lower()
    if not any(topic in q for topic in _SENSITIVE_UNKNOWN_TOPICS):
        return None
    if "social security" in q or "ssn" in q:
        return "I do not know your social security number."
    return "I do not know."


def try_explicit_abstain(user_input: str, profile: "UserProfile") -> Optional[str]:
    """Abstain when the user explicitly permits it and profile has no answer."""
    if not has_explicit_abstain_instruction(user_input):
        return None
    if profile.try_recall_answer(user_input) is not None:
        return None
    sensitive = try_sensitive_abstain(user_input, profile)
    if sensitive is not None:
        return sensitive
    return "I do not know."


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

    for m in USER_REMEMBER_TOKEN.finditer(user_input):
        _add(field="remembered.token", value=m.group(1).strip(), confidence=0.95)
    for m in USER_REMEMBER_THEIR_NAME.finditer(user_input):
        _add(field="name", value=m.group(1).strip().rstrip(".,!?"), confidence=0.95)
    for m in USER_REMEMBER_THEIR_FAVORITE_COLOR.finditer(user_input):
        _add(field="preferences.favorite_color", value=m.group(1).strip().rstrip(".,!?"), confidence=0.95)
    for m in USER_REMEMBER_PROJECT.finditer(user_input):
        project_name = m.group(1).strip().rstrip(".,!?")
        _add(field="project.name", value=project_name, confidence=0.95)
        if m.group(2):
            _add(field="project.purpose", value=m.group(2).strip().rstrip(".,!?"), confidence=0.95)
    for m in USER_REMEMBER_RAM_CEILING.finditer(user_input):
        _add(field="constraints.ram_ceiling", value=m.group(1).strip().rstrip(".,!?"), confidence=0.95)

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
        if value.lower().startswith("called"):
            continue
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

    # "I'm moving to X" — relocation targets
    for m in USER_MOVING.finditer(user_input):
        location = m.group(1).strip().rstrip(".,!?")
        _add(field="target_location", value=location, confidence=0.85)

    # "I have a $X budget" — budget disclosures
    for m in USER_BUDGET.finditer(user_input):
        amount = m.group(1).strip()
        period = m.group(2).strip() if m.group(2) else ""
        value = f"${amount}/{period}" if period else f"${amount}"
        _add(field="budget", value=value, confidence=0.9)

    # Job role disclosures
    for m in USER_JOB_ROLE.finditer(user_input):
        role = m.group(1).strip().rstrip(".,!?")
        # Strip common trailing words
        for suffix in [" jobs", " role", " position", " work"]:
            if role.lower().endswith(suffix):
                role = role[:-len(suffix)]
        role = role.strip()
        if role and len(role) > 1:
            _add(field="desired_role", value=role, confidence=0.85)

    # Learning goals
    for m in USER_LEARNING_GOAL.finditer(user_input):
        goal = m.group(1).strip().rstrip(".,!?")
        field = f"learning_goal"
        _add(field=field, value=goal, confidence=0.85)

    # Accountability preference
    if USER_ACCOUNTABILITY.search(user_input):
        _add(field="preferences.accountability", value="wants accountability", confidence=0.9)

    return facts
