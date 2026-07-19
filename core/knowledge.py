"""
core/knowledge.py

The Knowledge module — WHAT an identity knows (facts, domain expertise).

Critically distinct from Memory:
  Memory   = personal experiences (time-indexed, first-person, ephemeral)
  Knowledge = transferable facts and domain expertise (time-independent, shareable)

Knowledge is organized into KnowledgePacks — independently loadable units,
like software packages. An identity loads KnowledgePacks the same way a program
imports libraries. You can give any identity a KnowledgePack without changing
who they are.

Example KnowledgePacks:
  - "medical-ethics-v2"
  - "python-best-practices-2025"
  - "organizational-psychology-intro"
  - "officer-maya-police-procedure"

An identity can load multiple packs, and packs can depend on each other.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set

# ─── Enums ────────────────────────────────────────────────────────────────────

class KnowledgeFormat(str, Enum):
    TEXT = "text"           # Plain text facts
    MARKDOWN = "markdown"   # Structured markdown documents
    QA = "qa"               # Q&A pairs (fine-tuning ready)
    CONCEPT_MAP = "concept_map"  # Structured concept relationships
    CODE = "code"           # Code examples and snippets
    STRUCTURED = "structured"  # JSON/YAML structured data


class KnowledgeTier(str, Enum):
    """
    How fundamental is this knowledge to the identity's function?
    CORE    = without this, the identity cannot operate (e.g. base language model)
    DOMAIN  = professional / domain expertise
    CONTEXT = situational knowledge loaded on demand
    TEMP    = temporary session knowledge
    """
    CORE = "core"
    DOMAIN = "domain"
    CONTEXT = "context"
    TEMP = "temp"


# ─── KnowledgeEntry ───────────────────────────────────────────────────────────

@dataclass
class KnowledgeEntry:
    """
    A single piece of knowledge within a KnowledgePack.
    Analogous to a MemoryFragment but time-independent and transferable.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    content: str = ""
    format: KnowledgeFormat = KnowledgeFormat.TEXT
    source_url: str = ""
    tags: List[str] = field(default_factory=list)
    confidence: float = 1.0         # How reliable is this knowledge
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "format": self.format.value,
            "source_url": self.source_url,
            "tags": self.tags,
            "confidence": self.confidence,
            "created_at": self.created_at.isoformat(),
            "extra": self.extra,
        }


# ─── KnowledgePack ────────────────────────────────────────────────────────────

@dataclass
class KnowledgePack:
    """
    A self-contained, named collection of knowledge entries.
    Think: a textbook, a domain guide, or a skill reference.

    KnowledgePacks are designed to be:
    - Composable: multiple packs load together
    - Portable: shareable between identities
    - Versioned: updated without changing the identity itself
    - Replaceable: swap "medical-ethics-v1" for "medical-ethics-v2"
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    version: str = "1.0.0"
    tier: KnowledgeTier = KnowledgeTier.DOMAIN
    author: str = ""

    # ── Content ──────────────────────────────────────────────────────────────
    entries: List[KnowledgeEntry] = field(default_factory=list)

    # ── Dependency resolution ─────────────────────────────────────────────────
    # IDs of other KnowledgePacks this pack requires
    depends_on: List[str] = field(default_factory=list)

    # ── Compatibility ─────────────────────────────────────────────────────────
    # Which identity classes can load this pack
    compatible_classes: List[str] = field(default_factory=list)

    # ── Metadata ─────────────────────────────────────────────────────────────
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    extra: Dict[str, Any] = field(default_factory=dict)

    # ── Token budget hint ─────────────────────────────────────────────────────
    # Approximate tokens this pack consumes in a context window
    estimated_tokens: int = 0

    def add_entry(self, content: str, title: str = "", **kwargs: Any) -> KnowledgeEntry:
        entry = KnowledgeEntry(title=title, content=content, **kwargs)
        self.entries.append(entry)
        self.updated_at = datetime.now(timezone.utc)
        return entry

    def search(self, query: str) -> List[KnowledgeEntry]:
        """
        Naive keyword search over entries.
        The Runtime's KnowledgeEngine replaces this with semantic search.
        """
        q = query.lower()
        return [
            e for e in self.entries
            if q in e.content.lower() or q in e.title.lower() or any(q in t for t in e.tags)
        ]

    def to_context_string(self, max_entries: Optional[int] = None) -> str:
        """
        Render the pack as a plain-text string suitable for context injection.
        The ContextComposer calls this when building the prompt.
        """
        entries = self.entries[:max_entries] if max_entries else self.entries
        lines = [f"## Knowledge Pack: {self.name} (v{self.version})"]
        if self.description:
            lines.append(self.description)
        lines.append("")
        for e in entries:
            if e.title:
                lines.append(f"### {e.title}")
            lines.append(e.content)
            lines.append("")
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "tier": self.tier.value,
            "author": self.author,
            "entries": [e.to_dict() for e in self.entries],
            "depends_on": self.depends_on,
            "compatible_classes": self.compatible_classes,
            "tags": self.tags,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "estimated_tokens": self.estimated_tokens,
            "extra": self.extra,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KnowledgePack":
        entries = [KnowledgeEntry(**e) for e in data.get("entries", [])]
        pack = cls(
            id=data.get("id", str(uuid.uuid4())),
            name=data.get("name", ""),
            description=data.get("description", ""),
            version=data.get("version", "1.0.0"),
            tier=KnowledgeTier(data.get("tier", "domain")),
            author=data.get("author", ""),
            entries=entries,
            depends_on=data.get("depends_on", []),
            compatible_classes=data.get("compatible_classes", []),
            tags=data.get("tags", []),
            estimated_tokens=data.get("estimated_tokens", 0),
            extra=data.get("extra", {}),
        )
        return pack


# ─── KnowledgeRegistry ────────────────────────────────────────────────────────

class KnowledgeRegistry:
    """
    Registry of all available KnowledgePacks.
    An identity looks up and loads packs by ID from this registry.

    In production, this is backed by a database or filesystem store.
    The Runtime manages the registry; this class is the domain interface.
    """

    def __init__(self) -> None:
        self._packs: Dict[str, KnowledgePack] = {}

    def register(self, pack: KnowledgePack) -> None:
        self._packs[pack.id] = pack

    def get(self, pack_id: str) -> Optional[KnowledgePack]:
        return self._packs.get(pack_id)

    def get_by_name(self, name: str) -> List[KnowledgePack]:
        return [p for p in self._packs.values() if p.name.lower() == name.lower()]

    def list_packs(self) -> List[KnowledgePack]:
        return list(self._packs.values())

    def load_for_identity(self, pack_ids: List[str]) -> List[KnowledgePack]:
        """
        Resolve and return KnowledgePacks for a given list of IDs,
        including their transitive dependencies (simple BFS).
        """
        loaded: List[KnowledgePack] = []
        visited: Set[str] = set()
        queue = list(pack_ids)

        while queue:
            pid = queue.pop(0)
            if pid in visited:
                continue
            visited.add(pid)
            pack = self._packs.get(pid)
            if pack:
                loaded.append(pack)
                for dep in pack.depends_on:
                    if dep not in visited:
                        queue.append(dep)

        # Sort by tier: CORE first, then DOMAIN, then CONTEXT, then TEMP
        tier_order = {KnowledgeTier.CORE: 0, KnowledgeTier.DOMAIN: 1,
                      KnowledgeTier.CONTEXT: 2, KnowledgeTier.TEMP: 3}
        loaded.sort(key=lambda p: tier_order.get(p.tier, 99))
        return loaded

    def __len__(self) -> int:
        return len(self._packs)
