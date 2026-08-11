"""
resolver.py — Resolve a skill request against INSTALLED capabilities only.

There is deliberately no path that resolves against the global capability
registry: the resolver only ever surfaces skills the identity actually has
installed.  This closes the "skill name = capability-name branch" gap.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class Resolution:
    found: bool
    capability_id: str = ""
    skill_name: str = ""
    instance: Any = None
    reason: str = ""


class CapabilityResolver:
    """Resolve ``skill`` strings against the identity's installed abilities."""

    def __init__(self, capability_registry: Any, identity_id: str) -> None:
        self._registry = capability_registry
        self._identity_id = identity_id

    def resolve(self, skill_name: str) -> Resolution:
        """Resolve ``skill_name`` -> installed capability instance.

        ``skill_name`` may be fully qualified (``cap.skill``) or bare
        (``skill``) when exactly one installed capability provides it.
        """
        if not skill_name:
            return Resolution(found=False, reason="empty skill name")
        name = skill_name.strip()
        if "." in name:
            cap_id, _, sub = name.partition(".")
            inst = self._get_installed(cap_id)
            if inst is None:
                return Resolution(found=False, reason=f"no installed capability provides {cap_id!r}")
            if not self._has_skill(inst, name):
                return Resolution(found=False, capability_id=cap_id, skill_name=name,
                                  reason=f"{cap_id} does not expose skill {sub!r}")
            return Resolution(found=True, capability_id=cap_id, skill_name=name,
                              instance=inst, reason="installed")
        providers = []
        for cap_id, inst in self._iter_installed():
            if self._has_skill(inst, f"{cap_id}.{name}"):
                providers.append(cap_id)
        if not providers:
            return Resolution(found=False, reason=f"no installed capability provides skill {name!r}")
        if len(providers) > 1:
            return Resolution(found=False, reason=f"ambiguous skill {name!r} across {providers}")
        cap_id = providers[0]
        inst = self._get_installed(cap_id)
        return Resolution(found=True, capability_id=cap_id, skill_name=f"{cap_id}.{name}",
                          instance=inst, reason="installed")

    def list_skills(self) -> list[str]:
        out = []
        for cap_id, inst in self._iter_installed():
            for s in inst.skills() or []:
                out.append(s.name)
        return sorted(out)

    def _iter_installed(self) -> list[tuple[str, Any]]:
        if self._registry is None:
            return []
        try:
            caps = self._registry.list(self._identity_id)
        except Exception:
            return []
        return [(getattr(c, "id", "unknown"), c) for c in caps if c is not None]

    def _get_installed(self, cap_id: str) -> Optional[Any]:
        if self._registry is None:
            return None
        try:
            return self._registry.get(self._identity_id, cap_id)
        except Exception:
            return None

    @staticmethod
    def _has_skill(inst: Any, fq_name: str) -> bool:
        try:
            names = [s.name for s in inst.skills() or [] if getattr(s, "name", None)]
        except Exception:
            return False
        return any(n == fq_name or fq_name == n.split(".", 1)[-1] for n in names)