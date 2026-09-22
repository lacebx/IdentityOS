"""Generic gap → Executive acquisition adapter for operator identities.

The operations engine's capability-gap phase asks for a *skill* (e.g.
``culture_commons.observe``) and translates it to a *capability* (e.g.
``culture_commons``) through a data-driven prefix table.  The resolution then
flows through the existing durable Executive acquisition lifecycle
(``get_acquisition_provider(storage).request_acquisition(...)``) — the same path
Registry Manager uses — never through a planner special-case and never through a
second, parallel acquisition system.

The adapter decides nothing about *how* to acquire.  It only resolves "which
capability provides this skill" and hands the request to the registered
Executive provider.  Success here means a durable acquisition task was created
or already exists (a runtime fact); it does not claim the capability is
operational.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

# skill-name prefix -> capability id that provides those skills
SKILL_PREFIX_PROVIDERS: tuple[tuple[str, str], ...] = (
    ("mcp.", "mcp"),
    ("a2a.", "a2a"),
    ("culture_commons.", "culture_commons"),
    ("cc.", "culture_commons"),
)


def provider_for(skill: str) -> Optional[str]:
    for prefix, cap_id in SKILL_PREFIX_PROVIDERS:
        if skill.startswith(prefix):
            return cap_id
    return None


def build_gap_acquisition(
    storage: Any,
    identity_id: str,
    *,
    capability_registry: Any = None,
) -> Callable[[str], tuple[bool, str]]:
    """Return an acquisition callable matching CapabilityGapDetector's contract.

    ``__call__(skill) -> (ok, detail)``: resolves the provider capability and
    submits a durable acquisition request to the registered Executive.  If no
    Executive is registered the gap is reported unresolved (honest failure).
    """

    def acquire(skill: str) -> tuple[bool, str]:
        cap_id = provider_for(skill)
        if cap_id is None:
            return (False, f"no interop provider knows skill '{skill}'")
        if capability_registry is not None:
            try:
                if capability_registry.get(identity_id, cap_id) is not None:
                    return (True, f"capability '{cap_id}' already installed")
            except Exception:
                pass
        from core.acquisition import get_acquisition_provider

        provider = get_acquisition_provider(storage)
        if provider is None:
            return (False, f"no durable Executive registered to acquire '{cap_id}'")
        goal = f"Install and verify the {cap_id} capability"
        task, created = provider.request_acquisition(
            identity_id=identity_id,
            capability_id=cap_id,
            goal=goal,
            original_request=goal,
        )
        if not created:
            return (True, f"acquisition already in progress (task {task.task_id})")
        return (True, f"acquisition task {task.task_id} created for '{cap_id}'")

    return acquire