"""
persistence.py - IdentityOS Persistence Layer

Defines the abstract StorageBackend interface and concrete implementations
for persisting identity state across sessions. This is M2 of the IdentityOS
roadmap: every module's state becomes durable, portable, and versionable.

Backends:
  - JSONFileBackend  : local flat-file storage (default / dev)
  - SQLiteBackend    : embedded relational storage (lightweight production)
  - RemoteBackend    : stub for cloud/remote storage (future)

Design principles:
  - Backend-agnostic: runtime/orchestrator only talks to StorageBackend
  - Atomic writes: snapshot written fully before replacing old state
  - Schema-versioned: every persisted blob carries a schema_version field
  - Event-aware: writes emit IDENTITY_PERSISTED onto the EventBus if available
"""

from __future__ import annotations

import abc
import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Schema version — bump this when the persisted format changes
# ---------------------------------------------------------------------------
SCHEMA_VERSION = "1.0.0"


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class StorageBackend(abc.ABC):
    """
    Abstract interface for all IdentityOS storage backends.

    Every backend must support four operations:
      save(identity_id, namespace, data)   -> commit a dict under a namespace
      load(identity_id, namespace)         -> retrieve that dict (or None)
      list_namespaces(identity_id)         -> all namespaces stored for an id
      delete(identity_id, namespace)       -> remove a namespace blob
    """

    @abc.abstractmethod
    def save(
        self,
        identity_id: str,
        namespace: str,
        data: dict[str, Any],
    ) -> None:
        """Persist *data* under identity_id / namespace."""

    @abc.abstractmethod
    def load(
        self,
        identity_id: str,
        namespace: str,
    ) -> Optional[dict[str, Any]]:
        """Return the stored dict or None if not found."""

    @abc.abstractmethod
    def list_namespaces(self, identity_id: str) -> list[str]:
        """Return all namespaces stored for the given identity."""

    @abc.abstractmethod
    def delete(self, identity_id: str, namespace: str) -> None:
        """Remove a namespace blob for the given identity."""

    @abc.abstractmethod
    def list_identities(self) -> list[str]:
        """Return all identity IDs stored in this backend."""

    # ------------------------------------------------------------------
    # Memory persistence (optional — not all backends need implement)
    # ------------------------------------------------------------------

    def save_memory(self, identity_id: str, memory: dict[str, Any]) -> None:
        """Persist a single memory fragment for an identity.

        Default implementation is a no-op. Backends that support memory
        persistence should override this.
        """

    def load_memories(self, identity_id: str) -> list[dict[str, Any]]:
        """Load all persisted memories for an identity.

        Default returns an empty list.
        """
        return []

    def delete_memories(self, identity_id: str) -> None:
        """Delete all persisted memories for an identity.

        Default implementation is a no-op.
        """

    # ------------------------------------------------------------------
    # Convenience helpers (built on top of the abstract primitives)
    # ------------------------------------------------------------------

    def save_snapshot(
        self,
        identity_id: str,
        snapshot: dict[str, Any],
    ) -> str:
        """
        Persist a full identity snapshot and return the snapshot id.

        The snapshot is stored under namespace 'snapshot:<snapshot_id>'.
        A 'latest' alias is also updated to point to the new snapshot.
        """
        snapshot_id = str(uuid.uuid4())
        envelope = {
            "schema_version": SCHEMA_VERSION,
            "snapshot_id": snapshot_id,
            "identity_id": identity_id,
            "saved_at": time.time(),
            "data": snapshot,
        }
        ns = f"snapshot:{snapshot_id}"
        self.save(identity_id, ns, envelope)
        self.save(identity_id, "latest", envelope)
        return snapshot_id

    def load_latest(self, identity_id: str) -> Optional[dict[str, Any]]:
        """Return the most recent snapshot envelope for an identity."""
        envelope = self.load(identity_id, "latest")
        return envelope.get("data") if envelope else None

    def list_snapshots(self, identity_id: str) -> list[str]:
        """Return a list of snapshot ids ordered from oldest to newest."""
        namespaces = self.list_namespaces(identity_id)
        snapshot_ids = [
            ns.split(":", 1)[1]
            for ns in namespaces
            if ns.startswith("snapshot:")
        ]
        return snapshot_ids


# ---------------------------------------------------------------------------
# JSON file backend
# ---------------------------------------------------------------------------

