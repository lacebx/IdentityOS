# IdentityOS Roadmap

**Last updated:** 2026-08-29

IdentityOS is evolving toward persistent identities, portable capabilities,
truthful execution, durable long-running tasks, evidence-backed memory, model
independence, and cross-session continuity.

The runtime is functional, but the North Star is not complete. A passing model
response is never treated as execution evidence; each milestone below requires
runtime-observed behavior and regression tests.

## Current Evidence

| North Star property | Current runtime evidence | Remaining gap |
|---|---|---|
| Persistent identities | JSON and SQLite backends, snapshots, migrations, restart tests | Crash-safe background state commits and broader migration fixtures |
| Portable capabilities | Installable capability registry, typed skill contracts, centralized invocation gateway | Full generate-to-reuse conformance suite for arbitrary third-party packs |
| Truthful execution | Structured capability results, evidence footers, failure diagnostics, hermetic validation gates | Standard evidence receipts across every adapter and external integration |
| Durable long-running tasks | Persisted Executive tasks, checkpoints, recovery, retry policy, reconciliation for uncertain side effects | Provider-level idempotency keys and automated reconciliation where external APIs support them |
| Evidence-backed memory | User-scoped profiles/memories, contradiction evidence, restart recall, generic holdout extraction | Retention policy, provenance queries, and multi-process conflict resolution |
| Model independence | Provider adapters and model-neutral runtime contracts | Repeatable conformance runs across local and hosted model families |
| Cross-session continuity | Stable user IDs across sessions/apps with isolation tests | Production multi-device synchronization and conflict handling |
| Responsive interaction | Per-stage latency measurements and one-time recovery | Move nonessential evaluation/evolution work behind a durable background boundary |

## Milestone 1: Runtime Truth Foundation — Complete on This Branch

- Hermetic default test suite; network tests are explicitly marked.
- CI and benchmark scripts preserve failing exit codes.
- Capability calls use one validation, authorization, execution, and evidence path.
- Filesystem and command capabilities enforce workspace and subprocess boundaries.
- JSON persistence derives filesystem keys from fixed-alphabet digests and can read the legacy human-readable layout.
- User facts, memories, relationships, timelines, and sessions are scoped separately from identity state.
- Interrupted non-idempotent task steps stop for evidence-based reconciliation rather than replaying blindly.
- Event subscriber and optional-subsystem failures produce structured diagnostics.
- Interaction responses expose measured stage timings.
- User fact extraction and recall use general field matching with unseen holdout tests rather than frozen-prompt branches.

This milestone is complete only when its executable validation gates remain
green after integration with `main`.

## Milestone 2: Durable Background Boundary — Active

**Goal:** ordinary conversation must not wait for unrelated evolution or
maintenance work.

- Add a persisted work journal for post-response evaluation, learning, and maintenance.
- Make journal items independently retryable and observable.
- Preserve read-your-writes semantics for facts explicitly disclosed in the current turn.
- Add crash/restart tests at every journal transition.
- Establish latency budgets for policy, context, model, tool, and state-commit stages.

## Milestone 3: Capability Lifecycle Conformance — Next

**Goal:** demonstrate the complete lifecycle for arbitrary capability packs.

```text
generate -> validate -> publish -> install -> activate -> invoke
         -> observe -> verify -> persist -> restart -> reuse
```

- Publish a capability conformance harness with representative success and failure fixtures.
- Require declared permissions, input schemas, effect classification, and replay policy.
- Add signed package metadata and dependency verification.
- Record durable invocation receipts that can be queried by task and identity.
- Validate third-party packs without weakening execution boundaries.

## Milestone 4: Continuity and Provenance — Next

- Define retention, deletion, export, and merge semantics for user-scoped state.
- Expose fact and memory provenance through SDK and REST APIs.
- Add deterministic conflict resolution for concurrent devices/processes.
- Test identity upgrades without mixing user, identity, episodic, and execution state.
- Prove portable export/import with multiple users and capability receipts.

## Milestone 5: Ecosystem Validation — Planned

- Run the same conformance suite against CLI, SDK, REST, browser, and Discord surfaces.
- Publish cross-model compatibility results with environment metadata.
- Expand IdentityBench as an observability system with causes and actionable follow-up.
- Establish third-party governance and compatibility policy only after the runtime contracts stabilize through real applications.

## Definition of North Star Done

The North Star is reached when a fresh identity can:

```text
understand -> decide -> acquire capability -> execute -> observe reality
           -> learn -> persist -> restart -> continue
```

and the repository can prove each transition using runtime evidence, including
failure, recovery, persistence, and reuse. Model claims, successful imports,
and green unit tests alone are insufficient.

## Validation Gates

```bash
# Hermetic default suite
python -m pytest -q

# Explicit external integration suite
python -m pytest -q -m network

# Frozen benchmark integrity and report regeneration
python benchmarks/runner.py --report-only
```

Generated runs under `benchmarks/results/` are local and gitignored. Frozen
baseline/treatment summaries and experiment decisions are the reviewed,
version-controlled evidence.

## How to Contribute

See [CONTRIBUTING.md](../CONTRIBUTING.md). Keep changes focused, include
executable evidence, preserve failures honestly, and document meaningful
architectural changes.
