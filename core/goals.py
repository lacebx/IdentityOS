from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from .confidence import ConfidenceScorer


class GoalStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    PAUSED = "paused"
    ABANDONED = "abandoned"
    BLOCKED = "blocked"


_VALID_TRANSITIONS: Dict[GoalStatus, List[GoalStatus]] = {
    GoalStatus.ACTIVE: [GoalStatus.COMPLETED, GoalStatus.PAUSED, GoalStatus.ABANDONED, GoalStatus.BLOCKED],
    GoalStatus.PAUSED: [GoalStatus.ACTIVE, GoalStatus.ABANDONED],
    GoalStatus.BLOCKED: [GoalStatus.ACTIVE, GoalStatus.ABANDONED],
    GoalStatus.COMPLETED: [],
    GoalStatus.ABANDONED: [],
}


def _validate_transition(from_status: GoalStatus, to_status: GoalStatus) -> None:
    allowed = _VALID_TRANSITIONS.get(from_status, [])
    if to_status not in allowed:
        raise ValueError(
            f"Cannot transition goal from {from_status.value} to {to_status.value}. "
            f"Allowed transitions from {from_status.value}: "
            f"{[s.value for s in allowed] or '(none)'}"
        )


class GoalPriority(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class GoalScope(str, Enum):
    IMMEDIATE = "immediate"   # Single interaction
    SESSION = "session"       # Within a session
    PERSISTENT = "persistent" # Survives across sessions
    LIFELONG = "lifelong"     # Core identity goal


@dataclass
class Milestone:
    """A checkpointable sub-step within a Goal."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    description: str = ""
    completed: bool = False
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def complete(self) -> None:
        self.completed = True
        self.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "completed": self.completed,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Milestone":
        m = cls(
            id=data.get("id", str(uuid.uuid4())),
            description=data.get("description", ""),
            completed=data.get("completed", False),
            metadata=data.get("metadata", {}),
        )
        if data.get("completed_at"):
            m.completed_at = datetime.fromisoformat(data["completed_at"])
        return m


@dataclass
class Goal:
    """
    A goal an identity is pursuing.
    Goals drive behavior, filter memory relevance, and shape responses.
    Goals can be nested (sub-goals) and have milestones for progress tracking.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    description: str = ""
    status: GoalStatus = GoalStatus.ACTIVE
    priority: GoalPriority = GoalPriority.MEDIUM
    scope: GoalScope = GoalScope.PERSISTENT
    parent_id: Optional[str] = None        # For nested/sub-goals
    blocked_by: List[str] = field(default_factory=list)  # Goal IDs blocking this
    milestones: List[Milestone] = field(default_factory=list)
    required_skills: List[str] = field(default_factory=list)   # skill IDs
    required_knowledge: List[str] = field(default_factory=list) # pack IDs
    success_criteria: str = ""
    progress: float = 0.0    # 0.0 to 1.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    deadline: Optional[datetime] = None
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_milestone(self, description: str) -> Milestone:
        m = Milestone(description=description)
        self.milestones.append(m)
        self._sync_progress()
        return m

    def complete_milestone(self, milestone_id: str) -> bool:
        for m in self.milestones:
            if m.id == milestone_id:
                m.complete()
                self._sync_progress()
                return True
        return False

    def _sync_progress(self) -> None:
        """Recalculate progress based on completed milestones."""
        if not self.milestones:
            return
        done = sum(1 for m in self.milestones if m.completed)
        self.progress = done / len(self.milestones)
        if self.progress >= 1.0:
            self.status = GoalStatus.COMPLETED
        self.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

    def _transition(self, new_status: GoalStatus, reason: str = "") -> None:
        _validate_transition(self.status, new_status)
        self.status = new_status
        if reason:
            self.metadata[f"transition_reason_{new_status.value}"] = reason
        self.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

    def mark_completed(self, reason: str = "") -> None:
        self._transition(GoalStatus.COMPLETED, reason)
        self.progress = 1.0

    def block(self, reason: str = "") -> None:
        self._transition(GoalStatus.BLOCKED, reason)
        if reason:
            self.metadata["block_reason"] = reason

    def pause(self, reason: str = "") -> None:
        self._transition(GoalStatus.PAUSED, reason)

    def resume(self, reason: str = "") -> None:
        self._transition(GoalStatus.ACTIVE, reason)

    def abandon(self, reason: str = "") -> None:
        self._transition(GoalStatus.ABANDONED, reason)

    def reprioritize(self, new_priority: GoalPriority) -> None:
        self.priority = new_priority
        self.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

    def is_active(self) -> bool:
        return self.status == GoalStatus.ACTIVE

    @property
    def confidence(self) -> float:
        """Confidence that this goal will be completed.
        Based on progress, priority, and status.
        """
        if self.status == GoalStatus.COMPLETED:
            return 1.0
        if self.status == GoalStatus.ABANDONED:
            return 0.0
        if self.status == GoalStatus.BLOCKED:
            return max(0.1, self.progress * 0.5)
        if self.status == GoalStatus.PAUSED:
            return max(0.2, self.progress * 0.7)
        base = 0.5 + (self.progress * 0.4)
        priority_bonus = (self.priority.value - 1) * 0.05
        return min(1.0, base + priority_bonus)

    @property
    def confidence_label(self) -> str:
        return ConfidenceScorer.label(self.confidence)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "priority": self.priority.value,
            "scope": self.scope.value,
            "parent_id": self.parent_id,
            "blocked_by": self.blocked_by,
            "milestones": [m.to_dict() for m in self.milestones],
            "required_skills": self.required_skills,
            "required_knowledge": self.required_knowledge,
            "success_criteria": self.success_criteria,
            "progress": self.progress,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "tags": self.tags,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Goal":
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            title=data.get("title", ""),
            description=data.get("description", ""),
            status=GoalStatus(data.get("status", "active")),
            priority=GoalPriority(data.get("priority", GoalPriority.MEDIUM.value)),
            scope=GoalScope(data.get("scope", "persistent")),
            parent_id=data.get("parent_id"),
            blocked_by=data.get("blocked_by", []),
            milestones=[Milestone.from_dict(m) for m in data.get("milestones", [])],
            required_skills=data.get("required_skills", []),
            required_knowledge=data.get("required_knowledge", []),
            success_criteria=data.get("success_criteria", ""),
            progress=data.get("progress", 0.0),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now(timezone.utc).replace(tzinfo=None),
            updated_at=datetime.fromisoformat(data["updated_at"]) if "updated_at" in data else datetime.now(timezone.utc).replace(tzinfo=None),
            deadline=datetime.fromisoformat(data["deadline"]) if data.get("deadline") else None,
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
        )


