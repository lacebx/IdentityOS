"""
executive — Capability wrapper around the Executive Runtime.

Gives every identity a natural API for committing to long-running work:

    executive.start_task(goal="...")
    executive.current_task()
    executive.task_status(task_id=...)
    executive.resume_task(task_id=...)
    ...

The underlying engine is generic; this capability only adapts the API for
the LLM.  It never knows individual capability names.
"""

from __future__ import annotations

from typing import Any, Optional

from core.capabilities.base import Capability, Skill
from core.capabilities.registry import register
from core.capabilities.result import CapabilityResult
from core.executive import get_executive_for, register_executive
from core.executive.engine import ExecutiveRuntime


@register
class ExecutiveCapability(Capability):
    id = "executive"
    name = "Executive"
    version = "1.0.0"
    author = "IdentityOS"
    license = "MIT"
    description = "Persistent task engine: commit to goals, execute steps, track progress, recover from interruption"
    permissions = ["public"]

    def __init__(self, config: Optional[dict] = None) -> None:
        super().__init__(config)
        self._storage = None

    def install(self, identity_id: str, storage: Any) -> None:
        self._storage = storage
        # Make sure a live engine exists for this storage backend.
        if get_executive_for(storage) is None:
            from core.capabilities.registry import CapabilityRegistry
            engine = ExecutiveRuntime(storage=storage, capability_registry=CapabilityRegistry(storage))
            register_executive(engine)
        storage.save(identity_id, "capability.executive", {"installed_at": None})

    def uninstall(self, identity_id: str, storage: Any) -> None:
        storage.delete(identity_id, "capability.executive")

    def prompts(self, identity_id: str) -> list[str]:
        return [
            "## Executive Runtime (MANDATORY for long-running work)\n"
            "You have an executive brain. When the user asks you to create, build, acquire, install, "
            "implement, or otherwise complete a multi-step goal:\n"
            "- Call executive.start_task(goal=\"<the full goal>\") FIRST. It persists the commitment.\n"
            "- Do NOT ask 'should I build it?' — the task is already committed and running.\n"
            "- When the user asks 'did you finish?', call executive.current_task / executive.task_status "
            "and report the REAL progress from the returned state. Never guess, never restart work that is in progress.\n"
            "- If a task exists but is blocked or interrupted, call executive.resume_task(task_id=...). Never restart it from scratch.\n"
            "- Use executive.cancel_task only when the user explicitly abandons the goal.\n"
            "- When you report completion, you MUST cite the evidence returned by the executive.\n",
        ]

    _SKILLS = [
        Skill(name="executive.start_task", description="Commit to a goal and create a persistent task", permission="public"),
        Skill(name="executive.resume_task", description="Resume a paused/blocked/failed task from its last completed step", permission="public"),
        Skill(name="executive.pause_task", description="Pause a running task", permission="public"),
        Skill(name="executive.cancel_task", description="Cancel a task", permission="public"),
        Skill(name="executive.complete_task", description="Mark a task complete with a result", permission="public"),
        Skill(name="executive.current_task", description="Return the currently active task with real progress", permission="public"),
        Skill(name="executive.active_tasks", description="List all queued/running/blocked tasks", permission="public"),
        Skill(name="executive.task_status", description="Return real status and progress for a task", permission="public"),
        Skill(name="executive.task_progress", description="Return the progress breakdown for a task", permission="public"),
        Skill(name="executive.checkpoint", description="Persist the current state of a task", permission="public"),
        Skill(name="executive.recover", description="Reload and resume any interrupted tasks", permission="public"),
        Skill(name="executive.history", description="Return recently completed/failed tasks", permission="public"),
    ]

    def skills(self) -> list[Skill]:
        return list(self._SKILLS)

    def call(self, skill_name: str, **params: Any) -> CapabilityResult:
        import time as _time

        _t0 = _time.monotonic()
        try:
            dispatch = {
                "executive.start_task": self._start_task,
                "executive.resume_task": self._resume_task,
                "executive.pause_task": self._pause_task,
                "executive.cancel_task": self._cancel_task,
                "executive.complete_task": self._complete_task,
                "executive.current_task": self._current_task,
                "executive.active_tasks": self._active_tasks,
                "executive.task_status": self._task_status,
                "executive.task_progress": self._task_progress,
                "executive.checkpoint": self._checkpoint,
                "executive.recover": self._recover,
                "executive.history": self._history,
            }
            handler = dispatch.get(skill_name)
            if handler is None:
                return CapabilityResult.fail("executive", skill_name, "unknown_skill", f"Unknown skill: {skill_name}")
            identity_id = params.pop("identity_id", None) or params.pop("identity", None) or ""
            data = handler(identity_id, **params)
            return CapabilityResult.from_data("executive", skill_name, data, source="executive runtime", duration_ms=(_time.monotonic() - _t0) * 1000)
        except Exception as e:
            return CapabilityResult.fail("executive", skill_name, type(e).__name__, str(e), duration_ms=(_time.monotonic() - _t0) * 1000)

    # ── Engine access ────────────────────────────────────────────────

    def _engine(self, identity_id: str) -> ExecutiveRuntime:
        engine = get_executive_for(self._storage) if self._storage is not None else None
        if engine is None:
            from core.capabilities.registry import CapabilityRegistry
            engine = ExecutiveRuntime(storage=self._storage, capability_registry=CapabilityRegistry(self._storage))
            register_executive(engine)
        return engine

    # ── Skill handlers ───────────────────────────────────────────────

    def _start_task(self, identity_id: str, goal: str = "", capability_id: str = "", priority: int = 0, **kwargs: Any) -> dict:
        if not goal:
            return {"error": "goal is required"}
        engine = self._engine(identity_id)
        task = engine.start_task(
            goal=goal,
            identity_id=identity_id,
            capability_id=capability_id or None,
            original_request=goal,
            priority=priority,
            autostart=True,
        )
        engine.scheduler.start()
        return {
            "task_id": task.task_id,
            "goal": task.goal,
            "status": task.status.value,
            "steps": len(task.steps),
            "message": "Task committed and running. Use executive.task_status to check real progress.",
        }

    def _resume_task(self, identity_id: str, task_id: str = "", **kwargs: Any) -> dict:
        if not task_id:
            return {"error": "task_id is required"}
        try:
            task = self._engine(identity_id).resume_task(identity_id, task_id)
            return {"task_id": task.task_id, "status": task.status.value, "resumed": True}
        except Exception as e:
            return {"error": str(e)}

    def _pause_task(self, identity_id: str, task_id: str = "", **kwargs: Any) -> dict:
        if not task_id:
            return {"error": "task_id is required"}
        task = self._engine(identity_id).pause_task(identity_id, task_id)
        return {"task_id": task.task_id, "status": task.status.value}

    def _cancel_task(self, identity_id: str, task_id: str = "", **kwargs: Any) -> dict:
        if not task_id:
            return {"error": "task_id is required"}
        task = self._engine(identity_id).cancel_task(identity_id, task_id)
        return {"task_id": task.task_id, "status": task.status.value}

    def _complete_task(self, identity_id: str, task_id: str = "", result: Any = None, **kwargs: Any) -> dict:
        if not task_id:
            return {"error": "task_id is required"}
        task = self._engine(identity_id).complete_task(identity_id, task_id, result={"result": result} if not isinstance(result, dict) else result)
        return {"task_id": task.task_id, "status": task.status.value}

    def _current_task(self, identity_id: str, **kwargs: Any) -> dict:
        engine = self._engine(identity_id)
        task = engine.current_task(identity_id)
        if task is None:
            return {"current_task": None, "message": "No active task."}
        return {"current_task": engine.task_status(identity_id, task.task_id)}

    def _active_tasks(self, identity_id: str, **kwargs: Any) -> dict:
        tasks = self._engine(identity_id).active_tasks(identity_id)
        return {
            "active_tasks": [
                {
                    "task_id": t.task_id,
                    "goal": t.goal,
                    "status": t.status.value,
                    "progress_percent": round(t.progress * 100, 1),
                    "current_step": t.current_step,
                }
                for t in tasks
            ],
            "count": len(tasks),
        }

    def _task_status(self, identity_id: str, task_id: str = "", **kwargs: Any) -> dict:
        if not task_id:
            return {"error": "task_id is required"}
        return self._engine(identity_id).task_status(identity_id, task_id)

    def _task_progress(self, identity_id: str, task_id: str = "", **kwargs: Any) -> dict:
        return self._task_status(identity_id, task_id)

    def _checkpoint(self, identity_id: str, task_id: str = "", **kwargs: Any) -> dict:
        if not task_id:
            return {"error": "task_id is required"}
        task = self._engine(identity_id).checkpoint(identity_id, task_id)
        return {"task_id": task.task_id, "status": task.status.value, "checkpoint": task.checkpoint}

    def _recover(self, identity_id: str, **kwargs: Any) -> dict:
        recovered = self._engine(identity_id).recover(identity_id)
        return {"recovered": [t.task_id for t in recovered], "count": len(recovered)}

    def _history(self, identity_id: str, **kwargs: Any) -> dict:
        return {"history": self._engine(identity_id).history(identity_id)}
