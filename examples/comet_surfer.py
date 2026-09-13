#!/usr/bin/env python3
"""Create / load the Comet surfing identity and run a tiny browser mission.

Usage:
  source .venv/bin/activate
  pip install -e ".[browser]" && playwright install chromium
  python examples/comet_surfer.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Allow running from repo root
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from identityos import Identity

STORE = os.environ.get("IDENTITY_STORE_PATH", ".identity_store")


def main() -> int:
    try:
        comet = Identity.load("comet", storage_path=STORE)
        print(f"loaded identity: {comet.id}")
    except Exception:
        comet = Identity.create(
            name="Comet",
            identity_id="comet",
            persona=(
                "Person-like web surfing agent. Search, judge usefulness, "
                "open pages, login when authorized, finish in-page tasks."
            ),
            role="web surfing agent",
            storage_path=STORE,
        )
        print(f"created identity: {comet.id}")

    installed = {c["id"] for c in comet.capabilities()}
    for cap, cfg in [
        ("browser", {"headless": True, "storage_root": STORE}),
        ("web", None),
        ("task_planner", None),
        ("datetime", None),
        ("github", None),
        ("text", None),
    ]:
        if cap not in installed:
            comet.install(cap, config=cfg) if cfg else comet.install(cap)
            print(f"installed {cap}")

    task = "Find the canonical Example Domain page and confirm its heading"
    search = comet.use("browser").search(query="example domain iana", task=task, max_results=5)
    if not search.success:
        print("search failed:", search.error)
        return 2

    recommended = search.data.get("recommended") or search.data.get("results") or []
    print(json.dumps({
        "useful_count": search.data.get("useful_count"),
        "top": [
            {"score": r.get("score"), "useful": r.get("useful"), "title": r.get("title"), "url": r.get("url")}
            for r in recommended[:3]
        ],
    }, indent=2))

    url = "https://example.com"
    for r in recommended:
        if r.get("useful") and r.get("url"):
            url = r["url"]
            break

    opened = comet.use("browser").open(url=url)
    snap = comet.use("browser").snapshot()
    print("opened:", (opened.data or {}).get("title"), (opened.data or {}).get("url"))
    print("snapshot chars:", len((snap.data or {}).get("text", "")) if snap.success else snap.error)
    comet.use("browser").close()
    return 0 if opened.success and snap.success else 2


if __name__ == "__main__":
    raise SystemExit(main())
