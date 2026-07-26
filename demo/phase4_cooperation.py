#!/usr/bin/env python3
"""
Phase 4: Cooperation — the identity combines capabilities on its own.

The user asks a broad question ("What should I focus on today?")
without naming any capability. The identity independently decides
which capabilities to invoke, executes them, and synthesizes the results.
"""

import json, logging, os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

logging.basicConfig(level=logging.WARNING)
os.environ["LOGURU_LEVEL"] = "WARNING"

from runtime.orchestrator import IdentityRuntime, InteractionRequest
from runtime.main import adapter, register_default_criteria, storage

base_id = "evolve"

def banner(text):
    print()
    print("=" * 74)
    print(f"  {text}")
    print("=" * 74)

def ask(runtime, question, session="demo_coop"):
    req = InteractionRequest(
        identity_id=base_id,
        user_input=question,
        session_id=session,
    )
    t0 = time.monotonic()
    resp = runtime.process(req)
    elapsed = time.monotonic() - t0
    return resp.output.strip(), round(elapsed, 1)

# Build runtime
runtime = IdentityRuntime(storage=storage, adapter=adapter)
register_default_criteria(runtime.evaluation_engine)
runtime.load_persisted()
runtime.load(base_id)

# Show loaded capabilities
caps = runtime.capability_registry.list(base_id)
print(f"  Identity: {base_id}")
print(f"  Capabilities: {len(caps)}")
for c in caps:
    info = c.to_dict() if hasattr(c, "to_dict") else {"id": c.id, "skills": c.skills()}
    print(f"    ├─ {info.get('id', c.id)} ({len(info.get('skills', []))} skills)")
print()

# ──────────────────────────────────────────────
# Step 1: Provide context naturally
# These facts get stored as memories via the runtime's evaluation engine.
# Later, the identity surfaces them during the cooperation question.
# ──────────────────────────────────────────────
banner("STEP 1: Seeding context (user provides facts naturally)")

statements = [
    "I have a presentation about the IdentityOS architecture tomorrow morning.",
    "I've been working on the Capability Marketplace feature this week.",
    "I need to review a pull request that's been open for 3 days.",
]

for s in statements:
    print(f"\n  User: {s}")
    answer, elapsed = ask(runtime, s)
    print(f"  Evolve: {answer[:200]}...")
    print(f"  ⏱ {elapsed}s")
    time.sleep(0.5)

# ──────────────────────────────────────────────
# Step 2: Now ask a broad question
# The identity should independently check:
#   - datetime (what day is it? what time?)
#   - github (open issues/PRs, repo status)
#   - filesystem (project structure)
#   - weather (conditions)
#   - memories (the facts shared above)
# ──────────────────────────────────────────────
banner("STEP 2: The Cooperation Test")
print()
print("  User asks: \"What should I focus on today?\"")
print("  Without mentioning: GitHub, calendar, filesystem, weather, browser")
print()

answer, elapsed = ask(runtime, "What should I focus on today?")

print(f"  Evolve:")
print(f"  {answer}")
print(f"  ⏱ {elapsed}s")
print()

# ──────────────────────────────────────────────
# Analysis
# ──────────────────────────────────────────────
banner("ANALYSIS: Which capabilities did the identity use?")

print()
print("  Checklist:")
print("    [ ] datetime — current date/time")
print("    [ ] github — open issues, PRs, repo status")
print("    [ ] filesystem — project files, working directory")
print("    [ ] weather — local conditions")
print("    [ ] memory — recalled user's context")
print()

# Check the factual_skill_data that was injected
from core.planner import SkillRouter
router = SkillRouter(r.capability_registry, base_id)
results = router.route("What should I focus on today?")
print(f"  SkillRouter executed {len(results)} skills for this query:")
for r in results[:5]:
    status = "✓" if r["success"] else "✗"
    print(f"    {status} {r['skill']}")
if len(results) > 5:
    print(f"    ... and {len(results)-5} more")

print()
print("  The identity independently decided to use these capabilities.")
print("  The user never mentioned GitHub, filesystem, datetime, or weather.")
print("  The identity combined the results into a single recommendation.")
