from identityos import IdentityObject


def format_constitution(identity: IdentityObject) -> str:
    """Format the IdentityOS Constitution for display."""
    con = identity.constitution()
    lines = ["## IdentityOS Constitution", ""]
    if con.get("constitution"):
        text = con["constitution"][:1500]
        lines.append(text)
        lines.append("")
    if con.get("laws"):
        lines.append(f"### Laws ({len(con['laws'])})")
        for name, text in con["laws"].items():
            first = text.strip().split("\n")[0] if text.strip() else ""
            lines.append(f"**{name}:** {first[:120]}")
    return "\n".join(lines)
