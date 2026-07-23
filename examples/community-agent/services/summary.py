import logging
from typing import Dict
from identityos import IdentityObject

logger = logging.getLogger(__name__)


def generate_team_summary(identity: IdentityObject) -> str:
    """Generate a human-readable team status summary using only the SDK."""
    status = identity.team_status()
    reminders = identity.reminders(max_results=10)

    lines = [
        "## Team Status",
        "",
    ]

    active_goals = status.get("goals", [])
    if active_goals:
        lines.append(f"### Goals ({len(active_goals)})")
        for g in active_goals:
            lines.append(f"- **{g['title']}** [{g['priority']}] — {g.get('progress', 0):.0%}")
        lines.append("")
    else:
        lines.append("### Goals\nNo active goals.\n")

    intentions_by_author = status.get("intentions_by_author", {})
    if intentions_by_author:
        lines.append(f"### Active Intentions ({status['total_active_intentions']})")
        for author, ints in intentions_by_author.items():
            lines.append(f"**{author}:**")
            for i in ints:
                lines.append(f"- {i['description']} (due: {i.get('expires_at', '?')[:10]})")
        lines.append("")
    else:
        lines.append("### Intentions\nNo active intentions.\n")

    if reminders:
        overdue = [r for r in reminders if r["label"] == "overdue"]
        if overdue:
            lines.append(f"### Overdue ({len(overdue)})")
            for r in overdue:
                author = r.get("author_id", "unknown")
                lines.append(f"- **{author}:** {r['description']}")
            lines.append("")

        due_today = [r for r in reminders if r["label"] in ("due_today", "approaching", "due_soon")]
        if due_today:
            lines.append(f"### Due Soon ({len(due_today)})")
            for r in due_today:
                author = r.get("author_id", "unknown")
                lines.append(f"- **{author}:** {r['description']} ({r['label'].replace('_', ' ')})")
            lines.append("")

    upcoming = status.get("upcoming_meetings", [])
    if upcoming:
        lines.append(f"### Upcoming Meetings ({len(upcoming)})")
        for m in upcoming:
            lines.append(f"- {m['title']} ({m.get('occurred_at', '?')[:10]})")
        lines.append("")

    recent = status.get("recent_events", [])
    if recent:
        lines.append(f"### Recent Events ({len(recent)})")
        for e in recent[-5:]:
            lines.append(f"- {e['title']} ({e.get('occurred_at', '?')[:16]})")

    return "\n".join(lines)


def generate_digest_message(identity: IdentityObject, period: str = "daily") -> str:
    """Generate a formatted digest message using only the SDK."""
    digest = identity.digest(period=period)

    lines = [
        f"## {digest['label']}",
        "",
    ]

    summary = digest["summary"]
    lines.append(f"**Summary:** {summary['active_goals']} goals, "
                  f"{summary['active_intentions']} intentions, "
                  f"{summary['completed_items']} completed, "
                  f"{summary['pending_reminders']} reminders, "
                  f"{summary['recent_events']} events")
    lines.append("")

    if digest.get("goals"):
        lines.append("### Active Goals")
        for g in digest["goals"]:
            lines.append(f"- {g['title']} [{g['priority']}] — {g.get('progress', 0):.0%} complete")
        lines.append("")

    if digest.get("intentions"):
        lines.append("### Intentions by Person")
        for author, ints in digest["intentions"].items():
            lines.append(f"**{author}:**")
            for i in ints:
                lines.append(f"- {i['description']}")
        lines.append("")

    if digest.get("pending_reminders"):
        overdue = [r for r in digest["pending_reminders"] if r["label"] == "overdue"]
        if overdue:
            lines.append(f"### Overdue ({len(overdue)})")
            for r in overdue:
                lines.append(f"- {r['author_id']}: {r['description']}")
            lines.append("")

    if digest.get("upcoming_meetings"):
        lines.append("### Upcoming Meetings")
        for m in digest["upcoming_meetings"]:
            lines.append(f"- {m['title']}")
        lines.append("")

    if digest.get("recent_timeline_events"):
        lines.append("### Timeline Highlights")
        for e in digest["recent_timeline_events"][-5:]:
            lines.append(f"- {e['title']} ({e.get('occurred_at', '?')[:10]})")
        lines.append("")

    if digest.get("relationship_highlights"):
        lines.append("### Relationship Changes")
        for r in digest["relationship_highlights"]:
            lines.append(f"- {r['entity_id']}: {r['edge_type']} (trust: {r['trust_level']})")

    return "\n".join(lines)
