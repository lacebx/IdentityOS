"""Global test state isolation — each module starts clean."""

import os
import subprocess
import time

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


@pytest.fixture(autouse=True)
def _flush_deferred_post_process(monkeypatch):
    """Drain IdentityRuntime deferred post-processing after process().

    Production chat returns before eval/memory/mutation persistence finishes;
    tests assert on that state immediately, so flush after each process().

    Set ``runtime._skip_test_post_process_flush = True`` to observe deferral.
    """
    from runtime.orchestrator import IdentityRuntime

    if os.environ.get("IDENTITYOS_NO_TEST_FLUSH", "").strip().lower() in ("1", "true", "yes"):
        yield
        return

    original = IdentityRuntime.process

    def _wrapped(self, *args, **kwargs):
        resp = original(self, *args, **kwargs)
        if not getattr(self, "_skip_test_post_process_flush", False):
            self.flush_post_process()
        return resp

    monkeypatch.setattr(IdentityRuntime, "process", _wrapped)
    yield


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
