"""Tests for core.snapshot module."""

from core.snapshot import (
    IdentitySnapshot,
    SnapshotManager,
    diff_snapshots,
)
from runtime.persistence import InMemoryBackend
import time


class TestIdentitySnapshot:
    def test_creation(self):
        snap = IdentitySnapshot(
            snapshot_id="snap-1",
            identity_id="test",
            captured_at=time.time(),
            modules={"identity": {"name": "Test"}},
            label="test",
        )
        assert snap.snapshot_id == "snap-1"
        assert snap.identity_id == "test"
        assert snap.label == "test"

    def test_to_dict(self):
        snap = IdentitySnapshot(
            snapshot_id="snap-1",
            identity_id="test",
            captured_at=1234567890.0,
            modules={"identity": {"name": "Test"}},
            label="test",
        )
        data = snap.to_dict()
        assert data["snapshot_id"] == "snap-1"
        assert data["identity_id"] == "test"
        assert data["captured_at"] == 1234567890.0
        assert data["label"] == "test"
        assert data["modules"]["identity"]["name"] == "Test"

    def test_from_dict(self):
        data = {
            "snapshot_id": "snap-1",
            "identity_id": "test",
            "captured_at": 1234567890.0,
            "label": "test",
            "schema_version": "1.0.0",
            "modules": {"identity": {"name": "Test"}},
            "meta": {},
        }
        snap = IdentitySnapshot.from_dict(data)
        assert snap.snapshot_id == "snap-1"
        assert snap.identity_id == "test"
        assert snap.captured_at == 1234567890.0

    def test_summary(self):
        snap = IdentitySnapshot(
            snapshot_id="snap-12345678",
            identity_id="test",
            captured_at=time.time(),
            modules={"identity": {}, "memory": {}},
            label="initial",
        )
        summary = snap.summary()
        assert "snap-123" in summary  # Truncated to 8 chars
        assert "[initial]" in summary


class TestDiffSnapshots:
    def test_added_key(self):
        before = IdentitySnapshot(snapshot_id="b", identity_id="test", captured_at=1.0, modules={"a": 1})
        after = IdentitySnapshot(snapshot_id="a", identity_id="test", captured_at=2.0, modules={"a": 1, "b": 2})
        diff = diff_snapshots(before, after)
        assert diff["change_count"] == 1
        assert diff["changes"][0]["change"] == "added"
        assert diff["changes"][0]["path"] == "b"

    def test_removed_key(self):
        before = IdentitySnapshot(snapshot_id="b", identity_id="test", captured_at=1.0, modules={"a": 1, "b": 2})
        after = IdentitySnapshot(snapshot_id="a", identity_id="test", captured_at=2.0, modules={"a": 1})
        diff = diff_snapshots(before, after)
        assert diff["change_count"] == 1
        assert diff["changes"][0]["change"] == "removed"
        assert diff["changes"][0]["path"] == "b"

    def test_modified_value(self):
        before = IdentitySnapshot(snapshot_id="b", identity_id="test", captured_at=1.0, modules={"a": 1})
        after = IdentitySnapshot(snapshot_id="a", identity_id="test", captured_at=2.0, modules={"a": 2})
        diff = diff_snapshots(before, after)
        assert diff["change_count"] == 1
        assert diff["changes"][0]["change"] == "modified"
        assert diff["changes"][0]["old"] == 1
        assert diff["changes"][0]["new"] == 2

    def test_nested_diff(self):
        before = IdentitySnapshot(snapshot_id="b", identity_id="test", captured_at=1.0, modules={"identity": {"name": "Old"}})
        after = IdentitySnapshot(snapshot_id="a", identity_id="test", captured_at=2.0, modules={"identity": {"name": "New"}})
        diff = diff_snapshots(before, after)
        assert diff["change_count"] == 1
        assert diff["changes"][0]["path"] == "identity.name"
        assert diff["changes"][0]["old"] == "Old"
        assert diff["changes"][0]["new"] == "New"

    def test_list_diff(self):
        before = IdentitySnapshot(snapshot_id="b", identity_id="test", captured_at=1.0, modules={"tags": ["a", "b"]})
        after = IdentitySnapshot(snapshot_id="a", identity_id="test", captured_at=2.0, modules={"tags": ["a", "c"]})
        diff = diff_snapshots(before, after)
        assert diff["change_count"] == 1
        assert diff["changes"][0]["change"] == "modified"


class TestSnapshotManager:
    def test_capture(self):
        storage = InMemoryBackend()
        manager = SnapshotManager(storage, "test-identity")
        modules = {"identity": {"name": "Test"}, "memory": {"entries": []}}
        snap_id = manager.capture(modules, label="initial")
        assert snap_id
        # Verify it was saved
        latest = storage.load("test-identity", "latest_snapshot")
        assert latest is not None
        assert latest["label"] == "initial"

    def test_restore(self):
        storage = InMemoryBackend()
        manager = SnapshotManager(storage, "test-identity")
        modules = {"identity": {"name": "Test"}}
        snap_id = manager.capture(modules, label="test")
        restored = manager.restore(snap_id)
        assert restored.snapshot_id == snap_id
        assert restored.modules["identity"]["name"] == "Test"

    def test_restore_missing(self):
        storage = InMemoryBackend()
        manager = SnapshotManager(storage, "test-identity")
        try:
            manager.restore("nonexistent")
            assert False, "Should have raised KeyError"
        except KeyError:
            pass

    def test_latest(self):
        storage = InMemoryBackend()
        manager = SnapshotManager(storage, "test-identity")
        assert manager.latest() is None
        manager.capture({"identity": {}}, label="first")
        latest = manager.latest()
        assert latest is not None
        assert latest.label == "first"

    def test_history(self):
        storage = InMemoryBackend()
        manager = SnapshotManager(storage, "test-identity")
        manager.capture({"identity": {}}, label="first")
        manager.capture({"identity": {}}, label="second")
        history = manager.history()
        assert len(history) == 2
        assert history[0].label == "first"
        assert history[1].label == "second"

    def test_diff(self):
        storage = InMemoryBackend()
        manager = SnapshotManager(storage, "test-identity")
        snap1_id = manager.capture({"identity": {"name": "Old"}}, label="v1")
        snap2_id = manager.capture({"identity": {"name": "New"}}, label="v2")
        diff = manager.diff(snap1_id, snap2_id)
        assert diff["change_count"] == 1
        assert diff["changes"][0]["path"] == "identity.name"
        assert diff["changes"][0]["old"] == "Old"
        assert diff["changes"][0]["new"] == "New"

    def test_rollback(self):
        storage = InMemoryBackend()
        manager = SnapshotManager(storage, "test-identity")
        snap1_id = manager.capture({"identity": {"name": "Old"}}, label="v1")
        manager.capture({"identity": {"name": "New"}}, label="v2")
        # Rollback to v1
        rolled_back = manager.rollback(snap1_id)
        assert rolled_back.snapshot_id == snap1_id
        # Latest should now be v1
        latest = manager.latest()
        assert latest.snapshot_id == snap1_id
        # v2 should still exist in history
        history = manager.history()
        assert len(history) == 2

    def test_prune(self):
        storage = InMemoryBackend()
        manager = SnapshotManager(storage, "test-identity")
        for i in range(15):
            manager.capture({"identity": {"v": i}}, label=f"v{i}")
        deleted = manager.prune(keep_last=10)
        assert deleted == 5
        history = manager.history()
        assert len(history) == 10