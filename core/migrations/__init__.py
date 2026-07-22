"""
core/migrations - IdentityOS Migration Framework

Provides a formal mechanism for upgrading persisted identity data
across schema versions. Migrations are registered, ordered, and
run automatically when loading data from storage.

Schema versions follow semver (e.g. "0.0.0", "1.0.0").
Each migration transforms data from one version to the next.
"""

from .registry import Migration, MigrationRegistry, CURRENT_SCHEMA_VERSION, version_compare
from .manager import MigrationManager
from .handlers import register_core_migrations

__all__ = [
    "Migration",
    "MigrationRegistry",
    "MigrationManager",
    "CURRENT_SCHEMA_VERSION",
    "version_compare",
    "register_core_migrations",
]
