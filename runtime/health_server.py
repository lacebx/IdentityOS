"""
runtime/health_server.py — localhost-only Aster Control endpoint.

Read paths (Tailnet-private, no per-request auth — same posture as the
dashboard they extend; polling them never invokes a model):

  GET /health            sanitized presence JSON
  GET /status            mobile dashboard (Overview tab renders server-side)
  GET /api/presence      presence JSON (alias)
  GET /api/activity      sanitized provenance/notification timeline
  GET /api/relationships sanitized relationships
  GET /api/capabilities  installed capabilities + per-skill permission state
  GET /api/messages      principal conversation history (sanitized envelopes)
  GET /manifest.json     PWA manifest (no tracking, local icon only)
  GET /icon.svg          original Aster mark (local asset, no third parties)

State-changing paths (require principal verification — see _principal_verified):

  POST /api/messages     submit a principal message to the SAME persistent
                         identity; stored RECEIVED, processed by the operator
                         loop, never faked.

Principal verification = Tailnet Host match + exact Tailscale-User-Login match
+ anti-CSRF request marker. Tailscale Serve injects the login header for
genuine Tailnet viewers; direct-local requests cannot satisfy the Host rule,
so forged headers from localhost curl are rejected. Funnel is never used.

Zero model calls on any path in this process. Binds localhost only by
default. Only sanitized fields leave the box: no topics, phone numbers,
credentials, tokens, standing secrets, message contents (outside the
principal's own conversation), or chain-of-thought.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Optional
from urllib.parse import urlparse

from core.operations.presence import PresenceStore
from runtime.persistence import get_backend

REFRESH_SECONDS = 15
MESSAGES_POLL_SECONDS = 4
ACTIVITY_POLL_SECONDS = 20
SLOW_POLL_SECONDS = 60
MAX_POST_BYTES = 16 * 1024
MAX_POSTS_PER_MINUTE = 20

_post_minutes: dict[str, int] = {}
_post_minutes_lock = threading.Lock()


def _esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def render_dashboard(view: dict[str, Any]) -> str:
    """Render the mobile-first presence dashboard from a sanitized view.

    The page paints server-rendered values immediately, then refreshes its
    data every ``REFRESH_SECONDS`` via ``fetch('/health')`` with in-place DOM
    updates (no full-page reload, no frameworks, no model calls).
    """
    status = _esc(view.get("status") or "unknown")
    health = _esc(view.get("health") or "unknown")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#0b0f14">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Aster">
<meta name="mobile-web-app-capable" content="yes">
<link rel="manifest" href="/manifest.json">
<link rel="apple-touch-icon" href="/icon.svg">
<link rel="icon" type="image/svg+xml" href="/icon.svg">
<title>Aster · {{status}}</title>
<style>
:root {{ color-scheme: dark; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; padding: 16px 16px 32px; background: #0b0f14; color: #e8eef4;
  font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", sans-serif; }}
.wrap {{ max-width: 560px; margin: 0 auto; }}
.head {{ display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }}
h1 {{ font-size: 26px; margin: 6px 0 2px; letter-spacing: .2px; }}
.sub {{ color: #93a1b3; font-size: 13px; }}
.pill {{ display: inline-flex; align-items: center; gap: 8px; font-weight: 700; font-size: 15px;
  padding: 8px 14px; border-radius: 999px; background: #1a2230; border: 1px solid #2b3a55; }}
.dot {{ width: 12px; height: 12px; border-radius: 50%; background: #8a94a6; }}
.h-online .dot {{ background: #34d17b; box-shadow: 0 0 8px #34d17b; }}
.h-degraded .dot {{ background: #ff6b4a; box-shadow: 0 0 8px #ff6b4a; }}
.h-offline .dot, .h-unknown .dot {{ background: #4a5568; }}
.card {{ background: #131a24; border: 1px solid #223047; border-radius: 14px;
  padding: 14px 16px; margin-top: 12px; }}
.label {{ font-size: 11px; text-transform: uppercase; letter-spacing: 1.2px; color: #93a1b3; }}
.value {{ font-size: 17px; margin-top: 4px; line-height: 1.45; word-break: break-word; }}
.big {{ font-size: 20px; }}
.grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
.foot {{ margin-top: 14px; color: #93a1b3; font-size: 12px; text-align: center; }}
.warn {{ color: #ffb02e; }}
nav.tabs {{ display: flex; gap: 6px; margin-top: 14px; overflow-x: auto; }}
nav.tabs button {{ flex: 1 0 auto; background: #131a24; color: #93a1b3; border: 1px solid #223047;
  border-radius: 10px; padding: 10px 8px; font-size: 13px; font-weight: 600; }}
nav.tabs button.on {{ color: #e8eef4; border-color: #34d17b; }}
section.tab {{ display: none; }}
section.tab.on {{ display: block; }}
.ev {{ border-left: 3px solid #2b3a55; padding: 6px 0 6px 12px; margin: 10px 0; }}
.ev .t {{ font-size: 12px; color: #93a1b3; }}
.ev .c {{ font-size: 11px; text-transform: uppercase; letter-spacing: 1px; color: #5aa9ff; }}
.msg {{ border-radius: 14px; padding: 10px 14px; margin: 10px 0; max-width: 92%; line-height: 1.45; }}
.msg.in {{ background: #1d3a5f; margin-left: auto; }}
.msg.out {{ background: #16241d; border: 1px solid #234034; }}
.msg .meta {{ font-size: 11px; color: #93a1b3; margin-top: 6px; }}
.msg .st {{ display: inline-block; font-size: 11px; font-weight: 700; padding: 2px 8px;
  border-radius: 999px; background: #223047; margin-top: 6px; }}
.st-processing {{ color: #ffb02e; }} .st-completed, .st-sent {{ color: #34d17b; }}
.st-deferred, .st-permission_required, .st-failed {{ color: #ff6b4a; }}
form.composer {{ display: flex; gap: 8px; margin-top: 12px; position: sticky; bottom: 0;
  background: #0b0f14; padding: 10px 0; }}
form.composer textarea {{ flex: 1; background: #131a24; color: #e8eef4; border: 1px solid #223047;
  border-radius: 12px; padding: 10px 12px; font-size: 16px; resize: none; }}
form.composer button {{ background: #34d17b; color: #06210f; border: 0; border-radius: 12px;
  padding: 0 18px; font-size: 16px; font-weight: 700; }}
.err {{ color: #ff6b4a; font-size: 13px; margin-top: 8px; }}
</style>
</head>
<body>
<div class="wrap">
  <div class="head">
    <div>
      <h1 id="identity">{_esc(view.get("identity") or "Aster")}</h1>
      <div class="sub">IdentityOS operator · AI identity</div>
    </div>
    <div class="pill st-{status} h-{health}" id="pill"><span class="dot"></span><span id="status">{status.upper()}</span></div>
  </div>
  <nav class="tabs">
    <button data-tab="overview" class="on">Overview</button>
    <button data-tab="activity">Activity</button>
    <button data-tab="relationships">People</button>
    <button data-tab="capabilities">Skills</button>
    <button data-tab="work">Work</button>
    <button data-tab="messages">Messages</button>
  </nav>
  <section class="tab on" id="sec-overview">
  <div class="card"><div class="label">Activity</div><div class="value big" id="activity">{_esc(view.get("activity") or "—")}</div></div>
  <div class="card"><div class="label">Current objective</div><div class="value" id="objective">{_esc(view.get("current_objective") or "—")}</div></div>

  <div class="grid">
    <div class="card"><div class="label">Last heartbeat</div><div class="value" id="heartbeat">—</div></div>
    <div class="card"><div class="label">Uptime</div><div class="value" id="uptime">—</div></div>
  </div>

  <div class="card"><div class="label">Last meaningful action</div><div class="value" id="action">{_esc(view.get("last_meaningful_action") or "None recorded yet")}</div><div class="sub" id="action-age"></div></div>
  <div class="card"><div class="label">Next</div><div class="value" id="next">{_esc(view.get("next_planned_action") or "—")}</div><div class="sub" id="next-in"></div></div>

  <div class="grid">
    <div class="card"><div class="label">Service</div><div class="value" id="service">—</div></div>
    <div class="card"><div class="label">Culture Commons</div><div class="value" id="commons">—</div></div>
  </div>
  <div class="grid">
    <div class="card"><div class="label">Notifications</div><div class="value" id="notifications">—</div></div>
    <div class="card"><div class="label">Opportunities</div><div class="value" id="opportunities">—</div></div>
  </div>
  <div class="card"><div class="label">Capabilities</div><div class="value" id="capabilities">—</div><div class="sub" id="capabilities-sub"></div></div>
  </section>
  <section class="tab" id="sec-activity">
    <div class="card"><div class="label">Recent activity</div><div id="timeline"><div class="sub">Loading…</div></div></div>
  </section>
  <section class="tab" id="sec-relationships">
    <div class="card"><div class="label">Relationships</div><div id="rel-list"><div class="sub">Loading…</div></div></div>
  </section>
  <section class="tab" id="sec-capabilities">
    <div class="card"><div class="label">Capabilities</div><div id="cap-list"><div class="sub">Loading…</div></div></div>
  </section>
  <section class="tab" id="sec-work"><div class="card"><div class="label">Delegated work</div><div id="work-list">No delegated work.</div></div></section>
  <section class="tab" id="sec-messages">
    <div class="card"><div class="label">Conversation with Aster</div><div id="msg-list"><div class="sub">Loading…</div></div>
      <form class="composer" id="composer">
        <textarea id="composer-text" rows="2" maxlength="4000" placeholder="Message Aster…"></textarea>
        <button type="submit">Send</button>
      </form>
      <div class="err" id="composer-err"></div>
    </div>
  </section>

  <div class="foot"><span id="updated">Loading…</span> · auto-refreshes</div>
</div>
<script>
(function () {{
  "use strict";
  var last = null;
  function $(id) {{ return document.getElementById(id); }}
  function ago(iso) {{
    if (!iso) return "unknown";
    var s = Math.max(0, Math.floor((Date.now() - Date.parse(iso)) / 1000));
    if (s < 5) return "just now";
    if (s < 90) return s + " seconds ago";
    var m = Math.floor(s / 60);
    if (m < 90) return m + (m === 1 ? " minute ago" : " minutes ago");
    var h = Math.floor(m / 60);
    if (h < 48) return h + (h === 1 ? " hour ago" : " hours ago");
    return Math.floor(h / 24) + " days ago";
  }}
  function ahead(iso) {{
    if (!iso) return "";
    var s = Math.floor((Date.parse(iso) - Date.now()) / 1000);
    if (s <= 0) return "due now";
    if (s < 90) return "in " + s + " seconds";
    var m = Math.floor(s / 60);
    if (m < 90) return "in " + m + (m === 1 ? " minute" : " minutes");
    return "in " + Math.floor(m / 60) + " hours";
  }}
  function dur(sec) {{
    if (sec == null || sec < 0) return "—";
    sec = Math.floor(sec);
    var h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60);
    if (h > 0) return h + "h " + m + "m";
    if (m > 0) return m + "m " + (sec % 60) + "s";
    return sec + "s";
  }}
  function apply(v) {{
    last = v;
    document.title = "Aster · " + (v.status || "unknown");
    var pill = $("pill");
    pill.className = "pill st-" + (v.status || "unknown") + " h-" + (v.health || "unknown");
    $("status").textContent = String(v.status || "unknown").toUpperCase();
    $("identity").textContent = v.identity || "Aster";
    $("activity").textContent = (v.status || "") + " — " + (v.activity || "No activity recorded");
    $("objective").textContent = v.current_objective || "—";
    $("action").textContent = v.last_meaningful_action || "None recorded yet";
    $("next").textContent = v.next_planned_action || "—";
    var pid = v.operator_pid ? " · pid " + v.operator_pid : "";
    $("service").textContent = (v.service_state || "unknown") + pid;
    $("commons").textContent = v.commons_standing || "unknown";
    $("notifications").textContent = "ntfy · " + (v.notification_transport_health || "unknown");
    $("opportunities").textContent = String(v.opportunity_count == null ? 0 : v.opportunity_count);
    var sum = v.capability_summary || {{}};
    var limited = sum.limited || [];
    var disp = v.capability_display || "unknown";
    $("capabilities").textContent = (sum.healthy == null ? 0 : sum.healthy) + " healthy · " + limited.length + " limited (" + disp + ")";
    $("capabilities-sub").textContent = limited.length ? "Limited: " + limited.join(", ") : "";
    tick();
  }}
  function tick() {{
    if (!last) return;
    $("heartbeat").textContent = ago(last.last_heartbeat);
    var up = null;
    if (last.started_at && last.operator_pid) {{
      up = (Date.now() - Date.parse(last.started_at)) / 1000;
    }}
    $("uptime").textContent = up == null ? "—" : dur(up);
    $("action-age").textContent = last.last_meaningful_action ? ago(last.last_meaningful_action_at) : "";
    var ni = ahead(last.next_check_at);
    $("next-in").textContent = ni;
  }}
  async function refresh() {{
    try {{
      var r = await fetch("/health", {{ cache: "no-store" }});
      if (!r.ok) throw new Error("http " + r.status);
      apply(await r.json());
      $("updated").textContent = "Last updated " + new Date().toLocaleTimeString();
      $("updated").className = "";
    }} catch (e) {{
      $("updated").textContent = "Refresh failed — showing last known state";
      $("updated").className = "warn";
    }}
  }}
  var activeTab = "overview";
  function showTab(name) {{
    activeTab = name;
    var btns = document.querySelectorAll("nav.tabs button");
    for (var bi = 0; bi < btns.length; bi++) {{
      btns[bi].className = btns[bi].getAttribute("data-tab") === name ? "on" : "";
    }}
    var secs = document.querySelectorAll("section.tab");
    for (var si = 0; si < secs.length; si++) {{
      secs[si].className = "tab" + (secs[si].id === "sec-" + name ? " on" : "");
    }}
    pull(name, true);
  }}
  var navBtns = document.querySelectorAll("nav.tabs button");
  for (var ni = 0; ni < navBtns.length; ni++) {{
    (function (b) {{
      b.addEventListener("click", function () {{ showTab(b.getAttribute("data-tab")); }});
    }})(navBtns[ni]);
  }}
  function el(tag, cls, text) {{
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }}
  function fmtTime(iso) {{
    if (!iso) return "";
    try {{ return new Date(Date.parse(iso)).toLocaleString(); }} catch (e) {{ return ""; }}
  }}
  async function getJSON(path) {{
    var r = await fetch(path, {{ cache: "no-store" }});
    if (!r.ok) throw new Error("http " + r.status);
    return r.json();
  }}
  function statusLabel(s) {{
    var m = {{"received": "Received", "queued": "Queued for Aster",
      "processing": "Aster is working on it…", "completed": "Completed",
      "deferred": "Deferred", "permission_required": "Needs your approval",
      "failed": "Failed", "sent": "Sent"}};
    return m[s] || s || "";
  }}
  async function pullMessages() {{
    var mm = await getJSON("/api/messages?limit=50");
    var ml = $("msg-list"); ml.textContent = "";
    var msgs = mm.messages || [];
    if (!msgs.length) ml.appendChild(el("div", "sub", "No messages yet. Say hello."));
    for (var i = 0; i < msgs.length; i++) {{
      var msg = msgs[i];
      var mine = msg.direction === "inbound";
      var bubble = el("div", "msg " + (mine ? "in" : "out"), msg.body || "");
      var meta = [fmtTime(msg.sent_at || msg.received_at || msg.created_at)];
      if (!mine && msg.via && msg.via.model) meta.push("via " + msg.via.model);
      else if (!mine && msg.via && msg.via.adapter) meta.push("via " + msg.via.adapter);
      bubble.appendChild(el("div", "meta", meta.join(" · ")));
      if (msg.runtime_evidence) {{
        var details = el("details", "sub");
        details.appendChild(el("summary", "", "Runtime evidence"));
        details.appendChild(el("div", "", "Observed " + fmtTime(msg.runtime_evidence.observed_at)));
        details.appendChild(el("div", "", msg.runtime_evidence.guard === "fallback" ? "Runtime report substituted for an unsupported model response." : "Structured claims checked against runtime state."));
        bubble.appendChild(details);
      }}
      if (mine) {{
        var st = el("div", "st st-" + msg.status,
          statusLabel(msg.status) + (msg.detail ? " — " + msg.detail : ""));
        bubble.appendChild(st);
      }}
      ml.appendChild(bubble);
    }}
  }}
  async function pull(name, now) {{
    if (document.hidden && !now) return;
    try {{
      if (name === "activity") {{
        var a = await getJSON("/api/activity?limit=30");
        var tl = $("timeline"); tl.textContent = "";
        var evs = a.events || [];
        if (!evs.length) tl.appendChild(el("div", "sub", "No activity recorded yet."));
        for (var i = 0; i < evs.length; i++) {{
          var ev = evs[i];
          var d = el("div", "ev");
          d.appendChild(el("div", "t", fmtTime(ev.at)));
          d.appendChild(el("div", "c", ev.category || ""));
          d.appendChild(el("div", "", ev.description || ""));
          if (ev.count > 1) d.appendChild(el("div", "sub", "Repeated " + ev.count + " times · first " + fmtTime(ev.first_at) + " · last " + fmtTime(ev.at)));
          if (ev.outcome) d.appendChild(el("div", "sub", ev.outcome));
          tl.appendChild(d);
        }}
      }} else if (name === "work") {{
        var ww = await getJSON("/api/work");
        var wl = $("work-list"); wl.textContent = "";
        if (!(ww.jobs || []).length) wl.appendChild(el("div", "sub", "No delegated work."));
        (ww.jobs || []).forEach(function(j) {{
          var card = el("div", "ev");
          card.appendChild(el("div", "big", j.provider + " · " + j.skill));
          card.appendChild(el("div", "", j.state + " · " + (j.price ? j.price + " IDC" : "FREE")));
          card.appendChild(el("div", "sub", j.pricing_reason || "Not quoted"));
          card.appendChild(el("div", "sub", "Acceptance: " + j.acceptance));
          card.appendChild(el("div", "sub", "Job " + j.id));
          if (j.artifact) card.appendChild(el("div", "sub", "Artifact " + j.artifact));
          wl.appendChild(card);
        }});
      }} else if (name === "relationships") {{
        var rr = await getJSON("/api/relationships");
        var rl = $("rel-list"); rl.textContent = "";
        var rels = rr.relationships || [];
        if (!rels.length) rl.appendChild(el("div", "sub", "No relationships yet."));
        for (var m = 0; m < rels.length; m++) {{
          var rel = rels[m];
          var card = el("div", "ev");
          card.appendChild(el("div", "c", rel.type || rel.state || ""));
          card.appendChild(el("div", "big", rel.name || ""));
          var bits = [];
          if (rel.where) bits.push(rel.where);
          if (rel.state) bits.push(rel.state);
          bits.push(rel.interactions + " interaction" + (rel.interactions === 1 ? "" : "s"));
          if (rel.last_interaction) bits.push("last " + ago(rel.last_interaction));
          card.appendChild(el("div", "sub", bits.join(" · ")));
          for (var n = 0; n < (rel.notes || []).length; n++) {{
            card.appendChild(el("div", "sub", rel.notes[n]));
          }}
          if (rel.pending) card.appendChild(el("div", "", "Pending: " + rel.pending));
          rl.appendChild(card);
        }}
      }} else if (name === "capabilities") {{
        var cc = await getJSON("/api/capabilities");
        var cl = $("cap-list"); cl.textContent = "";
        var caps = cc.capabilities || [];
        if (!caps.length) cl.appendChild(el("div", "sub", "No verified installed capabilities in this view."));
        for (var p = 0; p < caps.length; p++) {{
          var cap = caps[p];
          var cc0 = el("div", "ev");
          cc0.appendChild(el("div", "c", cap.installed ? "installed" : "not installed"));
          cc0.appendChild(el("div", "big", cap.name || cap.id));
          if (cap.state && cap.state !== "INSTALLED_EXECUTABLE") cc0.appendChild(el("div", "sub", cap.state.replaceAll("_", " ").toLowerCase()));
          if (cap.description) cc0.appendChild(el("div", "sub", cap.description));
          for (var q = 0; q < (cap.skills || []).length; q++) {{
            var sk = cap.skills[q];
            cc0.appendChild(el("div", sk.allowed ? "" : "warn",
              (sk.executable === true ? "✓ " : (!sk.allowed ? "Permission required · " : (sk.state === "INSTALLED_PROVIDER_UNAVAILABLE" ? "Provider unavailable · " : sk.state === "INSTALLED_DEPENDENCY_UNAVAILABLE" ? "Dependency unavailable · " : sk.state === "INSTALLED_MISCONFIGURED" ? "Configuration required · " : "Readiness unverified · "))) + sk.name));
            if (sk.provenance) {{
              cc0.appendChild(el("div", "sub", "Provided by " + sk.provenance.provider + " · acceptance tested by " + sk.provenance.accepted_by));
              cc0.appendChild(el("div", "sub", "Job " + sk.provenance.job + " · " + sk.provenance.fingerprint));
            }}
            if (!sk.allowed && sk.limited_explanation) {{
              cc0.appendChild(el("div", "sub", sk.limited_explanation));
            }} else if (!sk.allowed && sk.reason) {{
              cc0.appendChild(el("div", "sub", sk.reason));
            }}
          }}
          cl.appendChild(cc0);
        }}
      }} else if (name === "messages") {{
        await pullMessages();
      }}
    }} catch (e) {{}}
  }}
  $("composer").addEventListener("submit", async function (e) {{
    e.preventDefault();
    var box = $("composer-text");
    var err = $("composer-err");
    err.textContent = "";
    var text = box.value.trim();
    if (!text) return;
    try {{
      var r = await fetch("/api/messages", {{
        method: "POST",
        headers: {{"Content-Type": "application/json", "X-Requested-With": "AsterControl"}},
        body: JSON.stringify({{text: text}})
      }});
      var data = await r.json().catch(function () {{ return {{}}; }});
      if (!r.ok) throw new Error((data && data.error) || ("http " + r.status));
      box.value = "";
      await pullMessages();
    }} catch (ex) {{
      err.textContent = "Send failed: " + ex.message;
    }}
  }});
  setInterval(tick, 1000);
  setInterval(function () {{ if (!document.hidden && activeTab === "overview") refresh(); }}, {REFRESH_SECONDS} * 1000);
  setInterval(function () {{ if (!document.hidden && activeTab === "messages") pullMessages().catch(function () {{}}); }}, {MESSAGES_POLL_SECONDS} * 1000);
  setInterval(function () {{ if (!document.hidden && activeTab === "activity") pull("activity"); }}, {ACTIVITY_POLL_SECONDS} * 1000);
  setInterval(function () {{ if (!document.hidden && (activeTab === "relationships" || activeTab === "capabilities" || activeTab === "work")) pull(activeTab); }}, {SLOW_POLL_SECONDS} * 1000);
  refresh();
}})();
</script>
</body>
</html>"""


