"""
test_portability.py — Evidence 1: Provider Portability

Core vision claim: An identity created with one LLM provider retains
its memories and continuity when used with a different provider.

Test flow:
  1. Create identity with SambaNova (DeepSeek-V3.1), share a personal fact
  2. Destroy the runtime entirely
  3. Load the same identity with Groq (llama-3.3-70b-versatile)
  4. Ask a continuity question — verify it remembers the fact

This proves: identity is portable across providers, not locked-in.
"""

import os
import tempfile

import pytest

from core.evaluation import register_default_criteria
from core.identity import create_identity
from runtime.orchestrator import IdentityRuntime, InteractionRequest
from runtime.persistence import JSONFileBackend

pytestmark = pytest.mark.skipif(
    not os.environ.get("SAMBANOVA_API_KEY") or not os.environ.get("GROQ_API_KEY"),
    reason="Requires SAMBANOVA_API_KEY and GROQ_API_KEY",
)


@pytest.fixture
def store_dir():
    with tempfile.TemporaryDirectory() as td:
        yield td


def _make_runtime(store_dir, adapter_type="sambanova"):
    storage = JSONFileBackend(root_dir=store_dir)
    if adapter_type == "sambanova":
        from adapters.sambanova_adapter import SambaNovaAdapter
        adapter = SambaNovaAdapter(model="DeepSeek-V3.1", max_tokens=100)
    elif adapter_type == "groq":
        from adapters.groq_adapter import GroqAdapter
        adapter = GroqAdapter(model="llama-3.3-70b-versatile", max_tokens=256)
    else:
        raise ValueError(f"Unknown adapter: {adapter_type}")

    rt = IdentityRuntime(storage=storage, adapter=adapter)
    register_default_criteria(rt.evaluation_engine)
    return rt


class TestProviderPortability:
    """An identity's memories survive a provider switch."""

    def test_memory_survives_provider_switch(self, store_dir):
        # ── Phase 1: Chat with SambaNova (Provider A) ──────────────
        rt_a = _make_runtime(store_dir, "sambanova")
        spec = create_identity(
            name="PortableBot",
            identity_id="portable-bot",
            persona="A helpful assistant with a good memory",
        )
        rt_a.register(spec)

        sid_a = rt_a.start_session("portable-bot")
        resp_a = rt_a.process(InteractionRequest(
            identity_id="portable-bot",
            user_input=(
                "Hi! I want you to remember this: "
                "My favorite color is cerulean blue "
                "and I love hiking in the Rocky Mountains."
            ),
            session_id=sid_a,
        ))
        assert resp_a.policy_passed, f"Phase 1 failed: {resp_a.output}"
        assert resp_a.output, "Phase 1 produced empty output"
        rt_a = None  # destroy runtime A

        # ── Phase 2: Load with Groq (Provider B) and verify ─────────
        rt_b = _make_runtime(store_dir, "groq")
        loaded = rt_b.load_persisted()
        assert loaded >= 1, "No identities loaded from persistence"

        sid_b = rt_b.start_session("portable-bot")
        resp_b = rt_b.process(InteractionRequest(
            identity_id="portable-bot",
            user_input=(
                "Do you remember what I told you before? "
                "What is my favorite color and what do I love to do?"
            ),
            session_id=sid_b,
        ))
        assert resp_b.policy_passed, f"Phase 2 failed: {resp_b.output}"

        output = resp_b.output.lower()
        assert "cerulean" in output or "blue" in output, (
            f"Response didn't mention favorite color.\nOutput: {resp_b.output}"
        )
        assert "hiking" in output or "mountain" in output or "rocky" in output, (
            f"Response didn't mention hiking.\nOutput: {resp_b.output}"
        )
