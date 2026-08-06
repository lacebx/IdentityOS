"""
models.py — Executive Runtime data model.

A persistent, generic task engine for identities. Every long-running goal
becomes a ``Task`` that survives conversation turns and is always in one of
the canonical statuses defined by the executive state machine.

This module contains only data structures — no execution logic.
"""

from __future__ import annotations

import enum
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional


class TaskStatus(str, enum.Enum):
    """Canonical task lifecycle states.

    Valid transitions (see :mod:`core.executive.state`):
      QUEUED -> RUNNING
      RUNNING -> BLOCKED
      BLOCKED -> RUNNING
      RUNNING -> COMPLETED
      RUNNING -> FAILED
      QUEUED/RUNNING/BLOCKED -> CANCELLED
    """

    QUEUED = "queued"
    RUNNING = "running"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskStepStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"


@dataclass
class Evidence:
    """A single verifiable fact produced while executing a step."""

    step: str
    label: str
    detail: str
    success: bool
    timestamp: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    data: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "step": self.step,
            "label": self.label,
            "detail": self.detail,
            "success": self.success,
            "timestamp": self.timestamp,
            "data": self.data,
        }

    @classmethod
    def from_dict(cls, raw: dict) -> "Evidence":
        return cls(
            step=raw.get("step", ""),
            label=raw.get("label", ""),
            detail=raw.get("detail", ""),
            success=raw.get("success", False),
            timestamp=raw.get("timestamp", ""),
            data=raw.get("data", {}),
        )


@dataclass
class TaskStep:
    """One unit of executable work within a task."""

    action: str
    description: str
    params: dict = field(default_factory=dict)
    status: TaskStepStatus = TaskStepStatus.PENDING
    retry_count: int = 0
    max_retries: int = 2
    evidence: list = field(default_factory=list)  # list[Evidence]
    result: dict = field(default_factory=dict)
    error: Optional[str] = None
    # Conditional guard: skip when the named prior step's result has `key` truthy.
    run_unless_step: Optional[str] = None
    run_unless_key: Optional[str] = None
    # Continue only if the named prior step's result has `key` falsy.
    run_if_step: Optional[str] = None
    run_if_key: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "action": self.action,
            "description": self.description,
            "params": self.params,
            "status": self.status.value,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "evidence": [e.to_dict() for e in self.evidence],
            "result": self.result,
            "error": self.error,
            "run_unless_step": self.run_unless_step,
            "run_unless_key": self.run_unless_key,
            "run_if_step": self.run_if_step,
            "run_if_key": self.run_if_key,
        }

    @classmethod
    def from_dict(cls, raw: dict) -> "TaskStep":
        return cls(
            action=raw.get("action", ""),
            description=raw.get("description", ""),
            params=raw.get("params", {}),
            status=TaskStepStatus(raw.get("status", TaskStepStatus.PENDING.value)),
            retry_count=raw.get("retry_count", 0),
            max_retries=raw.get("max_retries", 2),
            evidence=[Evidence.from_dict(e) for e in raw.get("evidence", [])],
            result=raw.get("result", {}),
            error=raw.get("error"),
            run_unless_step=raw.get("run_unless_step"),
            run_unless_key=raw.get("run_unless_key"),
            run_if_step=raw.get("run_if_step"),
            run_if_key=raw.get("run_if_key"),
        )


@dataclass
class Task:
    """A persistent unit of work owned by the executive."""

    task_id: str
    goal: str
    identity_id: str
    created_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    status: TaskStatus = TaskStatus.QUEUED
    priority: int = 0
    capability_id: Optional[str] = None
    original_request: Optional[str] = None
    steps: list = field(default_factory=list)  # list[TaskStep]
    retry_count: int = 0
    max_retries: int = 1
    evidence: list = field(default_factory=list)  # list[Evidence]
    current_step: Optional[str] = None
    last_updated: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    completion_result: Optional[dict] = None
    error: Optional[str] = None
    # Checkpoint data — set at every step boundary so interruption recovery
    # can resume exactly from the last completed step.
    checkpoint: dict = field(default_factory=dict)

    # ── Helpers ──────────────────────────────────────────────────────

    @property
    def progress(self) -> float:
        if not self.steps:
            return 0.0
        completed = sum(1 for s in self.steps if s.status in (TaskStepStatus.COMPLETED, TaskStepStatus.SKIPPED))
        return round(completed / len(self.steps), 4)

    @property
    def completed_steps(self) -> list[TaskStep]:
        return [s for s in self.steps if s.status == TaskStepStatus.COMPLETED]

    @property
    def remaining_steps(self) -> list[TaskStep]:
        return [s for s in self.steps if s.status in (TaskStepStatus.PENDING, TaskStepStatus.RUNNING, TaskStepStatus.BLOCKED)]

    @property
    def failed_steps(self) -> list[TaskStep]:
        return [s for s in self.steps if s.status == TaskStepStatus.FAILED]

    def step_by_id(self, step_id: str) -> Optional[TaskStep]:
        for s in self.steps:
            if s.action == step_id:
                return s
        return None

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "goal": self.goal,
            "identity_id": self.identity_id,
            "created_at": self.created_at,
            "status": self.status.value,
            "priority": self.priority,
            "capability_id": self.capability_id,
            "original_request": self.original_request,
            "steps": [s.to_dict() for s in self.steps],
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "evidence": [e.to_dict() for e in self.evidence],
            "current_step": self.current_step,
            "progress": self.progress,
            "last_updated": self.last_updated,
            "completion_result": self.completion_result,
            "error": self.error,
            "checkpoint": self.checkpoint,
        }

    @classmethod
    def from_dict(cls, raw: dict) -> "Task":
        return cls(
            task_id=raw.get("task_id", str(uuid.uuid4())),
            goal=raw.get("goal", ""),
            identity_id=raw.get("identity_id", ""),
            created_at=raw.get("created_at", ""),
            status=TaskStatus(raw.get("status", TaskStatus.QUEUED.value)),
            priority=raw.get("priority", 0),
            capability_id=raw.get("capability_id"),
            original_request=raw.get("original_request"),
            steps=[TaskStep.from_dict(s) for s in raw.get("steps", [])],
            retry_count=raw.get("retry_count", 0),
            max_retries=raw.get("max_retries", 1),
            evidence=[Evidence.from_dict(e) for e in raw.get("evidence", [])],
            current_step=raw.get("current_step"),
            last_updated=raw.get("last_updated", ""),
            completion_result=raw.get("completion_result"),
            error=raw.get("error"),
            checkpoint=raw.get("checkpoint", {}),
        )
