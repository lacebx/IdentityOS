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

from typing import Any

from core.executive.models import Evidence, ReplayPolicy, Task, TaskStatus, TaskStepStatus
from core.executive.state import transition


def recover_tasks(store: Any, identity_id: str, policy_resolver: Any = None) -> list[Task]:
    """Reload and repair active tasks so work can continue after interruption."""
    recovered: list[Task] = []
    for task in store.load_all(identity_id):
        if task.status.value not in ("queued", "running", "blocked"):
            continue
        if task.status == TaskStatus.RUNNING:
            _repair_running(task, policy_resolver)
        recovered.append(task)
        store.save(task)  # persist any state repair
    return recovered


def _repair_running(task: Task, policy_resolver: Any = None) -> None:
    """Ensure a RUNNING task points at the correct next step.

    A RUNNING step has an unknown outcome: the process might have stopped
    before execution or after its external effect. Only steps explicitly
    declared replay-safe are reset. Other steps block for reconciliation.
    """
    for step in task.steps:
        if step.status == TaskStepStatus.RUNNING:
            policy = step.replay_policy
            if policy is None and policy_resolver is not None:
                policy = policy_resolver(step.action)
                step.replay_policy = policy
            policy = policy or ReplayPolicy.BLOCK
            attempt = next(
                (a for a in reversed(step.execution_attempts) if a.get("status") == "running"),
                None,
            )
            if policy == ReplayPolicy.RETRY:
                if attempt is not None:
                    attempt["status"] = "interrupted"
                step.status = TaskStepStatus.PENDING
                step.error = None
                evidence = Evidence(
                    step=step.action,
                    label="interrupted_attempt_requeued",
                    detail="Interrupted replay-safe step was requeued",
                    success=True,
                    data={"attempt_id": (attempt or {}).get("attempt_id", "")},
                )
            else:
                if attempt is not None:
                    attempt["status"] = "outcome_unknown"
                step.status = TaskStepStatus.BLOCKED
                step.error = (
                    "Execution outcome is unknown after interruption; reconcile "
                    "the external effect before retrying or accepting completion"
                )
                evidence = Evidence(
                    step=step.action,
                    label="manual_reconciliation_required",
                    detail=step.error,
                    success=False,
                    data={"attempt_id": (attempt or {}).get("attempt_id", "")},
                )
                transition(task, TaskStatus.BLOCKED)
                task.error = step.error
            step.evidence.append(evidence)
            task.evidence.append(evidence)
    task.current_step = next(
        (
            s.description
            for s in task.steps
            if s.status in (TaskStepStatus.PENDING, TaskStepStatus.BLOCKED)
        ),
        task.current_step,
    )
