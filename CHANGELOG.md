# Changelog

All notable changes to this project are documented here.

## [Unreleased]

### Added

- **Live Firefox bridge** (`browser.live.*`): identities can drive the user's
  real Firefox through the `@identityos/live-browser-bridge` WebExtension and
  native messaging host. See `docs/live-browser-bridge.md` for setup, usage,
  and security boundaries.
- **Named OpenAI-compatible providers**: configure multiple endpoints at once
  with `OPENAI_<NAME>_API_KEY`, `OPENAI_<NAME>_BASE_URL`, and
  `OPENAI_<NAME>_MODEL`. Providers are discovered side-effect-free from the
  environment. `list_configured_openai_providers()` returns the configured
  providers (name, display_name, base_url, model, is_local) for UI selection.
  See `docs/openai_providers.md`.

### Changed

- **Backward compatibility kept**: legacy `OPENAI_API_KEY`, `OPENAI_BASE_URL`,
  `OPENAI_MODEL`, `OLLAMA_API_KEY`, and `OLLAMA_MODEL` still select the
  `openai`/`ollama` providers exactly as before.
- **Credential brokering**: model tool calls must supply credentials as
  ephemeral `secret-ref://` references. Only credential-aware skills such as
  `browser.login` may resolve them; generic automation (`browser.fill`,
  `browser.eval_js`, ...) rejects them.

### Testing

- `tests/test_live_bridge_e2e.py` spawns the real two-process bridge
  (`native_host.py` SERVER + `--relay`) over stdio pipes and exercises
  status/list_tabs/active_tab, command forwarding, disconnect errors, and
  large frames; no Firefox is required.
- `tests/test_native_host.py` covers the exact-read/exact-write framing
  helpers under partial pipe and socket reads.
- `tests/test_adapter_configuration.py` covers provider discovery, legacy
  env combinations, local-endpoint (Ollama) selection, and routing of named
  providers to dedicated adapters.
- `tests/test_orchestrator.py` verifies the runtime wiring change, and
  `tests/test_sensitive.py` verifies `secret-ref://` brokering rules.

### Risk and rollback

- Additive by default: existing single-provider setups, legacy env vars, and
  `browser.*` behavior are unchanged unless the new `browser.live.*` scopes or
  named providers are used.
- The `runtime/orchestrator.py` change is session-scoped secret bookkeeping
  only (merge on session resolution, consume on successful tool call, clear on
  session end); it delegates policy to `runtime/sensitive.py` and is covered
  by tests.
- The bridge fails safe: when Firefox is not connected, requests return an
  explicit error instead of a silent success, and the native host never
  evaluates shell or dynamic code.
- Rolling back is removing the branch; no data migrations or state format
  changes are introduced.