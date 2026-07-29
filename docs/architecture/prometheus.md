# Prometheus: Autonomous Capability Evolution

**Design Document — v1**

---

## Problem

IdentityOS ships with a fixed set of built-in capabilities. Users inevitably ask the
system to do things it wasn't built for — search a GitHub repository, check the weather,
calculate a complex expression, read a file.

Without Prometheus, the system can only say "I can't do that." The user is stuck. The
system cannot grow.

Prometheus closes this gap. It detects when a missing capability is needed, finds a
trustworthy version, installs it safely, retries the original task, and remembers what
it learned so the next request is faster.

---

## Goals

### Autonomous evolution

The system should acquire new capabilities on its own, without requiring code deploys,
Docker rebuilds, or human intervention. The user asks for something. If a capability
exists in the registry that can fulfill the request, Prometheus finds it, installs it,
and the user gets their answer — all in one interaction.

### Safe evolution

Autonomous installation is inherently risky. Prometheus must guarantee:

- No recursive acquisition loops (evolution that triggers evolution that triggers...)
- No repeated installation of the same capability
- No installation of untrusted capabilities without policy checks
- No unbounded installs (rate limiting)
- Clean rollback if install or validation fails

### Measurable evolution

Every acquisition attempt produces metrics: gap detection accuracy, search quality,
install success rate, retry success rate, adaptation speed, reuse rate, unnecessary
install prevention, and performance improvement. These feed into IdentityBench as the
"Evolution" category, creating a closed feedback loop.

### Reversible evolution

Every installation can be rolled back. If validation fails after install, Prometheus
uninstalls the capability before returning. The system never leaves a half-installed
capability behind.

---

## Non-goals

Prometheus does **not**:

- **Answer user questions.** That is the LLM adapter's job. Prometheus only detects
  gaps and installs missing capabilities. It never generates responses.

- **Execute capabilities.** Installed capabilities are invoked by the SkillRouter and
  Planner layers. Prometheus only handles the acquisition lifecycle.

- **Own memories.** Memory and fact stores are managed by the Identity Runtime.
  Prometheus has its own learning store (success rates, task→capability mappings,
  evidence history) that is separate from identity memory.

- **Own planning.** The Planner routes user intent to installed capabilities.
  Prometheus runs before and after planning to ensure the right capabilities are
  available, but it does not participate in routing decisions.

- **Generate registry content.** The capability registry is maintained externally.
  Prometheus reads from it but never writes to it.

- **Implement user approval UI.** In `APPROVAL_REQUIRED` mode, Prometheus gates on
  trust score but does not surface a UI for human approval. That is the responsibility
  of the integration layer (CLI, API, frontend).

---

## Architecture

```
User says: "Check my latest PR on GitHub"
                │
                ▼
┌─────────────────────────────┐
│ 1. Need Detector            │  ← keyword matching + response pattern analysis
│    "github" in user_input   │     detects missing capability
└─────────────┬───────────────┘
              │ gap detected
              ▼
┌─────────────────────────────┐
│ 2. Registry Search          │  ← loads registry/capabilities/index.json
│    Found: github v2.4       │     scores each entry for relevance
└─────────────┬───────────────┘
              │ candidates found
              ▼
┌─────────────────────────────┐
│ 3. Ranking                  │  ← relevance + author trust + version maturity
│    #1 github by IdentityOS  │
└─────────────┬───────────────┘
              │ best candidate
              ▼
┌─────────────────────────────┐
│ 4. Trust Verification       │  ← author reputation, version, permissions
│    IdentityOS → score 0.75  │     mode-dependent threshold
└─────────────┬───────────────┘
              │ trusted (or blocked)
              ▼
┌─────────────────────────────┐
│ 5. Dependency Resolution    │  ← checks candidate.dependencies against
│    No missing deps          │     installed_ids
└─────────────┬───────────────┘
              │ deps satisfied
              ▼
┌─────────────────────────────┐
│ 6. Installation             │  ← registry.install(identity_id, cap_id)
│    github v2.4 installed    │     on failure → rollback
└─────────────┬───────────────┘
              │ installed
              ▼
┌─────────────────────────────┐
│ 7. Validation               │  ← registry.list() + skills() check
│    Skills available ✓       │     on failure → rollback + uninstall
└─────────────┬───────────────┘
              │ validated
              ▼
┌─────────────────────────────┐
│ 8. Retry                    │  ← runtime.process() with original request
│    "Here is the latest PR"  │     adapter now has the capability
└─────────────┬───────────────┘
              │ response received
              ▼
┌─────────────────────────────┐
│ 9. Performance Evaluation   │  ← compare original refusal vs retry response
│    Gain: +0.8               │     measures delta
└─────────────┬───────────────┘
              │ evaluated
              ▼
┌─────────────────────────────┐
│ 10. Learning                │  ← persist to prometheus_learning.json
│     +1 success for github   │     update task→capability map
└─────────────┬───────────────┘
              │ learned
              ▼
┌─────────────────────────────┐
│ 11. Evidence Recording      │  ← persist to prometheus_evidence.json
│     Full acquisition trace  │     queryable via engine.history()
└─────────────┬───────────────┘
              │ recorded
              ▼
    EvolutionResult returned to runtime
```

