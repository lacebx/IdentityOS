"""
state.py — Executive task state machine.

The executive guarantees that tasks never silently disappear.  A task is
always in exactly one canonical status and can only move between statuses
through this state machine.  Any attempt to make an illegal transition
raises ``IllegalTransition``, forcing callers to be explicit about intent.
"""

from __future__ import annotations

from typing import Union

from core.executive.models import Task, TaskStatus


class IllegalTransition(Exception):
    """Raised when a task is asked to make a transition that is not allowed."""


# Valid transitions (from -> set of allowed targets).
# The user's spec:
#   Queued -> Running -> Blocked -> Running -> Completed
#   Queued -> Running -> Failed
#   or Cancelled
_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.QUEUED: {TaskStatus.RUNNING, TaskStatus.CANCELLED},
    TaskStatus.RUNNING: {TaskStatus.BLOCKED, TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED},
    TaskStatus.BLOCKED: {TaskStatus.RUNNING, TaskStatus.CANCELLED},
    TaskStatus.COMPLETED: set(),
    TaskStatus.FAILED: {TaskStatus.RUNNING},  # explicit retry/failure-recovery
    TaskStatus.CANCELLED: set(),
}


def can_transition(current: Union[TaskStatus, str], target: Union[TaskStatus, str]) -> bool:
    cur = current if isinstance(current, TaskStatus) else TaskStatus(current)
    tgt = target if isinstance(target, TaskStatus) else TaskStatus(target)
    return tgt in _TRANSITIONS.get(cur, set())


def transition(task: Task, target: Union[TaskStatus, str]) -> None:
    """Move *task* to *target*, enforcing the state machine."""
    import time as _time

    tgt = target if isinstance(target, TaskStatus) else TaskStatus(target)
    if not can_transition(task.status, tgt):
        raise IllegalTransition(
            f"Illegal task transition: {task.status.value} -> {tgt.value} "
            f"(task {task.task_id})"
        )
    task.status = tgt
    task.last_updated = _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime())
