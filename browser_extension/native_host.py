#!/usr/bin/env python3
"""
IdentityOS Live Browser Bridge - Native Messaging Host

Two roles share this executable:

* SERVER (default, spawned by Firefox when the WebExtension calls
  ``browser.runtime.connectNative``): owns the real tab state that the
  extension pushes over native messaging, and exposes it to relay clients
  over a Unix domain socket.  This process is the authority for what is
  actually open in the user's Firefox.

* RELAY (spawned by IdentityOS ``_NativeMessagingClient`` with ``--relay``):
  forwards length-prefixed JSON requests to the server's socket and returns
  the server's response.  If no server is reachable it truthfully reports
  that the live bridge is not connected.

Protocol on the socket is identical to Firefox native messaging
(4-byte little-endian length prefix + UTF-8 JSON), which keeps the relay
trivially transparent.
"""

import sys
import os
import json
import struct
import socket
import tempfile
import threading
import logging
from typing import Any, Dict, Optional, Tuple
from pathlib import Path

# Add IdentityOS root to path so internal imports work when installed standalone.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


def _default_socket_path() -> str:
    """Stable per-user socket path for the live bridge."""
    override = os.environ.get("IDENTITYOS_BRIDGE_SOCKET")
    if override:
        return override
    tmp = Path(tempfile.gettempdir())
    uid = os.getuid() if hasattr(os, "getuid") else "user"
    return str(tmp / f"identityos_live_bridge_{uid}.sock")


BRIDGE_SOCKET = _default_socket_path()


def _read_exact(stream: Any, n: int) -> bytes:
    """Read exactly *n* bytes from a pipe/file, tolerating partial reads.

    ``stream.read(n)`` (and ``socket.recv(n)``) may return fewer bytes than
    requested when a frame exceeds the OS buffer, so framing code must loop
    until the full frame has arrived.
    """
    buf = bytearray()
    while len(buf) < n:
        chunk = stream.read(n - len(buf))
        if not chunk:
            break
        buf.extend(chunk)
    return bytes(buf)


def _write_all(stream: Any, data: bytes) -> None:
    """Write all of *data*, tolerating partial writes on unbuffered pipes."""
    view = memoryview(data)
    while view:
        written = stream.write(view)
        if written is None:
            break
        view = view[written:]
    stream.flush()


def _recv_exact(conn: Any, n: int) -> bytes:
    """Receive exactly *n* bytes from a socket, tolerating partial reads."""
    buf = bytearray()
    while len(buf) < n:
        chunk = conn.recv(n - len(buf))
        if not chunk:
            break
        buf.extend(chunk)
    return bytes(buf)


