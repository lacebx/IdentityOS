"""Eval Engine

Evaluates each LLM exchange and decides what's worth remembering.
This is what makes identity persistent and evolving over time.

The eval engine asks:
  - Did the user reveal a preference?
  - Did the user make a decision?
  - Did the user correct or push back on the AI?
  - Did a milestone happen?
  - Is this worth remembering at all?
"""

from typing import Dict, Any, List
import re
import logging

from memory_engine import MemoryEngine

logger = logging.getLogger(__name__)


# --- Heuristic patterns for detecting memorable content ---

PREFERENCE_SIGNALS = [
    r"i prefer", r"i like", r"i don't like", r"i hate",
    r"i love", r"i always", r"i never", r"my favorite",
    r"i tend to", r"i usually", r"i want", r"i need",
    r"my style", r"my approach", r"i'm a", r"i am a"
]

DECISION_SIGNALS = [
    r"let's go with", r"i'll go with", r"i've decided",
    r"we're going with", r"i chose", r"i picked",
    r"i'm going to", r"i'll use", r"final answer"
]

CORRECTION_SIGNALS = [
    r"no, that's wrong", r"actually", r"that's not right",
    r"you're wrong", r"incorrect", r"that's not what i meant",
    r"i didn't say", r"please don't", r"stop doing"
]

MILESTONE_SIGNALS = [
    r"i finished", r"i completed", r"i shipped", r"i launched",
    r"i got the job", r"i passed", r"i graduated",
    r"we hit", r"i published", r"first time"
]


def _matches_any(text: str, patterns: List[str]) -> bool:
    text_lower = text.lower()
    return any(re.search(p, text_lower) for p in patterns)


def _classify_memory_type(message: str, response: str) -> str:
    """Classify what type of memory this exchange represents."""
    combined = f"{message} {response}".lower()
    if _matches_any(message, CORRECTION_SIGNALS):
        return "correction"
    if _matches_any(message, MILESTONE_SIGNALS):
        return "milestone"
    if _matches_any(message, DECISION_SIGNALS):
        return "decision"
    if _matches_any(message, PREFERENCE_SIGNALS):
        return "preference"
    return "general"


def _extract_memory_content(message: str, response: str, memory_type: str) -> str:
    """Create a concise memory string from the exchange."""
    # For preferences: extract the key preference statement
    msg_sentences = [s.strip() for s in message.split(".") if len(s.strip()) > 10]
    resp_sentences = [s.strip() for s in response.split(".") if len(s.strip()) > 10]

    if memory_type == "preference":
        # Try to find the preference sentence in the user's message
        for sentence in msg_sentences:
            if _matches_any(sentence, PREFERENCE_SIGNALS):
                return sentence[:200]

    elif memory_type == "decision":
        for sentence in msg_sentences:
            if _matches_any(sentence, DECISION_SIGNALS):
                return sentence[:200]

    elif memory_type == "correction":
        return f"User correction: {message[:150]}"

    elif memory_type == "milestone":
        for sentence in msg_sentences:
            if _matches_any(sentence, MILESTONE_SIGNALS):
                return sentence[:200]

    # General: summarize the exchange topic
    if msg_sentences:
        return msg_sentences[0][:200]
    return message[:200]


def _compute_relevance(memory_type: str) -> float:
    """Assign a base relevance score by memory type."""
    scores = {
        "correction": 1.5,   # Corrections are very important — user explicitly pushed back
        "preference": 1.3,   # Preferences shape every future interaction
        "milestone": 1.2,    # Milestones mark the relationship timeline
        "decision": 1.1,     # Decisions made together
        "general": 0.8       # General context, lower priority
    }
    return scores.get(memory_type, 1.0)


def _is_worth_remembering(message: str, response: str) -> bool:
    """Quick pre-filter: is this exchange even worth evaluating?"""
    # Too short to be meaningful
    if len(message) < 15:
        return False
    # Simple acknowledgements
    simple_acks = ["ok", "okay", "thanks", "thank you", "got it", "sure", "yes", "no", "great"]
    if message.lower().strip() in simple_acks:
        return False
    return True


def _extract_tags(memory_type: str, content: str) -> List[str]:
    """Extract simple tags for the memory."""
    tags = [memory_type]
    # Add topic tags from keywords
    keywords = {
        "typescript": "typescript", "python": "python", "javascript": "javascript",
        "react": "react", "startup": "startup", "job": "career",
        "interview": "interview", "project": "project",
        "money": "finance", "health": "health"
    }
    content_lower = content.lower()
    for kw, tag in keywords.items():
        if kw in content_lower and tag not in tags:
            tags.append(tag)
    return tags


class EvalEngine:
    """Evaluates exchanges and stores memorable content as memories."""

    def __init__(self, memory_engine: MemoryEngine):
        self.memory = memory_engine

    async def evaluate(
        self,
        message: str,
        response: str,
        identity: Dict[str, Any],
        user_id: str,
        session_id: str
    ) -> Dict[str, Any]:
        """
        Evaluate an exchange. Store a memory if it's worth keeping.
        Returns summary of what was stored.
        """
        identity_id = identity["identity"]["id"]
        memory_config = identity.get("memory_config", {})
        retention_policy = memory_config.get("retention_policy", "store_significant")
        configured_types = memory_config.get("memory_types",
            ["preference", "decision", "milestone", "correction", "general"])
        threshold = memory_config.get("relevance_threshold", 0.7)

        # Pre-filter
        if not _is_worth_remembering(message, response):
            return {"memories_stored": 0, "summary": "Not memorable", "tags": []}

        memory_type = _classify_memory_type(message, response)
        content = _extract_memory_content(message, response, memory_type)
        relevance = _compute_relevance(memory_type)
        tags = _extract_tags(memory_type, content)

        # Apply retention policy
        should_store = False
        if retention_policy == "store_all":
            should_store = True
        elif retention_policy == "store_significant":
            should_store = (memory_type != "general" and relevance >= threshold)
        elif retention_policy == "store_corrections_only":
            should_store = (memory_type == "correction")

        # Check if this memory type is configured
        if memory_type not in configured_types:
            should_store = False

        if should_store:
            self.memory.store(
                user_id=user_id,
                identity_id=identity_id,
                content=content,
                memory_type=memory_type,
                session_id=session_id,
                tags=tags,
                relevance_score=relevance
            )
            logger.info(f"Stored {memory_type} memory for {user_id}/{identity_id}: {content[:60]}")
            return {
                "memories_stored": 1,
                "summary": f"Stored {memory_type}: {content[:100]}",
                "tags": tags
            }
        else:
            return {
                "memories_stored": 0,
                "summary": f"Not stored (policy={retention_policy}, type={memory_type})",
                "tags": tags
            }
