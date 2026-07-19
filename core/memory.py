"""
core/memory.py

The Memory module — WHAT an identity has experienced.

Memory is strictly separated from Identity and Knowledge.
- Memory = experiences, episodes, interactions (time-indexed, personal)
- Knowledge = facts, domain expertise (time-independent, transferable)
- Identity = who the entity is (stable core)

Memory is organized into three tiers:
  CORE     — foundational memories that define the identity's worldview
  SEMANTIC — distilled facts extracted from episodic patterns
  EPISODIC — raw experiences, conversations, events

The MemoryStore is the access layer; MemoryEngine (in runtime/) handles
embeddings, search, and consolidation.
"""

from __future__ import annotations

import json
import math
import os
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

# ─── Enums ────────────────────────────────────────────────────────────────────

class MemoryType(str, Enum):
    CORE = "core"           # Inviolable founding experiences
    SEMANTIC = "semantic"   # Distilled facts / generalized knowledge from episodes
    EPISODIC = "episodic"   # Raw interactions and events
    WORKING = "working"     # Short-term, in-session context (not persisted long-term)


class MemoryConfidence(str, Enum):
    HIGH = "high"       # Well-corroborated, stable
    MEDIUM = "medium"   # Plausible but not fully confirmed
    LOW = "low"         # Single occurrence, may contradict other memories
    INFERRED = "inferred"  # Derived by the semantic consolidation process


# ─── MemoryFragment ───────────────────────────────────────────────────────────

