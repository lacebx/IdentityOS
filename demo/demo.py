#!/usr/bin/env python3
"""
IdentityOS Demo: The identity reasons across decisions.

Two conversations. Two apps. One identity that connects them.
Not memory — reasoning about dependencies the user didn't notice.
"""

import sys
import os
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

    say(magenta('  >>> I need to ship something big to justify a promotion.\n'))
    time.sleep(0.3)
    say(magenta('  >>> Thinking of rewriting the payment service — it would look great in my review.\n'))
    time.sleep(0.3)

    r1 = runtime.process(InteractionRequest(
        identity_id=identity_id,
        user_input="I need to ship something big this quarter to justify my promotion. "
                   "I'm thinking of rewriting the payment service — it would look great in my review.",
        session_id="chatgpt-web",
    ))
    print(green(f"  {r1.output[:300]}"))
    print()

    # ── SCENE 2: Discord ─────────────────────────────────────────────
    print(dim("  ─────────────────────────────────────────────────────"))
    print(dim("  You close ChatGPT. Open Discord."))
    print(dim("  Discord has never seen the ChatGPT conversation."))
    print(dim("  ─────────────────────────────────────────────────────"))
    time.sleep(1)
    print()

    print(bold("  \033[38;5;33m●\033[0m Discord"))
    print()
    say(magenta('  >>> CTO just announced all non-critical work is frozen.\n'))
    time.sleep(0.3)
    say(magenta('  >>> My payment rewrite is shelved. That\'s the project I was counting on for the review.\n'))
    time.sleep(0.3)

    r2 = runtime.process(InteractionRequest(
        identity_id=identity_id,
        user_input="CTO just announced all non-critical work is frozen. "
                   "My payment rewrite is shelved. That was the project I was counting on for the promotion review.",
        session_id="discord-bot",
    ))
    print(green(f"  {r2.output[:300]}"))
    print()

    # ── THE REVEAL ────────────────────────────────────────────────────
    print(dim("  ─────────────────────────────────────────────────────"))
    time.sleep(0.5)
    say(yellow(bold("\n  Stop. Read those two conversations again.\n")), 0.04)
    time.sleep(0.3)
    print(dim("  ChatGPT: promotion depends on shipping the payment rewrite."))
    print(dim("  Discord:  payment rewrite is dead."))
    print(dim("  Neither app knows the other exists."))
    time.sleep(0.5)
    print()

    # ── SCENE 3: The intervention ────────────────────────────────────
    print(dim("  ─────────────────────────────────────────────────────"))
    print(dim("  Next day. You open a new workspace."))
    print(dim("  The identity has information from both conversations."))
    print(dim("  It doesn't wait to be asked."))
    print(dim("  ─────────────────────────────────────────────────────"))
    time.sleep(1)
    print()

    print(bold("  \033[38;5;33m●\033[0m Cursor (next day)"))
    print()
    say(magenta('  >>> What should I work on today?\n'))
    time.sleep(0.3)

    r3 = runtime.process(InteractionRequest(
        identity_id=identity_id,
        user_input="What should I work on today?",
        session_id="cursor-ide",
    ))
    print(green(f"  {r3.output[:600]}"))
    print()

    # ── THE SURPRISE REVEAL ──────────────────────────────────────────
    print(dim("  ─────────────────────────────────────────────────────"))
    time.sleep(0.5)
    say(yellow(bold("\n  Wait.\n")), 0.04)
    time.sleep(0.2)
    say(yellow("  I told ChatGPT about the promotion.\n"), 0.04)
    time.sleep(0.2)
    say(yellow("  I told Discord about the freeze.\n"), 0.04)
    time.sleep(0.2)
    say(yellow("  I never connected them.\n\n"), 0.04)
    time.sleep(0.3)
    say(yellow(bold("  The identity did.\n")), 0.04)
    time.sleep(0.5)

    # ── Conclusion ────────────────────────────────────────────────────
    print("\n" + "=" * 72)
    say(green("  ChatGPT decided a promotion depends on a project.\n"), 0.03)
    time.sleep(0.1)
    say(green("  Discord cancelled that project.\n"), 0.03)
    time.sleep(0.1)
    say(green("  Neither app alone had the full picture.\n"), 0.03)
    time.sleep(0.1)
    say(cyan("\n  The identity connected them — and concluded the plan was broken\n"), 0.03)
    say(cyan("  before the user realized it.\n"), 0.03)
    time.sleep(0.2)
    say(cyan("\n  That's not memory. That's reasoning across a life.\n"), 0.03)
    print()
    print(dim("  You can verify this is real state:"))
    print(dim("  identity inspect --id arsene"))
    print(dim('  identity explain arsene "promotion"'))
    print(dim('  identity explain arsene "shelved"'))
    print("=" * 72 + "\n")


if __name__ == "__main__":
    main()
