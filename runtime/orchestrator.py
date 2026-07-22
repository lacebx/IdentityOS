from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from core.cognitive_engine import ComposedContext, ContextComposer
from core.evaluation import (
    EvaluationEngine,
    classify_memory_type,
    is_worth_remembering,
)
from core.goals import GoalEngine
from core.identity import IdentitySpec, IdentityStore, MutabilityLevel
from core.identity_facts import FactStore
from core.identity_mutation import (
    IdentityMutationEngine,
    MutationProposal,
    MutationStatus,
    MutationType,
)
from core.memory import MemoryFragment, MemoryStore, MemoryType
from core.motivations import MotivationEngine
from core.policies import PolicyEngine, PolicyScope
from core.relationships import EdgeType, IdentityGraph, TrustLevel
from core.skills import SkillRegistry
from core.timeline import LifeEvent, LifeEventType, TimelineRegistry
from core.user_profile import UserProfile, extract_user_facts
from runtime.event_bus import EventBus, EventType


class SessionMode(str, Enum):
    """
    Session mode determines how identity evolution is handled.
    Modes are **detected** from user input, not hard-coded per identity.

    NORMAL       — Identity evolves as usual. Mutations are processed against
                   the canonical FactStore.
    ROLEPLAY     — User is roleplaying the identity as a character.
                   Identity mutations are isolated to this session only —
                   they DON'T touch the canonical FactStore.
                   Context includes a roleplay framing directive.
    SIMULATION   — Like roleplay, but explicitly marked as simulation.
    DREAM        — Like simulation, framed as a dream.
    HYPOTHETICAL — Like simulation, framed as hypothetical/what-if.

    Isolated sessions (ROLEPLAY, SIMULATION, DREAM, HYPOTHETICAL) persist
    their identity state in a per-session FactStore fork. When the same
    session_id is used later, the isolated context is restored.
    """
    NORMAL = "normal"
    ROLEPLAY = "roleplay"
    SIMULATION = "simulation"
    DREAM = "dream"
    HYPOTHETICAL = "hypothetical"


@dataclass
class EmotionState:
    """
    The identity's perceived emotional state, extracted from user input
    and conversation context.

    This is stored SEPARATELY from identity facts — emotions are ephemeral
    and should NOT bleed into identity evolution.
    """
    primary_emotion: str = "neutral"
    intensity: float = 0.0          # 0.0 – 1.0
    triggered_by: str = ""           # what in the input triggered this
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_prompt_block(self) -> str:
        if self.primary_emotion == "neutral" and self.intensity < 0.3:
            return ""
        return (
            f"## Current Emotional State\n"
            f"  Mood: {self.primary_emotion}\n"
            f"  Intensity: {self.intensity:.1f}\n"
        )


# Simple emotion extraction patterns
_EMOTION_PATTERNS: Dict[str, List[str]] = {
    "happy": ["happy", "joy", "glad", "wonderful", "great", "excited", "love", "amazing"],
    "sad": ["sad", "unhappy", "depressed", "lonely", "heartbroken", "grief", "crying", "miserable"],
    "angry": ["angry", "furious", "mad", "annoyed", "frustrated", "irritated", "rage", "livid"],
    "anxious": ["anxious", "worried", "nervous", "fearful", "scared", "terrified", "panicked", "stressed"],
    "grateful": ["grateful", "thankful", "appreciative", "blessed", "fortunate"],
    "confused": ["confused", "confusing", "unsure", "uncertain", "perplexed", "baffled", "puzzled"],
    "hurt": ["hurt", "offended", "insulted", "betrayed", "wounded", "pained"],
    "proud": ["proud", "accomplished", "achieved", "triumph", "victory"],
}


