"""
core/evidence_graph.py

Evidence Graph — connects every stable identity fact to its origins.

Every identity fact knows why it exists:
  favorite_color → blue
    ↓
  Evidence: conversation #14
    ↓
  Reason: calmness, trust, stability
    ↓
  Confidence: 96%
    ↓
  Contradictions: 0

This graph replaces flat belief storage with inspectable provenance.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class EvidenceType(str, Enum):
    CONVERSATION = "conversation"
    EVALUATION = "evaluation"
    USER_STATEMENT = "user_statement"
    ASSISTANT_STATEMENT = "assistant_statement"
    CREATOR_DEFINED = "creator_defined"
    RUNTIME_INFERRED = "runtime_inferred"
    POLICY_CHECK = "policy_check"


@dataclass
class EvidenceNode:
    """
    A node in the evidence graph representing a piece of evidence.
    Can be a conversation turn, an evaluation result, a user statement, etc.
    """

    evidence_id: str
    evidence_type: EvidenceType
    description: str
    source_text: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "evidence_type": self.evidence_type.value,
            "description": self.description,
            "source_text": self.source_text,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvidenceNode":
        return cls(
            evidence_id=data.get("evidence_id", str(uuid.uuid4())),
            evidence_type=EvidenceType(data.get("evidence_type", "conversation")),
            description=data.get("description", ""),
            source_text=data.get("source_text", ""),
            timestamp=data.get("timestamp", datetime.now(timezone.utc).isoformat()),
            metadata=data.get("metadata", {}),
        )


@dataclass
class EvidenceEdge:
    """
    A directed edge connecting a fact to its evidence.
    fact_id → evidence_id
    """

    edge_id: str
    fact_id: str
    evidence_id: str
    relationship: str = "supported_by"  # "supported_by", "contradicted_by", "inferred_from"
    weight: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "edge_id": self.edge_id,
            "fact_id": self.fact_id,
            "evidence_id": self.evidence_id,
            "relationship": self.relationship,
            "weight": self.weight,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvidenceEdge":
        return cls(
            edge_id=data.get("edge_id", str(uuid.uuid4())),
            fact_id=data["fact_id"],
            evidence_id=data["evidence_id"],
            relationship=data.get("relationship", "supported_by"),
            weight=data.get("weight", 1.0),
        )


class EvidenceGraph:
    """
    The full evidence graph for an identity.

    Maintains:
    - Evidence nodes (conversations, evaluations, etc.)
    - Edges connecting identity facts to their evidence
    - Query methods for traceability
    """

    def __init__(self) -> None:
        self._nodes: Dict[str, EvidenceNode] = {}
        self._edges: Dict[str, EvidenceEdge] = {}

    def add_node(self, node: EvidenceNode) -> None:
        self._nodes[node.evidence_id] = node

    def get_node(self, evidence_id: str) -> Optional[EvidenceNode]:
        return self._nodes.get(evidence_id)

    def add_edge(self, edge: EvidenceEdge) -> None:
        self._edges[edge.edge_id] = edge

    def connect(self, fact_id: str, evidence_id: str,
                relationship: str = "supported_by", weight: float = 1.0) -> EvidenceEdge:
        edge = EvidenceEdge(
            edge_id=str(uuid.uuid4()),
            fact_id=fact_id,
            evidence_id=evidence_id,
            relationship=relationship,
            weight=weight,
        )
        self._edges[edge.edge_id] = edge
        return edge

    def evidence_for(self, fact_id: str) -> List[EvidenceNode]:
        """Get all evidence supporting a given fact."""
        evidence_ids = [
            e.evidence_id for e in self._edges.values()
            if e.fact_id == fact_id and e.relationship == "supported_by"
        ]
        return [self._nodes[eid] for eid in evidence_ids if eid in self._nodes]

    def facts_for(self, evidence_id: str) -> List[str]:
        """Get all fact IDs connected to a piece of evidence."""
        return [
            e.fact_id for e in self._edges.values()
            if e.evidence_id == evidence_id
        ]

    def provenance(self, fact_id: str) -> Dict[str, Any]:
        """
        Get full provenance for a fact:
        - All evidence nodes
        - All edges
        - Summary of how many evidence items, types, etc.
        """
        nodes = self.evidence_for(fact_id)
        edges = [e for e in self._edges.values() if e.fact_id == fact_id]
        return {
            "fact_id": fact_id,
            "evidence_count": len(nodes),
            "evidence": [n.to_dict() for n in nodes],
            "edges": [e.to_dict() for e in edges],
            "evidence_types": list(set(n.evidence_type.value for n in nodes)),
        }

    def add_conversation_evidence(
        self, fact_id: str, conversation_text: str,
        description: str = "", metadata: Optional[Dict] = None
    ) -> EvidenceNode:
        """Convenience: create a conversation evidence node and link it to a fact."""
        node = EvidenceNode(
            evidence_id=str(uuid.uuid4()),
            evidence_type=EvidenceType.CONVERSATION,
            description=description or conversation_text[:80],
            source_text=conversation_text,
            metadata=metadata or {},
        )
        self.add_node(node)
        self.connect(fact_id, node.evidence_id)
        return node

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nodes": [n.to_dict() for n in self._nodes.values()],
            "edges": [e.to_dict() for e in self._edges.values()],
        }

    def to_dict_list(self) -> Dict[str, List[Dict[str, Any]]]:
        return self.to_dict()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvidenceGraph":
        graph = cls()
        for nd in data.get("nodes", []):
            graph.add_node(EvidenceNode.from_dict(nd))
        for ed in data.get("edges", []):
            graph.add_edge(EvidenceEdge.from_dict(ed))
        return graph

    def __len__(self) -> int:
        return len(self._nodes)
