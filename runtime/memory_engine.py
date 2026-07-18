"""Memory Engine

Manages the persistent memory store for AI identities.
Uses SQLite + simple cosine similarity for local-first MVP.
In production: swap to pgvector or Pinecone.
"""

import sqlite3
import json
import os
import math
import time
import uuid
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

DB_PATH = os.environ.get("MEMORY_DB_PATH", "./identity_runtime.db")


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def _simple_embedding(text: str) -> List[float]:
    """
    Fallback embedding: character frequency vector (dim=128).
    In production: use nomic-embed-text via Ollama or OpenAI embeddings.
    This is good enough for MVP local testing without any API keys.
    """
    vec = [0.0] * 128
    for ch in text.lower():
        idx = ord(ch) % 128
        vec[idx] += 1.0
    # Normalize
    total = sum(vec)
    if total > 0:
        vec = [v / total for v in vec]
    return vec


try:
    import httpx
    async def _ollama_embedding(text: str) -> List[float]:
        """Get embedding from Ollama (nomic-embed-text)."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(
                    "http://localhost:11434/api/embeddings",
                    json={"model": "nomic-embed-text", "prompt": text}
                )
                data = resp.json()
                return data.get("embedding", _simple_embedding(text))
        except Exception:
            return _simple_embedding(text)
except ImportError:
    async def _ollama_embedding(text: str) -> List[float]:  # type: ignore
        return _simple_embedding(text)


class MemoryEngine:
    """SQLite-backed memory store with vector similarity search."""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize the SQLite database with the memories table."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                identity_id TEXT NOT NULL,
                session_id TEXT,
                content TEXT NOT NULL,
                memory_type TEXT DEFAULT 'general',
                embedding TEXT,  -- JSON array
                relevance_score REAL DEFAULT 1.0,
                created_at REAL NOT NULL,
                accessed_at REAL,
                access_count INTEGER DEFAULT 0,
                tags TEXT  -- JSON array
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_identity
            ON memories (user_id, identity_id)
        """)
        conn.commit()
        conn.close()
        logger.info(f"Memory engine initialized: {self.db_path}")

    def store(
        self,
        user_id: str,
        identity_id: str,
        content: str,
        memory_type: str = "general",
        session_id: Optional[str] = None,
        embedding: Optional[List[float]] = None,
        tags: Optional[List[str]] = None,
        relevance_score: float = 1.0
    ) -> str:
        """Store a new memory. Returns the memory ID."""
        memory_id = str(uuid.uuid4())
        now = time.time()
        embedding_json = json.dumps(embedding or _simple_embedding(content))
        tags_json = json.dumps(tags or [])

        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT INTO memories
            (id, user_id, identity_id, session_id, content, memory_type,
             embedding, relevance_score, created_at, accessed_at, access_count, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
        """, (
            memory_id, user_id, identity_id, session_id,
            content, memory_type, embedding_json,
            relevance_score, now, now, tags_json
        ))
        conn.commit()
        conn.close()
        logger.debug(f"Stored memory {memory_id} for {user_id}/{identity_id}")
        return memory_id

    def retrieve(
        self,
        user_id: str,
        identity_id: str,
        query: str,
        top_k: int = 5,
        threshold: float = 0.3
    ) -> List[Dict[str, Any]]:
        """Retrieve the most relevant memories for a query."""
        query_vec = _simple_embedding(query)

        conn = sqlite3.connect(self.db_path)
        rows = conn.execute("""
            SELECT id, content, memory_type, embedding, relevance_score,
                   created_at, access_count, tags
            FROM memories
            WHERE user_id = ? AND identity_id = ?
            ORDER BY created_at DESC
            LIMIT 200
        """, (user_id, identity_id)).fetchall()
        conn.close()

        scored = []
        for row in rows:
            mem_id, content, mem_type, emb_json, rel_score, created, acc_count, tags_json = row
            try:
                emb = json.loads(emb_json) if emb_json else _simple_embedding(content)
                sim = _cosine_similarity(query_vec, emb)
                if sim >= threshold:
                    scored.append({
                        "id": mem_id,
                        "content": content,
                        "memory_type": mem_type,
                        "similarity": round(sim, 4),
                        "relevance_score": rel_score,
                        "created_at": created,
                        "access_count": acc_count,
                        "tags": json.loads(tags_json) if tags_json else []
                    })
            except Exception as e:
                logger.warning(f"Error scoring memory {mem_id}: {e}")

        # Sort by similarity * relevance_score
        scored.sort(key=lambda x: x["similarity"] * x["relevance_score"], reverse=True)
        top = scored[:top_k]

        # Update access counts
        if top:
            conn = sqlite3.connect(self.db_path)
            now = time.time()
            for m in top:
                conn.execute(
                    "UPDATE memories SET access_count = access_count + 1, accessed_at = ? WHERE id = ?",
                    (now, m["id"])
                )
            conn.commit()
            conn.close()

        return top

    def get_all(
        self,
        user_id: str,
        identity_id: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get all memories for a user/identity pair."""
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute("""
            SELECT id, content, memory_type, relevance_score,
                   created_at, access_count, tags, session_id
            FROM memories
            WHERE user_id = ? AND identity_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        """, (user_id, identity_id, limit)).fetchall()
        conn.close()

        return [{
            "id": r[0],
            "content": r[1],
            "memory_type": r[2],
            "relevance_score": r[3],
            "created_at": r[4],
            "access_count": r[5],
            "tags": json.loads(r[6]) if r[6] else [],
            "session_id": r[7]
        } for r in rows]

    def clear(self, user_id: str, identity_id: str) -> int:
        """Delete all memories for a user/identity pair. Returns deleted count."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            "DELETE FROM memories WHERE user_id = ? AND identity_id = ?",
            (user_id, identity_id)
        )
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        logger.info(f"Cleared {deleted} memories for {user_id}/{identity_id}")
        return deleted

    def count(self, user_id: str, identity_id: str) -> int:
        """Count memories for a user/identity pair."""
        conn = sqlite3.connect(self.db_path)
        result = conn.execute(
            "SELECT COUNT(*) FROM memories WHERE user_id = ? AND identity_id = ?",
            (user_id, identity_id)
        ).fetchone()
        conn.close()
        return result[0] if result else 0
