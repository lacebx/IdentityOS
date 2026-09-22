"""Durable secret handling for IdentityOS.

Secrets are addressed only by opaque handles (``secret://<namespace>/<name>``).
Plaintext values live exclusively on disk in a private directory (0600) and are
resolved only at the trusted execution boundary.  Handles — never values — are
allowed to appear in identity state, capability configs, provenance, and logs.
"""

from .store import (
    HANDLE_PATTERN,
    SecretHandleError,
    SecretNotFound,
    SecretStore,
    SecretStoreError,
    default_secret_store_dir,
    scrub_all,
)

__all__ = [
    "HANDLE_PATTERN",
    "SecretHandleError",
    "SecretNotFound",
    "SecretStore",
    "SecretStoreError",
    "default_secret_store_dir",
    "scrub_all",
]
