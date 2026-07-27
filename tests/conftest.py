"""Global test state isolation — each module starts clean."""

import os
import signal
import subprocess
import time
from pathlib import Path

import pytest


@pytest.fixture(autouse=True, scope="session")
def isolate_global_state():
    """Kill leftover servers before/after all tests.

    Does NOT touch .identity_store — individual test fixtures that need
    a clean store create their own with tmp_path or their own cleanup.
    """
    _kill_servers()
    yield
    _kill_servers()


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
