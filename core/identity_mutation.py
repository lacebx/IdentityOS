"""
core/identity_mutation.py

Identity Mutation Engine — the module responsible for detecting when an
identity's own attributes (preferences, beliefs, traits, etc.) should evolve
based on conversation.

Produces canonical IdentityFact objects (not raw text) — each fact has
structured metadata: value, confidence, reasons, evidence references, and status.

This is NOT memory extraction. This is identity evolution detection.

The detection is deliberate: one conversation should NOT permanently mutate
identity. Facts accumulate confidence through reinforcement. Stable identity
requires evidence, not single utterances.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from .identity_facts import (
    FactDomain,
    FactSource,
    FactStatus,
    FactStore,
    IdentityFact,
    EvolutionThresholds,
    ContradictionEngine,
    ContradictionResult,
)


# ─── Mutation Types ────────────────────────────────────────────────────────────


class MutationType(str, Enum):
    PREFERENCE_ADOPTED = "preference_adopted"
    PREFERENCE_CHANGED = "preference_changed"
    BELIEF_ADOPTED = "belief_adopted"
    BELIEF_CHANGED = "belief_changed"
    TRAIT_EVOLVED = "trait_evolved"
    TRUST_EVOLVED = "trust_evolved"
    COMMUNICATION_EVOLVED = "communication_evolved"
    HABIT_NOTED = "habit_noted"
    LIKE_ADDED = "like_added"
    DISLIKE_ADDED = "dislike_added"


class MutationStatus(str, Enum):
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    CONFLICT = "conflict"


# ─── Data Classes ──────────────────────────────────────────────────────────────


@dataclass
class MutationProposal:
    """
    A structured proposal representing a detected identity evolution opportunity.
    The engine proposes; the runtime validates and decides.

    Produces a canonical IdentityFact on acceptance.
    """

    mutation_id: str
    mutation_type: MutationType
    field: str
    old_value: Any
    new_value: Any
    confidence: float
    reason: str
    reasons: List[str]
    source_text: str
    conversation_context: str
    proposed_at: str
    status: MutationStatus = MutationStatus.PROPOSED
    rejection_reason: str = ""

    def to_fact(self, evidence_id: str = "") -> IdentityFact:
        domain_map = {
            MutationType.PREFERENCE_ADOPTED: FactDomain.PREFERENCE,
            MutationType.PREFERENCE_CHANGED: FactDomain.PREFERENCE,
            MutationType.BELIEF_ADOPTED: FactDomain.BELIEF,
            MutationType.BELIEF_CHANGED: FactDomain.BELIEF,
            MutationType.TRAIT_EVOLVED: FactDomain.TRAIT,
            MutationType.TRUST_EVOLVED: FactDomain.RELATIONSHIP,
            MutationType.COMMUNICATION_EVOLVED: FactDomain.COMMUNICATION,
            MutationType.HABIT_NOTED: FactDomain.HABIT,
            MutationType.LIKE_ADDED: FactDomain.PREFERENCE,
            MutationType.DISLIKE_ADDED: FactDomain.PREFERENCE,
        }
        return IdentityFact(
            fact_id=str(uuid.uuid4()),
            domain=domain_map.get(self.mutation_type, FactDomain.PREFERENCE),
            field=self.field,
            value=self.new_value,
            confidence=self.confidence,
            reasons=self.reasons,
            source=FactSource.ASSISTANT_SELF,
            evidence_ids=[evidence_id] if evidence_id else [],
            first_seen=datetime.now(timezone.utc).isoformat(),
            last_confirmed=datetime.now(timezone.utc).isoformat(),
            times_reinforced=0,
            status=FactStatus.PENDING,
        )


@dataclass
class MutationRecord:
    """
    A permanent record of a processed mutation (accepted, rejected, or conflicted).
    """

    mutation_id: str
    mutation_type: MutationType
    field: str
    old_value: Any
    new_value: Any
    confidence: float
    reason: str
    source_text: str
    status: MutationStatus
    applied_at: str
    rejection_reason: str = ""
    resolved_conflict: bool = False


# ─── Regular Expression Patterns ──────────────────────────────────────────────

PREFERENCE_ADOPT = re.compile(
    r"""I\s+(?:really\s+|definitely\s+|absolutely\s+)?
        (?:like|love|prefer|enjoy|favor|adore|am\s+fond\s+of|am\s+into)
        \s+(.+?)(?:[.,!?]|$)""",
    re.IGNORECASE | re.VERBOSE,
)

FITS_ME_PATTERN = re.compile(
    r"""I\s+think\s+(.+?)\s+fits\s+me(?:[.,!?]|$)""",
    re.IGNORECASE | re.VERBOSE,
)

COLOR_IS_PATTERN = re.compile(
    r"""my\s+favorite\s+color\s+is\s+(.+?)(?:[.,!?]|$)""",
    re.IGNORECASE | re.VERBOSE,
)

FAVORITE_PATTERN = re.compile(
    r"""my\s+favorite\s+(\w[\w\s]*?)\s+is\s+(.+?)(?:[.,!?]|$)""",
    re.IGNORECASE | re.VERBOSE,
)

DISLIKE_PATTERN = re.compile(
    r"""I\s+(?:don't\s+|do\s+not\s+|no\s+longer\s+)
        (?:like|enjoy|prefer|love|favor|crave|want)
        (?:\s+(?:to|it|that|this))?
        \s*(.+?)(?:[.,!?]|$|anymore)""",
    re.IGNORECASE | re.VERBOSE,
)

BELIEF_PATTERN = re.compile(
    r"""I\s+(?:believe|think|feel|am\s+convinced|consider|find)
        \s+(?:that\s+)?(.+?)(?:[.,!?]|$)""",
    re.IGNORECASE | re.VERBOSE,
)

TRAIT_EVOLVE = re.compile(
    r"""I\s+(?:have\s+|am\s+|feel\s+|grew|become|am\s+getting|am\s+learning\s+to\s+be)
        (?:become|grown|evolved|developed|learned)\s+
        more\s+(.+?)(?:[.,!?]|$)""",
    re.IGNORECASE | re.VERBOSE,
)

TRAIT_BECOME = re.compile(
    r"""I\s+(?:am|have\s+become|feel)\s+
        (?:more\s+|less\s+|very\s+|quite\s+)?
        (.+?)(?:[.,!?]|$)(?:\s+than\s+before)?""",
    re.IGNORECASE | re.VERBOSE,
)

TRUST_PATTERN = re.compile(
    r"""I\s+(?:trust|don't\s+trust|distrust|have\s+faith\s+in|believe\s+in)
        \s+(.+?)(?:[.,!?]|$)""",
    re.IGNORECASE | re.VERBOSE,
)

COMMUNICATION_PATTERN = re.compile(
    r"""I\s+(?:prefer|like|tend)\s+to\s+
        (?:communicate|speak|talk|express|write)\s+(.+?)(?:[.,!?]|$)""",
    re.IGNORECASE | re.VERBOSE,
)


# ─── Color / trait hint dictionaries ─────────────────────────────────────────

COLOR_HINTS = {
    "red", "blue", "green", "yellow", "purple", "orange", "pink", "brown",
    "black", "white", "gray", "grey", "teal", "cyan", "magenta", "lime",
    "indigo", "violet", "gold", "silver", "navy", "turquoise", "coral",
    "maroon", "plum", "olive", "beige", "ivory", "tan", "crimson", "amber",
}

TRAIT_KEYWORDS = {
    "patient", "curious", "creative", "analytical", "empathetic", "cautious",
    "bold", "thoughtful", "playful", "serious", "loyal", "independent",
    "adventurous", "protective", "witty", "strategic", "diplomatic",
    "direct", "patient", "persistent", "adaptable", "organized", "spontaneous",
    "introspective", "outgoing", "calm", "energetic", "focus", "discipline",
}


# ─── Helper: normalize detected subject to field path ──────────────────────


def _normalize_field(subject: str, detected: str) -> str:
    """
    Given a detected subject phrase, normalize to a dotted field path.
    E.g. "blue" → "preferences.favorite_color", "coffee" → "preferences.drink.coffee"
    """
    subj_lower = subject.strip().lower()
    det_lower = detected.strip().lower() if detected else ""

    # If detected mentions "color" explicitly
    if "color" in subj_lower or "color" in det_lower:
        return "preferences.favorite_color"

    # Colors — check the last word of detected value too (catches "blue fits me" → "blue")
    det_last_word = det_lower.split()[-1] if det_lower.split() else ""
    if det_lower in COLOR_HINTS or subj_lower in COLOR_HINTS or det_last_word in COLOR_HINTS:
        return "preferences.favorite_color"

    # Foods / drinks
    drink_keywords = {"coffee", "tea", "juice", "soda", "water", "wine", "beer", "milk"}
    food_keywords = {"pizza", "pasta", "chocolate", "cake", "fruit", "vegetable", "meat", "fish"}
    words = set(det_lower.split()) | set(subj_lower.split())
    if words & drink_keywords:
        return f"preferences.drink.{det_lower.replace(' ', '_')}"
    if words & food_keywords:
        return f"preferences.food.{det_lower.replace(' ', '_')}"

    # Music / hobby / activity
    hobby_keywords = {"music", "reading", "writing", "drawing", "painting",
                      "running", "swimming", "hiking", "cooking", "dancing",
                      "singing", "gaming", "travel", "photography"}
    if words & hobby_keywords:
        return f"preferences.hobby.{det_lower.replace(' ', '_')}"

    return f"preferences.general.{det_lower.replace(' ', '_')}"


def _normalize_trait(detected: str) -> str:
    """Map a detected trait phrase to a canonical trait name."""
    d = detected.strip().lower().rstrip(".,!?")
    # Find the best matching trait keyword
    for trait in sorted(TRAIT_KEYWORDS, key=len, reverse=True):
        if trait in d:
            return trait
    return d.replace(" ", "_")


# ─── IdentityMutationEngine ────────────────────────────────────────────────────


class IdentityMutationEngine:
    """
    Analyzes interaction output (the assistant's response) and detects
    opportunities for identity evolution.

    Returns structured MutationProposal objects. It does NOT apply any changes.
    """

    def __init__(
        self,
        min_confidence: float = 0.5,
        fact_store: Optional[FactStore] = None,
        thresholds: Optional[EvolutionThresholds] = None,
    ) -> None:
        self._min_confidence = min_confidence
        self._proposal_history: List[MutationProposal] = []
        self._fact_store = fact_store or FactStore()
        self._thresholds = thresholds or EvolutionThresholds()
        self._contradiction_engine = ContradictionEngine(
            thresholds=self._thresholds,
        )

    def analyze(
        self,
        user_input: str,
        assistant_response: str,
        identity_spec: Any,
    ) -> List[MutationProposal]:
        """
        Analyze an interaction turn and return all detected mutation proposals.

        Args:
            user_input: The user's message.
            assistant_response: The assistant's reply.
            identity_spec: The current IdentitySpec (used to check existing values).

        Returns:
            List of MutationProposal objects.
        """
        proposals: List[MutationProposal] = []

        proposals.extend(self._detect_preferences(assistant_response, identity_spec))
        proposals.extend(self._detect_beliefs(assistant_response, identity_spec))
        proposals.extend(self._detect_traits(assistant_response, identity_spec))
        proposals.extend(self._detect_trust(assistant_response, identity_spec))
        proposals.extend(self._detect_communication(assistant_response, identity_spec))

        for p in proposals:
            self._proposal_history.append(p)

        return proposals

    def _build_proposal(
        self,
        mutation_type: MutationType,
        field: str,
        new_value: Any,
        confidence: float,
        reason: str,
        source_text: str,
        identity_spec: Any,
        old_value: Any = None,
        reasons: Optional[List[str]] = None,
    ) -> MutationProposal:
        """Create a MutationProposal, detecting old_value from identity_spec."""
        if old_value is None:
            old_value = self._get_current_value(identity_spec, field)
        return MutationProposal(
            mutation_id=str(uuid.uuid4()),
            mutation_type=mutation_type,
            field=field,
            old_value=old_value,
            new_value=new_value,
            confidence=min(1.0, confidence),
            reason=reason,
            reasons=reasons or [reason],
            source_text=source_text,
            conversation_context=f"User: {source_text}",
            proposed_at=datetime.now(timezone.utc).isoformat(),
        )

    def _get_current_value(self, identity_spec: Any, field: str) -> Any:
        """Read a dotted field path from the identity spec."""
        if identity_spec is None:
            return None
        parts = field.split(".")
        obj = identity_spec
        for part in parts:
            if isinstance(obj, dict):
                obj = obj.get(part)
            else:
                obj = getattr(obj, part, None)
            if obj is None:
                return None
        return obj

    # ── Detection methods ──────────────────────────────────────────────────

    def _detect_preferences(
        self, text: str, identity_spec: Any
    ) -> List[MutationProposal]:
        proposals = []

        # Pattern: "My favorite X is Y"
        for m in FAVORITE_PATTERN.finditer(text):
            subject = m.group(1).strip()
            value = m.group(2).strip()
            field = _normalize_field(subject, value)
            proposals.append(self._build_proposal(
                mutation_type=MutationType.PREFERENCE_ADOPTED,
                field=field,
                new_value=value,
                confidence=0.93,
                reason=f"Assistant explicitly declared favorite {subject}.",
                source_text=m.group(0),
                identity_spec=identity_spec,
                reasons=[f"Explicitly declared favorite {subject}", f"Chose {value}"],
            ))

        # Pattern: "I like/love/prefer X"
        for m in PREFERENCE_ADOPT.finditer(text):
            value = m.group(1).strip()
            field = _normalize_field("", value)
            is_color = value.strip().lower().rstrip(".,!?") in COLOR_HINTS
            confidence = 0.88 if is_color else 0.80
            proposals.append(self._build_proposal(
                mutation_type=MutationType.PREFERENCE_ADOPTED,
                field=field,
                new_value=value.rstrip(".,!?"),
                confidence=confidence,
                reason=f"Assistant expressed a preference.",
                source_text=m.group(0),
                identity_spec=identity_spec,
                reasons=[f"Expressed liking {value.strip().lower()[:30]}"],
            ))

        # Pattern: "I think X fits me" (e.g. "I think blue fits me")
        for m in FITS_ME_PATTERN.finditer(text):
            value = m.group(1).strip()
            field = _normalize_field("", value)
            is_color = value.strip().lower().rstrip(".,!?").split()[-1] in COLOR_HINTS
            confidence = 0.88 if is_color else 0.80
            proposals.append(self._build_proposal(
                mutation_type=MutationType.PREFERENCE_ADOPTED,
                field=field,
                new_value=value.rstrip(".,!?"),
                confidence=confidence,
                reason=f"Assistant indicated a preference.",
                source_text=m.group(0),
                identity_spec=identity_spec,
                reasons=[f"Self-identified preference for {value.strip().lower()[:30]}"],
            ))

        # Pattern: "my favorite color is X"
        for m in COLOR_IS_PATTERN.finditer(text):
            value = m.group(1).strip()
            proposals.append(self._build_proposal(
                mutation_type=MutationType.PREFERENCE_ADOPTED,
                field="preferences.favorite_color",
                new_value=value.rstrip(".,!?"),
                confidence=0.95,
                reason=f"Assistant explicitly declared favorite color.",
                source_text=m.group(0),
                identity_spec=identity_spec,
                reasons=[f"Explicitly declared favorite color", f"Chose {value.strip().lower()[:20]}"],
            ))

        # Pattern: "I don't like / no longer enjoy X"
        for m in DISLIKE_PATTERN.finditer(text):
            value = m.group(1).strip()
            field = _normalize_field("", value)
            proposals.append(self._build_proposal(
                mutation_type=MutationType.PREFERENCE_CHANGED,
                field=field,
                new_value=False,
                confidence=0.85,
                reason=f"Assistant expressed disinterest or ceased preference.",
                source_text=m.group(0),
                identity_spec=identity_spec,
            ))

        return proposals

    def _detect_beliefs(
        self, text: str, identity_spec: Any
    ) -> List[MutationProposal]:
        proposals = []
        for m in BELIEF_PATTERN.finditer(text):
            statement = m.group(1).strip().rstrip(".,!?")
            if len(statement.split()) < 3:
                continue
            # Skip if it's actually a preference (handled above)
            if any(w in statement.lower() for w in ["like", "love", "prefer", "enjoy"]):
                continue
            # Skip if it's a "fits me" pattern (handled as preference)
            if re.search(r"fits\s+me", statement, re.IGNORECASE):
                continue
            # Skip if the statement is just a color
            if statement.strip().lower().rstrip(".,!?") in COLOR_HINTS:
                continue
            key = statement.lower().replace(" ", "_")[:40]
            proposals.append(self._build_proposal(
                mutation_type=MutationType.BELIEF_ADOPTED,
                field=f"beliefs.{key}",
                new_value=statement,
                confidence=0.78,
                reason=f"Assistant stated a belief or opinion.",
                source_text=m.group(0),
                identity_spec=identity_spec,
                reasons=[f"Stated belief: {statement[:60]}"],
            ))
        return proposals

    def _detect_traits(
        self, text: str, identity_spec: Any
    ) -> List[MutationProposal]:
        proposals = []

        # Pattern: "I have become more X"
        for m in TRAIT_EVOLVE.finditer(text):
            trait_raw = m.group(1).strip().rstrip(".,!?")
            trait_name = _normalize_trait(trait_raw)
            current = self._get_current_value(identity_spec, f"traits.{trait_name}")
            new_score = min(1.0, (current + 0.15) if isinstance(current, (int, float)) else 0.65)
            proposals.append(self._build_proposal(
                mutation_type=MutationType.TRAIT_EVOLVED,
                field=f"traits.{trait_name}",
                new_value={"score": new_score, "description": trait_raw},
                confidence=0.80,
                reason=f"Assistant described personal growth in '{trait_name}'.",
                source_text=m.group(0),
                identity_spec=identity_spec,
                reasons=[f"Described growth in '{trait_name}'"],
            ))

        # Pattern: "I am patient / I feel more patient"
        for m in TRAIT_BECOME.finditer(text):
            trait_raw = m.group(1).strip().rstrip(".,!?").lower()
            words = set(trait_raw.split())
            matched = TRAIT_KEYWORDS & words
            if not matched:
                continue
            trait_name = matched.pop()
            current = self._get_current_value(identity_spec, f"traits.{trait_name}")
            new_score = min(1.0, (current + 0.12) if isinstance(current, (int, float)) else 0.62)
            proposals.append(self._build_proposal(
                mutation_type=MutationType.TRAIT_EVOLVED,
                field=f"traits.{trait_name}",
                new_value={"score": new_score, "description": trait_raw},
                confidence=0.75,
                reason=f"Assistant self-identified as '{trait_name}'.",
                source_text=m.group(0),
                identity_spec=identity_spec,
                reasons=[f"Self-identified as '{trait_name}'"],
            ))

        return proposals

    def _detect_trust(
        self, text: str, identity_spec: Any
    ) -> List[MutationProposal]:
        proposals = []
        for m in TRUST_PATTERN.finditer(text):
            target = m.group(1).strip().rstrip(".,!?")
            is_positive = not any(
                w in m.group(0).lower() for w in ["don't", "distrust"]
            )
            sentiment = "trust" if is_positive else "distrust"
            proposals.append(self._build_proposal(
                mutation_type=MutationType.TRUST_EVOLVED,
                field=f"relationships.trust.{target.lower().replace(' ', '_')}",
                new_value=is_positive,
                confidence=0.82,
                reason=f"Assistant expressed {sentiment} toward '{target}'.",
                source_text=m.group(0),
                identity_spec=identity_spec,
                reasons=[f"Expressed {sentiment} toward {target[:30]}"],
            ))
        return proposals

    def _detect_communication(
        self, text: str, identity_spec: Any
    ) -> List[MutationProposal]:
        proposals = []
        for m in COMMUNICATION_PATTERN.finditer(text):
            style = m.group(1).strip().rstrip(".,!?")
            proposals.append(self._build_proposal(
                mutation_type=MutationType.COMMUNICATION_EVOLVED,
                field="communication_style",
                new_value=style,
                confidence=0.77,
                reason=f"Assistant stated a communication preference.",
                source_text=m.group(0),
                identity_spec=identity_spec,
                reasons=[f"Stated communication preference: {style[:30]}"],
            ))
        return proposals

    # ── Validation ────────────────────────────────────────────────────────

    def check_contradiction(
        self,
        proposal: MutationProposal,
        existing_records: Optional[List[MutationRecord]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Check if a proposal contradicts previously accepted identity.
        Checks both MutationRecords (legacy) and the FactStore (canonical).

        Returns a dict describing the contradiction, or None if none found.
        """
        # Check against existing MutationRecords
        if existing_records:
            for record in existing_records:
                if record.status != MutationStatus.ACCEPTED:
                    continue
                if record.field != proposal.field:
                    continue
                if record.new_value != proposal.new_value:
                    return {
                        "type": "mutation_record",
                        "record_id": record.mutation_id,
                        "old_value": record.old_value,
                        "new_value": record.new_value,
                        "field": record.field,
                    }

        # Check against FactStore using ContradictionEngine
        existing = self._fact_store.find(proposal.field)
        if existing is not None and existing.value != proposal.new_value:
            resolution = self._contradiction_engine.resolve(
                proposal.to_fact(), existing
            )
            if resolution in (
                ContradictionResult.REJECTED_KEEP_EXISTING,
                ContradictionResult.PENDING_REVIEW,
            ):
                return {
                    "type": "fact_store",
                    "existing_fact_id": existing.fact_id,
                    "old_value": existing.value,
                    "new_value": proposal.new_value,
                    "field": proposal.field,
                    "resolution": resolution.value,
                }

        return None

    def validate(
        self,
        proposals: List[MutationProposal],
        existing_records: Optional[List[MutationRecord]] = None,
        policy_engine: Any = None,
    ) -> List[MutationProposal]:
        """
        Validate proposals: check confidence threshold, contradictions, policy.
        Returns proposals with status updated.
        """
        validated = []
        for proposal in proposals:
            # Confidence threshold
            if proposal.confidence < self._min_confidence:
                proposal.status = MutationStatus.REJECTED
                proposal.rejection_reason = (
                    f"Confidence {proposal.confidence:.2f} below threshold {self._min_confidence}"
                )
                validated.append(proposal)
                continue

            # Contradiction check (checks both records and FactStore)
            conflict = self.check_contradiction(proposal, existing_records)
            if conflict:
                proposal.status = MutationStatus.CONFLICT
                conflict_id = conflict.get("record_id", conflict.get("existing_fact_id", "unknown"))
                proposal.rejection_reason = (
                    f"Contradicts {conflict['type']} {str(conflict_id)[:8]}: "
                    f"'{conflict.get('old_value')}' → '{conflict.get('new_value')}'"
                )
                validated.append(proposal)
                continue

            proposal.status = MutationStatus.ACCEPTED
            validated.append(proposal)

        return validated

    @property
    def fact_store(self) -> FactStore:
        return self._fact_store

    @fact_store.setter
    def fact_store(self, store: FactStore) -> None:
        self._fact_store = store
        self._contradiction_engine = ContradictionEngine(
            thresholds=self._thresholds,
        )

    def apply_proposals_to_fact_store(
        self,
        proposals: List[MutationProposal],
        evidence_id: str = "",
    ) -> List[IdentityFact]:
        """
        Apply accepted proposals to the FactStore, converting them to IdentityFact objects.
        Uses merge_or_reinforce to handle reinforcement properly.
        Returns the list of IdentityFact objects affected.
        """
        applied: List[IdentityFact] = []
        for proposal in proposals:
            if proposal.status != MutationStatus.ACCEPTED:
                continue
            fact = self._fact_store.merge_or_reinforce(
                field=proposal.field,
                value=proposal.new_value,
                confidence=proposal.confidence,
                reasons=proposal.reasons,
                source=FactSource.ASSISTANT_SELF,
                evidence_id=evidence_id,
            )
            applied.append(fact)
        return applied

    def get_fact_by_field(self, field: str) -> Optional[IdentityFact]:
        """Retrieve the latest active fact for a given field from the FactStore."""
        return self._fact_store.find(field)

    def all_facts(self) -> List[IdentityFact]:
        """Return all facts in the FactStore."""
        return self._fact_store.all()

    def proposal_history(self) -> List[MutationProposal]:
        return list(self._proposal_history)
