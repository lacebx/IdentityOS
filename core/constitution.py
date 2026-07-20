"""
core/constitution.py

Identity Constitution — the runtime's authoritative source of truth about who
the identity is, rendered every conversation BEFORE memories.

The Constitution contains:
- Core values (immutable)
- Stable beliefs (confidence >= threshold)
- Active preferences
- Traits with scores
- Communication style
- Goals
- Key relationships
- Identity age
- Evolution history summary
- Identity stability score
- Identity confidence score

The adapter receives this before memories.
The Constitution IS the identity. Memories merely explain why it became that way.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .timeline import TimelineRegistry

from .identity_facts import FactDomain, FactStatus, FactStore, IdentityFact
from .identity import IdentitySpec, Trait


def build_constitution(
    identity: IdentitySpec,
    fact_store: Optional[FactStore] = None,
    interaction_count: int = 0,
    mutation_count: int = 0,
    timeline: Any = None,
) -> str:
    """
    Build the Identity Constitution — a structured text block that represents
    the runtime's authoritative knowledge of who the identity is.

    This is rendered into the context BEFORE memories so the adapter never
    has to guess or remember identity facts.
    """
    lines: List[str] = []
    lines.append(f"# Identity Constitution: {identity.name}")
    lines.append("")

    # Identity Info
    lines.append("## Identity")
    lines.append(f"  Age: {_format_age(identity.created_at)}")
    if identity.persona:
        lines.append(f"  Persona: {identity.persona}")
    if identity.role:
        lines.append(f"  Role: {identity.role}")
    if identity.tagline:
        lines.append(f"  Tagline: {identity.tagline}")
    lines.append("")

    # Core Values
    if identity.core_values:
        lines.append("## Core Values (Immutable)")
        for cv in identity.core_values:
            label = f"{cv.name}" + (f" — {cv.description}" if cv.description else "")
            strength = f"strength={cv.strength:.1f}" if cv.strength < 1.0 else "foundational"
            lines.append(f"  {label} ({strength})")
        lines.append("")

    # Active Preferences from fact store
    if fact_store:
        prefs = fact_store.by_domain(FactDomain.PREFERENCE)
        active_prefs = [f for f in prefs if f.status == FactStatus.ACTIVE]
        if active_prefs:
            lines.append("## Preferences")
            for f in sorted(active_prefs, key=lambda x: x.last_confirmed, reverse=True):
                label = f.field.split(".")[-1].replace("_", " ")
                lines.append(f"  {label}: {f.value}")
                details = []
                if f.confidence >= 0.8:
                    details.append(f"confidence={f.confidence:.0%}")
                if f.times_reinforced > 0:
                    details.append(f"reinforced={f.times_reinforced}x")
                if f.reasons and len(f.reasons) <= 3:
                    details.append(f"reason={', '.join(f.reasons[:3])}")
                if details:
                    lines.append(f"    ({'; '.join(details)})")
            lines.append("")

        # Stable Beliefs
        beliefs = fact_store.by_domain(FactDomain.BELIEF)
        active_beliefs = [f for f in beliefs if f.status == FactStatus.ACTIVE]
        if active_beliefs:
            lines.append("## Beliefs")
            for f in sorted(active_beliefs, key=lambda x: x.confidence, reverse=True):
                if f.confidence >= 0.7:
                    lines.append(f"  - {f.value}")
            lines.append("")

    # Traits — prefer FactStore canonical traits, fall back to IdentitySpec
    trait_facts: List[IdentityFact] = []
    if fact_store:
        trait_facts = [f for f in fact_store.by_domain(FactDomain.TRAIT)
                       if f.status == FactStatus.ACTIVE]
    if trait_facts:
        lines.append("## Traits")
        for f in sorted(trait_facts, key=lambda x: x.confidence, reverse=True):
            val = f.value
            if isinstance(val, dict):
                name = val.get("name", f.field.split(".")[-1])
                score = val.get("score", 0.5)
                desc = val.get("description", "")
            else:
                name = f.field.split(".")[-1]
                score = 0.5
                desc = str(val)
            bar = _score_bar(score)
            detail = f" — {desc}" if desc else ""
            lines.append(f"  {name}: {bar} ({score:.2f}){detail}")
        lines.append("")
    elif identity.traits:
        lines.append("## Traits")
        for t in sorted(identity.traits, key=lambda x: x.score, reverse=True):
            bar = _score_bar(t.score)
            desc = f" — {t.description}" if t.description else ""
            lines.append(f"  {t.name}: {bar} ({t.score:.2f}){desc}")
        lines.append("")

    # Communication Style
    if identity.communication_style:
        lines.append("## Communication Style")
        lines.append(f"  {identity.communication_style}")
        lines.append("")

    # Goals
    if fact_store:
        goals = fact_store.by_domain(FactDomain.GOAL)
        active_goals = [f for f in goals if f.status == FactStatus.ACTIVE]
        if active_goals:
            lines.append("## Current Goals")
            for f in active_goals:
                lines.append(f"  - {f.value}")
            lines.append("")

    # Relationships
    if fact_store:
        rels = fact_store.by_domain(FactDomain.RELATIONSHIP)
        active_rels = [f for f in rels if f.status == FactStatus.ACTIVE]
        if active_rels:
            lines.append("## Relationships")
            for f in active_rels:
                target = f.field.split(".")[-1].replace("_", " ")
                trust_level = "high" if f.confidence >= 0.8 else "medium" if f.confidence >= 0.5 else "developing"
                lines.append(f"  {target}: {trust_level} trust")
            lines.append("")

    # Evolution Summary
    lines.append("## Identity Evolution")
    lines.append(f"  Interactions: {interaction_count}")
    lines.append(f"  Total Mutations: {mutation_count}")

    if fact_store:
        total_facts = len(fact_store.all())
        active_facts = len(fact_store.active())
        pending_facts = len(fact_store.by_status(FactStatus.PENDING))
        contested_facts = len(fact_store.by_status(FactStatus.CONTESTED))
        lines.append(f"  Active Facts: {active_facts}")
        lines.append(f"  Pending Facts: {pending_facts}")
        lines.append(f"  Contested Facts: {contested_facts}")
        lines.append(f"  Total Facts (lifecycle): {total_facts}")

    stability = _compute_stability(identity, fact_store)
    lines.append(f"  Identity Stability: {stability:.1f}%")
    lines.append("")

    return "\n".join(lines)


def _format_age(created_at: datetime) -> str:
    now = datetime.now(timezone.utc)
    delta = now - created_at
    days = delta.days
    if days < 1:
        return "less than a day"
    elif days < 30:
        return f"{days} days"
    elif days < 365:
        months = days // 30
        return f"{months} month{'s' if months > 1 else ''}"
    else:
        years = days // 365
        return f"{years} year{'s' if years > 1 else ''}"


def _score_bar(score: float, width: int = 10) -> str:
    filled = max(0, min(width, int(score * width)))
    return "█" * filled + "░" * (width - filled)


def _compute_stability(identity: IdentitySpec,
                       fact_store: Optional[FactStore] = None) -> float:
    """
    Compute identity stability as a percentage.

    Factors:
    - Ratio of active facts to total facts (higher = more stable)
    - Ratio of stable confidence facts
    - Age (older = more stable)
    - Trait variance (lower variance = more stable)
    """
    scores: List[float] = []

    if fact_store and len(fact_store) > 0:
        total = len(fact_store)
        active = len(fact_store.by_status(FactStatus.ACTIVE))
        contested = len(fact_store.by_status(FactStatus.CONTESTED))
        pending = len(fact_store.by_status(FactStatus.PENDING))
        scores.append(active / max(total, 1) * 30)
        scores.append(max(0, (1 - contested / max(total, 1)) * 20)
                      if total > 0 else 20)
        scores.append(max(0, (1 - pending / max(total, 1)) * 10)
                      if total > 0 else 10)
        high_conf = sum(1 for f in fact_store.all() if f.confidence >= 0.8)
        scores.append((high_conf / max(total, 1)) * 20 if total > 0 else 20)

    # Age contributes up to 10 points
    age_hours = (datetime.now(timezone.utc) - identity.created_at).total_seconds() / 3600
    scores.append(min(10, age_hours / 24 * 2))

    # Trait variance (lower = more stable, contributes up to 10)
    trait_scores = []
    if fact_store:
        trait_facts = fact_store.by_domain(FactDomain.TRAIT)
        for f in trait_facts:
            if isinstance(f.value, dict) and "score" in f.value:
                trait_scores.append(float(f.value["score"]))
    if not trait_scores:
        trait_scores = [t.score for t in identity.traits]
    if trait_scores:
        mean = sum(trait_scores) / len(trait_scores)
        variance = sum((s - mean) ** 2 for s in trait_scores) / len(trait_scores)
        scores.append(max(0, 10 - variance * 20))

    return min(100, sum(scores))
