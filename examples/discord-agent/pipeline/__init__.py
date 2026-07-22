"""
Message processing pipeline.

Each step is an independent function that can be composed.
The pipeline runs on every message and detects:
- commitments → intentions
- deadlines → time-bound intentions
- meetings → timeline events
- completion → intention resolved
- preferences → observed facts
- relationship cues → identity graph edges
"""

import logging
import re
from typing import Any, Callable, Dict, List, Optional

from identityos import IdentityObject

logger = logging.getLogger(__name__)

# ── Pattern constants ──────────────────────────────────────────────────────────

_FINISHED_RE = re.compile(
    r"^(?:I\s+)?(?:finished|done|completed|all\s+done|wrapped\s+(?:up|it)|"
    r"it'?s?\s+done|just\s+finished|resolved|fixed|deployed|shipped)\b",
    re.IGNORECASE,
)

_MEETING_OUTCOME_RE = re.compile(
    r"(?:we\s+decided|decision|decided\s+to|agreed\s+on|summary|"
    r"outcome|conclusion|action\s+items|next\s+steps)",
    re.IGNORECASE,
)

_ASK_EVIDENCE_RE = re.compile(
    r"(?:why\s+do\s+you\s+think|what'?s?\s+the\s+evidence|"
    r"how\s+do\s+you\s+know|prove\s+it|evidence\s+for|"
    r"show\s+me\s+the\s+evidence)",
    re.IGNORECASE,
)

_ASK_STATUS_RE = re.compile(
    r"(?:what\s+(?:are|is)\s+(?:we|everyone|the\s+team)\s+(?:working\s+on|doing|up\s+to)|"
    r"what'?s?\s+the\s+status|status\s+update|"
    r"what\s+are\s+we\s+behind\s+on)",
    re.IGNORECASE,
)

# ── Step functions ────────────────────────────────────────────────────────────


# Each step is (name, predicate_fn, action_fn)
# predicate_fn(identity, content, author_id, channel_id) → bool
# action_fn(identity, content, author_id, channel_id) → dict


def step_detect_intentions(
    identity: IdentityObject,
    content: str,
    author_id: str,
    channel_id: str,
) -> List[dict]:
    """Detect commitments and create intentions."""
    results = identity.infer_intentions(text=content, author_id=author_id, source_channel=channel_id)
    for r in results:
        logger.info("Intention inferred: author=%s desc=%s", author_id, r["description"][:60])
    return results


def step_detect_meetings(
    identity: IdentityObject,
    content: str,
    author_id: str,
    channel_id: str,
) -> List[dict]:
    """Detect meeting proposals and record them."""
    results = identity.infer_meetings(text=content, author_id=author_id, source_channel=channel_id)
    for r in results:
        logger.info("Meeting detected: %s", r.get("title", "?")[:60])
    return results


def step_detect_completion(
    identity: IdentityObject,
    content: str,
    author_id: str,
    channel_id: str,
) -> Optional[dict]:
    """Detect 'I finished' and complete the author's most recent intention."""
    if not _FINISHED_RE.match(content):
        return None
    intentions = identity.intentions(status="active")
    author_ints = [
        i for i in intentions
        if i.get("metadata", {}).get("author_id") == author_id
    ]
    if not author_ints:
        return None
    author_ints.sort(key=lambda i: i.get("created_at", ""), reverse=True)
    latest = author_ints[0]
    success = identity.complete_intention(latest["id"], reason=f"Completed by author")
    if success:
        identity.record_event(
            event_type="goal_completed",
            title=f"Intention completed: {latest['description'][:60]}",
            description=f"{author_id} completed: {latest['description']}",
            significance=2,
        )
        logger.info("Intention completed: %s — %s", latest["id"], latest["description"][:60])
        return latest
    return None


