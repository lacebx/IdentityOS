# Prometheus — Autonomous Capability Evolution

## What Problem Does It Solve

IdentityOS starts with a fixed set of built-in capabilities. When a user asks the system
to do something that requires a capability it doesn't have, Prometheus detects the gap,
searches the capability registry, verifies trustworthiness, installs the capability,
retries the original task, evaluates the result, and remembers what it learned.

This enables the system to grow its abilities autonomously over time without human
intervention or code deploys.

## What It Owns

- **Gap detection** — identifying missing capabilities from user requests and LLM responses
- **Registry search** — discovering candidate capabilities from local or remote indexes
- **Trust evaluation** — scoring candidates by author reputation, version maturity, permissions
- **Installation** — safe install with rollback on failure
- **Validation** — verifying installed capabilities are functional
- **Retry** — re-invoking the original task with the newly acquired capability
- **Performance evaluation** — measuring whether the acquisition improved the outcome
- **Learning** — persisting success rates, task→capability mappings, and evidence history
- **Acquisition lifecycle** — tracking every acquisition attempt through a status state machine

## What It Does Not Own

- **LLM responses** — Prometheus observes outputs but does not generate or modify them
- **Policy enforcement** — governed by the PolicyEngine, not Prometheus
- **Identity lifecycle** — identities are managed by the runtime; Prometheus only queries them
- **Capability execution** — installed capabilities are invoked by the SkillRouter/Planner
- **Registry content** — the capability registry is maintained externally; Prometheus only reads it
- **User approval UX** — `APPROVAL_REQUIRED` mode gates on trust but does not implement UI

## Acquisition Lifecycle

```
User Input
    │
    ▼
[1] Need Detection (pre-check)
    │
    ├─ No gap → skip
    │
    └─ Gap detected → check if already installed
         │
         ├─ Already installed → skip
         │
         └─ Missing → evolve()
              │
              ▼
[2] Registry Search ─────────► No candidates → FAILED
    │
    ▼
[3] Candidate Ranking ───────► No suitable candidate → FAILED
    │
    ▼
[4] Trust Verification ──────► Below threshold → FAILED
    │                           (mode-dependent: AUTO, APPROVAL, READ_ONLY, ENTERPRISE)
    ▼
[5] Dependency Check ────────► Missing deps → FAILED
    │
    ▼
[6] Install ─────────────────► Install failed → ROLLED_BACK
    │
    ▼
[7] Validate ────────────────► Validation failed → ROLLED_BACK
    │
    ▼
[8] Retry Original Task ─────► Retry failed → FAILED
    │
    ▼
[9] Evaluate Performance ────► Record gain/loss
    │
    ▼
[10] Learn & Record Evidence ─► Persist for future reference
    │
    ▼
[11] Return Result
```

## Decision Lifecycle

Each acquisition attempt flows through a state machine defined by `AcquisitionStatus`:

```
NEED_DETECTED → SEARCHING → CANDIDATES_FOUND → TRUST_VERIFIED → INSTALLING
    → INSTALLED → VALIDATING → VALIDATED → RETRYING → SUCCEEDED
                                                        → FAILED
                                                        → ROLLED_BACK
```

Any stage can transition to FAILED. Install/Validate failures transition to ROLLED_BACK
(which calls `registry.uninstall()` to undo partial installations).

## Architecture

