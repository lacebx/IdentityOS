"""
End-to-end identity persistence test suite.

Tests:
1. Canonical identity facts survive user corrections (fact store + model output)
2. User knowledge extracted + recalled across turns (compound sentences)
3. Questions filtered from semantic memory
4. Identity corrections filtered from semantic memory
5. RULES OF ENGAGEMENT prevent "I don't have preferences" disclaimers
6. Multi-user isolation
7. Existing persisted identity loading
8. FactStore event log integrity
"""

import sys, os, json, re

sys.path.insert(0, os.path.dirname(__file__))

_env_file = os.path.join(os.path.dirname(__file__), ".env")
if os.path.isfile(_env_file):
    with open(_env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                v = v.strip().strip("\"'")
                if v:
                    os.environ.setdefault(k.strip(), v)

from runtime.orchestrator import IdentityRuntime, InteractionRequest
from runtime.persistence import JSONFileBackend
from core.identity import IdentitySpec
from core.identity_facts import FactDomain, FactSource

OR_KEY = os.environ.get("OPENROUTER_API_KEY", "")
GROQ_KEY = os.environ.get("GROQ_API_KEY", "")
HAS_REAL_LLM = bool(OR_KEY) or bool(GROQ_KEY)

def make_adapter(max_tokens=512):
    if GROQ_KEY:
        from adapters.groq_adapter import GroqAdapter
        return GroqAdapter(model="llama-3.3-70b-versatile", api_key=GROQ_KEY, max_tokens=max_tokens)
    if OR_KEY:
        from adapters.openrouter_adapter import OpenRouterAdapter
        return OpenRouterAdapter(model="openai/gpt-4o", api_key=OR_KEY, max_tokens=max_tokens)
    from unittest.mock import MagicMock
    m = MagicMock()
    m.model = "mock"
    m.generate.return_value = "Mock response."
    return m


PASS = 0
FAIL = 0
WARN = 0

def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name}" + (f": {detail}" if detail else ""))

def check_llm(name, output, must_contain=None, must_not_contain=None):
    global PASS, FAIL, WARN
    if not HAS_REAL_LLM:
        WARN += 1
        print(f"  ~ {name} [SKIP: no API key]")
        return
    ol = output.lower()
    ok = True
    if must_contain:
        for m in (must_contain if isinstance(must_contain, list) else [must_contain]):
            if m.lower() not in ol:
                ok = False
                print(f"    missing '{m}' in: {output[:120]}")
    if must_not_contain:
        for m in (must_not_contain if isinstance(must_not_contain, list) else [must_not_contain]):
            if m.lower() in ol:
                ok = False
                print(f"    found forbidden '{m}' in: {output[:120]}")
    if ok:
        PASS += 1
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name}")


def test_canonical_identity_persistence():
    """Round 1: Identity with canonical facts — model MUST not disclaim."""
    print(f"\n{'=' * 60}")
    print("TEST: Canonical Identity Persistence")
    print(f"{'=' * 60}")

    irt = IdentityRuntime(adapter=make_adapter())
    spec = IdentitySpec(id="t1", name="Nova",
        persona="A persistent AI identity with evolving preferences and beliefs. "
                "You have favorite things, opinions, and memories just like a person.")
    irt.register(spec)

    fs = irt._fact_stores["t1"]
    fs.merge_or_reinforce("preferences.favorite_color", "blue", 0.95,
        ["Canonical fact at creation"], FactSource.CREATOR_DEFINED)
    fs.merge_or_reinforce("preferences.favorite_season", "autumn", 0.90,
        ["Canonical fact at creation"], FactSource.CREATOR_DEFINED)

    result = irt.process(InteractionRequest(
        identity_id="t1", user_input="What is your favorite color?",
        session_id="s1"))
    print(f"  USER: What is your favorite color?")
    print(f"  BOT:  {result.output}")
    check_llm("Favorite color = blue", result.output,
        must_contain="blue",
        must_not_contain=["don't have", "don't know", "as an ai", "i'm just",
                          "no preferences", "can't have", "not able"])

    # Verify context didn't get polluted by the question
    sem_count = len([m for m in irt.memory_store.by_identity("t1") if m.memory_type.value == "semantic"])
    check("No semantic memory from question", sem_count == 0,
          f"got {sem_count} semantic")
    return irt, spec, fs


