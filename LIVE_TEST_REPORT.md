# Live Gmail Test — Findings, Fixes, and Re-Run Plan

Two live-test runs informed this work: the **first** (July) ran against the real
Gmail box and surfaced six failures in the then-current

BROWSER-BRIDGE build. The **second run** described in this plan is the
permissioned `.aster-live-v2` re-run on a **clean store**, exercising the fixes
below.

Branch: `feat/live-browser-bridge`
Corrective commit: `af4ef28` (on top of `f215b77`, `08efc62`, `e6ff431`,
`3cfe99e`).

Full suite after fixes: **1120 passed / 40 skipped / 3 pre-existing env-gated
errors** (`tests/test_cross_app_continuity.py` `NameError: repo_root` — unrelated,
untouched).

---

## The 16 findings → root cause → fix

### 1. Unrelated/system mail was treated as part of a conversation
The engine reacted to every inbound message within any existing thread, even
genuine third-party or system mail that merely shared headers.
**Fix:** `ConversationMonitor` in `core/operations/monitor.py` now classifies
every message through `_classify()` into an `InboundDisposition`
(`TRUSTED_THREAD` / `APPROVED_SENDER` / `UNSOLICITED_UNKNOWN` / `AUTOMATED` /
`BOUNCE` / `SELF_COPY` / `SPAM_OR_BULK`). Only trusted categories may reach a
reply.

### 2. `no-reply@` automation was answered as if it were the counterparty
No relationship existed with the automation address, but abuses of thread
context slipped through.
**Fix:** an automated-sender regex (`no-reply`, `donotreply`, `mailer-daemon`,
`postmaster`, …) plus bounce/automated/spam subject-and-body patterns are the
secondary gate. Automated mail is `ignored`: recorded for audit, never replied
to, and **never** used to forge or mutate a relationship.

### 3. Mail arriving in a thread but from an unexpected sender was trusted
Header matching alone was treated as identity.
**Fix:** a trusted-thread disposition still requires `_norm(sender) ==
_norm(relationship.email)`. A mismatch is a **thread intrusion** → `quarantined`
and the rule tests prove the relationship email is never reassigned to the
intruder.

### 4. Self-copies and mailbox duplicates could double-process mail
SMTP sends landed back in the same IMAP folder the monitor reads.
**Fix:** `SELF_COPY` is matched against `self_address` (wired from
`config.sender_email`) and skipped; cursor dedupe (finding 15) prevents
re-processing across restarts.

### 5. No real technical answer — canned acknowledgements were sent
The reply path defaulted to a generic “thanks for getting back to me” you never
wrote, because fact grounding failed (finding 6).
**Fix:** `core/operations/composition.py::_structured_reply` rewritten as a
truthful, grounded reply: **no fabricated facts, no canned filler**, signature
wired from the adapter. If there is nothing real to say, the engine defers
rather than bluffing (finding 6/7).

### 6. Project observation produced `0 fact(s)`
The observer looked only directly in the configured directory, missing the real
project nested one level deeper (`…/Doug` wrapper → `…/Doug/IdentityOS` repo).
**Fix:** `core/operations/observer.py` auto-resolves a **nested project root**
(one–two-level `pyproject.toml` scan, unambiguous best-scoring child by
`.git`/`README`/tests), and only when it is unambiguous.

### 7. Facts were shallow strings with no provenance
Even a successful observation produced unverifiable claims.
**Fix:** observation now yields `ProjectState.fact_details: list[ProjectFact]`
with `source_type`/`source_path`/`observed_at`/`commit_sha`, drawn from
pyproject metadata, README, docs, registry config, tests, and git. `metadata`
carries the resolved root and commit SHA. CLI surface: `identity aster
status`, `would-send`, `notify`, `provenance` for review.

