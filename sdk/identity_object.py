"""
Legacy compatibility shim — the IdentityOS SDK now lives in identityos/.

New code should use:
    from identityos import Identity
"""
from identityos.identity import Identity, IdentityObject

__all__ = ["Identity", "IdentityObject"]
