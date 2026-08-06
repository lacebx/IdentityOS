"""
scheduler.py — Background task scheduler.

Runs queued/running tasks one step at a time on a daemon worker thread so an
identity can keep chatting while long-running work progresses.  Ordering is:

  1. RUNNING tasks (in priority order, then oldest first)
  2. QUEUED tasks (in priority order, then oldest first)

All step execution is serialized through a lock, so the JSON storage backend
never sees concurrent writes from this thread and the chat thread.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Optional


class TaskScheduler:
    def __init__(self, engine: Any, poll_interval: float = 0.15) -> None:
        self._engine = engine
        self._poll_interval = poll_interval
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="executive-scheduler",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                with self._lock:
                    self._engine.process_ready()
            except Exception:
                pass  # scheduler must never die; errors surface on the task
            self._stop.wait(self._poll_interval)

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()
