"""Tests for core.cognitive_engine module."""

from core.cognitive_engine import ComposedContext, ContextComposer
from core.identity import IdentitySpec
from core.memory import MemoryFragment, MemoryStore, MemoryType
from core.relationships import IdentityGraph


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
