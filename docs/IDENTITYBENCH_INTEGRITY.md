# IdentityBench integrity and continuous improvement

## Status

Proposed architecture. The versioned provenance and raw-evidence foundations
described below are implemented; the independent evaluator and autonomous
improvement loop require separate rollout work.

## Objective

Run IdentityBench several times per day, turn failures into actionable
engineering work, and accept improvements only when independently observed
behavior improves without weakening truthfulness, safety, continuity, or the
benchmark itself.

No benchmark can be mathematically cheat-proof when candidate code can inspect
or modify its evaluator. The defensible goal is to place candidate code and the
acceptance evaluator in different trust boundaries, hide and rotate a portion
of the test distribution, and make every accepted score reproducible and
tamper-evident.

## Threat model

The system must detect or make ineffective:

- prompt- or identity-specific branches;
- detecting CI, IdentityBench, scenario names, or fixed timestamps;
- changing score calculations to turn failures into passes;
- comparing different models, budgets, suites, or seeds as one trend;
- selecting only favorable trials;
- fabricated tool output or model-reported execution;
- leaking holdout prompts through artifacts or logs;
- modifying a workflow to skip gates or publish a forged check;
- sacrificing latency, safety, persistence, or general behavior for a score.

## Trust boundaries

```text
candidate commit (untrusted)
        |
        v
isolated runtime sandbox -----> short-lived, quota-bound model proxy
        |
        v
observed events and outputs
        |
        v
protected evaluator + hidden scenario pack
        |
        v
signed result ledger -----> aggregate PR check / engineering issue
```

The evaluator must come from a protected repository or immutable release, not
from the candidate branch. Candidate code runs without repository write access,
provider credentials, holdout files, or the scoring implementation. Model
access is exposed through a request-limited proxy so candidate code cannot read
or exfiltrate a reusable provider secret.

Do not use `pull_request_target` to check out and execute an untrusted pull
request with secrets. A trusted `workflow_run` consumer, isolated evaluator
service, or locked-down self-hosted runner should evaluate the already-frozen
commit SHA.

## Evaluation lanes

### Public development lane

- Deterministic scenarios, expected invariants, and scoring are public.
- Runs on every pull request without privileged credentials.
- Produces detailed per-interaction diagnostics for engineering.
- Prevents known bugs from returning but is not an acceptance authority by
  itself because authors can optimize directly against it.

### Protected holdout lane

- Scenario templates, paraphrases, identities, ordering, and seeds are stored
  outside the candidate repository.
- The evaluator selects seeds only after the commit SHA is frozen.
- Scenario packs rotate, and retired packs are published later for scrutiny.
- Pull requests receive categories, confidence intervals, and failure classes;
  raw protected prompts remain restricted until retirement.
- Maintainers retain access to complete execution evidence for audit.

### Cross-model lane

- Runs weekly across at least one canonical hosted model and two independent
  model families or local models.
- Rejects improvements that only work on one model's prompt or tool-call quirks.
- Never merges cross-model scores into one headline number; every model has its
  own baseline and comparison signature.

## Schedule

With a dedicated benchmark quota, run paired canonical-model smoke trials at
02:00, 10:00, and 18:00 UTC. Each window evaluates the protected `main` baseline
and candidate commit with the same freshly selected seeds and equivalent fresh
identities. Run a full suite nightly and the cross-model lane weekly.

If provider quota is constrained, preserve paired evaluation and reduce the
number of worlds or windows. Never run only the candidate to save quota: model
drift and provider variance would then look like product change.

Each score window should contain at least three paired trials. Promotion uses
the median paired delta and a confidence interval, not the single best result.
Nine paired observations across the three daily windows provide the first
decision-quality daily signal.

## Comparison eligibility

Every run records and signs:

- candidate and base commit SHA;
- scoring schema version and evaluator digest;
- public and protected suite digests;
- provider, exact model, and endpoint class;
- seed commitment and revealed seed;
- world list and ordering;
- context, output, tool-result, tool-count, and tool-round budgets;
- installed capability manifest digests;
- identity-state origin and persistence/restart evidence;
- raw runtime events, capability results, timings, and final outputs;
- artifact SHA-256 digest and completion status.

Runs with different comparison signatures are separate baselines. Failed,
partial, retried-with-different-settings, or missing-evidence runs remain in the
ledger but cannot contribute a score.

## Promotion gate

An implementation is called an improvement only when all of these hold:

1. Unit, integration, security, persistence, and capability conformance gates
   pass without weakening or deleting tests.
2. The median paired overall delta is at least +3 points and the confidence
   interval excludes zero.
3. No protected world regresses by more than 5 points.
4. Truthfulness, evidence accuracy, restart recovery, and isolation do not
   regress.
5. Interactive latency and prompt growth remain within explicit budgets.
6. Gains appear in both public and protected lanes and survive the canonical
   model; durable changes are later confirmed cross-model.
7. The change contains no benchmark identity, prompt, scenario, CI-environment,
   or score-specific production branch.
8. A reviewer can connect the gain to a general runtime invariant and executable
   evidence.

The protected evaluator owns the final check. Candidate code may emit evidence
but cannot assign itself a passing score.

## Automated improvement loop

After each daily window, an observer creates or updates one evidence-backed
finding per weak category. A separate engineering agent may select one finding,
reproduce it through a non-benchmark API test, identify the violated general
invariant, and implement a focused fix on a new branch.

```text
observe repeated failure
  -> classify runtime owner
  -> reproduce outside benchmark
  -> implement general fix
  -> add ordinary regression test
  -> run public lane
  -> run protected paired lane
  -> open PR only if promotion gate passes
```

The engineering agent receives failure classes and public examples, not active
holdout prompts. It cannot edit the protected evaluator, approve its own PR, or
merge. A low score is not permission to change production behavior without a
reproduced invariant violation.

## Governance

- Benchmark schema or scoring changes require designated CODEOWNERS and create
  a new baseline automatically.
- Evaluator releases are immutable and signed; their source is published after
  the corresponding holdout packs retire.
- Scheduled jobs publish all attempted trials, preventing cherry-picking.
- The result ledger is append-only with retention longer than the reporting
  window.
- Alerts distinguish product regression, model/provider drift, evaluator
  change, quota failure, and missing evidence.
- Quarterly audits seed known cheating implementations and verify that the
  protected lane rejects them.

## Rollout

1. Keep the current raw-artifact upload, truthfulness semantics, suite digest,
   and comparison signature as the local provenance layer.
2. Add paired base/head orchestration and three daily canonical-model windows.
3. Move acceptance scoring and rotating holdouts to a protected evaluator with
   a quota-bound model proxy and signed result ledger.
4. Add the observer-to-engineering-agent loop in advisory mode.
5. Allow autonomous PR creation only after several weeks of audited advisory
   results; retain independent review and normal branch protection.

