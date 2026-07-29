from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from typing import Optional


class SimulatedClock:
    def __init__(
        self,
        start_date: Optional[datetime] = None,
        tick_unit: int = 3600,
        seed: int = 42,
    ):
        self.current = start_date or datetime(2025, 1, 1, tzinfo=timezone.utc)
        self.tick_unit = tick_unit
        self.tick_count = 0
        self._rng = random.Random(seed)

    def advance(self, ticks: int = 1) -> None:
        self.current += timedelta(seconds=ticks * self.tick_unit)
        self.tick_count += ticks

    def advance_to(self, target: datetime) -> None:
        delta = (target - self.current).total_seconds()
        ticks = max(1, int(delta / self.tick_unit))
        self.advance(ticks)

    def now(self) -> datetime:
        return self.current

    def random(self, low: float = 0.0, high: float = 1.0) -> float:
        return self._rng.uniform(low, high)

    def randint(self, low: int, high: int) -> int:
        return self._rng.randint(low, high)

    def state(self) -> dict:
        return {
            "current": self.current.isoformat(),
            "tick_unit": self.tick_unit,
            "tick_count": self.tick_count,
        }

    @classmethod
    def from_state(cls, state: dict) -> SimulatedClock:
        clock = cls(
            start_date=datetime.fromisoformat(state["current"]),
            tick_unit=state["tick_unit"],
        )
        clock.tick_count = state["tick_count"]
        return clock
