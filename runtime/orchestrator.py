from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import uuid
from datetime import datetime

from ..core.identity import Identity, IdentityStore
from ..core.memory import MemoryStore, MemoryItem, MemoryTier
from ..core.knowledge import KnowledgeBase
from ..core.skills import SkillRegistry
from ..core.goals import GoalEngine
from ..core.relationships import IdentityGraph
from ..core.policies import PolicyEngine, PolicyScope
from ..core.evaluation import EvaluationEngine
from ..core.context_composer import ContextComposer, ComposedContext


@dataclass
class InteractionRequest:
    """A single interaction directed at a loaded identity."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    identity_id: str = ""
    user_input: str = ""
    session_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class InteractionResponse:
    """The result of processing an interaction through the runtime."""
    request_id: str
    identity_id: str
    output: str
    context_used: Optional[ComposedContext] = None
    policy_passed: bool = True
    eval_score: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


class IdentityRuntime:
    """
    The IdentityOS Runtime — the microkernel.

    Responsibilities:
    - Load and manage identities
    - Route interactions through the full pipeline:
        Input -> Policy(INPUT) -> ContextCompose -> Adapter -> Policy(OUTPUT)
        -> Evaluate -> Memory(store) -> Response
    - Orchestrate all core modules as services
    - Expose a clean interface to SDK clients and adapters

    The Runtime does NOT contain business logic. It orchestrates modules.
    """

    def __init__(
        self,
        adapter=None,
        max_context_tokens: int = 4000,
    ):
        # Core module instances (shared across identities)
        self.identity_store = IdentityStore()
        self.memory_store = MemoryStore()
        self.knowledge_base = KnowledgeBase()
        self.skill_registry = SkillRegistry()
        self.goal_engine = GoalEngine()
        self.identity_graph = IdentityGraph()
        self.policy_engine = PolicyEngine()
        self.evaluation_engine = EvaluationEngine()
        self.context_composer = ContextComposer(max_tokens=max_context_tokens)

        # Adapter: bridges Runtime to an LLM backend
        self.adapter = adapter

        # Active sessions: session_id -> identity_id
        self._sessions: Dict[str, str] = {}

    # ------------------------------------------------------------------
    # Identity Lifecycle
    # ------------------------------------------------------------------

    def load(self, identity_id: str) -> Optional[Identity]:
        """Load an identity by ID."""
        return self.identity_store.get(identity_id)

    def register(self, identity: Identity) -> None:
        """Register a new identity with the runtime."""
        self.identity_store.save(identity)

    def unload(self, identity_id: str) -> bool:
        """Remove an identity from the runtime."""
        return self.identity_store.delete(identity_id)

    # ------------------------------------------------------------------
    # Session Management
    # ------------------------------------------------------------------

    def start_session(
        self, identity_id: str, session_id: Optional[str] = None
    ) -> str:
        """Start a new session for an identity. Returns session_id."""
        sid = session_id or str(uuid.uuid4())
        self._sessions[sid] = identity_id
        return sid

    def end_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    # ------------------------------------------------------------------
    # Core Interaction Pipeline
    # ------------------------------------------------------------------

    def process(
        self,
        request: InteractionRequest,
        top_k_memories: int = 5,
    ) -> InteractionResponse:
        """
        Full pipeline for processing one interaction.

        Pipeline stages:
        1. Resolve identity
        2. Policy check on input
        3. Compose context
        4. Invoke adapter (LLM call)
        5. Policy check on output
        6. Evaluate response
        7. Store interaction in memory
        8. Return response
        """
        identity = self.identity_store.get(request.identity_id)
        if not identity:
            return InteractionResponse(
                request_id=request.id,
                identity_id=request.identity_id,
                output="[Error] Identity not found.",
                policy_passed=False,
            )

        # Stage 2: Input policy gate
        input_policy = self.policy_engine.evaluate(
            request.user_input, scope=PolicyScope.INPUT
        )
        if not input_policy.allowed:
            return InteractionResponse(
                request_id=request.id,
                identity_id=request.identity_id,
                output="[Blocked] Input did not pass policy check.",
                policy_passed=False,
            )

        sanitized_input = input_policy.transformed_data or request.user_input

        # Stage 3: Compose context
        context = self.context_composer.compose(
            identity=identity,
            memory_store=self.memory_store,
            knowledge_base=self.knowledge_base,
            skill_registry=self.skill_registry,
            goal_engine=self.goal_engine,
            identity_graph=self.identity_graph,
            query=sanitized_input,
            top_k_memories=top_k_memories,
        )

        # Stage 4: Adapter call
        if self.adapter:
            raw_output = self.adapter.generate(
                context=context.render(),
                user_input=sanitized_input,
                identity=identity,
            )
        else:
            raw_output = f"[No adapter configured. Context prepared for {identity.name}]"

        # Stage 5: Output policy gate
        output_policy = self.policy_engine.evaluate(
            raw_output, scope=PolicyScope.OUTPUT
        )
        if not output_policy.allowed:
            final_output = "[Blocked] Output did not pass policy check."
            policy_passed = False
        else:
            final_output = output_policy.transformed_data or raw_output
            policy_passed = True

        # Stage 6: Evaluate
        eval_report = self.evaluation_engine.evaluate(
            identity_id=identity.id,
            interaction_id=request.id,
            input_data=sanitized_input,
            output_data=final_output,
        )

        # Stage 7: Store in memory
        self.memory_store.add(MemoryItem(
            identity_id=identity.id,
            content=f"User: {sanitized_input}\nAssistant: {final_output}",
            tier=MemoryTier.EPISODIC,
            session_id=request.session_id,
            tags=["interaction"],
        ))

        return InteractionResponse(
            request_id=request.id,
            identity_id=identity.id,
            output=final_output,
            context_used=context,
            policy_passed=policy_passed,
            eval_score=eval_report.overall_score,
        )

    def __repr__(self) -> str:
        return (
            f"IdentityRuntime("
            f"identities={len(self.identity_store)}, "
            f"adapter={type(self.adapter).__name__ if self.adapter else 'None'}"
            f")"
        )
