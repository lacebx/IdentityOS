import logging
from typing import List, Optional
from identityos import IdentityObject

logger = logging.getLogger(__name__)


def detect_and_create_intentions(
    identity: IdentityObject,
    message: str,
    author_id: str,
    channel_id: str,
) -> List[dict]:
    """Detect commitments in a message and create SDK intentions."""
    results = identity.infer_intentions(
        text=message,
        author_id=author_id,
        source_channel=channel_id,
    )
    for r in results:
        logger.info(
            "Intention inferred: author=%s desc=%s expires=%s",
            author_id, r["description"], r.get("expires_at", "?"),
        )
    return results


def complete_authors_intention(
    identity: IdentityObject,
    author_id: str,
    message: str = "",
) -> Optional[dict]:
    """Find and complete the most recent active intention for an author."""
    intentions = identity.intentions(status="active")
    author_intentions = [
        i for i in intentions
        if i.get("metadata", {}).get("author_id") == author_id
    ]
    if not author_intentions:
        logger.info("No active intentions found for author %s", author_id)
        return None

    author_intentions.sort(key=lambda i: i.get("created_at", ""), reverse=True)
    latest = author_intentions[0]
    success = identity.complete_intention(
        latest["id"],
        reason=f"Completed by author: {message[:100] if message else 'confirmed'}",
    )
    if success:
        logger.info("Intention completed: %s — %s", latest["id"], latest["description"])
        identity.record_event(
            event_type="goal_completed",
            title=f"Intention completed: {latest['description'][:60]}",
            description=f"{author_id} completed: {latest['description']}",
            significance=2,
        )
        return latest
    return None
