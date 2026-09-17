"""Resolve and prepare Firefox profiles for Playwright sessions."""

from __future__ import annotations

import configparser
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


_FIREFOX_ROOTS = (
    Path.home() / ".mozilla" / "firefox",
    Path.home() / "snap" / "firefox" / "common" / ".mozilla" / "firefox",
    Path.home() / ".var" / "app" / "org.mozilla.firefox" / ".mozilla" / "firefox",
)

# Heavy / regenerable paths — skip when copying a locked live profile.
_COPY_IGNORE = shutil.ignore_patterns(
    "cache2",
    "startupCache",
    "thumbnails",
    "shader-cache",
    "OfflineCache",
    "safebrowsing",
    "datareporting",
    "saved-telemetry-pings",
    "crashes",
    "minidumps",
    "storage/temporary",
    "*.log",
)


@dataclass(frozen=True)
class FirefoxProfile:
    name: str
    path: Path
    is_default: bool = False
    is_relative: bool = True


def firefox_roots() -> list[Path]:
    return [p for p in _FIREFOX_ROOTS if p.is_dir()]


def list_firefox_profiles() -> list[FirefoxProfile]:
    found: list[FirefoxProfile] = []
    seen: set[Path] = set()
    for root in firefox_roots():
        ini = root / "profiles.ini"
        if not ini.exists():
            continue
        parser = configparser.ConfigParser()
        parser.read(ini)
        for section in parser.sections():
            if not section.lower().startswith("profile"):
                continue
            name = parser.get(section, "Name", fallback="") or section
            rel = parser.get(section, "Path", fallback="")
            if not rel:
                continue
            is_rel = parser.getboolean(section, "IsRelative", fallback=True)
            path = (root / rel).resolve() if is_rel else Path(rel).expanduser().resolve()
            if not path.exists() or path in seen:
                continue
            seen.add(path)
            found.append(
                FirefoxProfile(
                    name=name,
                    path=path,
                    is_default=parser.getboolean(section, "Default", fallback=False),
                    is_relative=is_rel,
                )
            )
    return found


def profile_is_locked(profile_path: Path) -> bool:
    lock = profile_path / "lock"
    parent = profile_path / ".parentlock"
    if lock.is_symlink() or lock.exists():
        return True
    if parent.exists() and parent.stat().st_size >= 0:
        # parentlock alone is weak signal; prefer lock symlink / running firefox
        if _firefox_running():
            return True
    return False


def _firefox_running() -> bool:
    try:
        import subprocess

        out = subprocess.check_output(["pgrep", "-x", "firefox"], text=True)
        return bool(out.strip())
    except Exception:
        return False


def resolve_firefox_profile(
    name_or_path: str,
    *,
    prefer_canvas: bool = True,
) -> FirefoxProfile:
    """Resolve a Firefox profile by path, exact name, or friendly alias.

    Aliases:
      - lace / original / main → best default-release / default match
    """
    raw = (name_or_path or "").strip()
    if not raw:
        raise ValueError("profile name or path is required")

    as_path = Path(raw).expanduser()
    if as_path.exists() and as_path.is_dir():
        return FirefoxProfile(name=as_path.name, path=as_path.resolve())

    profiles = list_firefox_profiles()
    if not profiles:
        raise FileNotFoundError("No Firefox profiles found under ~/.mozilla/firefox")

    lowered = raw.lower()
    for p in profiles:
        if p.name.lower() == lowered or p.path.name.lower() == lowered:
            return p

    # Friendly aliases for this machine / username.
    if lowered in {"lace", "original", "main"}:
        # Prefer the profile that actually has Canvas / school history.
        scored = sorted(
            profiles,
            key=lambda p: (_canvas_score(p.path), p.name == "default-release", p.is_default),
            reverse=True,
        )
        if scored:
            return scored[0]

    if lowered == "default":
        for p in profiles:
            if p.name.lower() == "default":
                return p

    if prefer_canvas:
        scored = sorted(profiles, key=lambda p: (_canvas_score(p.path), p.is_default), reverse=True)
        if scored and _canvas_score(scored[0].path) > 0:
            return scored[0]

    # Fall back to marked default, else first profile.
    for p in profiles:
        if p.is_default:
            return p
    return profiles[0]


def _canvas_score(path: Path) -> int:
    places = path / "places.sqlite"
    if not places.exists():
        return 0
    try:
        import sqlite3
        import tempfile

        tmp = Path(tempfile.mkstemp(suffix=".sqlite")[1])
        shutil.copy2(places, tmp)
        for suf in ("-wal", "-shm"):
            side = Path(str(places) + suf)
            if side.exists():
                shutil.copy2(side, Path(str(tmp) + suf))
        con = sqlite3.connect(f"file:{tmp}?mode=ro", uri=True)
        n = con.execute(
            "SELECT COUNT(*) FROM moz_places WHERE url LIKE '%instructure%' OR url LIKE '%canvas%'"
        ).fetchone()[0]
        con.close()
        return int(n)
    except Exception:
        return 0
    finally:
        for suf in ("", "-wal", "-shm"):
            try:
                Path(str(tmp) + suf).unlink(missing_ok=True)
            except Exception:
                pass


def prepare_firefox_profile(
    name_or_path: str,
    *,
    work_root: str | Path,
    force_copy: bool = False,
) -> dict:
    """Return a Playwright-usable profile directory.

    If the live profile is locked (Firefox open), copy a usable subset into
    ``work_root`` so Playwright can launch without fighting the lock.
    """
    profile = resolve_firefox_profile(name_or_path)
    locked = profile_is_locked(profile.path)
    must_copy = force_copy or locked
    result = {
        "name": profile.name,
        "source_path": str(profile.path),
        "locked": locked,
        "copied": False,
        "path": str(profile.path),
    }
    if not must_copy:
        return result

    dest = Path(work_root).expanduser().resolve() / "firefox-profile-copies" / profile.path.name
    if dest.exists():
        shutil.rmtree(dest, ignore_errors=True)
    dest.parent.mkdir(parents=True, exist_ok=True)

    def _ignore(dirpath: str, names: list[str]) -> set[str]:
        ignored = set(_COPY_IGNORE(dirpath, names))
        # Skip live lock symlinks that break copytree when the target vanished.
        for name in names:
            if name in {"lock", ".parentlock"}:
                ignored.add(name)
        return ignored

    try:
        shutil.copytree(profile.path, dest, ignore=_ignore, dirs_exist_ok=False)
    except shutil.Error as exc:
        # Partial copy with only lock-symlink errors is still usable.
        if not dest.exists():
            raise
        result["copy_warnings"] = [str(item) for item in getattr(exc, "args", [[]])[0][:5]]
    # Remove stale lock files from the copy
    for lock_name in ("lock", ".parentlock"):
        lock_path = dest / lock_name
        try:
            if lock_path.is_symlink() or lock_path.exists():
                lock_path.unlink()
        except Exception:
            pass
    result.update({"copied": True, "path": str(dest), "copy_reason": "locked" if locked else "forced"})
    return result
