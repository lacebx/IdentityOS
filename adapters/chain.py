from __future__ import annotations

import logging
from typing import Any, Optional

from .base import BaseAdapter

logger = logging.getLogger(__name__)

_EXHAUSTION_MARKERS = [
    "api keys exhausted",
    "all adapters exhausted",
]

# Provider-level failures that should fall through to the next adapter in the
# chain rather than abort it with an unhandled traceback: rate limiting,
# quota/account issues, auth failures, bad gateway, and connectivity errors.
_FALLTHROUGH_MARKERS = [
    "429",
    "rate limit",
    "rate_limit",
    "insufficient_quota",
    "quota exceeded",
    "401",
    "authentication",
    "invalid_api_key",
    "invalid api key",
    "403",
    "permission denied",
    "502",
    "503",
    "bad gateway",
    "service unavailable",
    "connection error",
    "connection refused",
    "timed out",
    "timeout",
    "api status error",
]


class ChainAdapter(BaseAdapter):
    """
    Tries multiple adapters in sequence, falling through when one is exhausted.

    Each adapter handles its own internal key rotation (e.g. GroqAdapter
    rotates through GROQ_API_KEY[1..6] with cooldown).  When ALL keys
    for a given provider are exhausted — or the adapter has no valid keys —
    ``ChainAdapter`` catches the exhaustion error and moves to the next
    adapter in the chain.

    Provider-level failures (rate limits, auth errors, 5xx, connectivity)
    are also treated as fallthrough triggers so one provider's outage never
    crashes the whole chain.
    """

    def __init__(
        self,
        adapters: list[BaseAdapter],
        model: str = "",
    ) -> None:
        self._adapters = adapters
        first = adapters[0] if adapters else None
        super().__init__(model=model or (first.model if first else ""))

    @property
    def model(self) -> str:
        return self._model or (self._adapters[0].model if self._adapters else "")

    @model.setter
    def model(self, val: str) -> None:
        self._model = val

    def _is_exhaustion(self, error: Exception) -> bool:
        msg = str(error).lower()
        if any(marker in msg for marker in _EXHAUSTION_MARKERS):
            return True
        # Provider-level failures are non-fatal to the chain: fall through so
        # the next adapter gets a chance instead of raising an unhandled error.
        return any(marker in msg for marker in _FALLTHROUGH_MARKERS)

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

        for idx, adapter in enumerate(self._adapters):
            name = type(adapter).__name__
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
                if not self._is_exhaustion(exc):
                    raise  # Non-exhaustion errors propagate immediately
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
