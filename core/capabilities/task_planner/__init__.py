from __future__ import annotations

import re
from typing import Any, Optional

from core.capabilities.base import Capability, Skill
from core.capabilities.registry import register, lookup, import_capability
from core.capabilities.result import CapabilityResult


_STEP_HANDLERS = {
    # File operations
    "write_file": lambda p: lookup("file_tools")().call("file_tools.write_file", **p),
    "create_directory": lambda p: lookup("file_tools")().call("file_tools.create_directory", **p),
    "append_file": lambda p: lookup("file_tools")().call("file_tools.append_file", **p),
    # Validation
    "validate_syntax": lambda p: lookup("skill_validator")().call("skill_validator.validate_syntax", **p),
    "check_interface": lambda p: lookup("skill_validator")().call("skill_validator.check_capability_interface", **p),
    # Registry
    "list_capabilities": lambda p: lookup("registry_manager")().call("registry_manager.list_capabilities", **p),
    "publish_capability": lambda p: lookup("registry_manager")().call("registry_manager.publish_capability", **p),
    "install_capability": lambda p: lookup("registry_manager")().call("registry_manager.install_capability", **p),
    "create_and_deploy": lambda p: lookup("registry_manager")().call("registry_manager.create_and_deploy", **p),
    "inventory": lambda p: lookup("registry_manager")().call("registry_manager.inventory", **p),
    "import_capability": lambda p: _import_step(p),
    "probe_skill": lambda p: _probe_step(p),
}


def _import_step(params: dict) -> CapabilityResult:
    cap_id = params.get("cap_id", "")
    try:
        cls = import_capability(cap_id)
        return CapabilityResult.ok(
            "task_planner",
            "import_capability",
            {"cap_id": cap_id, "class": cls.__name__, "goal_ok": True},
            source="hot-import",
        )
    except Exception as e:
        return CapabilityResult.fail("task_planner", "import_capability", type(e).__name__, str(e))


def _probe_step(params: dict) -> CapabilityResult:
    reg = params.get("_capability_registry")
    identity_id = params.get("identity_id", "")
    skill = params.get("skill", "")
    probe_params = {k: v for k, v in params.items() if k not in ("_capability_registry", "identity_id", "skill", "action")}
    if reg is None or not identity_id or not skill:
        return CapabilityResult.fail(
            "task_planner",
            "probe_skill",
            "missing_context",
            "probe requires identity_id, skill, and bound registry",
        )
    try:
        result = reg.call(identity_id, skill, **probe_params)
        if isinstance(result, CapabilityResult):
            data = {
                "skill": skill,
                "probe_success": result.success,
                "data": result.data,
                "goal_ok": result.success,
                "error": None if result.success else (result.error or "probe failed"),
            }
            return CapabilityResult.ok("task_planner", "probe_skill", data, source="probe")
        return CapabilityResult.ok(
            "task_planner",
            "probe_skill",
            {"skill": skill, "data": result, "goal_ok": True},
            source="probe",
        )
    except Exception as e:
        return CapabilityResult.fail("task_planner", "probe_skill", type(e).__name__, str(e))


# Words that must never become capability ids (regex NL debris)
_BLOCKED_CAP_NAMES = frozenset({
    "a", "an", "the", "this", "that", "these", "those", "and", "or", "but", "if",
    "to", "for", "with", "from", "into", "onto", "your", "my", "our", "me", "you",
    "it", "its", "is", "are", "be", "do", "did", "does", "can", "could", "would",
    "should", "will", "just", "please", "create", "build", "make", "write", "publish",
    "install", "validate", "check", "test", "list", "show", "add", "load", "register",
    "update", "delete", "remove", "capability", "capabilities", "skill", "skills",
    "new", "called", "named", "then", "also", "using", "have", "has", "all", "required",
    "wonderful", "since", "about", "what", "when", "where", "how", "why", "yes", "no",
    "ok", "okay", "anyway", "hmmm", "interesting", "gotcha", "hey", "hi", "hello",
    "internet", "explorer", "browser",  # handled via acquire-before-invent → web
})

# Goals that should install an existing cap instead of inventing a new one
_ACQUIRE_MAP = [
    (("browse", "internet", "web page", "fetch", "scrape", "look up", "search the web", "website"), "web"),
    (("weather", "forecast", "temperature"), "weather"),
    (("current time", "what time", "timezone", "date math"), "datetime"),
    (("github", "pull request", "repository"), "github"),
    (("calculate", "math expression", "unit convert"), "calc"),
]