def extract_emotion(user_input: str) -> EmotionState:
    """
    Extract the user's emotional state from their input.
    This is the identity's perception of the user's emotion,
    stored separately from identity facts.
    """
    input_lower = user_input.lower()
    best_emotion = "neutral"
    best_intensity = 0.0
    trigger = ""

    for emotion, keywords in _EMOTION_PATTERNS.items():
        for kw in keywords:
            if kw in input_lower:
                intensity = min(1.0, 0.3 + (0.1 * input_lower.count(kw)))
                if intensity > best_intensity:
                    best_intensity = intensity
                    best_emotion = emotion
                    trigger = kw

    return EmotionState(
        primary_emotion=best_emotion,
        intensity=best_intensity,
        triggered_by=trigger,
    )


# Patterns that indicate identity rename attempts
_IDENTITY_RENAME_PATTERNS = re.compile(
    r"(?:your\s+name\s+(?:is|should\s+be|will\s+be|ought\s+to\s+be)\s+(.+?)(?:[.,!?]|$))"
    r"|(?:I\s+(?:will\s+)?(?:call|rename|name)\s+you\s+(.+?)(?:[.,!?]|$))"
    r"|(?:from\s+now\s+on\s+(?:your\s+name\s+is|you\s+are)\s+(.+?)(?:[.,!?]|$))"
    r"|(?:you\s+are\s+now\s+called\s+(.+?)(?:[.,!?]|$))",
    re.IGNORECASE,
)


def detect_identity_rename_attempt(user_input: str) -> Optional[str]:
    """Detect if user is trying to rename the identity. Returns proposed name or None."""
    for m in _IDENTITY_RENAME_PATTERNS.finditer(user_input):
        for g in m.groups():
            if g:
                name = g.strip().rstrip(".,!?").strip()
                if name and len(name) > 1:
                    return name
    return None


# Session mode detection patterns
_ROLEPLAY_TRIGGERS = re.compile(
    r"(?:let'?s\s+role\s*play|pretend(?:\s+that)?|act\s+as)"
    r"(?:[.\s]*(?:you\s+are|you'?re))?"
    r"(?:[.\s]*(?:a|an|the))?\s+(.+?)(?=[.,!?]|$)",
    re.IGNORECASE,
)

_SIMULATION_TRIGGERS = re.compile(
    r"(?:simulate|simulation|in\s+a\s+simulation|this\s+is\s+a\s+simulation)",
    re.IGNORECASE,
)

_DREAM_TRIGGERS = re.compile(
    r"(?:dream|in\s+a\s+dream|imagine\s+a\s+dream|this\s+is\s+a\s+dream)",
    re.IGNORECASE,
)

_HYPOTHETICAL_TRIGGERS = re.compile(
    r"(?:hypothetical|what\s+if|suppose|pretend\s+that|imagine\s+(?:that|if))",
    re.IGNORECASE,
)


def detect_session_mode(user_input: str) -> SessionMode:
    """
    Detect the session mode from user input.

    Detection order (first match wins):
      1. SIMULATION — explicit simulation framing
      2. DREAM — explicit dream framing
      3. HYPOTHETICAL — hypothetical/what-if framing
      4. ROLEPLAY — roleplay / "you are a..." framing
      5. NORMAL — default
    """
    if _SIMULATION_TRIGGERS.search(user_input):
        return SessionMode.SIMULATION
    if _DREAM_TRIGGERS.search(user_input):
        return SessionMode.DREAM
    if _HYPOTHETICAL_TRIGGERS.search(user_input):
        return SessionMode.HYPOTHETICAL
    if _ROLEPLAY_TRIGGERS.search(user_input):
        return SessionMode.ROLEPLAY
    return SessionMode.NORMAL


