# Browser capability experiments

This document separates historical experiment notes from behavior established
by the current runtime and its executable tests. A public page can establish
that content exists, but it cannot by itself prove which identity or execution
path created it. See [`docs/BROWSER-CAPABILITY.md`](../docs/BROWSER-CAPABILITY.md)
for the supported interface and security model.

## Recorded experiments

These observations were supplied after manual sessions with the Comet identity
and Surfer ISP pack on 2026-09-12. The repository does not contain the original
event streams, so they are useful exploratory notes rather than regression-test
evidence.

### Write.as publishing

- An initial post containing a GitHub link was reportedly rejected by the
  service's anti-spam controls.
- A second post was published at
  <https://write.as/6n4r8zu44tac1.md>. Its title and body were independently
  reachable over HTTP on 2026-09-12.
- The page is evidence of the output, not proof that the following automation
  sequence created it.

The recorded sequence was:

```text
browser.search(query="anonymous publishing platform", task="find a platform")
browser.open(url="https://write.as")
browser.click(selector="a:has-text('Start writing')")
browser.type(selector="textarea#writer", text="[content]")
browser.type(selector="input[placeholder*='Title']", text="[title]")
browser.click(selector="button:has-text('Publish')")
browser.snapshot()
```

### Hastebin

The manual session reportedly typed content successfully, but the Toptal
Hastebin wrapper did not return a new paste URL after Save. That makes this a
partial/failed workflow, not a demonstrated publish operation.

### YouTube

The manual session reportedly navigated, clicked, scrolled, and captured page
snapshots. Transcript extraction was not established. Any summary produced in
that session must therefore be treated as a model interpretation rather than a
transcript-grounded capability result.

## Runtime-established behavior

The hermetic real-Chromium test in `tests/test_browser_security.py` establishes
the following behavior independently of model prose:

- install and permission activation;
- navigation, form filling, clicking, key presses, waits, and snapshots;
- login failure and success based on observed postconditions;
- credential redaction before persistence or model exposure;
- persistent cookies across a fresh Python process;
- profile isolation across storage roots, identities, and user scopes;
- bounded profile removal on uninstall; and
- compatibility with an existing non-browser capability path.

CI runs that lifecycle against a local fixture rather than a third-party site,
so service changes, bot protection, or network instability cannot create false
positives.

## Current limitations

| Area | Current behavior | Remaining limitation |
|---|---|---|
| Browser engine | Playwright Chromium; headless is configurable | No Firefox/WebKit selection or extension API |
| Profile state | IdentityOS-owned Chromium profiles persist cookies and local storage across process restarts | Importing or sharing a user's existing browser profile is intentionally unsupported |
| Tabs | The persistent context can contain pages, but the capability exposes one active page | No explicit tab create/list/switch API |
| Checkpointing | Browser profile data persists on disk | No portable/exportable session checkpoint format |
| Credentials | Explicit chat credentials are replaced with ephemeral references and require a separate permission | No durable password store, 2FA, or OAuth coordinator |
| Content extraction | DOM text and interactive elements are captured | Closed shadow roots, canvases, media, and bot-protected content may be inaccessible |
| Navigation safety | `file:`, loopback, link-local, and private-network targets are denied by default | Public sites can still be malicious; Chromium is not an OS sandbox |
| Reliability | Failures return structured evidence | No generic retry/backoff policy; selectors can become stale |
| Visual interaction | DOM-driven actions and snapshots | No screenshot/vision-based element grounding |

## Safe expansion priorities

1. Add explicit multi-tab APIs with per-action evidence and tests.
2. Add portable, encrypted session export/import with expiry, origin allowlists,
   and user confirmation. Do not silently attach an identity to a person's
   everyday browser profile.
3. Add recoverable retry/backoff for idempotent reads while leaving writes
   explicit and non-retrying by default.
4. Add screenshot evidence and visual element grounding without treating model
   interpretation as action success.
5. Add controlled OAuth/2FA handoff flows in which the user completes sensitive
   approval steps and tokens never enter model context.
6. Add configurable viewport and supported browser-engine selection.
7. Add domain allowlists, rate limits, `robots.txt` policy options, and
   container guidance for untrusted workloads.

CAPTCHA bypass, fingerprint evasion, and automatic reuse of a user's logged-in
browser profile are deliberately not roadmap items. Those mechanisms weaken
consent and isolation boundaries and can violate service policies.

## Definition of evidence for future experiments

For a future external-site claim to become verified behavior, preserve:

1. the exact code revision and identity/capability configuration;
2. redacted runtime capability events and returned results;
3. an observable postcondition, such as a read-back of the created resource;
4. failure and recovery evidence;
5. a reproducible hermetic regression test where practical; and
6. confirmation after a fresh process when persistence is part of the claim.

External artifacts may supplement that evidence, but never replace it.
