"""Auto-generated generic capability: speech."""

from __future__ import annotations

from typing import Any, Optional

from core.capabilities.base import Capability, Skill
from core.capabilities.registry import register
from core.capabilities.result import CapabilityResult


@register
class SpeechCapability(Capability):
    id = "speech"
    name = "Speech"
    version = "1.0.0"
    author = "executive-generated"
    license = "MIT"
    description = "Generic capability scaffold for speech"
    permissions = ["public"]

    def __init__(self, config: Optional[dict] = None) -> None:
        super().__init__(config)

    def install(self, identity_id: str, storage: Any) -> None:
        storage.save(identity_id, "capability.speech", {"installed_at": None})

    def uninstall(self, identity_id: str, storage: Any) -> None:
        storage.delete(identity_id, "capability.speech")

    def prompts(self, identity_id: str) -> list[str]:
        return ["## Speech Skill\nUse speech.run to invoke speech, and speech.info for capability info."]

    _SKILLS = [
        Skill(name="speech.info", description="Return metadata about this capability", permission="public"),
        Skill(name="speech.run", description="Invoke the speech capability", permission="public"),
    ]

    def skills(self) -> list[Skill]:
        return list(self._SKILLS)

    def call(self, skill_name: str, **params: Any) -> CapabilityResult:
        import time as _time
        _t0 = _time.monotonic()
        try:
            dispatch = {
                "speech.info": self._info,
                "speech.run": self._run,
            }
            handler = dispatch.get(skill_name)
            if handler is None:
                return CapabilityResult.fail("speech", skill_name, "unknown_skill", f"Unknown skill: {skill_name}")
            data = handler(**params)
            return CapabilityResult.ok("speech", skill_name, data, source="executive scaffold", duration_ms=(_time.monotonic() - _t0) * 1000)
        except Exception as e:
            return CapabilityResult.fail("speech", skill_name, type(e).__name__, str(e), duration_ms=(_time.monotonic() - _t0) * 1000)

    def _info(self, **kwargs: Any) -> dict[str, Any]:
        return {
            "capability": "speech",
            "name": "Speech",
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
