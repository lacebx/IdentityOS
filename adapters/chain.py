from __future__ import annotations

import logging
import threading
import time
from typing import Any, Optional

from .base import BaseAdapter

logger = logging.getLogger(__name__)

_EXHAUSTION_MARKERS = [
    "api keys exhausted",
    "all adapters exhausted",
]


class ChainAdapter(BaseAdapter):
    """
    Tries multiple adapters in sequence, falling through when one is unusable.

    Each adapter handles its own internal key rotation (e.g. GroqAdapter
    rotates through GROQ_API_KEY[1..N] with cooldown; keys are auto-discovered
    incrementally).  When ALL keys for a given provider are exhausted — or the
    provider is unreachable/rate-limited/erroring — ``ChainAdapter`` catches the
    error and moves to the next adapter in the chain (which may be another
    provider, or a local Ollama model as the final fallback).

    Usage::

        chain = ChainAdapter([groq_adapter, ollama_adapter])
        chain.generate(context, user_input, identity)
    """

    def __init__(
        self,
        adapters: list[BaseAdapter],
        model: str = "",
        cooldown_seconds: float = 0,
    ) -> None:
        self._adapters = adapters
        self._cooldown_seconds = max(0, cooldown_seconds)
        self._cooldowns: dict[int, float] = {}
        self._cooldown_lock = threading.Lock()
        first = adapters[0] if adapters else None
        super().__init__(model=model or (first.model if first else ""))

    @property
    def model(self) -> str:
        return self._model or (self._adapters[0].model if self._adapters else "")

    @model.setter
    def model(self, val: str) -> None:
        self._model = val

    @property
    def adapters(self) -> tuple[BaseAdapter, ...]:
        """Ordered, read-only provider chain for diagnostics."""
        return tuple(self._adapters)

    def _is_exhaustion(self, error: Exception) -> bool:
        """True when the provider is unusable and the next adapter should be tried.

        Treats rate limits, connection failures, 5xx, and key exhaustion as
        "try the next provider" conditions.  Genuine model-side errors (e.g.
        400/bad request) are NOT exhaustion and propagate immediately.
        """
        msg = str(error).lower()
        if any(marker in msg for marker in _EXHAUSTION_MARKERS):
            return True
        for token in ("rate limit", "429", "quota", "throttl",
                      "connection", "timed out", "timeout",
                      "service unavailable", "500", "502", "503", "504",
                      "api keys exhausted", "invalid api key",
                      "authentication failed", "401", "402"):
            if token in msg:
                return True
        return False

    def generate(
        self,
        context: str,
        user_input: str,
        identity: Any,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> str:
        errors: list[tuple[str, str]] = []
        tool_invoked = False
        execute_tool = kwargs.get("execute_tool")
        if execute_tool is not None:
            def tracked_tool(*args, **tool_kwargs):
                nonlocal tool_invoked
                # Set before invocation: a callback can fail after a side effect.
                tool_invoked = True
                return execute_tool(*args, **tool_kwargs)
            kwargs["execute_tool"] = tracked_tool

        for idx, adapter in enumerate(self._adapters):
            name = type(adapter).__name__
            with self._cooldown_lock:
                cooling = self._cooldowns.get(idx, 0) > time.monotonic()
            if cooling:
                errors.append((name, "provider cooling down"))
                continue
            try:
                return adapter.generate(
                    context=context,
                    user_input=user_input,
                    identity=identity,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs,
                )
            except Exception as exc:
                errors.append((name, str(exc)))
                if tool_invoked:
                    raise  # Never replay an already-started capability on failover.
                if not self._is_exhaustion(exc):
                    raise  # Non-exhaustion errors propagate immediately
                with self._cooldown_lock:
                    self._cooldowns[idx] = time.monotonic() + self._cooldown_seconds
                if idx < len(self._adapters) - 1:
                    next_name = type(self._adapters[idx + 1]).__name__
                    logger.warning(
                        "%s exhausted, falling through to next adapter (%s). Error: %s",
                        name,
                        next_name,
                        exc,
                    )
                continue

        raise RuntimeError(
            f"All adapters exhausted ({len(self._adapters)} tried). Errors:\n"
            + "\n".join(f"  {n}: {e}" for n, e in errors)
        )

    def health_check(self) -> bool:
        return any(a.health_check() for a in self._adapters)

    def __repr__(self) -> str:
        inner = ", ".join(type(a).__name__ for a in self._adapters)
        return f"ChainAdapter([{inner}])"