# ── control API: sanitizers ───────────────────────────────────────────────

def _clip(value: Any, limit: int) -> str:
    text = "" if value is None else str(value)
    return text if len(text) <= limit else text[:limit] + "…"


def _timeline(store: Any, *, limit: int = 30) -> list[dict[str, Any]]:
    """Sanitized recent activity from provenance + notifications.

    Only timestamp, category, summary, and short outcome are exposed.
    Evidence arrays and refs are deliberately excluded: they may carry
    operational details (addresses, excerpts) that have no place in the UI.
    """
    entries: list[dict[str, Any]] = []
    for item in store.list_provenance(limit=1000):
        entries.append({
            "at": item.at,
            "category": item.phase.value if hasattr(item.phase, "value") else str(item.phase),
            "description": _clip(item.summary, 280),
            "outcome": _clip(item.result, 200),
        })
    for note in store.list_notifications()[-max(1, limit):]:
        entries.append({
            "at": getattr(note, "at", ""),
            "category": f"notification:{getattr(note, 'kind', '')}",
            "description": _clip(getattr(note, "summary", ""), 280),
            "outcome": "unread" if not getattr(note, "read", True) else "read",
        })
    # Group the read model only; underlying provenance remains untouched.
    from core.services.integration import existing_store
    from datetime import datetime, timezone
    services = existing_store(store._storage)
    if services:
        identity = store.identity_id
        for event in services.rows('SELECT kind,job,created FROM events WHERE identity=? ORDER BY seq DESC LIMIT 100', (identity,)):
            entries.append({'at':datetime.fromtimestamp(event['created'],timezone.utc).isoformat(),
                'category':'service','description':event['kind'].replace('_',' '),
                'outcome':event['job'] or ''})
    entries.sort(key=lambda e: e["at"] or "", reverse=True)
    groups = {}
    for entry in entries:
        key = (entry['category'],entry['description'],entry['outcome'])
        if key not in groups:
            groups[key] = dict(entry, count=1, first_at=entry['at'])
        else:
            groups[key]['count'] += 1
            groups[key]['first_at'] = entry['at']
    return list(groups.values())[:max(1,limit)]


