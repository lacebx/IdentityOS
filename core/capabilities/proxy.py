from __future__ import annotations

from typing import Any

from .base import Capability


class CapabilityProxy:
    """
    Wraps a ``Capability`` so skills are accessible as attributes.

    Usage::

        github = identity.use("github")
        github.search_repositories(query="identityos")
        github.review_pull_request(owner="lacebx", repo="IdentityOS", number=1)
    """

    def __init__(self, cap: Capability) -> None:
        self._cap = cap

    # ── Metadata passthrough ───────────────────────────────────────────

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

    # ── Skill routing ──────────────────────────────────────────────────

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        skill_name = f"{self._cap.id}.{name}"
        can, reason = self._cap.can(skill_name)
        if not can:
            raise AttributeError(
                f"Capability '{self._cap.id}' has no skill '{name}'"
            )
        def caller(**params: Any) -> Any:
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
            {"name": s.name, "description": s.description, "permission": s.permission}
            for s in self._cap.skills()
        ]
