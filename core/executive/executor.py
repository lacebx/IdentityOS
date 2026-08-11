"""
executor.py — Generic step executor.

Executes one ``TaskStep`` at a time, producing evidence for every step.
The executor knows step *action types* (registry_search, generate, validate,
publish, install, verify, verify_goal) — it never knows individual capability
names.  It also passes through planner-style file actions so plans produced
by the planner execute with the same persistence and evidence guarantees.

Every handler returns ``(success, result_dict, evidence_list)``.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from core.executive.models import Evidence, Task, TaskStep
from core.executive.templates import capability_module
from core.executive.verification import capability_module_path, verify_capability

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


@dataclass
class ExecutionContext:
    identity_id: str
    capability_registry: Any
    storage: Any
    runtime: Any = None


class StepError(Exception):
    """Raised when a step fails permanently (after retries exhausted)."""

    def __init__(self, message: str, evidence: Optional[list] = None):
        super().__init__(message)
        self.evidence = evidence or []


def execute_step(task: Task, step: TaskStep, ctx: ExecutionContext) -> tuple[bool, dict, list]:
    """Execute a single step.

    Returns ``(success, result, evidence)``. Raises ``StepError`` only when
    the step should be treated as a hard failure (not retried).
    """
    handler = _HANDLERS.get(step.action)
    if handler is None:
        return (False, {}, [Evidence(
            step=step.action, label="unknown_action",
            detail=f"No handler for action: {step.action}", success=False,
        )])
    return handler(task, step, ctx)


# ── Generic acquisition handlers ────────────────────────────────────────

def _registry_search(task: Task, step: TaskStep, ctx: ExecutionContext) -> tuple[bool, dict, list]:
    cap = step.params.get("capability", "")
    found, candidate = _search_marketplace(cap)
    evidence = [Evidence(
        step=step.action, label="registry_search",
        detail=f"found={found} candidate={candidate or 'none'}", success=True,
        data={"capability": cap, "found": found, "candidate": candidate},
    )]
    return (True, {"found": found, "candidate": candidate}, evidence)


def _generate(task: Task, step: TaskStep, ctx: ExecutionContext) -> tuple[bool, dict, list]:
    cap = step.params.get("capability", "")
    path = capability_module_path(cap)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(capability_module(cap), encoding="utf-8")
        evidence = [Evidence(
            step=step.action, label="file_generated",
            detail=f"wrote {path} ({path.stat().st_size} bytes)", success=True,
            data={"path": str(path), "bytes": path.stat().st_size},
        )]
        return (True, {"path": str(path)}, evidence)
    except Exception as e:
        return (False, {}, [Evidence(
            step=step.action, label="file_generated",
            detail=f"failed to generate: {e}", success=False, data={"error": str(e)},
        )])


def _validate(task: Task, step: TaskStep, ctx: ExecutionContext) -> tuple[bool, dict, list]:
    cap = step.params.get("capability", "")
    path = capability_module_path(cap)
    evidence: list = []
    ok = True
    try:
        import ast
        ast.parse(path.read_text(encoding="utf-8"))
        evidence.append(Evidence(step=step.action, label="syntax_valid", detail=str(path), success=True))
    except Exception as e:
        ok = False
        evidence.append(Evidence(step=step.action, label="syntax_valid", detail=f"invalid syntax: {e}", success=False, data={"error": str(e)}))
    try:
        from core.capabilities.registry import lookup
        import importlib
        importlib.import_module(f"core.capabilities.{cap}")
        lookup(cap)
        evidence.append(Evidence(step=step.action, label="interface_valid", detail=f"{cap} imports and registers", success=True))
    except Exception as e:
        ok = False
        evidence.append(Evidence(step=step.action, label="interface_valid", detail=f"import/register failed: {e}", success=False, data={"error": str(e)}))
    return (ok, {"valid": ok}, evidence)


def _publish(task: Task, step: TaskStep, ctx: ExecutionContext) -> tuple[bool, dict, list]:
    cap = step.params.get("capability", "")
    try:
        from core.capabilities.registry import lookup
        rmgmt = lookup("registry_manager")()
        res = rmgmt.call(
            "registry_manager.publish_capability",
            cap_id=cap,
            name=cap.replace("_", " ").title(),
            version="1.0.0",
            description=f"Generic capability: {cap}",
        )
        success = bool(getattr(res, "success", False)) or "published" in str(getattr(res, "data", {}))
        evidence = [Evidence(
            step=step.action, label="registry_published",
            detail=f"{cap} published ({getattr(res, 'data', {})})", success=success,
            data=getattr(res, "data", {}) if isinstance(getattr(res, "data", {}), dict) else {"result": str(getattr(res, "data", ""))},
        )]
        return (success, {"published": success}, evidence)
    except Exception as e:
        return (False, {}, [Evidence(step=step.action, label="registry_published", detail=f"publish failed: {e}", success=False, data={"error": str(e)})])


def _resolve_capability(task: Task, step: TaskStep) -> str:
    """Resolve the canonical capability id for a step.

    Prefers the marketplace-resolved candidate from the registry_search step
    so steps after search install/verify the *canonical* id even when the
    goal named the capability loosely (e.g. 'command' -> 'command_exec').
    """
    cap = step.params.get("capability", "")
    ref = task.step_by_id("registry_search")
    if ref is not None and ref.result.get("candidate"):
        return ref.result["candidate"]
    return cap


def _install(task: Task, step: TaskStep, ctx: ExecutionContext) -> tuple[bool, dict, list]:
    cap = _resolve_capability(task, step)
    try:
        import importlib
        from core.capabilities.registry import lookup
        importlib.import_module(f"core.capabilities.{cap}")  # fires @register
        lookup(cap)  # must be registered before install
        if ctx.capability_registry is None:
            return (False, {}, [Evidence(step=step.action, label="installed", detail="no capability registry available", success=False)])
        cap_obj = ctx.capability_registry.install(ctx.identity_id, cap)
        evidence = [Evidence(
            step=step.action, label="installed",
            detail=f"{cap} installed for {ctx.identity_id}", success=True,
            data={"capability": cap, "identity_id": ctx.identity_id, "skills": [s.name for s in cap_obj.skills()]},
        )]
        return (True, {"installed": cap, "skills": [s.name for s in cap_obj.skills()]}, evidence)
    except Exception as e:
        return (False, {}, [Evidence(step=step.action, label="installed", detail=f"install failed: {e}", success=False, data={"error": str(e)})])


def _verify(task: Task, step: TaskStep, ctx: ExecutionContext) -> tuple[bool, dict, list]:
    cap = _resolve_capability(task, step)
    evidence = verify_capability(cap, ctx.identity_id, ctx.capability_registry)
    ok = all(e.success for e in evidence)
    return (ok, {"verified": ok, "checks": len(evidence)}, evidence)


_VERIFY_GOAL_MAX_REENTRANT = 2


def _verify_goal(task: Task, step: TaskStep, ctx: ExecutionContext) -> tuple[bool, dict, list]:
    """Goal-level verification that NEVER recurses into the runtime.

    The old implementation re-entered ``ctx.runtime.process()`` with the
    original request (R6), which re-triggered Prometheus keyword detection,
    re-committed terminal goals and recursed until ``RecursionError``.

    New contract: the runtime owns verification.  This step only inspects
    persisted task + capability state:
      * if a real ``verify`` step already verified the capability with
        behavioral evidence → CONFIRMED
      * if the capability is installed but unverifiable → NOT CONFIRMED (fail)
      * if an original request exists and the pipeline never completed, we
        re-invoke it at MOST a bounded number of times through the SAME
        executive engine (never a fresh ``process()`` pipeline) and only when
        no terminal task exists for the same request.
    """
    request = step.params.get("request", "")
    cap = step.params.get("capability", "")

    # 1) If capability was verified by a real `verify` step → confirmed.
    verify_ref = task.step_by_id("verify")
    if verify_ref is not None and verify_ref.result:
        if verify_ref.result.get("verified") and all(
            e.success for e in verify_ref.evidence if e.label != "verify"
        ):
            return (True, {"confirmed": True, "requery": False}, [
                Evidence(step=step.action, label="goal_confirmed",
                         detail=f"{cap} verified by prior verify step",
                         success=True, data={"capability": cap, "confirmed": True}),
            ])

    # 2) Capability installed but not behaviorally verified → honest failure.
    if ctx.capability_registry is not None and cap:
        try:
            inst = ctx.capability_registry.get(ctx.identity_id, cap)
            installed = inst is not None
        except Exception:
            installed = False
        if installed and not (verify_ref and verify_ref.result.get("verified")):
            return (False, {"confirmed": False, "requery": False, "reason": "installed-but-unverified"}, [
                Evidence(step=step.action, label="goal_confirmed",
                         detail=f"{cap} is installed but its skills did not pass behavioral verification",
                         success=False, data={"capability": cap, "confirmed": False}),
            ])

    # 3) Bounded, non-recursive re-evaluation of the original request when
    #    the pipeline never produced a terminal task for it.
    if not request or ctx.runtime is None:
        return (True, {"confirmed": False, "requery": False, "reason": "nothing-to-verify"}, [
            Evidence(step=step.action, label="goal_confirmed",
                     detail="no original request to re-evaluate", success=True),
        ])

    reentrant_count = int(step.params.get("_requery_count", 0))
    if reentrant_count >= _VERIFY_GOAL_MAX_REENTRANT:
        return (False, {"confirmed": False, "requery": False, "reason": "requery-budget-exhausted"}, [
            Evidence(step=step.action, label="goal_confirmed",
                     detail=f"goal not confirmed after {reentrant_count} requeries",
                     success=False),
        ])

    # Inspect the executive store for an EXISTING task covering this request.
    # If a terminal task already exists for the same goal/capability, do NOT
    # spawn a new one — report that state instead.
    try:
        from core.executive.workflow import extract_capability_name
        _eng = None
        _rt = getattr(ctx, "runtime", None)
        if _rt is not None:
            _eng = getattr(_rt, "executive", None) or _rt
        if _eng is None:
            raise RuntimeError("no executive engine reachable from context")
        _existing_active = _eng.active_tasks(ctx.identity_id)
        _existing_terminal = _eng.history(ctx.identity_id)
    except Exception as e:
        return (False, {"confirmed": False, "requery": False, "error": str(e)}, [
            Evidence(step=step.action, label="goal_confirmed",
                     detail=f"cannot inspect task state: {e}", success=False,
                     data={"error": str(e)}),
        ])

    _all = list(_existing_active)
    for _t in _existing_terminal:
        if isinstance(_t, dict):
            try:
                _tobj = _eng.get_task(ctx.identity_id, _t.get("task_id", ""))
                if _tobj is not None:
                    _all.append(_tobj)
            except Exception:
                continue
    _same_goal = [
        t for t in _all if t is not None
        and ((cap and getattr(t, "capability_id", "") == cap) or (request and request in (getattr(t, "goal", "") or "")))
    ]
    if _same_goal:
        terminal = _same_goal[0]
        state = getattr(terminal, "status", None)
        return (True, {"confirmed": bool(state and str(state.value) == "completed"),
                       "requery": False, "existing_task": getattr(terminal, "task_id", None)}, [
            Evidence(step=step.action, label="goal_confirmed",
                     detail=("goal already completed" if (state and str(state.value) == "completed")
                             else f"goal already in state {state}"),
                     success=bool(state and str(state.value) == "completed"),
                     data={"existing_task": getattr(terminal, "task_id", None)}),
        ])

    # No existing task for this request → bounded single requery through the
    # executive engine (start_task) if this is a legitimate acquisition goal.
    # This reuses the SAME engine; it never re-enters the orchestrator's
    # process() pipeline (so no Prometheus re-detection, no recursion).
    if not request or not cap:
        return (True, {"confirmed": False, "requery": False}, [
            Evidence(step=step.action, label="goal_confirmed",
                     detail="cannot re-evaluate without capability+request", success=True),
        ])
    if reentrant_count >= 1:
        return (False, {"confirmed": False, "requery": False, "reason": "loop-bounded"}, [
            Evidence(step=step.action, label="goal_confirmed",
                     detail=f"goal not confirmed after requery attempt {reentrant_count}",
                     success=False),
        ])
    try:
        from core.executive.workflow import is_acquisition_goal
        if not is_acquisition_goal(request):
            return (True, {"confirmed": False, "requery": False, "reason": "not-an-acquisition-goal"}, [
                Evidence(step=step.action, label="goal_confirmed",
                         detail="request is not a capability-acquisition goal; nothing to re-evaluate",
                         success=True),
            ])
        step.params["_requery_count"] = reentrant_count + 1
        _eng.create_acquisition_task(
            identity_id=ctx.identity_id,
            capability_id=cap,
            goal=request,
            original_request=request,
            runtime=_rt,
        )
        if getattr(_eng, "scheduler", None):
            _eng.scheduler.start()
        return (True, {"confirmed": False, "requery": True, "attempt": reentrant_count + 1}, [
            Evidence(step=step.action, label="goal_confirmed",
                     detail=f"re-queued acquisition task for {cap} (attempt {reentrant_count + 1})",
                     success=True, data={"capability": cap}),
        ])
    except Exception as e:
        return (True, {"confirmed": False, "requery": False, "error": str(e)}, [
            Evidence(step=step.action, label="goal_confirmed",
                     detail=f"requery unavailable: {e}", success=False,
                     data={"error": str(e)}),
        ])


# ── Planner file-action passthrough handlers ─────────────────────────────

def _passthrough_file_tools(action: str):
    def handler(task: Task, step: TaskStep, ctx: ExecutionContext) -> tuple[bool, dict, list]:
        try:
            from core.capabilities.registry import lookup
            res = lookup("file_tools")().call(f"file_tools.{action}", **step.params)
            ok = bool(getattr(res, "success", False))
            data = getattr(res, "data", {})
            ev = [Evidence(step=step.action, label=action, detail=f"{action} ok" if ok else f"{action} failed", success=ok, data=data if isinstance(data, dict) else {})]
            return (ok, data if isinstance(data, dict) else {"result": str(data)}, ev)
        except Exception as e:
            return (False, {}, [Evidence(step=step.action, label=action, detail=f"{action} failed: {e}", success=False, data={"error": str(e)})])
    return handler


def _passthrough_validator(action: str):
    def handler(task: Task, step: TaskStep, ctx: ExecutionContext) -> tuple[bool, dict, list]:
        try:
            from core.capabilities.registry import lookup
            skill = "skill_validator.validate_syntax" if action == "validate_syntax" else "skill_validator.check_capability_interface"
            res = lookup("skill_validator")().call(skill, **step.params)
            ok = bool(getattr(res, "success", False))
            data = getattr(res, "data", {})
            ev = [Evidence(step=step.action, label=action, detail="validated" if ok else "validation failed", success=ok, data=data if isinstance(data, dict) else {})]
            return (ok, data if isinstance(data, dict) else {"result": str(data)}, ev)
        except Exception as e:
            return (False, {}, [Evidence(step=step.action, label=action, detail=f"{action} failed: {e}", success=False, data={"error": str(e)})])
    return handler


def _passthrough_registry(action: str):
    def handler(task: Task, step: TaskStep, ctx: ExecutionContext) -> tuple[bool, dict, list]:
        try:
            from core.capabilities.registry import lookup
            skill = {
                "list_capabilities": "registry_manager.list_capabilities",
                "publish_capability": "registry_manager.publish_capability",
                "install_capability": "registry_manager.install_capability",
            }[action]
            params = dict(step.params)
            params.setdefault("identity_id", ctx.identity_id)
            params.setdefault("registry", ctx.capability_registry)
            res = lookup("registry_manager")().call(skill, **params)
            ok = bool(getattr(res, "success", False))
            data = getattr(res, "data", {})
            ev = [Evidence(step=step.action, label=action, detail=f"{action} ok" if ok else f"{action} failed", success=ok, data=data if isinstance(data, dict) else {})]
            return (ok, data if isinstance(data, dict) else {"result": str(data)}, ev)
        except Exception as e:
            return (False, {}, [Evidence(step=step.action, label=action, detail=f"{action} failed: {e}", success=False, data={"error": str(e)})])
    return handler


def _passthrough_command(task: Task, step: TaskStep, ctx: ExecutionContext) -> tuple[bool, dict, list]:
    try:
        from core.capabilities.registry import lookup
        import importlib
        cap = step.params.get("cap_id", "command_exec")
        cmd = step.params.get("command", "")
        importlib.import_module(f"core.capabilities.{cap}")
        res = lookup(cap)().call(f"{cap}.run", command=cmd)
        ok = bool(getattr(res, "success", False))
        data = getattr(res, "data", {})
        ev = [Evidence(step=step.action, label="command_run", detail=f"exit={data.get('exit_code')}" if isinstance(data, dict) else "ran", success=ok, data=data if isinstance(data, dict) else {})]
        return (ok, data if isinstance(data, dict) else {"result": str(data)}, ev)
    except Exception as e:
        return (False, {}, [Evidence(step=step.action, label="command_run", detail=f"command failed: {e}", success=False, data={"error": str(e)})])


_HANDLERS: dict[str, Any] = {
    "registry_search": _registry_search,
    "generate": _generate,
    "validate": _validate,
    "publish": _publish,
    "install": _install,
    "verify": _verify,
    "verify_goal": _verify_goal,
    # planner passthrough
    "create_directory": _passthrough_file_tools("create_directory"),
    "write_file": _passthrough_file_tools("write_file"),
    "append_file": _passthrough_file_tools("append_file"),
    "validate_syntax": _passthrough_validator("validate_syntax"),
    "check_interface": _passthrough_validator("check_interface"),
    "list_capabilities": _passthrough_registry("list_capabilities"),
    "publish_capability": _passthrough_registry("publish_capability"),
    "install_capability": _passthrough_registry("install_capability"),
    "run_command": _passthrough_command,
}


def _load_manifest_skills(cap_id: str) -> list:
    manifest_path = _REPO_ROOT / "registry" / "capabilities" / cap_id / "manifest.json"
    try:
        with open(manifest_path) as f:
            manifest = json.load(f)
        return manifest.get("skills", [])
    except Exception:
        return []


def _search_marketplace(capability: str) -> tuple[bool, Optional[str]]:
    """Search the marketplace index for a capability by id/name/skills."""
    idx_path = _REPO_ROOT / "registry" / "capabilities" / "index.json"
    try:
        with open(idx_path) as f:
            data = json.load(f)
    except Exception:
        return (False, None)
    entries = data if isinstance(data, list) else data.get("capabilities", [])
    needle = (capability or "").lower()
    for e in entries:
        eid = str(e.get("id", "")).lower()
        name = str(e.get("name", "")).lower()
        skills = e.get("skills", [])
        if isinstance(skills, int):
            skills = []
        if not skills:
            skills = _load_manifest_skills(e.get("id", ""))
        skills = [str(s.get("name", "")).lower() for s in skills if isinstance(s, dict)]
        if needle in eid or needle == name or needle in skills or needle in [s.split(".")[0] for s in skills]:
            return (True, e.get("id", capability))
        if needle == eid.split(".")[-1]:
            return (True, e.get("id", capability))
    return (False, None)
