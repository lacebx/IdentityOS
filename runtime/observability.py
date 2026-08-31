"""Low-overhead interaction timing primitives for the runtime boundary."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict


@dataclass
class InteractionTrace:
    """Accumulate monotonic stage timings without coupling pipeline stages."""

    interaction_id: str
    _started_at: float = field(default_factory=time.monotonic)
    _timings_ms: Dict[str, float] = field(default_factory=dict)

    @staticmethod
    def start_stage() -> float:
        return time.monotonic()

    def end_stage(self, name: str, started_at: float) -> float:
        duration_ms = max(0.0, (time.monotonic() - started_at) * 1000)
        self._timings_ms[name] = round(
            self._timings_ms.get(name, 0.0) + duration_ms,
            3,
        )
        return duration_ms

    def record(self, name: str, duration_ms: float) -> None:
        self._timings_ms[name] = round(max(0.0, duration_ms), 3)

    def finish(self) -> Dict[str, float]:
        timings = dict(self._timings_ms)
        timings["total"] = round(max(0.0, (time.monotonic() - self._started_at) * 1000), 3)
        return timings
