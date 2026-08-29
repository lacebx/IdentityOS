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
        query_terms = _semantic_terms(user_input, query=True)
        broad_recall = bool(_BROAD_RECALL.search(user_input))
        ranked: List[tuple[int, UserFact]] = []
        for fact in self._facts.values():
            if fact.uncertain:
                continue
            field_terms = _semantic_terms(fact.field)
            overlap = query_terms & field_terms
            if overlap:
                ranked.append((len(overlap), fact))
            elif broad_recall and not query_terms:
                ranked.append((1, fact))
        if not ranked:
            return None
        best_score = max(score for score, _ in ranked)
        matches = [fact for score, fact in ranked if score == best_score]
        if len(matches) == 1:
            fact = matches[0]
            return f"Your {_readable_field(fact.field)} is {fact.value}."
        lines = ["I have these stored user facts:"]
        for fact in matches:
            lines.append(f"- {_readable_field(fact.field)}: {fact.value}")
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
    r"""my\s+(?:(favorite|favourite)\s+)?(\w[\w\s]*?)\s+is\s+(.+?)(?=\s+and\s+(?:my|I)|[.,!?]|$)""",
    re.IGNORECASE,
)

USER_MY_NAME = re.compile(
    r"""my\s+name\s+is\s+(.+?)(?=\s+and\s+(?:my|I)\b|[.,!?]|$)""",
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

_REMEMBER_DIRECTIVE = re.compile(
    r"\b(?:please\s+)?remember(?:\s+that)?\s*:?\s*(?P<body>.+)$",
    re.IGNORECASE | re.DOTALL,
)
_FACT_RELATION = re.compile(
    r"^(?P<label>.+?)\s*(?P<connector>\bis\s+called\b|\bis\b|\bare\b|=|:)\s*(?P<value>.+)$",
    re.IGNORECASE,
)
_COLLECTION_HEADER = re.compile(
    r"^(?P<label>(?:these\s+|the\s+)?(?:one|two|three|four|five|six|seven|eight|nine|ten|\d+)?\s*[\w' -]+):\s*(?P<items>.+)$",
    re.IGNORECASE | re.DOTALL,
)
_RECALL_FORM = re.compile(
    r"(?:\b(?:remember|recall|stored|told|tell)\b"
    r"|\b(?:do|did)\s+you\s+know\b"
    r"|\b(?:what|which|who|where|when)\b.*\b(?:my|our|user'?s)\b)",
    re.IGNORECASE,
)
_BROAD_RECALL = re.compile(
    r"\bwhat\s+did\s+i\s+(?:ask\s+you\s+to\s+remember|tell\s+you)\b",
    re.IGNORECASE,
)
_SENSITIVE_UNKNOWN_TOPICS = (
    "social security", "ssn", "government id", "password", "passcode",
    "credit card", "bank account",
)

_TERM_STOPWORDS = {
    "a", "an", "and", "are", "ask", "called", "did", "do", "does", "for",
    "have", "i", "is", "it", "me", "my", "of", "our", "please", "remember",
    "stored", "tell", "told", "the", "this", "to", "user", "users", "was", "what",
    "when", "where", "which", "who", "you", "your", "exactly", "hard",
    "favorite", "favourite", "item",
}
_FIELD_NAMESPACES = {
    "remembered", "preferences", "preference", "attributes", "attribute",
}


def _normalized_word(word: str) -> str:
    word = word.lower().replace("colour", "color")
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        word = word[:-1]
    return word


def _semantic_terms(text: str, *, query: bool = False) -> set[str]:
    normalized = text.replace(".", " ").replace("_", " ").replace("'s", "")
    words = {_normalized_word(word) for word in re.findall(r"[A-Za-z0-9]+", normalized)}
    stopwords = _TERM_STOPWORDS | (_FIELD_NAMESPACES if not query else set())
    return {word for word in words if word not in stopwords and not word.isdigit()}


def _slug(text: str) -> str:
    return "_".join(re.findall(r"[a-z0-9]+", text.lower().replace("colour", "color")))


def _normalize_explicit_field(
    label: str,
    *,
    connector: str = "",
    prior_field: str = "",
) -> str:
    raw = label.strip().lower().replace("’", "'")
    raw = re.sub(r"^(?:the\s+)?user'?s\s+|^(?:my|our|this|the)\s+", "", raw)
    raw = re.sub(r"^(?:its)\s+", "", raw)
    raw = re.sub(r"\b(?:exactly|hard)\b", "", raw)
    raw = re.sub(r"\s+", " ", raw).strip()
    slug = _slug(raw)
    if slug in {"name", "full_name"}:
        return "name"
    if slug.startswith(("favorite_", "favourite_")):
        suffix = re.sub(r"^(?:favorite|favourite)_", "", slug)
        return f"preferences.favorite_{suffix}"
    if slug == "project" and "called" in connector.lower():
        return "project.name"
    if slug == "purpose" and prior_field.startswith("project."):
        return "project.purpose"
    if any(term in slug.split("_") for term in ("constraint", "ceiling", "limit")):
        return f"constraints.{slug}"
    return f"remembered.{slug or 'fact'}"


def _readable_field(field: str) -> str:
    parts = [part for part in field.split(".") if part not in _FIELD_NAMESPACES]
    label = " ".join(parts).replace("_", " ")
    label = re.sub(r"\bitem\s+(\d+)\b", r"item \1", label)
    return label or "stored fact"


def _extract_explicit_remembered_facts(user_input: str) -> List[tuple[str, str]]:
    match = _REMEMBER_DIRECTIVE.search(user_input)
    if not match:
        return []
    body = match.group("body").strip()
    collection = _COLLECTION_HEADER.match(body)
    if collection:
        items = [
            re.sub(r"^and\s+", "", item.strip(), flags=re.IGNORECASE).strip(" .")
            for item in re.split(r"\s*,\s*|\s+and\s+", collection.group("items"))
            if item.strip().strip(" .")
        ]
        label = collection.group("label").strip()
        label_terms = _semantic_terms(label)
        if len(items) > 1 and (label_terms or re.search(r"\b\d+\b", label)):
            namespace = "constraints" if "constraint" in label_terms else f"remembered.{_slug(label)}"
            return [(f"{namespace}.item_{index}", value) for index, value in enumerate(items, 1)]

    clauses = [
        clause.strip()
        for clause in re.split(r"(?<=[.;])\s+|\s+and\s+(?=(?:my|our|the\s+user'?s|its)\b)", body)
        if clause.strip()
    ]
    extracted: List[tuple[str, str]] = []
    prior_field = ""
    for clause in clauses:
        relation = _FACT_RELATION.match(clause.strip().strip(" ."))
        if not relation:
            continue
        field = _normalize_explicit_field(
            relation.group("label"),
            connector=relation.group("connector"),
            prior_field=prior_field,
        )
        value = relation.group("value").strip().strip(" .,!?")
        if field and value:
            extracted.append((field, value))
            prior_field = field
    return extracted


def looks_like_recall_question(user_input: str) -> bool:
    text = user_input.strip()
    is_question = text.endswith("?")
    is_recall_command = bool(re.match(r"^(?:list|recall|remind|show|tell)\b", text, re.IGNORECASE))
    if not is_question and not is_recall_command:
        return False
    return bool(_RECALL_FORM.search(text))


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
    return "I do not know that sensitive value."


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
    seen_claims: set = set()
    facts: List[UserFact] = []

    def _add(field: str, value: str, confidence: float = 0.7, source: str = "") -> None:
        claim = (frozenset(_semantic_terms(field)), str(value).strip().casefold())
        if field in seen_fields or claim in seen_claims:
            return
        seen_fields.add(field)
        seen_claims.add(claim)
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

    for field, value in _extract_explicit_remembered_facts(user_input):
        _add(field=field, value=value, confidence=0.95)

    # "My name is X"
    for m in USER_MY_NAME.finditer(user_input):
        _add(
            field="name",
            value=m.group(1).strip().rstrip(".,!?"),
            confidence=0.9,
        )

    # "My [favorite] X is Y" — preferences and general attributes
    for m in USER_MY_PREFERENCE.finditer(user_input):
        is_favorite = bool(m.group(1))
        subject = m.group(2).strip().lower()
        if subject == "name":
            continue
        value = m.group(3).strip()
        if value.lower().startswith("called"):
            continue
        field = (
            f"preferences.favorite_{_slug(subject)}"
            if is_favorite
            else f"attributes.{_slug(subject)}"
        )
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
