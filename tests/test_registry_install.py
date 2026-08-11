"""
test_registry_install.py — R4 regression: install_capability actually installs.

The old ``registry_manager.install_capability`` skill only looked the
capability up in the registry index and returned ``{"status":
"ready_to_install", "message": "To install: ..."}`` — delegating the real
install to a hypothetical caller.  The runtime boundary invariant: the
runtime performs the action; the model only requests it.  A skill that
reports "ready to install" without installing is a fabrication.

New contract asserts:
  * target capability is resolved from the registry index first;
  * when identity/registry context is available, the skill performs a real
    install into the identity registry (verified via the registry).
  * when no registry context is available it says so instead of faking.
"""

import pytest

from core.capabilities.registry import CapabilityRegistry, lookup


@pytest.fixture()
def storage(tmp_path):
    from runtime.persistence import JSONFileBackend
    return JSONFileBackend(root_dir=str(tmp_path / "store"))


@pytest.fixture()
def registration_index(tmp_path):
    """Isolate the registry index + marketplace under a temp root."""
    import json
    import os

    root = tmp_path / "registry"
    (root / "capabilities").mkdir(parents=True, exist_ok=True)
    (root / "capabilities" / "index.json").write_text(
        json.dumps({"registry": "IdentityOS Marketplace", "capabilities": [
            {"id": "calc", "name": "Calc", "version": "1.0.0", "description": "arithmetic"},
            {"id": "datetime", "name": "DateTime", "version": "1.0.0", "description": "current time"},
        ]}), encoding="utf-8"
    )
    (root / "index.json").write_text(
        json.dumps({"capabilities": [
            {"id": "calc", "name": "Calc", "version": "1.0.0", "description": "arithmetic"},
            {"id": "datetime", "name": "DateTime", "version": "1.0.0", "description": "current time"},
        ]}), encoding="utf-8"
    )
    return root


def _rm_instance(registration_index):
    import os
    from core.capabilities.registry_manager import RegistryManagerCapability

    cap = RegistryManagerCapability()
    # point registry paths at the isolated index instead of the repo registry
    _root = os.path.abspath(str(registration_index))
    cap._registry_path = lambda: _root  # type: ignore[method-assign]
    return cap


def test_install_capability_real_install_with_identity_registry(storage, registration_index):
    """With identity+registry context the skill must install for real."""
    reg = CapabilityRegistry(storage)
    rmgmt = _rm_instance(registration_index)
    # simulate the identity having registry_manager loaded so the instance
    # carries a live registry reference
    rmgmt._identity_registry = reg
    rmgmt._identity_id = "tester"

    res = rmgmt.call("registry_manager.install_capability", cap_id="calc")
    assert res.success
    data = res.data
    assert data["status"] == "installed"
    assert data["cap_id"] == "calc"
    assert res.data["identity_id"] == "tester"

    # the registry must actually contain the installed capability
    installed = reg.get("tester", "calc")
    assert installed is not None, "calc was not really installed"
    assert installed.id == "calc"


def test_install_capability_missing_context_is_honest(storage, registration_index):
    """Without identity/registry context the skill must not fake an install."""
    reg = CapabilityRegistry(storage)
    rmgmt = _rm_instance(registration_index)

    res = rmgmt.call("registry_manager.install_capability", cap_id="calc")
    assert res.success  # the call itself succeeded
    assert res.data["status"] == "install_context_missing"
    assert res.data["cap_id"] == "calc"

    # nothing may have been installed
    assert reg.get("tester", "calc") is None


def test_install_capability_unknown_id_fails(storage, registration_index):
    rmgmt = _rm_instance(registration_index)
    res = rmgmt.call("registry_manager.install_capability", cap_id="does_not_exist")
    assert res.success is False or (res.success and "error" in res.data)
    assert "does_not_exist" in res.data.get("error", "")


def test_install_capability_passthrough_from_executor_injects_context(tmp_path):
    """The executory passthrough must inject identity_id + registry."""
    from core.executive.executor import ExecutionContext, execute_step
    from core.executive.models import Task, TaskStep
    from runtime.persistence import JSONFileBackend

    storage = JSONFileBackend(root_dir=str(tmp_path / "store"))
    reg = CapabilityRegistry(storage)
    ctx = ExecutionContext(identity_id="tester", capability_registry=reg, storage=storage)
    task = Task(task_id="t", goal="g", identity_id="tester")
    step = TaskStep(
        action="install_capability",
        description="install",
        params={"capability": "calc"},
    )
    ok, result, evidence = execute_step(task, step, ctx)
    assert ok is True
    assert result.get("status") == "installed"
    assert reg.get("tester", "calc") is not None