@register
class TaskPlannerCapability(Capability):
    id = "task_planner"
    name = "Task Planner"
    version = "1.1.0"
    author = "IdentityOS"
    license = "MIT"
    homepage = "https://github.com/lacebx/IdentityOS"
    description = "Plan and execute multi-step tasks with progress tracking and reporting"
    permissions = ["public"]

    def __init__(self, config: Optional[dict] = None) -> None:
        super().__init__(config)

    def install(self, identity_id: str, storage: Any) -> None:
        storage.save(identity_id, "capability.task_planner", {"installed_at": None})

    def uninstall(self, identity_id: str, storage: Any) -> None:
        storage.delete(identity_id, "capability.task_planner")

    def prompts(self, identity_id: str) -> list[str]:
        return [
            "## Task Planner Skills (MANDATORY — use for multi-step autonomous tasks)",
            "When asked to create, build, publish, or install anything that requires multiple steps:",
            "  1. Call task_planner.plan_and_execute with your goal as the 'goal' parameter",
            "  2. Prefer acquire-before-invent: if a registry capability already covers the need (e.g. web), install it — do NOT invent duplicates",
            "  3. For novel skills, pass structured fields when possible: cap_id (snake_case), skill_kind (reverse|echo|upper|greet), identity_id",
            "  4. Report success ONLY if the result has goal_ok=true — never claim install/create succeeded otherwise",
            "Example: task_planner.plan_and_execute(goal='create capability string_reverse that reverses text, publish and install it', cap_id='string_reverse', skill_kind='reverse')",
        ]

    _SKILLS = [
        Skill(
            name="task_planner.plan_and_execute",
            description="Plan and execute a multi-step task. Provide goal text and optional structured cap_id/skill_kind. Returns progress and goal_ok.",
            permission="public",
        ),
    ]

    def skills(self) -> list[Skill]:
        return list(self._SKILLS)

    def call(self, skill_name: str, **params: Any) -> CapabilityResult:
        import time as _time
        _t0 = _time.monotonic()
        try:
            dispatch = {
                "task_planner.plan_and_execute": self._plan_and_execute,
            }
            handler = dispatch.get(skill_name)
            if handler is None:
                return CapabilityResult.fail("task_planner", skill_name, "unknown_skill", f"Unknown skill: {skill_name}")
            # Bind runtime context into params for install/probe
            if not params.get("identity_id"):
                params["identity_id"] = getattr(self, "_identity_id", "")
            if "_capability_registry" not in params:
                params["_capability_registry"] = getattr(self, "_capability_registry", None)
            data = handler(**params)
            return CapabilityResult.ok(
                "task_planner",
                skill_name,
                data,
                source="task planner",
                duration_ms=(_time.monotonic() - _t0) * 1000,
            )
        except Exception as e:
            return CapabilityResult.fail(
                "task_planner",
                skill_name,
                type(e).__name__,
                str(e),
                duration_ms=(_time.monotonic() - _t0) * 1000,
            )

    def _plan_and_execute(
        self,
        goal: str = "",
        steps: Optional[list] = None,
        cap_id: str = "",
        skill_kind: str = "",
        identity_id: str = "",
        _capability_registry: Any = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        if not goal and not steps and not cap_id:
            return {"error": "Provide a 'goal' string or structured cap_id.", "goal_ok": False}

        identity_id = identity_id or getattr(self, "_identity_id", "") or ""
        registry = _capability_registry or getattr(self, "_capability_registry", None)

        plan = steps or self._generate_plan(
            goal,
            cap_id=cap_id,
            skill_kind=skill_kind,
            identity_id=identity_id,
            registry=registry,
        )
        total = len(plan)
        step_results = []
        postconditions: list[dict[str, Any]] = []

        for i, step in enumerate(plan, 1):
            action = step.get("action", "")
            params = dict(step.get("params", {}))
            description = step.get("description", action)

            # Always forward identity + registry into install/deploy/probe
            if identity_id and "identity_id" not in params:
                params["identity_id"] = identity_id
            if registry is not None:
                params["_capability_registry"] = registry
            # For registry_manager steps, use the *bound* instance when possible
            if action in ("install_capability", "publish_capability", "create_and_deploy", "inventory", "list_capabilities"):
                if registry is not None and identity_id:
                    bound = registry.get(identity_id, "registry_manager")
                    if bound is not None:
                        skill_map = {
                            "install_capability": "registry_manager.install_capability",
                            "publish_capability": "registry_manager.publish_capability",
                            "create_and_deploy": "registry_manager.create_and_deploy",
                            "inventory": "registry_manager.inventory",
                            "list_capabilities": "registry_manager.list_capabilities",
                        }
                        progress_line = f"[{i}/{total}] {description}"
                        try:
                            result = bound.call(skill_map[action], **{k: v for k, v in params.items() if not k.startswith("_")})
                            ok = bool(result.success and (result.goal_ok is not False))
                            step_results.append({
                                "step": i,
                                "action": action,
                                "progress": progress_line,
                                "success": ok,
                                "data": result.data,
                                "duration_ms": result.duration_ms,
                                "goal_ok": result.goal_ok,
                            })
                            postconditions.append({"step": i, "action": action, "ok": ok})
                            if not ok and step.get("critical", True):
                                break
                        except Exception as e:
                            step_results.append({
                                "step": i,
                                "action": action,
                                "progress": progress_line,
                                "success": False,
                                "error": str(e),
                                "goal_ok": False,
                            })
                            break
                        continue

            progress_line = f"[{i}/{total}] {description}"
            handler = _STEP_HANDLERS.get(action)

            if handler is None:
                step_results.append({
                    "step": i,
                    "action": action,
                    "progress": progress_line,
                    "success": False,
                    "error": f"No handler for action: {action}",
                    "goal_ok": False,
                })
                continue

            try:
                result = handler(params)
                data = result.data if isinstance(result, CapabilityResult) else result
                ok = bool(getattr(result, "success", False))
                if isinstance(data, dict) and data.get("goal_ok") is False:
                    ok = False
                if isinstance(data, dict) and data.get("error"):
                    ok = False
                if isinstance(data, dict) and data.get("valid") is False:
                    ok = False
                step_results.append({
                    "step": i,
                    "action": action,
                    "progress": progress_line,
                    "success": ok,
                    "data": data,
                    "duration_ms": getattr(result, "duration_ms", 0),
                    "goal_ok": ok,
                })
                postconditions.append({"step": i, "action": action, "ok": ok})
                if not ok and step.get("critical", True):
                    break
            except Exception as e:
                step_results.append({
                    "step": i,
                    "action": action,
                    "progress": progress_line,
                    "success": False,
                    "error": str(e),
                    "goal_ok": False,
                })
                break

        total_success = sum(1 for r in step_results if r.get("success"))
        goal_ok = bool(step_results) and all(r.get("success") for r in step_results)
        return {
            "plan": [{k: v for k, v in s.items() if k != "params" or True} for s in plan],
            "total_steps": total,
            "completed": total_success,
            "failed": len(step_results) - total_success,
            "all_succeeded": goal_ok,
            "goal_ok": goal_ok,
            "postconditions": postconditions,
            "results": step_results,
            "error": None if goal_ok else "one or more steps failed postconditions",
        }

    @classmethod
    def _generate_plan(
        cls,
        goal: str,
        cap_id: str = "",
        skill_kind: str = "",
        identity_id: str = "",
        registry: Any = None,
    ) -> list[dict]:
        gl = (goal or "").lower()

        # ── Acquire-before-invent ────────────────────────────────────
        for keywords, existing_id in _ACQUIRE_MAP:
            if any(k in gl for k in keywords) and any(
                w in gl for w in ("create", "build", "make", "invent", "new capability", "internet_explorer", "browser")
            ):
                return [
                    {
                        "action": "list_capabilities",
                        "params": {},
                        "description": f"Checking registry for existing '{existing_id}'",
                        "critical": False,
                    },
                    {
                        "action": "install_capability",
                        "params": {"cap_id": existing_id, "identity_id": identity_id},
                        "description": f"Installing existing capability '{existing_id}' (acquire-before-invent)",
                        "critical": True,
                    },
                ]
            # Also: if goal is just to fetch/browse without create, install if needed
            if any(k in gl for k in keywords) and "create" not in gl and "build" not in gl:
                installed = []
                if registry is not None and identity_id:
                    installed = [c.id for c in registry.list(identity_id)]
                if existing_id not in installed:
                    return [
                        {
                            "action": "install_capability",
                            "params": {"cap_id": existing_id, "identity_id": identity_id},
                            "description": f"Installing '{existing_id}' to fulfill the request",
                            "critical": True,
                        }
                    ]

        # ── Structured / safe cap_id extraction ──────────────────────
        resolved_id = cap_id or cls._extract_cap_id(gl)
        kind = skill_kind or cls._infer_skill_kind(gl, resolved_id)

        if resolved_id:
            # Prefer one-shot create_and_deploy when creating
            if any(w in gl for w in ("create", "build", "make", "write", "scaffold")):
                return [
                    {
                        "action": "create_and_deploy",
                        "params": {
                            "cap_id": resolved_id,
                            "skill_kind": kind,
                            "skill_short": kind,
                            "identity_id": identity_id,
                            "description": f"Auto-generated from goal: {goal[:120]}",
                        },
                        "description": f"Create, validate, publish, install, and probe '{resolved_id}'",
                        "critical": True,
                    }
                ]

            steps: list[dict] = []
            if "publish" in gl or "register" in gl:
                steps.append({
                    "action": "publish_capability",
                    "params": {
                        "cap_id": resolved_id,
                        "name": resolved_id.replace("_", " ").title(),
                        "version": "1.0.0",
                        "description": f"Auto-generated: {goal[:80]}",
                        "skills": [f"{resolved_id}.{kind}"],
                    },
                    "description": f"Publishing {resolved_id} to registry",
                    "critical": True,
                })
            if "install" in gl or "add" in gl or "load" in gl:
                steps.append({
                    "action": "install_capability",
                    "params": {"cap_id": resolved_id, "identity_id": identity_id},
                    "description": f"Installing {resolved_id} onto identity",
                    "critical": True,
                })
            if steps:
                return steps

        # Inventory / list requests
        if any(w in gl for w in ("list", "inventory", "what can", "installed", "available")):
            return [{
                "action": "inventory",
                "params": {"identity_id": identity_id},
                "description": "Reporting installed vs available capabilities",
                "critical": True,
            }]

        return [{
            "action": "list_capabilities",
            "params": {},
            "description": "Assessing current registry state",
            "critical": False,
        }]

    @staticmethod
    def _extract_cap_id(gl: str) -> Optional[str]:
        """Extract a safe snake_case capability id — never English debris."""
        patterns = [
            r'(?:cap_id|capability_id)\s*[=:]\s*["\']?([a-z][a-z0-9_]{1,64})["\']?',
            r'(?:called|named)\s+["\']([a-z][a-z0-9_]{1,64})["\']',
            r'(?:called|named)\s+([a-z][a-z0-9]*_[a-z0-9_]+)',
            r'(?:create|build|make|write)\s+(?:a\s+|an\s+)?(?:new\s+)?(?:capability\s+)?["\']([a-z][a-z0-9_]{1,64})["\']',
            r'(?:create|build|make)\s+(?:a\s+|an\s+)?([a-z][a-z0-9]*_[a-z0-9_]+)\s+capability',
            r'capability\s+([a-z][a-z0-9]*_[a-z0-9_]+)',
            r'\b([a-z][a-z0-9]*_(?:skill|cap|tool|util|helper|reverse|echo))\b',
        ]
        for pat in patterns:
            m = re.search(pat, gl)
            if m:
                candidate = m.group(1).strip().lower().replace(" ", "_")
                if candidate not in _BLOCKED_CAP_NAMES and candidate.isidentifier():
                    return candidate

        # Multi-word explicit: "capability called Foo Bar" → foo_bar (only with called/named)
        m = re.search(r'(?:called|named)\s+([a-z]+(?:\s+[a-z]+){0,3})', gl)
        if m:
            words = [w for w in m.group(1).split() if w not in _BLOCKED_CAP_NAMES]
            if words:
                candidate = "_".join(words)
                if candidate not in _BLOCKED_CAP_NAMES and len(candidate) >= 3:
                    return candidate
        return None

    @staticmethod
    def _infer_skill_kind(gl: str, cap_id: Optional[str]) -> str:
        # Prefer functional intent over incidental words in examples ("hello world...")
        if "reverse" in gl or (cap_id and "reverse" in cap_id):
            return "reverse"
        if "count" in gl or (cap_id and "count" in cap_id):
            return "count"
        if "upper" in gl or "uppercase" in gl:
            return "upper"
        if "greet" in gl and "hello world" not in gl:
            return "greet"
        return "echo"

    @staticmethod
    def _capability_template(
        name: str,
        skills: Optional[list] = None,
        description: str = "",
    ) -> str:
        """Generate a valid capability Python file with real skill handlers."""
        cap_id = name
        class_name = "".join(p.title() for p in name.split("_")) + "Capability"
        skill_defs = skills or [{"name": "echo", "kind": "echo", "description": "Echo input"}]
        description = description or f"Auto-generated capability: {name}"

        skill_entries = []
        dispatch_entries = []
        methods = []
        for s in skill_defs:
            short = s.get("name") or s.get("kind") or "echo"
            kind = s.get("kind") or short
            full = f"{cap_id}.{short}"
            desc = s.get("description") or f"{kind} skill"
            skill_entries.append(
                f'        Skill(name="{full}", description="{desc}", permission="public"),'
            )
            dispatch_entries.append(f'                "{full}": self._{short},')
            methods.append(TaskPlannerCapability._handler_method(short, kind, cap_id))

        skills_block = "\n".join(skill_entries)
        dispatch_block = "\n".join(dispatch_entries)
        methods_block = "\n\n".join(methods)
        prompt_skills = ", ".join(f"{cap_id}.{s.get('name') or s.get('kind')}" for s in skill_defs)

        return f'''from __future__ import annotations

from typing import Any, Optional
from core.capabilities.base import Capability, Skill
from core.capabilities.registry import register
from core.capabilities.result import CapabilityResult


@register
class {class_name}(Capability):
    id = "{cap_id}"
    name = "{name.replace('_', ' ').title()}"
    version = "1.0.0"
    author = "auto-generated"
    license = "MIT"
    description = {description!r}
    permissions = ["public"]

    def __init__(self, config: Optional[dict] = None) -> None:
        super().__init__(config)

    def install(self, identity_id: str, storage: Any) -> None:
        storage.save(identity_id, "capability.{cap_id}", {{"installed_at": None}})

    def uninstall(self, identity_id: str, storage: Any) -> None:
        storage.delete(identity_id, "capability.{cap_id}")

    def prompts(self, identity_id: str) -> list[str]:
        return [
            "## {name} Skill",
            "Use {prompt_skills} when relevant. Do not invent results — call the skill.",
        ]

    _SKILLS = [
{skills_block}
    ]

    def skills(self) -> list[Skill]:
        return list(self._SKILLS)

    def call(self, skill_name: str, **params: Any) -> CapabilityResult:
        import time as _time
        _t0 = _time.monotonic()
        try:
            dispatch = {{
{dispatch_block}
            }}
            handler = dispatch.get(skill_name)
            if handler is None:
                return CapabilityResult.fail("{cap_id}", skill_name, "unknown_skill", f"Unknown skill: {{skill_name}}")
            data = handler(**params)
            return CapabilityResult.ok("{cap_id}", skill_name, data, source="auto-generated", duration_ms=(_time.monotonic() - _t0) * 1000)
        except Exception as e:
            return CapabilityResult.fail("{cap_id}", skill_name, type(e).__name__, str(e), duration_ms=(_time.monotonic() - _t0) * 1000)

{methods_block}
'''

    @staticmethod
    def _handler_method(short: str, kind: str, cap_id: str) -> str:
        if kind == "reverse":
            body = '''        text = params.get("text") or params.get("message") or params.get("input") or ""
        return {"original": text, "reversed": text[::-1], "goal_ok": True}'''
        elif kind == "upper":
            body = '''        text = params.get("text") or params.get("message") or params.get("input") or ""
        return {"original": text, "upper": text.upper(), "goal_ok": True}'''
        elif kind == "greet":
            body = f'''        who = params.get("name") or params.get("text") or "friend"
        return {{"message": f"Hello {{who}} from {cap_id}!", "goal_ok": True}}'''
        elif kind == "count":
            body = '''        text = params.get("text") or params.get("message") or params.get("input") or ""
        return {"text": text, "chars": len(text), "words": len(text.split()), "goal_ok": True}'''
        else:  # echo
            body = '''        text = params.get("text") or params.get("message") or params.get("input") or ""
        return {"echo": text, "goal_ok": True}'''
        return f'''    def _{short}(self, **params: Any) -> dict[str, Any]:
{body}'''
