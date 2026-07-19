"""
DEPRECATED — runtime/memory_engine.py

This module has been superseded by core/memory.py.

The canonical MemoryStore and PersistentMemoryStore now live in
core/memory.py. PersistentMemoryStore provides the SQLite-backed persistence
that was formerly in this module.

Use core.memory.PersistentMemoryStore or core.memory.MemoryStore for new code.
"""

from core.memory import MemoryFragment, MemoryStore, MemoryType, PersistentMemoryStore

MemoryEngine = PersistentMemoryStore

__all__ = [
    "MemoryStore",
    "PersistentMemoryStore",
    "MemoryEngine",
    "MemoryFragment",
    "MemoryType",
]
