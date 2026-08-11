from __future__ import annotations

import logging
import os
import queue
import re
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from core.cognitive_engine import ComposedContext, ContextComposer
from core.migrations import (
    MigrationManager,
    MigrationRegistry,
    CURRENT_SCHEMA_VERSION,
    register_core_migrations,
)
from core.evaluation import (
    EvaluationEngine,
    classify_memory_type,
    is_worth_remembering,
)
from core.goals import GoalEngine
from core.intentions import IntentionEngine
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
from core.capabilities import CapabilityRegistry as PluginRegistry
from core.prometheus import PrometheusEngine
from core.skills import SkillRegistry
from core.timeline import LifeEvent, LifeEventType, TimelineRegistry
from core.user_profile import UserProfile, extract_user_facts
from runtime.event_bus import EventBus, EventType

_log = logging.getLogger(__name__)

# Opt-in stage timing: IDENTITYOS_LATENCY=1|true|yes
_LATENCY_ENV = os.environ.get("IDENTITYOS_LATENCY", "").strip().lower()
_LATENCY_ENABLED = _LATENCY_ENV in ("1", "true", "yes", "debug")


@dataclass
class _StageTimer:
    """Lightweight per-process() stage timing (disabled unless IDENTITYOS_LATENCY is set)."""

    stages_ms: Dict[str, float] = field(default_factory=dict)
    _starts: Dict[str, float] = field(default_factory=dict)

    def start(self, name: str) -> None:
        if _LATENCY_ENABLED:
            self._starts[name] = time.monotonic()

    def end(self, name: str) -> None:
        if not _LATENCY_ENABLED:
            return
        t0 = self._starts.pop(name, None)
        if t0 is not None:
            self.stages_ms[name] = round((time.monotonic() - t0) * 1000.0, 3)

    def attach(self, metadata: Dict[str, Any]) -> None:
        if _LATENCY_ENABLED and self.stages_ms:
            metadata["latency_ms"] = dict(self.stages_ms)
            _log.debug("IdentityRuntime.process latency_ms=%s", self.stages_ms)


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
        self.intention_engine = IntentionEngine()
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

        # Migration framework — upgrades persisted data on load
        self._migration_registry = MigrationRegistry()
        register_core_migrations(self._migration_registry)
        self._migration_manager = MigrationManager(
            self._migration_registry, storage=self._storage,
        )

        # Pluggable Capability System — installed per identity
        self.capability_registry = PluginRegistry(storage=self._storage)

        # Event Bus — wired into the pipeline but subscribers are opt-in
        self.event_bus = EventBus()

        # Prometheus — autonomous capability evolution system
        self.prometheus = PrometheusEngine(
            capability_registry=self.capability_registry,
            storage=self._storage,
        )

        # Executive Runtime — persistent task engine for committed goals
        self.executive = None
        if self._storage is not None:
            try:
                from core.executive import ExecutiveRuntime
                from core.executive.engine import register_executive
                self.executive = ExecutiveRuntime(
                    storage=self._storage,
                    capability_registry=self.capability_registry,
                )
                register_executive(self.executive)
            except Exception:
                self.executive = None

        # Deferred post-response work (eval/memory/mutation/persist).
        # Single worker keeps ordering; flush_post_process() waits for drain.
        self._post_process_queue: queue.Queue = queue.Queue()
        self._post_process_worker = threading.Thread(
            target=self._post_process_loop,
            name="identity-post-process",
            daemon=True,
        )
        self._post_process_worker.start()

    # ------------------------------------------------------------------
    # Deferred post-processing
    # ------------------------------------------------------------------

    def _post_process_loop(self) -> None:
        while True:
            job = self._post_process_queue.get()
            try:
                if job is None:
                    return
                job()
            finally:
                self._post_process_queue.task_done()

    def _schedule_post_process(self, fn: Callable[[], None]) -> None:
        """Queue post-response work so process() can return the reply first."""
        self._post_process_queue.put(fn)

    def flush_post_process(self, timeout: Optional[float] = 30.0) -> None:
        """Block until all queued post-process jobs finish.

        Called at the start of process() so the next turn sees prior
        mutations/memories, and by tests that assert on persisted state.
        """
        if timeout is None:
            self._post_process_queue.join()
            return
        deadline = time.monotonic() + timeout
        while self._post_process_queue.unfinished_tasks:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("flush_post_process timed out")
            time.sleep(min(0.01, remaining))

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
                identity_data = self._migration_manager.migrate_blob_in_place(
                    identity_data, identity_id=identity_id, namespace="identity_spec",
                )
                spec = IdentitySpec.from_dict(identity_data)
                self.identity_store.save(spec)
                self.timeline_registry.create(spec.id)
                self._load_timeline(spec.id)
                self._load_relationships(spec.id)
                self._load_goals(spec.id)
                self._load_fact_store(spec.id)
                self._load_persisted_memories(spec.id)
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
            # Only write latest_snapshot if it doesn't exist yet (first-time setup).
            # SnapshotManager.capture() owns this namespace after initial creation.
            if not self._storage.load(identity.id, "latest_snapshot"):
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

    def _ensure_executive_capability(self, identity_id: str) -> None:
        """Ensure the identity has the core executive capability installed."""
        if hasattr(self, "capability_registry") and self.capability_registry:
            if not self.capability_registry.get(identity_id, "executive"):
                try:
                    self.capability_registry.install(identity_id, "executive")
                except Exception:
                    pass

    def _build_tool_executor(self, identity: Any) -> tuple[Any, dict]:
        """Build the native tool-call surface (Step 4).

        Returns ``(executor, generate_kwargs)``.  Only installed skills are
        exposed as tools, and every tool result is produced by the runtime —
        the model requests actions, it never declares them successful.
        """
        try:
            from core.executive import ActionExecutor
            executor = ActionExecutor(self.capability_registry, identity.id)
            def execute_tool(name: str, args: dict) -> str:
                ar = executor.execute(name, **args) if isinstance(args, dict) else executor.execute(name)
                try:
                    block = ar.to_context_block()
                except Exception:
                    block = f"Status: {getattr(ar, 'status', 'unknown')}. Error: {getattr(ar, 'error', '')}"
                return block
            return (executor, {"tools": executor.tool_defs(), "execute_tool": execute_tool})
        except Exception:
            return (None, {})

    def load_persisted(self) -> int:
        """Load all identities from the persistence backend into the in-memory store.

        Also loads persisted memories for each identity.
        Runs any pending schema migrations on persisted data.

        Returns the number of identities loaded.
        """
        if not self._storage:
            return 0
        self._migration_manager.migrate_all()
        ids = self._storage.list_identities()
        count = 0
        for identity_id in ids:
            if self.load(identity_id):
                count += 1
        return count

    def _load_persisted_memories(self, identity_id: str) -> int:
        """Load persisted memories for an identity into the in-memory store.
        Skips duplicates (by fragment ID) to prevent memory duplication on reload.
        """
        if not self._storage:
            return 0
        mem_dicts = self._storage.load_memories(identity_id)
        count = 0
        for d in mem_dicts:
            try:
                frag = MemoryFragment.from_dict(d)
                if self.memory_store.get(frag.id):
                    continue
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
            self._storage.save(identity_id, "goals", self.goal_engine.to_dict())
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
            from core.goals import GoalEngine
            loaded = GoalEngine.from_dict(data)
            for g in loaded.all():
                self.goal_engine.add(g)
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

    def _get_user_profile(self, identity_id: str) -> UserProfile:
        """Get or create a UserProfile for the given identity.

        User profiles are shared across all sessions for the same identity,
        so facts learned in one app are available in another.
        """
        key = identity_id
        if key not in self._user_profiles:
            self._user_profiles[key] = UserProfile(user_id=key)
            self._load_user_profile(key)
        return self._user_profiles[key]

    def _load_user_profile(self, identity_id: str) -> None:
        """Load a persisted user profile from storage."""
        if not self._storage:
            return
        try:
            data = self._storage.load(identity_id, "_user_profile")
            if data:
                self._user_profiles[identity_id] = UserProfile.from_dict(data)
        except Exception:
            pass

    def _save_user_profile(self, identity_id: str) -> None:
        """Persist a user profile keyed by identity."""
        if not self._storage:
            return
        profile = self._user_profiles.get(identity_id)
        if not profile:
            return
        try:
            self._storage.save(identity_id, "_user_profile", profile.to_dict())
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
        if user_facts:
            profile = self._get_user_profile(identity_id)
            for uf in user_facts:
                profile.add_or_update(
                    field=uf.field,
                    value=uf.value,
                    source=uf.source_conversation,
                    confidence=uf.confidence,
                )
            self._save_user_profile(identity_id)

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
        top_k_memories: int = 3,
    ) -> InteractionResponse:
        """
        Full pipeline for processing one interaction.

        Pipeline stages:
        1. Resolve identity
        1b. Detect session mode & identity rename attempts
        2. Policy check on input
        2b. Executive recover/commit (execution runs on the scheduler)
        2c. Prometheus pre-check (only evolves when a real gap is detected)
        3. Compose context (+ capability evidence when required)
        4. Invoke adapter (LLM call)
        4b. Prometheus post-check (only when response indicates a gap)
        5. Policy check on output
        6+. Evaluate / memory / mutation / timeline / relationships — deferred

        Events are emitted at each stage for subscribers on the EventBus.
        """
        timer = _StageTimer()
        # Ensure prior turn's deferred persistence is visible to this turn.
        self.flush_post_process()

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
        timer.start("policy")
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
            timer.end("policy")
            return InteractionResponse(
                request_id=request.id,
                identity_id=request.identity_id,
                output="[Blocked] Input did not pass policy check.",
                policy_passed=False,
            )

        sanitized_input = input_policy.transformed_data or request.user_input
        timer.end("policy")

        # Stage 2b: Executive recovery + optional task commit.
        # Long-running execution is owned by the Executive scheduler — ordinary
        # chat must NOT block on a synchronous multi-tick execution loop.
        timer.start("executive")
        _executive_state_block = ""
        if self.executive is not None:
            self._ensure_executive_capability(identity.id)
            try:
                recovered = self.executive.recover(identity.id)
                self.executive._ctx(identity.id, runtime=self)
                if (recovered or self.executive.active_tasks(identity.id)) and self.executive.scheduler:
                    self.executive.scheduler.start()
                _executive_state_block = self.executive.render_state(identity.id)
            except Exception:
                _executive_state_block = ""

            # Automatic Need Detection -> Task Creation.
            # Capability-acquisition goals are committed before the LLM replies
            # so the answer reflects real task state. Execution continues on
            # the background scheduler (no synchronous tick loop here).
            try:
                from core.executive.workflow import extract_capability_name, is_acquisition_goal
                _acq_cap = extract_capability_name(sanitized_input)
                if _acq_cap and is_acquisition_goal(sanitized_input):
                    _existing = self.executive.active_tasks(identity.id)
                    _recent_terminal = []
                    try:
                        for _h in self.executive.history(identity.id):
                            _ht = self.executive.get_task(identity.id, _h.get("task_id", ""))
                            if _ht is not None:
                                _recent_terminal.append(_ht)
                    except Exception:
                        _recent_terminal = []
                    _all_tasks = list(_existing) + _recent_terminal
                    _dupe = any(
                        t is not None and (
                            getattr(t, "capability_id", "") == _acq_cap
                            or _acq_cap in (getattr(t, "goal", "") or "")
                        )
                        for t in _all_tasks
                    )
                    if not _dupe:
                        self.executive.create_acquisition_task(
                            identity_id=identity.id,
                            capability_id=_acq_cap,
                            goal=sanitized_input,
                            original_request=sanitized_input,
                        )
                        if self.executive.scheduler:
                            self.executive.scheduler.start()
                    _executive_state_block = self.executive.render_state(identity.id)
            except Exception:
                pass
        timer.end("executive")

        # Stage 2c: Prometheus pre-check — only runs the evolution pipeline
        # when detect_need_from_input finds a real capability gap.
        timer.start("prometheus")
        _prometheus_evolved = False
        _pre_evolve_result = self.prometheus.pre_check_and_evolve(
            user_input=sanitized_input,
            identity_id=identity.id,
            runtime=self,
            session_id=request.session_id,
        )
        if _pre_evolve_result and _pre_evolve_result.acquired:
            _prometheus_evolved = True
        timer.end("prometheus")

        # Stage 3: Compose context
        timer.start("planner")
        user_profile = self._get_user_profile(identity.id)
        session_fact_store = self._get_fact_store_for_session(identity.id, session_id)
        cap_prompts = self.capability_registry.all_prompts(identity.id)

        # Route user intent through installed capabilities (the Planner layer)
        _router = __import__("core.planner", fromlist=["SkillRouter"]).SkillRouter
        _skill_router = _router(self.capability_registry, identity.id)
        _evidence = _skill_router.route(sanitized_input)
        _report = _evidence.report()
        _evidence_results = [r.to_evidence_dict() for r in _evidence._results] if hasattr(_evidence, '_results') else []
        _has_evidence = bool(_report.facts or _report.failures)
        _history = _evidence.call_history
        timer.end("planner")

        timer.start("context")
        context = self.context_composer.compose(
            identity=identity,
            memory_store=self.memory_store,
            skill_registry=self.skill_registry,
            goal_engine=self.goal_engine,
            intention_engine=self.intention_engine,
            identity_graph=self.identity_graph,
            motivation_engine=self.motivation_engine,
            timeline_registry=self.timeline_registry,
            fact_store=session_fact_store,
            user_profile=user_profile,
            query=sanitized_input,
            top_k_memories=top_k_memories,
            session_id=request.session_id,
            session_mode=session_mode,
            emotion_state=emotion_state,
            capability_prompts=cap_prompts if cap_prompts else None,
            evidence_results=_evidence_results if _evidence_results else None,
        )

        self._emit(
            EventType.CONTEXT_COMPOSED,
            identity_id=identity.id,
            session_id=session_id,
            token_estimate=context.token_estimate(),
            session_mode=session_mode.value,
        )

        if _has_evidence:
            context.custom_blocks["factual_skill_data"] = _skill_router.format_for_context(_evidence)
        if _executive_state_block:
            context.custom_blocks["executive_state"] = _executive_state_block
        timer.end("context")

        # Stage 4: Adapter call
        timer.start("llm")
        if self.adapter:
            self._emit(
                EventType.MODEL_REQUESTED,
                identity_id=identity.id,
                session_id=request.session_id,
                model=self.adapter.model,
            )
            _t0 = time.monotonic()
            _executor, _gen_kwargs = self._build_tool_executor(identity)
            raw_output = self.adapter.generate(
                context=context.render(),
                user_input=sanitized_input,
                identity=identity,
                **_gen_kwargs,
            )
            _latency = time.monotonic() - _t0
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
        timer.end("llm")

        # Stage 4b: Prometheus post-check — only evolves when the response
        # indicates a missing capability (engine short-circuits otherwise).
        if not _prometheus_evolved and self.adapter:
            timer.start("prometheus")
            _post_result = self.prometheus.post_check_and_evolve(
                response=raw_output,
                user_input=sanitized_input,
                identity_id=identity.id,
                runtime=self,
                session_id=request.session_id,
            )
            if _post_result and _post_result.acquired and _post_result.retry_response:
                raw_output = _post_result.retry_response
                _prometheus_evolved = True
            timer.end("prometheus")

        # Stage 4c: Runtime confidence enforcement — if evidence has
        # low confidence or failures, prepend a disclaimer to the output.
        # This is enforced at the runtime level, not left to LLM discretion.
        if _has_evidence:
            _metrics = _report.trust_metrics()
            _low_conf = _metrics["low_confidence_facts"]
            _fails = _metrics["failed"]
            _total = _metrics["total_capability_calls"]
            if _low_conf > 0 or _fails > 0:
                _disc_parts = [f"\n\u26a0 **Confidence Notice** \u2014 {_low_conf} low-confidence, {_fails} failed out of {_total} capability calls."]
                for _r in _evidence._results:
                    if not _r.success:
                        _disc_parts.append(
                            f"  \u2022 {_r.capability}.{_r.action} failed: "
                            f"{_r.error.get('message','')[:150] if _r.error else 'unknown'}"
                        )
                    elif _r.confidence < 0.8:
                        _disc_parts.append(
                            f"  \u2022 {_r.capability}.{_r.action} confidence={_r.confidence}"
                        )
                _disc_parts.append("")
                raw_output = "\n".join(_disc_parts) + raw_output

        # Stage 5: Output policy gate
        timer.start("output_policy")
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
        timer.end("output_policy")

        # Append evidence footer before returning (part of the user-visible reply)
        if _evidence_results and policy_passed:
            footer_lines = ["\n\n---\n📊 **Evidence Sources**"]
            for ev in _evidence_results[:12]:
                status = "✓" if ev["success"] else "✗"
                conf = ev["confidence"]
                label = "verified" if conf >= 0.8 else "sourced" if conf >= 0.5 else "inferred"
                err = f" — {ev['error']['message'][:200]}" if ev.get("error") else ""
                cap = ev.get("capability", "")
                act = ev.get("action", "")
                skill_label = act if act.startswith(f"{cap}.") else f"{cap}.{act}"
                footer_lines.append(
                    f"  {status} `{skill_label}` — {label} ({conf:.1f}) — {ev['duration_ms']:.0f}ms{err}"
                )
            footer_lines.append("---")
            final_output += "\n".join(footer_lines)

        response = InteractionResponse(
            request_id=request.id,
            identity_id=identity.id,
            output=final_output,
            context_used=context,
            policy_passed=policy_passed,
            eval_score=None,
        )
        timer.attach(response.metadata)

        # Stages 6–10: defer post-response work off the critical reply path.
        # Persistence still occurs; the next process() flushes first.
        _post_identity = identity
        _post_session_id = session_id
        _post_session_mode = session_mode
        _post_sanitized = sanitized_input
        _post_final = final_output
        _post_request_id = request.id
        _post_req_session = request.session_id
        _post_history = list(_history) if _history else []

        def _post_process() -> None:
            timer.start("post_processing")
            try:
                # Trust metrics from capability evidence
                if _post_history and self._storage is not None:
                    try:
                        _trust_raw = self._storage.load(_post_identity.id, "capability.trust") or {}
                        _existing = _trust_raw.get("calls", [])
                        _existing.extend(_post_history)
                        _trust_raw["calls"] = _existing[-100:]
                        self._storage.save(_post_identity.id, "capability.trust", _trust_raw)
                    except Exception:
                        pass  # Trust persistence is non-critical

                # Stage 6: Evaluate
                eval_report = self.evaluation_engine.evaluate(
                    identity_id=_post_identity.id,
                    interaction_id=_post_request_id,
                    input_data=_post_sanitized,
                    output_data=_post_final,
                )
                response.eval_score = eval_report.overall_score

                self._emit(
                    EventType.EVALUATION_COMPLETED,
                    identity_id=_post_identity.id,
                    session_id=_post_req_session,
                    overall_score=eval_report.overall_score,
                    passed=eval_report.passed,
                    criteria_count=len(eval_report.records),
                )

                # Stage 7: Store interaction in memory
                episodic = MemoryFragment(
                    identity_id=_post_identity.id,
                    content=f"User: {_post_sanitized}\nAssistant: {_post_final}",
                    memory_type=MemoryType.EPISODIC,
                    session_id=_post_req_session,
                    tags=["interaction"],
                )
                self.memory_store.add(episodic)
                self._persist_memory(episodic)

                self._emit(
                    EventType.EXPERIENCE_RECORDED,
                    identity_id=_post_identity.id,
                    session_id=_post_req_session,
                    memory_id=episodic.id,
                    memory_type=episodic.memory_type.value,
                    content=episodic.content[:200],
                )

                semantic_mem = self._extract_and_store_semantic_memory(
                    user_input=_post_sanitized,
                    output=_post_final,
                    identity_id=_post_identity.id,
                    session_id=_post_req_session,
                )

                # Stage 7c: Identity Mutation
                if _post_session_mode == SessionMode.NORMAL:
                    fact_store = self._fact_stores.get(_post_identity.id)
                else:
                    fact_store = self._session_fact_stores.get(_post_session_id)
                if fact_store is not None:
                    self.mutation_engine.fact_store = fact_store

                mutation_proposals = self.mutation_engine.analyze(
                    user_input=_post_sanitized,
                    assistant_response=_post_final,
                    identity_spec=_post_identity,
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
                                identity_id=_post_identity.id,
                                session_id=_post_session_id,
                                field=proposal.field,
                                old_value=proposal.old_value,
                                new_value=proposal.new_value,
                                confidence=proposal.confidence,
                                reason=proposal.reason,
                            )
                        else:
                            self._emit(
                                EventType.IDENTITY_MUTATION_REJECTED,
                                identity_id=_post_identity.id,
                                session_id=_post_session_id,
                                field=proposal.field,
                                reason=proposal.rejection_reason,
                            )

                    accepted_count = sum(1 for p in validated if p.status == MutationStatus.ACCEPTED)
                    if accepted_count > 0 and _post_session_mode == SessionMode.NORMAL:
                        fields_changed = [p.field for p in validated if p.status == MutationStatus.ACCEPTED]
                        _post_identity.bump_version(
                            level="patch",
                            changelog=f"Mutated: {', '.join(fields_changed[:3])}",
                        )

                    if _post_session_mode == SessionMode.NORMAL:
                        self._save_fact_store(_post_identity.id)
                        self._persist_identity(_post_identity)
                    else:
                        self._save_session_fact_store(_post_session_id)

                tl_title = "Interaction"
                tl_description = f"User said: {_post_sanitized[:100]}"
                tl_meta = {
                    "session_id": _post_req_session,
                    "eval_score": eval_report.overall_score,
                }
                if semantic_mem:
                    mem_tags = semantic_mem.tags
                    if "preference" in mem_tags:
                        tl_title = "Learned preference"
                        tl_description = _post_sanitized[:120]
                    elif "decision" in mem_tags:
                        tl_title = "Made decision"
                        tl_description = _post_sanitized[:120]
                    elif "correction" in mem_tags:
                        tl_title = "Received correction"
                        tl_description = _post_sanitized[:120]
                    elif "milestone" in mem_tags:
                        tl_title = "Milestone"
                        tl_description = _post_sanitized[:120]
                    tl_meta["memory_id"] = semantic_mem.id
                    tl_meta["memory_type"] = semantic_mem.memory_type.value

                self.timeline_registry.record_event(
                    _post_identity.id,
                    LifeEvent(
                        identity_id=_post_identity.id,
                        event_type=LifeEventType.MILESTONE,
                        title=tl_title,
                        description=tl_description,
                        significance=2,
                        metadata=tl_meta,
                    ),
                )

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
                        _post_identity.id,
                        LifeEvent(
                            identity_id=_post_identity.id,
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

                self._persist_timeline(_post_identity.id)
                self._emit(
                    EventType.LIFE_EVENT_RECORDED,
                    identity_id=_post_identity.id,
                    session_id=_post_req_session,
                    title=tl_title,
                    description=tl_description,
                )

                target = _post_req_session or "user"
                self.identity_graph.interact_or_connect(
                    source_id=_post_identity.id,
                    target_id=target,
                    edge_type=EdgeType.PEER,
                    bidirectional=False,
                )
                self._persist_relationships(_post_identity.id)
                self._persist_goals(_post_identity.id)
            finally:
                timer.end("post_processing")
                timer.attach(response.metadata)

        self._schedule_post_process(_post_process)
        return response

    def __repr__(self) -> str:
        return (
            f"IdentityRuntime("
            f"identities={len(self.identity_store)}, "
            f"adapter={type(self.adapter).__name__ if self.adapter else 'None'}"
            f")"
        )
