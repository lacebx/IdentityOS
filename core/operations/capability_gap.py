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
from enum import Enum
from typing import Any, Callable, Optional

from .store import OperationsStore


class CapabilityStatus(str, Enum):
    """Why a required skill is currently unavailable (or whether it is ready)."""

    READY = "ready"
    CAPABILITY_MISSING = "capability_missing"
    AVAILABLE_NOT_INSTALLED = "available_not_installed"
    INSTALLED_PERMISSION_MISSING = "installed_permission_missing"


@dataclass
class CapabilityGap:
    required_skill: str
    category: str = "capability"
    reason: str = ""
    resolved: bool = False
    resolution: str = ""
    evidence: list[str] = field(default_factory=list)
    status: str = CapabilityStatus.CAPABILITY_MISSING.value

    def to_dict(self) -> dict[str, Any]:
        return {
            "required_skill": self.required_skill,
            "category": self.category,
            "reason": self.reason,
            "resolved": self.resolved,
            "resolution": self.resolution,
            "evidence": list(self.evidence),
            "status": self.status,
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
                gaps.append(CapabilityGap(
                    required_skill=skill,
                    reason="no capability registry wired",
                    evidence=["registry=absent"],
                    status=CapabilityStatus.CAPABILITY_MISSING.value,
                ))
                continue
            try:
                allowed, reason = self._registry.can(self._identity_id, skill)
            except Exception as exc:  # pragma: no cover - defensive
                gaps.append(CapabilityGap(
                    required_skill=skill, reason=f"registry error: {exc}",
                    evidence=["registry=error"],
                    status=CapabilityStatus.CAPABILITY_MISSING.value,
                ))
                continue
            if not allowed:
                status, detail, evidence = self._diagnose(skill, reason)
                gaps.append(CapabilityGap(
                    required_skill=skill, reason=detail,
                    evidence=evidence, status=status.value,
                ))
        return gaps

    def _diagnose(self, skill: str, permission_reason: str) -> tuple[CapabilityStatus, str, list[str]]:
        """Classify *why* a skill is unavailable.

        Installed but permission-denied beats merely available; available-but-
        not-installed beats entirely missing.  This lets the operator distinguish
        "install it" from "ask the principal to grant `web.search`".
        """
        installed_provider = self._find_installed_provider(skill)
        if installed_provider is not None:
            return (
                CapabilityStatus.INSTALLED_PERMISSION_MISSING,
                permission_reason or f"installed '{installed_provider.id}' but permission denied",
                ["installed=yes", "permission=denied", f"capability={installed_provider.id}"],
            )
        available_cap = self._find_available_provider(skill)
        if available_cap:
            return (
                CapabilityStatus.AVAILABLE_NOT_INSTALLED,
                f"capability '{available_cap}' is available but not installed",
                ["installed=no", f"available_capability={available_cap}"],
            )
        return (
            CapabilityStatus.CAPABILITY_MISSING,
            permission_reason or "no capability provides this skill",
            ["installed=no", "available=no"],
        )

    def _find_installed_provider(self, skill: str) -> Any:
        if self._registry is None:
            return None
        try:
            for cap in self._registry.list(self._identity_id):
                try:
                    if any(s.name == skill for s in cap.skills()):
                        return cap
                except Exception:
                    continue
        except Exception:
            return None
        return None

    def _find_available_provider(self, skill: str) -> str:
        """Return a built-in (registered) capability id that provides the skill."""
        try:
            from core.capabilities.registry import available, lookup

            for cap_id in available():
                try:
                    instance = lookup(cap_id)(config={})
                    if any(s.name == skill for s in instance.skills()):
                        return cap_id
                except Exception:
                    continue
        except Exception:
            return ""
        return ""

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
