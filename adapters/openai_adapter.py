from __future__ import annotations

from typing import Any, Optional

from .base import BaseAdapter


class OpenAIAdapter(BaseAdapter):
    """
    Adapter for OpenAI-compatible APIs (GPT-4, GPT-3.5, etc.).

    Supports:
    - Standard OpenAI Python SDK
    - Any OpenAI-compatible endpoint (Azure OpenAI, local proxies, etc.)

    Usage:
        adapter = OpenAIAdapter(
            model="gpt-4o",
            api_key="sk-...",
            base_url=None,  # Optional: override for Azure/local
        )
        runtime = IdentityRuntime(adapter=adapter)
    """

    def __init__(
        self,
        model: str = "gpt-4o",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        organization: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs
    ):
        super().__init__(model=model, **kwargs)
        self.api_key = api_key
        self.base_url = base_url
        self.organization = organization
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._client = None

    def _get_client(self):
        """Lazily initialize the OpenAI client."""
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url,
                    organization=self.organization,
                )
            except ImportError:
                raise ImportError(
                    "openai package not found. Install with: pip install openai"
                )
        return self._client

    def generate(
        self,
        context: str,
        user_input: str,
        identity: Any,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> str:
        """
        Generate a response using the OpenAI Chat Completions API.

        The context string is injected as the system message.
        The user_input becomes the user turn.
        """
        client = self._get_client()
        messages = [
            {"role": "system", "content": context},
            {"role": "user", "content": user_input},
        ]
        response = client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature or self.temperature,
            max_tokens=max_tokens or self.max_tokens,
            **kwargs
        )
        return response.choices[0].message.content or ""

    def health_check(self) -> bool:
        """Verify connectivity by listing available models."""
        try:
            client = self._get_client()
            client.models.list()
            return True
        except Exception:
            return False


class AnthropicAdapter(BaseAdapter):
    """
    Adapter for Anthropic Claude models.

    Usage:
        adapter = AnthropicAdapter(
            model="claude-3-5-sonnet-20241022",
            api_key="sk-ant-...",
        )
    """

    def __init__(
        self,
        model: str = "claude-3-5-sonnet-20241022",
        api_key: Optional[str] = None,
        max_tokens: int = 1024,
        **kwargs
    ):
        super().__init__(model=model, **kwargs)
        self.api_key = api_key
        self.max_tokens = max_tokens
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=self.api_key)
            except ImportError:
                raise ImportError(
                    "anthropic package not found. Install with: pip install anthropic"
                )
        return self._client

    def generate(
        self,
        context: str,
        user_input: str,
        identity: Any,
        **kwargs
    ) -> str:
        client = self._get_client()
        response = client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=context,
            messages=[{"role": "user", "content": user_input}],
            **kwargs
        )
        return response.content[0].text if response.content else ""


class OllamaAdapter(BaseAdapter):
    """
    Adapter for local Ollama models (llama3, mistral, etc.).
    Ollama exposes an OpenAI-compatible API at localhost:11434.

    Usage:
        adapter = OllamaAdapter(model="llama3.2")
    """

    def __init__(
        self,
        model: str = "llama3.2",
        base_url: str = "http://localhost:11434/v1",
        **kwargs
    ):
        super().__init__(model=model, **kwargs)
        self.base_url = base_url

    def generate(
        self,
        context: str,
        user_input: str,
        identity: Any,
        **kwargs
    ) -> str:
        # Uses OpenAI-compatible endpoint
        try:
            from openai import OpenAI
            client = OpenAI(
                api_key="ollama",  # Ollama doesn't require a real key
                base_url=self.base_url,
            )
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": context},
                    {"role": "user", "content": user_input},
                ],
            )
            return response.choices[0].message.content or ""
        except ImportError:
            raise ImportError(
                "openai package required for OllamaAdapter. "
                "Install with: pip install openai"
            )