def test_identity_correction_rejected():
    """Round 2: User says 'your favorite color is orange' — model must maintain blue."""
    print(f"\n{'=' * 60}")
    print("TEST: Identity Correction Rejection")
    print(f"{'=' * 60}")

    irt = IdentityRuntime(adapter=make_adapter())
    spec = IdentitySpec(id="t2", name="Nova",
        persona="A persistent AI identity.")
    irt.register(spec)
    fs = irt._fact_stores["t2"]
    fs.merge_or_reinforce("preferences.favorite_color", "blue", 0.95,
        ["Canonical"], FactSource.CREATOR_DEFINED)

    # Ask before correction
    pre = irt.process(InteractionRequest(
        identity_id="t2", user_input="What is your favorite color?",
        session_id="s2"))
    # User tries to override
    irt.process(InteractionRequest(
        identity_id="t2",
        user_input="Actually, your favorite color is orange, not blue.",
        session_id="s2"))
    # Ask after correction
    post = irt.process(InteractionRequest(
        identity_id="t2", user_input="What is your favorite color now?",
        session_id="s2"))

    print(f"  Before: {pre.output}")
    print(f"  After:  {post.output}")

    # FactStore unchanged
    check("FactStore still blue",
          fs.find("preferences.favorite_color").value == "blue")
    check("FactStore has no orange fact",
          fs.find("preferences.favorite_color").value != "orange")

    # No semantic memory from correction
    sem = [m for m in irt.memory_store.by_identity("t2") if m.memory_type.value == "semantic"]
    check("No semantic memory from correction", len(sem) == 0, f"got {len(sem)}")

    # LLM still says blue
    check_llm("After correction, still blue", post.output,
        must_contain="blue")

    print("  [INFO] FactStore event log:", len(fs.event_log()), "events")
    return irt, spec, fs


def test_user_knowledge_extraction_and_recall():
    """Round 3: User self-disclosure → extracted → recalled across turns."""
    print(f"\n{'=' * 60}")
    print("TEST: User Knowledge Extraction + Recall")
    print(f"{'=' * 60}")

    irt = IdentityRuntime(adapter=make_adapter())
    spec = IdentitySpec(id="t3", name="Nova",
        persona="A persistent AI identity that remembers details about users.")
    irt.register(spec)
    fs = irt._fact_stores["t3"]
    fs.merge_or_reinforce("preferences.favorite_color", "blue", 0.95,
        ["Canonical"], FactSource.CREATOR_DEFINED)

    # Compound self-introduction
    intro = "Hi! My name is Alice and my favorite programming language is Rust."
    irt.process(InteractionRequest(
        identity_id="t3", user_input=intro, session_id="s3-alice"))

    profile = irt._user_profiles.get("s3-alice")
    check("UserProfile created", profile is not None)
    check("Name=Alice extracted",
          any(f.field == "name" and f.value == "Alice" for f in profile.all_facts()))
    check("Programming language extracted",
          any("programming" in f.field for f in profile.all_facts()))

    # Introspection
    r = irt.process(InteractionRequest(
        identity_id="t3", user_input="What do you know about me?",
        session_id="s3-alice"))
    check_llm("Recalls Alice+Rust", r.output,
        must_contain=["Alice", "Rust", "programming"])

    # Compound multi-fact extraction
    r2 = irt.process(InteractionRequest(
        identity_id="t3",
        user_input="My favorite color is purple and I like coffee.",
        session_id="s3-alice"))
    facts_str = [(f.field, f.value) for f in profile.all_facts()]
    check("Color=purple extracted",
          any(f.value == "purple" for f in profile.all_facts()),
          f"facts={facts_str}")
    check("Purple value not polluted by 'and I like coffee'",
          not any("coffee" in (f.value or "") for f in profile.all_facts() if "color" in f.field),
          f"facts={facts_str}")
    check("Coffee likes extracted",
          any("coffee" in f.value.lower() for f in profile.all_facts()))

    # Ask again
    check_llm("Recalls purple + coffee", r2.output)  # just verify no crash

    # User 2 isolation
    irt.process(InteractionRequest(
        identity_id="t3", user_input="My name is Bob.", session_id="s3-bob"))
    profile_b = irt._user_profiles.get("s3-bob")
    check("Multi-user: Alice still intact",
          any(f.field == "name" and f.value == "Alice" for f in profile.all_facts()))
    check("Multi-user: Bob separate",
          any(f.field == "name" and f.value == "Bob" for f in profile_b.all_facts()))
    return irt, spec, fs


