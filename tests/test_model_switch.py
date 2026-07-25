"""
test_model_switch.py — Evidence B: Seamless model switch mid-conversation

Core differentiation claim:
  You can swap the underlying LLM model mid-conversation and the identity
  continues as if nothing changed. No memory loss. No restart. No export.

Test:
  1. Share personal facts with the identity via one model
  2. Swap to a different model on the same adapter
  3. Ask a continuity question requiring recall of phase 1
  4. Verify the response shows continuity
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


class TestModelSwitch:
    """Swapping the model mid-conversation preserves continuity."""

    def test_facts_survive_model_swap(self, store_dir):
        storage = JSONFileBackend(root_dir=store_dir)

        # ── Phase 1: Chat with one Groq model ───────────────────────
        from adapters.groq_adapter import GroqAdapter
        adapter_a = GroqAdapter(model="llama-3.3-70b-versatile", max_tokens=100)

        rt = IdentityRuntime(storage=storage, adapter=adapter_a)
        register_default_criteria(rt.evaluation_engine)

        spec = create_identity(
            name="SwitchBot",
            identity_id="switch-bot",
            persona="A helpful assistant with a good memory",
        )
        rt.register(spec)

        resp = rt.process(InteractionRequest(
            identity_id="switch-bot",
            user_input=(
                "My name is Alex. I'm a web developer and "
                "my favorite framework is FastAPI."
            ),
            session_id="alex-session",
        ))
        assert resp.policy_passed, f"Phase 1 failed: {resp.output}"

        # ── Phase 2: Swap to a different model ON THE SAME RUNTIME ──
        adapter_b = GroqAdapter(
            model="llama-3.1-8b-instant",
            max_tokens=100,
        )
        rt.adapter = adapter_b  # Hot-swap the adapter while runtime keeps running

        resp = rt.process(InteractionRequest(
            identity_id="switch-bot",
            user_input=(
                "I also love hiking and my dog's name is Max."
            ),
            session_id="alex-session",
        ))
        assert resp.policy_passed, f"Phase 2 failed: {resp.output}"

        # ── Phase 3: Verify continuity with the new model ───────────
        resp = rt.process(InteractionRequest(
            identity_id="switch-bot",
            user_input=(
                "Do you remember our conversation? "
                "What is my name, what do I do, "
                "what's my favorite framework, and what's my dog's name?"
            ),
            session_id="alex-session",
        ))
        assert resp.policy_passed, f"Phase 3 failed: {resp.output}"

        output = resp.output.lower()
        assert "alex" in output, f"Didn't recall name.\nOutput: {resp.output}"
        assert "web developer" in output or "developer" in output, (
            f"Didn't recall occupation.\nOutput: {resp.output}"
        )
        assert "fastapi" in output, f"Didn't recall framework.\nOutput: {resp.output}"
        assert "max" in output, f"Didn't recall dog name.\nOutput: {resp.output}"
