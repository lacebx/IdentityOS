from __future__ import annotations

from typing import Any

from .base import Capability
from .result import CapabilityResult


class CapabilityProxy:
    """
    Wraps a Capability so skills are accessible as attributes.

    Usage::

        github = identity.use("github")
        results = github.search_repositories(query="identityos")
        # returns CapabilityResult — use .data for the raw result
    """

    def __init__(
        self,
        cap: Capability,
        registry: Any = None,
        identity_id: str = "",
    ) -> None:
        self._cap = cap
        self._registry = registry
        self._identity_id = identity_id

    @property
    def id(self) -> str:
        return self._cap.id

    @property
    def name(self) -> str:
        return self._cap.name

    @property
    def version(self) -> str:
        return self._cap.version

    def metadata(self) -> dict[str, Any]:
        return self._cap.to_dict()

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        skill_name = f"{self._cap.id}.{name}"
        can, reason = self._cap.can(skill_name)
        if not can:
            raise AttributeError(
                f"Capability '{self._cap.id}' has no skill '{name}'"
            )
        def caller(**params: Any) -> CapabilityResult:
            if self._registry is not None and self._identity_id:
                return self._registry.call(self._identity_id, skill_name, **params)
            return self._cap.call(skill_name, **params)
        caller.__name__ = name
        caller.__qualname__ = f"{type(self).__name__}.{name}"
        doc = next(
            (s.description for s in self._cap.skills() if s.name == skill_name),
            "",
        )
        caller.__doc__ = doc
        return caller

    def skills(self) -> list[dict[str, Any]]:
        return [
            {
                "name": s.name,
                "description": s.description,
                "permission": s.permission,
                "effect": s.effect,
                "input_schema": s.input_schema,
            }
            for s in self._cap.skills()
        ]
