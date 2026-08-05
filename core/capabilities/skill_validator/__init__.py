from __future__ import annotations

import ast
import os
import subprocess
import sys
import tempfile
from typing import Any, Optional

from core.capabilities.base import Capability, Skill
from core.capabilities.registry import register
from core.capabilities.result import CapabilityResult


@register
class SkillValidatorCapability(Capability):
    id = "skill_validator"
    name = "Skill Validator"
    version = "1.0.0"
    author = "IdentityOS"
    license = "MIT"
    homepage = "https://github.com/lacebx/IdentityOS"
    description = "Validate Python skill code for syntax errors, test imports, and verify Capability interface compliance"
    permissions = ["public"]

    def __init__(self, config: Optional[dict] = None) -> None:
        super().__init__(config)

    def install(self, identity_id: str, storage: Any) -> None:
        storage.save(identity_id, "capability.skill_validator", {"installed_at": None})

    def uninstall(self, identity_id: str, storage: Any) -> None:
        storage.delete(identity_id, "capability.skill_validator")

    def prompts(self, identity_id: str) -> list[str]:
        return [
            "## Skill Validator Skills (MANDATORY — use before publishing or installing any new capability)",
            "When you create a new capability or modify an existing one, you MUST validate it using the skills below.",
            "Always validate syntax before publishing to catch errors early.",
            "Use validate_syntax to check Python syntax. Use check_capability_interface to verify it follows the Capability pattern.",
        ]

    _SKILLS = [
        Skill(name="skill_validator.validate_syntax", description="Validate Python syntax of a skill file", permission="public"),
        Skill(name="skill_validator.check_capability_interface", description="Check that a capability file follows the required Capability interface", permission="public"),
    ]

    def skills(self) -> list[Skill]:
        return list(self._SKILLS)

    def call(self, skill_name: str, **params: Any) -> CapabilityResult:
        import time as _time
        _t0 = _time.monotonic()
        try:
            dispatch = {
                "skill_validator.validate_syntax": self._validate_syntax,
                "skill_validator.check_capability_interface": self._check_capability_interface,
            }
            handler = dispatch.get(skill_name)
            if handler is None:
                return CapabilityResult.fail("skill_validator", skill_name, "unknown_skill", f"Unknown skill: {skill_name}")
            data = handler(**params)
            if isinstance(data, dict) and (data.get("error") or data.get("valid") is False):
                data = {**data, "goal_ok": False}
                if not data.get("error"):
                    data["error"] = data.get("message") or "validation failed"
            else:
                if isinstance(data, dict):
                    data = {**data, "goal_ok": True}
            return CapabilityResult.ok("skill_validator", skill_name, data, source="code analysis", duration_ms=(_time.monotonic() - _t0) * 1000)
        except Exception as e:
            return CapabilityResult.fail("skill_validator", skill_name, type(e).__name__, str(e), duration_ms=(_time.monotonic() - _t0) * 1000)

    def _validate_syntax(self, path: str = "", code: str = "", **kwargs: Any) -> dict[str, Any]:
        if path:
            if not os.path.isfile(path):
                return {"error": f"File not found: {path}"}
            with open(path) as f:
                code = f.read()
        if not code:
            return {"error": "No code provided. Provide either a path or code string."}
        try:
            ast.parse(code)
            return {
                "valid": True,
                "message": "Python syntax is valid",
                "line_count": len(code.splitlines()),
            }
        except SyntaxError as e:
            return {
                "valid": False,
                "message": f"Syntax error at line {e.lineno}: {e.msg}",
                "line": e.lineno,
                "error": e.msg,
            }

    def _check_capability_interface(self, path: str = "", code: str = "", **kwargs: Any) -> dict[str, Any]:
        if path:
            if not os.path.isfile(path):
                return {"error": f"File not found: {path}"}
            with open(path) as f:
                code = f.read()
        if not code:
            return {"error": "No code provided."}
        checks = []
        issues = []
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return {"valid": False, "issues": [f"Syntax error: {e}"]}
        classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
        cap_classes = [c for c in classes if any(
            b.id == "Capability" for b in c.bases if isinstance(b, ast.Name)
        )]
        if not cap_classes:
            issues.append("No class found that inherits from Capability")
        else:
            for cls in cap_classes:
                methods = [n.name for n in cls.body if isinstance(n, ast.FunctionDef)]
                checks.append(f"Class '{cls.name}' inherits Capability")
                for required in ["install", "uninstall", "prompts", "skills", "call"]:
                    if required in methods:
                        checks.append(f"  implements {required}()")
                    else:
                        issues.append(f"  MISSING {required}()")
                has_id = any(
                    isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "id" for t in n.targets)
                    for n in cls.body
                )
                if has_id:
                    checks.append("  has id attribute")
                else:
                    issues.append("  MISSING id attribute")
                has_skills_list = any(
                    any(isinstance(t, ast.Name) and t.id == "_SKILLS" for t in n.targets)
                    for n in cls.body if isinstance(n, ast.Assign)
                )
                has_skills_method = "skills" in methods
                if has_skills_list:
                    checks.append("  has _SKILLS list")
                elif has_skills_method:
                    checks.append("  has skills() method")
                else:
                    issues.append("  MISSING _SKILLS or skills()")
        return {
            "valid": len(issues) == 0,
            "checks": checks,
            "issues": issues,
            "class_count": len(cap_classes),
        }