def _relationship_cards(store: Any) -> list[dict[str, Any]]:
    """Sanitized relationships. Email addresses are never exposed."""
    cards: list[dict[str, Any]] = []
    for rel in store.list_relationships():
        last = [t for t in (
            getattr(rel, "last_inbound_at", None),
            getattr(rel, "last_outbound_at", None),
        ) if t]
        notes = [_clip(n, 200) for n in (getattr(rel, "notes", None) or [])][-5:]
        thread_ids = list(getattr(rel, "thread_ids", None) or [])
        cards.append({
            "id": rel.id,
            "name": _clip(getattr(rel, "display_name", ""), 120) or "(unnamed)",
            "type": _clip(getattr(rel, "role", "") or getattr(rel, "purpose", ""), 160),
            "state": rel.status.value if hasattr(rel.status, "value") else str(rel.status),
            "where": _clip(getattr(rel, "organization", ""), 160),
            "first_contact": getattr(rel, "first_contacted_at", None),
            "last_interaction": max(last) if last else None,
            "interactions": len(getattr(rel, "message_ids", None) or []),
            "threads": len(thread_ids),
            "notes": notes,
            "pending": _clip(getattr(rel, "next_action", ""), 200),
        })
    cards.sort(key=lambda c: c["last_interaction"] or "", reverse=True)
    return cards


