"""Direct integration coverage for IdentityRuntime subsystem wiring."""

from __future__ import annotations

from core.acquisition import get_acquisition_provider
from core.executive.models import TaskStatus
from core.identity import create_identity
from runtime.orchestrator import IdentityRuntime
from runtime.persistence import JSONFileBackend


def test_runtime_wires_and_releases_durable_acquisition(tmp_path):
    storage = JSONFileBackend(root_dir=str(tmp_path / "store"))
    runtime = IdentityRuntime(storage=storage)
    identity = create_identity("Orchestrated", identity_id="orchestrated")
    runtime.register(identity)

    assert runtime.executive is not None
    assert get_acquisition_provider(storage) is runtime.executive
    if runtime.prometheus is not None:
        assert runtime.prometheus.executive is runtime.executive

    runtime.capability_registry.install(identity.id, "registry_manager")
    runtime.capability_registry.grant(
        identity.id,
        "registry_manager",
        "capability:manage",
    )
    queued = runtime.capability_registry.call(
        identity.id,
        "registry_manager.install_capability",
        cap_id="calc",
    )

    for _ in range(100):
        runtime.executive.process_ready(identity.id)
        task = runtime.executive.get_task(identity.id, queued.data["task_id"])
        if task.status in (
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.BLOCKED,
        ):
            break

    assert task.status == TaskStatus.COMPLETED, task.error
    assert [step.action for step in task.steps] == [
        "registry_search",
        "trust",
        "dependencies",
        "generate",
        "validate",
        "publish",
        "install",
        "activate",
        "invoke",
        "persist",
        "reload",
        "reuse",
        "verify_goal",
    ]
    assert task.step_by_id("invoke").result["invoked"] is True
    assert task.step_by_id("persist").result["persisted"] is True
    assert task.step_by_id("reload").result["reloaded"] is True
    assert task.step_by_id("reuse").result["reused"] is True
    assert runtime.capability_registry.get(identity.id, "calc") is not None

    runtime.shutdown()
    assert get_acquisition_provider(storage) is None


def test_runtime_install_local_datetime_capability_and_call(tmp_path):
    storage = JSONFileBackend(root_dir=str(tmp_path / "store"))
    runtime = IdentityRuntime(storage=storage)
    identity = create_identity("DatetimeCaps", identity_id="datetime-caps")
    runtime.register(identity)

    runtime.capability_registry.install(identity.id, "datetime")
    now = runtime.capability_registry.call(identity.id, "datetime.now")

    assert now.success is True, now.error
    assert "datetime" in now.data

    runtime.shutdown()
