from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional


@dataclass
class ScheduledEvent:
    tick: int
    callback: Callable
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    recurring_interval: Optional[int] = None
    fired: bool = False
    label: str = ""


class Scheduler:
    def __init__(self):
        self._events: List[ScheduledEvent] = []
        self._tick: int = 0

    def set_tick(self, tick: int) -> None:
        self._tick = tick

    def at(
        self,
        tick: int,
        callback: Callable,
        *args,
        label: str = "",
        **kwargs,
    ) -> ScheduledEvent:
        event = ScheduledEvent(
            tick=tick,
            callback=callback,
            args=args,
            kwargs=kwargs,
            label=label,
        )
        self._events.append(event)
        return event

    def every(
        self,
        interval_ticks: int,
        callback: Callable,
        *args,
        label: str = "",
        start_tick: int = 0,
        **kwargs,
    ) -> ScheduledEvent:
        event = ScheduledEvent(
            tick=start_tick,
            callback=callback,
            args=args,
            kwargs=kwargs,
            recurring_interval=interval_ticks,
            label=label,
        )
        self._events.append(event)
        return event

    def tick(self) -> List[Any]:
        fired_callbacks: List[Any] = []
        for event in self._events:
            if event.tick == self._tick and not event.fired:
                result = event.callback(*event.args, **event.kwargs)
                fired_callbacks.append(result)
                if event.recurring_interval is not None:
                    event.tick += event.recurring_interval
                else:
                    event.fired = True
        self._tick += 1
        return fired_callbacks

    def due_events(self) -> List[ScheduledEvent]:
        return [e for e in self._events if e.tick == self._tick and not e.fired]

    def reset(self) -> None:
        self._events.clear()
        self._tick = 0

    def pending_count(self) -> int:
        return sum(1 for e in self._events if not e.fired)
