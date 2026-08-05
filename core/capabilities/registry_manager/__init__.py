from __future__ import annotations

import json
import os
from typing import Any, Optional

from core.capabilities.base import Capability, Skill
from core.capabilities.registry import register, available, import_capability
from core.capabilities.result import CapabilityResult


@register
class RegistryManagerCapability(Capability):
    id = "registry_manager"
    name = "Registry Manager"
    version = "1.1.0"
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
            "Use inventory to accurately report installed vs available capabilities — NEVER invent capabilities or claim install success without inventory confirmation.",
            "IMPORTANT: Prefer installing an existing registry capability over creating a duplicate (acquire-before-invent).",
            "Use these skills when you want to evolve your capabilities autonomously.",
            "Never claim a capability is installed unless registry_manager.install_capability returned status='installed' AND goal_ok=true.",
        ]

    _SKILLS = [
        Skill(name="registry_manager.list_capabilities", description="List all capabilities available in the local registry", permission="public"),
        Skill(name="registry_manager.inventory", description="Show installed capabilities vs registry-available (not installed) for this identity", permission="public"),
        Skill(name="registry_manager.publish_capability", description="Publish a new capability to the local registry with a manifest", permission="public"),
        Skill(name="registry_manager.install_capability", description="Install a capability from the registry onto the current identity (real install)", permission="public"),
        Skill(name="registry_manager.create_and_deploy", description="Create a new capability module, validate, publish, install on self, and probe it", permission="public"),
    ]

    def skills(self) -> list[Skill]:
        return list(self._SKILLS)

    def call(self, skill_name: str, **params: Any) -> CapabilityResult:
        import time as _time
        _t0 = _time.monotonic()
        try:
            dispatch = {
                "registry_manager.list_capabilities": self._list_capabilities,
                "registry_manager.inventory": self._inventory,
                "registry_manager.publish_capability": self._publish_capability,
                "registry_manager.install_capability": self._install_capability,
                "registry_manager.create_and_deploy": self._create_and_deploy,
            }
            handler = dispatch.get(skill_name)
            if handler is None:
                return CapabilityResult.fail("registry_manager", skill_name, "unknown_skill", f"Unknown skill: {skill_name}")
            data = handler(**params)
            return CapabilityResult.ok(
                "registry_manager",
                skill_name,
                data,
                source="local registry",
                duration_ms=(_time.monotonic() - _t0) * 1000,
            )
        except Exception as e:
            return CapabilityResult.fail(
                "registry_manager",
                skill_name,
                type(e).__name__,
                str(e),
                duration_ms=(_time.monotonic() - _t0) * 1000,
            )

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
            f.write("\n")

    def _resolve_identity_id(self, identity_id: str = "", **kwargs: Any) -> str:
        return (
            identity_id
            or kwargs.get("identity_id", "")
            or getattr(self, "_identity_id", "")
            or ""
        )

    def _resolve_registry(self) -> Any:
        return getattr(self, "_capability_registry", None)

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
            "goal_ok": True,
        }

    def _inventory(self, identity_id: str = "", **kwargs: Any) -> dict[str, Any]:
        identity_id = self._resolve_identity_id(identity_id, **kwargs)
        reg = self._resolve_registry()
        index = self._load_index()
        available_caps = index.get("capabilities", [])
        installed_ids: list[str] = []
        installed_detail: list[dict[str, Any]] = []
        if reg is not None and identity_id:
            for cap in reg.list(identity_id):
                installed_ids.append(cap.id)
                installed_detail.append({
                    "id": cap.id,
                    "name": cap.name,
                    "version": cap.version,
                    "skills": [s.name for s in cap.skills()],
                })
        not_installed = [
            {
                "id": c.get("id", "?"),
                "name": c.get("name", "?"),
                "description": c.get("description", ""),
            }
            for c in available_caps
            if c.get("id") not in installed_ids
        ]
        cannot_do = []
        if "web" not in installed_ids:
            cannot_do.append("fetch/browse arbitrary web pages (install 'web')")
        if "datetime" not in installed_ids:
            cannot_do.append("report live local timezones (install 'datetime')")
        if not cannot_do:
            cannot_do.append("capabilities not present in the registry without creating them first")
        return {
            "identity_id": identity_id or None,
            "installed": installed_detail,
            "installed_ids": installed_ids,
            "available_not_installed": not_installed,
            "registry_count": len(available_caps),
            "example_gaps": cannot_do,
            "goal_ok": bool(identity_id and reg is not None),
            "error": None if (identity_id and reg is not None) else "identity_id or capability_registry not bound",
        }

    def _publish_capability(
        self,
        cap_id: str = "",
        name: str = "",
        version: str = "1.0.0",
        description: str = "",
        skills: Optional[list] = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        if not cap_id:
            return {"error": "cap_id is required", "goal_ok": False}
        if not name:
            name = cap_id.replace("_", " ").title()
        index = self._load_index()
        caps = index.get("capabilities", [])
        existing = [c for c in caps if c.get("id") == cap_id]
        entry = {
            "id": cap_id,
            "name": name,
            "version": version,
            "description": description,
            "skills": skills or [],
            "published": "auto",
        }
        if existing:
            existing[0].update(entry)
            existing[0]["updated"] = True
        else:
            caps.append(entry)
        index["capabilities"] = caps
        self._save_index(index)

        # Hot-import if module exists on disk
        module_loaded = False
        module_error = None
        cap_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", cap_id, "__init__.py"
        )
        if os.path.isfile(os.path.abspath(cap_dir)):
            try:
                import_capability(cap_id)
                module_loaded = True
            except Exception as e:
                module_error = str(e)

        # Postcondition: entry must exist in index
        reloaded = self._load_index()
        found = any(c.get("id") == cap_id for c in reloaded.get("capabilities", []))
        return {
            "cap_id": cap_id,
            "name": name,
            "version": version,
            "status": "published" if found else "publish_failed",
            "total_capabilities": len(caps),
            "module_loaded": module_loaded,
            "module_error": module_error,
            "goal_ok": found,
            "error": None if found else "index entry missing after save",
        }

    def _install_capability(self, cap_id: str = "", identity_id: str = "", **kwargs: Any) -> dict[str, Any]:
        if not cap_id:
            return {"error": "cap_id is required", "goal_ok": False}
        identity_id = self._resolve_identity_id(identity_id, **kwargs)
        reg = self._resolve_registry()
        if not identity_id:
            return {"error": "identity_id is required for real install", "goal_ok": False}
        if reg is None:
            return {
                "error": "capability_registry not bound on this skill instance — cannot install",
                "goal_ok": False,
            }

        index = self._load_index()
        caps = index.get("capabilities", [])
        match = next((c for c in caps if c.get("id") == cap_id), None)
        # Allow install of builtin modules even if not yet in index
        if match is None and cap_id not in available():
            # try import from disk
            try:
                import_capability(cap_id)
            except Exception as e:
                return {
                    "error": f"Capability '{cap_id}' not found in registry and cannot import: {e}",
                    "goal_ok": False,
                }

        if cap_id not in available():
            try:
                import_capability(cap_id)
            except Exception as e:
                return {"error": f"Cannot load capability module '{cap_id}': {e}", "goal_ok": False}

        try:
            cap = reg.install(identity_id, cap_id)
        except Exception as e:
            return {"error": f"Install failed: {e}", "goal_ok": False}

        installed = reg.get(identity_id, cap_id) is not None
        skill_names = [s.name for s in cap.skills()] if cap else []
        return {
            "cap_id": cap.id if cap else cap_id,
            "name": cap.name if cap else cap_id,
            "version": cap.version if cap else "?",
            "status": "installed" if installed else "install_failed",
            "skills": skill_names,
            "identity_id": identity_id,
            "goal_ok": installed,
            "error": None if installed else "capability missing after install",
            "message": f"Installed '{cap_id}' onto identity '{identity_id}'" if installed else "install failed",
        }

    def _create_and_deploy(
        self,
        cap_id: str = "",
        name: str = "",
        description: str = "",
        skill_short: str = "",
        skill_kind: str = "echo",
        identity_id: str = "",
        code: str = "",
        probe_text: str = "hello",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Create → validate → publish → install → probe in one shot."""
        from core.capabilities.task_planner import TaskPlannerCapability

        identity_id = self._resolve_identity_id(identity_id, **kwargs)
        if not cap_id:
            return {"error": "cap_id is required (snake_case)", "goal_ok": False}
        if not cap_id.replace("_", "").isalnum() or not cap_id[0].isalpha():
            return {"error": f"Invalid cap_id '{cap_id}' — use snake_case identifier", "goal_ok": False}

        # Acquire-before-invent: if id already in registry, just install
        index = self._load_index()
        existing = next((c for c in index.get("capabilities", []) if c.get("id") == cap_id), None)
        if existing and not code:
            install_result = self._install_capability(cap_id=cap_id, identity_id=identity_id)
            install_result["acquired_existing"] = True
            install_result["note"] = "Capability already in registry — installed instead of recreating"
            return install_result

        name = name or cap_id.replace("_", " ").title()
        short = skill_short or skill_kind or kwargs.get("skill_name") or "echo"
        full_skill = f"{cap_id}.{short}"
        description = description or f"Auto-generated capability: {cap_id}"

        if not code:
            code = TaskPlannerCapability._capability_template(
                cap_id,
                skills=[{"name": short, "kind": skill_kind, "description": f"{skill_kind} skill"}],
                description=description,
            )

        cap_dir = os.path.abspath(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", cap_id)
        )
        cap_path = os.path.join(cap_dir, "__init__.py")
        os.makedirs(cap_dir, exist_ok=True)
        with open(cap_path, "w") as f:
            f.write(code)

        # Validate
        from core.capabilities.skill_validator import SkillValidatorCapability
        validator = SkillValidatorCapability()
        syntax = validator._validate_syntax(path=cap_path)
        if syntax.get("valid") is False or syntax.get("error"):
            return {
                "error": f"Syntax validation failed: {syntax}",
                "goal_ok": False,
                "path": cap_path,
                "step": "validate_syntax",
            }
        iface = validator._check_capability_interface(path=cap_path)
        if not iface.get("valid", False):
            return {
                "error": f"Interface check failed: {iface}",
                "goal_ok": False,
                "path": cap_path,
                "step": "check_interface",
            }

        try:
            import_capability(cap_id)
        except Exception as e:
            return {"error": f"Hot-import failed: {e}", "goal_ok": False, "step": "import"}

        pub = self._publish_capability(
            cap_id=cap_id,
            name=name,
            description=description,
            skills=[full_skill],
        )
        if not pub.get("goal_ok"):
            return {**pub, "step": "publish", "goal_ok": False}

        inst = self._install_capability(cap_id=cap_id, identity_id=identity_id)
        if not inst.get("goal_ok"):
            return {**inst, "step": "install", "goal_ok": False}

        # Probe
        reg = self._resolve_registry()
        probe: dict[str, Any] = {"skipped": True}
        if reg is not None and identity_id:
            try:
                result = reg.call(identity_id, full_skill, text=probe_text, message=probe_text)
                probe = {
                    "skill": full_skill,
                    "success": bool(getattr(result, "success", False)),
                    "data": getattr(result, "data", None),
                    "error": getattr(result, "error", None),
                }
            except Exception as e:
                probe = {"skill": full_skill, "success": False, "error": str(e)}

        goal_ok = bool(inst.get("goal_ok") and probe.get("success", False))
        return {
            "cap_id": cap_id,
            "path": cap_path,
            "published": pub,
            "installed": inst,
            "probe": probe,
            "status": "deployed" if goal_ok else "deploy_incomplete",
            "goal_ok": goal_ok,
            "error": None if goal_ok else "probe failed or install incomplete",
            "skills": [full_skill],
        }
