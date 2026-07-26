#!/usr/bin/env python3
"""
Phase 3: Grow the identity — one capability at a time.

Each capability installation addresses specific limitations observed in Phase 1.
After each install we re-ask the same questions so the viewer sees exactly
what changed.
"""

import json, logging, os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

logging.basicConfig(level=logging.WARNING)
os.environ["LOGURU_LEVEL"] = "WARNING"

from runtime.orchestrator import IdentityRuntime, InteractionRequest
from runtime.main import adapter, register_default_criteria, storage

base_id = "evolve"
OUT_DIR = os.path.join(os.path.dirname(__file__), "output")
os.makedirs(OUT_DIR, exist_ok=True)

def banner(text):
    print()
    print("=" * 74)
    print(f"  {text}")
    print("=" * 74)

def ask(runtime, question):
    req = InteractionRequest(
        identity_id=base_id,
        user_input=question,
        session_id="demo_growth",
    )
    t0 = time.monotonic()
    resp = runtime.process(req)
    elapsed = time.monotonic() - t0
    return resp.output.strip(), round(elapsed, 1)

def skill_names(cap):
    info = cap.to_dict() if hasattr(cap, "to_dict") else {"skills": cap.skills()}
    return ", ".join(info.get("skills", []))

# Load base results for comparison
with open("demo/phase1_results.json") as f:
    phase1 = json.load(f)

# Build fresh runtime
runtime = IdentityRuntime(storage=storage, adapter=adapter)
register_default_criteria(runtime.evaluation_engine)
runtime.load_persisted()
runtime.load(base_id)

def base_answers(*domains):
    return [r for r in phase1 if r["domain"] in domains]

all_results = {}  # domain -> {before, after}

# ──────────────────────────────────────────────
# STEP 1: Install datetime
# ──────────────────────────────────────────────
banner("STEP 1: datetime — addresses 'I don't know the current date/time'")

cap = runtime.capability_registry.install(base_id, "datetime")
print(f"  Installed: {cap.id} — {len(cap.skills())} skills: {skill_names(cap)}")
print(f"  Solves: timezone lookup, date math, real-time clock")

for r in base_answers("datetime"):
    answer, elapsed = ask(runtime, r["question"])
    all_results.setdefault("datetime", {"before": {}, "after": {}})
    all_results["datetime"]["before"]["answer"] = r["answer"][:100]
    all_results["datetime"]["after"]["answer"] = answer[:200]
    print(f"\n  BEFORE: {r['answer'][:120]}...")
    print(f"  AFTER:  {answer[:250]}")

# ──────────────────────────────────────────────
# STEP 2: Install github
# ──────────────────────────────────────────────
banner("STEP 2: github — addresses 'I can't access GitHub data'")

cap = runtime.capability_registry.install(base_id, "github")
print(f"  Installed: {cap.id} — {len(cap.skills())} skills: {skill_names(cap)}")
print(f"  Solves: live repo stats, issue tracking, code search")

for r in base_answers("github"):
    answer, elapsed = ask(runtime, r["question"])
    print(f"\n  BEFORE: {r['answer'][:120]}...")
    print(f"  AFTER:  {answer[:350]}")

# ──────────────────────────────────────────────
# STEP 3: Install filesystem
# ──────────────────────────────────────────────
banner("STEP 3: filesystem — addresses 'I don't know what files exist'")

cap = runtime.capability_registry.install(base_id, "filesystem")
print(f"  Installed: {cap.id} — {len(cap.skills())} skills: {skill_names(cap)}")
print(f"  Solves: directory listing, file reading, metadata")

for r in base_answers("filesystem"):
    answer, elapsed = ask(runtime, r["question"])
    print(f"\n  BEFORE: {r['answer'][:120]}...")
    print(f"  AFTER:  {answer[:350]}")

# ──────────────────────────────────────────────
# STEP 4: Install system_info
# ──────────────────────────────────────────────
banner("STEP 4: system_info — addresses 'I don't know your OS or disk space'")

cap = runtime.capability_registry.install(base_id, "system_info")
print(f"  Installed: {cap.id} — {len(cap.skills())} skills: {skill_names(cap)}")
print(f"  Solves: OS detection, disk usage, CPU info")

for r in base_answers("system"):
    answer, elapsed = ask(runtime, r["question"])
    print(f"\n  BEFORE: {r['answer'][:120]}...")
    print(f"  AFTER:  {answer[:350]}")

# ──────────────────────────────────────────────
# STEP 5: Install weather
# ──────────────────────────────────────────────
banner("STEP 5: weather — addresses 'I don't know the weather'")

cap = runtime.capability_registry.install(base_id, "weather")
print(f"  Installed: {cap.id} — {len(cap.skills())} skills: {skill_names(cap)}")
print(f"  Solves: real-time weather, forecasts")

for r in base_answers("weather"):
    answer, elapsed = ask(runtime, r["question"])
    print(f"\n  BEFORE: {r['answer'][:120]}...")
    print(f"  AFTER:  {answer[:350]}")

# ──────────────────────────────────────────────
# STEP 6: Install web
# ──────────────────────────────────────────────
banner("STEP 6: web — addresses 'I can't fetch live web content'")

cap = runtime.capability_registry.install(base_id, "web")
print(f"  Installed: {cap.id} — {len(cap.skills())} skills: {skill_names(cap)}")
print(f"  Solves: HTTP fetching, content extraction")

for r in base_answers("web"):
    answer, elapsed = ask(runtime, r["question"])
    print(f"\n  BEFORE: {r['answer'][:120]}...")
    print(f"  AFTER:  {answer[:350]}")

# ──────────────────────────────────────────────
# SUMMARY
# ──────────────────────────────────────────────
banner("PHASE 3 COMPLETE: Identity Growth Trajectory")

all_installed = runtime.capability_registry.list(base_id)
print(f"\n  Identity: {base_id}")
print(f"  Capabilities installed: {len(all_installed)}")
print(f"  Total skills: {sum(len(c.skills()) for c in all_installed)}")
print(f"\n  Growth path:")
for i, c in enumerate(all_installed):
    info = c.to_dict() if hasattr(c, "to_dict") else {"id": c.id, "skills": c.skills()}
    sk = ", ".join(info.get("skills", []))
    print(f"    Step {i+1}: +{info.get('id', c.id)}")
    print(f"             skills: {sk}")

print(f"\n  What became possible:")
print(f"    Phase 1: Could only reason, could not sense the outside world")
print(f"    +datetime:   Knows real time, converts timezones, does date math")
print(f"    +github:     Queries live GitHub API — stars, issues, repos")
print(f"    +filesystem: Reads directories, file contents, metadata")
print(f"    +system_info:Detects OS, disk usage, CPU configuration")
print(f"    +weather:    Live Open-Meteo API — temperature, humidity, forecast")
print(f"    +web:        Fetches live web pages and extracts content")
print(f"\n  The identity at the end is objectively more capable than at the start.")
print(f"  Each installation added new abilities the LLM alone never had.")

runtime.capability_registry.persist(base_id)
print(f"\n  State saved for Phase 4.")
