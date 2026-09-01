from __future__ import annotations

from typing import Any, Optional

from .base import BaseAdapter, AdapterMessage, AdapterRequest, AdapterResponse
from .chain import ChainAdapter
from .cerebras_adapter import CerebrasAdapter
from .openai_adapter import OpenAIAdapter, AnthropicAdapter, OllamaAdapter
from .openrouter_adapter import OpenRouterAdapter
from .groq_adapter import GroqAdapter
from .cerebras_adapter import CerebrasAdapter
from .sambanova_adapter import SambaNovaAdapter
from .configuration import build_adapter_from_env, describe_adapter


def get_adapter(
    adapter_type: str = "openai",
    model: Optional[str] = None,
    **kwargs: Any,
) -> BaseAdapter:
    adapter_type = adapter_type.lower()
    registry = {
        "openai": OpenAIAdapter,
        "anthropic": AnthropicAdapter,
        "ollama": OllamaAdapter,
        "openrouter": OpenRouterAdapter,
        "groq": GroqAdapter,
        "sambanova": SambaNovaAdapter,
        "cerebras": CerebrasAdapter,
    }
    if adapter_type not in registry:
        raise ValueError(
            f"Unknown adapter '{adapter_type}'. Choose from: {list(registry.keys())}"
        )
    return registry[adapter_type](model=model or "", **kwargs)


__all__ = [
    "BaseAdapter",
    "ChainAdapter",
    "CerebrasAdapter",
    "AdapterMessage",
    "AdapterRequest",
    "AdapterResponse",
    "OpenAIAdapter",
    "AnthropicAdapter",
    "OllamaAdapter",
    "OpenRouterAdapter",
    "GroqAdapter",
    "SambaNovaAdapter",
    "get_adapter",
    "build_adapter_from_env",
    "describe_adapter",
]
