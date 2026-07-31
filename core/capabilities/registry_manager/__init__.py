from __future__ import annotations

import json
import os
from typing import Any, Optional

from core.capabilities.base import Capability, Skill
from core.capabilities.registry import register
from core.capabilities.result import CapabilityResult


@register
class RegistryManagerCapability(Capability):
    id = "registry_manager"
    name = "Registry Manager"
    version = "1.0.0"
    author = "IdentityOS"
    license = "MIT"
    homepage = "https://github.com/lacebx/IdentityOS"
    description = "Publish new capabilities to the registry, install capabilities from the registry, and list available capabilities"
    permissions = ["public"]

    def __init__(self, config: Optional[dict] = None) -> None:
        super().__init__(config)

    def install(self, identity_id: str, storage: Any) -> None:
        storage.save(identity_id, "capability.registry_manager", {"installed_at": None})

    def uninstall(self, identity_id: str, storage: Any) -> None:
        storage.delete(identity_id, "capability.registry_manager")

    def prompts(self, identity_id: str) -> list[str]:
        return [
            "## Registry Manager Skills (MANDATORY — use for publishing and installing capabilities)",
            "When you need to publish a new skill to the registry, install a capability, or list available capabilities, you MUST use the skills below.",
            "You have the ability to read the registry index, publish new capability manifests, and install capabilities onto your identity.",
            "Use these skills when you want to evolve your capabilities autonomously.",
        ]

    _SKILLS = [
        Skill(name="registry_manager.list_capabilities", description="List all capabilities available in the local registry", permission="public"),
        Skill(name="registry_manager.publish_capability", description="Publish a new capability to the local registry with a manifest", permission="public"),
        Skill(name="registry_manager.install_capability", description="Install a capability from the registry onto the current identity", permission="public"),
    ]

    def skills(self) -> list[Skill]:
        return list(self._SKILLS)

    def call(self, skill_name: str, **params: Any) -> CapabilityResult:
        import time as _time
        _t0 = _time.monotonic()
        try:
            dispatch = {
                "registry_manager.list_capabilities": self._list_capabilities,
                "registry_manager.publish_capability": self._publish_capability,
                "registry_manager.install_capability": self._install_capability,
            }
            handler = dispatch.get(skill_name)
            if handler is None:
                return CapabilityResult.fail("registry_manager", skill_name, "unknown_skill", f"Unknown skill: {skill_name}")
            data = handler(**params)
            return CapabilityResult.ok("registry_manager", skill_name, data, source="local registry", duration_ms=(_time.monotonic() - _t0) * 1000)
        except Exception as e:
            return CapabilityResult.fail("registry_manager", skill_name, type(e).__name__, str(e), duration_ms=(_time.monotonic() - _t0) * 1000)

    def _registry_path(self) -> str:
        base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "registry")
        return os.path.abspath(base)

    def _load_index(self) -> dict[str, Any]:
        idx_path = os.path.join(self._registry_path(), "index.json")
        if not os.path.isfile(idx_path):
            return {"capabilities": []}
        with open(idx_path) as f:
            return json.load(f)

    def _save_index(self, index: dict[str, Any]) -> None:
        idx_path = os.path.join(self._registry_path(), "index.json")
        with open(idx_path, "w") as f:
            json.dump(index, f, indent=2)

    def _list_capabilities(self, **kwargs: Any) -> dict[str, Any]:
        index = self._load_index()
        caps = index.get("capabilities", [])
        return {
            "capabilities": [
                {
                    "id": c.get("id", "?"),
                    "name": c.get("name", "?"),
                    "version": c.get("version", "?"),
                    "description": c.get("description", ""),
                    "skills": c.get("skills", []),
                }
                for c in caps
            ],
            "count": len(caps),
        }

    def _publish_capability(self, cap_id: str = "", name: str = "", version: str = "1.0.0", description: str = "", skills: Optional[list] = None, **kwargs: Any) -> dict[str, Any]:
        if not cap_id:
            return {"error": "cap_id is required"}
        if not name:
            return {"error": "name is required"}
        index = self._load_index()
        caps = index.get("capabilities", [])
        existing = [c for c in caps if c.get("id") == cap_id]
        if existing:
            existing[0]["version"] = version
            existing[0]["updated"] = True
        else:
            caps.append({
                "id": cap_id,
                "name": name,
                "version": version,
                "description": description,
                "skills": skills or [],
                "published": "auto",
            })
        index["capabilities"] = caps
        self._save_index(index)
        return {
            "cap_id": cap_id,
            "name": name,
            "version": version,
            "status": "published",
            "total_capabilities": len(caps),
        }

    def _install_capability(self, cap_id: str = "", **kwargs: Any) -> dict[str, Any]:
        if not cap_id:
            return {"error": "cap_id is required"}
        index = self._load_index()
        caps = index.get("capabilities", [])
        match = next((c for c in caps if c.get("id") == cap_id), None)
        if not match:
            return {"error": f"Capability '{cap_id}' not found in registry"}
        return {
            "cap_id": match["id"],
            "name": match.get("name", cap_id),
            "version": match.get("version", "?"),
            "status": "ready_to_install",
            "description": match.get("description", ""),
            "message": f"To install: runtime.capability_registry.install('<identity_id>', '{cap_id}')",
        }
