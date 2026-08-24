"""
Tests for all LLM adapters.

Uses mocked HTTP responses so tests are fast and need no real API keys.
"""

from __future__ import annotations

import json
import sys
from unittest.mock import MagicMock, patch

import pytest

# Install mock modules so adapter lazy-imports resolve during testing
_openai_mock = MagicMock()
_anthropic_mock = MagicMock()
sys.modules["openai"] = _openai_mock
sys.modules["anthropic"] = _anthropic_mock

from adapters.base import BaseAdapter  # noqa: E402
from adapters.openai_adapter import OpenAIAdapter, AnthropicAdapter, OllamaAdapter, list_ollama_models, resolve_ollama_model  # noqa: E402
from adapters.openrouter_adapter import OpenRouterAdapter  # noqa: E402
from adapters import get_adapter  # noqa: E402


# ---------------------------------------------------------------------------
# Mock identity for adapter.generate()
# ---------------------------------------------------------------------------

class _MockIdentity:
    id = "test-identity"
    name = "TestBot"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_openai_client():
    """Mock the openai.OpenAI client so no real API call is made."""
    _openai_mock.OpenAI = MagicMock()
    client = MagicMock()
    _openai_mock.OpenAI.return_value = client

    choice = MagicMock()
    choice.message.content = "Hello from the mock!"

    completion = MagicMock()
    completion.choices = [choice]
    client.chat.completions.create.return_value = completion
    yield _openai_mock.OpenAI


@pytest.fixture
def mock_anthropic_client():
    """Mock the anthropic.Anthropic client."""
    _anthropic_mock.Anthropic = MagicMock()
    client = MagicMock()
    _anthropic_mock.Anthropic.return_value = client

    content_block = MagicMock()
    content_block.text = "Hello from Claude mock!"

    message = MagicMock()
    message.content = [content_block]
    client.messages.create.return_value = message
    yield _anthropic_mock.Anthropic


# ---------------------------------------------------------------------------
# BaseAdapter tests
# ---------------------------------------------------------------------------

class TestBaseAdapter:
    def test_abstract_cannot_instantiate(self):
        with pytest.raises(TypeError):
            BaseAdapter()  # type: ignore[abstract]

    def test_build_messages(self):
        class ConcreteAdapter(BaseAdapter):
            def generate(self, context, user_input, identity, **kwargs):
                return "test"

        adapter = ConcreteAdapter(model="test-model")
        msgs = adapter.build_messages("system context", "user text")
        assert len(msgs) == 2
        assert msgs[0].role == "system"
        assert msgs[0].content == "system context"
        assert msgs[1].role == "user"
        assert msgs[1].content == "user text"

    def test_health_check_default(self):
        class ConcreteAdapter(BaseAdapter):
            def generate(self, context, user_input, identity, **kwargs):
                return "test"

        adapter = ConcreteAdapter()
        assert adapter.health_check() is True

    def test_repr(self):
        class ConcreteAdapter(BaseAdapter):
            def generate(self, context, user_input, identity, **kwargs):
                return "test"

        adapter = ConcreteAdapter(model="gpt-4o")
        assert repr(adapter) == "ConcreteAdapter(model='gpt-4o')"


# ---------------------------------------------------------------------------
# OpenAIAdapter tests
# ---------------------------------------------------------------------------

