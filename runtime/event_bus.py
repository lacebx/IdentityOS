from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

# ---------------------------------------------------------------------------
# Event Bus — the path toward a truly reactive IdentityOS
# ---------------------------------------------------------------------------
# The current orchestrator is linear:
#   Resolve → Policy → Context → Adapter → Policy → Evaluate → Memory
#
# That works for an MVP. But as identities grow more sophisticated,
# this linear pipe becomes a bottleneck.
#
# The event-driven model lets each subsystem react independently:
#
#   User Message
#         │
#         ▼
#   Event Bus
#         │
#  ┌─────┼────────┬─────────┐
#  ▼      ▼         ▼          ▼
# Goals  Memory  Policies  Relationships
#  │      │         │          │
#  └─────┼────────┘─────────┘
#         ▼
#  Cognitive Engine
#         ▼
#   Adapter
#         ▼
#  Response Events
#
# This file establishes the Event Bus infrastructure.
# Modules subscribe to event types and react independently.
# The Runtime publishes events and collects reactions.
# ---------------------------------------------------------------------------


class EventType(Enum):
    # Lifecycle
    IDENTITY_LOADED = "identity.loaded"
    IDENTITY_UNLOADED = "identity.unloaded"
    SESSION_STARTED = "session.started"
    SESSION_ENDED = "session.ended"

    # Interaction
    MESSAGE_RECEIVED = "message.received"     # Raw user input arrived
    MESSAGE_SANITIZED = "message.sanitized"   # After input policy
    CONTEXT_COMPOSED = "context.composed"     # Cognitive engine finished
    MODEL_REQUESTED = "model.requested"       # Adapter call initiated
    MODEL_RESPONDED = "model.responded"       # Adapter call completed
    RESPONSE_GENERATED = "response.generated" # Adapter returned output
    RESPONSE_DELIVERED = "response.delivered" # After output policy, sent

    # Memory / Experience
    EXPERIENCE_RECORDED = "experience.recorded"
    MEMORY_RETRIEVED = "memory.retrieved"

    # Goals / Motivations
    GOAL_ADDED = "goal.added"
    GOAL_COMPLETED = "goal.completed"
    GOAL_BLOCKED = "goal.blocked"
    MOTIVATION_EXPRESSED = "motivation.expressed"

    # Relationships
    RELATIONSHIP_FORMED = "relationship.formed"
    RELATIONSHIP_INTERACTED = "relationship.interacted"
    RELATIONSHIP_DECAYED = "relationship.decayed"

    # Knowledge / Skills
    KNOWLEDGE_LOADED = "knowledge.loaded"
    SKILL_INVOKED = "skill.invoked"
    SKILL_FAILED = "skill.failed"

    # Evaluation / Evolution
    EVALUATION_COMPLETED = "evaluation.completed"
    IDENTITY_EVOLVED = "identity.evolved"
    IDENTITY_MUTATION_PROPOSED = "identity.mutation_proposed"
    IDENTITY_MUTATION_ACCEPTED = "identity.mutation_accepted"
    IDENTITY_MUTATION_REJECTED = "identity.mutation_rejected"
    IDENTITY_MUTATION_CONFLICT = "identity.mutation_conflict"

    # Policy
    POLICY_TRIGGERED = "policy.triggered"
    POLICY_BLOCKED = "policy.blocked"

    # Timeline
    LIFE_EVENT_RECORDED = "timeline.life_event"

    # Custom
    CUSTOM = "custom"


