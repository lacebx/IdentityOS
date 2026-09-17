"""Extract Playwright-compatible cookies from a Firefox profile."""

from __future__ import annotations

import shutil
import sqlite3
import tempfile
from pathlib import Path
from typing import Any


def _copy_sqlite(db: Path) -> Path:
    tmp = Path(tempfile.mkstemp(suffix=".sqlite")[1])
    shutil.copy2(db, tmp)
    for suf in ("-wal", "-shm"):
        side = Path(str(db) + suf)
        if side.exists():
            shutil.copy2(side, Path(str(tmp) + suf))
    return tmp


def extract_firefox_cookies(
    profile_path: str | Path,
    *,
    host_substr: tuple[str, ...] = (),
) -> list[dict[str, Any]]:
    """Return cookies from ``cookies.sqlite`` in Playwright add_cookies shape."""
    profile = Path(profile_path).expanduser().resolve()
    db = profile / "cookies.sqlite"
    if not db.exists():
        return []

    tmp = _copy_sqlite(db)
    cookies: list[dict[str, Any]] = []
    try:
        con = sqlite3.connect(f"file:{tmp}?mode=ro", uri=True)
        rows = con.execute(
            """
            SELECT host, name, value, path, expiry, isSecure, isHttpOnly, sameSite
            FROM moz_cookies
            """
        ).fetchall()
        con.close()
    finally:
        for suf in ("", "-wal", "-shm"):
            try:
                Path(str(tmp) + suf).unlink(missing_ok=True)
            except Exception:
                pass

    wanted = tuple(h.lower() for h in host_substr) if host_substr else ()
    for host, name, value, path, expiry, is_secure, is_http_only, same_site in rows:
        host_s = (host or "").strip()
        if not name or value is None or value == "":
            continue
        if wanted and not any(w in host_s.lower() for w in wanted):
            continue

        # Map Firefox sameSite ints → Playwright enum.
        # 0=no_restriction/None, 1=lax, 2=strict, -1=unspecified
        same = {0: "None", 1: "Lax", 2: "Strict", -1: "Lax"}.get(
            same_site if same_site is not None else -1,
            "Lax",
        )
        secure = bool(is_secure)
        if same == "None" and not secure:
            # Playwright requires Secure when SameSite=None
            secure = True

        item: dict[str, Any] = {
            "name": str(name),
            "value": str(value),
            "domain": host_s,
            "path": path or "/",
            "httpOnly": bool(is_http_only),
            "secure": secure,
            "sameSite": same,
        }
        try:
            exp = int(expiry or 0)
            # Firefox stores expiry in milliseconds; Playwright wants seconds.
            if exp > 10_000_000_000:  # clearly ms
                exp = exp // 1000
            if exp > 0:
                item["expires"] = exp
        except Exception:
            pass
        cookies.append(item)
    return cookies


def auth_relevant_cookies(profile_path: str | Path) -> list[dict[str, Any]]:
    """Cookies useful for Canvas / school SSO re-auth."""
    return extract_firefox_cookies(
        profile_path,
        host_substr=(
            "instructure",
            "canvas",
            "oc.edu",
            "sso",
            "oklahomachristian",
        ),
    )
