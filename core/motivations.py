from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Motivations — the distinction that makes identities feel real
# ---------------------------------------------------------------------------
# Goals are what an identity is trying to accomplish today.
# Motivations are why it exists at all.
#
# Goals:       Finish the report. Close the case. Ship the feature.
# Motivations: Protect people. Seek truth. Reduce suffering. Become wiser.
#
# Goals change every day. Motivations rarely do.
# Humans have both. So should identities.
#
# Motivations live in the identity kernel, not the goal queue.
# They influence EVERY decision the identity makes, all the time,
# without being explicitly invoked.
# ---------------------------------------------------------------------------


class MotivationStrength(Enum):
    """How powerfully this motivation drives behavior."""
    BACKGROUND = 1   # Always present, rarely decisive
    MODERATE = 2     # Regularly influences decisions
    STRONG = 3       # Frequently decisive
    CORE = 4         # Defines the identity. Almost never overridden.


class MotivationDomain(Enum):
    """The sphere of life this motivation operates in."""
    SELF = "self"                   # Personal development, growth
    OTHERS = "others"               # Care, protection, service
    TRUTH = "truth"                 # Knowledge, honesty, understanding
    CREATION = "creation"           # Making things, building, art
    JUSTICE = "justice"             # Fairness, order, ethics
    LEGACY = "legacy"               # Impact beyond oneself
    BELONGING = "belonging"         # Connection, community, loyalty
    SURVIVAL = "survival"           # Continuity, safety


@dataclass
class Motivation:
    """
    A persistent drive that shapes an identity's behavior across all contexts.

    Motivations are not goals. They don't have deadlines or completion states.
    They are the underlying *why* behind everything the identity does.

    Example motivations:
        - "Protect civilians" (domain=OTHERS, strength=CORE)
        - "Seek truth" (domain=TRUTH, strength=STRONG)
        - "Become wiser through every failure" (domain=SELF, strength=MODERATE)
        - "Leave something that outlasts me" (domain=LEGACY, strength=STRONG)
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""  # Narrative explanation
    domain: MotivationDomain = MotivationDomain.SELF
    strength: MotivationStrength = MotivationStrength.MODERATE
    origin: str = ""       # What caused this motivation (experience, teaching, etc.)
    expressed_as: List[str] = field(default_factory=list)  # Behaviors it produces
    conflicts_with: List[str] = field(default_factory=list)  # IDs of conflicting motivations
    reinforced_by: List[str] = field(default_factory=list)   # Experience IDs that strengthened this
    established_at: datetime = field(default_factory=datetime.utcnow)
    last_expressed: Optional[datetime] = None
    expression_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def express(self) -> None:
        """Record that this motivation drove behavior."""
        self.last_expressed = datetime.utcnow()
        self.expression_count += 1

    def is_core(self) -> bool:
        return self.strength == MotivationStrength.CORE

    def to_prompt_line(self) -> str:
        return f"  [{self.domain.value.upper()}] {self.name}: {self.description}"


class MotivationEngine:
    """
    Manages an identity's motivational profile.

    Motivations are injected into the Cognitive Engine's context
    as the deepest layer — they are always present, always shaping output,
    even when the user never mentions them.

    Conflict detection: when two motivations pull in opposite directions,
    the system surfaces the tension rather than silently resolving it.
    This produces more authentic, human-feeling responses.
    """

    def __init__(self):
        self._motivations: Dict[str, Motivation] = {}

    def add(self, motivation: Motivation) -> None:
        self._motivations[motivation.id] = motivation

    def remove(self, motivation_id: str) -> bool:
        return bool(self._motivations.pop(motivation_id, None))

    def get(self, motivation_id: str) -> Optional[Motivation]:
        return self._motivations.get(motivation_id)

    def core(self) -> List[Motivation]:
        """Return only CORE-strength motivations."""
        return [
            m for m in self._motivations.values()
            if m.strength == MotivationStrength.CORE
        ]

    def by_domain(self, domain: MotivationDomain) -> List[Motivation]:
        return [m for m in self._motivations.values() if m.domain == domain]

    def sorted_by_strength(self) -> List[Motivation]:
        return sorted(
            self._motivations.values(),
            key=lambda m: -m.strength.value
        )

    def active_conflicts(self) -> List[tuple]:
        """
        Detect pairs of motivations that list each other as conflicting.
        Returns list of (Motivation, Motivation) pairs.
        """
        conflicts: List[tuple] = []
        motivations = list(self._motivations.values())
        for i, m in enumerate(motivations):
            for conflict_id in m.conflicts_with:
                if conflict_id in self._motivations:
                    other = self._motivations[conflict_id]
                    pair = tuple(sorted([m.id, conflict_id]))
                    if pair not in [tuple(sorted([a.id, b.id])) for a, b in conflicts]:
                        conflicts.append((m, other))
        return conflicts

    def to_prompt_block(self) -> str:
        """Render motivations for injection into the Cognitive Engine."""
        sorted_motivations = self.sorted_by_strength()
        if not sorted_motivations:
            return ""
        lines = ["## Core Motivations"]
        for m in sorted_motivations:
            strength_label = "*" * m.strength.value
            lines.append(f"  {strength_label} [{m.domain.value}] {m.name}")
            if m.description:
                lines.append(f"    {m.description}")
        conflicts = self.active_conflicts()
        if conflicts:
            lines.append("## Active Tensions")
            for a, b in conflicts:
                lines.append(f"  {a.name} <-> {b.name}")
        return "\n".join(lines)

    def __len__(self) -> int:
        return len(self._motivations)
