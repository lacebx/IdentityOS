from __future__ import annotations

from typing import Any, Optional
from core.capabilities.base import Capability, Skill
from core.capabilities.registry import register, lookup
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
}


@register
class TaskPlannerCapability(Capability):
    id = "task_planner"
    name = "Task Planner"
    version = "1.0.0"
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
            "  2. The planner will break it into steps, execute each one, and return progress",
            "  3. Report the final result to the user — do NOT describe intermediate steps in detail",
            "Example: task_planner.plan_and_execute(goal='create a greeting skill, validate it, publish it, and install it')",
        ]

    _SKILLS = [
        Skill(name="task_planner.plan_and_execute", description="Plan and execute a multi-step task. Provide the goal as text. Returns progress indicators like [1/5] and final results.", permission="public"),
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
            data = handler(**params)
            return CapabilityResult.ok("task_planner", skill_name, data, source="task planner", duration_ms=(_time.monotonic() - _t0) * 1000)
        except Exception as e:
            return CapabilityResult.fail("task_planner", skill_name, type(e).__name__, str(e), duration_ms=(_time.monotonic() - _t0) * 1000)

    def _plan_and_execute(self, goal: str = "", steps: Optional[list] = None, **kwargs: Any) -> dict[str, Any]:
        """
        Given a goal, generate a step-by-step plan and execute each step.
        Returns a structured report with progress indicators.
        """
        if not goal and not steps:
            return {"error": "Provide a 'goal' string describing what you want to accomplish."}

        # If steps are provided directly, use them. Otherwise auto-generate from goal.
        plan = steps or self._generate_plan(goal)
        total = len(plan)
        step_results = []

        for i, step in enumerate(plan, 1):
            action = step.get("action", "")
            params = step.get("params", {})
            description = step.get("description", action)

            progress_line = f"[{i}/{total}] {description}"
            handler = _STEP_HANDLERS.get(action)

            if handler is None:
                step_results.append({
                    "step": i,
                    "action": action,
                    "progress": progress_line,
                    "success": False,
                    "error": f"No handler for action: {action}",
                })
                continue

            try:
                result = handler(params)
                step_results.append({
                    "step": i,
                    "action": action,
                    "progress": progress_line,
                    "success": result.success,
                    "data": result.data,
                    "duration_ms": result.duration_ms,
                })
            except Exception as e:
                step_results.append({
                    "step": i,
                    "action": action,
                    "progress": progress_line,
                    "success": False,
                    "error": str(e),
                })

        total_success = sum(1 for r in step_results if r.get("success"))
        return {
            "plan": plan,
            "total_steps": total,
            "completed": total_success,
            "failed": total - total_success,
            "all_succeeded": total_success == total,
            "results": step_results,
        }

    @staticmethod
    def _generate_plan(goal: str) -> list[dict]:
        """Parse a natural language goal into an ordered list of steps."""
        import re
        gl = goal.lower()

        # Extract capability name: look for words that appear right after "create", "called", "named", "a", "an"
        cap_name = None
        patterns = [
            r'(?:create|build|make|write)\s+(?:a\s+|an\s+)?(?:capability\s+|skill\s+)?["\']?([a-z_]\w*)["\']?',
            r'(?:called|named)\s+["\']?([a-z_]\w*)["\']?',
            r'(?:capability|skill)\s+["\']?([a-z_]\w*)["\']?',
            r'["\']?([a-z_]\w*_cap)["\']?',
            r'["\']?([a-z_]\w*_skill)["\']?',
        ]
        for pat in patterns:
            m = re.search(pat, gl)
            if m:
                candidate = m.group(1)
                # Skip action verbs that aren't capability names
                if candidate not in ("create", "build", "make", "write", "publish", "install", "validate", "check", "test", "list", "show", "add", "load", "register", "update", "delete", "remove"):
                    cap_name = candidate
                    break

        steps = []

        if cap_name:
            cap_dir = f"core/capabilities/{cap_name}"
            cap_path = f"{cap_dir}/__init__.py"
            steps.append({
                "action": "create_directory",
                "params": {"path": cap_dir},
                "description": f"Creating {cap_name} capability directory",
            })
            steps.append({
                "action": "write_file",
                "params": {
                    "path": cap_path,
                    "content": TaskPlannerCapability._capability_template(cap_name),
                },
                "description": f"Writing {cap_name} capability code",
            })

            if "valid" in gl or "check" in gl or "syntax" in gl or "test" in gl:
                steps.append({
                    "action": "validate_syntax",
                    "params": {"path": cap_path},
                    "description": f"Validating {cap_name} syntax",
                })
                steps.append({
                    "action": "check_interface",
                    "params": {"path": cap_path},
                    "description": f"Checking {cap_name} Capability interface",
                })

            if "publish" in gl or "register" in gl:
                steps.append({
                    "action": "publish_capability",
                    "params": {"cap_id": cap_name, "name": cap_name.replace("_", " ").title(), "version": "1.0.0", "description": f"Auto-generated: {goal[:80]}"},
                    "description": f"Publishing {cap_name} to registry",
                })

            if "install" in gl or "add" in gl or "load" in gl:
                steps.append({
                    "action": "install_capability",
                    "params": {"cap_id": cap_name},
                    "description": f"Installing {cap_name} onto identity",
                })
        else:
            # No capability name found, do generic actions
            if "publish" in gl or "register" in gl:
                steps.append({"action": "list_capabilities", "params": {}, "description": "Checking registry"})
            if "list" in gl or "show" in gl or "what" in gl:
                steps.append({"action": "list_capabilities", "params": {}, "description": "Listing capabilities"})

        if not steps:
            steps.append({"action": "list_capabilities", "params": {}, "description": "Assessing current state"})

        return steps

    @staticmethod
    def _capability_template(name: str) -> str:
        """Generate a minimal but valid capability Python file."""
        cap_id = name
        class_name = "".join(p.title() for p in name.split("_")) + "Capability"
        skill_name = f"{cap_id}.greet"
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
    description = "Auto-generated capability: {name}"
    permissions = ["public"]

    def __init__(self, config: Optional[dict] = None) -> None:
        super().__init__(config)

    def install(self, identity_id: str, storage: Any) -> None:
        storage.save(identity_id, "capability.{cap_id}", {{"installed_at": None}})

    def uninstall(self, identity_id: str, storage: Any) -> None:
        storage.delete(identity_id, "capability.{cap_id}")

    def prompts(self, identity_id: str) -> list[str]:
        return ["## {name} Skill\\nUse {skill_name} to greet."]

    _SKILLS = [
        Skill(name="{skill_name}", description="Greet the user", permission="public"),
    ]

    def skills(self) -> list[Skill]:
        return list(self._SKILLS)

    def call(self, skill_name: str, **params: Any) -> CapabilityResult:
        import time as _time
        _t0 = _time.monotonic()
        try:
            dispatch = {{
                "{skill_name}": self._greet,
            }}
            handler = dispatch.get(skill_name)
            if handler is None:
                return CapabilityResult.fail("{cap_id}", skill_name, "unknown_skill", f"Unknown skill: {{skill_name}}")
            data = handler(**params)
            return CapabilityResult.ok("{cap_id}", skill_name, data, source="auto-generated", duration_ms=(_time.monotonic() - _t0) * 1000)
        except Exception as e:
            return CapabilityResult.fail("{cap_id}", skill_name, type(e).__name__, str(e), duration_ms=(_time.monotonic() - _t0) * 1000)

    def _greet(self, **kwargs: Any) -> dict[str, Any]:
        return {{"message": "Hello from {name}!"}}
'''
