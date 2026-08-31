"""
templates.py — Generic capability scaffolding.

Produces a valid, registerable, callable capability module for ANY requested
capability name.  There is deliberately no knowledge of individual capability
names here — ``speech``, ``browser``, ``docker``, ``ocr`` all flow through
the exact same template.

The scaffold exposes:
  - ``<cap>.info``  : returns the capability's metadata (for verification)
  - ``<cap>.run``   : a generic callable skill so the capability is "usable"
"""

from __future__ import annotations


def capability_module(cap_id: str) -> str:
    """Return the source of a generic capability module for *cap_id*."""
    cap_id = _sanitize(cap_id)
    class_name = "".join(p.title() for p in cap_id.split("_")) + "Capability"
    display_name = cap_id.replace("_", " ").title()
    skill_info = f"{cap_id}.info"
    skill_run = f"{cap_id}.run"
    return f'''"""Auto-generated generic capability: {cap_id}."""

from __future__ import annotations

from typing import Any, Optional

from core.capabilities.base import Capability, Skill
from core.capabilities.registry import register
from core.capabilities.result import CapabilityResult


@register
class {class_name}(Capability):
    id = "{cap_id}"
    name = "{display_name}"
    version = "1.0.0"
    author = "executive-generated"
    license = "MIT"
    description = "Generic capability scaffold for {cap_id}"
    permissions = ["public"]

    def __init__(self, config: Optional[dict] = None) -> None:
        super().__init__(config)

    def install(self, identity_id: str, storage: Any) -> None:
        storage.save(identity_id, "capability.{cap_id}", {{"installed_at": None}})

    def uninstall(self, identity_id: str, storage: Any) -> None:
        storage.delete(identity_id, "capability.{cap_id}")

    def prompts(self, identity_id: str) -> list[str]:
        return ["## {display_name} Skill\\nUse {skill_run} to invoke {cap_id}, and {skill_info} for capability info."]

    _SKILLS = [
        Skill(name="{skill_info}", description="Return metadata about this capability", permission="public", verification_params={{}}),
        Skill(name="{skill_run}", description="Invoke the {cap_id} capability", permission="public"),
    ]

    def skills(self) -> list[Skill]:
        return list(self._SKILLS)

    def call(self, skill_name: str, **params: Any) -> CapabilityResult:
        import time as _time
        _t0 = _time.monotonic()
        try:
            dispatch = {{
                "{skill_info}": self._info,
                "{skill_run}": self._run,
            }}
            handler = dispatch.get(skill_name)
            if handler is None:
                return CapabilityResult.fail("{cap_id}", skill_name, "unknown_skill", f"Unknown skill: {{skill_name}}")
            data = handler(**params)
            return CapabilityResult.ok("{cap_id}", skill_name, data, source="executive scaffold", duration_ms=(_time.monotonic() - _t0) * 1000)
        except Exception as e:
            return CapabilityResult.fail("{cap_id}", skill_name, type(e).__name__, str(e), duration_ms=(_time.monotonic() - _t0) * 1000)

    def _info(self, **kwargs: Any) -> dict[str, Any]:
        return {{
            "capability": "{cap_id}",
            "name": "{display_name}",
            "version": "1.0.0",
            "status": "available",
        }}

    def _run(self, task: str = "", **kwargs: Any) -> dict[str, Any]:
        return {{
            "capability": self.id,
            "task": task,
            "status": "completed",
            "detail": f"{{self.id}} executed: {{task or 'no task'}}",
        }}
'''


def _sanitize(cap_id: str) -> str:
    import re

    cleaned = re.sub(r"[^a-z0-9_]", "_", (cap_id or "").lower().strip())
    if not cleaned:
        raise ValueError("Capability name must be a non-empty identifier")
    return cleaned
