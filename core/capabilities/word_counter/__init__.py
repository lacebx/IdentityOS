from __future__ import annotations

from typing import Any, Optional
from core.capabilities.base import Capability, Skill
from core.capabilities.registry import register
from core.capabilities.result import CapabilityResult


@register
class WordCounterCapability(Capability):
    id = "word_counter"
    name = "Word Counter"
    version = "1.0.0"
    author = "auto-generated"
    license = "MIT"
    description = 'Count words in text'
    permissions = ["public"]

    def __init__(self, config: Optional[dict] = None) -> None:
        super().__init__(config)

    def install(self, identity_id: str, storage: Any) -> None:
        storage.save(identity_id, "capability.word_counter", {"installed_at": None})

    def uninstall(self, identity_id: str, storage: Any) -> None:
        storage.delete(identity_id, "capability.word_counter")

    def prompts(self, identity_id: str) -> list[str]:
        return [
            "## word_counter Skill",
            "Use word_counter.count when relevant. Do not invent results — call the skill.",
        ]

    _SKILLS = [
        Skill(name="word_counter.count", description="Count words in text", permission="public"),
    ]

    def skills(self) -> list[Skill]:
        return list(self._SKILLS)

    def call(self, skill_name: str, **params: Any) -> CapabilityResult:
        import time as _time
        _t0 = _time.monotonic()
        try:
            dispatch = {
                "word_counter.count": self._count,
            }
            handler = dispatch.get(skill_name)
            if handler is None:
                return CapabilityResult.fail("word_counter", skill_name, "unknown_skill", f"Unknown skill: {skill_name}")
            data = handler(**params)
            return CapabilityResult.ok("word_counter", skill_name, data, source="auto-generated", duration_ms=(_time.monotonic() - _t0) * 1000)
        except Exception as e:
            return CapabilityResult.fail("word_counter", skill_name, type(e).__name__, str(e), duration_ms=(_time.monotonic() - _t0) * 1000)

    def _count(self, **params: Any) -> dict[str, Any]:
        text = params.get("text") or params.get("message") or params.get("input") or ""
        return {"text": text, "chars": len(text), "words": len(text.split()), "goal_ok": True}
