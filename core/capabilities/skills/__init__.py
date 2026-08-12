"""Auto-generated generic capability: skills."""

from __future__ import annotations

from typing import Any, Optional

from core.capabilities.base import Capability, Skill
from core.capabilities.registry import register
from core.capabilities.result import CapabilityResult


@register
class SkillsCapability(Capability):
    id = "skills"
    name = "Skills"
    version = "1.0.0"
    author = "executive-generated"
    license = "MIT"
    description = "Generic capability scaffold for skills"
    permissions = ["public"]

    def __init__(self, config: Optional[dict] = None) -> None:
        super().__init__(config)

    def install(self, identity_id: str, storage: Any) -> None:
        storage.save(identity_id, "capability.skills", {"installed_at": None})

    def uninstall(self, identity_id: str, storage: Any) -> None:
        storage.delete(identity_id, "capability.skills")

    def prompts(self, identity_id: str) -> list[str]:
        return ["## Skills Skill\nUse skills.run to invoke skills, and skills.info for capability info."]

    _SKILLS = [
        Skill(name="skills.info", description="Return metadata about this capability", permission="public"),
        Skill(name="skills.run", description="Invoke the skills capability", permission="public"),
    ]

    def skills(self) -> list[Skill]:
        return list(self._SKILLS)

    def call(self, skill_name: str, **params: Any) -> CapabilityResult:
        import time as _time
        _t0 = _time.monotonic()
        try:
            dispatch = {
                "skills.info": self._info,
                "skills.run": self._run,
            }
            handler = dispatch.get(skill_name)
            if handler is None:
                return CapabilityResult.fail("skills", skill_name, "unknown_skill", f"Unknown skill: {skill_name}")
            data = handler(**params)
            return CapabilityResult.ok("skills", skill_name, data, source="executive scaffold", duration_ms=(_time.monotonic() - _t0) * 1000)
        except Exception as e:
            return CapabilityResult.fail("skills", skill_name, type(e).__name__, str(e), duration_ms=(_time.monotonic() - _t0) * 1000)

    def _info(self, **kwargs: Any) -> dict[str, Any]:
        return {
            "capability": "skills",
            "name": "Skills",
            "version": "1.0.0",
            "status": "available",
        }

    def _run(self, task: str = "", **kwargs: Any) -> dict[str, Any]:
        return {
            "capability": self.id,
            "task": task,
            "status": "completed",
            "detail": f"{self.id} executed: {task or 'no task'}",
        }
