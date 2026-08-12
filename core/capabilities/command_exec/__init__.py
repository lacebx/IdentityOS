from __future__ import annotations

import subprocess
from typing import Any, Optional
from core.capabilities.base import Capability, Skill
from core.capabilities.registry import register
from core.capabilities.result import CapabilityResult


@register
class CommandExecCapability(Capability):
    id = "command_exec"
    name = "Command Exec"
    version = "1.0.0"
    author = "auto-generated"
    license = "MIT"
    description = "Executes real shell commands and returns actual stdout/stderr/exit code"
    permissions = ["public"]

    def __init__(self, config: Optional[dict] = None) -> None:
        super().__init__(config)

    def install(self, identity_id: str, storage: Any) -> None:
        storage.save(identity_id, "capability.command_exec", {"installed_at": None})

    def uninstall(self, identity_id: str, storage: Any) -> None:
        storage.delete(identity_id, "capability.command_exec")

    def prompts(self, identity_id: str) -> list[str]:
        return ["## Command Exec Skill\nUse command_exec.run to execute a shell command. It returns real stdout/stderr and the exit code."]

    _SKILLS = [
        Skill(name="command_exec.run", description="Execute a shell command, returning actual stdout, stderr, and exit code", permission="public"),
    ]

    def skills(self) -> list[Skill]:
        return list(self._SKILLS)

    def call(self, skill_name: str, **params: Any) -> CapabilityResult:
        import time as _time
        _t0 = _time.monotonic()
        try:
            dispatch = {
                "command_exec.run": self._run,
            }
            handler = dispatch.get(skill_name)
            if handler is None:
                return CapabilityResult.fail("command_exec", skill_name, "unknown_skill", f"Unknown skill: {skill_name}")
            data = handler(**params)
            return CapabilityResult.from_data("command_exec", skill_name, data, source="command exec", duration_ms=(_time.monotonic() - _t0) * 1000)
        except Exception as e:
            return CapabilityResult.fail("command_exec", skill_name, type(e).__name__, str(e), duration_ms=(_time.monotonic() - _t0) * 1000)

    def _run(self, command: str = "", timeout: int = 30, **kwargs: Any) -> dict[str, Any]:
        if not command:
            return {"error": "No command provided", "exit_code": -1, "stdout": "", "stderr": "command is empty"}
        try:
            proc = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return {
                "command": command,
                "exit_code": proc.returncode,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
                "found": proc.returncode == 0,
            }
        except subprocess.TimeoutExpired:
            return {"command": command, "error": "timeout", "exit_code": 124, "stdout": "", "stderr": f"command timed out after {timeout}s"}
        except FileNotFoundError:
            return {"command": command, "error": "not_found", "exit_code": 127, "stdout": "", "stderr": f"command not found: {command}"}
        except Exception as e:
            return {"command": command, "error": str(e), "exit_code": -1, "stdout": "", "stderr": str(e)}
