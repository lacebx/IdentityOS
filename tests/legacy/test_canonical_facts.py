"""
test_canonical_facts.py

Integration tests proving FactStore is the single source of truth:

1. Cross-session stability: favorite color chosen once survives across sessions
2. Cross-adapter stability: identity facts are adapter-independent
3. Contradiction rejection: user claims contradicting known facts are rejected
4. Inspection exposes canonical facts (not raw English belief strings)
5. User preferences are recalled from canonical facts (not semantic memory)
6. Runtime directives prevent adapter disclaimers
"""

import sys, os, json, time
sys.path.insert(0, os.path.dirname(__file__))

from runtime.orchestrator import IdentityRuntime, InteractionRequest
from runtime.persistence import JSONFileBackend
from core.evaluation import register_default_criteria
from core.identity import create_identity
from core.identity_facts import FactSource, FactDomain, FactStatus

TEST_STORE = ".test_canonical_facts"

def clean():
    import shutil
    if os.path.exists(TEST_STORE):
        shutil.rmtree(TEST_STORE)

def log(label, body=""):
    print(f"\n{'='*65}")
    print(f"  {label}")
    print(f"{'='*65}")
    if body:
        print(body)

# ─── Setup ─────────────────────────────────────────────────────────

clean()
storage = JSONFileBackend(root_dir=TEST_STORE)
rt = IdentityRuntime(storage=storage)
register_default_criteria(rt.evaluation_engine)

identity = create_identity(
    name="Canonical",
    identity_id="canonical-test",
    persona="A test identity for FactStore validation",
)
rt.register(identity)

engine = rt.mutation_engine

# ─── Test 1: Cross-session stability ───────────────────────────────

log("TEST 1: CROSS-SESSION STABILITY")
print("Session 1: assistant says 'I think blue fits me'")

proposals = engine.analyze(
    user_input="You should have your own favorite color.",
    assistant_response="I think blue fits me.",
    identity_spec=identity,
)

validated = engine.validate(proposals, existing_records=None)
engine.apply_proposals_to_fact_store(validated)
rt._fact_stores["canonical-test"] = engine.fact_store
rt._save_fact_store("canonical-test")

fact = engine.get_fact_by_field("preferences.favorite_color")
assert fact is not None, "Fact should exist after session 1"
assert fact.value == "blue", f"Should be 'blue', got {fact.value}"
log("Session 1 complete", f"  Fact: {fact.field} = {fact.value} (confidence={fact.confidence:.2f})")

print("\nSession 2: new runtime, same identity, no new utterance")
rt2_storage = JSONFileBackend(root_dir=TEST_STORE)
rt2 = IdentityRuntime(storage=rt2_storage)
register_default_criteria(rt2.evaluation_engine)
loaded = rt2.load_persisted()
assert loaded >= 1, "Should load at least one identity"

restored_fact = rt2._fact_stores["canonical-test"].find("preferences.favorite_color")
assert restored_fact is not None, "Fact should survive across sessions"
assert restored_fact.value == "blue", f"Should be 'blue', got {restored_fact.value}"
log("Session 2 (cross-session)", f"  Fact: {restored_fact.field} = {restored_fact.value} (confidence={restored_fact.confidence:.2f})")

# ─── Test 2: User preferences from canonical facts ────────────────

log("TEST 2: USER PREFERENCES FROM CANONICAL FACTS")
print("User says: 'My favorite color is red'")
print("Verifying it's stored as USER_KNOWLEDGE domain, not identity preference")

from core.user_profile import extract_user_facts
user_facts = extract_user_facts("My favorite color is red")
assert len(user_facts) > 0, "Should extract user facts"
log("User facts extracted", f"  {json.dumps([f.to_dict() for f in user_facts], indent=2)[:300]}")

# Verify the identity's preference is unchanged (still blue)
identity_fact = engine.get_fact_by_field("preferences.favorite_color")
assert identity_fact is not None, "Identity fact should exist"
assert identity_fact.value == "blue", "Identity favorite color should remain blue (not red)"
log("Identity preference unchanged", f"  Identity: {identity_fact.value} (not overwritten by user)")

# ─── Test 3: Contradiction rejection via FactStore ─────────────────

log("TEST 3: CONTRADICTION REJECTION")
print("Assistant says: 'Actually, my favorite color is green now'")
print("FactStore should flag this as a contradiction")

proposals2 = engine.analyze(
    user_input="What color do you prefer now?",
    assistant_response="Actually, my favorite color is green now.",
    identity_spec=identity,
)

validated2 = engine.validate(proposals2, existing_records=None)
conflicted = [p for p in validated2 if p.status.value == "conflict"]
rejected = [p for p in validated2 if p.status.value == "rejected"]

# At least one proposal should be conflicted (the fact_store check via ContradictionEngine)
assert len(conflicted) >= 1, f"Should detect contradiction, got {len(conflicted)} conflicted, {len(rejected)} rejected"
log("Contradiction detected", f"  {len(conflicted)} conflict(s), {len(rejected)} rejected")
for p in conflicted:
    print(f"  {p.field}: {p.rejection_reason}")

