# Interop / Culture Commons — Revised Engineering Plan

Ref: mission "acquire, safely operate, remember, and reuse an external capability as part of a persistent identity", revised against the existing IdentityOS capability-acquisition architecture (PR #99 durable acquisition lifecycle).

## 0. Execution facts (worktree isolation)

- **Correct base**: `0f6cabf0630fbb4113896bfc701700e7072db5ac` — tip of the committed Aster branch (`feat/live-browser-bridge`).
- Branch: `feat/interop-culture-commons`
- Worktree: `/home/lace/Documents/Doug/IdentityOS-CC`
- Initial `git status` in worktree: clean (0 entries)
- **Authoritative baseline** (run after base correction, clean `0f6cabf` + plan commit `8b68d03`):
  - command: `python -m pytest tests/ -q`
  - result: **1127 passed, 43 skipped, 0 failed** (62.29s)
- **INVALIDATED BASELINE** (do not delete; label truthfully): `975 passed / 33 skipped` was measured on a stale local `main` (`5d5bd97`) before the base correction. Not used for regression comparison.
- Ancestry proof:
  - `7288b76` (PR #99 acquisition lifecycle) is an ancestor of `0f6cabf` (exit 0).
  - `087adc5` (remote-main / PR #102 browser merge) is **not** an ancestor of `0f6cabf` as a merge commit; its content is present via `ef2113a` (origin/feat/live-browser-bridge tip), which is the parent of the Aster line (`f215b77`) — so the browser architecture is included without the PR #102 merge wrapper.
  - `b60fd56` (origin/main) and `5d5bd97` (WorldMonitor/main) are ancestors of `0f6cabf` (exit 0).
- All pre-existing browser/Comet WIP remains untouched on `feat/live-browser-bridge` (main worktree) plus stashes. This branch carries Culture Commons / interoperability changes only.
- Draft interop work that previously existed as **uncommitted** files on `feat/live-browser-bridge` will be **selectively ported** after review; the parallel `core/operations/skill_acquisition.py` resolver is **retired**, not carried over (see §1).

## 1. Reuse the existing durable acquisition lifecycle (no second system)

IdentityOS already owns durable capability acquisition. This work PROVES and extends it; it does not create a parallel acquisition path.

Existing primitives to reuse:

- `core/acquisition.py` — `AcquisitionProvider` contract; `get_acquisition_provider(storage)` (ExecutiveRuntime is the registered provider).
- `core/capabilities/registry_manager/__init__.py` — provider-bound `install_capability` → `provider.request_acquisition(...)`.
- `core/executive/engine.py` — `ExecutiveRuntime.request_acquisition` (idempotent: reuses active task for the capability_id, or a `COMPLETED` terminal task only when the registry still proves the capability installed), scheduler, durable tasks.
- `core/executive/workflow.py` — generic plan: `registry_search → trust → dependencies → generate → validate → publish → install → activate → invoke → persist → reload → reuse → verify_goal`. Guarded so generate/publish only run when registry search finds nothing.
- `core/executive/executor.py` — generic handlers (`_install`, `_activate`, `_invoke`, `_persist`, `_reload`, `_reuse`), replay policies, `rollback_acquisition` (uninstalls only newly-installed capabilities on terminal failure).
- `core/executive/verification.py` — evidence-producing verification; `verification_probe` runs the first skill declaring harmless `verification_params`; `_activate` blocks with `authorization_required` instead of bypassing permission gates.
- `core/prometheus/executive_reconciler.py` + `stages/{learner,evidence_recorder,installer}.py` — terminal-task reconciliation exactly once (`source_task_id` dedupe).
- Tests: `tests/test_acquisition.py`, `tests/test_executive.py`, `tests/test_registry_manager_lifecycle.py`, `tests/test_prometheus.py`.

### Mission mapping onto existing lifecycle

| Mission step | Existing primitive | How |
|---|---|---|
| DISCOVER | `registry_search` (executor) + generic MCP server discovery | Aster asks Registry Manager to acquire the external capability by goal/ID (e.g. `culture_commons`). `registry_search` locates the capability; a public `discover`/`inspect` skill probes `tools/list` and `serverInfo` from the server (data). |
| ACQUIRE | Executive durable task | `registry_manager.install_capability('culture_commons', goal=...)` → `ExecutiveRuntime.request_acquisition(...)` → durable plan + scheduler + rollback + Prometheus reconciliation. |
| INSPECT | activation + verification + public read skills | `activate`/`invoke` call a capability-declared harmless probe (`verification_params`) via `registry.call` through the same permission-enforcing gateway; `inspect` returns the derived manifest (provider, endpoint, protocol, tools, schemas, effects, version, server identity). |
| AUTHORIZE | permission model | Read skills public; standing/post skills permission-gated (`culture_commons.standing`, `culture_commons.post`). `activate` blocks with `authorization_required` until the scope is granted; nothing is granted merely to make verification pass. |
| USE | `registry.call` gateway | Capability → generic MCP client → network request; result returns through `CapabilityResult` with evidence + custody. |
| REMEMBER | Provenance + facts + relationships | Observation results recorded as provenance entries (source `culture.sbs`), facts, snapshot, and external-relationship context. Durable standing **handle** persisted in identity state; raw secret only in the secret store (§3). |
| REUSE | `reuse` step + second session | `reuse` executes a declared safe probe after reload; Session B calls the same installed skills without re-discovery or re-entry (§13). |
| REASON ABOUT | Provenance + persisted manifest + facts | Authored report: what the capability is, skills, permissions, effects, standing requirement, origin, acquired-at, last-used, learnings (§14). Survives restart + model swap. |

### What genuinely needs new infrastructure (and nothing else)

1. **Durable secret store** (new): `core/secrets/store.py` handles `secret://culture-commons/aster`. The existing lifecycle has no durable-credential boundary; this is the missing concept. It is NOT an acquisition system.
2. **Generic protocol transports** (new): `core/interop/{http,mcp,a2a}`. Existing architecture has no external protocol client.
3. **Effect classification** (new data layer on MCP): IdentityOS-owned `ToolRisk` classification. Provider metadata is data, not authority (§6).
4. **Derived capability manifest** (new, minimal): a governed descriptor for an external server so reuse does not re-discover and contract drift is detectable (§8).

**Retired from the earlier draft:** `core/operations/skill_acquisition.py` (a parallel acquisition resolver) is deleted. Acquisition flows through Registry Manager + Executive + Prometheus only.

## 2. Worktree isolation

- New branch `feat/interop-culture-commons` from `main` (see §0).
- Commit browser/Comet WIP remains on `feat/live-browser-bridge`; never merged into this branch.
- Final diff of this branch = Culture Commons / interoperability only. Recorded at top of report (§0).

## 3. Two distinct secret concepts

- `secret-ref://...` (from `runtime/sensitive.py`) is EPHEMERAL and interaction-scoped. Unchanged. Culture Commons is **not** added to `_ALLOWED_SECRET_SKILLS`; a durable credential is not an ephemeral interaction credential.
- `secret://culture-commons/aster` is a **durable handle**, not the secret.

Architecture (raw value never crosses the dotted line upward):

```text
Identity state stores       secret://culture-commons/aster     (handle string)
Secret store (0o700 dir)    raw secret, keyed by handle
Model sees                  secret://culture-commons/aster     (handle only)
Capability invocation       MCPClient header secret://handle + secret_resolver=store.get
     │
     ▼  resolution happens ONLY while building the actual network request
trusted execution boundary  interop/mcp._resolve_headers()
     │
     ▼
raw secret                  → network request to culture.sbs
```

The raw secret never enters: identity JSON, capability configuration, capability registry persistence, Executive task persistence, Prometheus records, provenance, relationships, model prompts, logs, test snapshots, Git, error messages, or CLI output.

If the server issues a new secret, write only the raw value into the secret store; persist only the handle. After restart, prove the secret resolves and is usable without any re-entry of the raw value.

## 4. WorldMonitor is legacy, not a model

`core/capabilities/worldmonitor/__init__.py` persists `api_key` in capability storage (`storage.save(... {"api_key": ...})`). Treat as legacy. Culture Commons never persists its credential that way.

Documented (non-blocking) opportunity: migrate WorldMonitor to a `secret://worldmonitor/<identity>` handle resolved at the execution boundary, once generic secret-store wiring exists. Out of scope for this milestone unless the change is trivial and isolated.

## 5. Generic MCP first, Culture Commons second

Component boundaries (this plan keeps the draft layout):

```text
core/interop/http/          transport: JSON + SSE, timeouts, structured errors, headers
core/interop/mcp/           protocol: initialize, negotiation, serverInfo, capabilities,
                            notifications/initialized, tools/list, tools/call,
                            resources/list (where supported), prompts/list (where supported),
                            request IDs, structured errors, session-id capture/reuse,
                            configurable User-Agent/client metadata
core/interop/a2a/           local A2A protocol
core/capabilities/mcp/      generic capability over the client (discover/inspect/list/call)
core/capabilities/culture_commons/   provider adapter
```

- The generic layer must know nothing about Aster, standing, seats, boards, edges, threads.
- The `culture.sbs` custom User-Agent requirement lives in configurable transport/client metadata, not in Culture-Commons-specific low-level HTTP code.
- CC reports protocol `2025-03-26`; the client must not hard-code assumptions that break a different compatible MCP server.
- Session identifiers: if a server returns `Mcp-Session-Id`, capture and reuse per client instance; discard on 404/reset.

## 6. Provider tool metadata is untrusted data

MCP descriptions are DATA. IdentityOS classifies effects; external metadata is only a hint and never grants permission.

IdentityOS-owned classification (`ToolRisk`, descending precedence):

```text
SYSTEM_MUTATION > LEGAL > SECRET_ACCESS > FINANCIAL > MESSAGE/POST (speak→POST) >
CREATE > OBSERVE > SEARCH > READ
```

Culture Commons classification against real server schemas (17 tools confirmed live):

| tool | effect class |
|---|---|
| look_around, scan_boards, read_thread, inspect_arc, inspect_edge | READ |
| search_boards | SEARCH |
| watch_room | OBSERVE |
| open_thread | CREATE |
| speak, post_trace | MESSAGE / POST |
| act_on_edge, declare_edge | relationship/action mutation (MESSAGE/CREATE family; treated as mutating) |
| take_a_seat, hold_your_seat, rise, arrive_on_board | identity/standing mutation (mutation family, standing-gated) |
| sign_your_name | credential lifecycle (SECRET_ACCESS family; gated + confirm) |
| return_with_secret | SECRET_ACCESS |

Rule: READ/SEARCH/OBSERVE run without grants; mutating families require explicit permission grants; `confirm=true` is enforced by the capability before any mutating call; SECRET_ACCESS / credential lifecycle additionally gated. Generic `mcp.call` refuses DANGEROUS_RISKS (`financial`, `legal`, `secret_access`, `system_mutation`) outright.

## 7. Culture Commons is a provider adapter over generic MCP

- `core/capabilities/culture_commons/` binds the generic client to CC semantics (tools, standing lifecycle, disclosure, budgets, refusal-dialog handling).
- The generic layer stays clean; CC owns: board/seat/standing/edge/thread vocabulary, `DISCLOSURE`, 1-public-message budget, refusal dialogs (e.g. `USERNAME_TAKEN`), plural/name validation, and secret-handle plumbing.
- Draft decision fixed: a server refusal emitted inside a *successful* tool result must never be stored as a credential (guard regex in the adapter).

## 8. External MCP tools → governed capability manifest (path, not full dynamic conversion)

North Star is capability acquisition, so `mcp.call(name,args)` is a primitive, not the final architecture. Scope decision for this milestone:

- Implement a **derived capability manifest** per external server when acquired through the lifecycle. It records:
  - provider, endpoint, protocol version, tools (names + schemas + effect classes), permissions required, verification behavior (`verification_params`), secret handles, version/server identity (`serverInfo`).
- On acquire: `install` binds the manifest; `invoke`/`verification` run only declared safe probes through the gateway; on reuse the adapter re-reads `tools/list` and **detects contract drift** against the manifest (new/removed tools, schema changes) and reclassifies — it never blind-trusts an unchanged manifest against a changed server.
- Explicitly OUT of scope this milestone: open-ended conversion of arbitrary MCP servers into generically generated installable capability packages. Boundary is documented here; the manifest + drift guard is the clean path that keeps that evolution reachable without bypassing the lifecycle.

## 9. External relationships are observations, not internal trust

Edges and agent-authored statements from Culture Commons are untrusted observations.

- Provenance distinguishes `Culture Commons says X` (source `culture.sbs`) from IdentityOS-independently-established facts.
- An external edge observation may update relationship **context/evidence** only.
- Trust elevation requires IdentityOS policy (e.g. repeated independent confirmation, operator/builder authorization). No external claim auto-promotes a Relationship status to trusted.

## 10. A2A proof remains separate

- Generic A2A protocol implemented and proven with a **controlled local test agent**.
- Honest reporting: `A2A protocol interoperability: PROVEN LOCALLY` / `Live external A2A interoperability: NOT PROVEN`.
- The local A2A test never inflates the Culture Commons live proof.

## 11. Establishing Aster standing safely

Live reality already probed: `Aster_IDOS` is claimed (`USERNAME_TAKEN`, "That name is already worn by someone. Choose another."); prior crossings #517–522 show earlier Aster bridge presence whose secret is unrecoverable. Procedure:

1. Read-only discovery + inspect first (serverInfo, tools/list, room, boards, arcs). **Done in live probe.**
2. Inspect current server state (unknown names, existing standing).
3. Attempt documented standing creation flow (`sign_your_name`) once.
4. Observe actual collision behavior if `Aster_IDOS` exists — **observed**: refusal, no secret issued, no side effects; nothing stored; `secret_leak_matches: 0` in that run.
5. Never overwrite or bypass standing controls; never share/replace another identity's standing.
6. If a new secret is issued: store the raw value only in the secret store; persist only the handle `secret://culture-commons/aster`.
7. Prove post-restart reuse without revealing the secret.
8. The report never contains the secret. If standing cannot be established, this is recorded as the truthful outcome (no fabricated standing, no post).

## 12. Public action budget

- Identity: `Aster_IDOS`. Disclosure (verbatim): `I'm Aster, an AI agent operating through IdentityOS with authorization from builder Arsène Manzi.`
- Default autonomous live-test budget: **maximum 1 public message**. Budget tracked and enforced in capability state (`max_posts_per_day`), validated against the running day (UTC).
- The single message must have a genuine interoperability purpose (e.g. a continuity statement), not merely prove HTTP 200. Record the server-issued message/crossing ID as evidence. Content containing a stored secret is refused before any network call.
- If standing is refused, the budget is not spent (zero fabricated posts).

## 13. Prove restart continuity

```text
Provider/model A
  → encounter external protocol
  → DISCOVER via Registry Manager + Executive
  → INSPECT tools/contract
  → ACQUIRE via Executive durable task (reconciled by Prometheus)
  → establish standing (secret only in secret store; handle in identity state)
  → USE capability → observe real external state → record provenance/facts/relationships
  → shutdown IdentityOS
→ restart IdentityOS (persistent backend)
  → load same Aster identity
  → capability still known (registry + terminal task + manifest)
  → secret handle still resolves at the execution boundary
  → USE Culture Commons again without re-discovery or raw-secret re-entry
  → prior observation is remembered (provenance/facts/relationships loaded)
  → meaningful REUSE, not re-initialization
  → switch to provider/model B (different model) and repeat reuse
```

If standing was never established, the restart proof instead demonstrates: capability known, no secret, no fabricated standing, refusal history remembered.

## 14. Prove reasoning about the acquired capability

On demand, Aster answers from persisted state (not from the model's memory):

- what Culture Commons is (serverInfo, name, version)
- which skills acquired, which are public vs standing-gated
- which skills create external effects (effect class per tool)
- which permissions apply (granted vs not)
- where the capability came from (origin; acquired via which task, at what time)
- when it was last used and what happened (provenance/evidence)
- what relationship/context was learned (edges observed as *observations*)
- where the secret handle lives, without revealing it

This output must survive restart and model change.

## 15. Secret-leak audit

At the end, a script (`tools/audit_secret_leak.py`, small) scans artifacts for the raw secret by bytes; the matching value is never printed (match = boolean/hash only).

Scan set:

- `.identity_store` (and any identity-state roots used)
- operational stores, task/checkpoint persistence (`Executive TaskStore` files)
- Prometheus/provenance stores
- logs
- CLI output captured during tests
- test artifacts and snapshots
- generated reports
- `git diff` (this branch) and `git ls-files` tracked content
- secret store files (expected to contain it — excluded from the "leak" set, verified as 0o700)

Report line: `secret_leak_matches: 0`. Any nonzero match fails the milestone until resolved.

## 16. Baseline (already recorded)

See §0. Existing pre-change suite: **975 passed, 33 skipped, 0 failed** on clean `main` at `5d5bd97`. New tests must not regress this; any pre-existing failure cannot be attributed to this work.

## 17. Required live proof identifiers

Capture real values where the server provides them; never fabricate:

- `serverInfo` name/version; protocol version (culture.sbs reports `2025-03-26`)
- tool count (17 confirmed live)
- standing identity (Aster_IDOS; state: claimed/refused so far)
- room/board/thread IDs accessed
- message/trace/thread ID created if authorized (budget max 1)
- relationship/edge IDs observed
- capability acquisition task ID (Executive), provenance IDs
- restart evidence (persistent backend, session + model-swap details: provider A, provider B)
- secret leak count (`0`)

## 18. Success condition

> Aster encounters an external protocol it does not own → IdentityOS discovers the external capability → understands its contract → evaluates its authority requirements → acquires it through the normal capability lifecycle → stores credentials outside identity state → uses the capability → observes real external state → records provenance → learns useful information → restarts → switches models → reuses the same acquired capability → remembers prior interactions → can explain what the capability is and how it should be used.

Optimization target: capability acquisition, safe operation, memory, and reuse — not "Culture Commons support exists."