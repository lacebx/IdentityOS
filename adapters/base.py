from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class AdapterMessage:
    """A single message in a conversation format."""
    role: str   # "system", "user", "assistant"
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AdapterRequest:
    """The fully assembled request sent to an LLM adapter."""
    messages: List[AdapterMessage]
    identity_id: str = ""
    model: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 1024
    stream: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AdapterResponse:
    """The response returned from an LLM adapter."""
    content: str
    model: str = ""
    usage: Dict[str, int] = field(default_factory=dict)  # prompt/completion/total tokens
    finish_reason: str = "stop"
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseAdapter(ABC):
    """
    Abstract base class for all LLM adapters.

    An adapter is a thin translation layer between the IdentityRuntime
    and a specific LLM provider (OpenAI, Anthropic, Ollama, etc.).

    Adapters receive:
    - A composed context string (system prompt + identity context)
    - The user input
    - The active identity

    Adapters return raw string output. Post-processing is handled by the runtime.

    Design principle: adapters are DUMB. They translate and call. No logic.
    """

    def __init__(self, model: str = "", **kwargs):
        self.model = model
        self.config = kwargs

    @abstractmethod
    def generate(
        self,
        context: str,
        user_input: str,
        identity: Any,
        **kwargs
    ) -> str:
        """
        Generate a response from the LLM.

        Args:
            context: The rendered system context from ContextComposer.
            user_input: The sanitized user input.
            identity: The active Identity object.

        Returns:
            Raw string output from the LLM.
        """
        ...

    def build_messages(
        self, context: str, user_input: str
    ) -> List[AdapterMessage]:
        """Helper to build a standard message list."""
        return [
            AdapterMessage(role="system", content=context),
            AdapterMessage(role="user", content=user_input),
        ]

    def health_check(self) -> bool:
        """Optional: verify the adapter can reach its backend."""
        return True

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(model={self.model!r})"
