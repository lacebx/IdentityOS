from __future__ import annotations

import os
from typing import Any, Optional

from .openai_adapter import OpenAIAdapter


class SambaNovaAdapter(OpenAIAdapter):
    """
    Adapter for SambaNova — OpenAI-compatible API at api.sambanova.ai.

    Usage:
        adapter = SambaNovaAdapter(
            model="DeepSeek-V3.1",
        )
        runtime = IdentityRuntime(adapter=adapter)

    Environment variables:
        SAMBANOVA_API_KEY  — your SambaNova API key (fallback if api_key not passed)
    """

    def __init__(
        self,
        model: str = "DeepSeek-V3.1",
        api_key: Optional[str] = None,
        base_url: str = "https://api.sambanova.ai/v1",
        **kwargs: Any,
    ):
        if api_key is None:
            api_key = os.environ.get("SAMBANOVA_API_KEY")
        super().__init__(
            model=model,
            api_key=api_key,
            base_url=base_url,
            **kwargs,
        )