class TestOpenAIAdapter:
    def test_generate(self, mock_openai_client):
        adapter = OpenAIAdapter(api_key="sk-test")
        result = adapter.generate(
            context="You are a helpful assistant.",
            user_input="Hello!",
            identity=_MockIdentity(),
        )
        assert result == "Hello from the mock!"
        mock_openai_client.return_value.chat.completions.create.assert_called_once()

    def test_generate_with_custom_temperature(self, mock_openai_client):
        adapter = OpenAIAdapter(api_key="sk-test", temperature=0.5)
        adapter.generate(
            context="Be concise.",
            user_input="Hi",
            identity=_MockIdentity(),
        )
        call_kwargs = mock_openai_client.return_value.chat.completions.create.call_args[1]
        assert call_kwargs["temperature"] == 0.5

    def test_generate_with_custom_max_tokens(self, mock_openai_client):
        adapter = OpenAIAdapter(api_key="sk-test", max_tokens=500)
        adapter.generate(
            context="Be concise.",
            user_input="Hi",
            identity=_MockIdentity(),
        )
        call_kwargs = mock_openai_client.return_value.chat.completions.create.call_args[1]
        assert call_kwargs["max_tokens"] == 500

    def test_health_check_success(self, mock_openai_client):
        adapter = OpenAIAdapter(api_key="sk-test")
        assert adapter.health_check() is True

    def test_health_check_failure(self):
        with patch("openai.OpenAI") as mock:
            client = MagicMock()
            mock.return_value = client
            client.models.list.side_effect = Exception("API error")
            adapter = OpenAIAdapter(api_key="sk-test")
            assert adapter.health_check() is False

    def test_lazy_client(self):
        adapter = OpenAIAdapter(api_key="sk-test")
        assert adapter._client is None
        # First call triggers _get_client
        with patch("openai.OpenAI") as mock:
            mock.return_value = MagicMock()
            adapter.generate(
                context="test", user_input="test", identity=_MockIdentity(),
            )
            assert adapter._client is not None

    def test_recovers_from_legacy_function_call_error(self, mock_openai_client):
        """Groq 400 tool_use_failed (legacy <function=...> syntax) should recover.

        The rejected generation is executed as a real tool call and the model
        is retried with the tool result in context.
        """
        client = mock_openai_client.return_value
        err_msg = (
            "Error code: 400 - {'error': {'message': 'Failed to call a function. "
            "See failed_generation.', 'code': 'tool_use_failed', 'failed_generation': "
            "\"<function=executive__start_task>{'goal': 'getting_to_know_each_other'}</function>\"}}"
        )
        client.chat.completions.create.side_effect = [
            RuntimeError(err_msg),
            MagicMock(
                choices=[
                    MagicMock(
                        message=MagicMock(content="Task committed!", tool_calls=None)
                    )
                ]
            ),
        ]

        executed = []

        def execute_tool(func_name, args):
            executed.append((func_name, args))
            return '{"task_id": "abc", "status": "queued"}'

        adapter = OpenAIAdapter(api_key="sk-test")
        result = adapter.generate(
            context="You are a helpful assistant.",
            user_input="start a task",
            identity=_MockIdentity(),
            execute_tool=execute_tool,
        )
        assert result == "Task committed!"
        assert executed == [("executive__start_task", {"goal": "getting_to_know_each_other"})]

    def test_parse_legacy_function_call_json_and_dict(self):
        from adapters.openai_adapter import _parse_legacy_function_call

        json_form = "<function=foo.bar>{\"x\": 1}</function>"
        assert _parse_legacy_function_call(json_form) == ("foo.bar", {"x": 1})

        dict_form = "<function=executive__start_task>{'goal': 'hi'}</function>"
        assert _parse_legacy_function_call(dict_form) == ("executive__start_task", {"goal": "hi"})

        assert _parse_legacy_function_call("no function here") is None

    def test_shrinks_max_tokens_on_token_limit_rejection(self, mock_openai_client):
        """A 413/token-budget rejection should shrink max_tokens and retry.

        Mirrors Groq's free-tier behavior where a request slightly over the
        tokens-per-minute allowance is rejected with 413.  The adapter halves
        the completion budget and retries instead of failing the whole turn.
        """
        client = mock_openai_client.return_value
        err_msg = (
            "Error code: 413 - {'error': {'message': 'Request too large for model "
            "`openai/gpt-oss-120b` on tokens per minute (TPM): Limit 8000, "
            "Requested 8040, please reduce your message size and try again.', "
            "'type': 'tokens', 'code': 'rate_limit_exceeded'}}"
        )
        client.chat.completions.create.side_effect = [
            RuntimeError(err_msg),
            MagicMock(
                choices=[
                    MagicMock(
                        message=MagicMock(content="Shrunk and succeeded!", tool_calls=None)
                    )
                ]
            ),
        ]

        adapter = OpenAIAdapter(api_key="sk-test", max_tokens=1024)
        result = adapter.generate(
            context="x" * 200,
            user_input="hi",
            identity=_MockIdentity(),
        )
        assert result == "Shrunk and succeeded!"
        calls = client.chat.completions.create.call_args_list
        assert len(calls) == 2
        assert calls[0].kwargs["max_tokens"] == 1024
        assert calls[1].kwargs["max_tokens"] == 512

    def test_does_not_shrink_below_floor(self, mock_openai_client):
        """max_tokens should not shrink below 256; persists token-limit errors."""
        client = mock_openai_client.return_value
        err_msg = (
            "Error code: 413 - Request too large for model "
            "`openai/gpt-oss-120b` (tokens per minute: Limit 8000)"
        )
        client.chat.completions.create.side_effect = RuntimeError(err_msg)

        adapter = OpenAIAdapter(api_key="sk-test", max_tokens=300)
        with pytest.raises(RuntimeError, match="413"):
            adapter.generate(
                context="x" * 100,
                user_input="hi",
                identity=_MockIdentity(),
            )
        # 300 -> 256 (floor), then raises
        assert client.chat.completions.create.call_count == 2
        assert client.chat.completions.create.call_args_list[1].kwargs["max_tokens"] == 256

    def test_is_token_limit_error_markers(self):
        from adapters.openai_adapter import _is_token_limit_error
        assert _is_token_limit_error("Error code: 413 - request too large")
        assert _is_token_limit_error("tokens per minute (TPM): Limit 8000")
        assert _is_token_limit_error("maximum context length exceeded")
        assert not _is_token_limit_error("rate limit 429, try again later")


