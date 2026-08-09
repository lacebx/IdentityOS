"""
workflow.py — Generic capability-acquisition workflow.

The executive's default plan for acquiring any capability:

    Need Detection
        -> Task Creation
        -> Registry Search
        -> Install if exists
        -> Else Design -> Generate -> Validate -> Publish
        -> Install
        -> Verify
        -> Retry Original Goal

No code here knows about individual capability names.  The target capability
is extracted from the goal string as data, then every step is built from a
fixed generic template.
"""

from __future__ import annotations

import re
from typing import Optional

_GENERIC_CAP_PATTERNS = [
    re.compile(r"(?:capability|skill)\s+(?:to|for)\s+['\"]?([a-z_][a-z0-9_]{1,31})['\"]?", re.IGNORECASE),
    re.compile(r"(?:create|build|make|acquire|develop|implement|add|install|set\s?up)\s+(?:a|an|the)?\s*(?:new\s+)?(?:capability\s+|skill\s+)?['\"]?([a-z_][a-z0-9_]{1,31})['\"]?(?:\s+capability|\s+skill|\b)", re.IGNORECASE),
    re.compile(r"(?:called|named)\s+['\"]?([a-z_][a-z0-9_]{1,31})['\"]?(?:\s+capability|\b)", re.IGNORECASE),
    re.compile(r"(?:capability|skill)\s+['\"]?([a-z_][a-z0-9_]{1,31})['\"]?", re.IGNORECASE),
    re.compile(r"\b([a-z_][a-z0-9_]{1,31}(?:_cap|_capability|_skill))\b", re.IGNORECASE),
]

_STOPWORDS = frozenset({
    "create", "build", "make", "acquire", "develop", "implement", "add",
    "install", "capability", "capabilities", "skill", "a", "an", "the",
    "new", "set", "up", "use", "using", "for", "and", "it", "one", "to",
    "of", "on", "self", "my", "myself", "your", "yourself",
})


def extract_capability_name(goal: str) -> Optional[str]:
    """Extract the target capability name from a natural-language goal.

    Returns the raw candidate or None when the goal does not describe a
    capability acquisition.
    """
    text = (goal or "").strip()
    if not text:
        return None
    for pat in _GENERIC_CAP_PATTERNS:
        m = pat.search(text)
        if m:
            cand = m.group(1)
            if cand.lower() not in _STOPWORDS:
                return cand.lower()
    return None


def is_acquisition_goal(goal: str) -> bool:
    """True when the goal describes creating/acquiring a capability."""
    text = (goal or "").lower()
    if not re.search(r"(create|build|make|acquire|develop|implement|install|add).{0,40}(capability|skill)", text):
        return False
    return extract_capability_name(goal) is not None


def build_acquisition_plan(capability_id: str, original_request: Optional[str] = None) -> list[dict]:
    """Build the generic acquisition plan for *capability_id*.

    Steps that only apply when the capability must be generated are guarded
    by ``run_unless`` on the ``registry_search`` result so the executor can
    skip them when the capability already exists in the registry.
    """
    plan = [
        {
            "action": "registry_search",
            "description": f"Searching registry for {capability_id}",
            "params": {"capability": capability_id},
        },
        {
            "action": "generate",
            "description": f"Generating {capability_id} capability",
            "params": {"capability": capability_id},
            "run_unless_step": "registry_search",
            "run_unless_key": "found",
        },
        {
            "action": "validate",
            "description": f"Validating {capability_id} capability",
            "params": {"capability": capability_id},
            "run_unless_step": "registry_search",
            "run_unless_key": "found",
        },
        {
            "action": "publish",
            "description": f"Publishing {capability_id} to registry",
            "params": {"capability": capability_id},
            "run_unless_step": "registry_search",
            "run_unless_key": "found",
        },
        {
            "action": "install",
            "description": f"Installing {capability_id}",
            "params": {"capability": capability_id},
        },
        {
            "action": "verify",
            "description": f"Verifying {capability_id}",
            "params": {"capability": capability_id},
        },
    ]
    if original_request:
        plan.append({
            "action": "verify_goal",
            "description": "Retrying original request",
            "params": {"request": original_request, "capability": capability_id},
        })
    return plan