### 8. `$200,000 for 10%` was not escalated for approval
High-value offer passed the old categorical gating.
**Fix:** `core/operations/policy.py` defines **immutable baseline consequential
categories** (investment, equity, contracts, legal, money, credentials, access,
ip ownership, repository access, employment, exclusivity).
`ControlState.require_approval_categories` may only *add*; a baseline category
cannot be disabled. Baseline test: an empty config still escalates
`$200,000 for 10%` and `category="investment"`.

### 9. Classification ran before the money/deal-shape guard
If the model mis-labelled the intent, consequential signals were skipped.
**Fix:** a deterministic regex scan over the combined routing/category/content
runs **before** model classification: money (`$`, `€`, amounts), compound
money+deal-shape (`$200,000` + `10%`), equity/share/ownership/sale/acquisition
phrases, and extended commitment phrasing all force
`AWAITING_AUTHORIZATION`.

### 10. Escalated messages should never be auto-replied
Once authority is required, the loop must stop being chatty about money that is
not yours to discuss.
**Fix:** escalated inbound marks the relationship
`awaiting_human_authorization` and yields **no auto-reply**; authorization is
reached only via `identity aster escalate` + `decide` (or a trusted operator).

### 11. Observe mode was ambiguous about external transmissions
ObseRvE was loosely defined and could be interpreted as still sending
messages.
**Fix:** observe mode is now **zero external transmissions, period** — inbound
is still read, facts still gathered, but all outbound goes to the *drafts
sandbox* surfaced by `identity aster would-send`. Nothing egresses on a real
transport in observe mode.

### 12. Unknown senders were replied to even in observe mode
Politeness drafting happened before classification.
**Fix:** disposition runs first: an unknown sender is `quarantined` and no
draft is even composed, in observe *or* autonomous mode. In observe mode only
trusted inbound (a real conversation) produces a `would-send` draft.

### 13. Confidence=0 outreach fired after disqualification
The candidate was disqualified yet still reached the act phase.
**Fix:** `core/operations/evaluation.py` now applies the `source_confidence`
factor **only when > 0** (no regression to zero-confidence scores) and a
zero-confidence recommendation becomes `hold` **unless `test_candidate=true`**
— plus a defense-in-depth gate in `engine._phase_act` that refuses any
QUALIFIED candidate with `confidence == 0.0` and no `test_candidate` flag.

### 14. Principal notifications were noisy and un-deduplicated
Repeated ticks spammed similar gap messages.
**Fix:** `core/operations/capability_gap.py` exposes `CapabilityStatus`
(`ready` / `capability_missing` / `available_not_installed` /
`installed_permission_missing`) on `CapabilityGap`; principal notifications are
emitted with kind `permission_required` or `capability_available` and
**deduplicated by (kind, required_skill)** across ticks. Regression tests cover
both statuses and dedupe.

### 15. Historical inbox contents were treated as new conversation
First connect replayed the whole mailbox.
**Fix:** IMAP uses a persisted high-water mark (`fetch_inbox_with_cursor`):
UID/UIDNEXT cursor with UIDVALIDITY reseed; a first run **baselines without
ingesting**, so old mail is never re-processed; cursor is saved on every fetch
and tolerant of `MailboxCursor | dict` storage.

### 16. The suite now locks all of the above in
- `test_operations_engine.py` (39): automated sender ignored + no forging,
  unsolicited sender quarantined, thread-intrusion quarantine, zero-facts
  knowledge gate (deferred + `project_context_unavailable`), `$200k/10%`
  escalation, baseline-categories-can’t-be-disabled, confidence 0 hold vs
  `test_candidate` override, gap statuses + dedupe, nested-root observer.
- `test_email_capability.py` (12): FakeIMAP cursor baseline-without-replay,
  UIDVALIDITY reseed, `read_inbox_cursor` round-trip.
- Observe-mode test updated to pre-seed a trusted relationship and asserts
  drafts-without-send; candidacy/mirror fixtures default trustworthy confidences.
