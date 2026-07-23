import logging
from typing import Optional
from identityos import IdentityObject

logger = logging.getLogger(__name__)


def process_message(
    identity: IdentityObject,
    message: str,
    author_id: str,
    channel_id: str,
) -> str:
    """Process an incoming message. Returns the bot's reply."""
    response = identity.chat(message)
    return response


def process_with_observations(
    identity: IdentityObject,
    message: str,
    author_id: str,
    channel_id: str,
) -> str:
    """Process a message, extract facts, and return a reply."""
    identity.observe(message, source=author_id)
    return identity.chat(message)
