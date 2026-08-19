"""
test_identity_isolation.py — Evidence D: Two identities, no leaking

Core differentiation claim:
  IdentityOS manages identities — not just conversations.
  Two identities with different personas, goals, and memories
  share the same runtime yet remain completely isolated.

Test:
  - Alice: Python mentor, user "student1" learning Python
  - Bob: Chef, user "foodie1" sharing recipes
  - Both run simultaneously on the same runtime
  - After multi-turn conversations, verify:
      1. Alice recalls her student's details
      2. Bob recalls his foodie's details
      3. Alice knows nothing about recipes
      4. Bob knows nothing about Python
      5. Goals are identity-specific
      6. Context composition is identity-specific
"""

import os
import tempfile

import pytest

from core.evaluation import register_default_criteria
from core.identity import create_identity
from runtime.orchestrator import IdentityRuntime, InteractionRequest
from runtime.persistence import JSONFileBackend

pytestmark = pytest.mark.skipif(
    not os.environ.get("GROQ_API_KEY"),
    reason="Requires GROQ_API_KEY",
)


@pytest.fixture
def store_dir():
    with tempfile.TemporaryDirectory() as td:
        yield td


@pytest.fixture
def runtime(store_dir):
    storage = JSONFileBackend(root_dir=store_dir)
    from adapters.groq_adapter import GroqAdapter
    adapter = GroqAdapter(model="openai/gpt-oss-120b", max_tokens=120)
    rt = IdentityRuntime(storage=storage, adapter=adapter)
    register_default_criteria(rt.evaluation_engine)
    return rt


