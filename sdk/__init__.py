"""
IdentityOS SDK — the primary developer interface for IdentityOS.

Usage:
    from sdk import Identity

    # Load an existing identity
    lace = Identity.load("lace")
    reply = lace.chat("Hello!")
    print(reply)

    # Create a new identity
    mentor = Identity.create("Mentor", persona="mentor")
    mentor.chat("What is your purpose?")

    # Import/export
    lace.export("lace.json")
    restored = Identity.from_file("lace.json")
"""

from .identity_object import Identity, IdentityObject

__all__ = ["Identity", "IdentityObject"]
