"""
IdentityOS — portable AI identity layer.

The primary public API for IdentityOS. All you need is:

    from identityos import Identity

    lace = Identity.load("lace")
    reply = lace.chat("Hello!")
    print(reply)

Or create a new identity:

    mentor = Identity.create("Mentor", identity_class="assistant")
    mentor.chat("What is your purpose?")
"""

from identityos.identity import Identity, IdentityObject
from identityos.client import IdentityClient

__all__ = ["Identity", "IdentityObject", "IdentityClient"]