def _capability_cards(registry: Any, identity_id: str, store: Any) -> list[dict[str, Any]]:
    """Thin UI adapter over canonical read-only self-state; never reload/install."""
    from core.self_knowledge import SelfKnowledge
    snapshot = SelfKnowledge(registry._storage, identity_id).snapshot(['capabilities','jobs'])
    data = snapshot['sections']['capabilities'].get('data') or {}
    jobs = (snapshot['sections']['jobs'].get('data') or {}).get('items', [])
    cards = []
    for cap_id, provider in data.get('providers', {}).items():
        skills = []
        for name, skill in data.get('skills', {}).items():
            if skill['provider'] != cap_id: continue
            accepted = [j for j in jobs if j['verified_completed'] and j['requester'] == identity_id]
            provenance = None
            # Artifact config stays private. Match fingerprint through stored safe bundle metadata.
            if cap_id == 'service_artifacts':
                installed = registry._storage.load(identity_id, 'capabilities') or {}
                entry = next((e for e in installed.get('installed',[]) if e['id']==cap_id), {})
                digest = entry.get('config',{}).get('bundles',{}).get(name,{}).get('fingerprint')
                match = next((j for j in accepted if j['artifact']==digest), None)
                if match: provenance = {'provider':match['provider'],'job':match['id'],'fingerprint':digest,'accepted_by':identity_id}
            skills.append({'name':name,'allowed':skill['authority'],'executable':skill['executable'],
                'state':skill['state'],'classification':skill['classification'],
                'permission':', '.join(skill['required_permissions']),'reason':skill['reason'],
                'limited_explanation':skill['reason'] if not skill['authority'] else '',
                'provenance':provenance})
        cards.append({'id':cap_id,'name':cap_id,'version':provider.get('version'),'installed':True,
                      'state':provider['state'],'description':'','skills':skills,'last_used':'unknown'})
    return cards


