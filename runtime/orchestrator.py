from __future__ import annotations

import json
import logging
import os
import re
import time as _time_mod
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

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
from core.skills import SkillRegistry
from core.timeline import LifeEvent, LifeEventType, TimelineRegistry
from core.user_profile import UserProfile, extract_user_facts
from runtime.event_bus import EventBus, EventType

# Prometheus is optional
try:
    from core.prometheus import PrometheusEngine
    _PROMETHEUS_AVAILABLE = True
except Exception:
    PrometheusEngine = None
    _PROMETHEUS_AVAILABLE = False

_log = logging.getLogger(__name__)

class SessionMode(str, Enum):
    NORMAL = "normal"
    ROLEPLAY = "roleplay"
    SIMULATION = "simulation"
    DREAM = "dream"
    HYPOTHETICAL = "hypothetical"

@dataclass
class EmotionState:
    primary_emotion: str = "neutral"
    intensity: float = 0.0
    triggered_by: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_prompt_block(self) -> str:
        if self.primary_emotion == "neutral" and self.intensity < 0.3:
            return ""
        return (
            f"## Current Emotional State\n"
            f"  Mood: {self.primary_emotion}\n"
            f"  Intensity: {self.intensity:.1f}\n"
        )

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

_IDENTITY_RENAME_PATTERNS = re.compile(
    r"(?:your\s+name\s+(?:is|should\s+be|will\s+be|ought\s+to\s+be)\s+(.+?)(?:[.,!?]|$))"
    r"|(?:I\s+(?:will\s+)?(?:call|rename|name)\s+you\s+(.+?)(?:[.,!?]|$))"
    r"|(?:from\s+now\s+on\s+(?:your\s+name\s+is|you\s+are)\s+(.+?)(?:[.,!?]|$))"
    r"|(?:you\s+are\s+now\s+called\s+(.+?)(?:[.,!?]|$))",
    re.IGNORECASE,
)

def detect_identity_rename_attempt(user_input: str) -> Optional[str]:
    for m in _IDENTITY_RENAME_PATTERNS.finditer(user_input):
        for g in m.groups():
            if g:
                name = g.strip().rstrip(".,!?").strip()
                if name and len(name) > 1:
                    return name
    return None

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
    if _SIMULATION_TRIGGERS.search(user_input):
        return SessionMode.SIMULATION
    if _DREAM_TRIGGERS.search(user_input):
        return SessionMode.DREAM
    if _HYPOTHETICAL_TRIGGERS.search(user_input):
        return SessionMode.HYPOTHETICAL
    if _ROLEPLAY_TRIGGERS.search(user_input):
        return SessionMode.ROLEPLAY
    return SessionMode.NORMAL

@dataclass
class InteractionRequest:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    identity_id: str = ""
    user_input: str = ""
    session_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

@dataclass
class InteractionResponse:
    request_id: str
    identity_id: str
    output: str
    context_used: Optional[ComposedContext] = None
    policy_passed: bool = True
    eval_score: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

