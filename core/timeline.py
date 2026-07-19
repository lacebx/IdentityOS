from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Timeline — identities have history, not just state
# ---------------------------------------------------------------------------
# Right now, everything exists. Nothing ages.
# An identity with no timeline is like a person who just appeared one day
# with no past, no growth, no scars, no victories.
#
# The Timeline gives an identity:
# - An age (how long it has existed)
# - Life events (significant moments that shaped it)
# - A history (a narrative you can query)
# - A sense of time passing
#
# This is what separates a chatbot from a persistent being.
# ---------------------------------------------------------------------------


class LifeEventType(Enum):
    CREATION = "creation"             # Identity was instantiated
    ACTIVATION = "activation"         # First time used in a session
    MILESTONE = "milestone"           # Significant achievement
    RELATIONSHIP_FORMED = "relationship_formed"
    RELATIONSHIP_LOST = "relationship_lost"
    KNOWLEDGE_ACQUIRED = "knowledge_acquired"
    SKILL_MASTERED = "skill_mastered"
    GOAL_COMPLETED = "goal_completed"
    FAILURE = "failure"               # Significant failure or setback
    PROMOTION = "promotion"           # Identity version upgraded
    TRANSFORMATION = "transformation" # Core identity change
    DORMANCY = "dormancy"             # Extended period of inactivity
    REACTIVATION = "reactivation"     # Return after dormancy


@dataclass
class LifeEvent:
    """
    A significant moment in an identity's history.

    Life events are not the same as experiences.
    Experiences are everything. Life events are the ones worth marking.
    They form the narrative spine of the identity's existence.

    Example timeline for Officer Maya:
    - Created            [t=0]
    - Joined Department  [t=18 months ago]
    - Met Officer Ryan   [t=16 months ago]  <- RELATIONSHIP_FORMED
    - Solved Case #4471  [t=12 months ago]  <- MILESTONE
    - Promoted           [t=6 months ago]   <- PROMOTION
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    identity_id: str = ""
    event_type: LifeEventType = LifeEventType.MILESTONE
    title: str = ""
    description: str = ""
    significance: int = 3            # 1-5, how important was this
    linked_entity_id: Optional[str] = None  # related identity, skill, goal, etc.
    occurred_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def age_label(self, relative_to: Optional[datetime] = None) -> str:
        """Human-readable age (e.g., '6 months ago', '2 years ago')."""
        now = relative_to or datetime.utcnow()
        delta = now - self.occurred_at
        days = delta.days
        if days < 1:
            return "today"
        elif days < 7:
            return f"{days} day{'s' if days > 1 else ''} ago"
        elif days < 30:
            weeks = days // 7
            return f"{weeks} week{'s' if weeks > 1 else ''} ago"
        elif days < 365:
            months = days // 30
            return f"{months} month{'s' if months > 1 else ''} ago"
        else:
            years = days // 365
            return f"{years} year{'s' if years > 1 else ''} ago"


class IdentityTimeline:
    """
    The Timeline for a single identity.

    Tracks:
    - When the identity was created (its "birth")
    - All life events in chronological order
    - Age (time since creation)
    - A queryable history

    The timeline is what makes an identity feel like it has lived.
    It answers: who were you before this conversation?
    """

    def __init__(self, identity_id: str, created_at: Optional[datetime] = None):
        self.identity_id = identity_id
        self.created_at = created_at or datetime.utcnow()
        self._events: List[LifeEvent] = []

        # Record the creation event automatically
        self._events.append(LifeEvent(
            identity_id=identity_id,
            event_type=LifeEventType.CREATION,
            title="Identity Created",
            description="This identity came into existence.",
            significance=5,
            occurred_at=self.created_at,
        ))

    @property
    def age(self) -> timedelta:
        """How long this identity has existed."""
        return datetime.utcnow() - self.created_at

    @property
    def age_label(self) -> str:
        """Human-readable age."""
        days = self.age.days
        if days < 1:
            return "less than a day"
        elif days < 30:
            return f"{days} day{'s' if days > 1 else ''}"
        elif days < 365:
            months = days // 30
            return f"{months} month{'s' if months > 1 else ''}"
        else:
            years = days // 365
            remaining_months = (days % 365) // 30
            if remaining_months:
                plural_y = "s" if years > 1 else ""
                plural_m = "s" if remaining_months > 1 else ""
                return f"{years} year{plural_y}, {remaining_months} month{plural_m}"
            return f"{years} year{'s' if years > 1 else ''}"

    def record(self, event: LifeEvent) -> None:
        """Add a life event to the timeline."""
        event.identity_id = self.identity_id
        self._events.append(event)
        # Keep chronological order
        self._events.sort(key=lambda e: e.occurred_at)

    def events(self) -> List[LifeEvent]:
        """All events in chronological order."""
        return list(self._events)

    def recent(self, limit: int = 5) -> List[LifeEvent]:
        return self._events[-limit:]

    def by_type(self, event_type: LifeEventType) -> List[LifeEvent]:
        return [e for e in self._events if e.event_type == event_type]

    def significant(self, min_significance: int = 4) -> List[LifeEvent]:
        """Return only highly significant events."""
        return [e for e in self._events if e.significance >= min_significance]

    def narrative(self, limit: int = 10) -> str:
        """
        Generate a narrative timeline for context injection.
        Shows an identity's history in human-readable form.
        """
        events = self.significant() or self.recent(limit)
        if not events:
            return ""
        now = datetime.utcnow()
        lines = [f"## Timeline (Age: {self.age_label})"]
        for e in events[-limit:]:
            age = e.age_label(relative_to=now)
            lines.append(f"  {age}: [{e.event_type.value}] {e.title}")
            if e.description:
                lines.append(f"    {e.description}")
        return "\n".join(lines)

    def __len__(self) -> int:
        return len(self._events)


class TimelineRegistry:
    """
    Registry that maps identity IDs to their timelines.
    Managed by the Runtime.
    """

    def __init__(self):
        self._timelines: Dict[str, IdentityTimeline] = {}

    def create(
        self, identity_id: str, created_at: Optional[datetime] = None
    ) -> IdentityTimeline:
        """Create a timeline for a new identity."""
        timeline = IdentityTimeline(identity_id=identity_id, created_at=created_at)
        self._timelines[identity_id] = timeline
        return timeline

    def get(self, identity_id: str) -> Optional[IdentityTimeline]:
        return self._timelines.get(identity_id)

    def get_or_create(self, identity_id: str) -> IdentityTimeline:
        if identity_id not in self._timelines:
            return self.create(identity_id)
        return self._timelines[identity_id]

    def record_event(
        self, identity_id: str, event: LifeEvent
    ) -> None:
        """Record a life event for an identity, creating timeline if needed."""
        timeline = self.get_or_create(identity_id)
        timeline.record(event)

    def __len__(self) -> int:
        return len(self._timelines)
