"""
core/intentions/engine.py - Intention dataclass and IntentionEngine.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from core.confidence import ConfidenceScorer


class IntentionStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    ABANDONED = "abandoned"
    EXPIRED = "expired"
    PROMOTED = "promoted"


class IntentionPriority(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3


class PromotionReason(str, Enum):
    REPEATED = "repeated"                     # Mentioned multiple times
    SUSTAINED_RELEVANCE = "sustained_relevance"  # Stayed relevant beyond expiry
    USER_REQUEST = "user_request"              # User explicitly asked
    SYSTEM_PROMOTION = "system_promotion"      # System auto-promoted


_DEFAULT_EXPIRY_HOURS = 24


@dataclass
class Intention:
    """
    A short-term commitment formed during conversation.

    Intentions are ephemeral — they auto-expire after a configurable
    duration. Sustained intentions may be promoted to Goals.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    description: str = ""
    status: IntentionStatus = IntentionStatus.ACTIVE
    priority: IntentionPriority = IntentionPriority.MEDIUM
    goal_id: Optional[str] = None           # Link to promoted goal, if any
    source_conversation: str = ""
    source_session_id: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    expires_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.expires_at is None:
            self.expires_at = self.created_at + timedelta(hours=_DEFAULT_EXPIRY_HOURS)

    def is_expired(self, now: Optional[datetime] = None) -> bool:
        if self.status != IntentionStatus.ACTIVE:
            return False
        check = now or datetime.now(timezone.utc).replace(tzinfo=None)
        return self.expires_at is not None and check >= self.expires_at

    def complete(self, reason: str = "") -> None:
        self.status = IntentionStatus.COMPLETED
        self.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
        if reason:
            self.metadata["completion_reason"] = reason

    def abandon(self, reason: str = "") -> None:
        self.status = IntentionStatus.ABANDONED
        if reason:
            self.metadata["abandon_reason"] = reason

    def mark_expired(self) -> None:
        self.status = IntentionStatus.EXPIRED

    def promote(
        self,
        goal_id: str,
        reason: PromotionReason = PromotionReason.SYSTEM_PROMOTION,
        detail: str = "",
    ) -> None:
        self.status = IntentionStatus.PROMOTED
        self.goal_id = goal_id
        self.metadata["promotion_reason"] = reason.value
        if detail:
            self.metadata["promotion_detail"] = detail

    def is_active(self) -> bool:
        return self.status == IntentionStatus.ACTIVE and not self.is_expired()

    @property
    def confidence(self) -> float:
        """Confidence that this intention will be fulfilled.
        Based on priority, time remaining, and status.
        """
        if self.status == IntentionStatus.COMPLETED:
            return 1.0
        if self.status == IntentionStatus.PROMOTED:
            return 1.0
        if self.status in (IntentionStatus.ABANDONED, IntentionStatus.EXPIRED):
            return 0.0
        priority_bonus = (self.priority.value - 1) * 0.1
        if self.expires_at:
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            total = (self.expires_at - self.created_at).total_seconds()
            remaining = (self.expires_at - now).total_seconds()
            time_factor = max(0.0, min(1.0, remaining / total)) if total > 0 else 0.5
        else:
            time_factor = 0.5
        return min(1.0, 0.5 + priority_bonus + (time_factor * 0.3))

    @property
    def confidence_label(self) -> str:
        return ConfidenceScorer.label(self.confidence)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "status": self.status.value,
            "priority": self.priority.value,
            "goal_id": self.goal_id,
            "source_conversation": self.source_conversation,
            "source_session_id": self.source_session_id,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Intention":
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            description=data.get("description", ""),
            status=IntentionStatus(data.get("status", "active")),
            priority=IntentionPriority(data.get("priority", IntentionPriority.MEDIUM.value)),
            goal_id=data.get("goal_id"),
            source_conversation=data.get("source_conversation", ""),
            source_session_id=data.get("source_session_id"),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now(timezone.utc).replace(tzinfo=None),
            expires_at=datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            metadata=data.get("metadata", {}),
        )


class IntentionEngine:
    """
    Manages short-term commitments (intentions).

    Handles creation, expiry, completion, abandonment, and promotion to goals.
    """

    def __init__(self):
        self._intentions: Dict[str, Intention] = {}

    def add(self, intention: Intention) -> None:
        self._intentions[intention.id] = intention

    def get(self, intention_id: str) -> Optional[Intention]:
        return self._intentions.get(intention_id)

    def remove(self, intention_id: str) -> bool:
        return bool(self._intentions.pop(intention_id, None))

    def active(self) -> List[Intention]:
        return [
            i for i in self._intentions.values()
            if i.is_active()
        ]

    def active_by_priority(self) -> List[Intention]:
        return sorted(
            self.active(),
            key=lambda i: (i.priority.value, -i.created_at.timestamp()),
            reverse=True,
        )

    def completed(self) -> List[Intention]:
        return [
            i for i in self._intentions.values()
            if i.status == IntentionStatus.COMPLETED
        ]

    def expired(self) -> List[Intention]:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        expired: List[Intention] = []
        for i in self._intentions.values():
            if i.status == IntentionStatus.ACTIVE and i.is_expired(now):
                i.mark_expired()
                expired.append(i)
        return expired

    def check_expiry(self) -> int:
        """Check all intentions and auto-expire any that have passed their deadline.
        Returns the number of intentions expired in this check.
        """
        expired = self.expired()
        return len(expired)

    def promote_to_goal(
        self,
        intention_id: str,
        goal_id: str,
        reason: PromotionReason = PromotionReason.SYSTEM_PROMOTION,
        detail: str = "",
    ) -> bool:
        intention = self._intentions.get(intention_id)
        if not intention or not intention.is_active():
            return False
        intention.promote(goal_id, reason, detail)
        return True

    def to_prompt_summary(self) -> str:
        """Summarize active intentions for context injection."""
        active = self.active()
        if not active:
            return ""
        sorted_i = sorted(active, key=lambda i: (-i.priority.value, i.created_at))
        lines = ["Active Intentions:"]
        for i in sorted_i:
            remaining = ""
            if i.expires_at:
                delta = i.expires_at - datetime.now(timezone.utc).replace(tzinfo=None)
                if delta.total_seconds() > 0:
                    hrs = int(delta.total_seconds() / 3600)
                    remaining = f" ({hrs}h remaining)"
            lines.append(f"  [{i.priority.name}] {i.description}{remaining}")
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intentions": [i.to_dict() for i in self._intentions.values()],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IntentionEngine":
        engine = cls()
        for idata in data.get("intentions", []):
            engine.add(Intention.from_dict(idata))
        return engine

    def all(self) -> List[Intention]:
        return list(self._intentions.values())

    def __len__(self) -> int:
        return len(self._intentions)
