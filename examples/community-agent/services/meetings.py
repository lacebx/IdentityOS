import logging
from typing import List, Optional
from identityos import IdentityObject

logger = logging.getLogger(__name__)


def detect_and_create_meeting(
    identity: IdentityObject,
    message: str,
    author_id: str,
    channel_id: str,
) -> List[dict]:
    """Detect meeting proposals in a message and record them via SDK."""
    results = identity.infer_meetings(
        text=message,
        author_id=author_id,
        source_channel=channel_id,
    )
    for r in results:
        logger.info(
            "Meeting detected: proposed_by=%s time=%s",
            r.get("proposed_by", "?"), r.get("proposed_time", "?"),
        )
    return results


def record_meeting_outcome(
    identity: IdentityObject,
    participants: List[str],
    summary: str,
    decisions: List[str],
) -> str:
    """Record a meeting outcome in the identity's timeline."""
    event_id = identity.record_event(
        event_type="milestone",
        title=f"Meeting completed: {summary[:60]}",
        description=(
            f"Participants: {', '.join(participants)}\n"
            f"Summary: {summary}\n"
            f"Decisions: {'; '.join(decisions)}"
        ),
        significance=4,
    )
    identity.remember(
        content=f"Meeting outcome: {summary} | Participants: {', '.join(participants)} | Decisions: {'; '.join(decisions)}",
        tags=["meeting", "outcome"],
    )
    logger.info("Meeting outcome recorded: %s", event_id)
    return event_id
