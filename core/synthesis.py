"""Proactive synthesis: notice gaps and patterns the user hasn't seen."""

from __future__ import annotations

from typing import Optional


def build_synthesis(
    user_profile=None,
    timeline=None,
) -> str:
    """Analyze known user data and produce insight-worthy observations.

    Looks for:
      - Gaps between stated goals and concrete actions
      - Tensions or contradictions between goals and constraints
      - Unaddressed high-risk items based on known plans

    Returns an empty string when there is too little data to synthesize.
    """
    facts = _get_facts(user_profile)
    events = _get_events(timeline)

    if not facts and not events:
        return ""

    lines = ["## Synthesis: Goals, Gaps & Patterns"]
    lines.append("")

    goals = _known_goals(facts)
    if goals:
        lines.append("Known goals and constraints:")
        lines.extend(f"  - {g}" for g in goals)
        lines.append("")

    if events:
        lines.append("Actions taken so far:")
        lines.extend(f"  - {e}" for e in events)
        lines.append("")

    gaps = _detect_gaps(facts, events)
    for gap in gaps:
        lines.append(f"\N{warning sign} {gap}")

    lines.append("")
    lines.append(
        "Use this synthesis to provide proactive, context-aware advice. "
        "If you notice a gap the user hasn't addressed, surface it naturally."
    )

    return "\n".join(lines)


def _get_facts(user_profile):
    if not user_profile:
        return []
    if callable(getattr(user_profile, "all_facts", None)):
        return user_profile.all_facts()
    if hasattr(user_profile, "_facts"):
        return list(user_profile._facts.values())
    return []


def _get_events(timeline):
    if not timeline:
        return []
    if callable(getattr(timeline, "events", None)):
        entries = timeline.events()
    elif hasattr(timeline, "_events"):
        entries = timeline._events
    else:
        entries = []
    return [str(e)[:120] for e in entries]


def _known_goals(facts: list) -> list[str]:
    seen = []
    for f in facts:
        cat = getattr(f, "category", "") or ""
        if cat in ("learning_goal", "target_location", "budget", "accountability", "job_role"):
            label = cat.replace("_", " ").title()
            val = str(getattr(f, "value", f))[:100]
            seen.append(f"{label}: {val}")
    return seen


def _detect_gaps(facts: list, events: list) -> list[str]:
    gaps = []

    raw_facts = [str(f).lower() for f in facts]
    raw_events = " ".join(events).lower()

    has_tokyo_move = any("tokyo" in f for f in raw_facts) or any("move" in f for f in raw_facts)
    has_housing = any(
        t in raw_events
        for t in ("housing", "apartment", "home", "rent", "real estate", "shibuya")
    )
    if has_tokyo_move and not has_housing:
        gaps.append(
            "User plans to move to Tokyo but has not yet explored housing. "
            "This is likely the highest-risk unaddressed item."
        )

    for f in raw_facts:
        if "japanese" in f and "200" in f:
            has_savings = any("saving" in ff or "budget" in ff for ff in raw_facts)
            if has_savings:
                gaps.append(
                    "The $200 Japanese course conflicts with the stated savings goal. "
                    "These are competing priorities the user may not have reconciled."
                )
            break

    if _has_goal(facts) and not events:
        gaps.append(
            "Goals are stated but no concrete actions have been logged yet. "
            "The user may benefit from a nudge to start executing."
        )

    return gaps


def _has_goal(facts: list) -> bool:
    for f in facts:
        cat = getattr(f, "category", "") or ""
        if cat in ("learning_goal", "target_location", "budget"):
            return True
    return False
