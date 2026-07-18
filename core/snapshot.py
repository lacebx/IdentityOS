"""
snapshot.py - Identity Snapshot & Version Control

Handles capturing, diffing, and restoring point-in-time snapshots of a
complete identity. Works with the persistence layer to enable:

  - Full identity checkpointing before risky operations
  - Rollback to any prior snapshot
  - Identity evolution audit trail
  - Diff comparison between snapshots (delta identity tracking)

This is the core of M3: Identity Evolution.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class IdentitySnapshot:
    """
    An immutable point-in-time record of an identity's complete state.
    """
    snapshot_id: str
    identity_id: str
    captured_at: float
    modules: dict[str, Any]
    label: str = ""
    schema_version: str = "1.0.0"
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "identity_id": self.identity_id,
            "captured_at": self.captured_at,
            "label": self.label,
            "schema_version": self.schema_version,
            "modules": self.modules,
            "meta": self.meta,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IdentitySnapshot":
        return cls(
            snapshot_id=data["snapshot_id"],
            identity_id=data["identity_id"],
            captured_at=data["captured_at"],
            label=data.get("label", ""),
            schema_version=data.get("schema_version", "1.0.0"),
            modules=data.get("modules", {}),
            meta=data.get("meta", {}),
        )

    def summary(self) -> str:
        ts = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(self.captured_at))
        label_part = f" [{self.label}]" if self.label else ""
        modules_listed = ", ".join(sorted(self.modules.keys()))
        return (
            f"Snapshot {self.snapshot_id[:8]}{label_part} "
            f"@ {ts} | modules: {modules_listed}"
        )


def _deep_diff(a: Any, b: Any, path: str = "") -> list[dict[str, Any]]:
    """
    Recursively compute a list of change records between two values.
    """
    changes: list[dict[str, Any]] = []
    if isinstance(a, dict) and isinstance(b, dict):
        all_keys = set(a) | set(b)
        for k in sorted(all_keys):
            child_path = f"{path}.{k}" if path else k
            if k not in a:
                changes.append({"path": child_path, "old": None, "new": b[k], "change": "added"})
            elif k not in b:
                changes.append({"path": child_path, "old": a[k], "new": None, "change": "removed"})
            else:
                changes.extend(_deep_diff(a[k], b[k], child_path))
    elif isinstance(a, list) and isinstance(b, list):
        if a != b:
            changes.append({"path": path, "old": a, "new": b, "change": "modified"})
    else:
        if a != b:
            changes.append({"path": path, "old": a, "new": b, "change": "modified"})
    return changes


def diff_snapshots(before: IdentitySnapshot, after: IdentitySnapshot) -> dict[str, Any]:
    """
    Return a structured diff between two snapshots.
    """
    changes = _deep_diff(before.modules, after.modules)
    return {
        "from_snapshot": before.snapshot_id,
        "to_snapshot": after.snapshot_id,
        "identity_id": before.identity_id,
        "elapsed_seconds": after.captured_at - before.captured_at,
        "change_count": len(changes),
        "changes": changes,
    }


class SnapshotManager:
    """
    Manages the full lifecycle of identity snapshots for one identity.

    Usage:
        manager = SnapshotManager(storage_backend, "mentor-01")
        snap_id = manager.capture({"identity": ..., "experience": ...})
        state   = manager.restore(snap_id)
        diff    = manager.diff(snap_id_a, snap_id_b)
    """

    INDEX_NS = "snapshots_index"

    def __init__(self, storage: Any, identity_id: str) -> None:
        self._storage = storage
        self._identity_id = identity_id

    def capture(
        self,
        modules: dict[str, Any],
        label: str = "",
        meta: Optional[dict[str, Any]] = None,
    ) -> str:
        """
        Persist the current module states as a new versioned snapshot.
        Returns the snapshot_id.
        """
        snap = IdentitySnapshot(
            snapshot_id=str(uuid.uuid4()),
            identity_id=self._identity_id,
            captured_at=time.time(),
            modules=modules,
            label=label,
            meta=meta or {},
        )
        self._storage.save(self._identity_id, f"snapshot:{snap.snapshot_id}", snap.to_dict())
        index = self._load_index()
        index.append(snap.snapshot_id)
        self._save_index(index)
        self._storage.save(self._identity_id, "latest_snapshot", snap.to_dict())
        return snap.snapshot_id

    def restore(self, snapshot_id: str) -> IdentitySnapshot:
        """Load and return a snapshot by id."""
        data = self._storage.load(self._identity_id, f"snapshot:{snapshot_id}")
        if data is None:
            raise KeyError(f"Snapshot '{snapshot_id}' not found.")
        return IdentitySnapshot.from_dict(data)

    def latest(self) -> Optional[IdentitySnapshot]:
        """Return the most recently captured snapshot, or None."""
        data = self._storage.load(self._identity_id, "latest_snapshot")
        return IdentitySnapshot.from_dict(data) if data else None

    def history(self) -> list[IdentitySnapshot]:
        """Return all snapshots in chronological order (oldest first)."""
        index = self._load_index()
        snapshots = []
        for sid in index:
            try:
                snapshots.append(self.restore(sid))
            except KeyError:
                pass
        return snapshots

    def diff(self, from_id: str, to_id: str) -> dict[str, Any]:
        """Compute a structured diff between two snapshots."""
        return diff_snapshots(self.restore(from_id), self.restore(to_id))

    def rollback(self, snapshot_id: str) -> IdentitySnapshot:
        """
        Non-destructive rollback: marks snapshot_id as latest without
        deleting newer snapshots. The orchestrator rehydrates from the return value.
        """
        snap = self.restore(snapshot_id)
        self._storage.save(self._identity_id, "latest_snapshot", snap.to_dict())
        return snap

    def prune(self, keep_last: int = 10) -> int:
        """Delete old snapshots, keeping only the most recent keep_last."""
        index = self._load_index()
        if len(index) <= keep_last:
            return 0
        to_delete = index[:-keep_last]
        for sid in to_delete:
            self._storage.delete(self._identity_id, f"snapshot:{sid}")
        self._save_index(index[-keep_last:])
        return len(to_delete)

    def _load_index(self) -> list[str]:
        data = self._storage.load(self._identity_id, self.INDEX_NS)
        return data.get("ids", []) if data else []

    def _save_index(self, ids: list[str]) -> None:
        self._storage.save(
            self._identity_id,
            self.INDEX_NS,
            {"ids": ids, "updated_at": time.time()},
        )
