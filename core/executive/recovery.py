"""
recovery.py — Interruption recovery.

After a crash or a new session, ``recover`` reloads every active task for an
identity and resumes it from its last completed step.  Because the executive
checkpoints after every step, an interrupted RUNNING task never restarts from
scratch — it continues exactly where it stopped.

Recovery rules:
  - RUNNING  -> resume from the first non-completed step (status stays RUNNING)
  - QUEUED   -> leave queued (the scheduler will pick it up)
  - BLOCKED  -> stay blocked (explicitly released by the identity)
"""

from __future__ import annotations

from typing import Any, Optional

from core.executive.models import Task, TaskStatus, TaskStepStatus


def recover_tasks(store: Any, identity_id: str) -> list[Task]:
    """Reload and repair active tasks so work can continue after interruption."""
    recovered: list[Task] = []
    for task in store.load_all(identity_id):
        if task.status.value not in ("queued", "running", "blocked"):
            continue
        if task.status == TaskStatus.RUNNING:
            _repair_running(task)
        recovered.append(task)
        store.save(task)  # persist any state repair
    return recovered


def _repair_running(task: Task) -> None:
    """Ensure a RUNNING task points at the correct next step.

    A step marked RUNNING in a previous session never completed its write —
    reset it so it re-runs; steps already COMPLETED stay done.
    """
    for step in task.steps:
        if step.status == TaskStepStatus.RUNNING:
            step.status = TaskStepStatus.PENDING
            step.error = None
    task.current_step = next(
        (s.description for s in task.steps if s.status == TaskStepStatus.PENDING),
        task.current_step,
    )
