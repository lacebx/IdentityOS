"""
core/operations/ambassador.py

Aster Ambassador — persistent objectives and social-state reporting.

An ambassador is an operator identity that *inhabits* external communities:
it observes, learns who matters, forms durable relationships, contributes
useful conversation, discovers collaborators/resources/opportunities, follows
up over time, and escalates only meaningful developments to its principal.

This module holds the ambassador's persistent objectives (recorded once in
operator state so restarts never reset them) and the social-status view the
principal uses to supervise without watching every cycle.
"""

from __future__ import annotations

from typing import Any

from .models import (
    MessageDirection,
    MessageStatus,
    NotificationEntry,
    ProvenancePhase,
    RelationshipStatus,
    utcnow,
)

OBJECTIVES_NAMESPACE = "operations.objectives"

AMBASSADOR_OBJECTIVES: list[dict[str, Any]] = [
    {
        "id": "ecosystem",
        "focus": "IdentityOS ecosystem",
        "description": (
            "Find and understand AI agents, agent-framework builders, identity and "
            "persistence researchers, MCP/A2A builders, autonomous-agent researchers, "
            "and people working on agent memory or interoperability — understand their "
            "work before engaging."
        ),
        "signals": [
            "agent framework", "agent memory", "agent interoperability", "MCP",
            "A2A", "autonomous agents", "identity", "persistence", "provenance",
        ],
    },
    {
        "id": "collaboration",
        "focus": "Collaboration",
        "description": (
            "Find people or agents who could contribute code, test IdentityOS, "
            "integrate their project, research with us, review architecture, or "
            "introduce us to relevant communities."
        ),
        "signals": [
            "contribute", "contribution", "collaborate", "integration",
            "research", "review", "open source", "maintainer",
        ],
    },
    {
        "id": "resources",
        "focus": "Resources",
        "description": (
            "Look for legitimate opportunities involving AI/API credits, compute, "
            "research grants, academic collaborations, accelerators, open-source "
            "sponsorship, cloud credits, or funding. Never treat every person as a "
            "fundraising target."
        ),
        "signals": [
            "credits", "compute", "grant", "accelerator", "sponsorship",
            "funding", "cloud credits", "research program",
        ],
    },
    {
        "id": "relationships",
        "focus": "Relationships",
        "description": (
            "The most important long-term objective: remember people, remember what "
            "they care about, remember prior conversations, notice their future "
            "activity, help when appropriate, and follow up contextually. Optimize "
            "for durable useful relationships, never for message count."
        ),
        "signals": ["follow up", "conversation", "context", "remember", "help"],
    },
]


def ensure_objectives(store: Any) -> list[dict[str, Any]]:
    """Persist the ambassador objectives once; returns the active objectives.

    Restarts never reset them: the record is durable operator state.
    """
    storage = store._storage
    raw = storage.load(store.identity_id, OBJECTIVES_NAMESPACE) or {}
    objectives = raw.get("objectives")
    if objectives:
        return objectives
    record = {
        "objectives": AMBASSADOR_OBJECTIVES,
        "created_at": utcnow().isoformat(),
    }
    storage.save(store.identity_id, OBJECTIVES_NAMESPACE, record)
    return AMBASSADOR_OBJECTIVES


def record_objectives_provenance(engine: Any) -> None:
    """Record a provenance entry the first time objectives are persisted."""
    store = engine.store
    raw = store._storage.load(store.identity_id, OBJECTIVES_NAMESPACE) or {}
    if raw.get("objectives_provenance_recorded"):
        return
    raw["objectives_provenance_recorded"] = True
    store._storage.save(store.identity_id, OBJECTIVES_NAMESPACE, raw)
    store.append_provenance(
        ProvenanceEntry(
            phase=ProvenancePhase.CONTROL,
            summary=f"ambassador objectives recorded ({len(AMBASSADOR_OBJECTIVES)} objectives)",
            action="ensure_objectives",
            result=", ".join(o["id"] for o in AMBASSADOR_OBJECTIVES),
            refs={"objectives": [o["id"] for o in AMBASSADOR_OBJECTIVES]},
        )
    )


