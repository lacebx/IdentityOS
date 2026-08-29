from __future__ import annotations

import os
from typing import Any, Optional

from core.capabilities.base import Capability, Skill
from core.capabilities.paths import resolve_workspace_path
from core.capabilities.registry import register
from core.capabilities.result import CapabilityResult


@register
class FileToolsCapability(Capability):
    id = "file_tools"
    name = "File Tools"
    version = "1.0.0"
    author = "IdentityOS"
    license = "MIT"
    homepage = "https://github.com/lacebx/IdentityOS"
    description = "Write, create, and modify files and directories on the local filesystem"
    permissions = ["filesystem:write"]

    def __init__(self, config: Optional[dict] = None) -> None:
        super().__init__(config)

    def install(self, identity_id: str, storage: Any) -> None:
        storage.save(identity_id, "capability.file_tools", {"installed_at": None})

    def uninstall(self, identity_id: str, storage: Any) -> None:
        storage.delete(identity_id, "capability.file_tools")

    def prompts(self, identity_id: str) -> list[str]:
        return [
            "## File Tools Skills (MANDATORY — use for creating/writing files)",
            "When you need to create a new file, write code, or modify an existing file, you MUST use the skills below.",
            "You have the ability to create directories, write files, and append to files.",
            "Use these skills when generating new capability code, creating manifests, or any file creation task.",
        ]

    _SKILLS = [
        Skill(
            name="file_tools.write_file",
            description="Write content to a file within an allowed workspace root",
            permission="filesystem:write",
            effect="write",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "minLength": 1},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
                "additionalProperties": False,
            },
        ),
        Skill(
            name="file_tools.append_file",
            description="Append content to a file within an allowed workspace root",
            permission="filesystem:write",
            effect="write",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "minLength": 1},
                    "content": {"type": "string", "minLength": 1},
                },
                "required": ["path", "content"],
                "additionalProperties": False,
            },
        ),
        Skill(
            name="file_tools.create_directory",
            description="Create a directory within an allowed workspace root",
            permission="filesystem:write",
            effect="write",
            input_schema={
                "type": "object",
                "properties": {"path": {"type": "string", "minLength": 1}},
                "required": ["path"],
                "additionalProperties": False,
            },
        ),
    ]

    def skills(self) -> list[Skill]:
        return list(self._SKILLS)

    def call(self, skill_name: str, **params: Any) -> CapabilityResult:
        import time as _time
        _t0 = _time.monotonic()
        try:
            dispatch = {
                "file_tools.write_file": self._write_file,
                "file_tools.append_file": self._append_file,
                "file_tools.create_directory": self._create_directory,
            }
            handler = dispatch.get(skill_name)
            if handler is None:
                return CapabilityResult.fail("file_tools", skill_name, "unknown_skill", f"Unknown skill: {skill_name}")
            data = handler(**params)
            return CapabilityResult.from_data("file_tools", skill_name, data, source="local filesystem", duration_ms=(_time.monotonic() - _t0) * 1000)
        except Exception as e:
            return CapabilityResult.fail("file_tools", skill_name, type(e).__name__, str(e), duration_ms=(_time.monotonic() - _t0) * 1000)

    def _write_file(self, path: str = "", content: str = "", **kwargs: Any) -> dict[str, Any]:
        if not path:
            return {"error": "path is required"}
        resolved = resolve_workspace_path(path, self._config)
        os.makedirs(resolved.parent, exist_ok=True)
        with resolved.open("w") as f:
            f.write(content)
        return {
            "path": str(resolved),
            "bytes_written": len(content),
            "status": "created" if resolved.is_file() else "error",
        }

    def _append_file(self, path: str = "", content: str = "", **kwargs: Any) -> dict[str, Any]:
        if not path:
            return {"error": "path is required"}
        resolved = resolve_workspace_path(path, self._config)
        if not resolved.is_file():
            return {"error": f"File does not exist: {resolved}"}
        with resolved.open("a") as f:
            f.write(content)
        return {
            "path": str(resolved),
            "bytes_appended": len(content),
            "status": "appended",
        }

    def _create_directory(self, path: str = "", **kwargs: Any) -> dict[str, Any]:
        if not path:
            return {"error": "path is required"}
        resolved = resolve_workspace_path(path, self._config)
        os.makedirs(resolved, exist_ok=True)
        return {
            "path": str(resolved),
            "status": "created" if resolved.is_dir() else "error",
        }
