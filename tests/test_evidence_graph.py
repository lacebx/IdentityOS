"""Tests for core.evidence_graph module."""

from core.evidence_graph import (
    EvidenceGraph,
    EvidenceNode,
    EvidenceEdge,
    EvidenceType,
)
from core.confidence import ConfidenceScorer


class TestEvidenceNode:
    def test_creation(self):
        node = EvidenceNode(
            evidence_id="e1",
            evidence_type=EvidenceType.CONVERSATION,
            description="User said they like Python",
            source_text="User: I love Python",
        )
        assert node.evidence_id == "e1"
        assert node.evidence_type == EvidenceType.CONVERSATION
        assert node.description == "User said they like Python"
        assert node.source_text == "User: I love Python"

    def test_to_dict(self):
        node = EvidenceNode(
            evidence_id="e1",
            evidence_type=EvidenceType.EVALUATION,
            description="Test eval",
            source_text="Full eval text",
        )
        data = node.to_dict()
        assert data["evidence_id"] == "e1"
        assert data["evidence_type"] == "evaluation"
        assert data["description"] == "Test eval"
        assert data["source_text"] == "Full eval text"

    def test_from_dict(self):
        data = {
            "evidence_id": "e1",
            "evidence_type": "conversation",
            "description": "Test",
            "source_text": "Source",
            "timestamp": "2024-01-01T00:00:00",
            "metadata": {"key": "value"},
        }
        node = EvidenceNode.from_dict(data)
        assert node.evidence_id == "e1"
        assert node.evidence_type == EvidenceType.CONVERSATION
        assert node.description == "Test"
        assert node.source_text == "Source"
        assert node.metadata == {"key": "value"}


class TestEvidenceEdge:
    def test_creation(self):
        edge = EvidenceEdge(
            edge_id="edge1",
            fact_id="f1",
            evidence_id="e1",
            relationship="supported_by",
            weight=0.9,
        )
        assert edge.edge_id == "edge1"
        assert edge.fact_id == "f1"
        assert edge.evidence_id == "e1"
        assert edge.relationship == "supported_by"
        assert edge.weight == 0.9

    def test_to_dict(self):
        edge = EvidenceEdge(
            edge_id="edge1",
            fact_id="f1",
            evidence_id="e1",
        )
        data = edge.to_dict()
        assert data["edge_id"] == "edge1"
        assert data["fact_id"] == "f1"
        assert data["evidence_id"] == "e1"
        assert data["relationship"] == "supported_by"
        assert data["weight"] == 1.0

    def test_from_dict(self):
        data = {
            "edge_id": "edge1",
            "fact_id": "f1",
            "evidence_id": "e1",
            "relationship": "contradicted_by",
            "weight": 0.5,
        }
        edge = EvidenceEdge.from_dict(data)
        assert edge.edge_id == "edge1"
        assert edge.fact_id == "f1"
        assert edge.evidence_id == "e1"
        assert edge.relationship == "contradicted_by"
        assert edge.weight == 0.5


