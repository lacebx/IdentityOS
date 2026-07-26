from __future__ import annotations

import os
from typing import Any, Optional

from core.capabilities.base import Capability, Skill
from core.capabilities.registry import register


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
            "## Available FileSystem Skills",
            "You can list directory contents, read file contents, and check file metadata.",
        ]

    _SKILLS = [
        Skill(name="filesystem.list_dir", description="List files and directories at a path", permission="public"),
        Skill(name="filesystem.read_file", description="Read the contents of a text file", permission="public"),
        Skill(name="filesystem.file_info", description="Get metadata about a file or directory", permission="public"),
    ]

    def skills(self) -> list[Skill]:
        return list(self._SKILLS)

    def call(self, skill_name: str, **params: Any) -> Any:
        dispatch = {
            "filesystem.list_dir": self._list_dir,
            "filesystem.read_file": self._read_file,
            "filesystem.file_info": self._file_info,
        }
        handler = dispatch.get(skill_name)
        if handler is None:
            raise ValueError(f"Unknown skill: {skill_name}")
        return handler(**params)

    def _list_dir(self, path: str = ".", **kwargs: Any) -> dict[str, Any]:
        if not os.path.isdir(path):
            return {"error": f"Not a directory: {path}"}
        entries = []
        for entry in sorted(os.scandir(path), key=lambda e: (not e.is_dir(), e.name)):
            entries.append({
                "name": entry.name,
                "type": "directory" if entry.is_dir() else "file",
                "size": entry.stat().st_size if entry.is_file() else 0,
            })
        return {"path": os.path.abspath(path), "entries": entries, "count": len(entries)}

    def _read_file(self, path: str = "", max_length: int = 5000, **kwargs: Any) -> dict[str, Any]:
        if not os.path.isfile(path):
            return {"error": f"Not a file: {path}"}
        with open(path) as f:
            content = f.read(max_length)
        return {
            "path": os.path.abspath(path),
            "content": content,
            "length": len(content),
            "truncated": len(content) >= max_length,
        }

    def _file_info(self, path: str = ".", **kwargs: Any) -> dict[str, Any]:
        if not os.path.exists(path):
            return {"error": f"Path does not exist: {path}"}
        stat = os.stat(path)
        return {
            "path": os.path.abspath(path),
            "type": "directory" if os.path.isdir(path) else "file",
            "size_bytes": stat.st_size,
            "modified": stat.st_mtime,
            "created": stat.st_ctime,
        }
