import os
import sys

# Add both the agent dir and repo root to path
_AGENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_REPO_ROOT = os.path.dirname(os.path.dirname(_AGENT_DIR))
for p in (_AGENT_DIR, _REPO_ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

from identityos import Identity


def make_agent(name: str = "test-agent"):
    return Identity.create(name, identity_id=name)