def step_detect_meeting_outcome(
    identity: IdentityObject,
    content: str,
    author_id: str,
    channel_id: str,
) -> Optional[str]:
    """Detect meeting outcomes and record them."""
    if not _MEETING_OUTCOME_RE.search(content):
        return None
    event_id = identity.record_event(
        event_type="milestone",
        title="Meeting outcome recorded",
        description=f"Participants: {author_id}. Context: {content[:200]}",
        significance=3,
    )
    identity.remember(
        content=f"Meeting outcome by {author_id}: {content[:200]}",
        tags=["meeting", "outcome"],
    )
    logger.info("Meeting outcome recorded: %s", event_id)
    return event_id


def step_process_chat(
    identity: IdentityObject,
    content: str,
    author_id: str,
    channel_id: str,
    session_id: str,
) -> str:
    """Send to chat and return the reply."""
    with identity.session(session_id=session_id) as session:
        return session.chat(content)


def step_format_context(
    intentions: List[dict],
    meetings: List[dict],
    completed: Optional[dict],
) -> Optional[str]:
    """Build context annotation from detected items."""
    parts = []
    if intentions:
        names = [i["description"][:40] for i in intentions]
        parts.append(f"Tracked: {', '.join(names)}")
    if meetings:
        parts.append("Meeting recorded.")
    if completed:
        parts.append(f"Completed: {completed['description'][:40]}")
    if parts:
        return "(" + " | ".join(parts) + ")"
    return None


# ── Pipeline runner ───────────────────────────────────────────────────────────


def run_pipeline(
    identity: IdentityObject,
    content: str,
    author_id: str,
    channel_id: str,
    session_id: str,
) -> Dict[str, Any]:
    """
    Run the full message processing pipeline.

    Returns a dict with:
      - reply: bot response text (or None if handled specially)
      - intentions: list of created intentions
      - meetings: list of created meetings
      - completed: completed intention (if any)
      - handled: True if the message was handled by a special step
    """
    result: Dict[str, Any] = {
        "reply": None,
        "intentions": [],
        "meetings": [],
        "completed": None,
        "handled": False,
    }

    # Step 1: Detect commitments
    result["intentions"] = step_detect_intentions(identity, content, author_id, channel_id)

    # Step 2: Detect meetings
    result["meetings"] = step_detect_meetings(identity, content, author_id, channel_id)

    # Step 3: Detect completion
    result["completed"] = step_detect_completion(identity, content, author_id, channel_id)

    # Step 4: Detect meeting outcomes
    step_detect_meeting_outcome(identity, content, author_id, channel_id)

    # Step 5: Detect evidence questions
    if _ASK_EVIDENCE_RE.search(content):
        result["handled"] = True
        entity_id = _find_evidence_target(identity, content)
        if entity_id:
            from services.summary import format_evidence
            result["reply"] = f"*Evidence-backed response:*\n{format_evidence(identity, entity_id)}"
        else:
            result["reply"] = "I couldn't determine what you're asking about. Try `/evidence <id>`."
        return result

    # Step 6: Detect status questions
    if _ASK_STATUS_RE.search(content):
        result["handled"] = True
        result["reply"] = generate_team_status(identity)
        return result

    # Step 7: Normal chat
    reply = step_process_chat(identity, content, author_id, channel_id, session_id)

    # Step 8: Append context
    context = step_format_context(result["intentions"], result["meetings"], result["completed"])
    if context:
        reply += f"\n\n*{context}*"

    result["reply"] = reply
    return result


def _find_evidence_target(identity: IdentityObject, content: str) -> Optional[str]:
    """Try to find an entity the user is asking about."""
    intentions = identity.intentions(status="active")
    for i in intentions:
        desc = i.get("description", "").lower()
        for word in content.lower().split():
            if len(word) > 3 and word in desc:
                return i["id"]
    return None


def generate_team_status(identity: IdentityObject) -> str:
    """Generate team status text."""
    from services.summary import generate_team_status
    return generate_team_status(identity)
