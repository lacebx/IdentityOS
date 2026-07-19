from __future__ import annotations

from typing import TYPE_CHECKING, Any, List, Optional

if TYPE_CHECKING:
    from core.goals import Goal
    from core.identity import IdentitySpec
    from core.knowledge import KnowledgePack
    from runtime.orchestrator import IdentityRuntime


class IdentityObject:
    """
    The primary SDK interface for interacting with an identity.

    This is how developers actually USE the IdentityOS.
    Instead of managing stores, engines, and configs directly,
    they interact with a live identity object that feels
    like communicating with an individual:

        mentor = runtime.load("mentor-identity-id")
        response = mentor.chat("Help me plan this project")
        mentor.remember("User prefers bullet points")
        mentor.pursue("Finish the identity-runtime MVP")

    The IdentityObject is a thin, ergonomic facade over the Runtime.
    It does not contain logic — it delegates to the Runtime pipeline.
    """

    def __init__(self, runtime: "IdentityRuntime", identity_id: str):
        self._runtime = runtime
        self._identity_id = identity_id
        self._session_id: Optional[str] = None

    # ------------------------------------------------------------------
    # Identity Access
    # ------------------------------------------------------------------

    @property
    def identity(self) -> Optional["IdentitySpec"]:
        return self._runtime.identity_store.get(self._identity_id)

    @property
    def name(self) -> str:
        id_obj = self.identity
        return id_obj.name if id_obj else "Unknown"

    @property
    def id(self) -> str:
        return self._identity_id

    # ------------------------------------------------------------------
    # Session Management
    # ------------------------------------------------------------------

    def begin_session(self, session_id: Optional[str] = None) -> "IdentityObject":
        """Start a new session. Returns self for chaining."""
        self._session_id = self._runtime.start_session(
            self._identity_id, session_id=session_id
        )
        return self

    def end_session(self) -> None:
        """End the current session."""
        if self._session_id:
            self._runtime.end_session(self._session_id)
            self._session_id = None

    # ------------------------------------------------------------------
    # Core Interaction
    # ------------------------------------------------------------------

    def chat(self, message: str, **kwargs) -> str:
        """
        Send a message to this identity and get a response.
        This is the primary interaction method.
        """
        from runtime.orchestrator import InteractionRequest
        request = InteractionRequest(
            identity_id=self._identity_id,
            user_input=message,
            session_id=self._session_id,
            metadata=kwargs,
        )
        response = self._runtime.process(request)
        return response.output

    def ask(self, question: str) -> str:
        """Alias for chat(). Semantically cleaner for Q&A use cases."""
        return self.chat(question)

    def instruct(self, instruction: str) -> str:
        """Alias for chat(). Semantically cleaner for instruction use cases."""
        return self.chat(instruction)

    # ------------------------------------------------------------------
    # Memory Interface
    # ------------------------------------------------------------------

    def remember(self, content: str, tags: Optional[List[str]] = None) -> None:
        """
        Store a memory for this identity.
        """
        from core.memory import MemoryFragment, MemoryType
        self._runtime.memory_store.add(MemoryFragment(
            identity_id=self._identity_id,
            content=content,
            memory_type=MemoryType.SEMANTIC,
            session_id=self._session_id,
            tags=tags or [],
        ))

    def recall(self, query: str, limit: int = 5) -> List[str]:
        """
        Retrieve memories relevant to a query.
        """
        items = self._runtime.memory_store.search_keywords(
            query, identity_id=self._identity_id, limit=limit
        )
        return [item.content for item in items]

    def forget(self, memory_id: str) -> bool:
        """Remove a specific memory by ID."""
        return self._runtime.memory_store.remove(memory_id)

    # ------------------------------------------------------------------
    # Goals Interface
    # ------------------------------------------------------------------

    def pursue(self, title: str, description: str = "", **kwargs) -> "Goal":
        """
        Add a goal for this identity to pursue.
        """
        from core.goals import Goal
        goal = Goal(
            title=title,
            description=description,
            **kwargs
        )
        self._runtime.goal_engine.add(goal)
        return goal

    def current_goals(self) -> List["Goal"]:
        """Return all active goals for this identity."""
        return self._runtime.goal_engine.active()

    # ------------------------------------------------------------------
    # Knowledge Interface
    # ------------------------------------------------------------------

    def load_knowledge(self, pack: "KnowledgePack") -> None:
        """Load a knowledge pack into this identity's knowledge base."""
        self._runtime.knowledge_base.load(pack)

    def unload_knowledge(self, pack_id: str) -> bool:
        """Unload a knowledge pack by ID."""
        return self._runtime.knowledge_base.unload(pack_id)

    # ------------------------------------------------------------------
    # Skills Interface
    # ------------------------------------------------------------------

    def can(self, skill_name: str) -> bool:
        """Check if this identity has a registered skill."""
        return self._runtime.skill_registry.get_by_name(skill_name) is not None

    def do(self, skill_name: str, **kwargs) -> Any:
        """
        Invoke a skill by name.
        """
        result = self._runtime.skill_registry.invoke(skill_name, **kwargs)
        if not result.success:
            raise RuntimeError(f"Skill '{skill_name}' failed: {result.error}")
        return result.output

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def describe(self) -> str:
        """Return a human-readable description of this identity's current state."""
        id_obj = self.identity
        if not id_obj:
            return f"Identity '{self._identity_id}' not found."
        goals = self._runtime.goal_engine.active()
        memories = self._runtime.memory_store.recent(
            identity_id=self._identity_id, n=3
        )
        lines = [
            f"Identity: {id_obj.name}",
            f"Role: {id_obj.role}",
            f"Active Goals: {len(goals)}",
            f"Recent Memories: {len(memories)}",
        ]
        return "\n".join(lines)

    def __repr__(self) -> str:
        return f"IdentityObject(name={self.name!r}, id={self._identity_id!r})"

    def __str__(self) -> str:
        return self.name


def load_identity(runtime: "IdentityRuntime", identity_id: str) -> IdentityObject:
    """
    Convenience function to load an identity from a runtime.
    """
    identity = runtime.identity_store.get(identity_id)
    if not identity:
        raise ValueError(f"Identity '{identity_id}' not found in runtime.")
    return IdentityObject(runtime=runtime, identity_id=identity_id)
