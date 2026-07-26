from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Skill:
    name: str
    description: str
    permission: str = "public"
    version: str = "1.0.0"


class Capability(ABC):
    id: str = ""
    name: str = ""
    version: str = "0.1.0"
    author: str = "unknown"
    license: str = "MIT"
    homepage: str = ""
    description: str = ""
    permissions: list[str] = field(default_factory=lambda: ["public"])

    def __init__(self, config: Optional[dict] = None) -> None:
        self._config = config or {}

    # ── Lifecycle ──────────────────────────────────────────────────────

    @abstractmethod
    def install(self, identity_id: str, storage: Any) -> None:
        """Set up storage namespaces, register state, etc."""

    @abstractmethod
    def uninstall(self, identity_id: str, storage: Any) -> None:
        """Clean up all storage artifacts created by this capability."""

    # ── Runtime interface ──────────────────────────────────────────────

    @abstractmethod
    def prompts(self, identity_id: str) -> list[str]:
        """Prompt fragments injected into the system message."""

    @abstractmethod
    def skills(self) -> list[Skill]:
        """All skills this capability exposes."""

    def tool_defs(self) -> list[dict]:
        """OpenAI-compatible tool definitions for each skill.

        Override to provide precise parameter schemas.
        """
        defs = []
        for s in self.skills():
            defs.append({
                "type": "function",
                "function": {
                    "name": s.name,
                    "description": s.description,
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "additionalProperties": True,
                    },
                },
            })
        return defs

    def can(self, skill_name: str) -> tuple[bool, str]:
        for s in self.skills():
            if s.name == skill_name:
                return (True, "")
        return (False, f"Unknown skill: {skill_name}")

    @abstractmethod
    def call(self, skill_name: str, **params: Any) -> Any:
        """Execute a skill and return the result."""

    # ── Event hooks (reserved — no-op by default) ─────────────────────

    def on_message(self, message: Any) -> None:
        pass

    def on_identity_loaded(self, identity_id: str) -> None:
        pass

    def on_memory_created(self, memory: Any) -> None:
        pass

    def on_goal_completed(self, goal: Any) -> None:
        pass

    # ── Inspection ─────────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "author": self.author,
            "license": self.license,
            "homepage": self.homepage,
            "description": self.description,
            "permissions": self.permissions,
            "skills": [s.name for s in self.skills()],
        }
