# IdentityOS Browser Bridge

The Manifest V3 extension carries one user-selected identity across ChatGPT,
Claude, Gemini, Grok, GitHub, Reddit, and YouTube. It works in Chrome and Edge;
the included Gecko manifest metadata supports current Firefox releases.

## Setup

1. Start IdentityOS: `uvicorn runtime.main:app --host 127.0.0.1 --port 8000`.
2. Open the browser extension-development page.
3. Load this `extension/` directory as an unpacked/temporary extension.
4. Select an identity in the popup.
5. Enable only the sites that should receive identity access.

If `IDENTITY_API_KEY` is enabled on the runtime, enter the same key in the
popup. The key is stored only in browser-local extension storage.

## Privacy model

- Site access is explicit and independently configurable.
- ChatGPT, Claude, Gemini, and Grok can receive private identity context in
  their chat composer.
- GitHub, Reddit, and YouTube default to disabled. When enabled, they show a
  private identity sidecar; identity context is never inserted into a public
  post or comment.
- Platform memory partitioning is enabled by default, so one site's user
  profile is not automatically visible to another. Disable it only when shared
  cross-site continuity is intentional.
- Context is cached locally for offline continuity. Evaluations that cannot be
  delivered are queued and retried when the runtime is reachable. The queue is
  capped at 200 entries.

The background worker is the only component that talks to IdentityOS. Content
scripts do not contain runtime URLs, API keys, or user identifiers.
