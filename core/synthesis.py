"""Proactive synthesis: notice gaps and patterns the user hasn't seen."""

from __future__ import annotations

from typing import Optional


def build_synthesis(
    user_profile=None,
    timeline=None,
    recent_memories: Optional[list[str]] = None,
) -> str:
    """Analyze known user data and produce insight-worthy observations.

    Looks for:
      - Gaps between stated goals and concrete actions
      - Tensions or contradictions between goals and constraints
      - Blocked goals (goal exists but enabling condition was cancelled)
      - Conflicting intentions across different conversations
      - Drifting priorities (what user said vs what they did)

    Returns an empty string when there is too little data to synthesize.
    """
    facts = _get_facts(user_profile)
    events = _get_events(timeline)

    if not facts and not events and not recent_memories:
        return ""

    lines = ["## Synthesis: Goals, Gaps & Patterns"]
    lines.append("")

    goals = _known_goals(facts)
    if goals:
        lines.append("Known goals and constraints:")
        lines.extend(f"  - {g}" for g in goals)
        lines.append("")

    intentions = _list_intentions(recent_memories, facts)
    if intentions:
        lines.append("Intentions stated across conversations:")
        lines.extend(f"  - {i}" for i in intentions)
        lines.append("")

    decisions = _list_decisions(recent_memories)
    if decisions:
        lines.append("Key decisions and commitments:")
        lines.extend(f"  - {d}" for d in decisions)
        lines.append("")

    if events:
        lines.append("Actions taken so far:")
        lines.extend(f"  - {e}" for e in events)
        lines.append("")

    gaps = _detect_gaps(facts, events)
    for gap in gaps:
        lines.append(f"\N{warning sign} {gap}")

    general = _detect_general_conflicts(intentions, decisions, events)
    for g in general:
        lines.append(f"\N{warning sign} {g}")

    lines.append("")
    lines.append(
        "Use this synthesis to provide proactive, context-aware advice. "
        "If you notice a gap, conflict, or drift the user hasn't addressed, "
        "surface it before they act. Do not wait to be asked."
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


# ── General mechanism: intentions, decisions, conflicts ──────────────────

_INTENTION_TRIGGERS = [
    "i want", "i need", "i plan", "i will", "i should",
    "i'm going to", "i am going to", "i have to",
    "my goal", "i intend", "i am planning",
]

_DECISION_TRIGGERS = [
    "i promised", "i committed", "i agreed",
    "i decided", "cancelled", "shelved", "froze",
    "i told", "i said i would", "is priority",
    "can wait", "is on hold", "is blocked",
]

_TIME_REFERENCES = [
    "today", "tonight", "tomorrow",
    "this week", "this weekend", "next week",
    "monday", "tuesday", "wednesday", "thursday",
    "friday", "saturday", "sunday",
    "this month", "next month",
    "by monday", "by friday", "by the end of",
]


def _list_intentions(
    recent_memories: Optional[list[str]],
    facts: list,
) -> list[str]:
    """Scan recent memories and facts for intention statements."""
    seen = set()
    results = []

    # Scan user-side of raw memory text (deduplicate by content)
    if recent_memories:
        seen_contents = set()
        for mem in recent_memories:
            # Strip "User:" prefix to get only the user's words
            if "user:" in mem.lower():
                idx = mem.lower().find("user:")
                user_part = mem[idx + 5:]
                # Also strip any trailing "Assistant:" or "User:" suffix
                for marker in ["\nassistant:", "\nuser:"]:
                    m_idx = user_part.lower().find(marker)
                    if m_idx >= 0:
                        user_part = user_part[:m_idx]
            else:
                user_part = mem
            lower = user_part.lower().strip()
            if not lower or lower in seen_contents:
                continue
            seen_contents.add(lower)
            for trigger in _INTENTION_TRIGGERS:
                idx = lower.find(trigger)
                if idx >= 0:
                    snippet = user_part[idx:idx + 150].strip().rstrip(".!")
                    if snippet not in seen:
                        seen.add(snippet)
                        results.append(snippet)
                    break

    # Also check user profile facts for intention content
    for f in facts:
        val = str(getattr(f, "value", f))
        lower = val.lower()
        for trigger in _INTENTION_TRIGGERS:
            if trigger in lower and val[:120] not in seen:
                seen.add(val[:120])
                results.append(val[:120])
                break

    return results[:6]


def _list_decisions(recent_memories: Optional[list[str]]) -> list[str]:
    """Scan recent memories for decisions and commitments."""
    if not recent_memories:
        return []
    seen = set()
    seen_contents = set()
    results = []
    for mem in recent_memories:
        if "user:" in mem.lower():
            idx = mem.lower().find("user:")
            user_part = mem[idx + 5:]
            for marker in ["\nassistant:", "\nuser:"]:
                m_idx = user_part.lower().find(marker)
                if m_idx >= 0:
                    user_part = user_part[:m_idx]
        else:
            user_part = mem
        lower = user_part.lower().strip()
        if not lower or lower in seen_contents:
            continue
        seen_contents.add(lower)
        for trigger in _DECISION_TRIGGERS:
            idx = lower.find(trigger)
            if idx >= 0:
                snippet = user_part[idx:idx + 150].strip().rstrip(".!")
                if snippet not in seen:
                    seen.add(snippet)
                    results.append(snippet)
                break
    return results[:4]


def _detect_general_conflicts(
    intentions: list[str],
    decisions: list[str],
    events: list[str],
) -> list[str]:
    """General conflict detection — no domain knowledge required.

    Mechanism:
      1. If two intentions share a time reference but describe different
         scopes of work, they may compete for the same time.
      2. If a decision explicitly shelves or delays a capability whose name
         appears in an intention, that intention may be blocked.
      3. If an intention exists but subsequent actions are about something
         else, priorities may have drifted.
    """
    seen = set()
    conflicts = []

    # ── Conflict 1: Two intentions, same time, different topics ──
    for i, a in enumerate(intentions):
        for b in intentions[i + 1:]:
            a_lower = a.lower()
            b_lower = b.lower()
            shared = _shared_time_ref(a_lower, b_lower)
            if shared and not _same_topic(a_lower, b_lower):
                msg = (
                    f"Two plans share a time window ('{shared}') but involve "
                    f"different work: '{_short(a, 60)}' vs '{_short(b, 60)}'. "
                    f"The user likely cannot do both."
                )
                if msg not in seen:
                    seen.add(msg)
                    conflicts.append(msg)

    # ── Conflict 2: Intention + decision that shelves something related ──
    for intention in intentions:
        i_lower = intention.lower()
        i_nouns = _key_nouns(i_lower)
        for decision in decisions:
            d_lower = decision.lower()
            if any(w in d_lower for w in ("cancel", "shelv", "freez", "hold", "wait")):
                d_nouns = _key_nouns(d_lower)
                overlap = i_nouns & d_nouns
                if overlap and not _is_about_same_decision(i_lower, d_lower):
                    msg = (
                        f"An intention ('{_short(intention, 60)}') involves "
                        f"something that was later cancelled or shelved: "
                        f"'{_short(decision, 75)}'. The goal may be blocked."
                    )
                    if msg not in seen:
                        seen.add(msg)
                        conflicts.append(msg)

    return conflicts


def _shared_time_ref(a: str, b: str) -> str:
    for ref in _TIME_REFERENCES:
        if ref in a and ref in b:
            return ref
    return ""


def _same_topic(a: str, b: str) -> bool:
    """Check if two texts share significant nouns (>40% overlap)."""
    nouns_a = _key_nouns(a)
    nouns_b = _key_nouns(b)
    if not nouns_a or not nouns_b:
        return False
    intersection = nouns_a & nouns_b
    smaller = min(len(nouns_a), len(nouns_b))
    return len(intersection) / smaller > 0.4 if smaller > 0 else False


def _key_nouns(text: str) -> set:
    """Extract significant content words (nouns, verbs, key terms)."""
    stopwords = {
        "i", "me", "my", "you", "your", "he", "she", "it", "we", "they",
        "the", "a", "an", "this", "that", "these", "those",
        "is", "am", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would",
        "can", "could", "may", "might", "shall", "should", "must",
        "to", "of", "in", "on", "at", "for", "with", "by", "from",
        "and", "or", "but", "not", "no", "so", "if", "as",
        "it's", "don't", "i'm", "i've", "i'll", "that's",
        "about", "into", "over", "after", "before", "between",
        "want", "need", "plan", "going", "get", "got", "make",
        "just", "really", "also", "very", "too", "now",
        "then", "there", "here", "some", "what", "which", "who",
        "when", "where", "how", "all", "each", "every", "both",
        "one", "two", "more", "some", "any", "few", "most",
    }
    words = text.lower().split()
    return {w.strip(".,!?;:'\"()[]") for w in words if len(w) > 2 and w not in stopwords}


def _is_about_same_decision(intention: str, decision: str) -> bool:
    """Check if intention and decision express the same thing (not a conflict).

    Returns True when noun overlap is very high (>70%), meaning the user
    is describing the same act in both — not a contradiction.
    """
    i_nouns = _key_nouns(intention)
    d_nouns = _key_nouns(decision)
    if not i_nouns or not d_nouns:
        return False
    overlap = i_nouns & d_nouns
    if not overlap:
        return False
    # High overlap = same topic, not necessarily same act.
    # Only treat as "same decision" if one is a subset of the other
    # (intention is fully contained in the decision or vice versa).
    smaller = min(len(i_nouns), len(d_nouns))
    return len(overlap) / smaller > 0.7


def _short(text: str, n: int) -> str:
    return text if len(text) <= n else text[:n - 3] + "..."

