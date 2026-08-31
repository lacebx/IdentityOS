"""
verification.py — Evidence-producing verification.

Every completed step must be backed by real evidence.  ``verify_capability``
checks, in order:

  1. source file exists on disk
  2. module imports without error (fires @register)
  3. capability class is registered
  4. capability is installed for the identity
  5. the capability exposes at least one callable skill
  6. calling a skill with explicit verification parameters succeeds

If any check fails the corresponding Evidence is marked failed and the
caller (executor) decides whether to retry or mark the task failed.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any, Optional

from core.executive.models import Evidence

_CORE_CAPS_DIR = Path(__file__).resolve().parent.parent / "capabilities"


def capability_module_path(capability_id: str) -> Path:
    return _CORE_CAPS_DIR / capability_id / "__init__.py"


def verify_capability(
    capability_id: str,
    identity_id: str,
    capability_registry: Any,
    *,
    load: bool = True,
) -> list[Evidence]:
    """Verify a capability end-to-end, returning one Evidence per check."""
    checks: list[Evidence] = []
    cap_id = capability_id

    # 1. Source file exists
    path = capability_module_path(cap_id)
    checks.append(Evidence(
        step="verify",
        label="source_file_exists",
        detail=str(path) if path.exists() else f"missing: {path}",
        success=path.exists(),
        data={"path": str(path)},
    ))

    # 2. Module imports (fires @register)
    imported = None
    try:
        imported = importlib.import_module(f"core.capabilities.{cap_id}")
        checks.append(Evidence(
            step="verify", label="module_imports",
            detail=f"imported core.capabilities.{cap_id}",
            success=True, data={"module": f"core.capabilities.{cap_id}"},
        ))
    except Exception as e:
        checks.append(Evidence(
            step="verify", label="module_imports",
            detail=f"import failed: {type(e).__name__}: {e}",
            success=False, data={"error": str(e)},
        ))

    # 3. Registered
    try:
        from core.capabilities.registry import lookup
        lookup(cap_id)
        checks.append(Evidence(
            step="verify", label="registered",
            detail=f"{cap_id} registered", success=True,
            data={"registered": True},
        ))
    except Exception as e:
        checks.append(Evidence(
            step="verify", label="registered",
            detail=f"not registered: {e}", success=False,
            data={"error": str(e)},
        ))

    # 4. Installed for identity
    installed = False
    if capability_registry is not None:
        try:
            cap = capability_registry.get(identity_id, cap_id)
            installed = cap is not None
        except Exception:
            installed = False
    else:
        installed = imported is not None
    checks.append(Evidence(
        step="verify", label="installed",
        detail=f"installed for {identity_id}" if installed else "not installed",
        success=installed, data={"identity_id": identity_id, "installed": installed},
    ))

    # 5. Exposes a skill
    has_skill = False
    try:
        if capability_registry is not None:
            cap = capability_registry.get(identity_id, cap_id)
            if cap is not None:
                has_skill = len(cap.skills()) > 0
        elif imported is not None:
            has_skill = True
    except Exception:
        has_skill = False
    checks.append(Evidence(
        step="verify", label="skill_exposed",
        detail="capability exposes skills" if has_skill else "no skills exposed",
        success=has_skill, data={"has_skill": has_skill},
    ))

    # 6. Skill callable. Never guess arguments or invoke the first skill
    # blindly: mutating/generated skills must opt into a harmless probe.
    callable_ok = False
    callable_data: dict[str, Any] = {"callable": False, "executed": False}
    if capability_registry is not None and installed:
        try:
            cap = capability_registry.get(identity_id, cap_id)
            if cap is not None:
                skills = cap.skills()
                probe = next(
                    (skill for skill in skills if skill.verification_params is not None),
                    None,
                )
                if probe is not None:
                    params = dict(probe.verification_params or {})
                    res = cap.call(probe.name, **params)
                    callable_ok = bool(getattr(res, "success", False))
                    callable_data = {
                        "callable": callable_ok,
                        "executed": True,
                        "skill": probe.name,
                        "params": params,
                    }
                else:
                    callable_data["reason"] = (
                        "no skill declares safe verification parameters"
                    )
        except Exception as e:
            callable_ok = False
            checks.append(Evidence(
                step="verify", label="skill_callable",
                detail=f"call failed: {e}", success=False, data={"error": str(e)},
            ))
    if not any(e.label == "skill_callable" for e in checks):
        checks.append(Evidence(
            step="verify", label="skill_callable",
            detail="skill probe succeeded" if callable_ok else "skill probe unavailable or failed",
            success=callable_ok, data=callable_data,
        ))

    return checks


def all_succeeded(evidence: list[Evidence]) -> bool:
    return all(e.success for e in evidence)
