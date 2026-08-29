"""
test_restart_continuity.py — Evidence 2: Restart Continuity

Core vision claim: An identity's memories and conversation history survive
a full runtime shutdown and restart, enabling the identity to recall prior
conversations after being reloaded.

Test flow:
  1. Create identity with Groq, hold a multi-turn conversation building
     personal context (name, plans, preferences)
  2. Destroy the runtime entirely
  3. Create a fresh runtime, load the same identity from storage
  4. Ask a continuity question requiring recall of Phase 1
  5. Verify the response references the prior conversation

This proves: identity is persistent, not ephemeral.
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


def _make_runtime(store_dir):
    storage = JSONFileBackend(root_dir=store_dir)

    from adapters.groq_adapter import GroqAdapter
    adapter = GroqAdapter(model="openai/gpt-oss-120b", max_tokens=256)

    rt = IdentityRuntime(storage=storage, adapter=adapter)
    register_default_criteria(rt.evaluation_engine)
    return rt


class TestRestartContinuity:
    """Identity remembers prior conversations after full restart."""

    def test_conversation_survives_restart(self, store_dir):
        # ── Phase 1: Build conversation history ─────────────────────
        rt_a = _make_runtime(store_dir)
        spec = create_identity(
            name="ContinuityBot",
            identity_id="continuity-bot",
            persona="A helpful assistant that remembers everything about the user",
        )
        rt_a.register(spec)

        sid = rt_a.start_session("continuity-bot")

        # Turn 1: Introduce name and trip plan
        resp1 = rt_a.process(InteractionRequest(
            identity_id="continuity-bot",
            user_input="Hi! My name is Alice and I'm planning a trip to Japan next month.",
            session_id=sid,
        ))
        assert resp1.policy_passed, f"Turn 1 failed: {resp1.output}"

        # Turn 2: Add details
        resp2 = rt_a.process(InteractionRequest(
            identity_id="continuity-bot",
            user_input="I'm most excited about trying the street food in Tokyo.",
            session_id=sid,
        ))
        assert resp2.policy_passed, f"Turn 2 failed: {resp2.output}"

        # Turn 3: Another detail
        resp3 = rt_a.process(InteractionRequest(
            identity_id="continuity-bot",
            user_input="I also want to visit Kyoto for the temples.",
            session_id=sid,
        ))
        assert resp3.policy_passed, f"Turn 3 failed: {resp3.output}"

        rt_a = None  # destroy runtime A — full shutdown

        # ── Phase 2: Fresh runtime, same storage ────────────────────
        rt_b = _make_runtime(store_dir)
        loaded = rt_b.load_persisted()
        assert loaded >= 1, "No identities loaded from persistence"

        sid2 = rt_b.start_session("continuity-bot")
        resp4 = rt_b.process(InteractionRequest(
            identity_id="continuity-bot",
            user_input=(
                "Do you remember our previous conversation? "
                "What is my name, where am I going, "
                "and what am I most excited about?"
            ),
            session_id=sid2,
        ))
        assert resp4.policy_passed, f"Continuity check failed: {resp4.output}"

        output = resp4.output.lower()
        assert "alice" in output, f"Didn't recall name.\nOutput: {resp4.output}"
        assert "japan" in output, f"Didn't recall destination.\nOutput: {resp4.output}"
        assert "tokyo" in output or "food" in output or "street" in output, (
            f"Didn't recall excitement details.\nOutput: {resp4.output}"
        )
