from __future__ import annotations

from typing import List, Set

from core.prometheus.models import RegistryCandidate


def resolve_dependencies(
    candidate: RegistryCandidate,
    installed_ids: Set[str],
) -> List[str]:
    deps = getattr(candidate, "dependencies", None)
    if not deps:
        return []
    missing = [d for d in deps if d not in installed_ids]
    return missing


def has_missing_dependencies(
    candidate: RegistryCandidate,
    installed_ids: Set[str],
) -> bool:
    return len(resolve_dependencies(candidate, installed_ids)) > 0
