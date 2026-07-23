"""
IdentityOS SDK — legacy compatibility shim.

New code should use:
    from identityos import Identity
"""
from identityos import Identity, IdentityObject, IdentityClient

__all__ = ["Identity", "IdentityObject", "IdentityClient"]
