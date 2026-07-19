from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class GoalStatus(Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    PAUSED = "paused"
    ABANDONED = "abandoned"
    BLOCKED = "blocked"


class GoalPriority(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class GoalScope(Enum):
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
        self.completed_at = datetime.utcnow()


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
    milestones: List[Milestone] = field(default_factory=list)
    required_skills: List[str] = field(default_factory=list)   # skill IDs
    required_knowledge: List[str] = field(default_factory=list) # pack IDs
    success_criteria: str = ""
    progress: float = 0.0    # 0.0 to 1.0
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
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
        self.updated_at = datetime.utcnow()

    def mark_completed(self) -> None:
        self.status = GoalStatus.COMPLETED
        self.progress = 1.0
        self.updated_at = datetime.utcnow()

    def block(self, reason: str = "") -> None:
        self.status = GoalStatus.BLOCKED
        if reason:
            self.metadata["block_reason"] = reason
        self.updated_at = datetime.utcnow()

    def is_active(self) -> bool:
        return self.status == GoalStatus.ACTIVE


class GoalEngine:
    """
    Manages the goal stack for an identity.
    Goals are prioritized and can be queried to drive behavior.
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

    def __len__(self) -> int:
        return len(self._goals)