def _message_cards(store: Any, *, limit: int = 50) -> list[dict[str, Any]]:
    """Principal conversation envelopes. Bodies belong to the principal's own
    conversation and are visible here — and nowhere else in the UI."""
    from core.operations.principal import CONTROL_CHANNEL, thread_messages

    cards: list[dict[str, Any]] = []
    for message in thread_messages(store, limit=limit):
        response_id = ""
        detail = ""
        for piece in message.evidence or []:
            if not isinstance(piece, str):
                continue
            if piece.startswith("response:"):
                response_id = piece.split(":", 1)[1]
            elif piece and not detail:
                detail = piece[:300]
        generation = dict(message.generation or {})
        cards.append({
            "id": message.id,
            "direction": message.direction.value if hasattr(message.direction, "value") else str(message.direction),
            "body": message.body or "",
            "status": message.status.value if hasattr(message.status, "value") else str(message.status),
            "created_at": message.created_at,
            "received_at": message.received_at,
            "sent_at": message.sent_at,
            "in_reply_to": message.in_reply_to or "",
            "thread_id": message.thread_id or "",
            "response_id": response_id,
            "detail": detail,
            "runtime_evidence": generation.get("grounding"),
            "via": {
                "mode": generation.get("mode", ""),
                "adapter": generation.get("adapter", ""),
                "model": generation.get("model", ""),
            },
        })
    return cards