@dataclass
class Event:
    """
    A single event in the IdentityOS event stream.

    Events are the unit of communication between subsystems.
    Every significant thing that happens is an event.
    Subsystems don't call each other — they publish and react.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: EventType = EventType.CUSTOM
    source: str = ""           # Which subsystem emitted this
    identity_id: Optional[str] = None
    session_id: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __repr__(self) -> str:
        return (
            f"Event(type={self.event_type.value!r}, "
            f"source={self.source!r}, "
            f"identity={self.identity_id!r})"
        )


# Type alias for event handlers
EventHandler = Callable[[Event], None]


class EventBus:
    """
    The IdentityOS Event Bus.

    The EventBus is a publish-subscribe system that decouples subsystems.
    Instead of the orchestrator calling each module directly (linear),
    each module subscribes to events it cares about and reacts.

    Current mode: synchronous (handlers called immediately).
    Future mode: async, allowing parallel subsystem reactions.

    Usage:
        bus = EventBus()

        # Subscribe
        bus.subscribe(EventType.MESSAGE_RECEIVED, memory_module.on_message)
        bus.subscribe(EventType.MESSAGE_RECEIVED, goal_engine.on_message)

        # Publish
        bus.publish(Event(
            event_type=EventType.MESSAGE_RECEIVED,
            source="orchestrator",
            identity_id=identity.id,
            payload={"content": user_input}
        ))
        # Both handlers called in subscription order
    """

    def __init__(self):
        self._handlers: Dict[EventType, List[EventHandler]] = defaultdict(list)
        self._wildcard_handlers: List[EventHandler] = []
        self._history: List[Event] = []
        self._max_history: int = 1000

    def subscribe(
        self,
        event_type: EventType,
        handler: EventHandler
    ) -> None:
        """Register a handler for a specific event type."""
        self._handlers[event_type].append(handler)

    def subscribe_all(self, handler: EventHandler) -> None:
        """Register a handler that receives ALL events."""
        self._wildcard_handlers.append(handler)

    def unsubscribe(
        self,
        event_type: EventType,
        handler: EventHandler
    ) -> bool:
        """Remove a handler for a specific event type."""
        handlers = self._handlers.get(event_type, [])
        if handler in handlers:
            handlers.remove(handler)
            return True
        return False

    def publish(self, event: Event) -> int:
        """
        Publish an event to all registered handlers.
        Returns the number of handlers invoked.
        """
        # Store in history
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

        count = 0
        # Type-specific handlers
        for handler in self._handlers.get(event.event_type, []):
            try:
                handler(event)
                count += 1
            except Exception:
                # Handlers should not crash the bus
                pass

        # Wildcard handlers
        for handler in self._wildcard_handlers:
            try:
                handler(event)
                count += 1
            except Exception:
                pass

        return count

    def emit(
        self,
        event_type: EventType,
        source: str,
        identity_id: Optional[str] = None,
        session_id: Optional[str] = None,
        **payload
    ) -> Event:
        """
        Convenience method: create and publish an event in one call.

        Usage:
            bus.emit(
                EventType.GOAL_COMPLETED,
                source="goal_engine",
                identity_id=identity.id,
                goal_title="Finish report"
            )
        """
        event = Event(
            event_type=event_type,
            source=source,
            identity_id=identity_id,
            session_id=session_id,
            payload=payload,
        )
        self.publish(event)
        return event

    def history(
        self,
        event_type: Optional[EventType] = None,
        identity_id: Optional[str] = None,
        limit: int = 50
    ) -> List[Event]:
        """Query recent event history with optional filters."""
        events = self._history
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        if identity_id:
            events = [e for e in events if e.identity_id == identity_id]
        return events[-limit:]

    def clear_history(self) -> None:
        self._history.clear()

    def handler_count(self, event_type: Optional[EventType] = None) -> int:
        if event_type:
            return len(self._handlers.get(event_type, []))
        return sum(len(h) for h in self._handlers.values()) + len(self._wildcard_handlers)

    def __repr__(self) -> str:
        return (
            f"EventBus("
            f"subscriptions={self.handler_count()}, "
            f"history={len(self._history)}"
            f")"
        )


# ---------------------------------------------------------------------------
# Mixin for subsystems that want to react to events
# ---------------------------------------------------------------------------

class EventAware:
    """
    Mixin for any subsystem that wants to subscribe to events.

    Usage:
        class GoalEngine(EventAware):
            def on_message_received(self, event: Event) -> None:
                # check if user message affects active goals
                ...

            def register(self, bus: EventBus) -> None:
                bus.subscribe(EventType.MESSAGE_RECEIVED, self.on_message_received)
                bus.subscribe(EventType.EVALUATION_COMPLETED, self.on_evaluation)
    """

    def register(self, bus: EventBus) -> None:
        """
        Register this subsystem's handlers on the event bus.
        Subclasses override this method.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement register(bus)"
        )
