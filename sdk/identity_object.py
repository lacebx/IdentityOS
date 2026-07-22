"""
sdk/identity_object.py — Complete IdentityOS developer SDK.

The SDK hides all internal runtime complexity behind a clean, typed API.

Example:
    from sdk import Identity

    # Load or create
    lace = Identity.load("lace")
    # lace = Identity.create("Lace", persona="mentor")

    # Chat
    reply = lace.chat("Hello, how are you?")

    # Observe facts
    lace.observe("My favorite color is blue")

    # Goals & intentions
    lace.goal("Learn Python", priority="high")
    lace.intention("Ask about their weekend")

    # Relationships
    rel = lace.relationship("user-123", trust_level=0.8)

    # Timeline
    events = lace.timeline(limit=10)

    # Export
    lace.export("lace-portable.json")
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from core.goals import Goal
    from core.identity import IdentitySpec
    from core.intentions import Intention
    from runtime.orchestrator import IdentityRuntime


# ---------------------------------------------------------------------------
# Identity class — main entry point
# ---------------------------------------------------------------------------


class Identity:
    """
    Main entry point for the IdentityOS SDK.

    Use ``Identity.load()`` to load an existing identity,
    ``Identity.create()`` to create a new one, or
    ``Identity.from_file()`` to import from a portable JSON export.

    All three return an ``IdentityObject`` that you can chat with,
    train, and inspect.
    """

    @classmethod
    def load(
        cls,
        identity_id: str,
        storage_path: str = ".identity_store",
    ) -> IdentityObject:
        """Load an identity from persistent storage."""
        from runtime.persistence import JSONFileBackend
        from runtime.orchestrator import IdentityRuntime

        storage = JSONFileBackend(root_dir=storage_path)
        runtime = IdentityRuntime(storage=storage)
        runtime.load(identity_id)
        return IdentityObject(runtime, identity_id)

    @classmethod
    def create(
        cls,
        name: str,
        identity_id: Optional[str] = None,
        identity_class: str = "agent",
        persona: str = "",
        role: str = "",
        storage_path: str = ".identity_store",
    ) -> IdentityObject:
        """Create a new identity and register it with the runtime.

        Args:
            name: Display name for the identity
            identity_id: Optional unique ID (auto-generated if omitted)
            identity_class: "agent", "assistant", "user", "system", etc.
            persona: Personality descriptor
            role: Functional role description
            storage_path: Directory for persistent storage
        """
        from runtime.persistence import JSONFileBackend
        from runtime.orchestrator import IdentityRuntime
        from core.identity import create_identity, IdentityClass

        ic_map = {
            "agent": IdentityClass.AGENT,
            "person": IdentityClass.PERSON,
            "robot": IdentityClass.ROBOT,
            "organization": IdentityClass.ORGANIZATION,
            "concept": IdentityClass.CONCEPT,
            "custom": IdentityClass.CUSTOM,
        }
        identity_class_enum = ic_map.get(identity_class, IdentityClass.AGENT)

        storage = JSONFileBackend(root_dir=storage_path)
        runtime = IdentityRuntime(storage=storage)
        spec = create_identity(
            name=name,
            identity_id=identity_id,
            identity_class=identity_class_enum,
            persona=persona,
            role=role,
        )
        runtime.register(spec)
        return IdentityObject(runtime, spec.id)

    @classmethod
    def from_file(cls, path: str) -> IdentityObject:
        """Import an identity from a portable JSON file."""
        from runtime.persistence import JSONFileBackend
        from runtime.orchestrator import IdentityRuntime
        from core.identity import IdentitySpec

        data = json.loads(Path(path).read_text(encoding="utf-8"))

        storage = JSONFileBackend(root_dir=".identity_store")
        runtime = IdentityRuntime(storage=storage)

        spec = IdentitySpec.from_dict(data.get("identity", data))
        runtime.register(spec)

        # Restore memories
        for m in data.get("memories", []):
            from core.memory import MemoryFragment
            try:
                runtime.memory_store.add(MemoryFragment.from_dict(m))
            except Exception:
                pass

        # Restore goals
        for gd in data.get("goals", []):
            from core.goals import Goal
            try:
                runtime.goal_engine.add(Goal.from_dict(gd))
            except Exception:
                pass

        # Restore intentions
        for id_ in data.get("intentions", []):
            from core.intentions import Intention
            try:
                runtime.intention_engine.add(Intention.from_dict(id_))
            except Exception:
                pass

        # Restore timeline
        tl_data = data.get("timeline")
        if tl_data:
            timeline = runtime.timeline_registry.get_or_create(spec.id)
            if tl_data.get("events"):
                from core.timeline import LifeEvent, LifeEventType
                for ed in tl_data["events"]:
                    try:
                        timeline.record(
                            LifeEvent(
                                id=ed.get("id", str(uuid.uuid4())),
                                identity_id=spec.id,
                                event_type=LifeEventType(ed["event_type"]),
                                title=ed.get("title", ""),
                                description=ed.get("description", ""),
                                significance=ed.get("significance", 3),
                            )
                        )
                    except Exception:
                        pass

        return IdentityObject(runtime, spec.id)


# ---------------------------------------------------------------------------
# Session context manager
# ---------------------------------------------------------------------------


@dataclass
class SessionContext:
    """
    Context manager for identity sessions.

    Usage:
        with identity.session() as s:
            s.chat("Hello in a session")
    """

    _identity: IdentityObject
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __enter__(self) -> SessionContext:
        self._identity._session_id = self.session_id
        self._identity._runtime.start_session(
            self._identity._identity_id, session_id=self.session_id,
        )
        return self

    def __exit__(self, *_: Any) -> None:
        self._identity._runtime.end_session(self.session_id)
        self._identity._session_id = None

    def chat(self, message: str, **kwargs: Any) -> str:
        return self._identity.chat(message, **kwargs)

    def observe(self, text: str, **kwargs: Any) -> List[Dict[str, Any]]:
        return self._identity.observe(text, **kwargs)


# ---------------------------------------------------------------------------
# IdentityObject — a live identity
# ---------------------------------------------------------------------------


class IdentityObject:
    """
    A live identity that you can chat with, train, inspect, and export.

    This is the primary object returned by ``Identity.load()``,
    ``Identity.create()``, and ``Identity.from_file()``.
    """

    def __init__(self, runtime: IdentityRuntime, identity_id: str) -> None:
        self._runtime = runtime
        self._identity_id = identity_id
        self._session_id: Optional[str] = None

    # ═══════════════════════════════════════════════════════════════════
    # Identity properties
    # ═══════════════════════════════════════════════════════════════════

    @property
    def id(self) -> str:
        return self._identity_id

    @property
    def name(self) -> str:
        spec = self._spec
        return spec.name if spec else "Unknown"

    @property
    def persona(self) -> str:
        spec = self._spec
        return spec.persona if spec else ""

    @property
    def role(self) -> str:
        spec = self._spec
        return spec.role if spec else ""

    @property
    def version(self) -> str:
        spec = self._spec
        return spec.version if spec else "0.0.0"

    @property
    def _spec(self) -> Optional[IdentitySpec]:
        return self._runtime.identity_store.get(self._identity_id)

    # ═══════════════════════════════════════════════════════════════════
    # Chat
    # ═══════════════════════════════════════════════════════════════════

    def chat(self, message: str, **kwargs: Any) -> str:
        """Send a message to this identity and get a response."""
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
        """Ask a question. Alias for chat()."""
        return self.chat(question)

    def instruct(self, instruction: str) -> str:
        """Give an instruction. Alias for chat()."""
        return self.chat(instruction)

    # ═══════════════════════════════════════════════════════════════════
    # Observe — extract facts from conversation
    # ═══════════════════════════════════════════════════════════════════

    def observe(
        self,
        text: str,
        source: str = "sdk",
    ) -> List[Dict[str, Any]]:
        """
        Extract facts from a piece of text and store them as user knowledge.

        Returns a list of extracted facts with field, value, and confidence.
        """
        from core.user_profile import extract_user_facts

        profile = self._get_user_profile()
        raw_facts = extract_user_facts(text)
        results: List[Dict[str, Any]] = []

        for fact in raw_facts:
            stored = profile.add_or_update(fact.field, fact.value, source=source)
            results.append({
                "field": stored.field,
                "value": stored.value,
                "confidence": stored.confidence,
                "uncertain": stored.uncertain,
                "contradictions": stored.contradictions,
            })

        return results

    # ═══════════════════════════════════════════════════════════════════
    # Memory
    # ═══════════════════════════════════════════════════════════════════

    def remember(
        self,
        content: str,
        tags: Optional[List[str]] = None,
        memory_type: str = "semantic",
    ) -> str:
        """
        Store a memory for this identity.

        Returns the memory fragment ID.
        """
        from core.memory import MemoryFragment, MemoryType

        mt = getattr(MemoryType, memory_type.upper(), MemoryType.SEMANTIC)
        frag = MemoryFragment(
            identity_id=self._identity_id,
            content=content,
            memory_type=mt,
            session_id=self._session_id,
            tags=tags or [],
        )
        self._runtime.memory_store.add(frag)
        return frag.id

    def recall(
        self,
        query: str,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve memories relevant to a query.

        Returns a list of dicts with id, content, memory_type, importance.
        """
        items = self._runtime.memory_store.search_keywords(
            query, identity_id=self._identity_id, limit=limit,
        )
        return [
            {
                "id": item.id,
                "content": item.content,
                "memory_type": item.memory_type.value,
                "importance": item.importance,
                "created_at": item.created_at.isoformat() if item.created_at else "",
                "tags": item.tags,
            }
            for item in items
        ]

    def forget(self, memory_id: str) -> bool:
        """Remove a specific memory by ID."""
        return self._runtime.memory_store.remove(memory_id)

    def memories(
        self,
        memory_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        List all memories for this identity, optionally filtered by type.
        """
        all_mems = self._runtime.memory_store.by_identity(self._identity_id)
        if memory_type:
            from core.memory import MemoryType
            mt = getattr(MemoryType, memory_type.upper(), None)
            if mt:
                all_mems = [m for m in all_mems if m.memory_type == mt]
        return [
            {
                "id": m.id,
                "content": m.content,
                "memory_type": m.memory_type.value,
                "importance": m.importance,
                "created_at": m.created_at.isoformat() if m.created_at else "",
                "tags": m.tags,
            }
            for m in all_mems[:limit]
        ]

    # ═══════════════════════════════════════════════════════════════════
    # Goals
    # ═══════════════════════════════════════════════════════════════════

    def goal(
        self,
        title: str,
        description: str = "",
        priority: str = "medium",
        scope: str = "persistent",
        success_criteria: str = "",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Create a goal for this identity to pursue.

        Args:
            title: Short goal name
            description: Detailed description
            priority: "low", "medium", "high", "critical"
            scope: "immediate", "session", "persistent", "lifelong"
            success_criteria: How to determine completion

        Returns:
            Dict with id, title, priority, scope, status
        """
        from core.goals import Goal, GoalPriority, GoalScope

        priority_map = {
            "low": GoalPriority.LOW,
            "medium": GoalPriority.MEDIUM,
            "high": GoalPriority.HIGH,
            "critical": GoalPriority.CRITICAL,
        }
        scope_map = {
            "immediate": GoalScope.IMMEDIATE,
            "session": GoalScope.SESSION,
            "persistent": GoalScope.PERSISTENT,
            "lifelong": GoalScope.LIFELONG,
        }

        goal = Goal(
            title=title,
            description=description,
            priority=priority_map.get(priority, GoalPriority.MEDIUM),
            scope=scope_map.get(scope, GoalScope.PERSISTENT),
            success_criteria=success_criteria,
            **kwargs,
        )
        self._runtime.goal_engine.add(goal)
        return self._goal_to_dict(goal)

    def goals(
        self,
        status: str = "active",
    ) -> List[Dict[str, Any]]:
        """List all goals, optionally filtered by status."""
        all_goals = self._runtime.goal_engine.all()
        if status and status != "all":
            from core.goals import GoalStatus
            target = getattr(GoalStatus, status.upper(), None)
            if target:
                all_goals = [g for g in all_goals if g.status == target]
        return [self._goal_to_dict(g) for g in all_goals]

    def complete_goal(self, goal_id: str, reason: str = "") -> bool:
        """Mark a goal as completed."""
        goal = self._runtime.goal_engine.get(goal_id)
        if not goal:
            return False
        goal.mark_completed(reason=reason)
        return True

    def abandon_goal(self, goal_id: str, reason: str = "") -> bool:
        """Abandon a goal."""
        goal = self._runtime.goal_engine.get(goal_id)
        if not goal:
            return False
        goal.abandon(reason=reason)
        return True

    @staticmethod
    def _goal_to_dict(goal: Any) -> Dict[str, Any]:
        return {
            "id": goal.id,
            "title": goal.title,
            "description": goal.description,
            "status": goal.status.value,
            "priority": goal.priority.name,
            "scope": goal.scope.value,
            "progress": goal.progress,
            "success_criteria": goal.success_criteria,
            "created_at": goal.created_at.isoformat() if goal.created_at else "",
            "confidence": getattr(goal, "confidence", 0.0),
            "confidence_label": getattr(goal, "confidence_label", "unknown"),
        }

    # ═══════════════════════════════════════════════════════════════════
    # Intentions
    # ═══════════════════════════════════════════════════════════════════

    def intention(
        self,
        description: str,
        priority: str = "medium",
        hours: int = 24,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Create a short-term commitment (intention).

        Intentions auto-expire after *hours* hours. Sustained intentions
        can be promoted to goals.

        Args:
            description: What the identity commits to
            priority: "low", "medium", "high"
            hours: Hours until auto-expiry

        Returns:
            Dict with id, description, priority, status, expires_at
        """
        from datetime import timedelta
        from core.intentions import Intention, IntentionPriority

        priority_map = {
            "low": IntentionPriority.LOW,
            "medium": IntentionPriority.MEDIUM,
            "high": IntentionPriority.HIGH,
        }

        intention = Intention(
            description=description,
            priority=priority_map.get(priority, IntentionPriority.MEDIUM),
            source_session_id=self._session_id,
            expires_at=datetime.now(timezone.utc).replace(tzinfo=None)
            + timedelta(hours=hours),
            **kwargs,
        )
        self._runtime.intention_engine.add(intention)
        return self._intention_to_dict(intention)

    def intentions(
        self,
        status: str = "active",
    ) -> List[Dict[str, Any]]:
        """List all intentions, optionally filtered by status."""
        # Auto-expire before listing
        self._runtime.intention_engine.check_expiry()

        all_intentions = self._runtime.intention_engine.all()
        if status and status != "all":
            from core.intentions import IntentionStatus
            target = getattr(IntentionStatus, status.upper(), None)
            if target:
                all_intentions = [i for i in all_intentions if i.status == target]
        return [self._intention_to_dict(i) for i in all_intentions]

    def complete_intention(self, intention_id: str, reason: str = "") -> bool:
        """Mark an intention as completed."""
        intention = self._runtime.intention_engine.get(intention_id)
        if not intention:
            return False
        intention.complete(reason=reason)
        return True

    def promote_intention(
        self,
        intention_id: str,
        goal_id: str,
        reason: str = "system_promotion",
        detail: str = "",
    ) -> bool:
        """Promote an intention to a goal."""
        from core.intentions import PromotionReason

        reason_map = {
            "repeated": PromotionReason.REPEATED,
            "sustained_relevance": PromotionReason.SUSTAINED_RELEVANCE,
            "user_request": PromotionReason.USER_REQUEST,
            "system_promotion": PromotionReason.SYSTEM_PROMOTION,
        }
        return self._runtime.intention_engine.promote_to_goal(
            intention_id, goal_id,
            reason=reason_map.get(reason, PromotionReason.SYSTEM_PROMOTION),
            detail=detail,
        )

    @staticmethod
    def _intention_to_dict(intention: Any) -> Dict[str, Any]:
        return {
            "id": intention.id,
            "description": intention.description,
            "status": intention.status.value,
            "priority": intention.priority.name,
            "goal_id": intention.goal_id,
            "created_at": intention.created_at.isoformat() if intention.created_at else "",
            "expires_at": intention.expires_at.isoformat() if intention.expires_at else "",
            "completed_at": intention.completed_at.isoformat() if intention.completed_at else "",
            "confidence": getattr(intention, "confidence", 0.0),
            "confidence_label": getattr(intention, "confidence_label", "unknown"),
            "metadata": getattr(intention, "metadata", {}),
        }

    # ═══════════════════════════════════════════════════════════════════
    # Relationships
    # ═══════════════════════════════════════════════════════════════════

    def relationship(
        self,
        entity_id: str,
        trust_level: Optional[float] = None,
        context: str = "",
        edge_type: str = "friend",
    ) -> Dict[str, Any]:
        """
        Get or set a relationship with an entity.

        If trust_level is provided, creates or updates the relationship.
        If omitted, returns the current relationship if it exists.

        Args:
            entity_id: The ID of the other entity
            trust_level: Trust level 0.0–1.0 (omit to query)
            context: Description of the relationship
            edge_type: "friend", "family", "mentor", "student", "collaborator", etc.

        Returns:
            Dict with relationship details
        """
        from core.relationships import EdgeType, TrustLevel

        et_map = {
            "friend": EdgeType.FRIEND,
            "family": EdgeType.FAMILY,
            "mentor": EdgeType.MENTOR,
            "student": EdgeType.STUDENT,
            "collaborator": EdgeType.COLLABORATOR,
            "delegate": EdgeType.DELEGATE,
            "adversary": EdgeType.ADVERSARY,
            "observer": EdgeType.OBSERVER,
        }

        if trust_level is not None:
            # Map float 0.0–1.0 to TrustLevel enum
            if trust_level >= 0.9:
                tl = TrustLevel.ABSOLUTE
            elif trust_level >= 0.7:
                tl = TrustLevel.HIGH
            elif trust_level >= 0.4:
                tl = TrustLevel.MEDIUM
            elif trust_level >= 0.1:
                tl = TrustLevel.LOW
            else:
                tl = TrustLevel.NONE

            et = et_map.get(edge_type, EdgeType.FRIEND)
            edge = self._runtime.identity_graph.connect(
                source_id=self._identity_id,
                target_id=entity_id,
                edge_type=et,
                trust_level=tl,
                metadata={"context": context} if context else {},
            )
            return self._edge_to_dict(edge)

        edges = self._runtime.identity_graph.get_relationships(self._identity_id)
        for e in edges:
            if e.target_id == entity_id or e.source_id == entity_id:
                return self._edge_to_dict(e)
        return {"entity_id": entity_id, "error": "No relationship found"}

    def relationships(self) -> List[Dict[str, Any]]:
        """List all relationships for this identity."""
        edges = self._runtime.identity_graph.get_relationships(self._identity_id)
        return [self._edge_to_dict(e) for e in edges]

    @staticmethod
    def _edge_to_dict(edge: Any) -> Dict[str, Any]:
        return {
            "source_id": edge.source_id,
            "target_id": edge.target_id,
            "edge_type": edge.edge_type.value if hasattr(edge.edge_type, "value") else str(edge.edge_type),
            "trust_level": edge.trust_level.value if hasattr(edge.trust_level, "value") else float(edge.trust_level),
            "interaction_count": getattr(edge, "interaction_count", 0),
            "last_interaction": getattr(edge, "last_interaction", ""),
            "metadata": getattr(edge, "metadata", {}),
        }

    # ═══════════════════════════════════════════════════════════════════
    # Timeline
    # ═══════════════════════════════════════════════════════════════════

    def timeline(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get timeline events for this identity."""
        timeline = self._runtime.timeline_registry.get(self._identity_id)
        if not timeline:
            return []
        events = timeline.events()
        return [
            {
                "id": e.id,
                "event_type": e.event_type.value if hasattr(e.event_type, "value") else str(e.event_type),
                "title": e.title,
                "description": e.description,
                "significance": e.significance,
                "occurred_at": e.occurred_at.isoformat() if hasattr(e.occurred_at, "isoformat") else str(e.occurred_at),
                "metadata": e.metadata,
            }
            for e in events[-limit:]
        ]

    def record_event(
        self,
        event_type: str,
        title: str,
        description: str = "",
        significance: int = 3,
    ) -> str:
        """Record a custom event in the identity's timeline."""
        from core.timeline import LifeEvent, LifeEventType

        valid_types = {e.value for e in LifeEventType}
        et_map = {
            "creation": LifeEventType.CREATION,
            "activation": LifeEventType.ACTIVATION,
            "milestone": LifeEventType.MILESTONE,
            "relationship_formed": LifeEventType.RELATIONSHIP_FORMED,
            "relationship_lost": LifeEventType.RELATIONSHIP_LOST,
            "knowledge_acquired": LifeEventType.KNOWLEDGE_ACQUIRED,
            "skill_mastered": LifeEventType.SKILL_MASTERED,
            "goal_completed": LifeEventType.GOAL_COMPLETED,
            "failure": LifeEventType.FAILURE,
            "promotion": LifeEventType.PROMOTION,
            "transformation": LifeEventType.TRANSFORMATION,
            "preference_learned": LifeEventType.PREFERENCE_LEARNED,
            "belief_adopted": LifeEventType.BELIEF_ADOPTED,
            "trait_changed": LifeEventType.TRAIT_CHANGED,
            "trust_changed": LifeEventType.TRUST_CHANGED,
        }

        et = et_map.get(event_type)
        if et is None and event_type in valid_types:
            et = LifeEventType(event_type)
        if et is None:
            et = LifeEventType.MILESTONE

        event = LifeEvent(
            identity_id=self._identity_id,
            event_type=et,
            title=title,
            description=description,
            significance=significance,
        )
        self._runtime.timeline_registry.record_event(self._identity_id, event)
        return event.id

    # ═══════════════════════════════════════════════════════════════════
    # Evidence & Provenance
    # ═══════════════════════════════════════════════════════════════════

    def evidence(self, entity_id: str) -> List[Dict[str, Any]]:
        """Get evidence chain for any entity (fact, goal, intention, etc.)."""
        evidence_list: List[Dict[str, Any]] = []

        # Check FactStore evidence
        fact_store = self._runtime._fact_stores.get(self._identity_id)
        if fact_store:
            fact = fact_store.find(entity_id)
            if fact and hasattr(fact, "evidence_ids") and fact.evidence_ids:
                for eid in fact.evidence_ids:
                    evidence_list.append({
                        "evidence_id": eid,
                        "source": "fact_store",
                        "field": fact.field,
                        "value": fact.value,
                        "confidence": fact.confidence,
                    })

        # Check EvidenceGraph
        from core.evidence_graph import EvidenceGraph
        evidence_graph = getattr(self._runtime, "_evidence_graph", None)
        if evidence_graph:
            nodes = evidence_graph.evidence_for(entity_id)
            for n in nodes:
                evidence_list.append({
                    "evidence_id": n.evidence_id,
                    "source": "evidence_graph",
                    "type": n.evidence_type.value if hasattr(n.evidence_type, "value") else str(n.evidence_type),
                    "description": n.description,
                    "source_text": n.source_text,
                    "timestamp": n.timestamp,
                })

        return evidence_list

    def provenance(self, entity_id: str) -> Dict[str, Any]:
        """Get full provenance for an entity — evidence, confidence, and history."""
        fact_store = self._runtime._fact_stores.get(self._identity_id)
        fact = fact_store.find(entity_id) if fact_store else None

        result: Dict[str, Any] = {
            "entity_id": entity_id,
            "evidence": self.evidence(entity_id),
            "confidence": 0.65,
            "confidence_label": "moderate",
        }

        if fact:
            result["value"] = fact.value
            result["confidence"] = fact.confidence
            from core.confidence import ConfidenceScorer
            result["confidence_label"] = ConfidenceScorer.label(fact.confidence)
            result["times_reinforced"] = getattr(fact, "times_reinforced", 0)
            result["contradictions"] = getattr(fact, "contradictions", 0)
            result["status"] = fact.status.value if hasattr(fact.status, "value") else str(fact.status)
            result["first_seen"] = fact.first_seen
            result["last_confirmed"] = fact.last_confirmed

        return result

    # ═══════════════════════════════════════════════════════════════════
    # Confidence
    # ═══════════════════════════════════════════════════════════════════

    def confidence(self, entity_id: str) -> Dict[str, Any]:
        """
        Get confidence score and details for any entity.

        Works with facts (preferences, beliefs), goals, and intentions.
        """
        from core.confidence import ConfidenceScorer

        # Check FactStore
        fact_store = self._runtime._fact_stores.get(self._identity_id)
        if fact_store:
            fact = fact_store.find(entity_id)
            if fact:
                return {
                    "entity_id": entity_id,
                    "value": fact.value,
                    "confidence": fact.confidence,
                    "label": ConfidenceScorer.label(fact.confidence),
                    "description": ConfidenceScorer.description(fact.confidence),
                    "times_reinforced": getattr(fact, "times_reinforced", 0),
                    "contradictions": getattr(fact, "contradictions", 0),
                }

        # Check goals
        goal = self._runtime.goal_engine.get(entity_id)
        if goal:
            return {
                "entity_id": entity_id,
                "type": "goal",
                "title": goal.title,
                "confidence": getattr(goal, "confidence", 0.0),
                "label": getattr(goal, "confidence_label", "unknown"),
            }

        # Check intentions
        intention = self._runtime.intention_engine.get(entity_id)
        if intention:
            return {
                "entity_id": entity_id,
                "type": "intention",
                "description": intention.description,
                "confidence": getattr(intention, "confidence", 0.0),
                "label": getattr(intention, "confidence_label", "unknown"),
            }

        return {
            "entity_id": entity_id,
            "error": "Entity not found",
        }

    # ═══════════════════════════════════════════════════════════════════
    # Constitution
    # ═══════════════════════════════════════════════════════════════════

    def constitution(self) -> Dict[str, Any]:
        """
        Load the IdentityOS Constitution and Laws.

        Returns a dict with 'constitution' (the full text) and 'laws'
        (a dict of law name → text).
        """
        result: Dict[str, Any] = {
            "constitution": "",
            "laws": {},
        }

        constitution_path = Path("docs/constitution/constitution-v1.md")
        if constitution_path.exists():
            result["constitution"] = constitution_path.read_text(encoding="utf-8")

        laws_dir = Path("docs/laws")
        if laws_dir.exists():
            for law_file in sorted(laws_dir.glob("*.md")):
                name = law_file.stem
                result["laws"][name] = law_file.read_text(encoding="utf-8")

        return result

    # ═══════════════════════════════════════════════════════════════════
    # Sessions
    # ═══════════════════════════════════════════════════════════════════

    def session(self, session_id: Optional[str] = None) -> SessionContext:
        """
        Create a session context manager.

        Usage:
            with identity.session() as s:
                s.chat("Hello in a session")
        """
        sid = session_id or str(uuid.uuid4())
        return SessionContext(_identity=self, session_id=sid)

    def sessions(self) -> List[Dict[str, Any]]:
        """List active sessions for this identity."""
        session_list: List[Dict[str, Any]] = []
        for sid, id_in_sesh in self._runtime._sessions.items():
            if id_in_sesh == self._identity_id:
                mode = self._runtime._session_modes.get(sid)
                session_list.append({
                    "session_id": sid,
                    "mode": mode.value if mode else "normal",
                })
        return session_list

    # ═══════════════════════════════════════════════════════════════════
    # Export / Import
    # ═══════════════════════════════════════════════════════════════════

    def export(self, path: Optional[str] = None) -> Dict[str, Any]:
        """
        Export this identity as a portable JSON dict.

        If *path* is provided, also writes to file.
        Returns the full portable dict.
        """
        spec = self._spec
        if not spec:
            raise RuntimeError(f"Identity '{self._identity_id}' not loaded")

        # Gather timeline
        timeline_data = None
        timeline = self._runtime.timeline_registry.get(self._identity_id)
        if timeline:
            timeline_data = {"events": []}
            for e in timeline.events():
                ed = {
                    "id": e.id,
                    "identity_id": e.identity_id,
                    "event_type": e.event_type.value if hasattr(e.event_type, "value") else str(e.event_type),
                    "title": e.title,
                    "description": e.description,
                    "significance": e.significance,
                    "occurred_at": e.occurred_at.isoformat() if hasattr(e.occurred_at, "isoformat") else str(e.occurred_at),
                    "metadata": e.metadata,
                }
                timeline_data["events"].append(ed)

        # Gather fact store
        fact_store_data = None
        fact_store = self._runtime._fact_stores.get(self._identity_id)
        if fact_store:
            fact_store_data = fact_store.to_dict_full() if hasattr(fact_store, "to_dict_full") else None

        # Gather user profile
        user_profile_key = f"user_{self._identity_id}"
        profile_data = None
        profile = self._runtime._user_profiles.get(user_profile_key)
        if profile:
            profile_data = profile.to_dict()

        portable = {
            "export_version": "1.0.0",
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "identity": spec.to_dict(),
            "memories": [
                m.to_dict() for m in self._runtime.memory_store.by_identity(self._identity_id)
            ],
            "goals": [g.to_dict() for g in self._runtime.goal_engine.all()],
            "intentions": [i.to_dict() for i in self._runtime.intention_engine.all()],
            "timeline": timeline_data,
            "fact_store": fact_store_data,
            "user_profile": profile_data,
        }

        if path:
            Path(path).write_text(
                json.dumps(portable, indent=2, default=str),
                encoding="utf-8",
            )

        return portable

    def import_(self, data: Dict[str, Any]) -> int:
        """
        Import data into this identity from a portable dict.

        Returns the number of items imported.
        """
        count = 0

        # Import goals
        for gd in data.get("goals", []):
            from core.goals import Goal
            try:
                self._runtime.goal_engine.add(Goal.from_dict(gd))
                count += 1
            except Exception:
                pass

        # Import intentions
        for id_ in data.get("intentions", []):
            from core.intentions import Intention
            try:
                self._runtime.intention_engine.add(Intention.from_dict(id_))
                count += 1
            except Exception:
                pass

        # Import memories
        for md in data.get("memories", []):
            try:
                from core.memory import MemoryFragment
                frag = MemoryFragment.from_dict(md)
                if not self._runtime.memory_store.get(frag.id):
                    self._runtime.memory_store.add(frag)
                    count += 1
            except Exception:
                pass

        return count

    # ═══════════════════════════════════════════════════════════════════
    # User profile access
    # ═══════════════════════════════════════════════════════════════════

    def _get_user_profile(self) -> Any:
        key = f"user_{self._identity_id}"
        if key not in self._runtime._user_profiles:
            self._runtime._user_profiles[key] = __import__(
                "core.user_profile", fromlist=["UserProfile"]
            ).UserProfile(user_id=key)
        return self._runtime._user_profiles[key]

    def user_facts(self) -> List[Dict[str, Any]]:
        """List all known user facts (preferences, beliefs, etc.)."""
        profile = self._get_user_profile()
        if hasattr(profile, "all_facts"):
            return [f.to_dict() for f in profile.all_facts()]
        if hasattr(profile, "_facts"):
            return [f.to_dict() for f in profile._facts.values()]
        return []

    # ═══════════════════════════════════════════════════════════════════
    # Skills
    # ═══════════════════════════════════════════════════════════════════

    def can(self, skill_name: str) -> bool:
        """Check if this identity has a registered skill."""
        return self._runtime.skill_registry.get_by_name(skill_name) is not None

    def do(self, skill_name: str, **kwargs: Any) -> Any:
        """Invoke a skill by name."""
        result = self._runtime.skill_registry.invoke(skill_name, **kwargs)
        if not result.success:
            raise RuntimeError(f"Skill '{skill_name}' failed: {result.error}")
        return result.output

    def skills(self) -> List[Dict[str, Any]]:
        """List all registered skills."""
        return [
            {
                "name": s.name,
                "description": getattr(s, "description", ""),
                "version": getattr(s, "version", ""),
            }
            for s in self._runtime.skill_registry.list_active()
        ]

    # ═══════════════════════════════════════════════════════════════════
    # Natural Language Understanding — Intention, Meeting, Deadline
    # ═══════════════════════════════════════════════════════════════════

    _COMMITMENT_PATTERNS = [
        (r"(?:I'?ll|I will|I'm going to|Let me|I shall)\s+(.+?)(?:\s+(?:today|tomorrow|tonight|this week|next week|this weekend|on\s+\w+day|in\s+\d+\s+(?:hour|day|week|minute)s?|by\s+\w+day|by\s+tomorrow|by\s+\d+\s*(?:pm|am)))?\s*\.?\s*$", 1),
        (r"(?:I'?ll|I will|I'm going to)\s+(.+?)\s+(?:today|tomorrow|tonight|this week|next week|this weekend|on\s+\w+day|in\s+\d+\s+(?:hour|day|week|minute)s?|by\s+\w+day|by\s+tomorrow)", 1),
        (r"(?:finish|complete|done with|done|deploy|release|push|submit|send|write|implement|fix|resolve)\s+(.+?)(?:\s+(?:today|tomorrow|tonight|this week|next week|by\s+\w+day|in\s+\d+\s+(?:hour|day)s?))?\s*\.?\s*$", 0),
    ]

    _DEADLINE_PATTERNS = [
        (r"(?:by|before|for)\s+(today|tomorrow|tonight|this week|next week|this weekend|(\w+day)(?:\s+at\s+\d+)?)", 1),
        (r"(?:today|tomorrow|tonight|this week|next week|this weekend|in\s+\d+\s+(?:hour|day|week|minute)s?)", 0),
    ]

    _MEETING_PATTERNS = [
        r"(?:let'?s|we should|we need to|can we|could we|shall we)\s+(?:meet|sync|catch up|talk|discuss|chat|huddle)",
        r"(?:meeting|sync|catch[- ]?up|huddle|standup|call)\s+(?:today|tomorrow|this week|next week|on\s+\w+day|at\s+\d+)",
        r"(?:schedule|set up|plan|arrange)\s+(?:a\s+)?(?:meeting|sync|call|chat)",
    ]

    _TEMPORAL_ALIASES = {
        "today": (0, "day"),
        "tonight": (0, "day"),
        "tomorrow": (1, "day"),
        "this week": (0, "week"),
        "next week": (1, "week"),
        "this weekend": (0, "week"),
    }

    def _parse_timeframe(self, text: str) -> Optional[Tuple[int, str]]:
        """Try to extract a relative timeframe from text. Returns (amount, unit) or None."""
        text_lower = text.lower()
        # Check aliases
        for alias, (amt, unit) in self._TEMPORAL_ALIASES.items():
            if alias in text_lower:
                return (amt, unit)

        # "in X hours/days/weeks"
        import re
        m = re.search(r"in\s+(\d+)\s+(hour|day|week|minute)s?", text_lower)
        if m:
            return (int(m.group(1)), m.group(2))

        # Day-of-week mentions
        day_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        today_idx = datetime.now().weekday()
        for i, name in enumerate(day_names):
            if name in text_lower:
                days_ahead = (i - today_idx) % 7
                if days_ahead == 0:
                    days_ahead = 7  # next week
                return (days_ahead, "day")

        return None

    def infer_intentions(
        self,
        text: str,
        author_id: str = "",
        source_channel: str = "",
    ) -> List[Dict[str, Any]]:
        """
        Parse natural language text for commitments and create intentions.

        Detects patterns like:
          - "I'll finish authentication tomorrow."
          - "I will deploy tonight."
          - "Let me review the PR."
          - "I'm going to write documentation this week."

        Args:
            text: The user's message text
            author_id: Discord user ID who made the commitment
            source_channel: Discord channel/thread ID

        Returns:
            List of created intention dicts
        """
        import re

        results: List[Dict[str, Any]] = []
        text_clean = text.strip()

        # Try each commitment pattern
        for pattern, group_idx in self._COMMITMENT_PATTERNS:
            for m in re.finditer(pattern, text_clean, re.IGNORECASE):
                description = m.group(group_idx).strip().rstrip(".,!?")
                if not description or len(description) < 3:
                    continue

                # Try to extract deadline
                hours = 24
                timeframe = self._parse_timeframe(text_clean)
                if timeframe:
                    amount, unit = timeframe
                    if unit == "day":
                        hours = amount * 24
                    elif unit == "week":
                        hours = amount * 24 * 7
                    elif unit == "hour":
                        hours = amount
                    elif unit == "minute":
                        hours = max(1, amount // 60)

                # Create the intention via the runtime
                # Tag with the author so we know who committed
                intention = self.intention(
                    description=description,
                    priority="medium",
                    hours=hours,
                    metadata={
                        "author_id": author_id,
                        "source_channel": source_channel,
                        "source_text": text_clean,
                        "inferred": True,
                    },
                )

                # Record timeline event
                self.record_event(
                    event_type="milestone",
                    title=f"Intention created: {description[:60]}",
                    description=f"{author_id} committed to: {description}",
                    significance=2,
                )

                results.append(intention)
                return results  # One intention per message

        return results

    def infer_meetings(
        self,
        text: str,
        author_id: str = "",
        source_channel: str = "",
    ) -> List[Dict[str, Any]]:
        """
        Parse natural language text for meeting proposals and record them.

        Detects patterns like:
          - "Let's meet Friday at 7."
          - "We should sync tomorrow."
          - "Can we schedule a meeting?"

        Args:
            text: The user's message text
            author_id: Discord user ID who proposed the meeting
            source_channel: Discord channel/thread ID

        Returns:
            List of created meeting event dicts
        """
        import re

        results: List[Dict[str, Any]] = []
        text_lower = text.lower()
        text_clean = text.strip()

        for pattern in self._MEETING_PATTERNS:
            if re.search(pattern, text_lower):
                # Extract proposed time
                timeframe = self._parse_timeframe(text)
                meeting_time = ""
                if timeframe:
                    amount, unit = timeframe
                    if unit == "day":
                        from datetime import timedelta
                        meeting_dt = datetime.now() + timedelta(days=amount)
                        meeting_time = meeting_dt.strftime("%A at 10:00 AM")
                    else:
                        meeting_time = f"{amount} {unit}(s) from now"
                else:
                    meeting_time = "proposed (no specific time detected)"

                title = f"Meeting proposed by {author_id}"
                description = text_clean[:200]

                # Record as timeline event
                event_id = self.record_event(
                    event_type="milestone",
                    title=title,
                    description=f"Proposed by {author_id}. Time: {meeting_time}. Context: {description}",
                    significance=3,
                )

                # Store meeting info as a memory
                self.remember(
                    content=f"Meeting: {text_clean[:200]} | Proposed by: {author_id} | Time: {meeting_time}",
                    tags=["meeting", "scheduled"],
                )

                results.append({
                    "event_id": event_id,
                    "title": title,
                    "proposed_by": author_id,
                    "proposed_time": meeting_time,
                    "source_text": text_clean[:200],
                })
                break

        return results

    def reminders(self, max_results: int = 20) -> List[Dict[str, Any]]:
        """
        Get chronological list of intentions that are:
          - Due soon (within next 4 hours)
          - Overdue (past deadline)
          - Expiring today

        Returns sorted list with human-readable status labels.
        """
        from datetime import datetime, timezone

        intentions = self._runtime.intention_engine.all()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        results: List[Dict[str, Any]] = []

        for i in intentions:
            if i.status.value != "active":
                continue
            if not i.expires_at:
                continue

            expires = i.expires_at
            if isinstance(expires, str):
                from datetime import datetime as dt
                expires = dt.fromisoformat(expires)

            remaining = (expires - now).total_seconds()
            hours_left = remaining / 3600

            label = "on_track"
            urgency = 0
            if remaining <= 0:
                label = "overdue"
                urgency = 5
            elif hours_left <= 1:
                label = "due_soon"
                urgency = 4
            elif hours_left <= 4:
                label = "approaching"
                urgency = 3
            elif hours_left <= 24:
                label = "due_today"
                urgency = 2
            elif hours_left <= 48:
                label = "due_tomorrow"
                urgency = 1

            results.append({
                "id": i.id,
                "description": i.description,
                "author_id": i.metadata.get("author_id", "unknown") if hasattr(i, "metadata") and i.metadata else "",
                "label": label,
                "urgency": urgency,
                "hours_left": round(hours_left, 1),
                "expires_at": expires.isoformat() if hasattr(expires, "isoformat") else str(expires),
                "created_at": i.created_at.isoformat() if i.created_at else "",
            })

        results.sort(key=lambda r: (-r["urgency"], r["hours_left"]))
        return results[:max_results]

    def team_status(self) -> Dict[str, Any]:
        """
        Generate a structured summary of what the team is working on.

        Aggregates:
          - Active goals
          - Active intentions (grouped by author)
          - Upcoming meetings from timeline
          - Recent timeline events
          - Relationship changes

        Returns a dict suitable for rendering as a status update.
        """
        active_goals = self._runtime.goal_engine.active()
        active_intentions = self._runtime.intention_engine.active()
        timeline = self._runtime.timeline_registry.get(self._identity_id)
        relationships = self._runtime.identity_graph.get_relationships(self._identity_id)

        # Group intentions by author
        by_author: Dict[str, List[Dict[str, Any]]] = {}
        for i in active_intentions:
            author = i.metadata.get("author_id", "unknown") if hasattr(i, "metadata") and i.metadata else "unknown"
            if author not in by_author:
                by_author[author] = []
            by_author[author].append({
                "id": i.id,
                "description": i.description,
                "priority": i.priority.name if hasattr(i.priority, "name") else str(i.priority),
                "expires_at": i.expires_at.isoformat() if i.expires_at else "",
            })

        # Upcoming meetings from timeline (last 30 days, high significance)
        upcoming: List[Dict[str, Any]] = []
        if timeline:
            for e in timeline.events():
                if "Meeting" in e.title or "meeting" in e.title or e.significance >= 3:
                    upcoming.append({
                        "id": e.id,
                        "title": e.title,
                        "significance": e.significance,
                        "occurred_at": e.occurred_at.isoformat() if e.occurred_at else "",
                    })

        # Relationship summary
        rel_summary: List[Dict[str, Any]] = []
        for r in relationships:
            tl = r.trust_level.value if hasattr(r.trust_level, "value") else r.trust_level
            rel_summary.append({
                "entity_id": r.target_id,
                "edge_type": r.edge_type.value if hasattr(r.edge_type, "value") else str(r.edge_type),
                "trust_level": tl,
            })

        # Recent timeline events (last 7 days)
        recent_events: List[Dict[str, Any]] = []
        if timeline:
            from datetime import timedelta, timezone
            week_ago = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=7)
            for e in timeline.events():
                occurred = e.occurred_at
                if isinstance(occurred, str):
                    occurred = datetime.fromisoformat(occurred)
                if hasattr(occurred, "tzinfo"):
                    occurred = occurred.replace(tzinfo=None)
                if occurred >= week_ago:
                    recent_events.append({
                        "id": e.id,
                        "title": e.title,
                        "event_type": e.event_type.value if hasattr(e.event_type, "value") else str(e.event_type),
                        "significance": e.significance,
                        "occurred_at": occurred.isoformat() if hasattr(occurred, "isoformat") else str(occurred),
                    })

        return {
            "goals": [self._goal_to_dict(g) for g in active_goals],
            "intentions_by_author": by_author,
            "total_active_intentions": len(active_intentions),
            "upcoming_meetings": upcoming,
            "relationships": rel_summary,
            "recent_events": recent_events[-10:],
        }

    def digest(
        self,
        period: str = "daily",
    ) -> Dict[str, Any]:
        """
        Generate a formatted digest of identity activity.

        Args:
            period: "daily" or "weekly"

        Returns:
            Dict with sections: summary, goals, intentions, meetings,
                                timeline, relationships, evidence_highlights
        """
        from datetime import timedelta, timezone, datetime

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        if period == "weekly":
            cutoff = now - timedelta(days=7)
            period_label = "Weekly"
        else:
            cutoff = now - timedelta(days=1)
            period_label = "Daily"

        status = self.team_status()
        timeline = self._runtime.timeline_registry.get(self._identity_id)

        # Filter events since cutoff
        digest_events: List[Dict[str, Any]] = []
        if timeline:
            for e in timeline.events():
                occurred = e.occurred_at
                if isinstance(occurred, str):
                    occurred = datetime.fromisoformat(occurred)
                if hasattr(occurred, "tzinfo"):
                    occurred = occurred.replace(tzinfo=None)
                if occurred >= cutoff:
                    digest_events.append({
                        "id": e.id,
                        "title": e.title,
                        "event_type": e.event_type.value if hasattr(e.event_type, "value") else str(e.event_type),
                        "significance": e.significance,
                        "occurred_at": occurred.isoformat() if hasattr(occurred, "isoformat") else str(occurred),
                    })

        # Count completed goals and intentions
        completed_count = 0
        all_goals = self._runtime.goal_engine.all()
        for g in all_goals:
            if hasattr(g, "completed_at") and g.completed_at:
                completed_at = g.completed_at
                if isinstance(completed_at, str):
                    completed_at = datetime.fromisoformat(completed_at)
                if hasattr(completed_at, "tzinfo"):
                    completed_at = completed_at.replace(tzinfo=None)
                if completed_at >= cutoff:
                    completed_count += 1

        # Relationship changes
        rel_changes: List[Dict[str, Any]] = []
        for r in status.get("relationships", []):
            if r.get("trust_level", 0) >= 3:
                rel_changes.append(r)

        # Pending reminders
        pending = self.reminders(max_results=10)

        digest = {
            "period": period,
            "label": f"{period_label} Digest",
            "generated_at": now.isoformat(),
            "summary": {
                "active_goals": len(status.get("goals", [])),
                "active_intentions": status.get("total_active_intentions", 0),
                "completed_items": completed_count,
                "pending_reminders": len(pending),
                "recent_events": len(digest_events),
                "relationships": len(status.get("relationships", [])),
            },
            "goals": status.get("goals", []),
            "intentions": status.get("intentions_by_author", {}),
            "pending_reminders": pending,
            "upcoming_meetings": status.get("upcoming_meetings", []),
            "recent_timeline_events": digest_events,
            "relationship_highlights": rel_changes,
        }

        return digest

    # ═══════════════════════════════════════════════════════════════════
    # Introspection
    # ═══════════════════════════════════════════════════════════════════

    def describe(self) -> Dict[str, Any]:
        """
        Return a detailed snapshot of this identity's current state.
        """
        spec = self._spec
        if not spec:
            return {"error": f"Identity '{self._identity_id}' not found"}

        active_goals = self._runtime.goal_engine.active()
        active_intentions = self._runtime.intention_engine.active()
        memory_count = len(self._runtime.memory_store.by_identity(self._identity_id))
        relationship_count = len(self._runtime.identity_graph.get_relationships(self._identity_id))
        timeline = self._runtime.timeline_registry.get(self._identity_id)
        timeline_count = len(timeline.events()) if timeline else 0

        return {
            "id": spec.id,
            "name": spec.name,
            "version": spec.version,
            "persona": spec.persona,
            "role": spec.role,
            "status": spec.status.value,
            "active_goals": len(active_goals),
            "active_intentions": len(active_intentions),
            "memories": memory_count,
            "relationships": relationship_count,
            "timeline_events": timeline_count,
            "created_at": spec.created_at.isoformat() if spec.created_at else "",
        }

    def __repr__(self) -> str:
        return f"Identity(name={self.name!r}, id={self._identity_id!r})"

    def __str__(self) -> str:
        return self.name
