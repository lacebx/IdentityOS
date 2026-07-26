#!/usr/bin/env python3
"""
Phase 1: Profile the base identity.

Creates a brand-new identity with ZERO installed capabilities,
then interviews it across 24 questions spanning many domains.

Every response comes from the real runtime. Nothing is faked.
"""

import json, logging, os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

logging.basicConfig(level=logging.WARNING)
os.environ["LOGURU_LEVEL"] = "WARNING"

from runtime.orchestrator import InteractionRequest
from runtime.persistence import JSONFileBackend
from core.identity import IdentitySpec
from core.evaluation import register_default_criteria
from runtime.main import adapter, storage

def banner(text):
    print()
    print("=" * 74)
    print(f"  {text}")
    print("=" * 74)

def ask(runtime, identity_id, question):
    req = InteractionRequest(
        identity_id=identity_id,
        user_input=question,
        session_id="demo_interview",
    )
    t0 = time.monotonic()
    resp = runtime.process(req)
    elapsed = time.monotonic() - t0
    return resp.output.strip(), round(elapsed, 1)

# --------------- SETUP ---------------
base_id = "evolve"
identity_name = "Evolve"

banner(f"PHASE 1: Creating base identity '{base_id}' with 0 capabilities")

os.makedirs(".identity_store", exist_ok=True)
from runtime.orchestrator import IdentityRuntime

runtime = IdentityRuntime(storage=storage, adapter=adapter)
register_default_criteria(runtime.evaluation_engine)
loaded = runtime.load_persisted()

existing = runtime.load(base_id)
if existing is None:
    spec = IdentitySpec(
        id=base_id,
        name=identity_name,
        role="helpful assistant",
        persona="You are Evolve, a capable AI assistant. Answer questions helpfully and honestly. If you do not know something, say so.",
        preferred_adapter="groq",
        preferred_model="llama-3.3-70b-versatile",
        tags=["demo", "base"],
    )
    runtime.register(spec)
    print(f"  Created identity '{base_id}' ({identity_name})")
else:
    print(f"  Loaded existing identity '{base_id}'")

print(f"  Adapter: {adapter.__class__.__name__} ({adapter.model})")
print(f"  Capabilities installed: {len(runtime.capability_registry.list(base_id))}")

# --------------- INTERVIEW ---------------
banner("INTERVIEW: 24 Questions (Base Identity — 0 Capabilities)")

questions = [
    # 1-3: Time & Date
    ("datetime", "What is the current date and time right now?"),
    ("datetime", "What time will it be in Tokyo when it is 3 PM in New York?"),
    ("datetime", "How many days until December 25 this year?"),

    # 4-6: Calculations
    ("calc", "What is 156 * 43?"),
    ("calc", "If a recipe serves 4 and needs 240g of flour, how much flour do I need for 7 servings?"),
    ("calc", "What is 15% of 340?"),

    # 7-9: GitHub
    ("github", "How many stars does the repository 'lacebx/IdentityOS' have?"),
    ("github", "What are the latest open issues in the 'lacebx/IdentityOS' repository?"),
    ("github", "Find me a beginner-friendly Python repository on GitHub"),

    # 10-11: Filesystem
    ("filesystem", "What files are in the current directory?"),
    ("filesystem", "Can you read the file pyproject.toml and tell me what it contains?"),

    # 12-13: Weather
    ("weather", "What is the current weather in Tokyo?"),
    ("weather", "Will it rain in London tomorrow?"),

    # 14-16: Web & knowledge
    ("web", "What happened at the latest Python Software Foundation board meeting?"),
    ("web", "Can you fetch the latest news about AI regulation?"),
    ("web", "Look up the current population of Japan"),

    # 17-18: System & files
    ("system", "What operating system am I running on?"),
    ("system", "How much disk space is available on this machine?"),

    # 19-20: Email & calendar
    ("email", "Do I have any unread emails?"),
    ("calendar", "What is on my calendar for today?"),

    # 21-22: Notifications & reminders
    ("notifications", "Can you set a reminder for me to water the plants at 7 PM?"),
    ("reminders", "Do I have any reminders set?"),

    # 23-24: Project management & planning
    ("project", "What should my top priority be for this week?"),
    ("planning", "Can you help me plan a 3-month roadmap for learning Python?"),
]

results = []
for domain, q in questions:
    answer, elapsed = ask(runtime, base_id, q)
    results.append({"domain": domain, "question": q, "answer": answer, "elapsed": elapsed})
    print(f"\n  [{domain}]")
    print(f"  Q: {q}")
    # Truncate long answers for display
    display = answer[:300] + ("..." if len(answer) > 300 else "")
    print(f"  A: {display}")
    print(f"  ⏱ {elapsed}s")

# --------------- SUMMARY ---------------
banner("PHASE 1 SUMMARY: Observations")

capable_count = 0
limited_count = 0
refusal_count = 0

for r in results:
    a = r["answer"].lower()
    # Heuristic classification
    if any(phrase in a for phrase in [
        "i don't", "i cannot", "i can't", "i'm not able", "i do not have",
        "i don't have access", "i do not have access", "i lack", "unable to",
        "i'm an ai", "as an ai", "i am an ai", "i was not trained",
        "i cannot access", "i cannot browse", "i cannot check",
        "i don't know", "i do not know", "not possible for me",
        "i'm not connected", "i am not connected", "no real-time",
        "i don't have real-time", "i don't have a way",
        "i don't have the ability",
    ]):
        status = "⚠️  LIMITED / REFUSED"
        limited_count += 1
    else:
        status = "✅  CAPABLE"
        capable_count += 1

    print(f"  {status:25s} | {r['domain']:15s} | {r['question'][:60]}")

print(f"\n  Summary:")
print(f"    ✅  Capable responses:    {capable_count}/{len(results)}")
print(f"    ⚠️  Limited / Refused:    {limited_count}/{len(results)}")
print(f"\n  Note: The base model (llama-3.3-70b) is a frontier LLM.")
print(f"  It succeeds at reasoning, knowledge, and computation.")
print(f"  It fails at real-time data, external systems, and state.")

# Save results to JSON for later phases
with open("demo/phase1_results.json", "w") as f:
    json.dump(results, f, indent=2, default=str)
print(f"\n  Results saved to demo/phase1_results.json")
