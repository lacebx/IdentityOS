from __future__ import annotations

import os
from typing import Any, Optional

from .openai_adapter import OpenAIAdapter


class OpenRouterAdapter(OpenAIAdapter):
    """
    Adapter for OpenRouter — a unified API gateway to many LLM providers.

    OpenRouter exposes an OpenAI-compatible API at openrouter.ai/api/v1
    and supports seamless model switching across providers.

    Usage:
        adapter = OpenRouterAdapter(
            model="openai/gpt-4o",
            api_key="sk-or-v1-...",
        )
        runtime = IdentityRuntime(adapter=adapter)

    Environment variables:
        OPENROUTER_API_KEY  — your OpenRouter API key (fallback if api_key not passed)
        OPENROUTER_BASE_URL — optional custom base URL (default: https://openrouter.ai/api/v1)
    """

    def __init__(
        self,
        model: str = "openai/gpt-4o",
        api_key: Optional[str] = None,
        base_url: str = "https://openrouter.ai/api/v1",
        site_url: Optional[str] = None,
        site_name: Optional[str] = None,
        **kwargs: Any,
    ):
        # Fall back to OPENROUTER_API_KEY env var if no explicit api_key
        if api_key is None:
            api_key = os.environ.get("OPENROUTER_API_KEY")
        # Fall back to OPENROUTER_BASE_URL env var
        base_url = os.environ.get("OPENROUTER_BASE_URL", base_url)

        super().__init__(
            model=model,
            api_key=api_key,
            base_url=base_url,
            **kwargs,
        )
        self.site_url = site_url
        self.site_name = site_name

    def _get_client(self):
        client = super()._get_client()
        if self.site_url or self.site_name:
            default_headers = {}
            if self.site_url:
                default_headers["HTTP-Referer"] = self.site_url
            if self.site_name:
                default_headers["X-Title"] = self.site_name
            if default_headers:
                client.default_headers = {
                    **(client.default_headers or {}),
                    **default_headers,
                }
        return client
