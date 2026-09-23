"""
runtime/health_server.py — localhost-only presence endpoint.

GET /health  -> sanitized presence JSON (machine-readable)
GET /status  -> mobile-friendly HTML dashboard (same real data, auto-refresh)

Zero model calls on any path. Binds localhost only by default. The dashboard
renders only sanitized ``public_view`` fields: no topics, phone numbers,
credentials, tokens, message contents, or chain-of-thought ever leave the box.
"""

from __future__ import annotations

import argparse
import html
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Optional

from core.operations.presence import PresenceStore
from runtime.persistence import get_backend

REFRESH_SECONDS = 15


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

  <div class="foot"><span id="updated">Loading…</span> · auto-refreshes every {REFRESH_SECONDS}s</div>
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
  setInterval(tick, 1000);
  setInterval(refresh, {REFRESH_SECONDS} * 1000);
  refresh();
}})();
</script>
</body>
</html>"""


class _HealthHandler(BaseHTTPRequestHandler):
    presence_store: Optional[PresenceStore] = None

    def log_message(self, format: str, *args: Any) -> None:
        # Suppress default log noise; serve() prints its own startup line.
        pass

    def do_GET(self) -> None:
        path = self.path.split("?")[0]
        if path not in ("/health", "/status"):
            self._send(404, b'{"error": "not found"}', "application/json")
            return

        if self.presence_store is None:
            self._send(503, b'{"error": "presence store not initialized"}', "application/json")
            return

        view = self.presence_store.public_view()
        if path == "/status":
            body = render_dashboard(view).encode("utf-8")
            self._send(200, body, "text/html; charset=utf-8")
        else:
            body = json.dumps(view, indent=2).encode("utf-8")
            self._send(200, body, "application/json; charset=utf-8")

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