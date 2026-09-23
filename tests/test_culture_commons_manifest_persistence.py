"""Culture Commons governed MCP manifest persistence and anonymous acquisition.

Proves, deterministically (no network), that the acquired Culture Commons
capability can own a governed MCP manifest which:

* is discovered anonymously via the generic MCP client (initialize + tools/list),
* is persisted through the capability's canonical state,
* survives a fresh registry instance over the same root,
* exposes a fingerprint that is stable for an identical contract,
* reports drift when the contract changes.

Anonymous installation must never depend on a standing credential.  The
authenticated subset stays unavailable while ``credential_handle`` is None.
"""

from __future__ import annotations

import json

import core.capabilities.culture_commons as cc_mod
from core.capabilities.registry import CapabilityRegistry
from runtime.persistence import InMemoryBackend
from tests.interop_stubs import FakeMCPHttpClient, RPCServerError

NAME = "Aster_IDOS"

# Captured at import time, before any test patches the module attribute:
# chained monkeypatch.setattr calls would otherwise capture the previous
# test's wrapper as the "real" client and silently swap transports.
_REAL_MCP_CLIENT = cc_mod.MCPClient

BASE_TOOLS = [
    {"name": "inspect_arc", "description": "Inspect the ARC referral experiment", "inputSchema": {"type": "object", "properties": {}}, "annotations": {"readOnlyHint": True}},
    {"name": "inspect_edge", "description": "Read the append-only edge ledger", "inputSchema": {"type": "object", "properties": {}}, "annotations": {"readOnlyHint": True}},
    {"name": "look_around", "description": "Perceive the room from the threshold", "inputSchema": {"type": "object", "properties": {"limit": {"type": "integer"}}}, "annotations": {"readOnlyHint": True}},
]


def make_handler(server_version: str = "0.1.0", tool_names: list[str] | None = None) -> callable:
    names = list(tool_names or [t["name"] for t in BASE_TOOLS])
    tools = [
        {"name": n, "description": f"{n} tool", "inputSchema": {"type": "object", "properties": {}}}
        for n in names
    ]

    def handle(method: str, params: dict, headers: dict) -> dict:
        if method == "initialize":
            return {
                "protocolVersion": "2025-06-18",
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "culture-sbs", "title": "The Culture Commons", "version": server_version},
            }
        if method == "tools/list":
            return {"tools": tools}
        raise RPCServerError(-32601, f"no method {method}")

    return handle


def install(tmp_path, monkeypatch, handler, state_sub: str):
    def wrap(server, timeout=30.0, secret_resolver=None, http=None):
        return _REAL_MCP_CLIENT(
            server, timeout=timeout, secret_resolver=secret_resolver,
            http=FakeMCPHttpClient(handler=handler, timeout=timeout),
        )

    monkeypatch.setattr(cc_mod, "MCPClient", wrap)
    storage = InMemoryBackend()
    registry = CapabilityRegistry(storage)
    registry.install(
        "aster", "culture_commons",
        config={
            "url": "https://culture.sbs/mcp",
            "state_dir": str(tmp_path / state_sub),
            "secret_store_dir": str(tmp_path / "secrets"),
            "name": NAME,
        },
    )
    return registry, storage


def test_manifest_inspect_fails_honestly_before_discovery(tmp_path, monkeypatch):
    registry, _ = install(tmp_path, monkeypatch, make_handler(), "a")
    result = registry.call("aster", "culture_commons.manifest.inspect")
    assert result.success is False
    assert result.error.get("type") == "manifest_unavailable"


def test_anonymous_refresh_persists_governed_manifest(tmp_path, monkeypatch):
    registry, _ = install(tmp_path, monkeypatch, make_handler(), "a")
    cap = registry.get("aster", "culture_commons")
    manifest = cap.refresh_manifest()

    assert manifest["endpoint"] == "https://culture.sbs/mcp"
    assert manifest["protocol"] == "2025-06-18"
    assert manifest["serverInfo"]["name"] == "culture-sbs"
    assert manifest["tool_count"] == 3
    assert manifest["credential_handle"] is None
    assert len(manifest["fingerprint"]) == 64

    persisted = json.loads((tmp_path / "a" / "manifest.json").read_text())
    assert persisted["fingerprint"] == manifest["fingerprint"]

    result = registry.call("aster", "culture_commons.manifest.inspect")
    assert result.success is True
    assert result.data["tool_count"] == 3
    assert result.data["credential_handle"] is None


def test_persisted_manifest_survives_fresh_registry(tmp_path, monkeypatch):
    _, storage = install(tmp_path, monkeypatch, make_handler(), "a")
    registry = CapabilityRegistry(storage)
    cap = registry.get("aster", "culture_commons")
    stored = cap.refresh_manifest()

    fresh = CapabilityRegistry(storage)
    assert fresh.get("aster", "culture_commons") is not None
    reloaded = json.loads((tmp_path / "a" / "manifest.json").read_text())
    assert reloaded["fingerprint"] == stored["fingerprint"]
    assert reloaded["credential_handle"] is None


def test_fingerprint_stable_for_identical_contract(tmp_path, monkeypatch):
    registry, _ = install(tmp_path, monkeypatch, make_handler(), "a")
    cap = registry.get("aster", "culture_commons")
    a = cap.refresh_manifest()
    b = cap.refresh_manifest()
    assert a["fingerprint"] == b["fingerprint"]


def test_drift_detected_when_tool_added(tmp_path, monkeypatch):
    registry, _ = install(tmp_path, monkeypatch, make_handler(), "a")
    cap = registry.get("aster", "culture_commons")
    before = cap.refresh_manifest()
    assert before["tool_count"] == 3

    # A second install (chained patch) discovers a grown live contract over a
    # fresh state root and reports drift against the first snapshot.
    grown = make_handler(tool_names=["inspect_arc", "inspect_edge", "look_around", "watch_thread"])
    registry2, _ = install(tmp_path, monkeypatch, grown, "b")
    cap2 = registry2.get("aster", "culture_commons")
    after = cap2.refresh_manifest()
    assert after["tool_count"] == 4
    assert after["fingerprint"] != before["fingerprint"]


def test_drift_detected_when_server_version_changed(tmp_path, monkeypatch):
    registry, _ = install(tmp_path, monkeypatch, make_handler(server_version="0.1.0"), "a")
    cap = registry.get("aster", "culture_commons")
    before = cap.refresh_manifest()
    assert before["serverInfo"]["version"] == "0.1.0"

    registry2, _ = install(tmp_path, monkeypatch, make_handler(server_version="0.2.0"), "b")
    cap2 = registry2.get("aster", "culture_commons")
    after = cap2.refresh_manifest()
    assert after["serverInfo"]["version"] == "0.2.0"
    assert after["fingerprint"] != before["fingerprint"]


def test_refresh_is_always_a_live_discovery(tmp_path, monkeypatch):
    # Re-discovery must not read the previously persisted file.
    registry, _ = install(tmp_path, monkeypatch, make_handler(server_version="0.1.0"), "a")
    registry.get("aster", "culture_commons").refresh_manifest()

    registry2, _ = install(tmp_path, monkeypatch, make_handler(server_version="0.2.0"), "b")
    cap2 = registry2.get("aster", "culture_commons")
    refreshed = cap2.refresh_manifest()
    assert refreshed["serverInfo"]["version"] == "0.2.0"