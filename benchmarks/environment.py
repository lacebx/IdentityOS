"""Freeze the machine + model used for a benchmark run."""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any


DEFAULT_OLLAMA_HOST = "http://localhost:11434"


def _run(cmd: list[str]) -> str:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return f"[unavailable: {exc}]"
    out = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()
    if proc.returncode != 0 and err:
        return err
    return out or err


def list_ollama_models(host: str = DEFAULT_OLLAMA_HOST, timeout: float = 2.0) -> list[dict[str, Any]]:
    try:
        with urllib.request.urlopen(f"{host.rstrip('/')}/api/tags", timeout=timeout) as resp:
            payload = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return []
    return payload.get("models") or []


def capture_environment(
    model: str,
    host: str = DEFAULT_OLLAMA_HOST,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    models = list_ollama_models(host=host)
    record = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "hostname": platform.node(),
        "uname": _run(["uname", "-a"]),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "memory": _run(["free", "-h"]),
        "cpu": _run(["lscpu"]),
        "ollama_version": _run(["ollama", "--version"]),
        "ollama_binary": shutil.which("ollama"),
        "ollama_models": models,
        "requested_model": model,
        "model_present": any(
            (m.get("name") == model) or str(m.get("name", "")).startswith(model)
            for m in models
        ),
        "cwd": os.getcwd(),
    }
    if extra:
        record.update(extra)
    return record
