from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set

# ---------------------------------------------------------------------------
# Identity Graph — a first-class subsystem
# ---------------------------------------------------------------------------
# Relationships should not live inside Identity.
# The Identity Graph deserves to be its own subsystem.
# Almost like Neo4j — queryable, traversable, alive.
#
# Think about what this enables:
#   Who does Maya trust?
#   Who influenced Maya?
#   Which identities know each other?
#   What is the path from Maya to the Chief?
#   Who in Maya's network has expertise in criminal law?
#
# None of that is possible when relationships are just a list
# attached to an identity object. It requires a graph.
# ---------------------------------------------------------------------------


class EdgeType(Enum):
    """The nature of the relationship between two identities."""
    PEER = "peer"
    MENTOR = "mentor"
    STUDENT = "student"
    COLLABORATOR = "collaborator"
    DELEGATE = "delegate"       # B acts on behalf of A
    PRINCIPAL = "principal"     # A acts on behalf of B
    REPORTS_TO = "reports_to"
    MANAGES = "manages"
    ADVERSARY = "adversary"
    OBSERVER = "observer"
    FAMILY = "family"
    FRIEND = "friend"


class TrustLevel(Enum):
    NONE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    ABSOLUTE = 4


@dataclass
class GraphEdge:
    """
    A directed, weighted edge between two identities in the graph.

    Direction matters: A MENTORS B is different from B MENTORS A.
    Bidirectional relationships are stored as two directed edges.

    The edge carries:
    - Type: what kind of relationship
    - Trust: how much the source trusts the target
    - Strength: 0.0–1.0, decays over time without interaction
    - Permissions: what the target is allowed to access on the source
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_id: str = ""       # Who holds this relationship
    target_id: str = ""       # Who it points to
    edge_type: EdgeType = EdgeType.PEER
    trust_level: TrustLevel = TrustLevel.MEDIUM
    strength: float = 1.0     # 0.0–1.0
    bidirectional: bool = False
    context: str = ""         # How this relationship started
    permissions: List[str] = field(default_factory=list)
    labels: List[str] = field(default_factory=list)
    established_at: datetime = field(default_factory=datetime.utcnow)
    last_interaction: Optional[datetime] = None
    interaction_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if isinstance(self.edge_type, str):
            self.edge_type = EdgeType(self.edge_type)
        if isinstance(self.trust_level, str):
            self.trust_level = TrustLevel[self.trust_level.upper()]
        elif isinstance(self.trust_level, int):
            self.trust_level = TrustLevel(self.trust_level)

    def interact(self) -> None:
        self.last_interaction = datetime.utcnow()
        self.interaction_count += 1
        self.reinforce()

    def reinforce(self, amount: float = 0.05) -> None:
        self.strength = min(1.0, self.strength + amount)

    def decay(self, factor: float = 0.95) -> None:
        self.strength = max(0.0, self.strength * factor)

    def trust_score(self) -> float:
        """Combined score: trust level * strength."""
        return (self.trust_level.value / 4.0) * self.strength


class IdentityGraph:
    """
    The Identity Graph — a first-class subsystem of IdentityOS.

    This is not a utility class inside Identity.
    This is a standalone graph database for identity relationships.

    Supports:
    - Adding/removing directed and bidirectional edges
    - Querying neighbors, trusted identities, mentors, students
    - Path finding between identities
    - Subgraph extraction
    - Influence mapping (who influenced who)
    - Trust-weighted queries

    This is what allows:
        graph.who_trusts("maya", min_trust=TrustLevel.HIGH)
        graph.shortest_path("maya", "chief_carter")
        graph.influenced_by("maya")
        graph.network_of("maya", depth=2)
    """

    def __init__(self):
        # source_id -> list of outgoing edges
        self._adjacency: Dict[str, List[GraphEdge]] = {}
        # edge_id -> edge, for direct lookup
        self._edges: Dict[str, GraphEdge] = {}

    # ------------------------------------------------------------------
    # Edge Management
    # ------------------------------------------------------------------

    def connect(
        self,
        source_id: str,
        target_id: str,
        edge_type: EdgeType = EdgeType.PEER,
        trust_level: TrustLevel = TrustLevel.MEDIUM,
        bidirectional: bool = False,
        **kwargs
    ) -> GraphEdge:
        """Create a directed edge from source to target."""
        edge = GraphEdge(
            source_id=source_id,
            target_id=target_id,
            edge_type=edge_type,
            trust_level=trust_level,
            bidirectional=bidirectional,
            **kwargs
        )
        self._add_edge(edge)

        if bidirectional:
            reverse = GraphEdge(
                source_id=target_id,
                target_id=source_id,
                edge_type=edge_type,
                trust_level=trust_level,
                bidirectional=True,
                **kwargs
            )
            self._add_edge(reverse)

        return edge

    def _add_edge(self, edge: GraphEdge) -> None:
        if edge.source_id not in self._adjacency:
            self._adjacency[edge.source_id] = []
        self._adjacency[edge.source_id].append(edge)
        self._edges[edge.id] = edge

    def disconnect(self, source_id: str, target_id: str) -> bool:
        """Remove the directed edge from source to target."""
        edges = self._adjacency.get(source_id, [])
        removed = [e for e in edges if e.target_id == target_id]
        if not removed:
            return False
        self._adjacency[source_id] = [e for e in edges if e.target_id != target_id]
        for e in removed:
            self._edges.pop(e.id, None)
        return True

    def get_edge(self, source_id: str, target_id: str) -> Optional[GraphEdge]:
        for edge in self._adjacency.get(source_id, []):
            if edge.target_id == target_id:
                return edge
        return None

    def interact(self, source_id: str, target_id: str) -> None:
        """Record an interaction between two identities."""
        edge = self.get_edge(source_id, target_id)
        if edge:
            edge.interact()

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_relationships(self, identity_id: str) -> List[GraphEdge]:
        """Alias for edges_from — all outgoing relationships from an identity."""
        return self.edges_from(identity_id)

    def get_relationship(
        self, source_id: str, target_id: str
    ) -> Optional[GraphEdge]:
        """Alias for get_edge."""
        return self.get_edge(source_id, target_id)

    def get_trusted(
        self, source_id: str, min_trust: "TrustLevel" = TrustLevel.MEDIUM
    ) -> List[GraphEdge]:
        """All outgoing relationships meeting a minimum trust threshold."""
        return [
            e for e in self._adjacency.get(source_id, [])
            if e.trust_level.value >= min_trust.value
        ]

    def record_interaction(self, source_id: str, target_id: str) -> None:
        """Alias for interact."""
        self.interact(source_id, target_id)

    def remove_relationship(self, source_id: str, target_id: str) -> bool:
        """Alias for disconnect."""
        return self.disconnect(source_id, target_id)

    def neighbors(self, identity_id: str) -> List[str]:
        """All identity IDs this identity has outgoing relationships to."""
        return [e.target_id for e in self._adjacency.get(identity_id, [])]

    def edges_from(self, identity_id: str) -> List[GraphEdge]:
        return list(self._adjacency.get(identity_id, []))

    def edges_to(self, target_id: str) -> List[GraphEdge]:
        """All edges pointing AT a given identity."""
        return [e for edges in self._adjacency.values() for e in edges if e.target_id == target_id]

    def who_trusts(
        self, identity_id: str, min_trust: TrustLevel = TrustLevel.MEDIUM
    ) -> List[str]:
        """Return identity IDs that trust this identity at or above min_trust."""
        return [
            e.source_id for e in self.edges_to(identity_id)
            if e.trust_level.value >= min_trust.value
        ]

    def trusted_by(
        self, identity_id: str, min_trust: TrustLevel = TrustLevel.MEDIUM
    ) -> List[str]:
        """Return identities that this identity trusts."""
        return [
            e.target_id for e in self._adjacency.get(identity_id, [])
            if e.trust_level.value >= min_trust.value
        ]

    def mentors_of(self, identity_id: str) -> List[str]:
        """Who mentors this identity?"""
        return [
            e.source_id for e in self.edges_to(identity_id)
            if e.edge_type == EdgeType.MENTOR
        ]

    def students_of(self, identity_id: str) -> List[str]:
        """Who does this identity mentor?"""
        return [
            e.target_id for e in self._adjacency.get(identity_id, [])
            if e.edge_type == EdgeType.MENTOR
        ]

    def influenced_by(self, identity_id: str) -> List[GraphEdge]:
        """All inbound relationships — who has shaped this identity."""
        return self.edges_to(identity_id)

    def network_of(
        self, identity_id: str, depth: int = 2
    ) -> Dict[str, List[str]]:
        """
        BFS expansion of the network up to `depth` hops.
        Returns adjacency map of discovered identity IDs.
        """
        visited: Set[str] = set()
        queue = [(identity_id, 0)]
        result: Dict[str, List[str]] = {}

        while queue:
            current, level = queue.pop(0)
            if current in visited or level > depth:
                continue
            visited.add(current)
            neighbors = self.neighbors(current)
            result[current] = neighbors
            for neighbor in neighbors:
                if neighbor not in visited:
                    queue.append((neighbor, level + 1))

        return result

    def shortest_path(
        self, source_id: str, target_id: str
    ) -> Optional[List[str]]:
        """
        BFS shortest path between two identities.
        Returns the list of identity IDs from source to target,
        or None if no path exists.
        """
        if source_id == target_id:
            return [source_id]

        visited: Set[str] = {source_id}
        queue: List[List[str]] = [[source_id]]

        while queue:
            path = queue.pop(0)
            current = path[-1]
            for neighbor in self.neighbors(current):
                if neighbor == target_id:
                    return path + [neighbor]
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(path + [neighbor])

        return None

    def all_identities(self) -> List[str]:
        ids: Set[str] = set(self._adjacency.keys())
        for edges in self._adjacency.values():
            for e in edges:
                ids.add(e.target_id)
        return list(ids)

    def to_adjacency_summary(self) -> Dict[str, List[str]]:
        return {
            src: [e.target_id for e in edges]
            for src, edges in self._adjacency.items()
        }

    def to_prompt_block(
        self, identity_id: str, min_trust: TrustLevel = TrustLevel.LOW
    ) -> str:
        """Render the relationship context for the Cognitive Engine."""
        edges = [
            e for e in self._adjacency.get(identity_id, [])
            if e.trust_level.value >= min_trust.value
        ]
        if not edges:
            return ""
        lines = ["## Relationships"]
        for e in sorted(edges, key=lambda x: -x.trust_score()):
            stars = "\u2605" * e.trust_level.value + "\u2606" * (4 - e.trust_level.value)
            lines.append(
                f"  {e.target_id} [{e.edge_type.value}] {stars} "
                f"strength={e.strength:.2f}"
            )
        return "\n".join(lines)

    def __len__(self) -> int:
        return len(self._edges)
