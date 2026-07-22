"""
IdentityOS SDK — legacy compatibility shim.

New code should use:
    from identityos import Identity
"""
from sdk.identity_object import Identity, IdentityObject

__all__ = ["Identity", "IdentityObject"]
