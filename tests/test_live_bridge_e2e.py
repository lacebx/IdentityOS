"""End-to-end tests for the live browser bridge (native messaging two-process bridge).

These spawn the `native_host.py` SERVER (mimicking what Firefox launches for
the WebExtension) and a `--relay` client (mimicking what IdentityOS's
``_NativeMessagingClient`` launches). They do NOT require a real Firefox, so
they run in normal CI.
"""

from __future__ import annotations

import json
import os
import select
import socket
import struct
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HOST = ROOT / "browser_extension" / "native_host.py"


def _frame(msg: dict) -> bytes:
    return struct.pack("@I", len(json.dumps(msg).encode())) + json.dumps(msg).encode()


def _write_all(stream, data: bytes) -> None:
    """Write all bytes, tolerating partial writes on unbuffered pipes."""
    view = memoryview(data)
    while view:
        written = stream.write(view)
        if written is None:
            break
        view = view[written:]
    stream.flush()


def _send(proc: subprocess.Popen, msg: dict) -> None:
    _write_all(proc.stdin, _frame(msg))


def _large_tabs() -> list[dict]:
    """Tabs whose serialized payload comfortably exceeds a 64 KiB pipe buffer."""
    big = "data:image/png;base64," + ("A" * 200_000)
    return [
        {
            "id": 1,
            "windowId": 1,
            "active": True,
            "title": "Big Tab " + ("T" * 500),
            "url": "https://example.com/",
            "favIconUrl": big,
        },
        {"id": 2, "windowId": 1, "active": False, "title": "Small", "url": "https://small.example/"},
    ]


class _Pipe:
    """Length-prefixed JSON read/write over a subprocess stdio pipe."""

    def __init__(self, proc: subprocess.Popen, typename: str):
        self._proc = proc
        self._typename = typename
        self._target = getattr(proc, typename)

    def send(self, msg: dict) -> None:
        _send(self._proc, msg)

    def recv(self, timeout: float = 8.0) -> dict | None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            r, _, _ = select.select([self._target], [], [], max(0.1, deadline - time.time()))
            if not r:
                continue
            head = b""
            while len(head) < 4:
                chunk = self._target.read(4 - len(head))
                if not chunk:
                    return None
                head += chunk
            length = struct.unpack("@I", head)[0]
            body = b""
            while len(body) < length:
                chunk = self._target.read(length - len(body))
                if not chunk:
                    break
                body += chunk
            if len(body) < length:
                return None
            return json.loads(body.decode("utf-8"))
        return None


