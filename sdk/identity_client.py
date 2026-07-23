"""
Legacy compatibility shim — the IdentityOS HTTP client now lives in identityos/.

New code should use:
    from identityos import IdentityClient
"""
from identityos.client import IdentityClient

__all__ = ["IdentityClient"]