def ambassador_status(engine: Any) -> dict[str, Any]:
    """The social-status view for the principal (never fabricates availability).

    Reports presence from the surfaces actually wired, relationship quality,
    active conversations, opportunities by focus, and what awaits whom.
    """
    store = engine.store
    relationships = store.list_relationships()
    opportunities = store.list_opportunities()
    messages = store.list_messages()
    notifications = store.list_notifications()

    presence: dict[str, Any] = {}
    for surface in getattr(engine, "_surfaces", []):
        try:
            presence[surface.name] = surface.status()
        except Exception as exc:
            presence[surface.name] = {"name": getattr(surface, "name", "unknown"), "error": str(exc)}

    active = [
        r for r in relationships
        if r.status in (RelationshipStatus.OUTREACH_SENT, RelationshipStatus.ENGAGED)
    ]
    dormant = [r for r in relationships if r.status is RelationshipStatus.DORMANT]
    promising = [
        r for r in active
        if (r.opportunity_id or r.commitments or len(r.message_ids) >= 2)
    ]
    observed_only = [
        r for r in relationships
        if r.status is RelationshipStatus.NEW and not r.message_ids
    ]

    awaiting_aster = [
        r for r in relationships
        if r.last_inbound_at and (not r.last_outbound_at or r.last_inbound_at > r.last_outbound_at)
    ]
    awaiting_others = [
        r for r in relationships
        if r.last_outbound_at and (not r.last_inbound_at or r.last_outbound_at > r.last_inbound_at)
    ]
    needs_arsene = [n for n in notifications if not n.read]

    by_focus: dict[str, int] = {}
    for opportunity in opportunities:
        focus = (opportunity.category or "other").split(".")[0]
        by_focus[focus] = by_focus.get(focus, 0) + 1

    by_status: dict[str, int] = {}
    for opportunity in opportunities:
        by_status[opportunity.status.value] = by_status.get(opportunity.status.value, 0) + 1
    # Top actionable items only: qualified/contacted records with a route.
    top_opportunities = [
        {
            "id": o.id,
            "name": (o.target_name or o.organization)[:80],
            "category": o.category,
            "status": o.status.value,
            "url": (o.contact_url or o.metadata.get("source_urls", [""])[0] if o.metadata else (o.contact_url or "")),
        }
        for o in opportunities
        if o.status.value in ("qualified", "contacted", "engaged")
    ][:6]

    conversations = [
        {
            "relationship_id": r.id,
            "display_name": r.display_name or r.organization,
            "status": r.status.value,
            "messages": len(r.message_ids),
            "next_action": r.next_action,
            "follow_up_due_at": r.follow_up_due_at,
        }
        for r in active + dormant
    ]

    recent_activity = [
        p.to_dict() for p in store.list_provenance(limit=12)
    ]

    return {
        "objectives": [o["id"] for o in ensure_objectives(store)],
        "presence": presence,
        "relationships": {
            "known": len(relationships),
            "active": len(active),
            "promising": len(promising),
            "dormant": len(dormant),
            "observed_only": len(observed_only),
        },
        "active_conversations": conversations,
        "opportunities": {
            "total": len(opportunities),
            "by_focus": by_focus,
            "by_status": by_status,
            "top": top_opportunities,
        },
        "outreach_today": {
            "cold_contacts": store.budget().cold_outreach,
            "follow_ups": store.budget().follow_ups,
        },
        "awaiting": {
            "aster": len(awaiting_aster),
            "others": len(awaiting_others),
            "needs_arsene": len(needs_arsene),
        },
        "recent_meaningful_activity": recent_activity,
        "message_totals": {
            "outbound": sum(1 for m in messages if m.direction is MessageDirection.OUTBOUND),
            "inbound": sum(1 for m in messages if m.direction is MessageDirection.INBOUND),
            "would_send": sum(1 for m in messages if m.status is MessageStatus.WOULD_SEND),
        },
    }
