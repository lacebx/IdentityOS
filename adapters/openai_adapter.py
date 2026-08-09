from __future__ import annotations

import logging
import os
import re
from typing import Any, Optional

from .base import BaseAdapter

logger = logging.getLogger(__name__)

_STATUS_RE = re.compile(r"(?:status|error)\s?code[:\s]+(\d{3})|\b(5\d\d)\b|\b(4(?:01|03|29))\b")

try:
    from openai import APIConnectionError as _APIConnectionError
except ImportError:  # pragma: no cover
    _APIConnectionError = Exception


def _http_status(exc: Exception) -> Optional[int]:
    """Extract an HTTP status code from an SDK/urllib error, if present."""
    status = getattr(exc, "status_code", None)
    if isinstance(status, int):
        return status
    response = getattr(exc, "response", None)
    if response is not None:
        status = getattr(response, "status_code", None)
        if isinstance(status, int):
            return status
    match = _STATUS_RE.search(str(exc))
    if match:
        code = match.group(1) or match.group(2) or match.group(3)
        if code:
            return int(code)
    return None


def _is_connection_error(exc: Exception) -> bool:
    """True when the error is a connectivity problem (APIConnectionError et al.)."""
    return isinstance(exc, _APIConnectionError) or "connection error" in str(exc).lower()


def _http_status(exc: Exception) -> Optional[int]:
    """Extract an HTTP status code from an SDK/urllib error, if present."""
    status = getattr(exc, "status_code", None)
    if isinstance(status, int):
        return status
    response = getattr(exc, "response", None)
    if response is not None:
        status = getattr(response, "status_code", None)
        if isinstance(status, int):
            return status
    match = _STATUS_RE.search(str(exc))
    if match:
        code = match.group(1) or match.group(2) or match.group(3)
        if code:
            return int(code)
    return None


def _is_connection_error(exc: Exception) -> bool:
    """True when the error is a connectivity problem (APIConnectionError et al.)."""
    return isinstance(exc, _APIConnectionError) or "connection error" in str(exc).lower()


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
        if api_key is None:
            api_key = os.environ.get("OPENAI_API_KEY")
        super().__init__(model=model, **kwargs)
        self.api_key = api_key
        if base_url is None:
            base_url = os.environ.get("OPENAI_BASE_URL")
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
        retries: int = 3,
        **kwargs
    ) -> str:
        """
        Generate a response using the OpenAI Chat Completions API.

        The context string is injected as the system message.
        The user_input becomes the user turn.
        Retries up to `retries` times with exponential backoff on rate limits.
        """
        import time as _time
        client = self._get_client()
        messages = [
            {"role": "system", "content": context},
            {"role": "user", "content": user_input},
        ]
        model = self.model or "gpt-4o"
        last_exc = None
        for attempt in range(retries):
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature or self.temperature,
                    max_tokens=max_tokens or self.max_tokens,
                    **kwargs
                )
                return response.choices[0].message.content or ""
            except Exception as exc:
                last_exc = exc
                msg = str(exc)
                msg_lower = msg.lower()
                if "rate limit" in msg_lower or "429" in msg:
                    if attempt < retries - 1:
                        wait = 2 ** attempt * 5
                        logger.warning("Rate limited, retrying in %ds...", wait)
                        _time.sleep(wait)
                    continue
                # Carry recognizable provider signals so chain/rotating
                # adapters can detect and fail over instead of crashing.
                status = _http_status(exc)
                if status == 429:
                    if attempt < retries - 1:
                        wait = 2 ** attempt * 5
                        logger.warning("Rate limited (HTTP %s), retrying in %ds...", status, wait)
                        _time.sleep(wait)
                        continue
                    raise RuntimeError(
                        f"Adapter error (model={model!r}, base_url={self.base_url!r}): "
                        f"429 rate limit exceeded: {msg}"
                    ) from exc
                if status == 401:
                    raise RuntimeError(
                        f"Adapter error (model={model!r}, base_url={self.base_url!r}): "
                        f"401 authentication failed (invalid API key): {msg}"
                    ) from exc
                if status in (502, 503, 504) or _is_connection_error(exc):
                    raise RuntimeError(
                        f"Adapter error (model={model!r}, base_url={self.base_url!r}): "
                        f"{status or 'connection'} service unavailable: {msg}"
                    ) from exc
                raise RuntimeError(
                    f"Adapter error (model={model!r}, base_url={self.base_url!r}): {msg}"
                ) from exc
        msg = str(last_exc)
        raise RuntimeError(
            f"Adapter error (model={model!r}, base_url={self.base_url!r}): {msg}"
        ) from last_exc

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
        if api_key is None:
            api_key = os.environ.get("ANTHROPIC_API_KEY")
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
        model = self.model or "claude-3-5-sonnet-20241022"
        try:
            response = client.messages.create(
                model=model,
                max_tokens=self.max_tokens,
                system=context,
                messages=[{"role": "user", "content": user_input}],
                **kwargs
            )
            return response.content[0].text if response.content else ""
        except Exception as exc:
            raise RuntimeError(
                f"Adapter error (model={model!r}): {exc}"
            ) from exc


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
        think: bool = False,
        **kwargs
    ):
        super().__init__(model=model, **kwargs)
        self.base_url = base_url
        # Reasoning-capable Ollama models may emit their answer exclusively in
        # a separate reasoning field. IdentityOS consumes chat content, so keep
        # reasoning disabled unless a caller intentionally enables it.
        self.think = think

    def generate(
        self,
        context: str,
        user_input: str,
        identity: Any,
        think: Optional[bool] = None,
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
                extra_body={"think": self.think if think is None else think},
            )
            return response.choices[0].message.content or ""
        except ImportError:
            raise ImportError(
                "openai package required for OllamaAdapter. "
                "Install with: pip install openai"
            )
