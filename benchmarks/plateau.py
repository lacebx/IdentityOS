"""Detect when the ratchet loop has stopped improving."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS_DIR = ROOT / "benchmarks" / "experiments"


def recent_verdicts(limit: int = 8) -> list[tuple[str, str]]:
    if not EXPERIMENTS_DIR.exists():
        return []
    paths = sorted(EXPERIMENTS_DIR.glob("EXP-*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    out: list[tuple[str, str]] = []
    for path in paths[:limit]:
        text = path.read_text(encoding="utf-8")
        verdict = "UNKNOWN"
        for line in text.splitlines():
            if line.startswith("Status:"):
                verdict = line.split(":", 1)[1].strip()
                break
        out.append((path.stem, verdict))
    return out


def consecutive_reverts(limit: int = 5) -> int:
    count = 0
    for _exp_id, verdict in recent_verdicts(limit):
        if verdict == "REVERT":
            count += 1
        else:
            break
    return count


def latest_success_rate() -> float | None:
    paths = sorted(EXPERIMENTS_DIR.glob("EXP-*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    for path in paths:
        text = path.read_text(encoding="utf-8")
        if "Status: KEEP" not in text:
            continue
        match = re.search(r"Task Success \| [^|]+\| (\d+)%", text)
        if match:
            return int(match.group(1)) / 100.0
    return None


def should_stop(*, max_consecutive_reverts: int = 4, target_success_rate: float = 0.85) -> tuple[bool, str]:
    reverts = consecutive_reverts(max_consecutive_reverts + 1)
    if reverts >= max_consecutive_reverts:
        return True, f"{reverts} consecutive REVERTs"
    rate = latest_success_rate()
    if rate is not None and rate >= target_success_rate:
        return True, f"success rate {rate * 100:.0f}% >= target {target_success_rate * 100:.0f}%"
    return False, ""
