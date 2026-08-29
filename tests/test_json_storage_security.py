"""Security boundaries for the local JSON persistence backend."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import pytest

from runtime.persistence import JSONFileBackend


@pytest.mark.parametrize(
    "operation",
    [
        lambda backend, identity_id: backend.save(identity_id, "latest", {"ok": True}),
        lambda backend, identity_id: backend.load(identity_id, "latest"),
        lambda backend, identity_id: backend.list_namespaces(identity_id),
        lambda backend, identity_id: backend.delete(identity_id, "latest"),
        lambda backend, identity_id: backend.save_memory(identity_id, {"text": "secret"}),
        lambda backend, identity_id: backend.load_memories(identity_id),
        lambda backend, identity_id: backend.delete_memories(identity_id),
    ],
)
@pytest.mark.parametrize("identity_id", ["../escaped", "nested/escaped", "nested\\escaped", ".."])
def test_identity_id_cannot_escape_storage_root(
    tmp_path: Path,
    operation: Callable[[JSONFileBackend, str], object],
    identity_id: str,
) -> None:
    backend = JSONFileBackend(root_dir=str(tmp_path / "store"))

    with pytest.raises(ValueError, match="identity_id"):
        operation(backend, identity_id)

    assert not (tmp_path / "escaped").exists()


@pytest.mark.parametrize("namespace", ["../escaped", "nested/escaped", "nested\\escaped", ".."])
def test_namespace_cannot_escape_identity_directory(tmp_path: Path, namespace: str) -> None:
    backend = JSONFileBackend(root_dir=str(tmp_path / "store"))

    with pytest.raises(ValueError, match="namespace"):
        backend.save("safe-identity", namespace, {"ok": False})

    assert not (tmp_path / "escaped.json").exists()


def test_safe_json_storage_still_round_trips(tmp_path: Path) -> None:
    backend = JSONFileBackend(root_dir=str(tmp_path / "store"))
    backend.save("safe-identity", "snapshot:abc-123", {"ok": True})

    assert backend.load("safe-identity", "snapshot:abc-123") == {"ok": True}
    assert backend.list_namespaces("safe-identity") == ["snapshot:abc-123"]
    assert backend.list_identities() == ["safe-identity"]


def test_reading_missing_identity_has_no_filesystem_side_effect(tmp_path: Path) -> None:
    backend = JSONFileBackend(root_dir=str(tmp_path / "store"))

    assert backend.load("missing", "latest") is None
    assert not (tmp_path / "store" / "missing").exists()
