"""Tests for Gate 0 honesty substrate + RSI create/publish/install loop."""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

from core.capabilities.registry import (
    CapabilityRegistry,
    available,
    import_capability,
    lookup,
)
from core.capabilities.result import CapabilityResult
from core.capabilities.task_planner import TaskPlannerCapability


class _MemStorage:
    def __init__(self) -> None:
        self._data: dict[tuple[str, str], dict] = {}

    def load(self, identity_id: str, namespace: str):
        return self._data.get((identity_id, namespace))

    def save(self, identity_id: str, namespace: str, data: dict) -> None:
        self._data[(identity_id, namespace)] = data

    def delete(self, identity_id: str, namespace: str) -> None:
        self._data.pop((identity_id, namespace), None)


@pytest.fixture()
def reg(tmp_path, monkeypatch):
    # Ensure builtins are imported
    import core.capabilities  # noqa: F401

    storage = _MemStorage()
    registry = CapabilityRegistry(storage)
    # Install bootstrap caps onto test identity
    for cap_id in ("registry_manager", "task_planner", "file_tools", "skill_validator"):
        registry.install("bones", cap_id)
    return registry


def test_capability_result_goal_ok_false_is_not_success():
    r = CapabilityResult.ok(
        "registry_manager",
        "install_capability",
        {"error": "identity_id is required", "goal_ok": False},
    )
    assert r.success is False
    assert r.goal_ok is False
    assert r.confidence == 0.0


def test_install_capability_actually_installs(reg):
    # datetime is a builtin — publish to index not required for install after import
    rm = reg.get("bones", "registry_manager")
    assert rm is not None
    result = rm.call("registry_manager.install_capability", cap_id="datetime", identity_id="bones")
    assert result.success is True
    assert result.goal_ok is True
    assert result.data["status"] == "installed"
    assert reg.get("bones", "datetime") is not None


def test_install_without_identity_fails(reg):
    rm = reg.get("bones", "registry_manager")
    # Clear bound identity to simulate unbound call
    rm._identity_id = ""  # type: ignore[attr-defined]
    result = rm.call("registry_manager.install_capability", cap_id="datetime", identity_id="")
    assert result.success is False
    assert result.goal_ok is False


def test_extract_cap_id_rejects_english_debris():
    assert TaskPlannerCapability._extract_cap_id("wonderful since you have all the skill") is None
    assert TaskPlannerCapability._extract_cap_id("create that and install it") is None
    assert TaskPlannerCapability._extract_cap_id(
        "create capability string_reverse that reverses text"
    ) == "string_reverse"
    assert TaskPlannerCapability._extract_cap_id(
        "create a capability called 'alpha_util'"
    ) == "alpha_util"


def test_acquire_before_invent_prefers_web():
    plan = TaskPlannerCapability._generate_plan(
        "create an internet_explorer capability to browse the web, publish and install it",
        identity_id="bones",
    )
    actions = [s["action"] for s in plan]
    assert "create_and_deploy" not in actions
    assert "install_capability" in actions
    install = next(s for s in plan if s["action"] == "install_capability")
    assert install["params"]["cap_id"] == "web"


def test_create_and_deploy_roundtrip(reg, tmp_path):
    rm = reg.get("bones", "registry_manager")
    cap_id = "string_reverse_gate"
    # Clean any leftover from prior runs
    cap_dir = Path(__file__).resolve().parents[1] / "core" / "capabilities" / cap_id
    if cap_dir.exists():
        shutil.rmtree(cap_dir)

    result = rm.call(
        "registry_manager.create_and_deploy",
        cap_id=cap_id,
        skill_kind="reverse",
        skill_short="reverse",
        identity_id="bones",
        probe_text="abc",
    )
    assert result.success is True, result.data
    assert result.goal_ok is True, result.data
    assert result.data["status"] == "deployed"
    assert reg.get("bones", cap_id) is not None

    probe = reg.call("bones", f"{cap_id}.reverse", text="abc")
    assert probe.success is True
    assert probe.data["reversed"] == "cba"

    # Cleanup generated capability + registry entry
    if cap_dir.exists():
        shutil.rmtree(cap_dir)
    idx_path = Path(__file__).resolve().parents[1] / "registry" / "index.json"
    index = json.loads(idx_path.read_text())
    index["capabilities"] = [c for c in index["capabilities"] if c.get("id") != cap_id]
    idx_path.write_text(json.dumps(index, indent=2) + "\n")


def test_inventory_lists_installed_and_gaps(reg):
    reg.install("bones", "datetime")
    rm = reg.get("bones", "registry_manager")
    result = rm.call("registry_manager.inventory", identity_id="bones")
    assert result.success is True
    assert "datetime" in result.data["installed_ids"]
    assert "registry_manager" in result.data["installed_ids"]
    assert isinstance(result.data["available_not_installed"], list)
