"""
persistence.py - IdentityOS Persistence Layer

Defines the abstract StorageBackend interface and concrete implementations
for persisting identity state across sessions. This is M2 of the IdentityOS
roadmap: every module's state becomes durable, portable, and versionable.

Backends:
  - InMemoryBackend  : process-local, explicitly non-durable storage
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
import copy
import hashlib
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

    def delete_user_memories(self, identity_id: str, user_id: str) -> int:
        """Delete one user's memories while retaining other users and shared state."""
        return 0

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
# In-memory backend
# ---------------------------------------------------------------------------

class InMemoryBackend(StorageBackend):
    """Process-local storage for explicitly non-persistent runtimes and tests."""

    def __init__(self) -> None:
        self._data: dict[str, dict[str, dict[str, Any]]] = {}
        self._memories: dict[str, list[dict[str, Any]]] = {}

    def save(self, identity_id: str, namespace: str, data: dict[str, Any]) -> None:
        self._data.setdefault(identity_id, {})[namespace] = copy.deepcopy(data)

    def load(self, identity_id: str, namespace: str) -> Optional[dict[str, Any]]:
        data = self._data.get(identity_id, {}).get(namespace)
        return copy.deepcopy(data) if data is not None else None

    def list_namespaces(self, identity_id: str) -> list[str]:
        return sorted(self._data.get(identity_id, {}))

    def delete(self, identity_id: str, namespace: str) -> None:
        self._data.get(identity_id, {}).pop(namespace, None)

    def list_identities(self) -> list[str]:
        return sorted(set(self._data) | set(self._memories))

    def save_memory(self, identity_id: str, memory: dict[str, Any]) -> None:
        self._memories.setdefault(identity_id, []).append(copy.deepcopy(memory))

    def load_memories(self, identity_id: str) -> list[dict[str, Any]]:
        return copy.deepcopy(self._memories.get(identity_id, []))

    def delete_memories(self, identity_id: str) -> None:
        self._memories.pop(identity_id, None)

    def delete_user_memories(self, identity_id: str, user_id: str) -> int:
        memories = self._memories.get(identity_id, [])
        kept = [memory for memory in memories if memory.get("user_id", identity_id) != user_id]
        deleted = len(memories) - len(kept)
        self._memories[identity_id] = kept
        return deleted


# ---------------------------------------------------------------------------
# JSON file backend
# ---------------------------------------------------------------------------