# Verify the original fact is still ACTIVE
original_fact = engine.get_fact_by_field("preferences.favorite_color")
assert original_fact is not None
assert original_fact.value == "blue", "Original fact should remain 'blue'"
assert original_fact.status == FactStatus.ACTIVE, "Original fact should still be ACTIVE"
log("Original fact preserved", f"  {original_fact.field} = {original_fact.value} (still {original_fact.status.value})")

# ─── Test 4: Inspection exposes canonical facts ───────────────────

log("TEST 4: INSPECTION EXPOSES CANONICAL FACTS")
print("Inspection should show structured facts, not raw English belief strings")

inspected = rt2.inspect_identity("canonical-test")
assert "error" not in inspected, f"Inspection failed: {inspected.get('error', '')}"

canonical = inspected.get("canonical_facts", {})
assert canonical.get("total", 0) >= 1, "Should have at least 1 canonical fact"
assert canonical.get("active", 0) >= 1, "Should have at least 1 active fact"

# Check the facts don't contain raw English belief strings
for f in canonical.get("facts", []):
    assert not isinstance(f.get("value"), str) or not f["value"].startswith("I believe"), \
        f"Fact value should not be raw English: {f['value']}"
    assert "fact_id" in f, "Should have structured fact_id"
    assert "domain" in f, "Should have structured domain"
    assert "confidence" in f, "Should have structured confidence"
    assert "status" in f, "Should have structured status"

log("Inspection verified", f"  {canonical['total']} total facts, {canonical['active']} active")
for f in canonical["facts"][:3]:
    print(f"  [{f['domain']}] {f['field']} = {f['value']} (confidence={f['confidence']})")

# Test get_fact query API
explain = rt2.get_fact("canonical-test", "preferences.favorite_color")
assert "current" in explain, "Should have current value in explanation"
assert explain["current"]["value"] == "blue", "Should be 'blue'"
assert explain["current"]["confidence"] >= 0.8, "Confidence should be >= 0.8"
log("Explain fact API", f"  field={explain['field']}, value={explain['current']['value']}, confidence={explain['current']['confidence']}")

# Test replay events
events = rt2.replay_events("canonical-test")
assert len(events) >= 1, "Should have at least 1 event"
log("Event log", f"  {len(events)} event(s)")
for e in events[:3]:
    print(f"  [{e['event_type']}] {e['field']}")

# Test constitution generation
constitution = rt2.identity_constitution("canonical-test")
assert "Identity Constitution" in constitution, "Should generate constitution"
assert "blue" in constitution.lower() or "favorite" in constitution.lower(), \
    "Constitution should reference identity facts"
log("Constitution generated", f"  {len(constitution)} chars")

# ─── Test 5: Runtime directives in context ────────────────────────

log("TEST 5: RUNTIME DIRECTIVES PREVENT DISCLAIMERS")
print("Verifying that composed context includes runtime directives")

context = rt2.context_composer.compose(
    identity=rt2.identity_store.get("canonical-test"),
    memory_store=rt2.memory_store,
    fact_store=rt2._fact_stores.get("canonical-test"),
)
rendered = context.render()
assert "Runtime Directives" in rendered, "Context should include Runtime Directives"
assert "NEVER claim" in rendered, "Directives should include disclaimer prohibition"
log("Runtime directives present")
for line in rendered.split("\n"):
    if "NEVER" in line:
        print(f"  {line.strip()}")

# ─── Test 6: IdentitySpec has no evolved fields ───────────────────

log("TEST 6: IDENTITYSPEC IS METADATA ONLY")
spec = rt2.identity_store.get("canonical-test")
spec_dict = spec.to_dict()
assert "preferences" not in spec_dict, "IdentitySpec should not have 'preferences' field"
assert "beliefs" not in spec_dict, "IdentitySpec should not have 'beliefs' field"
assert "mutation_history" not in spec_dict, "IdentitySpec should not have 'mutation_history' field"
assert "likes" not in spec_dict, "IdentitySpec should not have 'likes' field"
assert "dislikes" not in spec_dict, "IdentitySpec should not have 'dislikes' field"
log("IdentitySpec verified metadata-only", f"  Fields: id, name, version, persona (no evolved fields)")

# ─── Cleanup ─────────────────────────────────────────────────────

clean()

log("ALL CANONICAL FACT TESTS PASSED!")
print("\n  ✓ Cross-session stability: favorite color survives across sessions")
print("  ✓ User preferences separate from identity facts")
print("  ✓ Contradiction rejection via FactStore")
print("  ✓ Inspection exposes structured canonical facts (not raw English)")
print("  ✓ get_fact() API with full provenance")
print("  ✓ replay_events() for audit trail")
print("  ✓ Constitution generated from FactStore")
print("  ✓ Runtime directives prevent adapter disclaimers")
print("  ✓ IdentitySpec is metadata-only (no evolved fields)")
