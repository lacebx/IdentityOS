from __future__ import annotations

from typing import List, Optional

from core.prometheus.models import CapabilityNeed, RegistryCandidate


def rank_candidates(
    candidates: List[RegistryCandidate],
    need: CapabilityNeed,
) -> List[RegistryCandidate]:
    for c in candidates:
        score = c.relevance_score

        if c.author in ("IdentityOS", "identityos"):
            score += 0.1

        if c.version:
            try:
                parts = c.version.split(".")
                major = int(parts[0]) if parts else 0
                minor = int(parts[1]) if len(parts) > 1 else 0
                score += min(0.1, (major * 0.02) + (minor * 0.01))
            except (ValueError, IndexError):
                pass

        num_skills = len(c.skills)
        if num_skills > 0:
            score += min(0.05, num_skills * 0.01)

        c.relevance_score = round(min(1.0, score), 3)

    candidates.sort(key=lambda c: c.relevance_score, reverse=True)
    return candidates


def pick_best(candidates: List[RegistryCandidate]) -> Optional[RegistryCandidate]:
    if not candidates:
        return None
    return candidates[0]
