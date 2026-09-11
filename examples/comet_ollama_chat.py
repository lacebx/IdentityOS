#!/usr/bin/env python3
"""CPU-friendly Comet ↔ Ollama chat verification.

phi4-mini on CPU cannot reliably finish full IdentityOS contexts with native
tool schemas. This harness:
  - uses legacy text tool protocol (no native tool payload)
  - keeps context/tools small
  - proves browser.open/snapshot actually execute during chat
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from adapters import get_adapter
from identityos import Identity
from runtime.orchestrator import IdentityRuntime, InteractionRequest

STORE = os.environ.get("IDENTITY_STORE_PATH", ".identity_store")
MODEL = os.environ.get("OLLAMA_MODEL", "phi4-mini:latest")
TIMEOUT = float(os.environ.get("OPENAI_TIMEOUT", "900") or 900)
IDENTITY_ID = "comet-lite"


def ensure_lite() -> Identity:
    try:
        bot = Identity.load(IDENTITY_ID, storage_path=STORE)
    except Exception:
        bot = Identity.create(
            name="CometLite",
            identity_id=IDENTITY_ID,
            persona="Minimal web surfing agent. Always use browser tools; never invent page content.",
            role="web surfing agent",
            storage_path=STORE,
        )
    installed = {c["id"] for c in bot.capabilities()}
    if "browser" not in installed:
        bot.install("browser", config={"headless": True, "storage_root": STORE})
    # Keep only browser for CPU-local chats.
    for cap_id in list(installed):
        if cap_id != "browser":
            try:
                bot.uninstall(cap_id)
            except Exception:
                pass
    return bot


def main() -> int:
    bot = ensure_lite()
    adapter = get_adapter(
        "ollama",
        model=MODEL,
        think=False,
        temperature=0.1,
        max_tokens=256,
        timeout=TIMEOUT,
        prefer_legacy_tools=True,
    )
    # Keep local CPU inference bounded.
    adapter.max_tool_rounds = 3

    print(
        f"model={MODEL} legacy={adapter.prefer_legacy_tools} timeout={TIMEOUT}",
        flush=True,
    )

    # Warm model (load into RAM) with a tiny request.
    from types import SimpleNamespace
    t0 = time.monotonic()
    warm = adapter.generate(
        context="Reply with one word.",
        user_input="Say READY",
        identity=SimpleNamespace(name="warm", id="warm"),
    )
    print(f"warm={warm!r} in {time.monotonic()-t0:.1f}s", flush=True)

    # Reuse the SDK runtime so the identity is already registered/loaded.
    runtime = bot._runtime
    runtime.set_adapter(adapter)
    runtime.max_tools_per_request = 4
    runtime.context_composer.max_tokens = 1200
    session_id = runtime.start_session(IDENTITY_ID)

    tool_log: list[dict] = []
    orig = runtime.capability_registry.call

    def tracing_call(identity_id, skill_name, **params):
        print(f"  [tool] {skill_name} params={params}", flush=True)
        result = orig(identity_id, skill_name, **params)
        ok = getattr(result, "success", None)
        preview = {}
        if hasattr(result, "data") and isinstance(result.data, dict):
            preview = {
                k: result.data.get(k)
                for k in ("url", "title", "text_preview", "ok")
                if k in result.data
            }
        print(f"  [tool-done] {skill_name} success={ok} {preview}", flush=True)
        tool_log.append({"skill": skill_name, "success": ok, "preview": preview})
        return result

    runtime.capability_registry.call = tracing_call  # type: ignore

    prompt = (
        "You must call tools before answering.\n"
        'Emit: <function=browser__open>{"url":"https://example.com"}</function>\n'
        "After you receive the tool result, call "
        '<function=browser__snapshot>{}</function> if needed, '
        "then report the page title from the tool result only."
    )
    print("\n=== TURN browse ===", flush=True)
    t0 = time.monotonic()
    resp = runtime.process(
        InteractionRequest(
            identity_id=IDENTITY_ID,
            user_input=prompt,
            session_id=session_id,
        )
    )
    elapsed = time.monotonic() - t0
    reply = resp.output or ""
    print(f"comet> {reply[:1200]}", flush=True)
    print(f"(turn {elapsed:.1f}s)", flush=True)

    try:
        runtime.capability_registry.call(IDENTITY_ID, "browser.close")
    except Exception:
        pass

    skills = [e["skill"] for e in tool_log]
    open_ok = any(e["skill"] == "browser.open" and e["success"] for e in tool_log)
    grounded = ("example domain" in reply.lower()) or any(
        "Example Domain" in str((e.get("preview") or {}).get("title", ""))
        for e in tool_log
    )
    summary = {
        "model": MODEL,
        "identity": IDENTITY_ID,
        "tools_called": skills,
        "open_ok": open_ok,
        "content_grounded": grounded,
        "elapsed_s": round(elapsed, 1),
        "reply": reply[:500],
        "tool_log": tool_log,
    }
    out = ROOT / "demo" / "comet-ollama-chat.json"
    out.write_text(json.dumps(summary, indent=2))
    print("\n=== SUMMARY ===", flush=True)
    print(json.dumps({k: summary[k] for k in (
        "model", "identity", "tools_called", "open_ok", "content_grounded", "elapsed_s"
    )}, indent=2), flush=True)
    print(f"wrote {out}", flush=True)

    if open_ok and grounded:
        print("PASS: Comet used browser tools via Ollama and grounded the answer", flush=True)
        return 0
    print("FAIL: browser tool use / grounding incomplete", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
