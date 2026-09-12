import pytest

from adapters import ChainAdapter, build_adapter_from_env, describe_adapter
from adapters.groq_adapter import GroqAdapter
from adapters.openai_adapter import OllamaAdapter, OpenAIAdapter


def test_no_credentials_means_no_adapter():
    assert build_adapter_from_env({}) is None


def test_provider_keys_create_a_deterministic_fallback_chain():
    adapter = build_adapter_from_env({
        "GROQ_API_KEY": "groq-test-key",
        "GROQ_API_KEY_2": "groq-second-key",
        "OPENAI_API_KEY": "openai-test-key",
    })
    assert isinstance(adapter, ChainAdapter)
    assert isinstance(adapter.adapters[0], GroqAdapter)
    assert isinstance(adapter.adapters[1], OpenAIAdapter)
    assert adapter.adapters[0]._keys == ["groq-test-key", "groq-second-key"]
    description = describe_adapter(adapter)
    assert description["configured"] is True
    assert "test-key" not in str(description)


def test_local_openai_endpoint_selects_ollama_semantics():
    adapter = build_adapter_from_env({
        "OPENAI_API_KEY": "ollama",
        "OPENAI_BASE_URL": "http://localhost:11434/v1",
        "OLLAMA_MODEL": "qwen3:4b",
    })
    assert isinstance(adapter, OllamaAdapter)
    assert adapter.model == "qwen3:4b"
    assert adapter.timeout == 120.0


@pytest.mark.parametrize(
    ("base_url", "expected_type"),
    [
        ("https://api.openai.com/v1", OpenAIAdapter),
        ("http://localhost:11434/v1", OllamaAdapter),
    ],
)
def test_openai_timeout_propagates_to_openai_compatible_adapters(
    base_url, expected_type
):
    adapter = build_adapter_from_env({
        "OPENAI_API_KEY": "test-key",
        "OPENAI_BASE_URL": base_url,
        "OPENAI_TIMEOUT": "17.5",
    })

    assert isinstance(adapter, expected_type)
    assert adapter.timeout == 17.5


@pytest.mark.parametrize("value", ["invalid", "0", "-1", "nan", "inf"])
def test_invalid_openai_timeout_is_rejected(value):
    with pytest.raises(ValueError, match="OPENAI_TIMEOUT must be a positive number"):
        build_adapter_from_env({
            "OPENAI_API_KEY": "test-key",
            "OPENAI_TIMEOUT": value,
        })


def test_explicit_adapter_precedes_automatic_fallbacks():
    adapter = build_adapter_from_env({
        "IDENTITY_ADAPTER": "ollama",
        "IDENTITY_ADAPTER_CONFIG": '{"model": "llama3.2"}',
        "GROQ_API_KEY": "groq-test-key",
    })
    assert isinstance(adapter, ChainAdapter)
    assert isinstance(adapter.adapters[0], OllamaAdapter)
    assert isinstance(adapter.adapters[1], GroqAdapter)


def test_invalid_explicit_json_is_not_silently_ignored():
    with pytest.raises(ValueError, match="valid JSON"):
        build_adapter_from_env({
            "IDENTITY_ADAPTER": "ollama",
            "IDENTITY_ADAPTER_CONFIG": "{broken",
        })