# ── control API: principal verification ───────────────────────────────────

def _expected_login() -> str:
    return (os.environ.get("ASTER_BUILDER_LOGIN", "") or "").strip()


def _expected_host() -> str:
    return (os.environ.get("ASTER_TAILNET_HOST", "") or "").strip().lower()


def _principal_verified(handler: BaseHTTPRequestHandler) -> tuple[bool, str]:
    """Verify a state-changing request comes from the builder via the Tailnet.

    Three independent checks, all required:
    1. Host must be the Tailnet hostname. Tailscale Serve forwards the
       original Host; direct-local requests (Host: localhost/127.0.0.1)
       fail here even with forged identity headers.
    2. Tailscale-User-Login must exactly match the configured builder login.
       Tailscale Serve injects this for genuine Tailnet viewers.
    3. Anti-CSRF marker: browsers issuing cross-site requests cannot set
       X-Requested-With (preflight fails — we never emit CORS headers), so
       ordinary CSRF forms/fetch are rejected. Same-origin UI sets it.
    """
    host = (handler.headers.get("Host", "") or "").split(":")[0].strip().lower()
    expected_host = _expected_host()
    if not expected_host or host != expected_host:
        return False, "untrusted host"
    login = (handler.headers.get("Tailscale-User-Login", "") or "").strip()
    expected_login = _expected_login()
    if not expected_login or login != expected_login:
        return False, "principal not verified"
    if not handler.headers.get("X-Requested-With"):
        origin = (handler.headers.get("Origin", "") or handler.headers.get("Referer", ""))
        if expected_host not in origin.lower():
            return False, "missing request marker"
    return True, ""


