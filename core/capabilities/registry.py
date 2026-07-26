from __future__ import annotations

from typing import Any, Optional

from .base import Capability, Skill

# ── v0: static in-process registry ─────────────────────────────────────
# Future: entry_points discovery, pip-installed packages, plugins/
_BUILTIN_CAPABILITIES: dict[str, type[Capability]] = {}


def register(cap_cls: type[Capability]) -> type[Capability]:
    _BUILTIN_CAPABILITIES[cap_cls.id] = cap_cls
    return cap_cls


def lookup(cap_id: str) -> type[Capability]:
    cls = _BUILTIN_CAPABILITIES.get(cap_id)
    if cls is None:
        raise ValueError(
            f"Unknown capability '{cap_id}'. "
            f"Available: {list(_BUILTIN_CAPABILITIES.keys())}"
        )
    return cls


def available() -> list[str]:
    return list(_BUILTIN_CAPABILITIES.keys())


# ── Per-identity registry ──────────────────────────────────────────────


class CapabilityRegistry:
    """
    Manages installed capabilities for identities.

    Each identity stores its installed-capability list under the
    ``capabilities`` namespace in its storage backend.  On load the
    registry re-instantiates ``Capability`` objects so they can inject
    prompts, expose skills, and handle ``call()``.
    """

    CAP_NAMESPACE = "capabilities"

    def __init__(self, storage: Any) -> None:
        self._storage = storage
        # identity_id -> {cap_id: Capability}
        self._loaded: dict[str, dict[str, Capability]] = {}

    # ── Internal helpers ───────────────────────────────────────────────

    def _load_identity_caps(self, identity_id: str) -> dict[str, Capability]:
        if identity_id not in self._loaded:
            raw = self._storage.load(identity_id, self.CAP_NAMESPACE)
            entries = raw.get("installed", []) if raw else []
            instances: dict[str, Capability] = {}
            for entry in entries:
                cap_id = entry["id"]
                config = entry.get("config", {})
                try:
                    cls = lookup(cap_id)
                    instances[cap_id] = cls(config=config)
                except ValueError:
                    pass  # skip capabilities whose class isn't loaded
            self._loaded[identity_id] = instances
        return self._loaded[identity_id]

    def _save(self, identity_id: str) -> None:
        instances = self._loaded.get(identity_id, {})
        entries = [
            {"id": c.id, "version": c.version, "config": c._config}
            for c in instances.values()
        ]
        self._storage.save(identity_id, self.CAP_NAMESPACE, {"installed": entries})

    # ── Public API ─────────────────────────────────────────────────────

    def install(
        self, identity_id: str, cap_id: str, config: Optional[dict] = None
    ) -> Capability:
        cls = lookup(cap_id)
        cap = cls(config=config or {})
        cap.install(identity_id, self._storage)
        caps = self._load_identity_caps(identity_id)
        caps[cap_id] = cap
        self._save(identity_id)
        return cap

    def uninstall(self, identity_id: str, cap_id: str) -> None:
        caps = self._load_identity_caps(identity_id)
        if cap_id in caps:
            caps[cap_id].uninstall(identity_id, self._storage)
            del caps[cap_id]
            self._save(identity_id)

    def get(self, identity_id: str, cap_id: str) -> Optional[Capability]:
        return self._load_identity_caps(identity_id).get(cap_id)

    def list(self, identity_id: str) -> list[Capability]:
        return list(self._load_identity_caps(identity_id).values())

    def all_prompts(self, identity_id: str) -> list[str]:
        prompts: list[str] = []
        for cap in self.list(identity_id):
            prompts.extend(cap.prompts(identity_id))
        return prompts

    def all_skills(self, identity_id: str) -> list[Skill]:
        skills: list[Skill] = []
        for cap in self.list(identity_id):
            skills.extend(cap.skills())
        return skills

    def can(self, identity_id: str, skill_name: str) -> tuple[bool, str]:
        for cap in self.list(identity_id):
            ok, reason = cap.can(skill_name)
            if ok:
                return (True, "")
        return (False, f"No installed capability provides skill: {skill_name}")

    def call(self, identity_id: str, skill_name: str, **params: Any) -> Any:
        cap = self._find_capability_for_skill(identity_id, skill_name)
        if cap is None:
            raise ValueError(
                f"No installed capability provides skill: {skill_name}"
            )
        return cap.call(skill_name, **params)

    def _find_capability_for_skill(
        self, identity_id: str, skill_name: str
    ) -> Optional[Capability]:
        for cap in self.list(identity_id):
            ok, _ = cap.can(skill_name)
            if ok:
                return cap
        return None
