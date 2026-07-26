#!/usr/bin/env python3
"""
IdentityOS Product Demo

One conversation. Two apps. Zero setup.
The identity connects ideas across workspaces because it lives
in the runtime, not in any single application.
"""

import sys
import os
import subprocess
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from runtime.persistence import JSONFileBackend
from runtime.orchestrator import IdentityRuntime, InteractionRequest
from runtime.main import register_default_criteria
from core.identity import create_identity


def dim(t): return f"\033[2m{t}\033[0m"
def bold(t): return f"\033[1m{t}\033[0m"
def cyan(t): return f"\033[36m{t}\033[0m"
def green(t): return f"\033[32m{t}\033[0m"
def magenta(t): return f"\033[35m{t}\033[0m"
def yellow(t): return f"\033[33m{t}\033[0m"


def say(text, delay=0.02):
    for c in text:
        print(c, end="", flush=True)
        time.sleep(delay)
    print()


def main():
    identity_id = "arsene"

    # ── Init ──────────────────────────────────────────────────────────
    storage = JSONFileBackend(root_dir=".identity_store")
    runtime = IdentityRuntime(storage=storage)
    register_default_criteria(runtime.evaluation_engine)
    from adapters.groq_adapter import GroqAdapter
    runtime.adapter = GroqAdapter()
    spec = create_identity(name="Arsene", identity_id=identity_id)
    runtime.register(spec)
    runtime.load(identity_id)

    # ── SCENE 1: ChatGPT ─────────────────────────────────────────────
    print("\n" + "=" * 72)
    print(bold("  \033[38;5;40m●\033[0m ChatGPT"))
    print("=" * 72)
    print()

    say(magenta('  >>> I want to learn Japanese before moving to Tokyo.\n'))
    time.sleep(0.3)
    say(magenta('  >>> I found a course for $200 but I\'m trying to save $1,800 for the move.\n'))
    time.sleep(0.3)

    msg1 = "I want to learn Japanese before moving to Tokyo. I found a great course for $200 but I'm trying to save $1,800 for the move."
    r1 = runtime.process(InteractionRequest(
        identity_id=identity_id, user_input=msg1, session_id="chatgpt-web",
    ))
    print(green(f"  {r1.output[:300]}"))
    print()

    # ── SCENE 2: Discord ─────────────────────────────────────────────
    print(dim("  ─────────────────────────────────────────────────────"))
    print(dim("  You close ChatGPT. Open Discord."))
    print(dim("  Discord has never seen this conversation."))
    print(dim("  It knows nothing about Japanese, $200, or $1,800."))
    print(dim("  ─────────────────────────────────────────────────────"))
    time.sleep(1)
    print()

    print(bold("  \033[38;5;33m●\033[0m Discord"))
    print()
    say(magenta('  >>> Any advice for this week?\n'))
    time.sleep(0.3)

    r2 = runtime.process(InteractionRequest(
        identity_id=identity_id, user_input="Any advice for this week?", session_id="discord-bot",
    ))
    print(green(f"  {r2.output[:400]}"))
    print()

    # ── THE REVEAL ────────────────────────────────────────────────────
    print(dim("  ─────────────────────────────────────────────────────"))
    time.sleep(0.5)
    say(yellow(bold("\n  Wait. I never told Discord about the savings goal.\n")), 0.04)
    time.sleep(0.3)
    say(yellow("  I never told it about the Japanese course.\n"), 0.04)
    time.sleep(0.3)
    say(yellow("  It connected those two things on its own.\n\n"), 0.04)
    time.sleep(0.5)

    # ── SCENE 3: The Synthesis Surprise ──────────────────────────────
    print(dim("  ─────────────────────────────────────────────────────"))
    print(dim("  One week passes. Same Discord channel."))
    print(dim("  The identity now has: Tokyo move, Japanese goal, savings goal."))
    print(dim("  It notices something the user hasn't."))
    print(dim("  ─────────────────────────────────────────────────────"))
    time.sleep(1)
    print()

    print(bold("  \033[38;5;33m●\033[0m Discord (one week later)"))
    print()
    say(magenta('  >>> I have some free time this weekend. What should I do?\n'))
    time.sleep(0.3)

    r3 = runtime.process(InteractionRequest(
        identity_id=identity_id,
        user_input="I have some free time this weekend. What should I do?",
        session_id="discord-bot",
    ))
    print(green(f"  {r3.output[:500]}"))
    print()

    # ── THE SURPRISE REVEAL ───────────────────────────────────────────
    print(dim("  ─────────────────────────────────────────────────────"))
    time.sleep(0.5)
    say(yellow(bold("\n  Wait. I never asked about housing.\n")), 0.04)
    time.sleep(0.3)
    say(yellow("  It noticed the gap on its own.\n\n"), 0.04)
    time.sleep(0.5)

    # ── Inspect (brief) ─────────────────────────────────────────────
    print(dim("  ─────────────────────────────────────────────────────"))
    print(dim("  What the identity actually knows internally:"))
    print(dim("  ─────────────────────────────────────────────────────"))
    time.sleep(0.3)

    result = subprocess.run(
        [sys.executable, "tools/identity", "inspect", identity_id],
        capture_output=True, text=True,
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    )
    for line in result.stdout.split("\n"):
        if not line.startswith("INFO:"):
            print(line)

    # ── Conclusion ────────────────────────────────────────────────────
    print("\n" + "=" * 72)
    say(green("  The identity connected two facts from one conversation\n"), 0.03)
    say(green("  and applied them in a completely different app.\n"), 0.03)
    time.sleep(0.2)
    say(green("  Then it noticed a gap the user hadn't seen.\n"), 0.03)
    time.sleep(0.2)
    say(cyan("\n  That's not memory sync. That's a persistent assistant.\n"), 0.03)
    print()
    print(dim("  python3 tools/identity inspect arsene"))
    print(dim('  python3 tools/identity explain arsene "savings"'))
    print(dim('  python3 tools/identity explain arsene "housing"'))
    print("=" * 72 + "\n")


if __name__ == "__main__":
    main()