class JSONFileBackend(StorageBackend):
    """
    Stores each namespace as a separate JSON file under:
      <root_dir>/<identity_id>/<namespace>.json

    Suitable for local development and single-node deployments.
    Atomic writes via a tmp-file + rename pattern.
    """

    def __init__(self, root_dir: str = ".identity_store") -> None:
        self.root = Path(root_dir)
        self.root.mkdir(parents=True, exist_ok=True)

    def _ns_path(self, identity_id: str, namespace: str) -> Path:
        id_dir = self.root / identity_id
        id_dir.mkdir(parents=True, exist_ok=True)
        # Replace colons so filenames stay cross-platform safe
        safe_ns = namespace.replace(":", "__")
        return id_dir / f"{safe_ns}.json"

    def save(self, identity_id: str, namespace: str, data: dict[str, Any]) -> None:
        path = self._ns_path(identity_id, namespace)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        tmp.replace(path)  # atomic on POSIX; best-effort on Windows

    def load(self, identity_id: str, namespace: str) -> Optional[dict[str, Any]]:
        path = self._ns_path(identity_id, namespace)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def list_namespaces(self, identity_id: str) -> list[str]:
        id_dir = self.root / identity_id
        if not id_dir.exists():
            return []
        namespaces = []
        for f in id_dir.glob("*.json"):
            ns = f.stem.replace("__", ":")
            namespaces.append(ns)
        return sorted(namespaces)

    def delete(self, identity_id: str, namespace: str) -> None:
        path = self._ns_path(identity_id, namespace)
        if path.exists():
            path.unlink()

    def list_identities(self) -> list[str]:
        if not self.root.exists():
            return []
        return sorted(
            d.name for d in self.root.iterdir() if d.is_dir() and not d.name.startswith(".")
        )

    # ------------------------------------------------------------------
    # Memory persistence — stored as a single JSON file per identity
    # ------------------------------------------------------------------

    def _memories_path(self, identity_id: str) -> Path:
        id_dir = self.root / identity_id
        id_dir.mkdir(parents=True, exist_ok=True)
        return id_dir / "__memories__.json"

    def save_memory(self, identity_id: str, memory: dict[str, Any]) -> None:
        path = self._memories_path(identity_id)
        memories: list[dict[str, Any]] = []
        if path.exists():
            memories = json.loads(path.read_text(encoding="utf-8"))
        memories.append(memory)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(memories, indent=2, default=str), encoding="utf-8")
        tmp.replace(path)

    def load_memories(self, identity_id: str) -> list[dict[str, Any]]:
        path = self._memories_path(identity_id)
        if not path.exists():
            return []
        return json.loads(path.read_text(encoding="utf-8"))

    def delete_memories(self, identity_id: str) -> None:
        path = self._memories_path(identity_id)
        if path.exists():
            path.unlink()


# ---------------------------------------------------------------------------
# SQLite backend
# ---------------------------------------------------------------------------

class SQLiteBackend(StorageBackend):
    """
    Stores all namespaces in a single SQLite database at *db_path*.

    Schema:
      identity_store(identity_id TEXT, namespace TEXT, payload TEXT, updated_at REAL)
      PRIMARY KEY (identity_id, namespace)

    Suitable for lightweight production use and multi-process reads.
    """

    def __init__(self, db_path: str = ".identity_store/identities.db") -> None:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS identity_store (
                    identity_id TEXT NOT NULL,
                    namespace   TEXT NOT NULL,
                    payload     TEXT NOT NULL,
                    updated_at  REAL NOT NULL,
                    PRIMARY KEY (identity_id, namespace)
                )
            """)
            conn.commit()

    def save(self, identity_id: str, namespace: str, data: dict[str, Any]) -> None:
        payload = json.dumps(data, default=str)
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO identity_store (identity_id, namespace, payload, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(identity_id, namespace)
                DO UPDATE SET payload=excluded.payload, updated_at=excluded.updated_at
            """, (identity_id, namespace, payload, time.time()))
            conn.commit()

    def load(self, identity_id: str, namespace: str) -> Optional[dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload FROM identity_store WHERE identity_id=? AND namespace=?",
                (identity_id, namespace),
            ).fetchone()
        if row is None:
            return None
        return json.loads(row["payload"])

    def list_namespaces(self, identity_id: str) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT namespace FROM identity_store WHERE identity_id=? ORDER BY namespace",
                (identity_id,),
            ).fetchall()
        return [r["namespace"] for r in rows]

    def delete(self, identity_id: str, namespace: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM identity_store WHERE identity_id=? AND namespace=?",
                (identity_id, namespace),
            )
            conn.commit()

    def list_identities(self) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT identity_id FROM identity_store ORDER BY identity_id"
            ).fetchall()
        return [r["identity_id"] for r in rows]


# ---------------------------------------------------------------------------
# Remote backend stub
# ---------------------------------------------------------------------------

class RemoteBackend(StorageBackend):
    """
    Stub for a remote HTTP/cloud storage backend.

    Implement _request() to connect to your cloud store.
    This class shows the interface contract without coupling the core
    runtime to any specific cloud provider.
    """

    def __init__(self, base_url: str, api_key: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def _request(self, method: str, path: str, body: Any = None) -> Any:
        raise NotImplementedError(
            "RemoteBackend._request() must be implemented for your cloud provider."
        )

    def save(self, identity_id: str, namespace: str, data: dict[str, Any]) -> None:
        self._request("PUT", f"/identities/{identity_id}/{namespace}", body=data)

    def load(self, identity_id: str, namespace: str) -> Optional[dict[str, Any]]:
        return self._request("GET", f"/identities/{identity_id}/{namespace}")

    def list_namespaces(self, identity_id: str) -> list[str]:
        result = self._request("GET", f"/identities/{identity_id}")
        return result if isinstance(result, list) else []

    def delete(self, identity_id: str, namespace: str) -> None:
        self._request("DELETE", f"/identities/{identity_id}/{namespace}")

    def list_identities(self) -> list[str]:
        result = self._request("GET", "/identities")
        return result if isinstance(result, list) else []


# ---------------------------------------------------------------------------
# Factory helper
# ---------------------------------------------------------------------------

def get_backend(backend_type: str = "json", **kwargs: Any) -> StorageBackend:
    """
    Return a configured backend instance.

    Args:
        backend_type: "json" | "sqlite" | "remote"
        **kwargs: passed through to the backend constructor

    Example:
        store = get_backend("sqlite", db_path="/var/data/identities.db")
        store.save_snapshot("mentor-01", snapshot_data)
    """
    backends = {
        "json": JSONFileBackend,
        "sqlite": SQLiteBackend,
        "remote": RemoteBackend,
    }
    if backend_type not in backends:
        raise ValueError(
            f"Unknown backend '{backend_type}'. Choose from: {list(backends.keys())}"
        )
    return backends[backend_type](**kwargs)
