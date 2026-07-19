"""
End-to-end regression tests for identity persistence across CLI and runtime.

Tests cover:
- CLI creates identity → persisted to disk
- Runtime loads persisted identity
- GET /identity returns it
- POST /process succeeds
- Memory is stored and retrievable
- Restart preserves identity
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from core.memory import MemoryFragment, MemoryType
from runtime.orchestrator import IdentityRuntime, InteractionRequest
from runtime.persistence import JSONFileBackend


@pytest.fixture
def project_root():
    """Return absolute path to the project root (one level up from tests/)."""
    return str(Path(__file__).resolve().parent.parent)


@pytest.fixture
def temp_store(tmp_path):
    """Use a temp dir so tests don't interfere with real data.

    --store is a top-level argparse arg, so it must appear *before*
    the subcommand (e.g., "python -m cli.main --store X create ...").
    We set cwd to tmp_path so the default '.identity_store' resolves
    inside the temp dir, avoiding any global --store flag at all.
    """
    return str(tmp_path)


@pytest.fixture
def cli_create(temp_store, project_root):
    """Create an identity via the CLI and return its ID."""
    result = subprocess.run(
        [sys.executable, "-m", "cli.main", "create",
         "--name", "E2ETestBot", "--persona", "assistant"],
        capture_output=True, text=True,
        cwd=temp_store,
        env={**os.environ, "PYTHONPATH": project_root},
    )
    assert result.returncode == 0, f"CLI create failed: {result.stderr}"
    for line in result.stdout.strip().split("\n"):
        if "id" in line and ":" in line:
            return line.split(":")[1].strip()
    raise RuntimeError(f"Could not extract identity ID from: {result.stdout}")


class TestE2EPersistence:
    """End-to-end: CLI create → runtime load → process → restart → verify."""

    def test_cli_creates_files(self, cli_create, temp_store):
        """Verify the CLI actually wrote files to disk."""
        ident_dir = Path(temp_store) / ".identity_store" / cli_create
        assert ident_dir.is_dir(), f"Not found: {ident_dir}"
        files = [f.name for f in ident_dir.glob("*.json")]
        assert "latest_snapshot.json" in files
        assert any(f.startswith("snapshot__") for f in files)

    def _storage(self, temp_store):
        return JSONFileBackend(root_dir=str(Path(temp_store) / ".identity_store"))

    def test_runtime_loads_persisted_identity(self, cli_create, temp_store):
        """Runtime should see CLI-created identities after load_persisted()."""
        runtime = IdentityRuntime(storage=self._storage(temp_store))
        count = runtime.load_persisted()
        assert count >= 1

        loaded = runtime.load(cli_create)
        assert loaded is not None
        assert loaded.id == cli_create
        assert loaded.name == "E2ETestBot"

    def test_get_identity_returns_identity(self, cli_create, temp_store):
        """Runtime.list_identities() should include persisted identities."""
        runtime = IdentityRuntime(storage=self._storage(temp_store))
        runtime.load_persisted()
        ids = [s.id for s in runtime.list_identities()]
        assert cli_create in ids

    def test_process_interaction(self, cli_create, temp_store):
        """Runtime.process() should succeed for persisted identities."""
        runtime = IdentityRuntime(storage=self._storage(temp_store))
        runtime.load_persisted()

        sid = runtime.start_session(cli_create)
        req = InteractionRequest(
            identity_id=cli_create,
            user_input="Hello, who are you?",
            session_id=sid,
        )
        resp = runtime.process(req)
        assert resp.policy_passed is True
        assert "Context prepared for" in resp.output
        assert resp.eval_score is not None

    def test_memory_stored_and_retrievable(self, cli_create, temp_store):
        """Memory should be storable and searchable."""
        runtime = IdentityRuntime(storage=self._storage(temp_store))
        runtime.load_persisted()

        mem = MemoryFragment(
            identity_id=cli_create,
            content="User likes Python programming",
            memory_type=MemoryType.SEMANTIC,
        )
        runtime.memory_store.add(mem)
        assert len(runtime.memory_store) >= 1

        results = runtime.memory_store.search_keywords(
            "Python", identity_id=cli_create
        )
        assert len(results) >= 1
        assert "Python" in results[0].content

    def test_persistence_survives_restart(self, cli_create, temp_store):
        """Simulate a runtime restart — data should still be accessible."""
        runtime1 = IdentityRuntime(storage=self._storage(temp_store))
        runtime1.load_persisted()
        assert runtime1.load(cli_create) is not None

        # "Restart" — create a new runtime pointing at the same store
        runtime2 = IdentityRuntime(storage=self._storage(temp_store))
        count = runtime2.load_persisted()
        assert count >= 1

        loaded = runtime2.load(cli_create)
        assert loaded is not None
        assert loaded.name == "E2ETestBot"