# ---------------------------------------------------------------------------
# AnthropicAdapter tests
# ---------------------------------------------------------------------------

class TestAnthropicAdapter:
    def test_generate(self, mock_anthropic_client):
        adapter = AnthropicAdapter(api_key="sk-ant-test")
        result = adapter.generate(
            context="You are Claude.",
            user_input="Hello!",
            identity=_MockIdentity(),
        )
        assert result == "Hello from Claude mock!"
        mock_anthropic_client.return_value.messages.create.assert_called_once()

    def test_health_check_default(self):
        adapter = AnthropicAdapter(api_key="sk-ant-test")
        assert adapter.health_check() is True

    def test_lazy_client(self):
        adapter = AnthropicAdapter(api_key="sk-ant-test")
        assert adapter._client is None
        with patch("anthropic.Anthropic") as mock:
            mock.return_value = MagicMock()
            adapter.generate(
                context="test", user_input="test", identity=_MockIdentity(),
            )
            assert adapter._client is not None


# ---------------------------------------------------------------------------
# OllamaAdapter tests
# ---------------------------------------------------------------------------

class TestOllamaAdapter:
    def test_generate(self, mock_openai_client):
        adapter = OllamaAdapter(model="llama3.2")
        result = adapter.generate(
            context="You are a local model.",
            user_input="Hello!",
            identity=_MockIdentity(),
        )
        assert result == "Hello from the mock!"
        mock_openai_client.return_value.chat.completions.create.assert_called_once()

    def test_generate_disables_thinking_by_default(self, mock_openai_client):
        adapter = OllamaAdapter(model="qwen3.5:4b")
        adapter.generate(
            context="You are a local model.",
            user_input="Hello!",
            identity=_MockIdentity(),
        )
        call_kwargs = mock_openai_client.return_value.chat.completions.create.call_args[1]
        assert call_kwargs["extra_body"] == {"think": False}

    def test_generate_can_enable_thinking(self, mock_openai_client):
        adapter = OllamaAdapter(model="qwen3.5:4b", think=True)
        adapter.generate(
            context="You are a local model.",
            user_input="Hello!",
            identity=_MockIdentity(),
        )
        call_kwargs = mock_openai_client.return_value.chat.completions.create.call_args[1]
        assert call_kwargs["extra_body"] == {"think": True}

    def test_default_base_url(self):
        adapter = OllamaAdapter()
        assert adapter.base_url == "http://localhost:11434/v1"

    def test_health_check_default(self, monkeypatch):
        monkeypatch.setattr(
            "adapters.openai_adapter.list_ollama_models",
            lambda **kwargs: ["llama3.2:latest"],
        )
        adapter = OllamaAdapter(model="llama3.2")
        assert adapter.health_check() is True

    def test_health_check_missing_model(self, monkeypatch):
        monkeypatch.setattr(
            "adapters.openai_adapter.list_ollama_models",
            lambda **kwargs: ["smollm2:360m-instruct-q4_0"],
        )
        adapter = OllamaAdapter(model="llama3.2")
        assert adapter.health_check() is False

    def test_legacy_tool_loop_without_native_api(self, mock_openai_client):
        client = mock_openai_client.return_value
        client.chat.completions.create.side_effect = [
            MagicMock(
                choices=[
                    MagicMock(
                        message=MagicMock(
                            content='<function=calc__evaluate>{"expression": "837 * 492"}</function>',
                            tool_calls=None,
                        ),
                    )
                ]
            ),
            MagicMock(
                choices=[
                    MagicMock(message=MagicMock(content="411804", tool_calls=None)),
                ]
            ),
        ]

        executed = []

        def execute_tool(func_name, args):
            executed.append((func_name, args))
            return '{"result": 411804}'

        adapter = OllamaAdapter(model="smollm2:360m-instruct-q4_0")
        result = adapter.generate(
            context="Use tools for math.",
            user_input="Calculate 837 * 492",
            identity=_MockIdentity(),
            tools=[{"type": "function", "function": {"name": "calc__evaluate"}}],
            execute_tool=execute_tool,
        )
        assert result == "411804"
        assert executed == [("calc__evaluate", {"expression": "837 * 492"})]
        first_call = client.chat.completions.create.call_args_list[0]
        assert "tools" not in first_call[1]
        assert first_call[1]["extra_body"] == {"think": False}