- Targeted run 56 passed; full suite 1120 passed / 40 skipped / 3 env-gated errors.

---

## `.aster-live-v2` — permissioned re-run

New clean store. The old polluted store (`.aster-live`) is kept as evidence and
is **not** used.

### 0. Prerequisites
- Real credentials **must** be provided by you — this repo never contains them
  and no step below fabricates them.
- `ASTER_TEST_RECIPIENT` is a human-checked test recipient; the allowlist +
  candidates file are the enforcement boundary, not just this variable.

```sh
export IDENTITY_SMTP_HOST=smtp.gmail.com
export IDENTITY_SMTP_PORT=465
export IDENTITY_SMTP_USER='<address>@gmail.com'
export IDENTITY_SMTP_PASSWORD='<app password>'
export IDENTITY_IMAP_HOST=imap.gmail.com
export IDENTITY_IMAP_PORT=993
export IDENTITY_EMAIL_FROM='Aster <address>@gmail.com'
export ASTER_TEST_RECIPIENT='<your-check-address>@example.com'
# optional file mailbox instead of real IMAP for the read-only rehearsal:
# export IDENTITY_MAILBOX_ROOT=~/mailbox-v2
```

### 1. Clean-store init (grant email read + send)
```sh
python3 -m cli.main aster init \
  --store .aster-live-v2 \
  --project-root "$PWD" \
  --grant-email --grant-operations
```
> Note: `--grant-email` grants `email.send/read`; the inbox cursor fix (finding
> 15) is enabled by `IDENTITY_IMAP_HOST` being set at init for a real SMTP/IMAP
> backend.

### 2. Read-only rehearsal in observe mode (finding 11/12)
```sh
python3 -m cli.main aster outbound-mode --store .aster-live-v2 observe
python3 -m cli.main aster run --store .aster-live-v2 --once
python3 -m cli.main aster tick --store .aster-live-v2          # repeatable
python3 -m cli.main aster status --store .aster-live-v2
python3 -m cli.main aster would-send --store .aster-live-v2    # drafts only, nothing egresses
python3 -m cli.main aster notify --store .aster-live-v2        # incl. gap/permission kinds
python3 -m cli.main aster provenance --store .aster-live-v2    # dispositions shown per message
```
Expected: `0 fact(s)` is impossible (`status` shows real project facts from the
resolved nested root, finding 6/7); no automated/unknown mail is drafted; any
real thread stays a proper conversation.

### 3. Permissioned autonomous (still allowlisted, no outreach)
```sh
python3 -m cli.main aster override --store .aster-live-v2 allowed_external_recipients="<ASTER_TEST_RECIPIENT>"
python3 -m cli.main aster outbound-mode --store .aster-live-v2 autonomous
python3 -m cli.main aster tick --store .aster-live-v2
python3 -m cli.main aster messages --store .aster-live-v2 --unseen
python3 -m cli.main aster relationships --store .aster-live-v2
python3 -m cli.main aster escalate --store .aster-live-v2      # any \$/equity → here, no auto-reply
```
Deliberately **do not** seed or contact Beta Fund; no general outreach is
enabled. Anything consequential arrives in `escalate` for a human decision:
```sh
python3 -m cli.main aster decide --store .aster-live-v2 approve|reject <opportunity_id>
```

### 4. Verification checklist for the re-run
1. `provenance` shows the actual sender on `quarantined`/`ignored` entries.
2. No relationship ever contains a `no-reply@…` or an intruder address.
3. Every reply is grounded (no canned “thanks for getting back to me”).
4. `status` shows the resolved nested project root and non-zero facts.
5. A crafted `$200,000 for 10%` test email lands in `escalate`, not outbound.
6. Observe mode produced zero SMTP egress across multiple runs.

### Rollback
The store is a single directory; remove `.aster-live-v2` and re-init for a
from-scratch re-run. The evidence store `.aster-live` remains untouched.