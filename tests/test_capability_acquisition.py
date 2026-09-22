"""test_capability_acquisition.py — generic skill → capability acquisition.

Acquisition flows through the durable Executive lifecycle (the same path
Registry Manager uses): the gap adapter resolves which capability provides a
skill, then requests acquisition from the registered Executive provider.  It
never installs the capability directly and never claims success when no
Executive is registered.
"""

from __future__ import annotations

from core.acquisition import register_acquisition_provider, unregister_acquisition_provider
from core.capabilities.registry import CapabilityRegistry
from core.operations.executive_acquisition import (
    SKILL_PREFIX_PROVIDERS,
    build_gap_acquisition,
    provider_for,
)
from runtime.persistence import InMemoryBackend


class _FakeExecutive:
    """Minimal AcquisitionProvider double that records requests without executing."""

    def __init__(self) -> None:
        self.requests: list[tuple] = []
        self._created: dict[tuple[str, str], str] = {}

    def request_acquisition(
        self,
        identity_id: str,
        capability_id: str,
        goal: str,
        *,
        original_request: str | None = None,
        priority: int = 0,
        runtime: Any = None,
    ):
        """Faithful to ExecutiveRuntime.request_acquisition's durable contract:
        reuse the in-flight task for the same (identity, capability) and create
        nothing new; only a genuinely new durable task is recorded."""
        from types import SimpleNamespace

        key = (identity_id, capability_id)
        if key in self._created:
            task = SimpleNamespace(task_id=self._created[key], status="in_progress")
            return task, False
        task = SimpleNamespace(task_id=f"task-{len(self.requests)}", status="queued")
        self._created[key] = task.task_id
        self.requests.append((identity_id, capability_id, goal, original_request))
        return task, True


def _storage_and_registry():
    storage = InMemoryBackend()
    registry = CapabilityRegistry(storage)
    return storage, registry


def test_prefix_table_maps_every_interop_skill():
    assert ("mcp.", "mcp") in SKILL_PREFIX_PROVIDERS
    assert ("a2a.", "a2a") in SKILL_PREFIX_PROVIDERS
    assert ("culture_commons.", "culture_commons") in SKILL_PREFIX_PROVIDERS
    assert ("cc.", "culture_commons") in SKILL_PREFIX_PROVIDERS


def test_provider_for_resolves_capability_id():
    assert provider_for("mcp.discover") == "mcp"
    assert provider_for("mcp.call") == "mcp"
    assert provider_for("a2a.discover") == "a2a"
    assert provider_for("culture_commons.observe") == "culture_commons"
    assert provider_for("cc.observe") == "culture_commons"
    assert provider_for("mind.reading") is None


def test_acquire_routes_through_executive_provider():
    storage, registry = _storage_and_registry()
    executor = _FakeExecutive()
    register_acquisition_provider(storage, executor)
    try:
        acquire = build_gap_acquisition(storage, "aster", capability_registry=registry)
        ok, detail = acquire("mcp.discover")
        assert ok is True
        assert "acquisition task" in detail
        assert executor.requests == [("aster", "mcp", "Install and verify the mcp capability", "Install and verify the mcp capability")]
    finally:
        unregister_acquisition_provider(storage, executor)


def test_acquire_is_idempotent_per_capability():
    storage, registry = _storage_and_registry()
    executor = _FakeExecutive()
    register_acquisition_provider(storage, executor)
    try:
        acquire = build_gap_acquisition(storage, "aster", capability_registry=registry)
        first, _ = acquire("mcp.discover")
        second, detail = acquire("mcp.call")
        assert first is True and second is True
        assert "already in progress" in detail
        assert len(executor.requests) == 1, "second skill reuses the same capability task"
    finally:
        unregister_acquisition_provider(storage, executor)


def test_already_installed_capability_reports_installed():
    storage, registry = _storage_and_registry()
    registry.install("aster", "a2a")
    executor = _FakeExecutive()
    register_acquisition_provider(storage, executor)
    try:
        acquire = build_gap_acquisition(storage, "aster", capability_registry=registry)
        ok, detail = acquire("a2a.discover")
        assert ok is True
        assert "already installed" in detail
        assert executor.requests == [], "no acquisition task for an installed capability"
    finally:
        unregister_acquisition_provider(storage, executor)


def test_unknown_skill_is_honestly_unavailable():
    storage, _ = _storage_and_registry()
    acquire = build_gap_acquisition(storage, "aster")
    ok, detail = acquire("mind.reading")
    assert ok is False
    assert "no interop provider" in detail


def test_acquisition_without_executive_does_not_claim_success():
    storage, _ = _storage_and_registry()
    acquire = build_gap_acquisition(storage, "aster")
    ok, detail = acquire("mcp.discover")
    assert ok is False
    assert "no durable Executive registered" in detail


def test_gap_detection_routes_to_executive_through_build_aster_engine(tmp_path):
    """The operations engine's gap phase fills interop skills via the Executive."""
    from core.operations.aster import build_aster_config, build_aster_engine

    storage, registry = _storage_and_registry()
    executor = _FakeExecutive()
    register_acquisition_provider(storage, executor)
    try:
        engine = build_aster_engine(
            storage,
            project_root=tmp_path,
            capability_registry=registry,
            secret_store=None,
            register=False,
        )
        gaps = engine.gap_detector.check(build_aster_config(tmp_path).required_skills)
        interop_gaps = [g for g in gaps if g.required_skill in ("mcp.discover", "a2a.discover", "culture_commons.observe")]
        assert len(interop_gaps) == 3
        for gap in interop_gaps:
            engine.gap_detector.resolve(gap)
        submitted = {
            cap[1] for cap in executor.requests if cap[0] == "aster"
        }
        assert submitted == {"mcp", "a2a", "culture_commons"}
    finally:
        unregister_acquisition_provider(storage, executor)