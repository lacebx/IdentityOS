"""Filesystem boundary helpers shared by local capabilities."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def allowed_roots(config: dict[str, Any]) -> list[Path]:
    configured = config.get("allowed_roots")
    if isinstance(configured, str):
        configured = [configured]
    if not configured:
        env_roots = os.environ.get("IDENTITY_WORKSPACE_ROOTS", "")
        configured = [p for p in env_roots.split(os.pathsep) if p] or [os.getcwd()]
    return [Path(root).expanduser().resolve() for root in configured]


def resolve_workspace_path(path: str, config: dict[str, Any]) -> Path:
    """Resolve *path* and reject targets outside configured workspace roots."""
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    resolved = candidate.resolve()
    roots = allowed_roots(config)
    if not any(resolved == root or resolved.is_relative_to(root) for root in roots):
        rendered = ", ".join(str(root) for root in roots)
        raise PermissionError(
            f"Path '{resolved}' is outside the allowed workspace root(s): {rendered}"
        )
    return resolved
