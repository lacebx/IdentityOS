"""Tests for identity_graph.graph and core.relationships."""

from core.relationships import IdentityGraph as CoreIdentityGraph
from identity_graph.graph import EdgeType, GraphEdge, IdentityGraph, TrustLevel


class TestIdentityGraph:
    def test_add_relationship(self):
        g = IdentityGraph()
        edge = g.connect("alice", "bob", edge_type=EdgeType.COLLABORATOR)
        assert edge.source_id == "alice"
        assert edge.target_id == "bob"
        assert edge.edge_type == EdgeType.COLLABORATOR

    def test_get_relationships(self):
        g = IdentityGraph()
        g.connect("alice", "bob")
        g.connect("alice", "charlie")
        rels = g.get_relationships("alice")
        assert len(rels) == 2

    def test_get_edge(self):
        g = IdentityGraph()
        g.connect("alice", "bob")
        edge = g.get_relationship("alice", "bob")
        assert edge is not None
        assert edge.target_id == "bob"

    def test_disconnect(self):
        g = IdentityGraph()
        g.connect("alice", "bob")
        assert g.remove_relationship("alice", "bob") is True
        assert g.get_relationship("alice", "bob") is None

    def test_interact(self):
        g = IdentityGraph()
        g.connect("alice", "bob", strength=0.5)
        old = g.get_relationship("alice", "bob").strength
        g.record_interaction("alice", "bob")
        assert g.get_relationship("alice", "bob").strength > old

    def test_get_trusted(self):
        g = IdentityGraph()
        g.connect("alice", "bob", trust_level=TrustLevel.HIGH)
        g.connect("alice", "charlie", trust_level=TrustLevel.LOW)
        trusted = g.get_trusted("alice", min_trust=TrustLevel.MEDIUM)
        assert len(trusted) == 1
        assert trusted[0].target_id == "bob"

    def test_core_relationships_re_exports(self):
        assert CoreIdentityGraph is IdentityGraph


class TestGraphEdge:
    def test_default_attributes(self):
        e = GraphEdge(source_id="a", target_id="b")
        assert e.edge_type == EdgeType.PEER
        assert e.trust_level == TrustLevel.MEDIUM
        assert e.strength == 1.0

    def test_interact_increases_strength(self):
        e = GraphEdge(source_id="a", target_id="b", strength=0.5)
        old = e.strength
        e.interact()
        assert e.strength > old
