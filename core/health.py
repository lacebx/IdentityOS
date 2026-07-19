"""
core/health.py

HealthEngine — system health monitoring interface for IdentityOS.

Tracks module status, last-check timestamps, and provides a simple
health-check endpoint for the orchestrator and API layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Optional


@dataclass
class HealthCheck:
    name: str = ""
    status: str = "unknown"  # "ok" | "degraded" | "down"
    detail: str = ""
    last_checked: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, str] = field(default_factory=dict)


class HealthEngine:
    """Simple health monitoring for the runtime modules."""

    def __init__(self):
        self._checks: Dict[str, HealthCheck] = {}

    def register(self, check: HealthCheck) -> None:
        self._checks[check.name] = check

    def report(self, name: str, status: str, detail: str = "") -> None:
        if name in self._checks:
            self._checks[name].status = status
            self._checks[name].detail = detail
            self._checks[name].last_checked = datetime.now(timezone.utc)

    def all_ok(self) -> bool:
        return all(c.status == "ok" for c in self._checks.values())

    def summary(self) -> Dict[str, str]:
        return {c.name: c.status for c in self._checks.values()}

    def __repr__(self) -> str:
        ok = sum(1 for c in self._checks.values() if c.status == "ok")
        return f"HealthEngine(checks={len(self._checks)}, ok={ok})"
