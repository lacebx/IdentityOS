# Browser capability

The optional `browser` capability gives an identity an evidence-producing
Chromium session for web search, navigation, page inspection, and interaction.
It is routed through the normal IdentityOS capability registry and permission
gateway. A model response by itself is never treated as proof that a browser
action happened.

## Installation

Install the Python extra and Chromium once in the IdentityOS environment:

```bash
pip install -e ".[browser]"
playwright install chromium
```

Then install the capability directly or through the Surfer ISP pack:

```bash
identity cap install browser --identity gabe
# Or:
identity isp install surfer --identity gabe
```

No browser-specific environment variable is required. The selected model still
uses the normal provider configuration. `OPENAI_TIMEOUT` can be set to a finite,
positive number of seconds when an OpenAI-compatible local endpoint such as
Ollama needs more than the 120-second default.

## Usage

Start a normal chat and state the web task:

```bash
identity chat --id gabe
```

For example, ask the identity to search for primary documentation, open a
promising result, and summarize only what it observes. The model can route the
request through these runtime skills:

- `browser.search` and `browser.evaluate_results`
- `browser.open`, `browser.navigate`, and `browser.snapshot`
- `browser.click`, `browser.type`, `browser.fill`, and `browser.press`
- `browser.wait`, `browser.status`, and `browser.close`
- `browser.login`, after the separate credential grant described below

Search results include a task-relative usefulness score. Page claims should be
grounded in the returned search or snapshot evidence.

## Permissions and credentials

Installation grants ordinary `browser:read` and `browser:write` control. Login
is unavailable until the user explicitly grants the narrower credential
permission:

```bash
identity cap grant browser --identity gabe --permission browser:credentials
```

Supply a chat credential with an explicit `password=<value>` field. Before the
model, event stream, memory, timeline, or debugger sees the message, the runtime
replaces that value with an ephemeral reference. Plaintext is resolved only
inside the capability gateway for that interaction. Invented plaintext from a
model is rejected, and recorded capability parameters remain redacted.

A login call is successful only when its requested postcondition is observed,
such as a destination URL or selector. Submitting a form is not success
evidence by itself.

## Isolation and network policy

Profiles are isolated by storage root, identity, and user execution scope. A
shared Playwright driver may host multiple contexts, but identities and users
do not share browser state. Uninstalling the capability closes its sessions,
removes only its bounded identity profile directory, and revokes its grants.

Only external HTTP(S) destinations are allowed by default. File URLs,
loopback, link-local, and private-network targets are rejected to limit local
file access and server-side request forgery. Controlled test environments can
opt in with capability configuration:

```json
{"allow_private_network": true}
```

Do not enable private-network access for an identity that should browse only
the public internet.

## Security threat model

The protected assets are provider credentials, user login secrets, local files
and services, per-user browser state, and the integrity of execution evidence.
The capability assumes that page content and model output are untrusted.

| Threat | Runtime mitigation | Residual responsibility |
|---|---|---|
| Model invents or echoes a credential | Only ephemeral references created from explicit user input resolve; recorded parameters are redacted | Users should provide credentials only for an authorized login |
| Page or prompt claims an action succeeded | Skill results and postconditions establish success independently of model prose | Callers should inspect returned evidence for sensitive actions |
| Navigation reaches local files or services | File, loopback, link-local, and private-network destinations are denied by default | Operators must not enable private access for public browsing identities |
| One user receives another user browser state | Profile and context keys include storage root, identity, and execution scope | Applications must pass stable, distinct user IDs |
| Uninstall deletes unrelated data | Cleanup is bounded to the installed identity browser directory | Operators should configure `storage_root` to an IdentityOS-owned location |
| Browser dependency is unavailable or a page action fails | The capability returns structured failure evidence and does not synthesize success | Callers should retry only when the failure is recoverable |

Chromium is not a general operating-system sandbox. The URL policy and
capability permission boundary reduce exposure, but operators should still run
untrusted autonomous workloads with ordinary host/container isolation and
least-privilege credentials.

## Compatibility and removal

The capability is opt-in. Existing identities and deployments are unchanged
until `browser` or the Surfer pack is installed. Existing capability calls stay
compatible because execution scope is optional at the registry boundary and is
supplied by the runtime when a user session exists.

To remove browser access and its persisted profile through the SDK:

```python
from identityos import Identity

Identity.load("gabe").uninstall("browser")
```

## Verification

The browser CI job installs real Chromium and exercises install, permissions,
navigation, snapshots, user isolation, close, uninstall, and restart behavior
against a hermetic local site. Security tests separately cover denied URLs,
credential brokering, redaction, login postconditions, and rejection of
model-invented credentials.