def _post_rate_ok() -> bool:
    bucket = int(time.time() // 60)
    with _post_minutes_lock:
        _post_minutes[bucket] = _post_minutes.get(bucket, 0) + 1
        for old in [k for k in _post_minutes if k < bucket - 1]:
            del _post_minutes[old]
        return _post_minutes[bucket] <= MAX_POSTS_PER_MINUTE


# ── PWA assets ────────────────────────────────────────────────────────────

APP_MANIFEST = {
    "name": "Aster",
    "short_name": "Aster",
    "description": "Private Aster Control for IdentityOS",
    "display": "standalone",
    "orientation": "portrait",
    "background_color": "#0b0f14",
    "theme_color": "#0b0f14",
    "start_url": "/status",
    "scope": "/",
    "icons": [
        {"src": "/icon.svg", "sizes": "any", "type": "image/svg+xml", "purpose": "any"}
    ],
}

ICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">
<rect width="128" height="128" rx="28" fill="#0b0f14"/>
<circle cx="64" cy="64" r="34" fill="none" stroke="#34d17b" stroke-width="6"/>
<circle cx="64" cy="64" r="12" fill="#34d17b"/>
<circle cx="64" cy="18" r="5" fill="#5aa9ff"/>
</svg>
"""


class _HealthHandler(BaseHTTPRequestHandler):
    presence_store: Optional[PresenceStore] = None

    def log_message(self, format: str, *args: Any) -> None:
        # Suppress default log noise; serve() prints its own startup line.
        pass

    def _backend(self):
        """Build store/registry accessors bound to this server's storage."""
        presence = self.presence_store
        storage = presence._storage if presence is not None else None
        identity_id = presence.identity_id if presence is not None else "aster"
        return storage, identity_id

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/manifest.json":
            self._send(200, json.dumps(APP_MANIFEST, indent=2).encode("utf-8"),
                       "application/manifest+json")
            return
        if path == "/icon.svg":
            self._send(200, ICON_SVG.encode("utf-8"), "image/svg+xml")
            return
        if not path.startswith("/api/self") and path not in ("/health", "/status", "/api/presence", "/api/activity",
                        "/api/relationships", "/api/capabilities", "/api/messages", "/api/work"):
            self._send(404, b'{"error": "not found"}', "application/json")
            return

        if self.presence_store is None:
            self._send(503, b'{"error": "presence store not initialized"}', "application/json")
            return

        view = self.presence_store.public_view()
        if path == "/status":
            body = render_dashboard(view).encode("utf-8")
            self._send(200, body, "text/html; charset=utf-8")
            return
        if path in ("/health", "/api/presence"):
            body = json.dumps(view, indent=2).encode("utf-8")
            self._send(200, body, "application/json; charset=utf-8")
            return
        self._serve_read_api(path, parsed)

    def _serve_read_api(self, path: str, parsed: Any) -> None:
        from urllib.parse import parse_qs

        from core.operations.store import OperationsStore

        storage, identity_id = self._backend()
        if storage is None:
            self._send(503, b'{"error": "storage not initialized"}', "application/json")
            return
        if path == '/api/self' or path.startswith('/api/self/'):
            from core.self_knowledge import SelfKnowledge, SECTIONS
            section = path[len('/api/self/'): ] if path.startswith('/api/self/') else None
            if section and section not in SECTIONS:
                self._send(404, b'{"error":"unknown self-state section"}', "application/json")
                return
            payload = SelfKnowledge(storage, identity_id).snapshot([section] if section else None)
            self._send(200, json.dumps(payload).encode('utf-8'), "application/json; charset=utf-8")
            return
        store = OperationsStore(storage, identity_id)
        try:
            limit = int(parse_qs(parsed.query).get("limit", ["30"])[0])
        except (ValueError, TypeError):
            limit = 30
        limit = max(1, min(100, limit))
        try:
            if path == "/api/activity":
                payload = {"events": _timeline(store, limit=limit)}
            elif path == "/api/work":
                from core.services.integration import work_cards
                payload = {"jobs": work_cards(storage, identity_id)}
            elif path == "/api/relationships":
                payload = {"relationships": _relationship_cards(store)}
            elif path == "/api/capabilities":
                from core.capabilities.registry import CapabilityRegistry

                payload = {"capabilities": _capability_cards(
                    CapabilityRegistry(storage), identity_id, store)}
            elif path == "/api/messages":
                payload = {"messages": _message_cards(store, limit=limit)}
            else:
                self._send(404, b'{"error": "not found"}', "application/json")
                return
        except Exception as exc:
            self._send(500, json.dumps({"error": f"{type(exc).__name__}"}).encode(),
                       "application/json")
            return
        self._send(200, json.dumps(payload).encode("utf-8"), "application/json; charset=utf-8")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/api/messages":
            self._send(404, b'{"error": "not found"}', "application/json")
            return
        if self.presence_store is None:
            self._send(503, b'{"error": "presence store not initialized"}', "application/json")
            return
        ok, reason = _principal_verified(self)
        if not ok:
            self._send(403, json.dumps({"error": reason}).encode("utf-8"),
                       "application/json")
            return
        if not _post_rate_ok():
            self._send(429, b'{"error": "rate limit: slow down"}', "application/json")
            return
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
        except ValueError:
            length = 0
        if length <= 0 or length > MAX_POST_BYTES:
            self._send(400, b'{"error": "invalid request size"}', "application/json")
            return
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            self._send(400, b'{"error": "invalid JSON"}', "application/json")
            return
        text = payload.get("text", "") if isinstance(payload, dict) else ""
        thread_id = payload.get("thread_id", "") if isinstance(payload, dict) else ""
        if not isinstance(text, str) or not isinstance(thread_id, str):
            self._send(400, b'{"error": "invalid parameters"}', "application/json")
            return

        from core.operations.store import OperationsStore
        from core.operations.principal import submit_principal_message

        storage, identity_id = self._backend()
        store = OperationsStore(storage, identity_id)
        try:
            message = submit_principal_message(store, text, thread_id=thread_id.strip())
        except ValueError as exc:
            self._send(400, json.dumps({"error": str(exc)}).encode("utf-8"),
                       "application/json")
            return
        except RuntimeError as exc:
            self._send(429, json.dumps({"error": str(exc)}).encode("utf-8"),
                       "application/json")
            return
        self._send(201, json.dumps({
            "id": message.id,
            "status": message.status.value,
            "created_at": message.created_at,
        }).encode("utf-8"), "application/json; charset=utf-8")

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def build_presence_store(
    store_dir: str,
    backend_type: str,
    identity_id: str = "aster",
) -> PresenceStore:
    backend_kwargs = {}
    if backend_type == "sqlite":
        from pathlib import Path
        backend_kwargs["db_path"] = str(Path(store_dir) / "identities.db")
    else:
        backend_kwargs["root_dir"] = store_dir
    storage = get_backend(backend_type, **backend_kwargs)
    return PresenceStore(storage, identity_id)


def serve(
    host: str = "127.0.0.1",
    port: int = 8787,
    store: str = ".identity_store",
    backend: str = "json",
    identity: str = "aster",
) -> None:
    """Run the health endpoint server (blocks until shutdown)."""
    presence = build_presence_store(store, backend, identity)
    _HealthHandler.presence_store = presence

    server = ThreadingHTTPServer((host, port), _HealthHandler)
    print(f"Health server listening on http://{host}:{port}/health  (GET /health, /status)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        server.server_close()


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="IdentityOS presence health endpoint")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8787, help="Port (default: 8787)")
    parser.add_argument("--store", default=".identity_store", help="Identity store directory")
    parser.add_argument("--backend", choices=["json", "sqlite"], default="json", help="Storage backend")
    parser.add_argument("--identity", default="aster", help="Identity ID")
    args = parser.parse_args(argv)

    serve(host=args.host, port=args.port, store=args.store, backend=args.backend, identity=args.identity)
    return 0


if __name__ == "__main__":
    sys.exit(main())