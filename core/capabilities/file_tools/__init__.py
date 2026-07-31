from __future__ import annotations

import os
from typing import Any, Optional

from core.capabilities.base import Capability, Skill
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
    permissions = ["public"]

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
        Skill(name="file_tools.write_file", description="Write content to a file, creating directories and file if they do not exist", permission="public"),
        Skill(name="file_tools.append_file", description="Append content to an existing file", permission="public"),
        Skill(name="file_tools.create_directory", description="Create a directory and all parent directories if they do not exist", permission="public"),
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
            return CapabilityResult.ok("file_tools", skill_name, data, source="local filesystem", duration_ms=(_time.monotonic() - _t0) * 1000)
        except Exception as e:
            return CapabilityResult.fail("file_tools", skill_name, type(e).__name__, str(e), duration_ms=(_time.monotonic() - _t0) * 1000)

    def _write_file(self, path: str = "", content: str = "", **kwargs: Any) -> dict[str, Any]:
        if not path:
            return {"error": "path is required"}
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w") as f:
            f.write(content)
        return {
            "path": os.path.abspath(path),
            "bytes_written": len(content),
            "status": "created" if os.path.isfile(path) else "error",
        }

    def _append_file(self, path: str = "", content: str = "", **kwargs: Any) -> dict[str, Any]:
        if not path:
            return {"error": "path is required"}
        if not os.path.isfile(path):
            return {"error": f"File does not exist: {path}"}
        with open(path, "a") as f:
            f.write(content)
        return {
            "path": os.path.abspath(path),
            "bytes_appended": len(content),
            "status": "appended",
        }

    def _create_directory(self, path: str = "", **kwargs: Any) -> dict[str, Any]:
        if not path:
            return {"error": "path is required"}
        os.makedirs(path, exist_ok=True)
        return {
            "path": os.path.abspath(path),
            "status": "created" if os.path.isdir(path) else "error",
        }
