"""
core/migrations/handlers.py - Concrete migration handlers.

Each migration is a subclass of ``Migration`` with a unique ``id``,
``source_version``, ``target_version``, and ``run()`` implementation.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, TYPE_CHECKING

from .registry import Migration, MigrationRegistry

if TYPE_CHECKING:
    from runtime.persistence import StorageBackend

logger = logging.getLogger(__name__)


class Migration001AddSchemaVersion(Migration):
    """
    Ensures every persisted blob carries a ``schema_version`` field.

    This migration marks the transition from an unversioned schema (no
    schema_version field) to a versioned one.  It is a no-op on blobs
    that already have a schema_version.
    """

    id = "001-add-schema-version"
    description = "Add schema_version field to all persisted blobs"
    source_version = "0.0.0"
    target_version = "0.1.0"

    def run(
        self,
        data: Dict[str, Any],
        identity_id: str,
        namespace: str,
        storage: Optional["StorageBackend"] = None,
    ) -> Dict[str, Any]:
        if "schema_version" not in data:
            data["schema_version"] = "0.1.0"
            logger.debug("  Added schema_version=0.1.0 to %s/%s", identity_id, namespace)
        return data


def register_core_migrations(registry: MigrationRegistry) -> None:
    """Register all built-in migrations into *registry*."""
    registry.register(Migration001AddSchemaVersion())