class GoalEngine:
    """
    Manages the goal stack for an identity.
    Goals are prioritized and can be queried to drive behavior.
    Supports lifecycle transitions, persistence, and dependency resolution.
    """

    def __init__(self):
        self._goals: Dict[str, Goal] = {}

    def add(self, goal: Goal) -> None:
        self._goals[goal.id] = goal

    def remove(self, goal_id: str) -> bool:
        return bool(self._goals.pop(goal_id, None))

    def get(self, goal_id: str) -> Optional[Goal]:
        return self._goals.get(goal_id)

    def active(self) -> List[Goal]:
        return [
            g for g in self._goals.values()
            if g.status == GoalStatus.ACTIVE
        ]

    def top_priority(self) -> Optional[Goal]:
        """Return the highest-priority active goal."""
        active = self.active()
        if not active:
            return None
        return max(active, key=lambda g: (g.priority.value, -g.progress))

    def by_scope(self, scope: GoalScope) -> List[Goal]:
        return [g for g in self._goals.values() if g.scope == scope]

    def sub_goals(self, parent_id: str) -> List[Goal]:
        return [g for g in self._goals.values() if g.parent_id == parent_id]

    def resolve_blocked(self) -> int:
        """Check if any previously BLOCKED goals are now unblocked.
        A goal is unblocked if none of its blocked_by IDs are active goals.
        Returns the number of goals unblocked.
        """
        unblocked = 0
        for g in self._goals.values():
            if g.status != GoalStatus.BLOCKED:
                continue
            if not g.blocked_by:
                continue
            still_blocked = any(
                blocker_id in self._goals and self._goals[blocker_id].is_active()
                for blocker_id in g.blocked_by
            )
            if not still_blocked:
                g.resume("Dependencies resolved")
                unblocked += 1
        return unblocked

    def to_prompt_summary(self) -> str:
        """Summarize active goals for context injection."""
        active = self.active()
        if not active:
            return "No active goals."
        sorted_goals = sorted(active, key=lambda g: -g.priority.value)
        lines = ["Current Goals:"]
        for g in sorted_goals:
            pct = int(g.progress * 100)
            lines.append(f"  [{g.priority.name}] {g.title} ({pct}% complete)")
            if g.description:
                lines.append(f"    {g.description}")
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goals": [g.to_dict() for g in self._goals.values()],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GoalEngine":
        engine = cls()
        for gd in data.get("goals", []):
            engine.add(Goal.from_dict(gd))
        return engine

    def all(self) -> List[Goal]:
        return list(self._goals.values())

    def __len__(self) -> int:
        return len(self._goals)
