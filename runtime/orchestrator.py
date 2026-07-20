from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.cognitive_engine import ComposedContext, ContextComposer
from core.evaluation import (
    EvaluationEngine,
    classify_memory_type,
    is_worth_remembering,
)
from core.goals import GoalEngine
from core.identity import IdentitySpec, IdentityStore
from core.memory import MemoryFragment, MemoryStore, MemoryType
from core.motivations import MotivationEngine
from core.policies import PolicyEngine, PolicyScope
from core.relationships import EdgeType, IdentityGraph, TrustLevel
from core.skills import SkillRegistry
from core.timeline import LifeEvent, LifeEventType, TimelineRegistry
from runtime.event_bus import EventBus, EventType


@dataclass
class InteractionRequest:
    """A single interaction directed at a loaded identity."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    identity_id: str = ""
    user_input: str = ""
    session_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


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
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


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
        """Load an identity by ID. Falls back to the persistence backend."""
        cached = self.identity_store.get(identity_id)
        if cached:
            return cached
        if self._storage:
            snapshot = self._storage.load(identity_id, "latest_snapshot")
            if not snapshot:
                snapshot = self._storage.load_latest(identity_id)
            if snapshot:
                identity_data = snapshot.get("modules", {}).get("identity", snapshot)
                if isinstance(identity_data.get("created_at"), (int, float)):
                    from datetime import datetime, timezone
                    identity_data["created_at"] = (
                        datetime.fromtimestamp(identity_data["created_at"], tz=timezone.utc)
                        .isoformat()
                    )
                spec = IdentitySpec.from_dict(identity_data)
                self.identity_store.save(spec)
                self.timeline_registry.create(spec.id)
                self._load_timeline(spec.id)
                self._load_relationships(spec.id)
                self._load_goals(spec.id)
                return spec
        return None

    def register(self, identity: IdentitySpec) -> None:
        """Register a new identity with the runtime and persist."""
        self.identity_store.save(identity)
        self.timeline_registry.create(identity.id)
        if self._storage:
            snapshot_data = identity.to_dict()
            self._storage.save(identity.id, "identity_spec", snapshot_data)
            self._storage.save(
                identity.id,
                "latest_snapshot",
                {"modules": {"identity": snapshot_data}},
            )
        self._emit(
            EventType.IDENTITY_LOADED,
            identity_id=identity.id,
            name=identity.name,
        )

    def load_persisted(self) -> int:
        """Load all identities from the persistence backend into the in-memory store.

        Also loads persisted memories for each identity.

        Returns the number of identities loaded.
        """
        if not self._storage:
            return 0
        ids = self._storage.list_identities()
        count = 0
        for identity_id in ids:
            if self.load(identity_id):
                self._load_persisted_memories(identity_id)
                count += 1
        return count

    def _load_persisted_memories(self, identity_id: str) -> int:
        """Load persisted memories for an identity into the in-memory store."""
        if not self._storage:
            return 0
        mem_dicts = self._storage.load_memories(identity_id)
        count = 0
        for d in mem_dicts:
            try:
                frag = MemoryFragment.from_dict(d)
                self.memory_store.add(frag)
                count += 1
            except Exception:
                continue
        return count

    def _persist_memory(self, memory: MemoryFragment) -> None:
        """Persist a single memory fragment to the storage backend."""
        if not self._storage:
            return
        try:
            self._storage.save_memory(memory.identity_id, memory.to_dict())
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Timeline Persistence
    # ------------------------------------------------------------------

    def _persist_timeline(self, identity_id: str) -> None:
        if not self._storage:
            return
        timeline = self.timeline_registry.get(identity_id)
        if not timeline:
            return
        try:
            events_data = []
            for event in timeline.events():
                d = {
                    "id": event.id,
                    "identity_id": event.identity_id,
                    "event_type": event.event_type.value,
                    "title": event.title,
                    "description": event.description,
                    "significance": event.significance,
                    "linked_entity_id": event.linked_entity_id,
                    "occurred_at": event.occurred_at.isoformat(),
                    "metadata": event.metadata,
                }
                events_data.append(d)
            self._storage.save(identity_id, "timeline", {
                "events": events_data,
                "created_at": timeline.created_at.isoformat(),
            })
        except Exception:
            pass

    def _load_timeline(self, identity_id: str) -> None:
        if not self._storage:
            return
        try:
            data = self._storage.load(identity_id, "timeline")
            if not data:
                return
            from datetime import datetime
            timeline = self.timeline_registry.get_or_create(identity_id)
            for ed in data.get("events", []):
                if ed.get("event_type") == "creation":
                    continue
                event = LifeEvent(
                    id=ed["id"],
                    identity_id=ed["identity_id"],
                    event_type=LifeEventType(ed["event_type"]),
                    title=ed.get("title", ""),
                    description=ed.get("description", ""),
                    significance=ed.get("significance", 3),
                    linked_entity_id=ed.get("linked_entity_id"),
                    occurred_at=datetime.fromisoformat(ed["occurred_at"]),
                    metadata=ed.get("metadata", {}),
                )
                timeline.record(event)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Relationship Persistence
    # ------------------------------------------------------------------

    def _persist_relationships(self, identity_id: str) -> None:
        if not self._storage:
            return
        try:
            edges = self.identity_graph.get_relationships(identity_id)
            edges_data = []
            for e in edges:
                edges_data.append({
                    "id": e.id,
                    "source_id": e.source_id,
                    "target_id": e.target_id,
                    "edge_type": e.edge_type.value,
                    "trust_level": e.trust_level.value,
                    "strength": e.strength,
                    "bidirectional": e.bidirectional,
                    "context": e.context,
                    "permissions": e.permissions,
                    "labels": e.labels,
                    "established_at": e.established_at.isoformat(),
                    "last_interaction": e.last_interaction.isoformat() if e.last_interaction else None,
                    "interaction_count": e.interaction_count,
                    "metadata": e.metadata,
                })
            self._storage.save(identity_id, "relationships", {"edges": edges_data})
        except Exception:
            pass

    def _load_relationships(self, identity_id: str) -> None:
        if not self._storage:
            return
        try:
            data = self._storage.load(identity_id, "relationships")
            if not data:
                return
            for ed in data.get("edges", []):
                self.identity_graph.connect(
                    source_id=ed["source_id"],
                    target_id=ed["target_id"],
                    edge_type=EdgeType(ed["edge_type"]),
                    trust_level=TrustLevel(ed["trust_level"]),
                    bidirectional=ed.get("bidirectional", False),
                )
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Goal Persistence
    # ------------------------------------------------------------------

    def _persist_goals(self, identity_id: str) -> None:
        if not self._storage:
            return
        try:
            goals_data = []
            for g in self.goal_engine.active():
                goals_data.append({
                    "id": g.id,
                    "title": g.title,
                    "description": g.description,
                    "status": g.status.value,
                    "priority": g.priority.value,
                    "scope": g.scope.value,
                    "parent_id": g.parent_id,
                    "progress": g.progress,
                    "created_at": g.created_at.isoformat(),
                    "updated_at": g.updated_at.isoformat(),
                    "deadline": g.deadline.isoformat() if g.deadline else None,
                    "tags": g.tags,
                    "metadata": g.metadata,
                    "success_criteria": g.success_criteria,
                    "required_skills": g.required_skills,
                    "required_knowledge": g.required_knowledge,
                })
            self._storage.save(identity_id, "goals", {"goals": goals_data})
        except Exception:
            pass

    def _load_goals(self, identity_id: str) -> None:
        if not self._storage:
            return
        try:
            data = self._storage.load(identity_id, "goals")
            if not data:
                return
            from datetime import datetime
            from core.goals import Goal, GoalStatus, GoalPriority, GoalScope
            for gd in data.get("goals", []):
                goal = Goal(
                    id=gd["id"],
                    title=gd["title"],
                    description=gd.get("description", ""),
                    status=GoalStatus(gd["status"]),
                    priority=GoalPriority(gd["priority"]),
                    scope=GoalScope(gd.get("scope", "persistent")),
                    parent_id=gd.get("parent_id"),
                    progress=gd.get("progress", 0.0),
                    created_at=datetime.fromisoformat(gd["created_at"]),
                    updated_at=datetime.fromisoformat(gd["updated_at"]),
                    deadline=datetime.fromisoformat(gd["deadline"]) if gd.get("deadline") else None,
                    tags=gd.get("tags", []),
                    metadata=gd.get("metadata", {}),
                    success_criteria=gd.get("success_criteria", ""),
                    required_skills=gd.get("required_skills", []),
                    required_knowledge=gd.get("required_knowledge", []),
                )
                self.goal_engine.add(goal)
        except Exception:
            pass

    def _extract_and_store_semantic_memory(
        self,
        user_input: str,
        output: str,
        identity_id: str,
        session_id: Optional[str] = None,
    ) -> Optional[MemoryFragment]:
        """Classify user input and store a SEMANTIC memory if warranted.

        Evolves existing semantic facts rather than duplicating:
        - If a semantic memory of the same type with overlapping keywords exists,
          update its content and reinforce importance
        - Otherwise create a new semantic memory
        """
        if not is_worth_remembering(user_input, output):
            return None
        mem_type_str = classify_memory_type(user_input, output)
        if mem_type_str == "general":
            return None

        # Extract key tokens from the input for dedup matching
        input_lower = user_input.lower()
        key_tokens = {w for w in input_lower.split() if len(w) > 3}

        # Look for an existing semantic memory of the same type with overlapping content
        existing = self._find_semantic_match(identity_id, mem_type_str, key_tokens, input_lower)

        if existing is not None:
            # Evolve existing fact
            existing.content = user_input
            existing.importance = min(1.0, existing.importance + 0.1)
            existing.last_accessed = datetime.now(timezone.utc).replace(tzinfo=None)
            existing.access_count += 1
            self._persist_memory(existing)
            return existing

        semantic = MemoryFragment(
            identity_id=identity_id,
            content=user_input,
            memory_type=MemoryType.SEMANTIC,
            source="extraction",
            session_id=session_id,
            importance=0.7,
            tags=["semantic", mem_type_str],
        )
        self.memory_store.add(semantic)
        self._persist_memory(semantic)
        return semantic

    def _find_semantic_match(
        self,
        identity_id: str,
        mem_type: str,
        key_tokens: set,
        input_lower: str,
    ) -> Optional[MemoryFragment]:
        """Find an existing semantic memory that this new fact should replace."""
        for frag in self.memory_store.by_identity(identity_id):
            if frag.memory_type != MemoryType.SEMANTIC:
                continue
            if mem_type not in frag.tags:
                continue
            existing_lower = frag.content.lower()
            overlap = key_tokens & {w for w in existing_lower.split() if len(w) > 3}
            if len(overlap) >= 2:
                return frag
        return None

    def list_identities(self) -> List[IdentitySpec]:
        return self.identity_store.list_all()

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
            motivation_engine=self.motivation_engine,
            timeline_registry=self.timeline_registry,
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
            import time as _time
            _t0 = _time.monotonic()
            raw_output = self.adapter.generate(
                context=context.render(),
                user_input=sanitized_input,
                identity=identity,
            )
            _latency = _time.monotonic() - _t0
            self._emit(
                EventType.MODEL_RESPONDED,
                identity_id=identity.id,
                session_id=request.session_id,
                model=self.adapter.model,
                response_length=len(raw_output),
                latency_ms=round(_latency * 1000),
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
            criteria_count=len(eval_report.records),
        )

        # Stage 7: Store interaction in memory
        # 7a: Always store the raw interaction as an EPISODIC memory
        episodic = MemoryFragment(
            identity_id=identity.id,
            content=f"User: {sanitized_input}\nAssistant: {final_output}",
            memory_type=MemoryType.EPISODIC,
            session_id=request.session_id,
            tags=["interaction"],
        )
        self.memory_store.add(episodic)
        self._persist_memory(episodic)

        self._emit(
            EventType.EXPERIENCE_RECORDED,
            identity_id=identity.id,
            session_id=request.session_id,
            memory_id=episodic.id,
            memory_type=episodic.memory_type.value,
            content=episodic.content[:200],
        )

        # 7b: Extract and store semantic memories (preferences, decisions, etc.)
        semantic_mem = self._extract_and_store_semantic_memory(
            user_input=sanitized_input,
            output=final_output,
            identity_id=identity.id,
            session_id=request.session_id,
        )

        # Determine timeline title from semantic classification
        tl_title = "Interaction"
        tl_description = f"User said: {sanitized_input[:100]}"
        tl_meta = {"session_id": request.session_id, "eval_score": eval_report.overall_score}
        if semantic_mem:
            mem_tags = semantic_mem.tags
            if "preference" in mem_tags:
                tl_title = "Learned preference"
                tl_description = sanitized_input[:120]
            elif "decision" in mem_tags:
                tl_title = "Made decision"
                tl_description = sanitized_input[:120]
            elif "correction" in mem_tags:
                tl_title = "Received correction"
                tl_description = sanitized_input[:120]
            elif "milestone" in mem_tags:
                tl_title = "Milestone"
                tl_description = sanitized_input[:120]
            tl_meta["memory_id"] = semantic_mem.id
            tl_meta["memory_type"] = semantic_mem.memory_type.value

        # Stage 8: Record timeline life event
        self.timeline_registry.record_event(
            identity.id,
            LifeEvent(
                identity_id=identity.id,
                event_type=LifeEventType.MILESTONE,
                title=tl_title,
                description=tl_description,
                significance=2,
                metadata=tl_meta,
            ),
        )
        self._persist_timeline(identity.id)
        self._emit(
            EventType.LIFE_EVENT_RECORDED,
            identity_id=identity.id,
            session_id=request.session_id,
            title=tl_title,
            description=tl_description,
        )

        # Stage 9: Update relationship graph — reuse existing edge, evolve it
        target = request.session_id or "user"
        self.identity_graph.interact_or_connect(
            source_id=identity.id,
            target_id=target,
            edge_type=EdgeType.PEER,
            bidirectional=False,
        )
        self._persist_relationships(identity.id)

        # Stage 10: Persist goals
        self._persist_goals(identity.id)

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
