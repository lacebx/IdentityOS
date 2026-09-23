"""
runtime/health_server.py — localhost-only machine-readable presence endpoint.

GET /health  -> sanitized presence view (health, status, activity, heartbeat, etc.)
GET /status  -> same as /health (alias for convenience)

Zero model calls. Binds localhost only by default. No secrets exposed.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Optional

from core.operations.presence import PresenceStore
from runtime.persistence import get_backend


class _HealthHandler(BaseHTTPRequestHandler):
    presence_store: Optional[PresenceStore] = None

    def log_message(self, format: str, *args: Any) -> None:
        # Suppress default log noise; we'll print our own on start
        pass

    def do_GET(self) -> None:
        path = self.path.split("?")[0]
        if path not in ("/health", "/status"):
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"error": "not found"}')
            return

        if self.presence_store is None:
            self.send_response(503)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"error": "presence store not initialized"}')
            return

        view = self.presence_store.public_view()
        body = json.dumps(view, indent=2).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
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