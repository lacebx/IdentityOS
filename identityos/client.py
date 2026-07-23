"""
IdentityOS HTTP client — communicate with a remote Identity Runtime API.

Usage:
    from identityos.client import IdentityClient

    client = IdentityClient(base_url="http://localhost:8765")

    # Create an identity
    client.create_identity("pluto", name="Pluto", base_model="gpt-4o")

    # Add a memory
    client.add_memory("pluto", "I met Gesicht today. He feels something.", source="story")

    # Build context for a prompt
    ctx = client.build_context("pluto", recent_messages=[], max_tokens=800)
    print(ctx["context_block"])
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

try:
    import httpx
    _HTTPX_AVAILABLE = True
except ImportError:
    _HTTPX_AVAILABLE = False

try:
    import requests as _requests
    _REQUESTS_AVAILABLE = True
except ImportError:
    _REQUESTS_AVAILABLE = False


class IdentityClientError(Exception):
    """Raised when the Identity Runtime API returns an error."""


class IdentityClient:
    """
    Synchronous HTTP client for the Identity Runtime API.

    Supports both ``httpx`` and ``requests`` as the underlying HTTP library.
    Install one of them:
        pip install httpx
        # or
        pip install requests
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8765",
        timeout: float = 10.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

        if _HTTPX_AVAILABLE:
            self._client = httpx.Client(base_url=self.base_url, timeout=timeout)
            self._mode = "httpx"
        elif _REQUESTS_AVAILABLE:
            self._session = _requests.Session()
            self._mode = "requests"
        else:
            raise ImportError(
                "Either 'httpx' or 'requests' must be installed to use IdentityClient.\n"
                "  pip install httpx"
            )

    # ─── Internal ────────────────────────────────────────────────────────────────

    def _get(self, path: str) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        if self._mode == "httpx":
            r = self._client.get(path)
        else:
            r = self._session.get(url, timeout=self.timeout)
        self._raise_for_status(r)
        return r.json()

    def _post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        if self._mode == "httpx":
            r = self._client.post(path, json=payload)
        else:
            r = self._session.post(url, json=payload, timeout=self.timeout)
        self._raise_for_status(r)
        return r.json()

    def _delete(self, path: str) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        if self._mode == "httpx":
            r = self._client.delete(path)
        else:
            r = self._session.delete(url, timeout=self.timeout)
        self._raise_for_status(r)
        return r.json()

    @staticmethod
    def _raise_for_status(response: Any) -> None:
        status = response.status_code
        if status >= 400:
            try:
                detail = response.json().get("detail", response.text)
            except Exception:
                detail = response.text
            raise IdentityClientError(f"HTTP {status}: {detail}")

    # ─── Health ──────────────────────────────────────────────────────────────────

    def health(self) -> Dict[str, Any]:
        """Ping the runtime. Returns {'status': 'ok', ...}."""
        return self._get("/health")

    # ─── Identity CRUD ───────────────────────────────────────────────────────────

    def list_identities(self) -> List[str]:
        """Return a list of all identity IDs."""
        data = self._get("/identity")
        return data.get("identities", [])

    def get_identity(self, identity_id: str) -> Dict[str, Any]:
        """Fetch the full spec for a single identity."""
        return self._get(f"/identity/{identity_id}")

    def create_identity(
        self,
        identity_id: str,
        name: str = "",
        base_model: str = "model-agnostic",
        traits: Optional[List[str]] = None,
        memory_enabled: bool = True,
        eval_hooks: Optional[List[str]] = None,
        avatar: str = "⬡",
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create or overwrite an identity.

        Args:
            identity_id: Unique slug (e.g. "pluto").
            name: Human-readable display name.
            base_model: The default model this identity was shaped on.
            traits: List of trait descriptors (e.g. ["curious", "melancholic"]).
            memory_enabled: Whether episodic memory is active.
            eval_hooks: List of eval module names to run on each turn.
            avatar: Single emoji / character shown in the extension UI.
            extra: Any additional fields to merge into the spec.
        """
        payload: Dict[str, Any] = {
            "id": identity_id,
            "name": name or identity_id,
            "base_model": base_model,
            "traits": traits or [],
            "memory_enabled": memory_enabled,
            "eval_hooks": eval_hooks or [],
            "avatar": avatar,
        }
        if extra:
            payload.update(extra)
        return self._post(f"/identity/{identity_id}", payload)

    def delete_identity(self, identity_id: str) -> Dict[str, Any]:
        """Permanently delete an identity and all its memories."""
        return self._delete(f"/identity/{identity_id}")

    # ─── Memory ──────────────────────────────────────────────────────────────────

    def add_memory(
        self,
        identity_id: str,
        content: str,
        source: str = "api",
        memory_type: str = "episodic",
    ) -> Dict[str, Any]:
        """
        Persist a new memory fragment for an identity.

        Args:
            identity_id: The identity to store this memory under.
            content: The raw text to store and embed.
            source: Where it came from (e.g. "chatgpt", "grok", "api").
            memory_type: "episodic" | "semantic" | "core".
        """
        return self._post(
            f"/memory/{identity_id}",
            {"content": content, "source": source, "type": memory_type},
        )

    def search_memories(
        self,
        identity_id: str,
        query: str,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Semantic search over an identity's memory.

        Returns a list of memory objects ordered by relevance.
        """
        data = self._post(
            f"/memory/{identity_id}/search",
            {"query": query, "top_k": top_k},
        )
        return data.get("results", [])

    # ─── Context building ────────────────────────────────────────────────────────

    def build_context(
        self,
        identity_id: str,
        recent_messages: Optional[List[Dict[str, str]]] = None,
        max_tokens: int = 800,
    ) -> Dict[str, Any]:
        """
        Build a context block to prepend to a model prompt.

        Args:
            identity_id: Which identity to build context for.
            recent_messages: Last N messages in [{"role": ..., "content": ...}] format.
            max_tokens: Approximate token budget for the context block.

        Returns:
            dict with keys: ``context_block`` (str), ``token_estimate`` (int).
        """
        return self._post(
            f"/context/{identity_id}",
            {
                "recent_messages": recent_messages or [],
                "max_tokens": max_tokens,
            },
        )

    # ─── Eval ────────────────────────────────────────────────────────────────────

    def evaluate_response(
        self,
        identity_id: str,
        prompt: str,
        response: str,
    ) -> Dict[str, Any]:
        """
        Run the configured eval hooks against a model response.

        Returns a dict with per-hook scores and an overall alignment score.
        """
        return self._post(
            f"/eval/{identity_id}",
            {"prompt": prompt, "response": response},
        )

    # ─── Context manager ─────────────────────────────────────────────────────────

    def __enter__(self) -> "IdentityClient":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def close(self) -> None:
        """Release underlying HTTP connections."""
        if self._mode == "httpx" and hasattr(self, "_client"):
            self._client.close()
        elif self._mode == "requests" and hasattr(self, "_session"):
            self._session.close()
