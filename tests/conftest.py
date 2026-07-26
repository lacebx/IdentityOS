"""Global test state isolation — each module starts clean."""

import os
import signal
import subprocess
import shutil
import time
from pathlib import Path

import pytest


@pytest.fixture(autouse=True, scope="session")
def isolate_global_state():
    """Remove .identity_store and kill leftover servers before/after all tests."""
    repo_root = Path(__file__).resolve().parent.parent
    store_dir = repo_root / ".identity_store"
    _clean(store_dir)
    _kill_servers()
    yield
    _clean(store_dir)
    _kill_servers()


def _clean(store_dir: Path):
    if store_dir.exists():
        for p in store_dir.iterdir():
            if p.is_file():
                p.unlink()
            elif p.is_dir():
                shutil.rmtree(p, ignore_errors=True)


def _kill_servers():
    for _ in range(3):
        try:
            subprocess.run(
                ["pkill", "-f", "runtime.main"],
                capture_output=True, timeout=3,
            )
            time.sleep(1)
        except Exception:
            return
