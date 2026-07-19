"""
core/relationships.py

DEPRECATED: This module now re-exports from the canonical relationship graph at
identity_graph/graph.py.

The canonical Identity Graph lives at identity_graph/graph.py and provides:
- Directed, weighted edges with trust, decay, and permissions
- Path finding (shortest_path)
- BFS network expansion (network_of)
- Trust scoring and influence mapping
- Prompt block rendering for the cognitive engine

Use identity_graph.graph directly for new code.
"""

from identity_graph.graph import (
    EdgeType,
    GraphEdge,
    IdentityGraph,
    TrustLevel,
)

# Backward-compatible type aliases
RelationshipEdge = GraphEdge
RelationshipType = EdgeType

__all__ = [
    "IdentityGraph",
    "GraphEdge",
    "EdgeType",
    "TrustLevel",
    "RelationshipEdge",
    "RelationshipType",
]
