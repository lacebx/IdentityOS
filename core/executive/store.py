"""
store.py — Persistent task storage.

Tasks live under the identity's storage backend:

  namespace "executive.tasks"        -> {"task_ids": [...]}  (index)
  namespace "executive.task.<id>"    -> full task document

Per-task namespaces mean the scheduler can write one task while reads of
others proceed, and an interruption never loses more than the in-flight
step (checkpoints are written at every step boundary).
"""

from __future__ import annotations

from typing import Any, Optional

from core.executive.models import Task

_INDEX_NS = "executive.tasks"
_TASK_NS = "executive.task"


class TaskStore:
    def __init__(self, storage: Any) -> None:
        self._storage = storage

    # ── Index ────────────────────────────────────────────────────────

    def _index(self, identity_id: str) -> dict:
        raw = self._storage.load(identity_id, _INDEX_NS) or {}
        return {"task_ids": raw.get("task_ids", [])}

    def _save_index(self, identity_id: str, task_ids: list[str]) -> None:
        self._storage.save(identity_id, _INDEX_NS, {"task_ids": task_ids})

    def list_task_ids(self, identity_id: str) -> list[str]:
        return self._index(identity_id)["task_ids"]

    # ── CRUD ─────────────────────────────────────────────────────────

    def save(self, task: Task) -> None:
        self._storage.save(task.identity_id, self._task_ns(task.task_id), task.to_dict())
        ids = self._index(task.identity_id)["task_ids"]
        if task.task_id not in ids:
            ids.append(task.task_id)
            self._save_index(task.identity_id, ids)

    def load(self, identity_id: str, task_id: str) -> Optional[Task]:
        raw = self._storage.load(identity_id, self._task_ns(task_id))
        if raw is None:
            return None
        try:
            return Task.from_dict(raw)
        except Exception:
            return None

    def delete(self, identity_id: str, task_id: str) -> None:
        self._storage.delete(identity_id, self._task_ns(task_id))
        ids = self._index(identity_id)["task_ids"]
        if task_id in ids:
            ids.remove(task_id)
            self._save_index(identity_id, ids)

    def load_all(self, identity_id: str) -> list[Task]:
        tasks = []
        for task_id in self.list_task_ids(identity_id):
            t = self.load(identity_id, task_id)
            if t is not None:
                tasks.append(t)
        return tasks

    def load_active(self, identity_id: str) -> list[Task]:
        """Tasks still in progress (queued/running/blocked)."""
        return [
            t for t in self.load_all(identity_id)
            if t.status.value in ("queued", "running", "blocked")
        ]

    def load_terminal(self, identity_id: str) -> list[Task]:
        return [
            t for t in self.load_all(identity_id)
            if t.status.value in ("completed", "failed", "cancelled")
        ]

    @staticmethod
    def _task_ns(task_id: str) -> str:
        return f"{_TASK_NS}.{task_id}"
