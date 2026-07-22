from identityos import IdentityObject


def generate_team_status(identity: IdentityObject) -> str:
    """Generate a human-readable team status summary using only the SDK."""
    status = identity.team_status()
    reminders = identity.reminders(max_results=10)

    lines = ["## Team Status", ""]

    goals = status.get("goals", [])
    if goals:
        lines.append(f"### Goals ({len(goals)})")
        for g in goals:
            lines.append(f"- **{g['title']}** [{g['priority']}]")
        lines.append("")

    by_author = status.get("intentions_by_author", {})
    if by_author:
        lines.append(f"### Active Intentions ({status['total_active_intentions']})")
        for author, ints in by_author.items():
            lines.append(f"**{author}:**")
            for i in ints:
                lines.append(f"- {i['description']}")
        lines.append("")

    overdue = [r for r in reminders if r["label"] == "overdue"]
    if overdue:
        lines.append(f"### Overdue ({len(overdue)})")
        for r in overdue:
            lines.append(f"- {r['author_id']}: {r['description']}")
        lines.append("")

    meetings = status.get("upcoming_meetings", [])
    if meetings:
        lines.append(f"### Upcoming Meetings ({len(meetings)})")
        for m in meetings:
            lines.append(f"- {m['title']}")

    recent = status.get("recent_events", [])
    if recent:
        lines.append(f"### Recent Events ({len(recent)})")
        for e in recent[-5:]:
            lines.append(f"- {e['title']}")

    return "\n".join(lines)


def generate_digest(identity: IdentityObject, period: str = "daily") -> str:
    """Generate a formatted digest using only the SDK."""
    digest = identity.digest(period=period)
    lines = [f"## {digest['label']}", ""]
    s = digest["summary"]
    lines.append(
        f"**Summary:** {s['active_goals']} goals, {s['active_intentions']} intentions, "
        f"{s['completed_items']} completed, {s['pending_reminders']} reminders"
    )
    lines.append("")

    for g in digest.get("goals", []):
        lines.append(f"- {g['title']} [{g['priority']}]")

    if digest.get("pending_reminders"):
        overdue = [r for r in digest["pending_reminders"] if r["label"] == "overdue"]
        if overdue:
            lines.append("\n### Overdue")
            for r in overdue:
                lines.append(f"- {r['author_id']}: {r['description']}")

    for e in digest.get("recent_timeline_events", [])[-5:]:
        lines.append(f"- {e['title']} ({e.get('occurred_at', '?')[:10]})")

    return "\n".join(lines)


def format_evidence(identity: IdentityObject, entity_id: str) -> str:
    """Format evidence for a specific entity."""
    ev = identity.evidence(entity_id)
    prov = identity.provenance(entity_id)
    conf = identity.confidence(entity_id)
    lines = [f"### Evidence for `{entity_id}`", ""]
    if prov.get("value"):
        lines.append(f"**Value:** {prov['value']}")
        lines.append(f"**Confidence:** {prov.get('confidence_label', '?')} ({prov.get('confidence', 0):.0%})")
    if conf.get("label"):
        lines.append(f"**Rating:** {conf['label']} ({conf.get('confidence', 0):.0%})")
    if ev:
        lines.append(f"\n**Chain ({len(ev)} items):**")
        for item in ev:
            lines.append(f"- {item.get('description', '?')}")
    if not ev and not prov.get("value"):
        lines.append("No evidence found.")
    return "\n".join(lines)