class JSONFileBackend(StorageBackend):
    """
    Stores identities and namespaces under fixed-alphabet SHA-256 keys.

    Caller-provided identifiers are retained inside metadata envelopes, never
    interpolated into filesystem paths. Existing human-readable v1 directories
    remain readable so the security boundary does not strand persisted state.

    Suitable for local development and single-node deployments.
    Atomic writes via a tmp-file + rename pattern.
    """

    def __init__(self, root_dir: str = ".identity_store") -> None:
        self.root = Path(root_dir).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _validate_key(value: str, *, label: str) -> str:
        if not isinstance(value, str) or not value or len(value) > 1_024 or "\x00" in value:
            raise ValueError(f"Invalid {label}")
        if "/" in value or "\\" in value or value in {".", ".."}:
            raise ValueError(f"Invalid {label}: path separators are not allowed")
        return value

    @staticmethod
    def _storage_key(value: str, *, prefix: str) -> str:
        digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
        return f"{prefix}-{digest}"

    @staticmethod
    def _write_json(path: Path, data: Any) -> None:
        tmp = path.parent / f".{path.name}.{uuid.uuid4().hex}.tmp"
        try:
            with tmp.open("x", encoding="utf-8") as handle:
                handle.write(json.dumps(data, indent=2, default=str))
            tmp.replace(path)
        finally:
            if tmp.exists():
                tmp.unlink()

    @staticmethod
    def _confined_child(directory: Path, filename: str) -> Path:
        path = directory / filename
        if path.exists() or path.is_symlink():
            resolved = path.resolve()
            if resolved.parent != directory:
                raise ValueError("Persisted path escapes its storage directory")
        return path

    def _identity_dir(self, identity_id: str, *, create: bool = False) -> Path:
        identity_id = self._validate_key(identity_id, label="identity_id")
        id_dir = self.root / self._storage_key(identity_id, prefix="identity")
        if id_dir.exists() or id_dir.is_symlink():
            resolved = id_dir.resolve()
            if resolved.parent != self.root or not resolved.is_dir():
                raise ValueError("Persisted identity path escapes storage root")
            id_dir = resolved
        if create:
            id_dir.mkdir(parents=True, exist_ok=True)
            metadata_path = self._confined_child(id_dir, "__identity__.json")
            if metadata_path.exists():
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                if metadata.get("identity_id") != identity_id:
                    raise ValueError("Identity storage-key collision")
            else:
                self._write_json(metadata_path, {"format": "identityos-json-v2", "identity_id": identity_id})
        return id_dir

    def _legacy_identity_dir(self, identity_id: str) -> Optional[Path]:
        identity_id = self._validate_key(identity_id, label="identity_id")
        if not self.root.exists():
            return None
        for candidate in self.root.iterdir():
            if not candidate.is_dir() or candidate.name != identity_id:
                continue
            if (candidate / "__identity__.json").exists():
                continue
            resolved = candidate.resolve()
            if resolved.parent == self.root:
                return resolved
        return None

    def _identity_dirs(self, identity_id: str) -> list[Path]:
        directories: list[Path] = []
        legacy = self._legacy_identity_dir(identity_id)
        if legacy is not None:
            directories.append(legacy)
        current = self._identity_dir(identity_id)
        if current.is_dir() and current not in directories:
            directories.append(current)
        return directories

    def _ns_path(self, identity_id: str, namespace: str, *, create: bool = False) -> Path:
        namespace = self._validate_key(namespace, label="namespace")
        id_dir = self._identity_dir(identity_id, create=create)
        filename = self._storage_key(namespace, prefix="namespace") + ".json"
        return self._confined_child(id_dir, filename)

    def _legacy_ns_path(self, identity_id: str, namespace: str) -> Optional[Path]:
        namespace = self._validate_key(namespace, label="namespace")
        legacy_dir = self._legacy_identity_dir(identity_id)
        if legacy_dir is None:
            return None
        for candidate in legacy_dir.glob("*.json"):
            if candidate.name in {"__identity__.json", "__memories__.json"}:
                continue
            if candidate.stem.replace("__", ":") == namespace:
                return self._confined_child(legacy_dir, candidate.name)
        return None

    def save(self, identity_id: str, namespace: str, data: dict[str, Any]) -> None:
        path = self._ns_path(identity_id, namespace, create=True)
        envelope = {
            "format": "identityos-json-v2",
            "namespace": namespace,
            "data": data,
        }
        self._write_json(path, envelope)

    def load(self, identity_id: str, namespace: str) -> Optional[dict[str, Any]]:
        path = self._ns_path(identity_id, namespace)
        if path.exists():
            envelope = json.loads(path.read_text(encoding="utf-8"))
            if (
                envelope.get("format") != "identityos-json-v2"
                or envelope.get("namespace") != namespace
                or not isinstance(envelope.get("data"), dict)
            ):
                raise ValueError(f"Invalid persisted namespace envelope: {namespace}")
            return envelope["data"]
        legacy_path = self._legacy_ns_path(identity_id, namespace)
        if legacy_path is None:
            return None
        return json.loads(legacy_path.read_text(encoding="utf-8"))

    def list_namespaces(self, identity_id: str) -> list[str]:
        namespaces: set[str] = set()
        current = self._identity_dir(identity_id)
        if current.is_dir():
            for candidate in current.glob("namespace-*.json"):
                candidate = self._confined_child(current, candidate.name)
                envelope = json.loads(candidate.read_text(encoding="utf-8"))
                namespace = envelope.get("namespace")
                if envelope.get("format") != "identityos-json-v2" or not isinstance(namespace, str):
                    raise ValueError(f"Invalid persisted namespace envelope: {candidate.name}")
                namespaces.add(namespace)
        legacy = self._legacy_identity_dir(identity_id)
        if legacy is not None:
            for candidate in legacy.glob("*.json"):
                if candidate.name not in {"__identity__.json", "__memories__.json"}:
                    namespaces.add(candidate.stem.replace("__", ":"))
        return sorted(namespaces)

    def delete(self, identity_id: str, namespace: str) -> None:
        path = self._ns_path(identity_id, namespace)
        if path.exists():
            path.unlink()
        legacy_path = self._legacy_ns_path(identity_id, namespace)
        if legacy_path is not None and legacy_path.exists():
            legacy_path.unlink()

    def list_identities(self) -> list[str]:
        if not self.root.exists():
            return []
        identities: set[str] = set()
        for directory in self.root.iterdir():
            if not directory.is_dir() or directory.name.startswith("."):
                continue
            directory = directory.resolve()
            if directory.parent != self.root:
                raise ValueError("Persisted identity path escapes storage root")
            metadata_path = self._confined_child(directory, "__identity__.json")
            if metadata_path.exists():
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                identity_id = metadata.get("identity_id")
                if not isinstance(identity_id, str):
                    raise ValueError(f"Invalid identity metadata: {directory.name}")
                identities.add(identity_id)
            else:
                identities.add(directory.name)
        return sorted(identities)

    # ------------------------------------------------------------------
    # Memory persistence — stored as a single JSON file per identity
    # ------------------------------------------------------------------

    def _memories_path(self, identity_id: str, *, create: bool = False) -> Path:
        directory = self._identity_dir(identity_id, create=create)
        return self._confined_child(directory, "__memories__.json")

    def _memory_paths(self, identity_id: str) -> list[Path]:
        return [self._confined_child(directory, "__memories__.json")
                for directory in self._identity_dirs(identity_id)]

    def save_memory(self, identity_id: str, memory: dict[str, Any]) -> None:
        path = self._memories_path(identity_id, create=True)
        memories: list[dict[str, Any]] = []
        if path.exists():
            memories = json.loads(path.read_text(encoding="utf-8"))
        memories.append(memory)
        self._write_json(path, memories)

    def load_memories(self, identity_id: str) -> list[dict[str, Any]]:
        memories: list[dict[str, Any]] = []
        for path in self._memory_paths(identity_id):
            if path.exists():
                memories.extend(json.loads(path.read_text(encoding="utf-8")))
        return memories

    def delete_memories(self, identity_id: str) -> None:
        for path in self._memory_paths(identity_id):
            if path.exists():
                path.unlink()

    def delete_user_memories(self, identity_id: str, user_id: str) -> int:
        deleted = 0
        for path in self._memory_paths(identity_id):
            if not path.exists():
                continue
            memories = json.loads(path.read_text(encoding="utf-8"))
            kept = [memory for memory in memories if memory.get("user_id", identity_id) != user_id]
            path_deleted = len(memories) - len(kept)
            if path_deleted:
                self._write_json(path, kept)
                deleted += path_deleted
        return deleted


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
