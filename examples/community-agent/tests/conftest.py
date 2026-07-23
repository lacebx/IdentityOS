"""
Tests for the IdentityOS Community Agent.

All tests use ONLY `from identityos import Identity` — no internal modules.
"""
import os
import sys

# Ensure the community-agent package is importable
_AGENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _AGENT_DIR not in sys.path:
    sys.path.insert(0, _AGENT_DIR)

from identityos import Identity


def make_agent(name: str = "test-agent"):
    """Create a fresh test identity."""
    return Identity.create(name, identity_id=name)
