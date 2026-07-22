"""
core/migrations/registry.py - Migration class and version-tracked registry.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from runtime.persistence import StorageBackend


CURRENT_SCHEMA_VERSION = "1.0.0"


def version_compare(v1: str, v2: str) -> int:
    """Compare two semver strings. Returns -1, 0, or 1."""
    parts1 = [int(x) for x in v1.split(".")]
    parts2 = [int(x) for x in v2.split(".")]
    # Pad to equal length
    while len(parts1) < len(parts2):
        parts1.append(0)
    while len(parts2) < len(parts1):
        parts2.append(0)
    for a, b in zip(parts1, parts2):
        if a < b:
            return -1
        if a > b:
            return 1
    return 0


class Migration:
    """
    A single migration step that transforms persisted data from
    *source_version* to *target_version*.

    Subclasses must implement ``run()``.
    """

    id: str = ""
    description: str = ""
    source_version: str = ""
    target_version: str = ""

    def run(
        self,
        data: Dict[str, Any],
        identity_id: str,
        namespace: str,
        storage: Optional["StorageBackend"] = None,
    ) -> Dict[str, Any]:
        """Transform *data* from source_version to target_version.

        Args:
            data: The raw blob data to migrate (deserialized dict).
            identity_id: The identity this data belongs to.
            namespace: The storage namespace (e.g. 'identity_spec').
            storage: Optional storage backend for loading auxiliary data.

        Returns:
            The transformed data dict with schema_version bumped.
        """
        raise NotImplementedError


class MigrationRegistry:
    """Central registry of known migrations, ordered by version."""

    def __init__(self) -> None:
        self._migrations: Dict[str, Migration] = {}
        self._ordered: List[str] = []

    def register(self, migration: Migration) -> None:
        if migration.id in self._migrations:
            raise ValueError(f"Migration '{migration.id}' is already registered")
        if not migration.id:
            raise ValueError("Migration must have a non-empty 'id'")
        if not migration.source_version or not migration.target_version:
            raise ValueError(
                f"Migration '{migration.id}' must define source_version and target_version"
            )
        self._migrations[migration.id] = migration
        self._ordered.append(migration.id)

    def get(self, migration_id: str) -> Optional[Migration]:
        return self._migrations.get(migration_id)

    def get_pending(self, current_version: str) -> List[Migration]:
        """Return all migrations needed to reach CURRENT_SCHEMA_VERSION."""
        pending: List[Migration] = []
        for mid in self._ordered:
            m = self._migrations[mid]
            if version_compare(current_version, m.target_version) < 0:
                pending.append(m)
        return pending

    def all(self) -> List[Migration]:
        return [self._migrations[mid] for mid in self._ordered]

    def __len__(self) -> int:
        return len(self._migrations)
