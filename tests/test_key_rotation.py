"""
Tests for automatic API key rotation and cooldown handling in the
Groq / SambaNova / Cerebras adapters.

Uses mocked HTTP responses so tests are fast and need no real API keys.
"""

from __future__ import annotations

import sys
import time
from unittest.mock import MagicMock, patch

import pytest

# Reuse an existing openai module mock (e.g. from test_adapters.py) if already
# installed, so running both test files together keeps a single mock object.
_openai_mock = sys.modules.get("openai") or MagicMock()
sys.modules["openai"] = _openai_mock


class _MockIdentity:
    id = "test-identity"
    name = "TestBot"


@pytest.fixture
def mock_openai_client():
    """Mock the openai.OpenAI client so no real API call is made.

    The adapter lazy-imports ``openai`` at call time, and other test modules
    may replace ``sys.modules["openai"]`` during collection, so the fixture
    configures whichever module is current at setup time.
    """
    openai_mod = sys.modules.get("openai") or MagicMock()
    sys.modules["openai"] = openai_mod
    openai_mod.OpenAI = MagicMock()
    client = MagicMock()
    openai_mod.OpenAI.return_value = client

    choice = MagicMock()
    choice.message.content = "Hello from the mock!"
    choice.message.tool_calls = None

    completion = MagicMock()
    completion.choices = [choice]
    client.chat.completions.create.return_value = completion
    yield openai_mod.OpenAI


class TestGroqKeyRotation:
    def _groq(self, n_keys=3):
        from adapters.groq_adapter import GroqAdapter
        return GroqAdapter(api_keys=[f"g-{i}" for i in range(n_keys)])

    def test_extract_retry_after_formats(self):
        a = self._groq()
        assert a._extract_retry_after("Please try again in 55m49s") == 3349
        assert a._extract_retry_after("Please try again in 55m 49s") == 3349
        assert a._extract_retry_after("Please try again in 1m0s") == 60
        assert a._extract_retry_after("Please try again in 60.0s") == 60
        assert a._extract_retry_after("Please try again in 55.8m") == pytest.approx(3348)
        assert a._extract_retry_after("unrelated error") == 60

    def test_rotate_key_skips_cooldowns(self):
        a = self._groq()
        a._cooldowns[0] = time.time() + 9999
        a._cooldowns[1] = time.time() + 9999
        assert a._rotate_key() == "g-2"

    def test_rotate_key_returns_none_when_all_on_cooldown(self):
        a = self._groq()
        a._cooldowns[0] = time.time() + 9999
        a._cooldowns[1] = time.time() + 9999
        a._cooldowns[2] = time.time() + 9999
        assert a._rotate_key() is None

    def test_single_key_can_be_reselected_after_cooldown(self):
        a = self._groq(n_keys=1)
        a._cooldowns[0] = time.time() - 1
        assert a._rotate_key() == "g-0"

    def test_wait_shortest_cooldown_falls_through_when_too_long(self):
        a = self._groq()
        a._cooldowns[0] = time.time() + 9999
        a._cooldowns[1] = time.time() + 9999
        a._cooldowns[2] = time.time() + 9999
        with patch("adapters.groq_adapter.time.sleep") as mock_sleep:
            assert a._wait_shortest_cooldown(120) is False
        mock_sleep.assert_not_called()

    def test_wait_shortest_cooldown_waits_short_windows(self):
        a = self._groq()
        a._cooldowns[0] = time.time() + 4
        a._cooldowns[1] = time.time() + 9999
        a._cooldowns[2] = time.time() + 9999
        with patch("adapters.groq_adapter.time.sleep") as mock_sleep:
            assert a._wait_shortest_cooldown(120) is True
        mock_sleep.assert_called_once_with(5)

    def test_request_deadline_expands_only_for_explicit_long_cooldown(self):
        a = self._groq()
        assert a._request_deadline_seconds() == 45.0

        a._MAX_COOLDOWN_WAIT = 180.0

        assert a._request_deadline_seconds() == 195.0

    def test_generate_rotates_through_keys_on_429(self, mock_openai_client):
        """Rate limiting key 0 should rotate to key 1, not block."""
        client = mock_openai_client.return_value
        err = RuntimeError(
            "Error code: 429 - Please try again in 1m0s"
        )
        client.chat.completions.create.side_effect = [
            err,
            MagicMock(choices=[MagicMock(message=MagicMock(content="ok", tool_calls=None))]),
        ]
        a = self._groq()
        result = a.generate(
            context="ctx", user_input="hi", identity=_MockIdentity(),
        )
        assert result == "ok"
        assert a._key_index == 1
        assert 0 in a._cooldowns
        assert 1 not in a._cooldowns

    def test_generate_raises_when_all_keys_on_cooldown(self, mock_openai_client):
        """When every key is on a long cooldown, fall through fast (no long sleep)."""
        a = self._groq()
        a._cooldowns[0] = time.time() + 9999
        a._cooldowns[1] = time.time() + 9999
        a._cooldowns[2] = time.time() + 9999
        with patch("adapters.groq_adapter.time.sleep") as mock_sleep:
            with pytest.raises(RuntimeError, match="All Groq API keys on cooldown"):
                a.generate(
                    context="ctx", user_input="hi", identity=_MockIdentity(),
                )
        mock_sleep.assert_not_called()


class TestSambaNovaCooldown:
    def test_falls_through_when_all_on_cooldown(self):
        from adapters.sambanova_adapter import SambaNovaAdapter
        a = SambaNovaAdapter(api_keys=["s-0", "s-1", "s-2"])
        a._cooldowns[0] = time.time() + 9999
        a._cooldowns[1] = time.time() + 9999
        a._cooldowns[2] = time.time() + 9999
        with patch("adapters.sambanova_adapter.time.sleep") as mock_sleep:
            assert a._wait_shortest_cooldown(120) is False
        mock_sleep.assert_not_called()

    def test_rotates_to_free_key(self):
        from adapters.sambanova_adapter import SambaNovaAdapter
        a = SambaNovaAdapter(api_keys=["s-0", "s-1", "s-2"])
        a._cooldowns[0] = time.time() + 9999
        assert a._rotate_key() == "s-1"

    def test_single_key_can_be_reselected_after_cooldown(self):
        from adapters.sambanova_adapter import SambaNovaAdapter
        a = SambaNovaAdapter(api_keys=["s-0"])
        a._cooldowns[0] = time.time() - 1
        assert a._rotate_key() == "s-0"


class TestCerebrasCooldown:
    def test_falls_through_when_all_on_cooldown(self):
        from adapters.cerebras_adapter import CerebrasAdapter
        a = CerebrasAdapter(api_keys=["c-0", "c-1", "c-2"])
        a._cooldowns[0] = time.time() + 9999
        a._cooldowns[1] = time.time() + 9999
        a._cooldowns[2] = time.time() + 9999
        with patch("adapters.cerebras_adapter.time.sleep") as mock_sleep:
            assert a._wait_shortest_cooldown(120) is False
        mock_sleep.assert_not_called()

    def test_rotates_to_free_key(self):
        from adapters.cerebras_adapter import CerebrasAdapter
        a = CerebrasAdapter(api_keys=["c-0", "c-1", "c-2"])
        a._cooldowns[0] = time.time() + 9999
        assert a._rotate_key() == "c-1"

    def test_single_key_can_be_reselected_after_cooldown(self):
        from adapters.cerebras_adapter import CerebrasAdapter
        a = CerebrasAdapter(api_keys=["c-0"])
        a._cooldowns[0] = time.time() - 1
        assert a._rotate_key() == "c-0"