@dataclass
class MemoryFragment:
    """
    A single unit of memory. The atomic building block of the Memory module.

    Every interaction, fact, or experience is stored as a MemoryFragment.
    The embedding vector is computed by the MemoryEngine and stored externally.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    identity_id: str = ""
    content: str = ""
    memory_type: MemoryType = MemoryType.EPISODIC
    confidence: MemoryConfidence = MemoryConfidence.MEDIUM

    # ── Provenance ───────────────────────────────────────────────────────────
    source: str = "unknown"         # e.g. "chatgpt", "grok", "api", "story"
    session_id: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_accessed: Optional[datetime] = None

    # ── Importance & recall ──────────────────────────────────────────────────
    importance: float = 0.5         # 0.0 – 1.0; affects retrieval priority
    access_count: int = 0           # How many times this memory has been retrieved
    decay_factor: float = 1.0       # Multiplier applied over time (1.0 = no decay)

    # ── Embedding reference ──────────────────────────────────────────────────
    # The actual vector is stored in the vector DB, referenced by this ID.
    embedding_id: Optional[str] = None

    # ── Links ────────────────────────────────────────────────────────────────
    related_memory_ids: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)

    # ── Extra ─────────────────────────────────────────────────────────────────
    extra: Dict[str, Any] = field(default_factory=dict)

    def touch(self) -> None:
        """Record that this memory was accessed."""
        self.last_accessed = datetime.now(timezone.utc)
        self.access_count += 1

    def promote(self) -> None:
        """Increase importance (e.g. when corroborated by another memory)."""
        self.importance = min(1.0, self.importance + 0.1)

    def demote(self) -> None:
        """Decrease importance (e.g. contradicted by newer evidence)."""
        self.importance = max(0.0, self.importance - 0.1)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "identity_id": self.identity_id,
            "content": self.content,
            "memory_type": self.memory_type.value,
            "confidence": self.confidence.value,
            "source": self.source,
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat(),
            "last_accessed": self.last_accessed.isoformat() if self.last_accessed else None,
            "importance": self.importance,
            "access_count": self.access_count,
            "decay_factor": self.decay_factor,
            "embedding_id": self.embedding_id,
            "related_memory_ids": self.related_memory_ids,
            "tags": self.tags,
            "extra": self.extra,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryFragment":
        frag = cls(
            id=data.get("id", str(uuid.uuid4())),
            identity_id=data.get("identity_id", ""),
            content=data.get("content", ""),
            memory_type=MemoryType(data.get("memory_type", "episodic")),
            confidence=MemoryConfidence(data.get("confidence", "medium")),
            source=data.get("source", "unknown"),
            session_id=data.get("session_id"),
            importance=data.get("importance", 0.5),
            access_count=data.get("access_count", 0),
            decay_factor=data.get("decay_factor", 1.0),
            embedding_id=data.get("embedding_id"),
            related_memory_ids=data.get("related_memory_ids", []),
            tags=data.get("tags", []),
            extra=data.get("extra", {}),
        )
        if "created_at" in data and data["created_at"]:
            frag.created_at = datetime.fromisoformat(data["created_at"])
        if "last_accessed" in data and data["last_accessed"]:
            frag.last_accessed = datetime.fromisoformat(data["last_accessed"])
        return frag


# ─── MemorySearchResult ───────────────────────────────────────────────────────

@dataclass
class MemorySearchResult:
    """Returned by MemoryStore.search() — a fragment with its relevance score."""
    fragment: MemoryFragment
    score: float  # Cosine similarity or BM25 rank; higher = more relevant


# ─── MemoryStats ─────────────────────────────────────────────────────────────

@dataclass
class MemoryStats:
    """
    Summary statistics for an identity's memory.
    Shown in the Identity Explorer.
    """
    identity_id: str
    total_fragments: int = 0
    core_count: int = 0
    semantic_count: int = 0
    episodic_count: int = 0
    working_count: int = 0
    avg_importance: float = 0.0
    oldest_memory: Optional[datetime] = None
    newest_memory: Optional[datetime] = None
    total_accesses: int = 0
    confidence_distribution: Dict[str, int] = field(default_factory=dict)


# ─── MemoryStore ──────────────────────────────────────────────────────────────

class MemoryStore:
    """
    In-memory store of MemoryFragments across identities.

    This is the domain object — it has NO knowledge of databases or embeddings.
    Persistence and vector search are handled by the runtime layer.
    The MemoryStore gives the Runtime a clean API to work with memory in memory.

    Think of it as a mailbox. The persistence layer is the postal system.
    """

    def __init__(self) -> None:
        self._fragments: Dict[str, MemoryFragment] = {}

    # ── CRUD ──────────────────────────────────────────────────────────────────

    def add(self, fragment: MemoryFragment) -> MemoryFragment:
        """Add a memory fragment."""
        if not fragment.id:
            fragment.id = str(uuid.uuid4())
        self._fragments[fragment.id] = fragment
        return fragment

    def get(self, fragment_id: str) -> Optional[MemoryFragment]:
        frag = self._fragments.get(fragment_id)
        if frag:
            frag.touch()
        return frag

    def remove(self, fragment_id: str) -> bool:
        if fragment_id in self._fragments:
            del self._fragments[fragment_id]
            return True
        return False

    def all(self) -> List[MemoryFragment]:
        return list(self._fragments.values())

    # ── Filtered access ───────────────────────────────────────────────────────

    def by_type(self, memory_type: MemoryType) -> List[MemoryFragment]:
        return [f for f in self._fragments.values() if f.memory_type == memory_type]

    def by_source(self, source: str) -> List[MemoryFragment]:
        return [f for f in self._fragments.values() if f.source == source]

    def by_session(self, session_id: str) -> List[MemoryFragment]:
        return [f for f in self._fragments.values() if f.session_id == session_id]

    def core_memories(self) -> List[MemoryFragment]:
        return self.by_type(MemoryType.CORE)

    def by_identity(self, identity_id: str) -> List[MemoryFragment]:
        """Return all fragments for a given identity."""
        return [f for f in self._fragments.values() if f.identity_id == identity_id]

    def recent(self, identity_id: str = "", n: int = 10) -> List[MemoryFragment]:
        """Return the n most recently created fragments, optionally filtered by identity."""
        frags = list(self._fragments.values())
        if identity_id:
            frags = [f for f in frags if f.identity_id == identity_id]
        sorted_frags = sorted(
            frags,
            key=lambda f: f.created_at,
            reverse=True,
        )
        return sorted_frags[:n]

    def most_important(self, identity_id: str = "", n: int = 10) -> List[MemoryFragment]:
        """Return the n most important fragments, optionally filtered by identity."""
        frags = list(self._fragments.values())
        if identity_id:
            frags = [f for f in frags if f.identity_id == identity_id]
        sorted_frags = sorted(
            frags,
            key=lambda f: f.importance,
            reverse=True,
        )
        return sorted_frags[:n]

    def search_keywords(
        self, query: str, identity_id: str = "", limit: int = 10
    ) -> List[MemoryFragment]:
        """Simple keyword search over fragment content."""
        q = query.lower()
        frags = list(self._fragments.values())
        if identity_id:
            frags = [f for f in frags if f.identity_id == identity_id]
        results = [
            f for f in frags
            if q in f.content.lower() or any(q in t.lower() for t in f.tags)
        ]
        return sorted(results, key=lambda f: f.importance, reverse=True)[:limit]

    # ── Stats ─────────────────────────────────────────────────────────────────

    def clear_identity(self, identity_id: str) -> int:
        """Delete all memories for an identity. Returns count of deleted."""
        before = len(self._fragments)
        self._fragments = {
            k: v for k, v in self._fragments.items()
            if v.identity_id != identity_id
        }
        return before - len(self._fragments)

    def stats(self, identity_id: str = "") -> MemoryStats:
        frags = list(self._fragments.values())
        if not frags:
            return MemoryStats(identity_id=identity_id)

        if identity_id:
            frags = [f for f in frags if f.identity_id == identity_id]

        if not frags:
            return MemoryStats(identity_id=identity_id)

        conf_dist: Dict[str, int] = {}
        for f in frags:
            conf_dist[f.confidence.value] = conf_dist.get(f.confidence.value, 0) + 1

        return MemoryStats(
            identity_id=identity_id or "all",
            total_fragments=len(frags),
            core_count=sum(1 for f in frags if f.memory_type == MemoryType.CORE),
            semantic_count=sum(1 for f in frags if f.memory_type == MemoryType.SEMANTIC),
            episodic_count=sum(1 for f in frags if f.memory_type == MemoryType.EPISODIC),
            working_count=sum(1 for f in frags if f.memory_type == MemoryType.WORKING),
            avg_importance=sum(f.importance for f in frags) / len(frags),
            oldest_memory=min(f.created_at for f in frags),
            newest_memory=max(f.created_at for f in frags),
            total_accesses=sum(f.access_count for f in frags),
            confidence_distribution=conf_dist,
        )

    def __len__(self) -> int:
        return len(self._fragments)

    def __repr__(self) -> str:
        return f"MemoryStore(fragments={len(self)})"


# ─── Factory helpers ──────────────────────────────────────────────────────────

def make_memory(
    content: str,
    identity_id: str = "",
    memory_type: MemoryType = MemoryType.EPISODIC,
    source: str = "api",
    importance: float = 0.5,
    tags: Optional[List[str]] = None,
    **extra: Any,
) -> MemoryFragment:
    """Quick factory for creating a MemoryFragment."""
    return MemoryFragment(
        identity_id=identity_id,
        content=content,
        memory_type=memory_type,
        source=source,
        importance=importance,
        tags=tags or [],
        extra=extra,
    )


# ─── Backward-compatible aliases ─────────────────────────────────────────────
# These ensure consumers written against older type names continue to work.

MemoryItem = MemoryFragment
MemoryTier = MemoryType


# ─── SQLite-backed Persistent Memory Store ───────────────────────────────────
# The in-memory MemoryStore is the canonical domain object. For persistence,
# use PersistentMemoryStore — a drop-in replacement with SQLite storage.
# In production, swap to pgvector or Pinecone.
# ──────────────────────────────────────────────────────────────────────────────

_DB_PATH = os.environ.get("MEMORY_DB_PATH", "./identity_runtime.db")


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def _simple_embedding(text: str) -> List[float]:
    vec = [0.0] * 128
    for ch in text.lower():
        idx = ord(ch) % 128
        vec[idx] += 1.0
    total = sum(vec)
    if total > 0:
        vec = [v / total for v in vec]
    return vec


class PersistentMemoryStore(MemoryStore):
    """
    SQLite-backed memory store that mirrors the MemoryStore API.

    MemoryFragments are persisted to a local SQLite database with
    embedding vectors for cosine-similarity search.

    Usage is identical to MemoryStore — just pass it to the Runtime
    instead of the in-memory version.
    """

    def __init__(self, db_path: str = _DB_PATH):
        super().__init__()
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS core_memories (
                id TEXT PRIMARY KEY,
                identity_id TEXT NOT NULL,
                content TEXT NOT NULL,
                memory_type TEXT DEFAULT 'episodic',
                confidence TEXT DEFAULT 'medium',
                source TEXT DEFAULT 'unknown',
                session_id TEXT,
                importance REAL DEFAULT 0.5,
                access_count INTEGER DEFAULT 0,
                decay_factor REAL DEFAULT 1.0,
                embedding TEXT,
                embedding_id TEXT,
                related_memory_ids TEXT DEFAULT '[]',
                tags TEXT DEFAULT '[]',
                extra TEXT DEFAULT '{}',
                created_at TEXT NOT NULL,
                last_accessed TEXT
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_core_memories_identity
            ON core_memories (identity_id)
        """)
        conn.commit()
        conn.close()

    def add(self, fragment: MemoryFragment) -> MemoryFragment:
        super().add(fragment)
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT OR REPLACE INTO core_memories
            (id, identity_id, content, memory_type, confidence,
             source, session_id, importance, access_count, decay_factor,
             embedding, embedding_id, related_memory_ids,
             tags, extra, created_at, last_accessed)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            fragment.id, fragment.identity_id, fragment.content,
            fragment.memory_type.value, fragment.confidence.value,
            fragment.source, fragment.session_id,
            fragment.importance, fragment.access_count, fragment.decay_factor,
            json.dumps(_simple_embedding(fragment.content)),
            fragment.embedding_id,
            json.dumps(fragment.related_memory_ids),
            json.dumps(fragment.tags),
            json.dumps(fragment.extra),
            fragment.created_at.isoformat(),
            fragment.last_accessed.isoformat() if fragment.last_accessed else None,
        ))
        conn.commit()
        conn.close()
        return fragment

    def _row_to_fragment(self, row: tuple) -> MemoryFragment:
        col = {
            "id": 0, "identity_id": 1, "content": 2, "memory_type": 3,
            "confidence": 4, "source": 5, "session_id": 6,
            "importance": 7, "access_count": 8, "decay_factor": 9,
            "embedding_id": 11, "related_memory_ids": 12,
            "tags": 13, "extra": 14, "created_at": 15, "last_accessed": 16,
        }
        frag = MemoryFragment(
            id=row[col["id"]],
            identity_id=row[col["identity_id"]],
            content=row[col["content"]],
            memory_type=MemoryType(row[col["memory_type"]]),
            confidence=MemoryConfidence(row[col["confidence"]]),
            source=row[col["source"]],
            session_id=row[col["session_id"]],
            importance=row[col["importance"]],
            access_count=row[col["access_count"]],
            decay_factor=row[col["decay_factor"]],
            embedding_id=row[col["embedding_id"]],
            related_memory_ids=json.loads(row[col["related_memory_ids"]]),
            tags=json.loads(row[col["tags"]]),
            extra=json.loads(row[col["extra"]]),
        )
        if row[col["created_at"]]:
            frag.created_at = datetime.fromisoformat(row[col["created_at"]])
        if row[col["last_accessed"]]:
            frag.last_accessed = datetime.fromisoformat(row[col["last_accessed"]])
        return frag

    def get(self, fragment_id: str) -> Optional[MemoryFragment]:
        conn = sqlite3.connect(self.db_path)
        row = conn.execute(
            "SELECT * FROM core_memories WHERE id = ?", (fragment_id,)
        ).fetchone()
        conn.close()
        if row:
            frag = self._row_to_fragment(row)
            frag.touch()
            self._fragments[frag.id] = frag
            return frag
        return super().get(fragment_id)

    def remove(self, fragment_id: str) -> bool:
        conn = sqlite3.connect(self.db_path)
        conn.execute("DELETE FROM core_memories WHERE id = ?", (fragment_id,))
        conn.commit()
        conn.close()
        return super().remove(fragment_id)

    def all(self) -> List[MemoryFragment]:
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute("SELECT * FROM core_memories").fetchall()
        conn.close()
        return [self._row_to_fragment(r) for r in rows]

    def search(
        self,
        query: str,
        identity_id: str = "",
        top_k: int = 5,
        threshold: float = 0.3,
    ) -> List[MemorySearchResult]:
        """Cosine-similarity search over embeddings."""
        query_vec = _simple_embedding(query)
        conn = sqlite3.connect(self.db_path)
        if identity_id:
            rows = conn.execute(
                "SELECT * FROM core_memories WHERE identity_id = ?",
                (identity_id,),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM core_memories").fetchall()
        conn.close()

        scored: List[MemorySearchResult] = []
        for row in rows:
            try:
                emb = json.loads(row[10]) if row[10] else _simple_embedding(row[2])
                sim = _cosine_similarity(query_vec, emb)
                if sim >= threshold:
                    frag = self._row_to_fragment(row)
                    scored.append(MemorySearchResult(fragment=frag, score=sim))
            except Exception:
                continue

        scored.sort(key=lambda x: x.score, reverse=True)
        return scored[:top_k]

    def clear_identity(self, identity_id: str) -> int:
        """Delete all memories for an identity. Returns count of deleted."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            "DELETE FROM core_memories WHERE identity_id = ?", (identity_id,)
        )
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        self._fragments = {
            k: v for k, v in self._fragments.items() if v.identity_id != identity_id
        }
        return deleted
