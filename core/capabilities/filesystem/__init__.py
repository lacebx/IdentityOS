from __future__ import annotations

import os
from typing import Any, Optional

from core.capabilities.base import Capability, Skill
from core.capabilities.paths import resolve_workspace_path
from core.capabilities.registry import register
from core.capabilities.result import CapabilityResult


@register
class FileSystemCapability(Capability):
    id = "filesystem"
    name = "FileSystem"
    version = "1.0.0"
    author = "IdentityOS"
    license = "MIT"
    homepage = "https://github.com/lacebx/IdentityOS"
    description = "List directories, read files, and inspect file metadata"
    permissions = ["public"]

    def __init__(self, config: Optional[dict] = None) -> None:
        super().__init__(config)

    def install(self, identity_id: str, storage: Any) -> None:
        storage.save(identity_id, "capability.filesystem", {"installed_at": None})

    def uninstall(self, identity_id: str, storage: Any) -> None:
        storage.delete(identity_id, "capability.filesystem")

    def prompts(self, identity_id: str) -> list[str]:
        return [
            "## FileSystem Skills (MANDATORY — use for file/directory operations)",
            "When the user asks you to read a file or list a directory, you MUST use the skills below.",
            "Do NOT say you cannot access files. You CAN. Use the skills.",
        ]

    _SKILLS = [
        Skill(name="filesystem.list_dir", description="List files and directories within the workspace", permission="local", input_schema={"type": "object", "properties": {"path": {"type": "string"}}, "additionalProperties": False}, verification_params={"path": "."}),
        Skill(name="filesystem.read_file", description="Read a text file within the workspace", permission="local", input_schema={"type": "object", "properties": {"path": {"type": "string", "minLength": 1}, "max_length": {"type": "integer", "minimum": 1, "maximum": 100000}}, "required": ["path"], "additionalProperties": False}),
        Skill(name="filesystem.file_info", description="Get metadata about a path within the workspace", permission="local", input_schema={"type": "object", "properties": {"path": {"type": "string", "minLength": 1}}, "required": ["path"], "additionalProperties": False}),
    ]

    def skills(self) -> list[Skill]:
        return list(self._SKILLS)

    def call(self, skill_name: str, **params: Any) -> CapabilityResult:
        import time as _time
        _t0 = _time.monotonic()
        try:
            dispatch = {
                "filesystem.list_dir": self._list_dir,
                "filesystem.read_file": self._read_file,
                "filesystem.file_info": self._file_info,
            }
            handler = dispatch.get(skill_name)
            if handler is None:
                return CapabilityResult.fail("filesystem", skill_name, "unknown_skill", f"Unknown skill: {skill_name}")
            data = handler(**params)
            return CapabilityResult.from_data("filesystem", skill_name, data, source="local filesystem", duration_ms=(_time.monotonic() - _t0) * 1000)
        except Exception as e:
            return CapabilityResult.fail("filesystem", skill_name, type(e).__name__, str(e), duration_ms=(_time.monotonic() - _t0) * 1000)

    def _list_dir(self, path: str = ".", **kwargs: Any) -> dict[str, Any]:
        resolved = resolve_workspace_path(path, self._config)
        if not resolved.is_dir():
            return {"error": f"Not a directory: {resolved}"}
        entries = []
        for entry in sorted(os.scandir(resolved), key=lambda e: (not e.is_dir(), e.name)):
            entries.append({
                "name": entry.name,
                "type": "directory" if entry.is_dir() else "file",
                "size": entry.stat().st_size if entry.is_file() else 0,
            })
        return {"path": str(resolved), "entries": entries, "count": len(entries)}

    def _read_file(self, path: str = "", max_length: int = 5000, **kwargs: Any) -> dict[str, Any]:
        resolved = resolve_workspace_path(path, self._config)
        if not resolved.is_file():
            return {"error": f"Not a file: {resolved}"}
        max_length = max(1, min(int(max_length), 100000))
        with resolved.open() as f:
            content = f.read(max_length)
        return {
            "path": str(resolved),
            "content": content,
            "length": len(content),
            "truncated": len(content) >= max_length,
        }

    def _file_info(self, path: str = ".", **kwargs: Any) -> dict[str, Any]:
        resolved = resolve_workspace_path(path, self._config)
        if not resolved.exists():
            return {"error": f"Path does not exist: {resolved}"}
        stat = os.stat(resolved)
        return {
            "path": str(resolved),
            "type": "directory" if resolved.is_dir() else "file",
            "size_bytes": stat.st_size,
            "modified": stat.st_mtime,
            "created": stat.st_ctime,
        }