class NativeMessagingHost:
    """Server role: owns the tab state synced by the WebExtension."""

    def __init__(self, socket_path: str = BRIDGE_SOCKET):
        self.socket_path = socket_path
        self.running = True
        self.tabs: Dict[Any, dict] = {}
        self.active_tab_id = None
        self._tabs_lock = threading.Lock()
        self._sync_ts = 0.0
        self._extension_connected = False
        self._socket_server: Optional[socket.socket] = None
        self._socket_conns: set = set()
        self._sockets_lock = threading.Lock()
        self._pending_commands: Dict[str, Tuple[socket.socket, Any]] = {}
        self._pending_lock = threading.Lock()
        self._command_counter = 0
        self._command_lock = threading.Lock()

    # ── Native messaging (extension) framing ────────────────────────────

    def read_message(self) -> Optional[Dict[str, Any]]:
        """Read a length-prefixed JSON message from stdin (from extension)."""
        try:
            length_bytes = _read_exact(sys.stdin.buffer, 4)
            if len(length_bytes) < 4:
                return None
            length = struct.unpack("@I", length_bytes)[0]
            message_bytes = _read_exact(sys.stdin.buffer, length)
            if len(message_bytes) < length:
                return None
            return json.loads(message_bytes.decode("utf-8"))
        except (struct.error, json.JSONDecodeError, EOFError) as e:
            logger.error(f"Error reading message: {e}")
            return None

    def write_message(self, message: Dict[str, Any]) -> bool:
        """Write a length-prefixed JSON message to stdout (to extension)."""
        try:
            encoded = json.dumps(message).encode("utf-8")
            _write_all(sys.stdout.buffer, struct.pack("@I", len(encoded)) + encoded)
            return True
        except Exception as e:
            logger.error(f"Error writing message: {e}")
            return False

    # ── Socket framing (relay <-> server) ───────────────────────────────

    @staticmethod
    def _frame(msg: Dict[str, Any]) -> bytes:
        encoded = json.dumps(msg).encode("utf-8")
        return struct.pack("@I", len(encoded)) + encoded

    @staticmethod
    def _unframe(conn) -> Optional[Dict[str, Any]]:
        length_bytes = _recv_exact(conn, 4)
        if len(length_bytes) < 4:
            return None
        length = struct.unpack("@I", length_bytes)[0]
        body = _recv_exact(conn, length)
        if len(body) < length:
            return None
        return json.loads(body.decode("utf-8"))

    def _send_socket(self, conn: socket.socket, msg: Dict[str, Any]) -> None:
        try:
            conn.sendall(self._frame(msg))
        except Exception as e:
            logger.error(f"Error sending to relay: {e}")

    # ── Extension <-> server state ──────────────────────────────────────

    def _handle_sync_tabs(self, message: Dict[str, Any]) -> None:
        tabs = message.get("tabs") or []
        cleaned = []
        for tab in tabs:
            cleaned.append({
                "id": tab.get("id"),
                "window_id": tab.get("windowId"),
                "active": bool(tab.get("active", False)),
                "title": tab.get("title") or "",
                "url": tab.get("url") or "about:blank",
                "favIconUrl": tab.get("favIconUrl") or "",
            })
        with self._tabs_lock:
            self.tabs = {t["id"]: t for t in cleaned}
            # Prefer the extension-reported active tab.
            active = message.get("active_tab_id")
            if active is None or active not in self.tabs:
                active = next((t["id"] for t in cleaned if t["active"]), None)
            self.active_tab_id = active
            self._sync_ts = message.get("timestamp", 0) or 0
        logger.info(f"Synced {len(cleaned)} real tabs")

    def _handle_extension_message(self, message: Dict[str, Any]) -> None:
        msg_type = message.get("type")
        if msg_type == "sync_tabs":
            self._extension_connected = True
            self._handle_sync_tabs(message)
            return
        if msg_type == "command_result":
            cmd_id = message.get("id")
            if cmd_id is not None:
                conn, req_id = self._pending_commands.pop(cmd_id, (None, None))
                if conn is not None:
                    if "error" in message:
                        self._send_socket(conn, {"id": req_id, "error": message["error"]})
                    else:
                        self._send_socket(conn, {"id": req_id, "result": message.get("result", {})})
            return
        # Legacy: extension asking the host directly (popup-driven). Answer
        # from the authoritative state or via a forward.
        logger.debug(f"Extension message: {msg_type}")

    # ── Socket client requests ──────────────────────────────────────────

    def _handle_relay_request(self, conn: socket.socket, message: Dict[str, Any]) -> None:
        req_id = message.get("id")
        msg_type = message.get("type")
        if req_id is None or msg_type is None:
            self._send_socket(conn, {"id": None, "error": "Invalid message"})
            return

        if msg_type == "status":
            with self._tabs_lock:
                self._send_socket(conn, {"id": req_id, "result": {
                    "connected": self._extension_connected,
                    "tabs_count": len(self.tabs),
                    "active_tab": self.active_tab_id,
                    "identity_id": "live_browser",
                    "synced": self._sync_ts,  # 0 when extension is absent
                }})
            return
        if msg_type == "list_tabs":
            with self._tabs_lock:
                self._send_socket(conn, {"id": req_id, "result": list(self.tabs.values())})
            return
        if msg_type == "active_tab":
            with self._tabs_lock:
                tab = self.tabs.get(self.active_tab_id) if self.active_tab_id else None
            self._send_socket(conn, {"id": req_id, "result": tab})
            return

        # All remaining types mutate the real browser and must be executed
        # by the extension. Forward to it and wait for command_result.
        if not self._extension_connected:
            self._send_socket(conn, {
                "id": req_id,
                "error": "Live browser bridge is not connected to a Firefox instance.",
            })
            return

        with self._command_lock:
            self._command_counter += 1
            cmd_id = f"cmd_{self._command_counter}"

        forwarded = {"id": cmd_id, "type": msg_type}
        allowlist = {
            "activate_tab", "create_tab", "close_tab", "snapshot",
            "navigate", "click", "fill", "type", "press",
        }
        if msg_type not in allowlist:
            self._send_socket(conn, {"id": req_id, "error": f"Unknown message type: {msg_type}"})
            return
        for key in ("tabId", "url", "selector", "value", "text", "key", "maxChars", "waitUntil"):
            if key in message:
                forwarded[key] = message[key]

        with self._pending_lock:
            self._pending_commands[cmd_id] = (conn, req_id)
        ok = self.write_message(forwarded)
        if not ok:
            with self._pending_lock:
                self._pending_commands.pop(cmd_id, None)
            self._send_socket(conn, {"id": req_id, "error": "Failed to forward command to extension"})

    # ── Socket listeners ────────────────────────────────────────────────

    def _accept_loop(self) -> None:
        while self.running:
            try:
                conn, _addr = self._socket_server.accept()
                with self._sockets_lock:
                    self._socket_conns.add(conn)
                threading.Thread(
                    target=self._socket_reader, args=(conn,), daemon=True
                ).start()
            except OSError:
                break

    def _socket_reader(self, conn: socket.socket) -> None:
        try:
            while self.running:
                message = self._unframe(conn)
                if message is None:
                    break
                self._handle_relay_request(conn, message)
        except Exception as e:
            logger.error(f"Socket reader error: {e}")
        finally:
            with self._sockets_lock:
                self._socket_conns.discard(conn)
            try:
                conn.close()
            except OSError:
                pass

    def _bind_socket(self) -> bool:
        try:
            if os.path.exists(self.socket_path):
                # Attempt to detect a stale socket: connect then immediately
                # almost-close; if refused, the socket is orphaned.
                probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                try:
                    probe.connect(self.socket_path)
                    probe.close()
                except OSError:
                    os.unlink(self.socket_path)
            server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            server.bind(self.socket_path)
            server.listen(16)
            self._socket_server = server
            threading.Thread(target=self._accept_loop, daemon=True).start()
            logger.info(f"Bridge socket listening at {self.socket_path}")
            return True
        except OSError as e:
            logger.warning(f"Could not bind bridge socket: {e}")
            return False

    # ── Main loop (extension native messaging) ──────────────────────────

    def run(self) -> None:
        logger.info("Native messaging host started (server role)")
        if not self._bind_socket():
            logger.warning("Socket unavailable; running without relay support")
        while self.running:
            message = self.read_message()
            if message is None:
                break
            self._handle_extension_message(message)
        logger.info("Native messaging host stopped")


