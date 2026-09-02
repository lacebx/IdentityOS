"""Public persisted-state diagnostics regression tests."""

from core.identity import create_identity
from core.memory import MemoryFragment, MemoryType
from identityos.diagnostics import IdentityDiagnostics
from runtime.orchestrator import IdentityRuntime
from runtime.persistence import JSONFileBackend


def test_diagnostics_report_observed_state_and_restart_evidence(tmp_path):
    store_path = tmp_path / "identities"
    runtime = IdentityRuntime(storage=JSONFileBackend(root_dir=str(store_path)))
    identity = create_identity("Diagnostics Bot", identity_id="diagnostics-bot")
    runtime.register(identity)
    memory = MemoryFragment(
        identity_id=identity.id,
        user_id=identity.id,
        content="evidence survives",
        memory_type=MemoryType.SEMANTIC,
    )
    runtime.memory_store.add(memory)
    runtime._persist_memory(memory)

    evidence = IdentityDiagnostics(str(store_path)).inspect_health(identity.id)

    assert evidence.counts["memories"] == 1
    assert evidence.restart_recovery_pct == 100.0
    assert all(evidence.restart_evidence["checks"].values())
    assert len(evidence.identity_fingerprint) == 64


def test_diagnostics_reject_unknown_identity(tmp_path):
    diagnostics = IdentityDiagnostics(str(tmp_path / "identities"))

    try:
        diagnostics.inspect_health("missing")
    except ValueError as exc:
        assert "missing" in str(exc)
    else:
        raise AssertionError("missing identity should not produce health evidence")
