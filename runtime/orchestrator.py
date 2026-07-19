from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional

from core.cognitive_engine import ComposedContext, ContextComposer
from core.evaluation import EvaluationEngine
from core.experience import ExperienceStore
from core.goals import GoalEngine
from core.identity import IdentitySpec, IdentityStore
from core.memory import MemoryFragment, MemoryStore, MemoryType
from core.motivations import MotivationEngine
from core.policies import PolicyEngine, PolicyScope
from core.relationships import IdentityGraph
from core.skills import SkillRegistry
from core.timeline import TimelineRegistry
from runtime.event_bus import EventBus, EventType


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
    - Emit events at each pipeline stage via EventBus

    The Runtime does NOT contain business logic. It orchestrates modules.
    """

    def __init__(
        self,
        adapter=None,
        max_context_tokens: int = 4000,
        storage=None,
    ):
        self.identity_store = IdentityStore()
        self.memory_store = MemoryStore()
        self.experience_store = ExperienceStore()
        self.knowledge_base = SkillRegistry()  # used as KnowledgeBase placeholder
        self.skill_registry = SkillRegistry()
        self.goal_engine = GoalEngine()
        self.identity_graph = IdentityGraph()
        self.policy_engine = PolicyEngine()
        self.evaluation_engine = EvaluationEngine()
        self.context_composer = ContextComposer(max_tokens=max_context_tokens)
        self.motivation_engine = MotivationEngine()
        self.timeline_registry = TimelineRegistry()

        self.adapter = adapter
        self._sessions: Dict[str, str] = {}
        self._storage = storage

        # Event Bus — wired into the pipeline but subscribers are opt-in
        self.event_bus = EventBus()

    # ------------------------------------------------------------------
    # Event helpers
    # ------------------------------------------------------------------

    def _emit(
        self,
        event_type: EventType,
        identity_id: Optional[str] = None,
        session_id: Optional[str] = None,
        **payload,
    ) -> None:
        self.event_bus.emit(
            event_type=event_type,
            source="orchestrator",
            identity_id=identity_id,
            session_id=session_id,
            **payload,
        )

    # ------------------------------------------------------------------
    # Identity Lifecycle
    # ------------------------------------------------------------------

    def load(self, identity_id: str) -> Optional[IdentitySpec]:
        """Load an identity by ID."""
        return self.identity_store.get(identity_id)

    def register(self, identity: IdentitySpec) -> None:
        """Register a new identity with the runtime."""
        self.identity_store.save(identity)
        self.timeline_registry.create(identity.id)
        self._emit(
            EventType.IDENTITY_LOADED,
            identity_id=identity.id,
            name=identity.name,
        )

    def unload(self, identity_id: str) -> bool:
        """Remove an identity from the runtime."""
        self._emit(
            EventType.IDENTITY_UNLOADED,
            identity_id=identity_id,
        )
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
        self._emit(
            EventType.SESSION_STARTED,
            identity_id=identity_id,
            session_id=sid,
        )
        return sid

    def end_session(self, session_id: str) -> None:
        identity_id = self._sessions.pop(session_id, None)
        if identity_id:
            self._emit(
                EventType.SESSION_ENDED,
                identity_id=identity_id,
                session_id=session_id,
            )

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

        Events are emitted at each stage for subscribers on the EventBus.
        """
        # Stage 1: Resolve identity
        identity = self.identity_store.get(request.identity_id)
        if not identity:
            return InteractionResponse(
                request_id=request.id,
                identity_id=request.identity_id,
                output="[Error] Identity not found.",
                policy_passed=False,
            )

        self._emit(
            EventType.MESSAGE_RECEIVED,
            identity_id=identity.id,
            session_id=request.session_id,
            content=request.user_input,
        )

        # Stage 2: Input policy gate
        input_policy = self.policy_engine.evaluate(
            request.user_input, scope=PolicyScope.INPUT
        )
        self._emit(
            EventType.POLICY_TRIGGERED,
            identity_id=identity.id,
            session_id=request.session_id,
            scope="input",
            allowed=input_policy.allowed,
            policies_applied=input_policy.applied_policies,
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
            skill_registry=self.skill_registry,
            goal_engine=self.goal_engine,
            identity_graph=self.identity_graph,
            query=sanitized_input,
            top_k_memories=top_k_memories,
        )

        self._emit(
            EventType.CONTEXT_COMPOSED,
            identity_id=identity.id,
            session_id=request.session_id,
            token_estimate=context.token_estimate(),
        )

        # Stage 4: Adapter call
        if self.adapter:
            self._emit(
                EventType.MODEL_REQUESTED,
                identity_id=identity.id,
                session_id=request.session_id,
                model=self.adapter.model,
            )
            raw_output = self.adapter.generate(
                context=context.render(),
                user_input=sanitized_input,
                identity=identity,
            )
            self._emit(
                EventType.MODEL_RESPONDED,
                identity_id=identity.id,
                session_id=request.session_id,
                model=self.adapter.model,
                response_length=len(raw_output),
            )
        else:
            raw_output = f"[No adapter configured. Context prepared for {identity.name}]"

        # Stage 5: Output policy gate
        output_policy = self.policy_engine.evaluate(
            raw_output, scope=PolicyScope.OUTPUT
        )
        self._emit(
            EventType.POLICY_TRIGGERED,
            identity_id=identity.id,
            session_id=request.session_id,
            scope="output",
            allowed=output_policy.allowed,
            policies_applied=output_policy.applied_policies,
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

        self._emit(
            EventType.EVALUATION_COMPLETED,
            identity_id=identity.id,
            session_id=request.session_id,
            overall_score=eval_report.overall_score,
            passed=eval_report.passed,
        )

        # Stage 7: Store interaction in memory
        memory = MemoryFragment(
            identity_id=identity.id,
            content=f"User: {sanitized_input}\nAssistant: {final_output}",
            memory_type=MemoryType.EPISODIC,
            session_id=request.session_id,
            tags=["interaction"],
        )
        self.memory_store.add(memory)

        self._emit(
            EventType.EXPERIENCE_RECORDED,
            identity_id=identity.id,
            session_id=request.session_id,
            memory_id=memory.id,
            memory_type=memory.memory_type.value,
        )

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