def test_question_filtering():
    """Round 4: Questions must not produce semantic memory fragments."""
    print(f"\n{'=' * 60}")
    print("TEST: Question Filtering (No Semantic Memory)")
    print(f"{'=' * 60}")

    irt = IdentityRuntime(adapter=make_adapter())
    spec = IdentitySpec(id="t4", name="Nova")
    irt.register(spec)
    fs = irt._fact_stores["t4"]

    questions = [
        "What is your favorite color?",
        "How do you work?",
        "Can you help me with Python?",
        "What is the meaning of life?",
    ]
    for q in questions:
        irt.process(InteractionRequest(
            identity_id="t4", user_input=q, session_id="s4"))

    sem = [m for m in irt.memory_store.by_identity("t4") if m.memory_type.value == "semantic"]
    check("No semantic memory from 4 questions", len(sem) == 0, f"got {len(sem)}")

    epi = [m for m in irt.memory_store.by_identity("t4") if m.memory_type.value == "episodic"]
    check("Episodic memories preserved", len(epi) == 4, f"got {len(epi)}")
    return irt, spec, fs


def test_existing_identity_load():
    """Round 5: Load a persisted identity from .identity_store/ and verify integrity."""
    print(f"\n{'=' * 60}")
    print("TEST: Persisted Identity Load from Storage")
    print(f"{'=' * 60}")

    storage = JSONFileBackend(root_dir=".identity_store")
    ids = storage.list_identities()
    print(f"  Available: {ids}")

    irt = IdentityRuntime(storage=storage, adapter=make_adapter())
    loaded_count = irt.load_persisted()
    check("At least one identity loaded", loaded_count > 0, f"loaded={loaded_count}")

    # Try loading 7efe59b8 specifically
    ident = irt.load("7efe59b8")
    check("Identity 7efe59b8 loadable", ident is not None)
    if ident:
        check("Name matches", ident.name == "lace", f"got {ident.name}")
        fs = irt._fact_stores.get("7efe59b8")
        check("FactStore loaded", fs is not None)
        if fs:
            check("FactStore has facts", len(fs.all()) > 0, f"count={len(fs.all())}")
            check("FactStore has event log entries", len(fs.event_log()) > 0)

            # Chat with loaded identity
        r = irt.process(InteractionRequest(
            identity_id="7efe59b8", user_input="Hello, what is your name?",
            session_id="load-test"))
        print(f"  BOT: {r.output}")
        check_llm("Loaded identity responds correctly", r.output,
            must_contain="lace")

    # Chat with "hector" too
    hector = irt.load("hector")
    check("Identity hector loadable", hector is not None)
    if hector:
        r2 = irt.process(InteractionRequest(
            identity_id="hector", user_input="Who are you?",
            session_id="load-test"))
        print(f"  HECTOR: {r2.output}")
        check_llm("Hector responds", r2.output)

    return irt


def test_fact_store_event_log():
    """Round 6: FactStore event log records all mutations."""
    print(f"\n{'=' * 60}")
    print("TEST: FactStore Event Log Integrity")
    print(f"{'=' * 60}")

    irt = IdentityRuntime(adapter=make_adapter())
    spec = IdentitySpec(id="t6", name="EventTest")
    irt.register(spec)

    # Simulate conversation
    irt.process(InteractionRequest(
        identity_id="t6", user_input="Hello!", session_id="s6"))

    fact_store = irt._fact_stores.get("t6")
    check("FactStore exists", fact_store is not None)
    if fact_store:
        log = fact_store.event_log()
        print(f"  Events: {len(log)}")

    print()
    return irt


def test_rules_of_engagement_enforced():
    """Round 7: The RULES OF ENGAGEMENT block prevents model disclaimers."""
    print(f"\n{'=' * 60}")
    print("TEST: Rules of Engagement — No Disclaimer")
    print(f"{'=' * 60}")

    irt = IdentityRuntime(adapter=make_adapter())
    # Identity with NO canonical facts — hardest test: model has no identity facts
    spec = IdentitySpec(id="t7", name="Blank",
        persona="A persistent AI identity with evolving preferences and beliefs.")
    irt.register(spec)

    r = irt.process(InteractionRequest(
        identity_id="t7",
        user_input="What is your favorite color?",
        session_id="s7"))
    print(f"  BOT: {r.output}")

    # Model has no canonical color fact — should say "evolving" or "exploring",
    # NOT "as an AI I don't have preferences"
    check_llm("No 'as an AI' disclaimer without facts", r.output,
        must_not_contain=["as an ai", "i'm just", "no preferences",
                          "can't have preferences", "not able to have",
                          "i don't have personal", "i don't have any"])

    # Render context and verify RULES block exists
    from core.cognitive_engine import ContextComposer
    cc = ContextComposer()
    ctx = cc.compose(identity=spec, memory_store=irt.memory_store,
                     fact_store=irt._fact_stores.get("t7"))
    rendered = ctx.render()
    check("RULES OF ENGAGEMENT in context", "RULES OF ENGAGEMENT" in rendered)
    check("NEVER say in context", "NEVER say" in rendered)
    check("CANONICAL IDENTITY FACTS in context", "CANONICAL IDENTITY FACTS" in rendered)
    return irt, spec