### Pipeline integration points at runtime

The Prometheus engine hooks into `runtime/orchestrator.py` at two points in the
`process()` method:

**Pre-check (Stage 2b) — before context composition**

Runs after input sanitization but before the system composes the context that is
sent to the LLM. If Prometheus detects a missing capability and installs it here,
the context composition picks up the new capability's prompts and skills. The LLM
sees the capability from the very first adapter call.

```
Input → Sanitize → [Pre-check] → Compose Context → Route → Adapter → Output
```

**Post-check (Stage 4b) — after adapter response**

Runs after the LLM adapter responds. If the response contains patterns like "I don't
have a GitHub capability," Prometheus installs the missing capability and retries the
adapter call with the updated context. The user sees the retry response, not the
original refusal.

```
Input → ... → Adapter → [Post-check → Install → Retry] → Output
```

### Safety mechanisms during retry

When Prometheus retries the original task by calling `runtime.process()`, the re-entrancy
guard (`_evolving` flag) prevents the recursive evolution that would otherwise occur:

1. Post-check sets `_evolving = True`
2. Post-check calls `evolve()` which runs the pipeline
3. Pipeline calls `retry_original_task()` → `runtime.process()`
4. `runtime.process()` calls `pre_check_and_evolve()` which sees `_evolving = True` and returns `None`
5. `runtime.process()` completes normally
6. `runtime.process()` calls `post_check_and_evolve()` which sees `_evolving = True` and returns `None`
7. Control returns to the outer post-check which clears `_evolving = False`

---

## Failure modes

### Registry unavailable

The registry searcher loads a local JSON file (`registry/capabilities/index.json`).
If the file is missing or corrupted, search returns zero candidates. The pipeline
fails with "No candidates found in registry." The user sees the original response.

**Guarantee:** No crash. No partial state. The error is recorded in the
`AcquisitionRecord` for observability.

### Capability cannot be installed

`safe_install()` wraps `registry.install()` in a try/except. If install raises an
exception, `rollback_install()` calls `registry.uninstall()` to clean up. The pipeline
transitions to `ROLLED_BACK` status.

```
Install fails → rollback → ROLLED_BACK → return to user
```

**Guarantee:** The system never has a half-installed capability. Rollback always runs.

### Validation fails after install

After a successful install, `validate_capability()` checks that the capability appears
in `registry.list()` and that its skills are accessible. If validation fails:

```
Install succeeds → validate fails → uninstall → ROLLED_BACK → return to user
```

**Guarantee:** An installed but non-functional capability is immediately removed.
The uninstall runs in the same pipeline step.

### Recursive evolution

Without protection, the pipeline's retry step (which calls `runtime.process()`) would
trigger Prometheus hooks again, creating an infinite loop.

```
post_check → install → retry → process() → post_check → install → retry → ...
```

**Guarantee:** The `_evolving` flag prevents re-entry. Evolution is excluded from
nested `runtime.process()` calls. The guard is cleared in a `finally` block so
exceptions cannot leave the system permanently blocked.

### Acquisition limit reached

Without a cap, a single user interaction could trigger dozens of installs. The
`max_acquisitions_per_interaction` config (default 1) limits how many capabilities
can be installed in a single `process()` call.

```
Interaction 1: install github ✓
Interaction 1: install weather ✗ (limit reached)
Interaction 2: install weather ✓
```

---

## Future

### Marketplace integration

The registry searcher currently loads a local index. A marketplace would provide a
remote HTTP API returning the same candidate structure. The `search_registry()`
function can be replaced with one that queries the marketplace API while keeping
the same return type (`List[RegistryCandidate]`).