def _get_roleplay_framing(mode: SessionMode, user_input: str) -> str:
    """Generate roleplay framing directive for isolated sessions."""
    role = ""
    m = _ROLEPLAY_TRIGGERS.search(user_input)
    if m and m.group(1):
        role = m.group(1).strip().rstrip(".,!?")
    framings = {
        SessionMode.ROLEPLAY: "roleplaying",
        SessionMode.SIMULATION: "simulated scenario",
        SessionMode.DREAM: "dream",
        SessionMode.HYPOTHETICAL: "hypothetical scenario",
    }
    label = framings.get(mode, "roleplaying")
    if role:
        return f"You are currently {label} as \"{role}\". Your identity facts below reflect this {label} context."
    return f"You are currently in a {label}. Your identity facts below reflect this {label} context."


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
        self.mutation_engine = IdentityMutationEngine(min_confidence=0.5)
        self.timeline_registry = TimelineRegistry()
        self._fact_stores: Dict[str, FactStore] = {}
        self._user_profiles: Dict[str, UserProfile] = {}

        self.adapter = adapter
        self._sessions: Dict[str, str] = {}
        self._session_modes: Dict[str, SessionMode] = {}
        # Per-session isolated FactStores for roleplay/simulation/dream
        self._session_fact_stores: Dict[str, FactStore] = {}
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
                self._load_fact_store(spec.id)
                return spec
        return None

    def register(self, identity: IdentitySpec) -> None:
        """Register a new identity with the runtime and persist."""
        self.identity_store.save(identity)
        self.timeline_registry.create(identity.id)
        self._fact_stores[identity.id] = FactStore()
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

    def _persist_identity(self, identity: IdentitySpec) -> None:
        if not self._storage:
            return
        try:
            snapshot_data = identity.to_dict()
            self._storage.save(identity.id, "identity_spec", snapshot_data)
            self._storage.save(
                identity.id,
                "latest_snapshot",
                {"modules": {"identity": snapshot_data}},
            )
        except Exception:
            pass

    def _migrate_legacy_fields_to_fact_store(
        self, identity: IdentitySpec, fact_store: FactStore,
    ) -> int:
        """
        One-time migration: copy any data from legacy IdentitySpec fields
        (preferences, beliefs, mutation_history, etc.) into the FactStore.

        This ensures old identities loaded from disk aren't silently orphaned.
        Returns the number of facts migrated.
        """
        migrated = 0
        # Legacy snapshot may have had a 'preferences' dict embedded in the
        # identity spec data. We check via storage directly.
        if not self._storage:
            return 0
        try:
            raw = self._storage.load(identity.id, "identity_spec")
            if not raw:
                raw = self._storage.load_latest(identity.id)
            if not raw:
                return 0
            if isinstance(raw, dict) and "modules" in raw:
                raw = raw["modules"].get("identity", raw)
            from core.identity_facts import FactSource

            legacy_prefs = raw.get("preferences", {}) if isinstance(raw, dict) else {}
            for key, value in legacy_prefs.items():
                field = f"preferences.{key}"
                if not fact_store.find(field):
                    fact_store.merge_or_reinforce(
                        field=field, value=value, confidence=0.7,
                        reasons=["Migrated from legacy identity spec"],
                        source=FactSource.IMPORTED,
                    )
                    migrated += 1

            legacy_beliefs = raw.get("beliefs", {}) if isinstance(raw, dict) else {}
            for key, value in legacy_beliefs.items():
                field = f"beliefs.{key}"
                if not fact_store.find(field):
                    fact_store.merge_or_reinforce(
                        field=field, value=value, confidence=0.7,
                        reasons=["Migrated from legacy identity spec"],
                        source=FactSource.IMPORTED,
                    )
                    migrated += 1

            legacy_traits = raw.get("traits", []) if isinstance(raw, dict) else []
            for t_data in legacy_traits:
                name = t_data.get("name", "unknown")
                score = t_data.get("score", 0.5)
                desc = t_data.get("description", "")
                field = f"traits.{name}"
                if not fact_store.find(field):
                    fact_store.merge_or_reinforce(
                        field=field, value={"score": score, "description": desc},
                        confidence=0.7, reasons=["Migrated from legacy traits"],
                        source=FactSource.IMPORTED,
                    )
                    migrated += 1
        except Exception:
            pass
        return migrated

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

    def _load_fact_store(self, identity_id: str) -> None:
        """Load the FactStore for an identity from storage.
        Also runs one-time migration from legacy IdentitySpec fields.
        """
        if not self._storage:
            self._fact_stores[identity_id] = FactStore()
            return
        try:
            data = self._storage.load(identity_id, "fact_store")
            if data and "facts" in data:
                self._fact_stores[identity_id] = FactStore.from_dict_full(data)
            else:
                self._fact_stores[identity_id] = FactStore()
        except Exception:
            self._fact_stores[identity_id] = FactStore()

        # One-time migration from legacy fields
        identity = self.identity_store.get(identity_id)
        store = self._fact_stores.get(identity_id)
        if identity and store and len(store) == 0:
            migrated = self._migrate_legacy_fields_to_fact_store(identity, store)
            if migrated > 0:
                self._save_fact_store(identity_id)

    def _save_fact_store(self, identity_id: str) -> None:
        """Persist the FactStore for an identity."""
        if not self._storage:
            return
        store = self._fact_stores.get(identity_id)
        if store is None:
            return
        try:
            self._storage.save(identity_id, "fact_store", store.to_dict_full())
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Public Query API
    # ------------------------------------------------------------------

    def inspect_identity(self, identity_id: str) -> Dict[str, Any]:
        """
        Return a comprehensive inspection of the identity's current state.

        This is the primary introspection endpoint. It returns everything:
        - Identity constitution (generated)
        - Canonical facts from FactStore
        - Stability and age metrics
        - Evidence graph summary
        - Fact revisions
        - Recent reinforcements
        - Pending/rejected mutations
        - Contradiction log
        - Timeline events
        - Goals
        - Relationships
        - Communication style
        - User knowledge
        - Runtime statistics
        """
        identity = self.identity_store.get(identity_id)
        if identity is None:
            return {"error": f"Identity '{identity_id}' not found"}

        fact_store = self._fact_stores.get(identity_id)
        tl = self.timeline_registry.get(identity_id)
        age_delta = (datetime.now(timezone.utc).replace(tzinfo=None)
                     - identity.created_at.replace(tzinfo=None)) if identity.created_at else None
        age_days = age_delta.days if age_delta else 0

        # Build constitution
        constitution = ""
        try:
            from core.constitution import build_constitution
            constitution = build_constitution(
                identity=identity,
                fact_store=fact_store,
                timeline=tl,
            )
        except Exception:
            constitution = "(constitution generation failed)"

        # Fact stats
        all_facts = fact_store.all() if fact_store else []
        active_facts = [f for f in all_facts if f.status.value == "active"] if fact_store else []

        # Evidence summary
        evidence_summary = {}
        try:
            from core.evidence_graph import EvidenceGraph
            evidence_graph = getattr(self, '_evidence_graphs', {}).get(identity_id)
            if evidence_graph:
                all_evidence = list(evidence_graph._nodes.values())
                evidence_summary = {
                    "total_evidence_nodes": len(all_evidence),
                    "by_type": {
                        t: len([e for e in all_evidence if e.type.value == t])
                        for t in set(e.type.value for e in all_evidence)
                    } if all_evidence else {},
                }
        except Exception:
            pass

        # Contradiction log
        contradictions = []
        try:
            contradictions = self.mutation_engine._contradiction_engine.conflict_log()
        except Exception:
            pass

        # Pending and rejected mutations
        pending = []
        rejected = []
        for p in self.mutation_engine.proposal_history():
            if p.status.value == "proposed":
                pending.append({
                    "field": p.field, "new_value": p.new_value,
                    "confidence": p.confidence, "reason": p.reason,
                })
            elif p.status.value == "rejected":
                rejected.append({
                    "field": p.field, "new_value": p.new_value,
                    "reason": p.rejection_reason,
                })

        # Timeline events
        timeline_events = []
        if tl:
            timeline_events = [
                {"type": e.event_type.value, "title": e.title,
                 "description": e.description, "timestamp": e.occurred_at.isoformat() if hasattr(e, 'occurred_at') and hasattr(e.occurred_at, 'isoformat') else str(getattr(e, 'occurred_at', ''))}
                for e in tl.events()
            ]

        # Goals
        goals_data = []
        try:
            for g in self.goal_engine.list_by_scope("persistent"):
                goals_data.append({
                    "id": g.id, "title": g.title, "status": g.status.value,
                    "priority": g.priority.value, "progress": g.progress,
                })
        except Exception:
            pass

        # Relationships
        relationships = []
        try:
            for edge in self.identity_graph.get_relationships(identity_id):
                relationships.append({
                    "target": edge.target_id, "trust": edge.trust_level.value,
                    "strength": edge.strength, "tags": edge.tags,
                })
        except Exception:
            pass

        # Runtime stats
        event_log_count = len(fact_store.replay()) if fact_store else 0
        runtime_stats = {
            "interaction_count": len(self.mutation_engine.proposal_history()),
            "mutation_history_count": event_log_count,
            "fact_count": len(all_facts),
            "active_fact_count": len(active_facts),
            "timeline_event_count": len(timeline_events),
            "goal_count": len(goals_data),
            "relationship_count": len(relationships),
            "memory_count": len(self.memory_store.by_identity(identity_id)) if identity_id else 0,
        }

        # Recent reinforcements
        recent_reinforcements = []
        if fact_store:
            for f in all_facts:
                if f.times_reinforced > 0:
                    recent_reinforcements.append({
                        "field": f.field, "value": f.value,
                        "times_reinforced": f.times_reinforced,
                        "confidence": f.confidence,
                        "last_confirmed": f.last_confirmed,
                    })
            recent_reinforcements.sort(key=lambda x: x["last_confirmed"], reverse=True)

        return {
            "identity": {
                "id": identity.id,
                "name": identity.name,
                "class": identity.identity_class.value,
                "version": identity.version,
                "age_days": age_days,
                "status": identity.status.value,
                "persona": identity.persona,
                "communication_style": identity.communication_style,
            },
            "constitution": constitution,
            "canonical_facts": {
                "total": len(all_facts),
                "active": len(active_facts),
                "by_domain": {
                    d.value: len([f for f in all_facts if f.domain.value == d.value])
                    for d in {f.domain for f in all_facts}
                } if all_facts else {},
                "facts": [
                    {
                        "fact_id": f.fact_id[:8],
                        "domain": f.domain.value,
                        "field": f.field,
                        "value": f.value,
                        "confidence": round(f.confidence, 2),
                        "status": f.status.value,
                        "times_reinforced": f.times_reinforced,
                        "reasons": f.reasons[:3],
                        "version_count": len(f.version_history),
                    }
                    for f in sorted(all_facts, key=lambda x: x.last_confirmed, reverse=True)[:50]
                ],
            },
            "fact_revisions": [
                {
                    "field": f.field,
                    "versions": [
                        {"value": v.value, "confidence": v.confidence,
                         "status": v.status.value, "first_seen": v.first_seen}
                        for v in fact_store.all_versions_for_field(f.field)
                    ] if fact_store else [],
                }
                for f in active_facts[:20]
            ],
            "recent_reinforcements": recent_reinforcements[:10],
            "pending_mutations": pending,
            "rejected_mutations": rejected,
            "contradictions": contradictions[-10:],
            "evidence": evidence_summary,
            "timeline": timeline_events[-20:],
            "goals": goals_data,
            "relationships": relationships,
            "runtime_stats": runtime_stats,
        }

    def get_fact(self, identity_id: str, field: str) -> Dict[str, Any]:
        """Query a specific fact with full provenance."""
        identity = self.identity_store.get(identity_id)
        if identity is None:
            return {"error": f"Identity '{identity_id}' not found"}
        return identity.explain_fact(
            field=field,
            fact_store=self._fact_stores.get(identity_id),
        )

    def identity_constitution(self, identity_id: str) -> str:
        """Generate the identity constitution dynamically from current state."""
        identity = self.identity_store.get(identity_id)
        if identity is None:
            return f"Identity '{identity_id}' not found"
        try:
            from core.constitution import build_constitution
            return build_constitution(
                identity=identity,
                fact_store=self._fact_stores.get(identity_id),
                timeline=self.timeline_registry.get(identity_id),
            )
        except Exception as e:
            return f"(constitution generation failed: {e})"

    def replay_events(self, identity_id: str) -> List[Dict[str, Any]]:
        """Replay all fact events for an identity."""
        fact_store = self._fact_stores.get(identity_id)
        if fact_store is None:
            return []
        return [e.to_dict() for e in fact_store.replay()]

    def _get_user_profile(self, session_id: str) -> UserProfile:
        """Get or create a UserProfile for the given session."""
        key = session_id or "default"
        if key not in self._user_profiles:
            self._user_profiles[key] = UserProfile(user_id=key)
            self._load_user_profile(key)
        return self._user_profiles[key]

    def _load_user_profile(self, user_id: str) -> None:
        """Load a persisted user profile from storage."""
        if not self._storage:
            return
        try:
            data = self._storage.load(f"user_{user_id}", "profile")
            if data:
                self._user_profiles[user_id] = UserProfile.from_dict(data)
        except Exception:
            pass

    def _save_user_profile(self, user_id: str) -> None:
        """Persist a user profile."""
        if not self._storage:
            return
        profile = self._user_profiles.get(user_id)
        if not profile:
            return
        try:
            self._storage.save(f"user_{user_id}", "profile", profile.to_dict())
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

        Only stores user SELF-disclosures — filter out:
        - Questions (user asking, not disclosing)
        - User corrections about the assistant's identity
        - Simple acknowledgments

        User facts about themselves go into UserProfile, not MemoryStore.
        """
        # ── Step 1: Extract user profile facts first (always) ──
        user_facts = extract_user_facts(user_input)
        if user_facts and session_id:
            profile = self._get_user_profile(session_id)
            for uf in user_facts:
                profile.add_or_update(
                    field=uf.field,
                    value=uf.value,
                    source=uf.source_conversation,
                    confidence=uf.confidence,
                )
            self._save_user_profile(session_id)

        # ── Step 2: Check if the input is worth remembering as semantic fact ──
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
        self, identity_id: str, session_id: Optional[str] = None,
        mode: Optional[SessionMode] = None,
        user_input: str = "",
    ) -> str:
        """Start a new session for an identity. Returns session_id.
        
        If the session already exists (same session_id), its mode is preserved.
        If no mode is given, it is detected from user_input.
        """
        sid = session_id or str(uuid.uuid4())
        existing = self._sessions.get(sid)
        self._sessions[sid] = identity_id

        if sid not in self._session_modes:
            detected = mode or (detect_session_mode(user_input) if user_input else SessionMode.NORMAL)
            self._session_modes[sid] = detected
            # If isolated session, fork the FactStore
            if detected != SessionMode.NORMAL:
                canonical = self._fact_stores.get(identity_id)
                if canonical:
                    self._session_fact_stores[sid] = canonical.fork()
                else:
                    self._session_fact_stores[sid] = FactStore()

        self._emit(
            EventType.SESSION_STARTED,
            identity_id=identity_id,
            session_id=sid,
            session_mode=self._session_modes.get(sid, SessionMode.NORMAL).value,
        )
        return sid

    def end_session(self, session_id: str) -> None:
        identity_id = self._sessions.pop(session_id, None)
        mode = self._session_modes.pop(session_id, None)
        if mode != SessionMode.NORMAL:
            # Persist roleplay context for this session
            self._save_session_fact_store(session_id)
        self._session_fact_stores.pop(session_id, None)
        if identity_id:
            self._emit(
                EventType.SESSION_ENDED,
                identity_id=identity_id,
                session_id=session_id,
            )

    def get_session_mode(self, session_id: str) -> SessionMode:
        """Get the detected mode for a session."""
        return self._session_modes.get(session_id, SessionMode.NORMAL)

    def _get_fact_store_for_session(
        self, identity_id: str, session_id: Optional[str] = None
    ) -> FactStore:
        """Return the appropriate FactStore for a session.
        
        NORMAL sessions → canonical identity FactStore.
        Isolated sessions (ROLEPLAY/SIMULATION/DREAM/HYPOTHETICAL) → per-session fork.
        """
        if session_id and self._session_modes.get(session_id, SessionMode.NORMAL) != SessionMode.NORMAL:
            # Ensure session fork exists
            if session_id not in self._session_fact_stores:
                canonical = self._fact_stores.get(identity_id)
                if canonical:
                    self._session_fact_stores[session_id] = canonical.fork()
                else:
                    self._session_fact_stores[session_id] = FactStore()
            return self._session_fact_stores[session_id]
        return self._fact_stores.get(identity_id, FactStore())

    def _save_session_fact_store(self, session_id: str) -> None:
        """Persist isolated FactStore for a session."""
        if not self._storage:
            return
        fs = self._session_fact_stores.get(session_id)
        if fs:
            try:
                self._storage.save(f"session_{session_id}", "fact_store", fs.to_dict_full())
            except Exception:
                pass

    def _load_session_fact_store(self, session_id: str) -> Optional[FactStore]:
        """Load an isolated FactStore for a session."""
        if not self._storage:
            return None
        try:
            data = self._storage.load(f"session_{session_id}", "fact_store")
            if data and "facts" in data:
                return FactStore.from_dict_full(data)
        except Exception:
            pass
        return None

    # ------------------------------------------------------------------
    # Core Interaction Pipeline
    # ------------------------------------------------------------------

    def process(
        self,
        request: InteractionRequest,
        top_k_memories: int = 10,
    ) -> InteractionResponse:
        """
        Full pipeline for processing one interaction.

        Pipeline stages:
        1. Resolve identity
        1b. Detect session mode & identity rename attempts
        2. Policy check on input
        3. Compose context (with emotion, session mode, session-scoped facts)
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

        # Stage 1b: Detect session mode & enforce identity integrity
        session_id = request.session_id or "default"
        if session_id not in self._session_modes:
            mode = detect_session_mode(request.user_input)
            self._session_modes[session_id] = mode
            if mode != SessionMode.NORMAL:
                canonical = self._fact_stores.get(identity.id)
                if canonical:
                    self._session_fact_stores[session_id] = canonical.fork()
                else:
                    self._session_fact_stores[session_id] = FactStore()
        session_mode = self._session_modes.get(session_id, SessionMode.NORMAL)

        # Identity integrity gate: block rename attempts pre-LLM
        rename_attempt = detect_identity_rename_attempt(request.user_input)
        if rename_attempt and identity.is_field_locked("name"):
            return InteractionResponse(
                request_id=request.id,
                identity_id=identity.id,
                output=f"My name is {identity.name}. I cannot be renamed.",
                policy_passed=True,
            )

        # Emotion extraction (separate from identity evolution)
        emotion_state = extract_emotion(request.user_input)

        # Stage 2: Input policy gate
        input_policy = self.policy_engine.evaluate(
            request.user_input, scope=PolicyScope.INPUT
        )
        self._emit(
            EventType.POLICY_TRIGGERED,
            identity_id=identity.id,
            session_id=session_id,
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
        user_profile = self._user_profiles.get(session_id)
        session_fact_store = self._get_fact_store_for_session(identity.id, session_id)
        context = self.context_composer.compose(
            identity=identity,
            memory_store=self.memory_store,
            skill_registry=self.skill_registry,
            goal_engine=self.goal_engine,
            identity_graph=self.identity_graph,
            motivation_engine=self.motivation_engine,
            timeline_registry=self.timeline_registry,
            fact_store=session_fact_store,
            user_profile=user_profile,
            query=sanitized_input,
            top_k_memories=top_k_memories,
            session_mode=session_mode,
            emotion_state=emotion_state,
        )

        self._emit(
            EventType.CONTEXT_COMPOSED,
            identity_id=identity.id,
            session_id=session_id,
            token_estimate=context.token_estimate(),
            session_mode=session_mode.value,
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

        # Stage 7c: Identity Mutation — detect identity evolution opportunities
        # Route mutations to the correct FactStore based on session mode
        if session_mode == SessionMode.NORMAL:
            fact_store = self._fact_stores.get(identity.id)
        else:
            fact_store = self._session_fact_stores.get(session_id)
        if fact_store is not None:
            self.mutation_engine.fact_store = fact_store

        mutation_proposals = self.mutation_engine.analyze(
            user_input=sanitized_input,
            assistant_response=final_output,
            identity_spec=identity,
        )

        if mutation_proposals:
            validated = self.mutation_engine.validate(
                mutation_proposals,
                existing_records=None,
            )

            self.mutation_engine.apply_proposals_to_fact_store(validated)

            for proposal in validated:
                if proposal.status in (MutationStatus.ACCEPTED, MutationStatus.CONFLICT):
                    self._emit(
                        EventType.IDENTITY_MUTATION_ACCEPTED
                        if proposal.status == MutationStatus.ACCEPTED
                        else EventType.IDENTITY_MUTATION_CONFLICT,
                        identity_id=identity.id,
                        session_id=session_id,
                        field=proposal.field,
                        old_value=proposal.old_value,
                        new_value=proposal.new_value,
                        confidence=proposal.confidence,
                        reason=proposal.reason,
                    )
                else:
                    self._emit(
                        EventType.IDENTITY_MUTATION_REJECTED,
                        identity_id=identity.id,
                        session_id=session_id,
                        field=proposal.field,
                        reason=proposal.rejection_reason,
                    )

            # Bump identity version if any mutations were accepted
            accepted_count = sum(1 for p in validated if p.status == MutationStatus.ACCEPTED)
            if accepted_count > 0 and session_mode == SessionMode.NORMAL:
                fields_changed = [p.field for p in validated if p.status == MutationStatus.ACCEPTED]
                identity.bump_version(
                    level="patch",
                    changelog=f"Mutated: {', '.join(fields_changed[:3])}",
                )

            # Persist the appropriate fact store
            if session_mode == SessionMode.NORMAL:
                self._save_fact_store(identity.id)
                self._persist_identity(identity)
            else:
                self._save_session_fact_store(session_id)

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

        # Stage 8: Record timeline life events
        # Record the interaction event
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

        # Record mutation timeline events for accepted proposals
        for proposal in mutation_proposals if mutation_proposals else []:
            if proposal.status != MutationStatus.ACCEPTED:
                continue
            mutation_type_map = {
                MutationType.PREFERENCE_ADOPTED: LifeEventType.PREFERENCE_LEARNED,
                MutationType.PREFERENCE_CHANGED: LifeEventType.PREFERENCE_LEARNED,
                MutationType.BELIEF_ADOPTED: LifeEventType.BELIEF_ADOPTED,
                MutationType.BELIEF_CHANGED: LifeEventType.BELIEF_ADOPTED,
                MutationType.TRAIT_EVOLVED: LifeEventType.TRAIT_CHANGED,
                MutationType.TRUST_EVOLVED: LifeEventType.TRUST_CHANGED,
                MutationType.COMMUNICATION_EVOLVED: LifeEventType.COMMUNICATION_CHANGED,
            }
            tl_event_type = mutation_type_map.get(
                proposal.mutation_type, LifeEventType.PREFERENCE_LEARNED
            )
            field_short = proposal.field.split(".")[-1].replace("_", " ")
            self.timeline_registry.record_event(
                identity.id,
                LifeEvent(
                    identity_id=identity.id,
                    event_type=tl_event_type,
                    title=f"{tl_event_type.value.replace('_', ' ').title()}: {field_short}",
                    description=proposal.reason,
                    significance=3,
                    metadata={
                        "mutation_id": proposal.mutation_id,
                        "field": proposal.field,
                        "old_value": proposal.old_value,
                        "new_value": proposal.new_value,
                        "confidence": proposal.confidence,
                    },
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
