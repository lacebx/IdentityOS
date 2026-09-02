"""Shared, side-effect-free adapter configuration for services and benchmarks."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping
from typing import Any, Optional

from .base import BaseAdapter
from .cerebras_adapter import CerebrasAdapter
from .chain import ChainAdapter
from .groq_adapter import GroqAdapter
from .openai_adapter import AnthropicAdapter, OllamaAdapter, OpenAIAdapter
from .openrouter_adapter import OpenRouterAdapter
from .sambanova_adapter import SambaNovaAdapter


def _valid(value: Optional[str]) -> bool:
    return bool(value and "PLACEHOLDER" not in value.upper())


def _numbered_keys(env: Mapping[str, str], prefix: str) -> list[str]:
    pattern = re.compile(rf"^{re.escape(prefix)}(?:_(\d+))?$")
    matches: list[tuple[int, str]] = []
    for name, value in env.items():
        match = pattern.match(name)
        if match and _valid(value):
            matches.append((int(match.group(1) or 1), value))
    return [value for _, value in sorted(matches)]


def build_adapter_from_env(env: Optional[Mapping[str, str]] = None) -> Optional[BaseAdapter]:
    """Build the configured provider chain without making a network request.

    Explicit ``IDENTITY_ADAPTER`` configuration is tried first. Remaining
    providers with valid credentials form deterministic fallbacks. Duplicate
    provider types are omitted.
    """
    values = os.environ if env is None else env
    candidates: list[BaseAdapter] = []
    configured: set[str] = set()

    explicit = values.get("IDENTITY_ADAPTER", "").strip().lower()
    if explicit:
        from . import get_adapter

        try:
            config: dict[str, Any] = json.loads(values.get("IDENTITY_ADAPTER_CONFIG", "{}") or "{}")
        except json.JSONDecodeError as exc:
            raise ValueError("IDENTITY_ADAPTER_CONFIG must be valid JSON") from exc
        candidates.append(get_adapter(explicit, **config))
        configured.add(explicit)

    samba_keys = _numbered_keys(values, "SAMBANOVA_API_KEY")
    if samba_keys and "sambanova" not in configured:
        candidates.append(SambaNovaAdapter(
            model=values.get("SAMBANOVA_MODEL", "DeepSeek-V3.1"), api_keys=samba_keys,
        ))
        configured.add("sambanova")

    groq_keys = _numbered_keys(values, "GROQ_API_KEY")
    if groq_keys and "groq" not in configured:
        candidates.append(GroqAdapter(
            model=values.get("GROQ_MODEL", values.get("IDENTITY_MODEL", "openai/gpt-oss-120b")),
            api_keys=groq_keys,
        ))
        configured.add("groq")

    cerebras_keys = _numbered_keys(values, "CEREBRAS_API_KEY")
    if cerebras_keys and "cerebras" not in configured:
        candidates.append(CerebrasAdapter(
            model=values.get("CEREBRAS_MODEL", "gpt-oss-120b"), api_keys=cerebras_keys,
        ))
        configured.add("cerebras")

    if _valid(values.get("OPENROUTER_API_KEY")) and "openrouter" not in configured:
        candidates.append(OpenRouterAdapter(
            model=values.get("OPENROUTER_MODEL", "openai/gpt-4o-mini"),
            api_key=values.get("OPENROUTER_API_KEY"),
            base_url=values.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        ))
        configured.add("openrouter")

    if _valid(values.get("ANTHROPIC_API_KEY")) and "anthropic" not in configured:
        candidates.append(AnthropicAdapter(
            model=values.get("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022"),
            api_key=values.get("ANTHROPIC_API_KEY"),
        ))
        configured.add("anthropic")

    openai_key = values.get("OPENAI_API_KEY")
    openai_base = values.get("OPENAI_BASE_URL", "")
    is_local = any(host in openai_base for host in ("localhost", "127.0.0.1"))
    if _valid(openai_key) and "openai" not in configured and "ollama" not in configured:
        if is_local:
            candidates.append(OllamaAdapter(
                model=values.get("OLLAMA_MODEL", values.get("IDENTITY_MODEL", "llama3.2")),
                base_url=openai_base or "http://localhost:11434/v1",
            ))
        else:
            candidates.append(OpenAIAdapter(
                model=values.get("OPENAI_MODEL", values.get("IDENTITY_MODEL", "gpt-4o")),
                api_key=openai_key,
                base_url=openai_base or None,
            ))

    if not candidates:
        return None
    return candidates[0] if len(candidates) == 1 else ChainAdapter(candidates)


def describe_adapter(adapter: Optional[BaseAdapter]) -> dict[str, Any]:
    """Return public provider/model metadata without credentials."""
    if adapter is None:
        return {"configured": False, "providers": []}
    leaves = adapter.adapters if isinstance(adapter, ChainAdapter) else [adapter]
    return {
        "configured": True,
        "providers": [
            {
                "adapter": type(item).__name__,
                "model": str(getattr(item, "model", "") or ""),
            }
            for item in leaves
        ],
    }
