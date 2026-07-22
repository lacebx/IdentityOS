"""
core/migrations/manager.py - MigrationManager orchestrates data migration.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from .registry import MigrationRegistry, CURRENT_SCHEMA_VERSION, version_compare

if TYPE_CHECKING:
    from runtime.persistence import StorageBackend

logger = logging.getLogger(__name__)


class MigrationManager:
    """
    Orchestrates running pending migrations on persisted identity data.

    Usage:
        manager = MigrationManager(registry, storage)
        manager.migrate_identity("testbot")  # migrate a single identity
        manager.migrate_all()                # migrate all identities
    """

    def __init__(
        self,
        registry: MigrationRegistry,
        storage: Optional["StorageBackend"] = None,
    ) -> None:
        self._registry = registry
        self._storage = storage

    def get_data_version(self, data: Dict[str, Any]) -> str:
        """Extract schema_version from a data blob, defaulting to '0.0.0'."""
        return data.get("schema_version", "0.0.0")

    def set_data_version(self, data: Dict[str, Any], version: str) -> None:
        data["schema_version"] = version

    def migrate_blob(
        self,
        data: Dict[str, Any],
        identity_id: str,
        namespace: str = "identity_spec",
    ) -> Dict[str, Any]:
        """
        Run all pending migrations on a single data blob.
        Returns the migrated data (modifies in place).
        """
        current_version = self.get_data_version(data)
        pending = self._registry.get_pending(current_version)

        if not pending:
            return data

        logger.info(
            "Migrating %s/%s from %s through %d migration(s)",
            identity_id, namespace, current_version, len(pending),
        )

        for migration in pending:
            logger.debug(
                "  Applying %s (%s → %s): %s",
                migration.id, migration.source_version,
                migration.target_version, migration.description,
            )
            try:
                data = migration.run(
                    data=data,
                    identity_id=identity_id,
                    namespace=namespace,
                    storage=self._storage,
                )
                self.set_data_version(data, migration.target_version)
            except Exception:
                logger.exception(
                    "Migration %s failed for %s/%s",
                    migration.id, identity_id, namespace,
                )
                raise

        # Ensure final version is set
        if version_compare(self.get_data_version(data), CURRENT_SCHEMA_VERSION) < 0:
            self.set_data_version(data, CURRENT_SCHEMA_VERSION)

        return data

    def migrate_namespace(
        self,
        identity_id: str,
        namespace: str,
    ) -> Optional[Dict[str, Any]]:
        """Load, migrate, and save a single namespace blob for an identity."""
        if not self._storage:
            return None

        data = self._storage.load(identity_id, namespace)
        if data is None:
            return None

        migrated = self.migrate_blob(data, identity_id, namespace)
        if migrated is not data:  # was modified
            self._storage.save(identity_id, namespace, migrated)
        return migrated

    def migrate_identity(self, identity_id: str) -> int:
        """Migrate all namespaces for a single identity. Returns count of namespaces migrated."""
        if not self._storage:
            return 0

        namespaces = self._storage.list_namespaces(identity_id)
        count = 0
        for ns in namespaces:
            try:
                result = self.migrate_namespace(identity_id, ns)
                if result is not None:
                    count += 1
            except Exception:
                logger.exception("Failed to migrate %s/%s", identity_id, ns)
        return count

    def migrate_all(self) -> int:
        """Migrate all identities. Returns total count of namespaces migrated."""
        if not self._storage:
            return 0

        ids = self._storage.list_identities()
        total = 0
        for identity_id in ids:
            total += self.migrate_identity(identity_id)
        return total

    def migrate_blob_in_place(
        self,
        data: Dict[str, Any],
        identity_id: str = "__runtime__",
        namespace: str = "runtime",
    ) -> Dict[str, Any]:
        """Convenience: migrate a blob without storage interaction."""
        return self.migrate_blob(data, identity_id, namespace)
