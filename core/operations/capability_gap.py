"""
core/operations/capability_gap.py

Capability-gap detection and acquisition.

An operator adapts to its environment: if a required skill (e.g. sending email)
is not installed, that is a *runtime fact* to be detected, recorded as a need,
and resolved through the existing capability-acquisition machinery — never
assumed away.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from .store import OperationsStore


@dataclass
class CapabilityGap:
    required_skill: str
    category: str = "capability"
    reason: str = ""
    resolved: bool = False
    resolution: str = ""
    evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "required_skill": self.required_skill,
            "category": self.category,
            "reason": self.reason,
            "resolved": self.resolved,
            "resolution": self.resolution,
            "evidence": list(self.evidence),
        }


class CapabilityGapDetector:
    """Checks required skills against installed capabilities and tries to fill gaps."""

    def __init__(
        self,
        *,
        capability_registry: Any = None,
        identity_id: str = "",
        acquisition: Optional[Callable[[str], tuple[bool, str]]] = None,
        store: Optional[OperationsStore] = None,
    ) -> None:
        self._registry = capability_registry
        self._identity_id = identity_id
        self._acquisition = acquisition
        self._store = store

    def check(self, required_skills: list[str]) -> list[CapabilityGap]:
        gaps: list[CapabilityGap] = []
        for skill in required_skills:
            if self._registry is None:
                # No registry wired in: cannot verify availability. Report the
                # gap honestly rather than claiming the skill exists.
                gaps.append(CapabilityGap(required_skill=skill, reason="no capability registry wired", evidence=["registry=absent"]))
                continue
            try:
                allowed, reason = self._registry.can(self._identity_id, skill)
            except Exception as exc:  # pragma: no cover - defensive
                gaps.append(CapabilityGap(required_skill=skill, reason=f"registry error: {exc}", evidence=["registry=error"]))
                continue
            if not allowed:
                gaps.append(CapabilityGap(required_skill=skill, reason=reason or "skill not available", evidence=["registry=missing"]))
        return gaps

    def resolve(self, gap: CapabilityGap) -> CapabilityGap:
        """Attempt acquisition through the configured resolver."""
        if self._acquisition is None:
            gap.resolution = "no acquisition mechanism configured"
            self._record_gap_need(gap)
            return gap
        try:
            ok, detail = self._acquisition(gap.required_skill)
        except Exception as exc:  # pragma: no cover - defensive
            gap.resolution = f"acquisition failed: {exc}"
            self._record_gap_need(gap)
            return gap
        gap.resolved = bool(ok)
        gap.resolution = detail or ("acquired" if ok else "acquisition declined")
        gap.evidence.append(f"acquisition:{gap.resolution}")
        self._record_gap_need(gap)
        return gap

    def _record_gap_need(self, gap: CapabilityGap) -> None:
        if self._store is None or gap.resolved:
            return
        from .needs import NeedDetector

        NeedDetector.ensure_need(
            self._store,
            category=gap.category,
            description=f"Missing required capability for skill '{gap.required_skill}'",
            evidence=list(gap.evidence),
            urgency=0.6,
            impact=0.7,
        )
