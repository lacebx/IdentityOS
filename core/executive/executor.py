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

from core.executive.models import Evidence, ReplayPolicy, Task, TaskStep
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


def replay_policy_for_action(action: str) -> ReplayPolicy:
    """Return the declared crash-replay contract for an executor action.

    Unknown and externally mutating actions deliberately require manual
    reconciliation. Adding a new handler without declaring a policy therefore
    fails safe instead of silently duplicating a possible side effect.
    """

    return _REPLAY_POLICIES.get(action, ReplayPolicy.BLOCK)


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


def _verify_goal(task: Task, step: TaskStep, ctx: ExecutionContext) -> tuple[bool, dict, list]:
    request = step.params.get("request", "")
    cap = step.params.get("capability", "")
    if not request or ctx.runtime is None:
        return (True, {"retried": False}, [Evidence(step=step.action, label="goal_retry", detail="no original request to retry", success=True)])
    try:
        from runtime.orchestrator import InteractionRequest
        resp = ctx.runtime.process(InteractionRequest(
            identity_id=ctx.identity_id,
            user_input=request,
            session_id=None,
        ))
        output = getattr(resp, "output", "") or ""
        return (True, {"retried": True, "output": output[:500]}, [Evidence(step=step.action, label="goal_retry", detail="original request re-run", success=True, data={"output": output[:200]})])
    except Exception as e:
        return (True, {"retried": False, "error": str(e)}, [Evidence(step=step.action, label="goal_retry", detail=f"retry unavailable: {e}", success=False, data={"error": str(e)})])


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
            res = lookup("registry_manager")().call(skill, **step.params)
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


# These handlers are either observational or converge on the same persisted
# state when invoked repeatedly with the same parameters. Everything omitted
# from this set is treated as outcome-unknown after an interrupted attempt.
_REPLAY_POLICIES: dict[str, ReplayPolicy] = {
    "registry_search": ReplayPolicy.RETRY,
    "generate": ReplayPolicy.RETRY,
    "validate": ReplayPolicy.RETRY,
    "install": ReplayPolicy.RETRY,
    "verify": ReplayPolicy.RETRY,
    "create_directory": ReplayPolicy.RETRY,
    "write_file": ReplayPolicy.RETRY,
    "validate_syntax": ReplayPolicy.RETRY,
    "check_interface": ReplayPolicy.RETRY,
    "list_capabilities": ReplayPolicy.RETRY,
    "install_capability": ReplayPolicy.RETRY,
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
