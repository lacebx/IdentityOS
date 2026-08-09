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
    # verbs
    "create", "build", "make", "acquire", "develop", "implement", "add",
    "install", "use", "using", "come", "give", "help", "ask", "tell",
    "know", "think", "go", "want", "need", "like", "let", "do", "get",
    # capability nouns
    "capability", "capabilities", "skill", "one",
    # articles / determiners
    "a", "an", "the", "this", "that", "these", "those", "new", "set", "some",
    # prepositions / conjunctions
    "to", "of", "for", "on", "in", "at", "by", "with", "up", "and", "or",
    "but", "from", "about", "into", "over", "out",
    # pronouns
    "self", "my", "myself", "your", "yourself", "i", "me", "we", "our",
    "ours", "us", "you", "your", "he", "she", "it", "they", "them", "their",
    "him", "her", "its", "one", "someone", "anyone",
    # conversational filler / question particles
    "why", "well", "so", "ok", "okay", "no", "yes", "yeah", "now", "what",
    "when", "where", "who", "which", "how", "please", "thanks", "hey",
    "nice", "great", "good", "just", "really", "ive", "im", "dont", "youre",
    "cant", "wont", "gonna", "wanna", "should", "would", "could", "maybe",
    "can", "sure", "quite", "much", "more", "most", "very", "too", "also", "today",
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
            if cand.lower() in _STOPWORDS:
                # Skip conversational filler: look ahead for the first real
                # token (e.g. "build me a weather skill" -> "weather").
                lookahead = _next_candidate_token(text[m.end():])
                if lookahead is not None:
                    return lookahead
                continue
            return cand.lower()
    return None


def _next_candidate_token(segment: str) -> Optional[str]:
    """Return the first non-stopword token in *segment*, if any."""
    for tok in re.findall(r"[a-z_][a-z0-9_]*", segment.lower()):
        if tok not in _STOPWORDS:
            return tok
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
