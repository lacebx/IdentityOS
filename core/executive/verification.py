"""
verification.py — Evidence-producing verification.

Every completed step must be backed by real evidence.  ``verify_capability``
checks, in order:

  1. source file exists on disk
  2. module imports without error (fires @register)
  3. capability class is registered
  4. capability is installed for the identity
  5. the capability exposes at least one callable skill
  6. calling a harmless skill returns a successful result

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

    # 6. Skill callable — AND produces behavioral evidence, not self-reports.
    #    A capability must not be blessed merely because its call() returns
    #    success=True.  A pure status self-report ({"status": "completed",
    #    "detail": "<cap> executed ..."}) proves no real behavior, so it must
    #    fail verification (R3 regression).
    callable_ok = False
    call_note = "skill not callable"
    call_data: dict[str, Any] = {"callable": False}
    if capability_registry is not None and installed:
        try:
            cap = capability_registry.get(identity_id, cap_id)
            if cap is not None:
                skills = cap.skills() or []
                behavioral = [s.name for s in skills if s.name and not _is_metadata_skill(s.name)]
                if not behavioral:
                    call_note = f"no behavioral skill exposed by {cap_id}"
                    call_data = {"callable": False, "metadata_only": True}
                else:
                    skill_name = behavioral[0]
                    ok, _ = cap.can(skill_name)
                    if not ok:
                        call_note = f"{skill_name} not callable"
                        call_data = {"callable": False, "skill": skill_name}
                    else:
                        res = cap.call(skill_name)
                        callable_ok = bool(getattr(res, "success", False))
                        call_note = f"{skill_name} callable"
                        call_data = {"callable": True, "skill": skill_name}
                        data = getattr(res, "data", None)
                        if callable_ok and isinstance(data, dict) and _is_pure_status_report(data):
                            callable_ok = False
                            call_note = (
                                f"no behavioral evidence: {skill_name} returned a status "
                                f"self-report ({sorted(data.keys())}), not real output"
                            )
                            call_data = {"callable": False, "skill": skill_name,
                                         "self_report": True, "keys": sorted(data.keys())}
                        elif callable_ok and not _has_behavioral_output(data):
                            callable_ok = False
                            call_note = (
                                f"no behavioral evidence: {skill_name} returned empty output"
                            )
                            call_data = {"callable": False, "skill": skill_name,
                                         "self_report": True, "empty": True}
        except Exception as e:
            callable_ok = False
            call_note = f"call failed: {e}"
            call_data = {"callable": False, "error": str(e)}
            checks.append(Evidence(
                step="verify", label="skill_callable",
                detail=call_note, success=False, data=call_data,
            ))
    if not any(e.label == "skill_callable" for e in checks):
        checks.append(Evidence(
            step="verify", label="skill_callable",
            detail=call_note, success=callable_ok, data=call_data,
        ))

    return checks


_METADATA_SKILL_MARKERS = (".info", ".metadata", ".get_info", ".describe")

_STATUS_SELF_REPORT_KEYS = frozenset({
    "capability", "task", "status", "detail", "progress", "message", "result",
})


def _is_metadata_skill(name: str) -> bool:
    return name.endswith(_METADATA_SKILL_MARKERS)


def _is_pure_status_report(data: dict) -> bool:
    """True when ``data`` is ONLY a status self-report (no observable output).

    A real capability returns actual artifacts/observations (stdout, files,
    fetched content, computed values).  A fabricated one returns a canned
    claim like ``{"status": "completed", "detail": "<cap> executed: ..."}``.
    """
    if not data:
        return False
    keys = set(data.keys())
    if not keys <= _STATUS_SELF_REPORT_KEYS:
        return False
    if data.get("status") == "completed":
        return True
    detail = data.get("detail", "")
    return isinstance(detail, str) and bool(detail.strip())


def _has_behavioral_output(data: Any) -> bool:
    """True when the skill produced at least one observable value."""
    if data is None:
        return False
    if isinstance(data, dict):
        if not data:
            return False
        if data.keys() <= _STATUS_SELF_REPORT_KEYS:
            return False
        return True
    if isinstance(data, (list, tuple)):
        return bool(data)
    if isinstance(data, str):
        return bool(data.strip())
    return True


def all_succeeded(evidence: list[Evidence]) -> bool:
    return all(e.success for e in evidence)
