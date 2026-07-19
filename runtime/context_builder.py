"""
DEPRECATED — runtime/context_builder.py

This module has been superseded by core/cognitive_engine.py.

ContextComposer is now the canonical context assembly module.
It produces structured ComposedContext objects with identity, memory,
skills, goals, relationships, and more.

Use core.cognitive_engine.ContextComposer for new code.
"""

from core.cognitive_engine import ComposedContext, ContextComposer

__all__ = [
    "ContextComposer",
    "ComposedContext",
]