```
Current:  load index.json → score → return candidates
Future:   GET api.marketplace/search?q=github → score → return candidates
```

Trade-off: marketplace adds latency, requires auth, and introduces billing.
Prometheus does not need to change its pipeline — only the search stage.

### Federated registries

Multiple registries (local, enterprise, marketplace, community) can be searched in
parallel and their results merged before ranking. Each entry's `manifest_url` field
tracks provenance, enabling trust scoring by source.

```
registry_searcher():
    local_results = search_local(need)
    enterprise_results = search_enterprise(need)
    marketplace_results = search_marketplace(need)
    return merge(local_results, enterprise_results, marketplace_results)
```

### Capability signing

Trust verification currently uses author reputation + version maturity. Adding
signature verification (GPG, Sigstore, Sigsum) makes trust cryptographic rather
than reputational.

`verify_trust()` would add a step:
```
if candidate has signature and signature.verify(trusted_keys):
    score += 0.3
```

The `RegistryCandidate` model already has a `permissions` dict that could carry
signing metadata.

### Human approval

`APPROVAL_REQUIRED` mode currently gates on a lower trust threshold but has no
UI. A future integration would:

1. Detect a need and find a candidate
2. Gate on `mode == APPROVAL_REQUIRED`
3. Emit an event or enqueue a notification
4. Wait for human response (approve/reject/timeout)
5. Proceed or abort based on the response

The pipeline's mode check in `trust_verifier.py` is the insertion point:
```
if mode == APPROVAL_REQUIRED and score >= MIN_TRUST_SCORE:
    return await_human_approval(candidate)
```

### Organization policy

Enterprise deployments need policy-based gates beyond trust scoring. A policy
engine query would slot in after trust verification:

```
if not policy_engine.evaluate("capability.acquire", candidate):
    block with "Blocked by organization policy"
```

The `PolicyEngine` in `runtime/orchestrator.py` already exists for input/output
policies. Extending it to capability acquisition is a natural evolution.

### What this enables over time

| Phase | Capability | Mechanism |
|-------|-----------|-----------|
| Now | Auto-acquire from local registry | Keyword detection + pipeline |
| Short-term | Acquire from marketplace | Replace `search_registry()` |
| Medium-term | Federated registries | Parallel search + merge |
| Medium-term | Signed capabilities | Add verification to `verify_trust()` |
| Medium-term | Human approval flow | Mode routing + event emission |
| Long-term | Organization policies | PolicyEngine integration |
| Long-term | Dependency graphs | Recursive dependency resolution |
| Long-term | Cross-identity sharing | Learn once, reuse across identities |

---

## Code map

| File | Role |
|------|------|
| `core/prometheus/engine.py` | Public API — `detect_need()`, `evolve()`, `pre/post_check_and_evolve()`, `can_fulfill()`, `history()`, safety guard |
| `core/prometheus/pipeline.py` | Acquisition lifecycle — runs stages in order, manages `AcquisitionRecord`, rate limiting |
| `core/prometheus/models.py` | Data models — `CapabilityNeed`, `RegistryCandidate`, `AcquisitionRecord`, `EvolutionResult`, `PrometheusConfig`, enums |
| `core/prometheus/stages/need_detector.py` | Keyword matching and response pattern analysis |
| `core/prometheus/stages/registry_searcher.py` | Load registry index, score relevance, build candidates |
| `core/prometheus/stages/candidate_ranker.py` | Rank by relevance + author + version |
| `core/prometheus/stages/trust_verifier.py` | Trust scoring by author, version, permissions |
| `core/prometheus/stages/dependency_resolver.py` | Check candidate dependencies against installed set |
| `core/prometheus/stages/installer.py` | Safe install with rollback |
| `core/prometheus/stages/validator.py` | Post-install validation |
| `core/prometheus/stages/retry_handler.py` | Re-invoke `runtime.process()` |
| `core/prometheus/stages/performance_evaluator.py` | Compare original vs retry response quality |
| `core/prometheus/stages/learner.py` | Persist success rates and task→capability mappings |
| `core/prometheus/stages/evidence_recorder.py` | Persist acquisition evidence history |
| `runtime/orchestrator.py` | Integration hooks (Stage 2b and 4b) |
| `identitybench/metrics/evolution.py` | 8 Evolution metrics for IdentityBench |
| `identitybench/worlds/evolution.py` | Evolution benchmark world (10 interactions, 21 days) |
