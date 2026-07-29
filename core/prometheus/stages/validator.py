from __future__ import annotations

from typing import Optional, Set

from core.prometheus.models import RegistryCandidate


def validate_capability(
    candidate: RegistryCandidate,
    identity_id: str,
    capability_registry,
) -> bool:
    try:
        caps = capability_registry.list(identity_id)
        for c in caps:
            if hasattr(c, 'id') and c.id == candidate.cap_id:
                try:
                    skills = c.skills()
                    return len(skills) > 0
                except Exception:
                    return False
            if hasattr(c, 'name') and c.name == candidate.cap_id:
                try:
                    skills = c.skills()
                    return len(skills) > 0
                except Exception:
                    return False
        return False
    except Exception:
        return False


def verify_skills_available(
    candidate: RegistryCandidate,
    identity_id: str,
    capability_registry,
) -> bool:
    try:
        for skill in candidate.skills:
            skill_name = skill.get("name")
            if not skill_name:
                continue
            can_use = capability_registry.can(
                identity_id, f"{candidate.cap_id}.{skill_name}"
            )
            if not can_use:
                return False
        return True
    except Exception:
        return True
