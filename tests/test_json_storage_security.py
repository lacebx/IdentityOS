"""Security boundaries for the local JSON persistence backend."""

from __future__ import annotations

import json
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
        lambda backend, identity_id: backend.delete_user_memories(identity_id, "user"),
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


@pytest.mark.parametrize(
    "operation",
    [
        lambda backend, namespace: backend.save("safe-identity", namespace, {"ok": False}),
        lambda backend, namespace: backend.load("safe-identity", namespace),
        lambda backend, namespace: backend.delete("safe-identity", namespace),
    ],
)
@pytest.mark.parametrize("namespace", ["../escaped", "nested/escaped", "nested\\escaped", ".."])
def test_namespace_cannot_escape_identity_directory(
    tmp_path: Path,
    operation: Callable[[JSONFileBackend, str], object],
    namespace: str,
) -> None:
    backend = JSONFileBackend(root_dir=str(tmp_path / "store"))

    with pytest.raises(ValueError, match="namespace"):
        operation(backend, namespace)

    assert not (tmp_path / "escaped.json").exists()


def test_safe_json_storage_still_round_trips(tmp_path: Path) -> None:
    backend = JSONFileBackend(root_dir=str(tmp_path / "store"))
    backend.save("safe-identity", "snapshot:abc-123", {"ok": True})

    assert backend.load("safe-identity", "snapshot:abc-123") == {"ok": True}
    assert backend.list_namespaces("safe-identity") == ["snapshot:abc-123"]
    assert backend.list_identities() == ["safe-identity"]

    identity_dir = next(path for path in (tmp_path / "store").iterdir() if path.is_dir())
    namespace_file = next(identity_dir.glob("namespace-*.json"))
    assert identity_dir.name.startswith("identity-")
    assert "safe-identity" not in identity_dir.name
    assert "snapshot" not in namespace_file.name


def test_legacy_human_readable_layout_remains_loadable(tmp_path: Path) -> None:
    root = tmp_path / "store"
    legacy_dir = root / "legacy-identity"
    legacy_dir.mkdir(parents=True)
    (legacy_dir / "snapshot__abc.json").write_text(
        json.dumps({"legacy": True}),
        encoding="utf-8",
    )
    (legacy_dir / "__memories__.json").write_text(
        json.dumps([{"text": "legacy memory"}]),
        encoding="utf-8",
    )
    backend = JSONFileBackend(root_dir=str(root))

    assert backend.load("legacy-identity", "snapshot:abc") == {"legacy": True}
    assert backend.load_memories("legacy-identity") == [{"text": "legacy memory"}]
    assert backend.list_namespaces("legacy-identity") == ["snapshot:abc"]
    assert backend.list_identities() == ["legacy-identity"]


def test_new_writes_overlay_legacy_state_without_hiding_it(tmp_path: Path) -> None:
    root = tmp_path / "store"
    legacy_dir = root / "legacy-identity"
    legacy_dir.mkdir(parents=True)
    (legacy_dir / "old.json").write_text(json.dumps({"version": 1}), encoding="utf-8")
    (legacy_dir / "__memories__.json").write_text(
        json.dumps([{"text": "old"}]),
        encoding="utf-8",
    )
    backend = JSONFileBackend(root_dir=str(root))

    backend.save("legacy-identity", "new", {"version": 2})
    backend.save_memory("legacy-identity", {"text": "new"})

    assert backend.load("legacy-identity", "old") == {"version": 1}
    assert backend.load("legacy-identity", "new") == {"version": 2}
    assert backend.list_namespaces("legacy-identity") == ["new", "old"]
    assert backend.list_identities() == ["legacy-identity"]
    assert backend.load_memories("legacy-identity") == [{"text": "old"}, {"text": "new"}]


def test_reading_missing_identity_has_no_filesystem_side_effect(tmp_path: Path) -> None:
    backend = JSONFileBackend(root_dir=str(tmp_path / "store"))

    assert backend.load("missing", "latest") is None
    assert not (tmp_path / "store" / "missing").exists()


def test_encoded_identity_symlink_cannot_redirect_writes(tmp_path: Path) -> None:
    backend = JSONFileBackend(root_dir=str(tmp_path / "store"))
    outside = tmp_path / "outside"
    outside.mkdir()
    encoded_dir = backend._identity_dir("victim")
    encoded_dir.symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError, match="escapes storage root"):
        backend.save("victim", "latest", {"secret": True})

    assert not list(outside.iterdir())


def test_encoded_namespace_symlink_cannot_redirect_reads(tmp_path: Path) -> None:
    backend = JSONFileBackend(root_dir=str(tmp_path / "store"))
    backend.save("victim", "latest", {"safe": True})
    namespace_path = backend._ns_path("victim", "latest")
    outside = tmp_path / "outside.json"
    outside.write_text(json.dumps({"secret": True}), encoding="utf-8")
    namespace_path.unlink()
    namespace_path.symlink_to(outside)

    with pytest.raises(ValueError, match="escapes its storage directory"):
        backend.load("victim", "latest")
