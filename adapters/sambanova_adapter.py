from __future__ import annotations

import logging
import os
import time
from typing import Any, List, Optional

from .openai_adapter import OpenAIAdapter

logger = logging.getLogger(__name__)


class SambaNovaAdapter(OpenAIAdapter):
    """
    Adapter for SambaNova with automatic API key rotation on rate limits.

    Supports multiple API keys via environment variables:
        SAMBANOVA_API_KEY    — primary key
        SAMBANOVA_API_KEY_2  — first fallback
        SAMBANOVA_API_KEY_3  — second fallback

    When one key hits a 429 / rate-limit error, the adapter rotates
    to the next key. If all keys are rate-limited, it waits for
    the shortest retry-after and retries.
    """

    def __init__(
        self,
        model: str = "DeepSeek-V3.1",
        api_key: Optional[str] = None,
        base_url: str = "https://api.sambanova.ai/v1",
        api_keys: Optional[List[str]] = None,
        **kwargs: Any,
    ):
        self._keys: List[str] = api_keys or []
        if not self._keys:
            seen = set()
            for env_var in ("SAMBANOVA_API_KEY", "SAMBANOVA_API_KEY_2", "SAMBANOVA_API_KEY_3"):
                val = os.environ.get(env_var)
                if val and val.strip() and val not in seen:
                    seen.add(val)
                    self._keys.append(val)
            if api_key and api_key not in seen:
                self._keys.insert(0, api_key)

        if not self._keys:
            key = api_key or os.environ.get("SAMBANOVA_API_KEY")
            if key:
                self._keys = [key]
            else:
                logger.warning("No valid SambaNova API keys found")

        self._cooldowns: dict = {}
        self._key_index = 0
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
        now = time.time()
        for _ in range(len(self._keys) - 1):
            self._key_index = (self._key_index + 1) % len(self._keys)
            cooldown_until = self._cooldowns.get(self._key_index, 0)
            if cooldown_until <= now:
                logger.info(f"Rotated to SambaNova API key index {self._key_index}")
                print(f"  [SambaNova: switching to key {self._key_index + 1}/{len(self._keys)}]", flush=True)
                self.api_key = self._keys[self._key_index]
                self._client = None
                return self.api_key
        return None

    def _wait_shortest_cooldown(self, retry_after: float = 60):
        now = time.time()
        min_wait = retry_after
        for idx, until in self._cooldowns.items():
            remaining = until - now
            if 0 < remaining < min_wait:
                min_wait = remaining
        if min_wait > 0:
            logger.warning(f"All keys on cooldown. Waiting {min_wait:.0f}s...")
            time.sleep(min_wait + 1)
        self._key_index = 0
        self._rotate_key()

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
                    retries=1,  # Parent retry disabled — SambaNovaAdapter handles rotation
                    **kwargs,
                )
            except RuntimeError as exc:
                last_error = exc
                msg = str(exc)
                msg_lower = msg.lower()
                if "429" in msg_lower or "rate limit" in msg_lower or "quota" in msg_lower:
                    retry_after = 60
                    logger.warning(f"Rate limited on key {self._key_index}")
                    print(f"  [SambaNova: key {self._key_index + 1}/{len(self._keys)} rate limited, cooldown 60s]", flush=True)
                    self._cooldowns[self._key_index] = time.time() + retry_after
                    if self._rotate_key() is None:
                        self._wait_shortest_cooldown(retry_after)
                    continue
                raise

        raise RuntimeError(
            f"All SambaNova API keys exhausted. Last error: {last_error}"
        ) from last_error