@pytest.fixture
def server_proc(tmp_path):
    """A SERVER-role process (like one spawned by Firefox)."""
    os.environ["IDENTITYOS_BRIDGE_SOCKET"] = str(tmp_path / "bridge.sock")
    proc = subprocess.Popen(
        [sys.executable, "-u", str(HOST)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        bufsize=0,
    )
    time.sleep(1.0)
    try:
        yield proc
    finally:
        proc.stdin.close()
        proc.terminate()
        proc.wait(timeout=5)


def test_bridge_serves_real_tab_state(server_proc, tmp_path):
    pipe = _Pipe(server_proc, "stdout")

    # 1. The extension pushes its real tab state.
    server_proc.stdin.write(_frame({
        "type": "sync_tabs",
        "timestamp": 1000,
        "tabs": [
            {"id": 1, "windowId": 1, "active": False, "title": "Search", "url": "https://example.com/search"},
            {"id": 2, "windowId": 1, "active": True, "title": "Docs", "url": "https://example.com/docs"},
            {"id": 3, "windowId": 2, "active": False, "title": "GitHub", "url": "https://github.com/"},
        ],
        "active_tab_id": 2,
    }))
    server_proc.stdin.flush()
    time.sleep(0.5)

    # 2. A relay client (the comet's transport) queries the server.
    relay = subprocess.Popen(
        [sys.executable, "-u", str(HOST), "--relay"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        bufsize=0,
    )
    try:
        relay_pipe = _Pipe(relay, "stdout")
        relay_pipe.send({"id": 1, "type": "status"})
        status = relay_pipe.recv()
        assert status is not None
        assert status["id"] == 1
        assert status["result"]["connected"] is True
        assert status["result"]["tabs_count"] == 3

        relay_pipe.send({"id": 2, "type": "list_tabs"})
        tabs = relay_pipe.recv()
        assert tabs is not None and tabs["id"] == 2
        assert len(tabs["result"]) == 3
        assert "https://github.com/" in [t["url"] for t in tabs["result"]]

        relay_pipe.send({"id": 3, "type": "active_tab"})
        active = relay_pipe.recv()
        assert active is not None and active["id"] == 3
        assert active["result"]["id"] == 2
    finally:
        relay.terminate()
        relay.wait(timeout=5)


def test_bridge_forwards_extension_command_and_relays_result(server_proc):
    pipe = _Pipe(server_proc, "stdout")

    server_proc.stdin.write(_frame({
        "type": "sync_tabs",
        "tabs": [{"id": 3, "windowId": 2, "active": True, "title": "GitHub", "url": "https://github.com/"}],
        "active_tab_id": 3,
        "timestamp": 1111,
    }))
    server_proc.stdin.flush()
    time.sleep(0.5)

    relay = subprocess.Popen(
        [sys.executable, "-u", str(HOST), "--relay"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        bufsize=0,
    )
    try:
        relay_pipe = _Pipe(relay, "stdout")
        relay_pipe.send({"id": 7, "type": "navigate", "tabId": 3, "url": "https://github.com/lacebx"})

        # The server forwards to the extension (server stdout)...
        ext_cmd = pipe.recv()
        assert ext_cmd is not None
        assert ext_cmd["type"] == "navigate"
        assert ext_cmd["tabId"] == 3
        cmd_id = ext_cmd["id"]

        # ...the extension completes and reports a real result...
        server_proc.stdin.write(_frame({
            "id": cmd_id, "type": "command_result",
            "result": {"ok": True, "url": "https://github.com/lacebx", "tab_id": 3, "status": "complete"},
        }))
        server_proc.stdin.flush()

        # ...and the relay gets the resolved result back.
        nav_resp = relay_pipe.recv()
        assert nav_resp is not None
        assert nav_resp["id"] == 7
        assert nav_resp["result"]["ok"] is True
    finally:
        relay.terminate()
        relay.wait(timeout=5)


def test_bridge_reports_not_connected_without_extension(server_proc):
    relay = subprocess.Popen(
        [sys.executable, "-u", str(HOST), "--relay"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        bufsize=0,
    )
    try:
        relay_pipe = _Pipe(relay, "stdout")
        relay_pipe.send({"id": 5, "type": "navigate", "tabId": 1, "url": "https://x.io"})
        resp = relay_pipe.recv()
        assert resp is not None and resp["id"] == 5
        assert "error" in resp and "not connected" in resp["error"]
    finally:
        relay.terminate()
        relay.wait(timeout=5)


def test_relay_reports_error_when_no_server_running(tmp_path):
    relay = subprocess.Popen(
        [sys.executable, "-u", str(HOST), "--relay"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        bufsize=0,
    )
    try:
        relay_pipe = _Pipe(relay, "stdout")
        relay_pipe.send({"id": 9, "type": "status"})
        resp = relay_pipe.recv()
        assert resp is not None and resp["id"] == 9
        assert "error" in resp and "not connected" in resp["error"]
    finally:
        relay.terminate()
        relay.wait(timeout=5)


def test_bridge_handles_large_frames(server_proc):
    """Regression: frames larger than the OS pipe buffer (~64 KiB) must not be
    truncated by single ``read(n)`` calls. Real tab syncs include base64
    favicons that routinely push ``list_tabs`` past this size."""
    _send(server_proc, {
        "type": "sync_tabs",
        "tabs": _large_tabs(),
        "active_tab_id": 1,
        "timestamp": 2000,
    })
    time.sleep(0.6)

    relay = subprocess.Popen(
        [sys.executable, "-u", str(HOST), "--relay"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        bufsize=0,
    )
    try:
        relay_pipe = _Pipe(relay, "stdout")
        relay_pipe.send({"id": 1, "type": "list_tabs"})
        tabs = relay_pipe.recv(timeout=15.0)
        assert tabs is not None and tabs["id"] == 1
        assert len(tabs["result"]) == 2
        big = next(t for t in tabs["result"] if t["id"] == 1)
        assert len(big["favIconUrl"]) > 200_000
    finally:
        relay.terminate()
        relay.wait(timeout=5)


def test_native_client_handles_large_frames(server_proc):
    """The IdentityOS-side client must also read complete large frames."""
    _send(server_proc, {
        "type": "sync_tabs",
        "tabs": _large_tabs(),
        "active_tab_id": 1,
        "timestamp": 2001,
    })
    time.sleep(0.6)

    from core.capabilities.browser import _NativeMessagingClient

    client = _NativeMessagingClient(host_script=str(HOST))
    try:
        tabs = client.send("browser", type="list_tabs")
        assert len(tabs) == 2
        big = next(t for t in tabs if t["id"] == 1)
        assert len(big["favIconUrl"]) > 200_000
    finally:
        client.close()