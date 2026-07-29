from __future__ import annotations

import time
from typing import Optional, Set

from core.prometheus.models import RegistryCandidate


def install_capability(
    candidate: RegistryCandidate,
    identity_id: str,
    capability_registry,
) -> bool:
    try:
        capability_registry.install(identity_id, candidate.cap_id)
        return True
    except (ValueError, Exception):
        return False


def rollback_install(
    candidate: RegistryCandidate,
    identity_id: str,
    capability_registry,
) -> bool:
    try:
        capability_registry.uninstall(identity_id, candidate.cap_id)
        return True
    except Exception:
        return False


def safe_install(
    candidate: RegistryCandidate,
    identity_id: str,
    capability_registry,
) -> bool:
    try:
        result = install_capability(candidate, identity_id, capability_registry)
        if not result:
            rollback_install(candidate, identity_id, capability_registry)
        return result
    except Exception:
        rollback_install(candidate, identity_id, capability_registry)
        return False