class TestOllamaModelHelpers:
    def test_resolve_exact_match(self):
        models = ["llama3.2:latest", "smollm2:360m-instruct-q4_0"]
        assert resolve_ollama_model("smollm2:360m-instruct-q4_0", models) == "smollm2:360m-instruct-q4_0"

    def test_resolve_base_name(self):
        models = ["llama3.2:latest", "smollm2:360m-instruct-q4_0"]
        assert resolve_ollama_model("llama3.2", models) == "llama3.2:latest"

    def test_list_ollama_models_parses_tags(self, monkeypatch):
        class _Resp:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return json.dumps(
                    {"models": [{"name": "smollm2:360m-instruct-q4_0"}]}
                ).encode()

        monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: _Resp())
        assert list_ollama_models() == ["smollm2:360m-instruct-q4_0"]


# ---------------------------------------------------------------------------
# OpenRouterAdapter tests
# ---------------------------------------------------------------------------

class TestOpenRouterAdapter:
    def test_generate(self, mock_openai_client):
        adapter = OpenRouterAdapter(api_key="sk-or-test")
        result = adapter.generate(
            context="You are a multi-model gateway.",
            user_input="Hello!",
            identity=_MockIdentity(),
        )
        assert result == "Hello from the mock!"
        mock_openai_client.return_value.chat.completions.create.assert_called_once()

    def test_default_model(self):
        adapter = OpenRouterAdapter(api_key="sk-or-test")
        assert adapter.model == "openai/gpt-4o"

    def test_default_base_url(self):
        adapter = OpenRouterAdapter(api_key="sk-or-test")
        assert adapter.base_url == "https://openrouter.ai/api/v1"

    def test_site_headers(self, mock_openai_client):
        adapter = OpenRouterAdapter(
            api_key="sk-or-test",
            site_url="https://example.com",
            site_name="IdentityOS",
        )
        adapter.generate(
            context="test", user_input="test", identity=_MockIdentity(),
        )

    def test_health_check(self, mock_openai_client):
        adapter = OpenRouterAdapter(api_key="sk-or-test")
        assert adapter.health_check() is True


# ---------------------------------------------------------------------------
# get_adapter factory tests
# ---------------------------------------------------------------------------

class TestGetAdapter:
    def test_openai(self):
        adapter = get_adapter("openai", api_key="sk-test")
        assert isinstance(adapter, OpenAIAdapter)

    def test_anthropic(self):
        adapter = get_adapter("anthropic", api_key="sk-ant-test")
        assert isinstance(adapter, AnthropicAdapter)

    def test_ollama(self):
        adapter = get_adapter("ollama", model="llama3.2")
        assert isinstance(adapter, OllamaAdapter)

    def test_openrouter(self):
        adapter = get_adapter("openrouter", api_key="sk-or-test")
        assert isinstance(adapter, OpenRouterAdapter)

    def test_unknown_adapter(self):
        with pytest.raises(ValueError, match="Unknown adapter"):
            get_adapter("nonexistent")

    def test_with_model_override(self):
        adapter = get_adapter("openai", model="gpt-3.5-turbo", api_key="sk-test")
        assert adapter.model == "gpt-3.5-turbo"

    def test_case_insensitive(self):
        adapter = get_adapter("OpenAI", api_key="sk-test")
        assert isinstance(adapter, OpenAIAdapter)


# ---------------------------------------------------------------------------
# Runtime + adapter integration test
# ---------------------------------------------------------------------------

class TestAdapterInRuntime:
    def test_runtime_with_adapter(self, mock_openai_client):
        from core.evaluation import register_default_criteria
        from core.identity import create_identity
        from runtime.orchestrator import IdentityRuntime, InteractionRequest
        from runtime.persistence import JSONFileBackend
        from pathlib import Path
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            storage = JSONFileBackend(root_dir=str(Path(tmp) / ".store"))
            adapter = OpenAIAdapter(api_key="sk-test")
            rt = IdentityRuntime(storage=storage, adapter=adapter)
            register_default_criteria(rt.evaluation_engine)

            spec = create_identity(name="AdapterBot", identity_id="adapter-bot")
            rt.register(spec)
            sid = rt.start_session("adapter-bot")
            resp = rt.process(InteractionRequest(
                identity_id="adapter-bot",
                user_input="Hello from the runtime!",
                session_id=sid,
            ))
            assert resp.output == "Hello from the mock!"
            assert resp.policy_passed is True
