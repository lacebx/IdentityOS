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

_CAPABILITY_TOKEN = r"['\"]?([a-z_][a-z0-9_]{1,31})['\"]?"
_ACTION = r"(?:create|build|make|acquire|develop|implement|add|install|set\s?up)"

# Explicit naming is intentionally checked first. A name such as ``help`` is
# valid when the user says “called help”, but “create a capability to help” is
# an underspecified request and must not generate a junk package.
_EXPLICIT_CAP_PATTERNS = [
    re.compile(
        rf"(?:capability|skill)\s+(?:called|named)\s+{_CAPABILITY_TOKEN}",
        re.IGNORECASE,
    ),
    re.compile(
        rf"(?:called|named)\s+{_CAPABILITY_TOKEN}(?:\s+(?:capability|skill))?",
        re.IGNORECASE,
    ),
]

_GENERIC_CAP_PATTERNS = [
    # “build me a weather skill” / “create a new speech capability”
    re.compile(
        rf"{_ACTION}\s+(?:me\s+)?(?:a|an|the)?\s*(?:new\s+)?"
        rf"{_CAPABILITY_TOKEN}\s+(?:capability|skill)\b",
        re.IGNORECASE,
    ),
    # “create a capability to speak” / “build a skill for transcription”
    re.compile(
        rf"{_ACTION}\s+(?:me\s+)?(?:a|an|the)?\s*(?:new\s+)?"
        rf"(?:capability|skill)\s+(?:(?:to|for)\s+)?{_CAPABILITY_TOKEN}",
        re.IGNORECASE,
    ),
    # Preserve loose requests such as “create a command execution capability”;
    # registry resolution can map the meaningful leading token to a canonical
    # capability id (``command`` -> ``command_exec``).
    re.compile(
        rf"{_ACTION}\s+(?:me\s+)?(?:a|an|the)?\s*(?:new\s+)?"
        rf"(?:capability\s+|skill\s+)?{_CAPABILITY_TOKEN}\b",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\b([a-z_][a-z0-9_]{{1,31}}(?:_cap|_capability|_skill))\b",
        re.IGNORECASE,
    ),
]

_STOPWORDS = frozenset({
    # actions and vague verbs
    "create", "build", "make", "acquire", "develop", "implement", "add",
    "install", "use", "using", "come", "give", "help", "ask", "tell",
    "know", "think", "go", "want", "need", "like", "let", "do", "get",
    # capability nouns, articles, connectors, and pronouns
    "capability", "capabilities", "skill", "a", "an", "the", "this",
    "that", "these", "those", "new", "set", "some", "to", "of", "for",
    "on", "in", "at", "by", "with", "up", "and", "or", "but", "from",
    "about", "into", "over", "out", "self", "my", "myself", "your",
    "yourself", "i", "me", "we", "our", "ours", "us", "you", "he",
    "she", "it", "they", "them", "their", "him", "her", "its", "one",
    "someone", "anyone",
    # conversational filler and question particles
    "why", "well", "so", "ok", "okay", "no", "yes", "yeah", "now",
    "what", "when", "where", "who", "which", "how", "please", "thanks",
    "hey", "nice", "great", "good", "just", "really", "ive", "im",
    "dont", "youre", "cant", "wont", "gonna", "wanna", "should",
    "would", "could", "maybe", "can", "sure", "quite", "much", "more",
    "most", "very", "too", "also", "today",
})


def extract_capability_name(goal: str) -> Optional[str]:
    """Extract the target capability name from a natural-language goal.

    Returns the raw candidate or None when the goal does not describe a
    capability acquisition.
    """
    text = (goal or "").strip()
    if not text:
        return None
    for pat in _EXPLICIT_CAP_PATTERNS:
        match = pat.search(text)
        if match:
            return match.group(1).lower()
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
