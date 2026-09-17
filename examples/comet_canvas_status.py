#!/usr/bin/env python3
"""Use Comet's browser capability + Firefox 'lace' profile to read Canvas status.

Drives IdentityOS skills (not a fake scrape): use_profile → open → eval_js Canvas API.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from identityos import Identity

STORE = os.environ.get("IDENTITY_STORE_PATH", ".identity_store")
CANVAS = "https://oklahomachristian.instructure.com"
PROFILE = os.environ.get("COMET_FIREFOX_PROFILE", "lace")


def main() -> int:
    try:
        comet = Identity.load("comet", storage_path=STORE)
    except Exception:
        comet = Identity.create(
            name="Comet",
            identity_id="comet",
            persona="Web surfing agent",
            role="browser operator",
            storage_path=STORE,
        )

    installed = {c["id"] for c in comet.capabilities()}
    if "browser" not in installed:
        comet.install(
            "browser",
            config={
                "headless": True,
                "storage_root": STORE,
                "browser_type": "firefox",
            },
        )
    # Reinstall config so profile skills see storage_root
    try:
        comet.uninstall("browser")
    except Exception:
        pass
    comet.install(
        "browser",
        config={
            "headless": True,
            "storage_root": STORE,
            "browser_type": "firefox",
        },
    )

    # Ensure permissions for browsing
    for perm in ("browser:read", "browser:write"):
        try:
            comet.grant("browser", perm)
        except Exception:
            pass

    browser = comet.use("browser")

    print("=== list_profiles ===", flush=True)
    listed = browser.list_profiles()
    print(json.dumps(listed.data if listed.success else listed.error, indent=2)[:2000], flush=True)

    print(f"\n=== use_profile({PROFILE!r}) ===", flush=True)
    # Cookie-import into Playwright Chromium (system Firefox profile is too new
    # for Playwright's bundled Firefox binary).
    used = browser.use_profile(profile=PROFILE, browser_type="chromium", headless=True)
    print(json.dumps(used.data if used.success else used.error, indent=2), flush=True)
    if not used.success:
        return 2

    print("\n=== open Canvas ===", flush=True)
    opened = browser.open(url=f"{CANVAS}/")
    print(json.dumps({k: (opened.data or {}).get(k) for k in ("ok", "url", "title", "error")}, indent=2), flush=True)

    # Wait for possible SSO redirect
    browser.wait(ms=4000)
    snap = browser.snapshot(max_chars=4000)
    snap_data = snap.data or {}
    print("\n=== snapshot ===", flush=True)
    print("url:", snap_data.get("url"))
    print("title:", snap_data.get("title"))
    print("text_preview:", (snap_data.get("text") or "")[:500])

    url_now = (snap_data.get("url") or "").lower()
    logged_out = any(x in url_now for x in ("login", "sso", "cas", "rubycas"))
    if logged_out or "sign in" in (snap_data.get("text") or "").lower()[:200]:
        print("\nSession appears logged out — attempting SSO continue via Canvas login URL", flush=True)
        browser.open(url=f"{CANVAS}/login/cas")
        browser.wait(ms=5000)
        snap = browser.snapshot(max_chars=4000)
        snap_data = snap.data or {}
        print("after SSO url:", snap_data.get("url"), "title:", snap_data.get("title"), flush=True)

    # Canvas JSON API from inside the page (uses browser cookies)
    js = r"""
    async () => {
      const base = location.origin;
      const get = async (path) => {
        const r = await fetch(base + path, { credentials: 'include', headers: { 'Accept': 'application/json' } });
        const text = await r.text();
        let body = null;
        try { body = JSON.parse(text); } catch (e) { body = text.slice(0, 500); }
        return { status: r.status, ok: r.ok, body };
      };
      const profile = await get('/api/v1/users/self/profile');
      const courses = await get('/api/v1/courses?enrollment_state=active&per_page=50');
      const todo = await get('/api/v1/users/self/todo?per_page=50');
      const upcoming = await get('/api/v1/users/self/upcoming_events?per_page=50');
      const missing = await get('/api/v1/users/self/missing_submissions?include[]=planner_overrides&per_page=50');
      let assignments = [];
      if (courses.ok && Array.isArray(courses.body)) {
        for (const c of courses.body.slice(0, 12)) {
          const a = await get(`/api/v1/courses/${c.id}/assignments?per_page=50&order_by=due_at&include[]=submission`);
          if (a.ok && Array.isArray(a.body)) {
            for (const item of a.body) {
              assignments.push({
                course: c.name,
                course_id: c.id,
                id: item.id,
                name: item.name,
                due_at: item.due_at,
                points_possible: item.points_possible,
                html_url: item.html_url,
                submitted: !!(item.submission && item.submission.submitted_at),
                submitted_at: item.submission && item.submission.submitted_at,
                score: item.submission && item.submission.score,
                grade: item.submission && item.submission.grade,
                workflow_state: item.submission && item.submission.workflow_state,
                graded_at: item.submission && item.submission.graded_at,
              });
            }
          }
        }
      }
      return {
        location: location.href,
        title: document.title,
        profile,
        courses,
        todo,
        upcoming,
        missing,
        assignments,
      };
    }
    """
    print("\n=== eval_js Canvas API ===", flush=True)
    api = browser.eval_js(expression=js)
    if not api.success:
        print("eval failed:", api.error, flush=True)
        browser.close()
        return 2

    result = api.data.get("result") if api.data else None
    out = {
        "profile_used": PROFILE,
        "canvas_host": CANVAS,
        "page_url": (result or {}).get("location"),
        "page_title": (result or {}).get("title"),
        "api": result,
        "snapshot_url": snap_data.get("url"),
        "snapshot_title": snap_data.get("title"),
    }
    out_path = ROOT / "demo" / "comet-canvas-status.json"
    out_path.parent.mkdir(exist_ok=True)
    # Shrink assignment list for summary printing but keep full file
    out_path.write_text(json.dumps(out, indent=2, default=str))
    print(f"wrote {out_path}", flush=True)

    # Human summary
    body = result or {}
    profile = (body.get("profile") or {})
    courses = (body.get("courses") or {})
    assignments = body.get("assignments") or []
    print("\n=== SUMMARY ===", flush=True)
    print("profile API:", profile.get("status"), (profile.get("body") or {}).get("name") if isinstance(profile.get("body"), dict) else profile.get("body"))
    print("courses API:", courses.get("status"), "count", len(courses.get("body") or []) if isinstance(courses.get("body"), list) else courses.get("body"))
    submitted = [a for a in assignments if a.get("submitted")]
    graded = [a for a in assignments if a.get("grade") not in (None, "") or a.get("score") is not None]
    upcoming = [a for a in assignments if a.get("due_at") and not a.get("submitted")]
    print(f"assignments fetched: {len(assignments)}")
    print(f"submitted: {len(submitted)}  graded: {len(graded)}  unsubmitted_with_due: {len(upcoming)}")
    for label, rows in (("GRADED", graded[:15]), ("UPCOMING/UNSUBMITTED", upcoming[:15]), ("RECENT SUBMITTED", submitted[:10])):
        print(f"\n-- {label} --")
        for a in rows:
            print(f"- [{a.get('course')}] {a.get('name')} due={a.get('due_at')} grade={a.get('grade')} score={a.get('score')} submitted={a.get('submitted')}")

    browser.close()

    ok = isinstance(profile.get("body"), dict) and profile.get("status") == 200
    if not ok:
        print("\nFAIL: Canvas API did not return an authenticated profile (login required or SSO expired).", file=sys.stderr)
        return 2
    print("\nPASS: Authenticated Canvas data retrieved via Comet Firefox profile.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
