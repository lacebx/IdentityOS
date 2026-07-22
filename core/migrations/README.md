# Migration Framework

**Path:** `core/migrations/`

## Overview

The migration framework upgrades persisted identity data across schema versions. When loading data from storage, the `MigrationManager` detects pending migrations and applies them automatically.

## Components

- **`registry.py`** — `Migration` base class + `MigrationRegistry` for version-tracked ordered migrations
- **`manager.py`** — `MigrationManager` that orchestrates running pending migrations per identity/namespace
- **`handlers.py`** — Concrete migration implementations (registered via `register_core_migrations()`)

## Schema Versioning

Every persisted blob carries a `schema_version` field (semver). Data without this field defaults to `"0.0.0"`. The `CURRENT_SCHEMA_VERSION` in `registry.py` defines the target version.

## Adding a Migration

1. Create a subclass of `Migration` in `handlers.py`
2. Set `id`, `description`, `source_version`, `target_version`
3. Implement `run()` to transform the data dict
4. Register in `register_core_migrations()`

## Integration

- Wired into `IdentityRuntime.load()` and `load_persisted()` in orchestrator
- Migration runs before `IdentitySpec.from_dict()` deserialization
- Logs at INFO level for each migration applied