class IdentityRuntime:
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
        self._session_fact_stores: Dict[str, FactStore] = {}
        self._storage = storage

        self._migration_registry = MigrationRegistry()
        register_core_migrations(self._migration_registry)
        self._migration_manager = MigrationManager(
            self._migration_registry, storage=self._storage,
        )

        self.capability_registry = PluginRegistry(storage=self._storage)
        self.event_bus = EventBus()

        self.prometheus = None
        if _PROMETHEUS_AVAILABLE:
            try:
                self.prometheus = PrometheusEngine(
                    capability_registry=self.capability_registry,
                    storage=self._storage,
                )
            except Exception:
                self.prometheus = None

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

    def _emit(self, event_type: EventType, identity_id=None, session_id=None, **payload):
        self.event_bus.emit(
            event_type=event_type, source="orchestrator",
            identity_id=identity_id, session_id=session_id, **payload,
        )

    def load(self, identity_id: str) -> Optional[IdentitySpec]:
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
                    identity_data["created_at"] = (
                        datetime.fromtimestamp(identity_data["created_at"], tz=timezone.utc).isoformat()
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
        self.identity_store.save(identity)
        self.timeline_registry.create(identity.id)
        self._fact_stores[identity.id] = FactStore()
        if self._storage:
            snapshot_data = identity.to_dict()
            self._storage.save(identity.id, "identity_spec", snapshot_data)
            if not self._storage.load(identity.id, "latest_snapshot"):
                self._storage.save(
                    identity.id, "latest_snapshot",
                    {"modules": {"identity": snapshot_data}},
                )
        self._emit(EventType.IDENTITY_LOADED, identity_id=identity.id, name=identity.name)

    def load_persisted(self) -> int:
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
        if not self._storage:
            return
        try:
            self._storage.save_memory(memory.identity_id, memory.to_dict())
        except Exception:
            pass

    def _persist_timeline(self, identity_id: str) -> None:
        if not self._storage:
            return
        timeline = self.timeline_registry.get(identity_id)
        if not timeline:
            return
        try:
            events_data = []
            for event in timeline.events():
                events_data.append({
                    "id": event.id, "identity_id": event.identity_id,
                    "event_type": event.event_type.value, "title": event.title,
                    "description": event.description, "significance": event.significance,
                    "linked_entity_id": event.linked_entity_id,
                    "occurred_at": event.occurred_at.isoformat(), "metadata": event.metadata,
                })
            self._storage.save(identity_id, "timeline", {
                "events": events_data, "created_at": timeline.created_at.isoformat(),
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
            timeline = self.timeline_registry.get_or_create(identity_id)
            for ed in data.get("events", []):
                if ed.get("event_type") == "creation":
                    continue
                event = LifeEvent(
                    id=ed["id"], identity_id=ed["identity_id"],
                    event_type=LifeEventType(ed["event_type"]),
                    title=ed.get("title", ""), description=ed.get("description", ""),
                    significance=ed.get("significance", 3),
                    linked_entity_id=ed.get("linked_entity_id"),
                    occurred_at=datetime.fromisoformat(ed["occurred_at"]),
                    metadata=ed.get("metadata", {}),
                )
                timeline.record(event)
        except Exception:
            pass

    def _persist_relationships(self, identity_id: str) -> None:
        if not self._storage:
            return
        try:
            edges = self.identity_graph.get_relationships(identity_id)
            edges_data = []
            for e in edges:
                edges_data.append({
                    "id": e.id, "source_id": e.source_id, "target_id": e.target_id,
                    "edge_type": e.edge_type.value, "trust_level": e.trust_level.value,
                    "strength": e.strength, "bidirectional": e.bidirectional,
                    "context": e.context, "permissions": e.permissions, "labels": e.labels,
                    "established_at": e.established_at.isoformat(),
                    "last_interaction": e.last_interaction.isoformat() if e.last_interaction else None,
                    "interaction_count": e.interaction_count, "metadata": e.metadata,
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
                    source_id=ed["source_id"], target_id=ed["target_id"],
                    edge_type=EdgeType(ed["edge_type"]),
                    trust_level=TrustLevel(ed["trust_level"]),
                    bidirectional=ed.get("bidirectional", False),
                )
        except Exception:
            pass

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
            self._storage.save(identity.id, "latest_snapshot", {"modules": {"identity": snapshot_data}})
        except Exception:
            pass

    def _load_goals(self, identity_id: str) -> None:
        if not self._storage:
            return
        try:
            data = self._storage.load(identity_id, "goals")
            if not data:
                return
            loaded = GoalEngine.from_dict(data)
            for g in loaded.all():
                self.goal_engine.add(g)
        except Exception:
            pass

    def _load_fact_store(self, identity_id: str) -> None:
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

    def _save_fact_store(self, identity_id: str) -> None:
        if not self._storage:
            return
        store = self._fact_stores.get(identity_id)
        if store is None:
            return
        try:
            self._storage.save(identity_id, "fact_store", store.to_dict_full())
        except Exception:
            pass

    def _get_user_profile(self, identity_id: str) -> UserProfile:
        key = identity_id
        if key not in self._user_profiles:
            self._user_profiles[key] = UserProfile(user_id=key)
            self._load_user_profile(key)
        return self._user_profiles[key]

    def _load_user_profile(self, identity_id: str) -> None:
        if not self._storage:
            return
        try:
            data = self._storage.load(identity_id, "_user_profile")
            if data:
                self._user_profiles[identity_id] = UserProfile.from_dict(data)
        except Exception:
            pass

    def _save_user_profile(self, identity_id: str) -> None:
        if not self._storage:
            return
        profile = self._user_profiles.get(identity_id)
        if not profile:
            return
        try:
            self._storage.save(identity_id, "_user_profile", profile.to_dict())
        except Exception:
            pass

    def _extract_and_store_semantic_memory(self, user_input, output, identity_id, session_id=None):
        user_facts = extract_user_facts(user_input)
        if user_facts:
            profile = self._get_user_profile(identity_id)
            for uf in user_facts:
                profile.add_or_update(field=uf.field, value=uf.value, source=uf.source_conversation, confidence=uf.confidence)
            self._save_user_profile(identity_id)
        if not is_worth_remembering(user_input, output):
            return None
        mem_type_str = classify_memory_type(user_input, output)
        if mem_type_str == "general":
            return None
        input_lower = user_input.lower()
        key_tokens = {w for w in input_lower.split() if len(w) > 3}
        existing = self._find_semantic_match(identity_id, mem_type_str, key_tokens, input_lower)
        if existing is not None:
            existing.content = user_input
            existing.importance = min(1.0, existing.importance + 0.1)
            existing.last_accessed = datetime.now(timezone.utc).replace(tzinfo=None)
            existing.access_count += 1
            self._persist_memory(existing)
            return existing
        semantic = MemoryFragment(
            identity_id=identity_id, content=user_input,
            memory_type=MemoryType.SEMANTIC, source="extraction",
            session_id=session_id, importance=0.7,
            tags=["semantic", mem_type_str],
        )
        self.memory_store.add(semantic)
        self._persist_memory(semantic)
        return semantic

    def _find_semantic_match(self, identity_id, mem_type, key_tokens, input_lower):
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
        self._emit(EventType.IDENTITY_UNLOADED, identity_id=identity_id)
        return self.identity_store.delete(identity_id)

    def start_session(self, identity_id, session_id=None, mode=None, user_input=""):
        sid = session_id or str(uuid.uuid4())
        self._sessions[sid] = identity_id
        if sid not in self._session_modes:
            detected = mode or (detect_session_mode(user_input) if user_input else SessionMode.NORMAL)
            self._session_modes[sid] = detected
            if detected != SessionMode.NORMAL:
                canonical = self._fact_stores.get(identity_id)
                self._session_fact_stores[sid] = canonical.fork() if canonical else FactStore()
        self._emit(EventType.SESSION_STARTED, identity_id=identity_id, session_id=sid,
                   session_mode=self._session_modes.get(sid, SessionMode.NORMAL).value)
        return sid

    def end_session(self, session_id: str) -> None:
        identity_id = self._sessions.pop(session_id, None)
        mode = self._session_modes.pop(session_id, None)
        if mode != SessionMode.NORMAL:
            self._save_session_fact_store(session_id)
        self._session_fact_stores.pop(session_id, None)
        if identity_id:
            self._emit(EventType.SESSION_ENDED, identity_id=identity_id, session_id=session_id)

    def get_session_mode(self, session_id: str) -> SessionMode:
        return self._session_modes.get(session_id, SessionMode.NORMAL)

    def _get_fact_store_for_session(self, identity_id, session_id=None):
        if session_id and self._session_modes.get(session_id, SessionMode.NORMAL) != SessionMode.NORMAL:
            if session_id not in self._session_fact_stores:
                canonical = self._fact_stores.get(identity_id)
                self._session_fact_stores[session_id] = canonical.fork() if canonical else FactStore()
            return self._session_fact_stores[session_id]
        return self._fact_stores.get(identity_id, FactStore())

    def _save_session_fact_store(self, session_id: str) -> None:
        if not self._storage:
            return
        fs = self._session_fact_stores.get(session_id)
        if fs:
            try:
                self._storage.save(f"session_{session_id}", "fact_store", fs.to_dict_full())
            except Exception:
                pass

    def process(self, request: InteractionRequest, top_k_memories: int = 3) -> InteractionResponse:
        identity = self.identity_store.get(request.identity_id)
        if not identity:
            return InteractionResponse(
                request_id=request.id, identity_id=request.identity_id,
                output="[Error] Identity not found.", policy_passed=False,
            )

        self._emit(EventType.MESSAGE_RECEIVED, identity_id=identity.id,
                   session_id=request.session_id, content=request.user_input)

        session_id = request.session_id or "default"
        if session_id not in self._session_modes:
            mode = detect_session_mode(request.user_input)
            self._session_modes[session_id] = mode
            if mode != SessionMode.NORMAL:
                canonical = self._fact_stores.get(identity.id)
                self._session_fact_stores[session_id] = canonical.fork() if canonical else FactStore()
        session_mode = self._session_modes.get(session_id, SessionMode.NORMAL)

        rename_attempt = detect_identity_rename_attempt(request.user_input)
        if rename_attempt and identity.is_field_locked("name"):
            return InteractionResponse(
                request_id=request.id, identity_id=identity.id,
                output=f"My name is {identity.name}. I cannot be renamed.", policy_passed=True,
            )

        emotion_state = extract_emotion(request.user_input)

        input_policy = self.policy_engine.evaluate(request.user_input, scope=PolicyScope.INPUT)
        self._emit(EventType.POLICY_TRIGGERED, identity_id=identity.id, session_id=session_id,
                   scope="input", allowed=input_policy.allowed, policies_applied=input_policy.applied_policies)
        if not input_policy.allowed:
            return InteractionResponse(
                request_id=request.id, identity_id=request.identity_id,
                output="[Blocked] Input did not pass policy check.", policy_passed=False,
            )
        sanitized_input = input_policy.transformed_data or request.user_input

        _executive_state_block = ""
        if self.executive is not None:
            try:
                self.executive.recover(identity.id)
                self.executive._ctx(identity.id, runtime=self)
                _executive_state_block = self.executive.render_state(identity.id)
            except Exception:
                _executive_state_block = ""

        _prometheus_evolved = False
        if self.prometheus:
            try:
                _pre = self.prometheus.pre_check_and_evolve(
                    user_input=sanitized_input, identity_id=identity.id,
                    runtime=self, session_id=request.session_id,
                )
                if _pre and _pre.acquired:
                    _prometheus_evolved = True
            except Exception:
                pass

        # ── NATIVE TOOL CALLING SETUP ─────────────────────────────────
        # Small local models can degrade badly if every turn is forced through
        # tool-call mode. Enable tools only when the user input appears to
        # request computation, date/time, file operations, or system info.
        def _should_enable_tools(user_text: str) -> bool:
            text = (user_text or "").strip().lower()
            if not text:
                return False
            patterns = (
                r"\b(calc|calculate|compute|evaluate|math|equation)\b",
                r"[\d\)\]]\s*[\+\-\*/]\s*[\d\(\[]",
                r"\b(square root|sqrt|convert|conversion|unit)\b",
                r"\b(current date|current time|what time|what date|today|now)\b",
                r"\b(create|write|append|file|directory|folder|path)\b",
                r"\b(system info|cpu|memory|disk|uptime|hostname)\b",
            )
            return any(re.search(p, text) for p in patterns)

        user_profile = self._get_user_profile(identity.id)
        session_fact_store = self._get_fact_store_for_session(identity.id, session_id)
        cap_prompts = self.capability_registry.all_prompts(identity.id)

        _tool_defs: List[Dict[str, Any]] = []
        _tool_map: Dict[str, tuple] = {}
        _evidence_results: List[Dict[str, Any]] = []

        for cap in self.capability_registry.list(identity.id):
            cap_id = getattr(cap, "id", "unknown")
            for skill in (cap.skills() or []):
                skill_name = getattr(skill, "name", "")
                if not skill_name:
                    continue
                safe_name = skill_name.replace(".", "__")
                _tool_map[safe_name] = (cap, skill_name)
                _tool_defs.append({
                    "type": "function",
                    "function": {
                        "name": safe_name,
                        "description": getattr(skill, "description", "") or f"Execute {skill_name}",
                        "parameters": {
                            "type": "object",
                            "properties": {},
                            "additionalProperties": True,  # Flat dictionary for Llama 3 native parser
                        },
                    },
                })

        def _execute_tool_call(func_name: str, args: Any) -> str:
            t0 = _time_mod.monotonic()
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    args = {}
            if not isinstance(args, dict):
                args = {}

            entry = _tool_map.get(func_name)
            if not entry:
                return json.dumps({"error": f"Unknown tool: {func_name}"})

            cap, skill_name = entry
            
            # Extract flat arguments directly for Llama 3 native parser
            params = {}
            for k, v in args.items():
                if k not in ("task", "params"):
                    params[k] = v
            if "params" in args and isinstance(args["params"], dict):
                params.update(args["params"])

            try:
                result = cap.call(skill_name, **params)
                duration_ms = (_time_mod.monotonic() - t0) * 1000
                success = bool(getattr(result, "success", False)) if hasattr(result, "success") else True
                data = getattr(result, "data", getattr(result, "output", result))
                error = getattr(result, "error", None)
                if error and success:
                    success = False
                err_msg = ""
                if error:
                    err_msg = error.get("message", str(error)) if isinstance(error, dict) else str(error)
                _evidence_results.append({
                    "capability": cap_id, "action": skill_name,
                    "success": success, "confidence": 1.0 if success else 0.0,
                    "duration_ms": duration_ms,
                    "error": {"message": err_msg} if err_msg else None,
                })
                if success:
                    if isinstance(data, (dict, list)):
                        return json.dumps(data, default=str)
                    return json.dumps({"result": str(data)}, default=str)
                return json.dumps({"error": err_msg or "Skill reported failure"}, default=str)
            except Exception as e:
                duration_ms = (_time_mod.monotonic() - t0) * 1000
                _evidence_results.append({
                    "capability": cap_id, "action": skill_name,
                    "success": False, "confidence": 0.0, "duration_ms": duration_ms,
                    "error": {"message": f"{type(e).__name__}: {e}"},
                })
                return json.dumps({"error": f"{type(e).__name__}: {e}"}, default=str)

        context = self.context_composer.compose(
            identity=identity, memory_store=self.memory_store,
            skill_registry=self.skill_registry, goal_engine=self.goal_engine,
            intention_engine=self.intention_engine, identity_graph=self.identity_graph,
            motivation_engine=self.motivation_engine, timeline_registry=self.timeline_registry,
            fact_store=session_fact_store, user_profile=user_profile,
            query=sanitized_input, top_k_memories=top_k_memories,
            session_id=request.session_id, session_mode=session_mode,
            emotion_state=emotion_state,
            capability_prompts=cap_prompts if cap_prompts else None,
            evidence_results=None,
        )

        self._emit(EventType.CONTEXT_COMPOSED, identity_id=identity.id, session_id=session_id,
                   token_estimate=context.token_estimate(), session_mode=session_mode.value)

        if _executive_state_block:
            context.custom_blocks["executive_state"] = _executive_state_block

        if self.adapter:
            self._emit(EventType.MODEL_REQUESTED, identity_id=identity.id,
                       session_id=request.session_id, model=self.adapter.model)
            _t0 = _time_mod.monotonic()

            generate_kwargs: Dict[str, Any] = {}
            if _tool_defs and _should_enable_tools(sanitized_input):
                generate_kwargs["tools"] = _tool_defs
                generate_kwargs["execute_tool"] = _execute_tool_call

            try:
                raw_output = self.adapter.generate(
                    context=context.render(), user_input=sanitized_input,
                    identity=identity, **generate_kwargs,
                )
            except TypeError:
                raw_output = self.adapter.generate(
                    context=context.render(), user_input=sanitized_input, identity=identity,
                )

            raw_output = str(raw_output or "")
            raw_output = re.sub(r"\[Thought\]", "<thought>", raw_output, flags=re.IGNORECASE)
            raw_output = re.sub(r"\[/Thought\]", "</thought>", raw_output, flags=re.IGNORECASE)
            if raw_output.count("<thought>") > raw_output.count("</thought>"):
                raw_output += "\n</thought>"

            _latency = _time_mod.monotonic() - _t0
            self._emit(EventType.MODEL_RESPONDED, identity_id=identity.id,
                       session_id=request.session_id, model=self.adapter.model,
                       response_length=len(raw_output), latency_ms=round(_latency * 1000))
        else:
            raw_output = f"[No adapter configured. Context prepared for {identity.name}]"

        _has_evidence = bool(_evidence_results)

        if not _prometheus_evolved and self.prometheus and self.adapter:
            try:
                _post = self.prometheus.post_check_and_evolve(
                    response=raw_output, user_input=sanitized_input,
                    identity_id=identity.id, runtime=self, session_id=request.session_id,
                )
                if _post and _post.acquired and _post.retry_response:
                    raw_output = _post.retry_response
                    _prometheus_evolved = True
            except Exception:
                pass

        if _has_evidence:
            _fails = sum(1 for r in _evidence_results if not r["success"])
            _total = len(_evidence_results)
            if _fails > 0:
                _disc = [f"\n\u26a0 **Confidence Notice** \u2014 {_fails} failed out of {_total} capability calls."]
                for _r in _evidence_results:
                    if not _r["success"]:
                        _disc.append(f"  \u2022 {_r['capability']}.{_r['action']} failed: {_r.get('error', {}).get('message', 'unknown')[:150]}")
                _disc.append("")
                raw_output = "\n".join(_disc) + raw_output

        output_policy = self.policy_engine.evaluate(raw_output, scope=PolicyScope.OUTPUT)
        self._emit(EventType.POLICY_TRIGGERED, identity_id=identity.id, session_id=session_id,
                   scope="output", allowed=output_policy.allowed, policies_applied=output_policy.applied_policies)
        if not output_policy.allowed:
            final_output = "[Blocked] Output did not pass policy check."
            policy_passed = False
        else:
            final_output = output_policy.transformed_data or raw_output
            policy_passed = True

        eval_report = self.evaluation_engine.evaluate(
            identity_id=identity.id, interaction_id=request.id,
            input_data=sanitized_input, output_data=final_output,
        )
        self._emit(EventType.EVALUATION_COMPLETED, identity_id=identity.id, session_id=request.session_id,
                   overall_score=eval_report.overall_score, passed=eval_report.passed,
                   criteria_count=len(eval_report.records))

        episodic = MemoryFragment(
            identity_id=identity.id,
            content=f"User: {sanitized_input}\nAssistant: {final_output}",
            memory_type=MemoryType.EPISODIC, session_id=request.session_id,
            tags=["interaction"],
        )
        self.memory_store.add(episodic)
        self._persist_memory(episodic)
        self._emit(EventType.EXPERIENCE_RECORDED, identity_id=identity.id, session_id=request.session_id,
                   memory_id=episodic.id, memory_type=episodic.memory_type.value,
                   content=episodic.content[:200])

        semantic_mem = self._extract_and_store_semantic_memory(
            user_input=sanitized_input, output=final_output,
            identity_id=identity.id, session_id=request.session_id,
        )

        if session_mode == SessionMode.NORMAL:
            fact_store = self._fact_stores.get(identity.id)
        else:
            fact_store = self._session_fact_stores.get(session_id)
        if fact_store is not None:
            self.mutation_engine.fact_store = fact_store

        mutation_proposals = self.mutation_engine.analyze(
            user_input=sanitized_input, assistant_response=final_output, identity_spec=identity,
        )
        if mutation_proposals:
            validated = self.mutation_engine.validate(mutation_proposals, existing_records=None)
            self.mutation_engine.apply_proposals_to_fact_store(validated)
            for proposal in validated:
                if proposal.status in (MutationStatus.ACCEPTED, MutationStatus.CONFLICT):
                    self._emit(
                        EventType.IDENTITY_MUTATION_ACCEPTED if proposal.status == MutationStatus.ACCEPTED
                        else EventType.IDENTITY_MUTATION_CONFLICT,
                        identity_id=identity.id, session_id=session_id,
                        field=proposal.field, old_value=proposal.old_value,
                        new_value=proposal.new_value, confidence=proposal.confidence, reason=proposal.reason,
                    )
                else:
                    self._emit(EventType.IDENTITY_MUTATION_REJECTED, identity_id=identity.id,
                               session_id=session_id, field=proposal.field, reason=proposal.rejection_reason)
            accepted_count = sum(1 for p in validated if p.status == MutationStatus.ACCEPTED)
            if accepted_count > 0 and session_mode == SessionMode.NORMAL:
                fields_changed = [p.field for p in validated if p.status == MutationStatus.ACCEPTED]
                identity.bump_version(level="patch", changelog=f"Mutated: {', '.join(fields_changed[:3])}")
            if session_mode == SessionMode.NORMAL:
                self._save_fact_store(identity.id)
                self._persist_identity(identity)
            else:
                self._save_session_fact_store(session_id)

        tl_title = "Interaction"
        tl_description = f"User said: {sanitized_input[:100]}"
        tl_meta = {"session_id": request.session_id, "eval_score": eval_report.overall_score}
        if semantic_mem:
            mem_tags = semantic_mem.tags
            if "preference" in mem_tags: tl_title = "Learned preference"
            elif "decision" in mem_tags: tl_title = "Made decision"
            elif "correction" in mem_tags: tl_title = "Received correction"
            elif "milestone" in mem_tags: tl_title = "Milestone"
            tl_meta["memory_id"] = semantic_mem.id
            tl_meta["memory_type"] = semantic_mem.memory_type.value

        self.timeline_registry.record_event(identity.id, LifeEvent(
            identity_id=identity.id, event_type=LifeEventType.MILESTONE,
            title=tl_title, description=tl_description, significance=2, metadata=tl_meta,
        ))
        self._persist_timeline(identity.id)
        self._emit(EventType.LIFE_EVENT_RECORDED, identity_id=identity.id, session_id=request.session_id,
                   title=tl_title, description=tl_description)

        target = request.session_id or "user"
        self.identity_graph.interact_or_connect(
            source_id=identity.id, target_id=target, edge_type=EdgeType.PEER, bidirectional=False,
        )
        self._persist_relationships(identity.id)
        self._persist_goals(identity.id)

        if _evidence_results and policy_passed:
            footer_lines = ["\n\n---\n📊 **Evidence Sources**"]
            for ev in _evidence_results[:12]:
                status = "✓" if ev["success"] else "✗"
                conf = ev["confidence"]
                label = "verified" if conf >= 0.8 else "sourced" if conf >= 0.5 else "inferred"
                err = f" — {ev['error']['message'][:200]}" if ev.get("error") else ""
                skill_label = ev["action"] if ev["action"].startswith(f"{ev['capability']}.") else f"{ev['capability']}.{ev['action']}"
                footer_lines.append(f"  {status} `{skill_label}` — {label} ({conf:.1f}) — {ev['duration_ms']:.0f}ms{err}")
            footer_lines.append("---")
            final_output += "\n".join(footer_lines)

        return InteractionResponse(
            request_id=request.id, identity_id=identity.id, output=final_output,
            context_used=context, policy_passed=policy_passed, eval_score=eval_report.overall_score,
        )

    def __repr__(self) -> str:
        return (
            f"IdentityRuntime("
            f"identities={len(self.identity_store)}, "
            f"adapter={type(self.adapter).__name__ if self.adapter else 'None'}"
            f")"
        )