class TestEvidenceGraph:
    def test_add_node_and_get(self):
        graph = EvidenceGraph()
        node = EvidenceNode(
            evidence_id="e1",
            evidence_type=EvidenceType.CONVERSATION,
            description="Test",
        )
        graph.add_node(node)
        retrieved = graph.get_node("e1")
        assert retrieved is node

    def test_add_edge(self):
        graph = EvidenceGraph()
        edge = EvidenceEdge(
            edge_id="edge1",
            fact_id="f1",
            evidence_id="e1",
        )
        graph.add_edge(edge)
        assert "edge1" in graph._edges

    def test_connect(self):
        graph = EvidenceGraph()
        node = EvidenceNode(evidence_id="e1", evidence_type=EvidenceType.CONVERSATION, description="Test")
        graph.add_node(node)
        edge = graph.connect("f1", "e1", relationship="supported_by", weight=0.8)
        assert edge.fact_id == "f1"
        assert edge.evidence_id == "e1"
        assert edge.relationship == "supported_by"
        assert edge.weight == 0.8

    def test_evidence_for(self):
        graph = EvidenceGraph()
        node1 = EvidenceNode(evidence_id="e1", evidence_type=EvidenceType.CONVERSATION, description="Test1")
        node2 = EvidenceNode(evidence_id="e2", evidence_type=EvidenceType.EVALUATION, description="Test2")
        graph.add_node(node1)
        graph.add_node(node2)
        graph.connect("f1", "e1", relationship="supported_by")
        graph.connect("f1", "e2", relationship="supported_by")
        graph.connect("f1", "e1", relationship="contradicted_by")  # This should not appear in evidence_for
        evidence = graph.evidence_for("f1")
        assert len(evidence) == 2
        assert all(n.evidence_id in ["e1", "e2"] for n in evidence)

    def test_facts_for(self):
        graph = EvidenceGraph()
        node = EvidenceNode(evidence_id="e1", evidence_type=EvidenceType.CONVERSATION, description="Test")
        graph.add_node(node)
        graph.connect("f1", "e1")
        graph.connect("f2", "e1")
        facts = graph.facts_for("e1")
        assert set(facts) == {"f1", "f2"}

    def test_provenance(self):
        graph = EvidenceGraph()
        node = EvidenceNode(evidence_id="e1", evidence_type=EvidenceType.CONVERSATION, description="User likes Python", source_text="User: I love Python")
        graph.add_node(node)
        graph.connect("f1", "e1")
        prov = graph.provenance("f1")
        assert prov["fact_id"] == "f1"
        assert prov["evidence_count"] == 1
        assert "confidence" in prov
        assert "confidence_label" in prov
        assert len(prov["evidence"]) == 1
        assert prov["evidence"][0]["evidence_id"] == "e1"

    def test_confidence_for_no_evidence(self):
        graph = EvidenceGraph()
        conf = graph.confidence_for("nonexistent")
        assert conf == 0.65

    def test_confidence_for_with_evidence(self):
        graph = EvidenceGraph()
        node = EvidenceNode(evidence_id="e1", evidence_type=EvidenceType.CONVERSATION, description="User likes Python", source_text="User: I love Python")
        graph.add_node(node)
        graph.connect("f1", "e1")
        conf = graph.confidence_for("f1")
        assert 0.0 <= conf <= 1.0

    def test_add_conversation_evidence(self):
        graph = EvidenceGraph()
        node = graph.add_conversation_evidence("f1", "User: I love Python", description="User stated preference")
        assert node.evidence_id in graph._nodes
        assert node.evidence_type == EvidenceType.CONVERSATION
        assert node.source_text == "User: I love Python"
        evidence = graph.evidence_for("f1")
        assert len(evidence) == 1

    def test_to_dict(self):
        graph = EvidenceGraph()
        node = EvidenceNode(evidence_id="e1", evidence_type=EvidenceType.CONVERSATION, description="Test")
        graph.add_node(node)
        graph.connect("f1", "e1")
        data = graph.to_dict()
        assert len(data["nodes"]) == 1
        assert len(data["edges"]) == 1

    def test_from_dict(self):
        graph = EvidenceGraph()
        node = EvidenceNode(evidence_id="e1", evidence_type=EvidenceType.CONVERSATION, description="Test")
        graph.add_node(node)
        graph.connect("f1", "e1")
        data = graph.to_dict()
        new_graph = EvidenceGraph.from_dict(data)
        assert len(new_graph._nodes) == 1
        assert len(new_graph._edges) == 1
        assert new_graph.get_node("e1").description == "Test"

    def test_len(self):
        graph = EvidenceGraph()
        assert len(graph) == 0
        graph.add_node(EvidenceNode(evidence_id="e1", evidence_type=EvidenceType.CONVERSATION, description="Test"))
        assert len(graph) == 1