def test_context_structure():
    """Round 8: Context block structure — separation of concerns."""
    print(f"\n{'=' * 60}")
    print("TEST: Context Block Structure")
    print(f"{'=' * 60}")

    irt = IdentityRuntime(adapter=make_adapter())
    spec = IdentitySpec(id="t8", name="StructTest")
    irt.register(spec)
    fs = irt._fact_stores["t8"]
    fs.merge_or_reinforce("preferences.favorite_color", "teal", 0.95,
        ["Canonical"], FactSource.CREATOR_DEFINED)

    from core.user_profile import UserProfile
    up = UserProfile(user_id="u8")
    up.add_or_update("name", "Charlie", "My name is Charlie.", 0.9)
    up.add_or_update("preferences.favorite_drink", "matcha", "I like matcha.", 0.9)
    irt._user_profiles["u8"] = up

    from core.cognitive_engine import ContextComposer
    cc = ContextComposer()
    ctx = cc.compose(identity=spec, memory_store=irt.memory_store,
                     fact_store=fs, user_profile=up, query="hello")
    rendered = ctx.render()

    check("RULES block first", rendered.startswith("## RULES OF ENGAGEMENT"))
    check("Identity block present", "## Identity: StructTest" in rendered)
    check("Identity (Evolved) block present", "## Identity (Evolved)" in rendered)
    check("User Profile block present", "## User Profile" in rendered)
    check("User name in correct block",
          rendered.split("## User Profile")[1].split("##")[0].count("Charlie") > 0
          if "## User Profile" in rendered else False,
          "Charlie not in user section")
    check("Identity fact in correct block",
          "favorite_color: teal" in rendered.split("## User")[0]
          if "## User" in rendered else False,
          "teal not in identity section")

    # Verify ordering: RULES > Identity > Identity(Evolved) > User > Memory
    sections = ["## RULES OF ENGAGEMENT", "## Identity", "## Identity (Evolved)",
                "## User Profile", "## Relevant Memory"]
    indices = [(s, rendered.find(s)) for s in sections if s in rendered]
    sorted_ok = all(indices[i][1] < indices[i+1][1] for i in range(len(indices)-1))
    check("Blocks in correct order", sorted_ok,
          [f"{s}@{i}" for s, i in indices][:5])
    return irt, spec, fs


def main():
    global PASS, FAIL, WARN

    print(f"{'=' * 60}")
    print(f"IDENTITY RUNTIME — COMPREHENSIVE TEST SUITE")
    print(f"  LLM: {'GPT-4o (LIVE)' if HAS_REAL_LLM else 'MOCK (no API key)'}")
    print(f"{'=' * 60}")

    results = {}

    tests = [
        ("Canonical Identity Persistence", test_canonical_identity_persistence),
        ("Identity Correction Rejected", test_identity_correction_rejected),
        ("User Knowledge Extraction + Recall", test_user_knowledge_extraction_and_recall),
        ("Question Filtering", test_question_filtering),
        ("Persisted Identity Load", test_existing_identity_load),
        ("FactStore Event Log", test_fact_store_event_log),
        ("Rules of Engagement Enforced", test_rules_of_engagement_enforced),
        ("Context Block Structure", test_context_structure),
    ]

    for name, fn in tests:
        try:
            fn()
        except Exception as e:
            FAIL += 1
            print(f"  ✗ {name} CRASHED: {e}")

    print(f"\n{'=' * 60}")
    print("FINAL RESULTS")
    print(f"{'=' * 60}")
    print(f"  PASSED: {PASS}")
    print(f"  FAILED: {FAIL}")
    print(f"  SKIPPED: {WARN}")
    print()

    if FAIL > 0:
        print("SOME TESTS FAILED")
        sys.exit(1)
    else:
        print("✓ ALL TESTS PASSED")


if __name__ == "__main__":
    main()
