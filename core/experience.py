from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Experience Engine
# ---------------------------------------------------------------------------
# Memory was a starting point. Experience is the destination.
#
# Identities don't just store memories — they grow through experiences.
# A conversation, an observation, a failure, a success, skill practice,
# a relationship event, or goal progress are all experiences.
# Each one shapes the identity differently.
#
# This replaces the narrow concept of "MemoryStore" with a richer
# ExperienceStore that captures the full texture of an identity's life.
# ---------------------------------------------------------------------------


class ExperienceType(Enum):
    CONVERSATION = "conversation"       # An interaction with a user or another identity
    OBSERVATION = "observation"         # Something witnessed or noticed
    SKILL_PRACTICE = "skill_practice"   # Exercising a skill
    FAILURE = "failure"                 # Something that went wrong
    ACHIEVEMENT = "achievement"         # Something accomplished
    RELATIONSHIP_EVENT = "relationship_event"  # A meaningful interaction with a known identity
    GOAL_PROGRESS = "goal_progress"     # Movement toward or away from a goal
    KNOWLEDGE_ACQUIRED = "knowledge_acquired"  # Learning something new
    REFLECTION = "reflection"           # An internally-generated insight


class ExperienceImpact(Enum):
    """How significantly an experience shaped the identity."""
    TRIVIAL = 1
    MINOR = 2
    MODERATE = 3
    SIGNIFICANT = 4
    FORMATIVE = 5  # Rare. Changes the identity.


@dataclass
class Experience:
    """
    A single experience in an identity's life.

    Experiences are the atomic unit of identity growth.
    They are richer than memories: they carry context, impact,
    emotional weight, and links to the skills/goals/relationships they touched.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    identity_id: str = ""
    experience_type: ExperienceType = ExperienceType.CONVERSATION
    title: str = ""             # Brief label (e.g., "Solved Case #4471")
    description: str = ""       # What happened
    impact: ExperienceImpact = ExperienceImpact.MINOR
    emotional_valence: float = 0.0  # -1.0 (very negative) to 1.0 (very positive)
    skills_involved: List[str] = field(default_factory=list)   # skill IDs
    goals_involved: List[str] = field(default_factory=list)    # goal IDs
    relationships_involved: List[str] = field(default_factory=list)  # identity IDs
    knowledge_acquired: List[str] = field(default_factory=list)  # pack IDs
    raw_content: str = ""       # Original text (e.g., conversation transcript)
    tags: List[str] = field(default_factory=list)
    session_id: Optional[str] = None
    occurred_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_formative(self) -> bool:
        return self.impact == ExperienceImpact.FORMATIVE

    def summary(self) -> str:
        """One-line summary for context injection."""
        sign = "+" if self.emotional_valence >= 0 else ""
        return (
            f"[{self.experience_type.value}] {self.title} "
            f"(impact={self.impact.name}, valence={sign}{self.emotional_valence:.1f})"
        )


class ExperienceStore:
    """
    The Experience Store.

    Stores all experiences across all identities.
    Supports retrieval by:
    - Recency
    - Type
    - Impact threshold
    - Keyword search
    - Formative experiences (high-impact)

    This is the foundation for Identity Evolution:
    v1.0 -> [1000 experiences] -> Evaluation -> v1.1
    """

    def __init__(self):
        self._experiences: Dict[str, Experience] = {}
        # identity_id -> list of experience IDs, in order
        self._by_identity: Dict[str, List[str]] = {}

    def record(self, experience: Experience) -> None:
        """Record a new experience."""
        self._experiences[experience.id] = experience
        if experience.identity_id not in self._by_identity:
            self._by_identity[experience.identity_id] = []
        self._by_identity[experience.identity_id].append(experience.id)

    def get(self, experience_id: str) -> Optional[Experience]:
        return self._experiences.get(experience_id)

    def delete(self, experience_id: str) -> bool:
        exp = self._experiences.pop(experience_id, None)
        if exp and exp.identity_id in self._by_identity:
            self._by_identity[exp.identity_id] = [
                eid for eid in self._by_identity[exp.identity_id]
                if eid != experience_id
            ]
        return exp is not None

    def all_for(self, identity_id: str) -> List[Experience]:
        """All experiences for an identity, chronological."""
        ids = self._by_identity.get(identity_id, [])
        return [self._experiences[eid] for eid in ids if eid in self._experiences]

    def recent(self, identity_id: str, limit: int = 10) -> List[Experience]:
        return self.all_for(identity_id)[-limit:]

    def by_type(
        self, identity_id: str, exp_type: ExperienceType
    ) -> List[Experience]:
        return [
            e for e in self.all_for(identity_id)
            if e.experience_type == exp_type
        ]

    def formative(
        self, identity_id: str
    ) -> List[Experience]:
        """Return only formative (identity-changing) experiences."""
        return [
            e for e in self.all_for(identity_id)
            if e.impact == ExperienceImpact.FORMATIVE
        ]

    def above_impact(
        self, identity_id: str, min_impact: ExperienceImpact
    ) -> List[Experience]:
        return [
            e for e in self.all_for(identity_id)
            if e.impact.value >= min_impact.value
        ]

    def search(
        self, query: str, identity_id: Optional[str] = None, limit: int = 10
    ) -> List[Experience]:
        """Keyword search across title, description, and raw_content."""
        query_lower = query.lower()
        pool = (
            self.all_for(identity_id) if identity_id
            else list(self._experiences.values())
        )
        results = [
            e for e in pool
            if query_lower in e.title.lower()
            or query_lower in e.description.lower()
            or query_lower in e.raw_content.lower()
            or any(query_lower in tag for tag in e.tags)
        ]
        return results[-limit:]

    def experience_count(self, identity_id: str) -> int:
        return len(self._by_identity.get(identity_id, []))

    def growth_profile(self, identity_id: str) -> Dict[str, Any]:
        """
        Generate a growth profile: experience counts by type and
        overall emotional trajectory.
        """
        experiences = self.all_for(identity_id)
        if not experiences:
            return {"total": 0}

        by_type: Dict[str, int] = {}
        for exp in experiences:
            key = exp.experience_type.value
            by_type[key] = by_type.get(key, 0) + 1

        valences = [e.emotional_valence for e in experiences]
        avg_valence = sum(valences) / len(valences)

        # Trend: compare first half to second half
        mid = len(valences) // 2
        early_avg = sum(valences[:mid]) / max(mid, 1)
        late_avg = sum(valences[mid:]) / max(len(valences) - mid, 1)
        trend = "improving" if late_avg > early_avg else "declining" if late_avg < early_avg else "stable"

        return {
            "total": len(experiences),
            "by_type": by_type,
            "average_valence": round(avg_valence, 3),
            "emotional_trend": trend,
            "formative_count": len(self.formative(identity_id)),
        }

    def to_prompt_summary(
        self, identity_id: str, limit: int = 5
    ) -> str:
        recent = self.recent(identity_id, limit=limit)
        if not recent:
            return ""
        lines = ["## Recent Experiences"]
        for e in recent:
            lines.append(f"  {e.summary()}")
        return "\n".join(lines)

    def __len__(self) -> int:
        return len(self._experiences)
