"""Unit tests for the native messaging framing helpers.

OS pipes and sockets may deliver frames in many small chunks. These tests
verify the exact-read / exact-write helpers tolerate partial reads and
writes, which is required for large frames (e.g. tab lists with base64
favicons) that exceed the OS pipe buffer. The full relay handshake is
covered end-to-end by tests/test_live_bridge_e2e.py.
"""

from __future__ import annotations

import json
import struct

from browser_extension.native_host import (
    _read_exact,
    _recv_exact,
    _write_all,
)


class _PartialReader:
    """Return at most ``chunk_size`` bytes per read, like a real pipe."""

    def __init__(self, payload: bytes, chunk_size: int = 1):
        self.payload = payload
        self.chunk_size = chunk_size
        self.offset = 0

    def read(self, n: int) -> bytes:
        take = min(n, self.chunk_size, len(self.payload) - self.offset)
        chunk = self.payload[self.offset : self.offset + take]
        self.offset += take
        return chunk


class _ChunkingSink:
    def __init__(self, max_write: int = 3):
        self.buffer = bytearray()
        self.max_write = max_write

    def write(self, data: bytes) -> int:
        if len(data) > self.max_write:
            written = self.max_write
        else:
            written = len(data)
        self.buffer.extend(data[:written])
        return written

    def flush(self) -> None:
        pass


class _PartialSocket:
    def __init__(self, payload: bytes, chunk_size: int = 2):
        self.payload = payload
        self.chunk_size = chunk_size
        self.offset = 0

    def recv(self, n: int) -> bytes:
        take = min(n, self.chunk_size, len(self.payload) - self.offset)
        chunk = self.payload[self.offset : self.offset + take]
        self.offset += take
        return chunk


class TestExactReadHelpers:
    def test_read_exact_loops_over_partial_reads(self):
        payload = b"x" * 100_000
        assert _read_exact(_PartialReader(payload), len(payload)) == payload

    def test_read_exact_empty_stream_returns_short(self):
        assert _read_exact(_PartialReader(payload=b""), 8) == b""

    def test_recv_exact_loops_over_partial_socket_reads(self):
        payload = bytes(range(256)) * 500
        assert _recv_exact(_PartialSocket(payload), len(payload)) == payload


class TestExactWriteHelpers:
    def test_write_all_writes_every_byte(self):
        sink = _ChunkingSink(max_write=7)
        payload = b"y" * 50_000
        _write_all(sink, payload)
        assert bytes(sink.buffer) == payload


class TestLargeFrameRoundTrip:
    def test_frame_survives_partial_read_and_write(self):
        frame_payload = json.dumps(
            {"type": "list_tabs", "tabs": [{"id": i, "title": "t" * 1000} for i in range(200)]}
        ).encode()
        length_prefix = struct.pack("<I", len(frame_payload))
        frame = length_prefix + frame_payload
        assert len(frame) > 64 * 1024

        received = _read_exact(_PartialReader(frame, chunk_size=4096), len(frame))
        prefix, body = received[:4], received[4:]
        assert struct.unpack("<I", prefix)[0] == len(frame_payload)
        assert json.loads(body) == json.loads(frame_payload)