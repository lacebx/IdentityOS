from __future__ import annotations

import logging
import os
import time
from typing import Any, List, Optional

from .openai_adapter import OpenAIAdapter

logger = logging.getLogger(__name__)


class GroqAdapter(OpenAIAdapter):
    """
    Adapter for Groq with automatic API key rotation on rate limits.

    Supports multiple API keys via environment variables:
        GROQ_API_KEY    — primary key
        GROQ_API_KEY_2  — first fallback
        GROQ_API_KEY_3  — second fallback
        GROQ_API_KEY_4  — third fallback

    When one key hits a 429 / rate-limit error, the adapter waits
    for the retry-after window, then rotates to the next key.
    If all keys are rate-limited simultaneously, it waits for
    the shortest retry-after and retries.
    """

    def __init__(
        self,
        model: str = "llama-3.3-70b-versatile",
        api_key: Optional[str] = None,
        base_url: str = "https://api.groq.com/openai/v1",
        api_keys: Optional[List[str]] = None,
        **kwargs: Any,
    ):
        base_url = os.environ.get("GROQ_BASE_URL", base_url)

        # Collect all available keys
        self._keys: List[str] = api_keys or []
        if not self._keys:
            seen = set()
            for env_var in ("GROQ_API_KEY", "GROQ_API_KEY_2", "GROQ_API_KEY_3", "GROQ_API_KEY_4", "GROQ_API_KEY_5", "GROQ_API_KEY_6"):
                val = os.environ.get(env_var)
                if val and val.strip() and "PLACEHOLDER" not in val and val not in seen:
                    seen.add(val)
                    self._keys.append(val)
            if api_key and api_key not in seen:
                self._keys.insert(0, api_key)

        if not self._keys:
            logger.warning("No valid Groq API keys found")

        # Track cooldowns per key index: {index: unix_ts_until}
        self._cooldowns: dict = {}
        self._key_index = 0

        # Initialize with the first key
        current_key = self._keys[0] if self._keys else api_key
        super().__init__(
            model=model,
            api_key=current_key,
            base_url=base_url,
            **kwargs,
        )

    def _current_key(self) -> str:
        if not self._keys:
            return self.api_key or ""
        return self._keys[self._key_index]

    def _rotate_key(self) -> Optional[str]:
        """Move to the next key not in cooldown. Returns None if all are on cooldown."""
        now = time.time()
        for _ in range(len(self._keys) - 1):
            self._key_index = (self._key_index + 1) % len(self._keys)
            cooldown_until = self._cooldowns.get(self._key_index, 0)
            if cooldown_until <= now:
                logger.info(f"Rotated to Groq API key index {self._key_index}")
                self.api_key = self._keys[self._key_index]
                self._client = None
                return self.api_key
        return None

    def _wait_shortest_cooldown(self, retry_after: float = 60):
        """Wait for the shortest cooldown to expire, then rotate to that key."""
        now = time.time()
        min_wait = retry_after
        for idx, until in self._cooldowns.items():
            remaining = until - now
            if 0 < remaining < min_wait:
                min_wait = remaining
        if min_wait > 0:
            logger.warning(f"All keys on cooldown. Waiting {min_wait:.0f}s...")
            time.sleep(min_wait + 1)
        # Rotate to the first available key
        self._key_index = 0
        self._rotate_key()

    def _extract_retry_after(self, error_msg: str) -> float:
        """Parse retry-after duration from a Groq 429 error message."""
        import re
        m = re.search(r"try again in ([\d.]+)m?([\d.]+)?s", error_msg.lower())
        if m:
            minutes = float(m.group(1)) if m.group(1) else 0
            seconds = float(m.group(2)) if m.group(2) else 0
            return minutes * 60 + seconds
        return 60  # Default fallback

    def generate(
        self,
        context: str,
        user_input: str,
        identity: Any,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> str:
        last_error = None
        now = time.time()

        for attempt in range(len(self._keys) * 3):
            # Skip keys on cooldown
            cooldown_until = self._cooldowns.get(self._key_index, 0)
            if cooldown_until > now:
                if self._rotate_key() is None:
                    self._wait_shortest_cooldown()
                    now = time.time()

            try:
                return super().generate(
                    context=context,
                    user_input=user_input,
                    identity=identity,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs,
                )
            except RuntimeError as exc:
                last_error = exc
                msg = str(exc)
                msg_lower = msg.lower()
                if "429" in msg_lower or "rate limit" in msg_lower or "quota" in msg_lower or "insufficient_quota" in msg_lower:
                    retry_after = self._extract_retry_after(msg)
                    logger.warning(
                        f"Rate limited on key {self._key_index}, "
                        f"cooldown {retry_after:.0f}s"
                    )
                    self._cooldowns[self._key_index] = time.time() + retry_after
                    if self._rotate_key() is None:
                        self._wait_shortest_cooldown(retry_after)
                    continue
                raise  # Non-retryable error

        raise RuntimeError(
            f"All Groq API keys exhausted. Last error: {last_error}"
        ) from last_error