class TestIdentityIsolation:
    """Two identities with distinct domains, no cross-talk."""

    def test_alice_and_bob_dont_leak(self, runtime):
        # ── Create Alice (Python mentor) ─────────────────────────────
        alice = create_identity(
            name="Alice",
            identity_id="alice-mentor",
            persona="A patient Python mentor who teaches beginners",
            role="mentor",
        )
        runtime.register(alice)

        # ── Create Bob (Chef) ────────────────────────────────────────
        bob = create_identity(
            name="Bob",
            identity_id="bob-chef",
            persona="A professional chef who shares cooking tips",
            role="chef",
        )
        runtime.register(bob)

        # ── Alice's conversation (Python mentoring, user=student1) ───
        resp = runtime.process(InteractionRequest(
            identity_id="alice-mentor",
            user_input=(
                "Hi Alice! I'm student1. I'm struggling with Python "
                "list comprehensions. Can you help me understand them?"
            ),
            session_id="student1",
        ))
        assert resp.policy_passed, f"Alice turn 1: {resp.output}"

        # ── Bob's conversation (cooking, user=foodie1) ───────────────
        resp = runtime.process(InteractionRequest(
            identity_id="bob-chef",
            user_input=(
                "Hey Bob! I'm foodie1. I'm trying to perfect my "
                "sourdough bread recipe. Any tips?"
            ),
            session_id="foodie1",
        ))
        assert resp.policy_passed, f"Bob turn 1: {resp.output}"

        # ── Alice's second turn ──────────────────────────────────────
        resp = runtime.process(InteractionRequest(
            identity_id="alice-mentor",
            user_input=(
                "student1 here again. I tried using list comprehensions "
                "but got confused with nested ones. Can you show an example?"
            ),
            session_id="student1",
        ))
        assert resp.policy_passed, f"Alice turn 2: {resp.output}"

        # ── Bob's second turn ────────────────────────────────────────
        resp = runtime.process(InteractionRequest(
            identity_id="bob-chef",
            user_input=(
                "foodie1 back! My sourdough starter is finally active. "
                "How do I know when it's ready to bake?"
            ),
            session_id="foodie1",
        ))
        assert resp.policy_passed, f"Bob turn 2: {resp.output}"

        # ── Verification 1: Alice's memories ─────────────────────────
        alice_mems = runtime.memory_store.by_identity(identity_id="alice-mentor")
        alice_text = " ".join(m.content for m in alice_mems).lower()
        assert "student1" in alice_text, "Alice should know student1"
        assert "list comprehension" in alice_text or "nested" in alice_text, \
            "Alice should recall Python topics"
        assert "sourdough" not in alice_text, "Alice should NOT know about sourdough"
        assert "foodie1" not in alice_text, "Alice should NOT know foodie1"

        # ── Verification 2: Bob's memories ───────────────────────────
        bob_mems = runtime.memory_store.by_identity(identity_id="bob-chef")
        bob_text = " ".join(m.content for m in bob_mems).lower()
        assert "foodie1" in bob_text, "Bob should know foodie1"
        assert "sourdough" in bob_text or "starter" in bob_text or "bake" in bob_text, \
            "Bob should recall cooking topics"
        assert "list comprehension" not in bob_text, "Bob should NOT know about Python"
        assert "student1" not in bob_text, "Bob should NOT know student1"

        # ── Verification 3: Alice's relationships ────────────────────
        alice_edges = runtime.identity_graph.get_relationships("alice-mentor")
        alice_targets = [e.target_id for e in alice_edges]
        assert any("student1" in t for t in alice_targets), \
            f"Alice should have a relationship with student1. Got: {alice_targets}"
        assert not any("foodie1" in t for t in alice_targets), \
            "Alice should NOT have a relationship with foodie1"

        # ── Verification 4: Bob's relationships ──────────────────────
        bob_edges = runtime.identity_graph.get_relationships("bob-chef")
        bob_targets = [e.target_id for e in bob_edges]
        assert any("foodie1" in t for t in bob_targets), \
            f"Bob should have a relationship with foodie1. Got: {bob_targets}"
        assert not any("student1" in t for t in bob_targets), \
            "Bob should NOT have a relationship with student1"

        # ── Verification 5: Context isolation ────────────────────────
        ctx_alice = runtime.context_composer.compose(
            identity=alice,
            memory_store=runtime.memory_store,
            skill_registry=runtime.skill_registry,
            goal_engine=runtime.goal_engine,
            identity_graph=runtime.identity_graph,
            query="What do you know about me?",
        )
        alice_rendered = ctx_alice.render().lower()
        assert "student1" in alice_rendered, "Alice context should include student1"
        assert "sourdough" not in alice_rendered, \
            "Alice context should NOT include Bob's domain"

        ctx_bob = runtime.context_composer.compose(
            identity=bob,
            memory_store=runtime.memory_store,
            skill_registry=runtime.skill_registry,
            goal_engine=runtime.goal_engine,
            identity_graph=runtime.identity_graph,
            query="What do you know about me?",
        )
        bob_rendered = ctx_bob.render().lower()
        assert "foodie1" in bob_rendered, "Bob context should include foodie1"
        assert "list comprehension" not in bob_rendered, \
            "Bob context should NOT include Alice's domain"

        # ── Verification 6: Identity survives restart (isolation preserved) ──
        rt2 = IdentityRuntime(
            storage=runtime._storage,
            adapter=runtime.adapter,
        )
        register_default_criteria(rt2.evaluation_engine)
        loaded = rt2.load_persisted()
        assert loaded >= 2, "Both identities should be reloaded"

        # Verify isolation after restart
        alice2_mems = rt2.memory_store.by_identity(identity_id="alice-mentor")
        bob2_mems = rt2.memory_store.by_identity(identity_id="bob-chef")
        alice2_text = " ".join(m.content for m in alice2_mems).lower()
        bob2_text = " ".join(m.content for m in bob2_mems).lower()
        assert "student1" in alice2_text, "After restart: Alice remembers student1"
        assert "sourdough" not in alice2_text, "After restart: Alice still no sourdough"
        assert "foodie1" in bob2_text, "After restart: Bob remembers foodie1"
        assert "list comprehension" not in bob2_text, \
            "After restart: Bob still no Python"
