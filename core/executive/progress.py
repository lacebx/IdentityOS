"""
progress.py — Real progress reporting.

Progress percentages and step lists come from the persisted task document,
never from the language model.  This is what makes "did you finish?" answers
truthful: the identity reads its actual executive state.
"""

from __future__ import annotations

from typing import Optional

from core.executive.models import Evidence, Task, TaskStepStatus, TaskStatus


def compute_progress(task: Task) -> dict:
    """Return a structured progress snapshot for a task."""
    steps = task.steps
    completed = sum(1 for s in steps if s.status in (TaskStepStatus.COMPLETED, TaskStepStatus.SKIPPED))
    failed = sum(1 for s in steps if s.status == TaskStepStatus.FAILED)
    total = len(steps)
    pct = round((completed / total * 100) if total else 0.0, 1)

    done = [
        {
            "step": s.description,
            "status": "completed" if s.status == TaskStepStatus.COMPLETED else "skipped",
            "evidence": [e.label for e in s.evidence if e.success],
        }
        for s in steps
        if s.status in (TaskStepStatus.COMPLETED, TaskStepStatus.SKIPPED)
    ]
    current = next(
        ({"step": s.description, "action": s.action} for s in steps
         if s.status == TaskStepStatus.RUNNING),
        None,
    )
    if current is None and task.status == TaskStatus.RUNNING:
        # Determine the next step to run
        nxt = next((s for s in steps if s.status == TaskStepStatus.PENDING), None)
        if nxt is not None:
            current = {"step": nxt.description, "action": nxt.action}
    remaining = [
        s.description for s in steps
        if s.status in (TaskStepStatus.PENDING, TaskStepStatus.BLOCKED)
    ]
    if current is not None:
        remaining = [r for r in remaining if r != current["step"]]
    return {
        "task_id": task.task_id,
        "goal": task.goal,
        "status": task.status.value,
        "progress_percent": pct,
        "current_step": current["step"] if current else None,
        "completed_steps": done,
        "remaining_steps": remaining,
        "failed_steps": failed,
        "total_steps": total,
        "last_updated": task.last_updated,
        "evidence": [e.label for e in task.evidence],
    }


def render_progress_block(task: Task) -> str:
    """Render the progress snapshot as a human-readable block."""
    snap = compute_progress(task)
    lines = [
        f"Current Task: {snap['goal']}",
        f"Status: {snap['status']} ({snap['progress_percent']:.0f}%)",
    ]
    done = snap["completed_steps"]
    if done:
        lines.append("Completed:")
        for d in done:
            mark = "✓" if d["status"] == "completed" else "·"
            lines.append(f"  {mark} {d['step']}")
    if snap["current_step"]:
        lines.append(f"Current: {snap['current_step']}")
    rem = snap["remaining_steps"]
    if rem:
        lines.append("Remaining:")
        for r in rem:
            lines.append(f"  □ {r}")
    return "\n".join(lines)
