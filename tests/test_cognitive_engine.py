"""Tests for core.cognitive_engine module."""

from datetime import datetime, timedelta, timezone

from core.cognitive_engine import ComposedContext, ContextComposer
from core.identity import IdentitySpec
from core.memory import MemoryFragment, MemoryStore, MemoryType
from core.relationships import IdentityGraph
from core.timeline import IdentityTimeline, LifeEvent, LifeEventType, TimelineRegistry
from core.user_profile import UserProfile


class TestComposedContext:
    def test_render_empty(self):
        ctx = ComposedContext()
        assert ctx.render() == ""

    def test_render_with_content(self):
        ctx = ComposedContext(identity_block="I am Alice.", memory_block="You like coffee.")
        rendered = ctx.render()
        assert "I am Alice." in rendered
        assert "You like coffee." in rendered

    def test_token_estimate(self):
        ctx = ComposedContext(identity_block="hello world")
        assert ctx.token_estimate(1.0) == len("hello world")


class TestContextComposer:
    def test_compose_identity_only(self):
        composer = ContextComposer(
            include_memory=False,
            include_skills=False,
            include_goals=False,
            include_relationships=False,
        )
        identity = IdentitySpec(id="id1", name="TestBot", role="assistant")
        ctx = composer.compose(identity=identity)
        assert identity.name in ctx.identity_block
        assert ctx.memory_block == ""

    def test_compose_with_memory(self):
        composer = ContextComposer(include_skills=False, include_goals=False)
        identity = IdentitySpec(id="id2", name="MemBot")
        store = MemoryStore()
        store.add(MemoryFragment(
            identity_id="id2",
            content="User loves Python",
            memory_type=MemoryType.SEMANTIC,
        ))
        ctx = composer.compose(
            identity=identity,
            memory_store=store,
            query="Python",
        )
        assert "Python" in ctx.memory_block

    def test_compose_with_graph(self):
        composer = ContextComposer(
            include_memory=False,
            include_skills=False,
            include_goals=False,
            include_relationships=True,
        )
        identity = IdentitySpec(id="id3", name="RelBot")
        graph = IdentityGraph()
        from identity_graph.graph import TrustLevel
        graph.connect("id3", "user1", trust_level=TrustLevel.HIGH)
        ctx = composer.compose(identity=identity, identity_graph=graph)
        assert "user1" in ctx.relationships_block

    def test_runtime_directives_include_rule_11(self):
        composer = ContextComposer(
            include_memory=False,
            include_skills=False,
            include_goals=False,
            include_relationships=False,
        )
        identity = IdentitySpec(id="id4", name="ExecBot", role="assistant")
        ctx = composer.compose(identity=identity)
        directives = ctx.runtime_directives_block
        assert "NEVER SIMULATE TOOL CALLS" in directives
        assert "code fences" in directives
        assert "LONG-RUNNING WORK USES THE EXECUTIVE" in directives


class TestTimeAwareness:
    def _build(self):
        composer = ContextComposer(
            include_memory=False,
            include_skills=False,
            include_goals=False,
            include_relationships=False,
        )
        now = datetime.now(timezone.utc)
        created = now - timedelta(days=10)
        identity = IdentitySpec(id="tim1", name="TimeBot", role="assistant", created_at=created)
        registry = TimelineRegistry()
        timeline = registry.create("tim1", created_at=created)
        timeline.record(LifeEvent(
            identity_id="tim1",
            event_type=LifeEventType.MILESTONE,
            title="Interaction",
            description="User said: hi",
            occurred_at=now - timedelta(days=2),
            metadata={"session_id": "s1"},
        ))
        timeline.record(LifeEvent(
            identity_id="tim1",
            event_type=LifeEventType.MILESTONE,
            title="Interaction",
            description="User said: what's new",
            occurred_at=now - timedelta(hours=3),
            metadata={"session_id": "s2"},
        ))
        # Non-interaction event must NOT count as a user conversation
        timeline.record(LifeEvent(
            identity_id="tim1",
            event_type=LifeEventType.PREFERENCE_LEARNED,
            title="Preference Learned: favorite color",
            description="Assistant explicitly declared favorite color.",
            occurred_at=now - timedelta(hours=1),
            metadata={},
        ))
        return composer, identity, registry

    def test_last_user_conversation_from_user_events_only(self):
        composer, identity, registry = self._build()
        block = composer._render_time_awareness(identity=identity, timeline_registry=registry)
        assert "Most recent conversation with user: " in block
        assert "Time since last user message: 3h 0m ago" in block
        # The automated preference_learned event (1h ago) must not have been
        # treated as a user conversation.
        assert "Last interaction: 1 hour" not in block
        assert "Most recent conversation with user:" in block

    def test_no_user_events_guards_against_fabrication(self):
        composer = ContextComposer(
            include_memory=False, include_skills=False,
            include_goals=False, include_relationships=False,
        )
        registry = TimelineRegistry()
        registry.create("fresh")
        identity = IdentitySpec(id="fresh", name="FreshBot", role="assistant")
        block = composer._render_time_awareness(
            identity=identity, timeline_registry=registry,
        )
        assert "No recorded user interactions before this session" in block
        assert "never guess a date or time" in block

    def test_profile_fact_timestamp_not_labeled_interaction(self):
        composer = ContextComposer(
            include_memory=False, include_skills=False,
            include_goals=False, include_relationships=False,
        )
        now = datetime.now(timezone.utc)
        profile = UserProfile("u")
        profile.add_or_update("preferences.favorite_color", "blue",
                              "My favorite color is blue", 0.9)
        identity = IdentitySpec(id="tim3", name="Tim", role="assistant",
                                created_at=now - timedelta(days=1))
        block = composer._render_time_awareness(
            identity=identity, user_profile=profile,
        )
        # Regression: profile last_confirmed timestamps used to be reported as
        # "Last user interaction" — which produced the false "105h 41m ago"
        # answer. They must now be labeled as knowledge-learning only.
        assert "Last user interaction" not in block
        assert "Last interaction" not in block
        assert "First learned user knowledge on:" in block