class RelayClient:
    """Relay role: forwards IdentityOS requests to the server's socket."""

    def __init__(self, socket_path: str = BRIDGE_SOCKET):
        self.socket_path = socket_path
        self.running = True

    def _connect(self) -> socket.socket:
        conn = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        conn.connect(self.socket_path)
        return conn

    @staticmethod
    def _frame(msg: Dict[str, Any]) -> bytes:
        encoded = json.dumps(msg).encode("utf-8")
        return struct.pack("@I", len(encoded)) + encoded

    @staticmethod
    def _unframe(conn) -> Optional[Dict[str, Any]]:
        length_bytes = _recv_exact(conn, 4)
        if len(length_bytes) < 4:
            return None
        length = struct.unpack("@I", length_bytes)[0]
        body = _recv_exact(conn, length)
        if len(body) < length:
            return None
        return json.loads(body.decode("utf-8"))

    @staticmethod
    def _read_stdin() -> Optional[Dict[str, Any]]:
        try:
            length_bytes = _read_exact(sys.stdin.buffer, 4)
            if len(length_bytes) < 4:
                return None
            length = struct.unpack("@I", length_bytes)[0]
            message_bytes = _read_exact(sys.stdin.buffer, length)
            if len(message_bytes) < length:
                return None
            return json.loads(message_bytes.decode("utf-8"))
        except (struct.error, json.JSONDecodeError, EOFError) as e:
            logger.error(f"Error reading stdin message: {e}")
            return None

    def run(self) -> None:
        logger.info("Native messaging host started (relay role)")
        while self.running:
            message = self._read_stdin()
            if message is None:
                break
            response = self._round_trip(message)
            _write_all(sys.stdout.buffer, self._frame(response or {
                "id": message.get("id"),
                "error": "Live browser bridge is not connected to a Firefox instance.",
            }))
        logger.info("Relay stopped")

    def _round_trip(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        conn = None
        try:
            conn = self._connect()
            conn.sendall(self._frame(message))
            return self._unframe(conn)
        except OSError as e:
            logger.warning(f"No bridge server reachable: {e}")
            return None
        finally:
            if conn is not None:
                try:
                    conn.close()
                except OSError:
                    pass


def main() -> None:
    relay = "--relay" in sys.argv
    if relay:
        RelayClient().run()
    else:
        NativeMessagingHost().run()


if __name__ == "__main__":
    main()