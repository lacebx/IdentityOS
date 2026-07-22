# Contributing to IdentityOS

IdentityOS is an open standard for portable, persistent AI identities. Contributions are welcome in all forms — code, documentation, design, testing, and community governance.

---

## Table of Contents

- [Architecture Decision Process](#architecture-decision-process)
- [How ADRs Work](#how-adrs-work)
- [How Amendments Work](#how-amendments-work)
- [How Migrations Work](#how-migrations-work)
- [Proposing Identity Laws](#proposing-identity-laws)
- [Code Standards](#code-standards)
- [Testing Expectations](#testing-expectations)
- [Documentation Expectations](#documentation-expectations)
- [Getting Started](#getting-started)

---

## Architecture Decision Process

Major architectural decisions are recorded as **Architecture Decision Records (ADRs)**.

### When to Write an ADR

- Adding a new subsystem or module
- Changing a core data model
- Introducing a new external dependency
- Changing the persistence format
- Modifying the identity lifecycle
- Any decision with significant cross-module impact

### ADR Process

1. **Draft** — Write an ADR in `docs/adr/ADR-NNN-title.md` using the template
2. **Discuss** — Open a PR with the ADR for community review
3. **Decide** — The architecture council (or maintainers) ratifies or rejects
4. **Implement** — Code changes follow the ratified ADR

### ADR Template

Each ADR contains:

- **Status** — Draft, Accepted, Rejected, Deprecated, Superseded
- **Context** — Why this decision is needed
- **Decision** — What was decided
- **Rationale** — Why this option was chosen
- **Consequences** — Trade-offs and implications
- **Compliance** — Where the decision is enforced in code

See existing ADRs in `docs/adr/` for examples.

---

## How Amendments Work

Amendments modify the IdentityOS Constitution or Laws. They are the governance mechanism for evolving the identity specification.

### Amendment Process

1. **Draft** — Use `docs/amendments/TEMPLATE.md` to create an amendment
2. **Submit** — Open a PR with the amendment
3. **Ratify** — Maintainers approve or reject
4. **Implement** — If migration is required, create a migration handler
5. **Record** — Update supersession links if replacing a prior amendment

### When to Write an Amendment

- Changing the core identity model (immutable fields, mutability rules)
- Adding or removing constitutional articles
- Modifying identity laws
- Any change that affects the constitution's governing principles

### Amendment Structure

Each amendment includes:

- Amendment ID (e.g., `AMEND-001`)
- Constitutional articles and laws affected
- Summary and motivation
- Detailed changes (constitutional and law-level)
- Impact assessment (backward compatibility, migration required, breaking changes)
- Migration plan
- Ratification record
- Supersession record

See `docs/amendments/AMEND-001` through `AMEND-003` for examples.

---

## How Migrations Work

Migrations upgrade persisted identity data from one schema version to another.

### Migration Framework

The migration framework lives in `core/migrations/` and provides:

- **`Migration`** — Base class with `id`, `source_version`, `target_version`, and `run()` method
- **`MigrationRegistry`** — Ordered collection of known migrations
- **`MigrationManager`** — Orchestrates running pending migrations on identity data

### Adding a Migration

1. Create a subclass of `Migration` in `core/migrations/handlers.py`
2. Set a unique `id`, `source_version`, `target_version`, and `description`
3. Implement `run()` to transform the data dict from source to target version
4. Register in `register_core_migrations()`

### Versioning

- Every persisted blob carries a `schema_version` field (semver)
- Data without `schema_version` defaults to `"0.0.0"`
- The current version is defined in `core/migrations/registry.py` as `CURRENT_SCHEMA_VERSION`

### Running Migrations

Migrations run automatically when identities are loaded:

- `IdentityRuntime.load()` — Migrates identity data before deserialization
- `IdentityRuntime.load_persisted()` — Calls `migrate_all()` before loading
- Individual blobs are migrated per-namespace

---

## Proposing Identity Laws

Identity Laws govern specific domains of identity behavior. Each law corresponds to a constitutional article.

### Current Laws

- `docs/laws/identity.md` — Identity core
- `docs/laws/memory.md` — Memory management
- `docs/laws/relationships.md` — Relationships
- `docs/laws/preferences.md` — Preferences
- `docs/laws/goals.md` — Goals
- `docs/laws/intentions.md` — Intentions
- `docs/laws/evidence.md` — Evidence
- `docs/laws/timeline.md` — Timeline
- `docs/laws/confidence.md` — Confidence
- `docs/laws/sessions.md` — Sessions

### Proposing a New Law

1. Create a new `.md` file in `docs/laws/`
2. Follow the existing law format (purpose, responsibilities, allowed mutations, conflict resolution, evidence requirements, lifecycle, examples, future extensions)
3. Submit as a PR with the corresponding constitutional amendment if needed

### Modifying an Existing Law

1. Either create an amendment (for significant changes) or submit a PR (for minor clarifications)
2. Update the law file with the proposed changes
3. Ensure the corresponding implementation is updated or create a follow-up issue

---

## Code Standards

### Python

- **Python 3.10+** — Use modern type annotations (`list[X]` not `List[X]`)
- **Type hints** — All public functions and methods must have type annotations
- **No comments** — Code should be self-documenting. Avoid inline comments
- **Docstrings** — Module-level docstrings required. Function docstrings for non-trivial logic
- **Imports** — Standard library first, then third-party, then local. Alphabetical within groups
- **Line length** — 100 characters maximum
- **Naming** — `snake_case` for functions/variables, `PascalCase` for classes, `UPPER_CASE` for constants

### Architecture

- **Separation of concerns** — Core modules (`core/`) contain domain logic. Runtime (`runtime/`) contains orchestration. Adapters (`adapters/`) contain LLM integration
- **No circular imports** — Core modules must not import from runtime
- **Minimal dependencies** — Prefer standard library over third-party packages
- **Serialization** — Every data object should support `to_dict()` and `from_dict()`

### Git

- **Branch naming** — `feature/description`, `fix/description`, `docs/description`
- **Commit messages** — Conventional commits: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`
- **PRs** — Link to issues, milestone, and related ADRs/amendments

---

## Testing Expectations

### Test Types

- **Unit tests** — Test individual modules in isolation. Located in `tests/`
- **Architecture tests** — Verify constitutional and law compliance. Located in `tests/architecture/`
- **Integration tests** — Test module interactions. Located in `tests/`
- **Behavioral tests** — Test LLM-dependent behavior (rename resistance, roleplay isolation). Documented in `VERIFICATION_REPORT.md`

### Requirements

- **All tests must pass** before merging
- **New features require tests** — Every new module, method, or behavior
- **Architecture tests verify governance** — Constitutional compliance is automated
- **Test coverage** — Aim for >80% on core modules

### Running Tests

```bash
# Run all tests
python -m pytest tests/

# Run specific test file
python -m pytest tests/test_identity.py

# Run architecture tests
python -m pytest tests/architecture/

# Run excluding LLM-dependent tests
python -m pytest tests/ --ignore=tests/test_behavioral.py
```

---

## Documentation Expectations

### Required Documentation

- **Every module** needs a module-level docstring explaining its purpose
- **Every public class** needs a class-level docstring
- **Every law** needs an implementation reference (where in code the law is enforced)
- **Every ADR** needs compliance references (where in code the decision is implemented)

### Documentation Structure

```
docs/
  constitution/         — Identity Constitution
  laws/                 — Identity Laws (10 domains)
  amendments/           — Amendment records
  adr/                  — Architecture Decision Records
  architecture/         — Architecture guides
  future/               — Future design documents
```

### README Files

Subsystem READMEs (in `core/*/README.md`) should explain:

- Purpose of the subsystem
- Key classes and their responsibilities
- How to use the subsystem
- How the subsystem integrates with other modules
- Testing approach

---

## Getting Started

### Prerequisites

- Python 3.10+
- Git

### Setup

```bash
git clone https://github.com/lacebx/IdentityOS.git
cd IdentityOS
pip install -r runtime/requirements.txt
```

### First Contribution Ideas

- Improve documentation
- Write tests for uncovered modules
- Fix a bug from the issue tracker
- Add a new example project
- Review an open PR

### Need Help?

- Open a [Discussion](https://github.com/lacebx/IdentityOS/discussions)
- Comment on a relevant issue
- Join the community (coming soon)

---

## License

By contributing, you agree that your contributions will be licensed under the MIT License. See [LICENSE](LICENSE) for details.
