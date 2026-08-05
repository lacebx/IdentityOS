from __future__ import annotations

from typing import Any, Optional
from core.capabilities.base import Capability, Skill
from core.capabilities.registry import register
from core.capabilities.result import CapabilityResult


@register
class TextReverserCapability(Capability):
    id = "text_reverser"
    name = "Text Reverser"
    version = "1.0.0"
    author = "auto-generated"
    license = "MIT"
    description = 'Auto-generated from goal: Create a capability called text_reverser that reverses strings, publish it to the registry, install it on yourself, then'
    permissions = ["public"]

    def __init__(self, config: Optional[dict] = None) -> None:
        super().__init__(config)

    def install(self, identity_id: str, storage: Any) -> None:
        storage.save(identity_id, "capability.text_reverser", {"installed_at": None})

    def uninstall(self, identity_id: str, storage: Any) -> None:
        storage.delete(identity_id, "capability.text_reverser")

    def prompts(self, identity_id: str) -> list[str]:
        return [
            "## text_reverser Skill",
            "Use text_reverser.reverse when relevant. Do not invent results — call the skill.",
        ]

    _SKILLS = [
        Skill(name="text_reverser.reverse", description="reverse skill", permission="public"),
    ]

    def skills(self) -> list[Skill]:
        return list(self._SKILLS)

    def call(self, skill_name: str, **params: Any) -> CapabilityResult:
        import time as _time
        _t0 = _time.monotonic()
        try:
            dispatch = {
                "text_reverser.reverse": self._reverse,
            }
            handler = dispatch.get(skill_name)
            if handler is None:
                return CapabilityResult.fail("text_reverser", skill_name, "unknown_skill", f"Unknown skill: {skill_name}")
            data = handler(**params)
            return CapabilityResult.ok("text_reverser", skill_name, data, source="auto-generated", duration_ms=(_time.monotonic() - _t0) * 1000)
        except Exception as e:
            return CapabilityResult.fail("text_reverser", skill_name, type(e).__name__, str(e), duration_ms=(_time.monotonic() - _t0) * 1000)

    def _reverse(self, **params: Any) -> dict[str, Any]:
        text = params.get("text") or params.get("message") or params.get("input") or ""
        return {"original": text, "reversed": text[::-1], "goal_ok": True}
