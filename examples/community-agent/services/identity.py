import logging
from typing import Optional

from identityos import Identity, IdentityObject

logger = logging.getLogger(__name__)


def load_or_create_identity(identity_id: str, storage_path: str = ".identity_store") -> IdentityObject:
    """Load an existing identity or create a new one."""
    try:
        identity = Identity.load(identity_id, storage_path=storage_path)
        logger.info("Identity loaded: %s (v%s)", identity.name, identity.version)
        return identity
    except Exception:
        logger.info("Identity '%s' not found, creating...", identity_id)
        identity = Identity.create(
            name=identity_id,
            identity_id=identity_id,
            persona="community_manager",
            role="facilitator",
            storage_path=storage_path,
        )
        logger.info("Identity created: %s (v%s)", identity.name, identity.version)
        return identity


def describe_identity(identity: IdentityObject) -> str:
    """Generate a human-readable /about response."""
    desc = identity.describe()
    lines = [
        f"**{desc['name']}** v{desc['version']}",
        f"Persona: {desc['persona']}",
        f"Role: {desc['role']}",
        f"Status: {desc['status']}",
        "",
        f"**Goals:** {desc['active_goals']} active",
        f"**Intentions:** {desc['active_intentions']} active",
        f"**Memories:** {desc['memories']} stored",
        f"**Relationships:** {desc['relationships']} established",
        f"**Timeline Events:** {desc['timeline_events']} recorded",
        f"Created: {desc['created_at'][:10]}",
        "",
        "Powered by **IdentityOS**",
    ]
    return "\n".join(lines)


def get_constitution_text(identity: IdentityObject) -> str:
    """Generate a /constitution response using only the SDK."""
    con = identity.constitution()
    lines = [
        "## IdentityOS Constitution",
        "",
    ]
    if con.get("constitution"):
        lines.append(con["constitution"][:1500])
        lines.append("")

    if con.get("laws"):
        lines.append(f"### Laws ({len(con['laws'])})")
        for name, text in con["laws"].items():
            first_line = text.strip().split("\n")[0] if text.strip() else ""
            lines.append(f"**{name}:** {first_line[:120]}")
            lines.append("")

    return "\n".join(lines)


def get_evidence_text(identity: IdentityObject, entity_id: str) -> str:
    """Generate an evidence report for a given entity using only the SDK."""
    ev = identity.evidence(entity_id)
    prov = identity.provenance(entity_id)
    conf = identity.confidence(entity_id)

    lines = [
        f"### Evidence for: `{entity_id}`",
        "",
    ]

    if prov.get("value"):
        lines.append(f"**Value:** {prov['value']}")
        lines.append(f"**Confidence:** {prov.get('confidence_label', 'unknown').upper()} ({prov.get('confidence', 0):.0%})")
        lines.append(f"**Times reinforced:** {prov.get('times_reinforced', 0)}")
        lines.append(f"**Contradictions:** {prov.get('contradictions', 0)}")
        lines.append(f"**Status:** {prov.get('status', 'unknown')}")
        lines.append(f"**First seen:** {prov.get('first_seen', 'unknown')}")
        lines.append("")

    if conf.get("label"):
        lines.append(f"**Confidence Rating:** {conf['label'].upper()} ({conf.get('confidence', 0):.0%})")
        lines.append(f"**Description:** {conf.get('description', '')}")
        lines.append("")

    if ev:
        lines.append(f"**Evidence Chain ({len(ev)} items):**")
        for item in ev:
            lines.append(f"- {item.get('description', '')} (source: {item.get('source', 'unknown')})")
        lines.append("")

    if not ev and not prov.get("value"):
        lines.append("No evidence found for this entity.")

    return "\n".join(lines)