```
runtime/orchestrator.py
    │
    ├── __init__: self.prometheus = PrometheusEngine(registry, storage)
    │
    ├── process() Stage 2b: pre_check_and_evolve()
    │   │  (before context composition — install so context picks it up)
    │   │
    ├── process() Stage 4b: post_check_and_evolve()
    │   │  (after adapter response — detects gaps in LLM output)
    │   │
    └── [retry path]: runtime.process() re-enters pipeline but
                      _evolving guard prevents recursive evolution

core/prometheus/
    ├── __init__.py          — Public API exports
    ├── models.py            — Data models (dataclasses + enums)
    ├── engine.py            — PrometheusEngine (public entry point)
    ├── pipeline.py          — EvolutionPipeline (acquisition lifecycle)
    ├── ARCHITECTURE.md      — This file
    └── stages/
        ├── __init__.py          — Stage function exports
        ├── need_detector.py     — Keyword-based gap detection
        ├── registry_searcher.py — Registry index loading + relevance scoring
        ├── candidate_ranker.py  — Rank by relevance + author + version
        ├── trust_verifier.py    — Trust scoring by author/permissions/version
        ├── dependency_resolver.py — Missing dependency check
        ├── installer.py         — Safe install with rollback
        ├── validator.py         — Post-install validation
        ├── retry_handler.py     — Re-invoke runtime.process()
        ├── performance_evaluator.py — Before/after comparison
        ├── learner.py           — Persist success rates + mappings
        └── evidence_recorder.py — Persist acquisition evidence
```

## Safety Mechanisms

| Mechanism | Location | Description |
|-----------|----------|-------------|
| Re-entrancy guard | `engine.py` `_evolving` | Blocks recursive evolution during retry |
| Acquisition limit | `pipeline.py` `_interaction_acquisitions` | Caps acquisitions per interaction (default 1) |
| Already-installed check | `pipeline.py` + `searcher.py` | Skips if capability is already installed |
| Trust thresholds | `trust_verifier.py` | Mode-dependent minimum trust scores |
| Rollback on failure | `installer.py` + `pipeline.py` | Uninstalls on install or validation failure |
| Read-only mode | `engine.py` | `READ_ONLY` mode blocks all acquisition |

## Extension Points

### Stage Replacement

Each stage is a standalone function. Replace any by assigning a new function to
the corresponding attribute or by subclassing `EvolutionPipeline`:

```python
from core.prometheus.stages.registry_searcher import search_registry

def custom_searcher(need, max_candidates, installed_ids):
    # custom logic
    pass

import core.prometheus.stages.registry_searcher as searcher
searcher.search_registry = custom_searcher
```

### Registry Providers (future)

The `registry_searcher` currently loads from a local JSON index. To support remote
registries, replace `search_registry()` with a function that queries an HTTP API
while returning the same `List[RegistryCandidate]` type.

### Acquisition Modes

The `AcquisitionMode` enum supports AUTOMATIC, APPROVAL_REQUIRED, READ_ONLY,
and ENTERPRISE. Each mode maps to different trust thresholds in `trust_verifier.py`.
Add new modes there.

### Learning Backend (future)

`learner.py` and `evidence_recorder.py` persist to JSON files. Replace with
a database backend by swapping the functions, keeping the same signatures.

## Future Roadmap

### Short-term (next 3 months)
- **Dependency resolution**: Install transitive dependencies before the target
- **Version constraints**: Support `>=1.0.0`, `<2.0.0` in registry queries
- **Compatibility checks**: Verify python version, platform, etc.

### Medium-term (next 6 months)
- **Remote registries**: HTTP API-based registry search
- **Capability signing**: GPG/Sigstore verification in trust_verifier
- **Organization policies**: Policy-based approval gates
- **Acquisition modes**: Upgrade, downgrade, replace, disable, archive, remove

### Long-term (next 12 months)
- **Recommendation engine**: IdentityBench weaknesses → Prometheus suggestions
- **Marketplace integration**: Paid capability acquisition with billing
- **Dependency graphs**: Full transitive resolution with SAT solving
- **Cross-identity sharing**: Acquire once, share across identities

## How to Replace or Extend Prometheus

1. **Replace the engine**: Implement the same public API (`detect_need`, `evolve`,
   `pre_check_and_evolve`, `post_check_and_evolve`, `can_fulfill`, `history`)
2. **Replace the pipeline**: Subclass `EvolutionPipeline` and override `run()`
3. **Replace individual stages**: Swap any stage function while matching its signature
4. **Add a new mode**: Extend `AcquisitionMode` enum, add trust thresholds in
   `trust_verifier.py`, and update `engine.py` evolve method if the mode requires
   special routing
