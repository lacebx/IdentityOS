"""External experience → identity memory continuity (deterministic, no network).

Proves the full continuity chain without any live dependency:

    external byte → capability result → provenance → semantic memory

and that the chain survives a fresh runtime over the same persisted storage,
that recognition updates existing relationships instead of duplicating them,
and that failed observations never masquerade as current state.
"""

from __future__ import annotations

import json

import core.capabilities.culture_commons as cc_mod
from core.capabilities.culture_commons import CultureCommonsCapability
from core.capabilities.result import CapabilityResult
from core.identity_facts import FactDomain, FactSource
from identity_graph.graph import TrustLevel
from runtime.orchestrator import IdentityRuntime, InteractionRequest
from runtime.persistence import JSONFileBackend
from tests.interop_stubs import FakeMCPHttpClient, RPCServerError, TransportFailure

_REAL_MCP_CLIENT = cc_mod.MCPClient

ROOM_TEXT = (
    "The room is open. 2 present of 50 seats · 48 open · 0 waiting.\n\n"
    "Present now:\n"
    "  · hub — bot\n"
    "  · Selah — agent\n"
    "\n"
    "Room crossings through cursor 534:\n"
    "  #527 [19:29Z] Aster_IDOS entered\n"
    "  #534 [20:24Z] Aster_IDOS fell out of presence\n"
)


def make_handler(fail: bool = False, server_version: str = "0.1.0") -> callable:
    def handle(method: str, params: dict, headers: dict) -> dict:
        if fail:
            raise TransportFailure(503, "commons temporarily unavailable")
        if method == "initialize":
            return {
                "protocolVersion": "2025-06-18",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "culture-sbs", "title": "The Culture Commons", "version": server_version},
            }
        if method == "tools/list":
            return {"tools": [
                {"name": "look_around", "inputSchema": {"type": "object", "properties": {}}},
                {"name": "inspect_arc", "inputSchema": {"type": "object", "properties": {"name": {"type": "string"}}}},
            ]}
        if method == "tools/call":
            tool = params.get("name")
            if tool == "look_around":
                return {"room": {"present": [{"name": "hub", "kind": "bot"}, {"name": "Selah", "kind": "agent"}], "seats": 50}}
            if tool == "inspect_arc":
                return {"records": [{"recordId": {"value": "01MTEST", "trust": "machine_attested"}, "state": "closed"}]}
        raise RPCServerError(-32601, f"no method {method}")

    return handle


class ScriptedToolAdapter:
    """Deterministic fake model: calls the offered tool, then answers from it."""

    model = "scripted-test/1.0"

    def __init__(self, tool_name: str = "", answer: str = "Done.") -> None:
        self.tool_name = tool_name
        self.answer = answer
        self.offered_tools: list | None = None

    def generate(self, context, user_input, identity, tools=None, execute_tool=None,
                 tool_choice=None, **kwargs) -> str:
        self.offered_tools = tools
        if execute_tool and self.tool_name:
            result = execute_tool(self.tool_name.replace(".", "__"), {})
            return f"{self.answer}\n\nObserved: {str(result)[:400]}"
        return self.answer


def build_runtime(root, handler, adapter=None, monkeypatch=None) -> IdentityRuntime:
    def wrap(server, timeout=30.0, secret_resolver=None, http=None):
        return _REAL_MCP_CLIENT(
            server, timeout=timeout, secret_resolver=secret_resolver,
            http=FakeMCPHttpClient(handler=handler, timeout=timeout),
        )

    # Always patch through monkeypatch so the wrapper is restored after the
    # test; a leaked module patch chains into later test files' captures.
    if monkeypatch is not None:
        monkeypatch.setattr(cc_mod, "MCPClient", wrap)
    else:
        cc_mod.MCPClient = wrap
    storage = JSONFileBackend(root_dir=str(root))
    runtime = IdentityRuntime(storage=storage, adapter=adapter)
    spec_mod = __import__("core.identity", fromlist=["IdentitySpec"])
    runtime.register(spec_mod.IdentitySpec(
        id="aster", name="Aster",
        identity_class=spec_mod.IdentityClass.AGENT,
        tagline="continuity probe",
    ))
    runtime.capability_registry.install(
        "aster", "culture_commons",
        config={
            "url": "https://culture.sbs/mcp",
            "state_dir": str(root / "cc-state"),
            "secret_store_dir": str(root / "secrets"),
            "name": "Aster_IDOS",
        },
    )
    return runtime


def test_encounters_parsed_from_structured_room():
    enc = CultureCommonsCapability._encounters(
        {"room": {"present": [{"name": "hub", "kind": "bot"}, {"name": "Selah", "kind": "agent"}]}}
    )
    assert [e["name"] for e in enc] == ["hub", "Selah"]
    assert all(e["ref"].startswith("culture_commons:agent:") for e in enc)
    assert all(e["surface"] == "culture_commons" for e in enc)
    assert [e["kind"] for e in enc] == ["bot", "agent"]


def test_encounters_parsed_from_live_text_room():
    enc = CultureCommonsCapability._encounters({"content": [{"type": "text", "text": ROOM_TEXT}]})
    assert [e["name"] for e in enc] == ["hub", "Selah"]
    assert [e["kind"] for e in enc] == ["bot", "agent"]
    # crossings lines must not be parsed as present
    assert all("Aster_IDOS" not in e["name"] for e in enc)


def test_external_experience_persists_fact_memory_relationship(tmp_path, monkeypatch):
    adapter = ScriptedToolAdapter("culture_commons.room.read", "Checked the commons room.")
    runtime = build_runtime(tmp_path, make_handler(), monkeypatch=monkeypatch, adapter=adapter)
    sid = runtime.start_session("aster", user_id="doug")
    resp = runtime.process(InteractionRequest(
        identity_id="aster", user_input="Find out what is currently happening in Culture Commons.",
        user_id="doug", session_id=sid,
    ))
    assert resp.metadata["capability_results"], "capability evidence expected"
    assert resp.metadata["capability_results"][0]["success"] is True

    fact = runtime._fact_stores["aster"].find("external.culture_commons.culture_commons.room.read")
    assert fact is not None
    assert fact.domain == FactDomain.EXPERIENCE
    assert fact.source_capability == "culture_commons"
    assert fact.source == FactSource.RUNTIME_INFERRED
    assert fact.evidence_ids, "provenance evidence id expected"
    # Access mode is recorded from the capability result: no secret exists, so
    # the observation must be remembered as anonymous.
    assert fact.value.get("authenticated") is False

    external_mems = [
        m for m in runtime.memory_store.by_user("aster", "doug", include_shared=False)
        if "external" in m.tags and "culture_commons.room.read" in m.tags
    ]
    assert external_mems, "provenance-linked semantic memory expected"
    prov = external_mems[0].extra.get("provenance")
    assert prov["ref"] == fact.evidence_ids[0]
    assert prov["capability"] == "culture_commons"
    assert prov["external_refs"], "external entity refs expected"
    assert prov["authenticated"] is False

    edges = runtime.identity_graph.edges_from("aster")
    targets = {e.target_id for e in edges}
    assert "culture_commons:agent:hub" in targets
    assert "culture_commons:agent:Selah" in targets

    # Provenance chain: external byte → capability result → provenance → memory
    assert prov["ref"].startswith("culture_commons.culture_commons.room.read@")


def test_continuity_survives_fresh_runtime(tmp_path, monkeypatch):
    adapter = ScriptedToolAdapter("culture_commons.room.read", "Checked the commons room.")
    runtime = build_runtime(tmp_path, make_handler(), monkeypatch=monkeypatch, adapter=adapter)
    sid = runtime.start_session("aster")
    runtime.process(InteractionRequest(
        identity_id="aster", user_input="Find out what is currently happening in Culture Commons.",
        session_id=sid,
    ))
    fact_before = runtime._fact_stores["aster"].find("external.culture_commons.culture_commons.room.read")
    edge_before = next(
        e for e in (runtime.identity_graph.edges_from("aster"))
        if e.target_id == "culture_commons:agent:Selah"
    )

    # COMPLETE SHUTDOWN: drop every in-memory object; only persisted storage remains.
    runtime.shutdown()
    del runtime, adapter, sid

    fresh = IdentityRuntime(storage=JSONFileBackend(root_dir=str(tmp_path)))
    cc_mod.MCPClient = _REAL_MCP_CLIENT  # no network wrapper: recall must not dial out
    loaded = fresh.load("aster")
    assert loaded is not None
    assert fresh.capability_registry.get("aster", "culture_commons") is not None
    fact_after = fresh._fact_stores["aster"].find("external.culture_commons.culture_commons.room.read")
    assert fact_after is not None
    assert fact_after.evidence_ids == fact_before.evidence_ids
    edge_after = next(
        e for e in (fresh.identity_graph.edges_from("aster"))
        if e.target_id == "culture_commons:agent:Selah"
    )
    assert edge_after.interaction_count == edge_before.interaction_count
    external_mems = [
        m for m in fresh.memory_store.by_user("aster", "aster", include_shared=False)
        if "external" in m.tags
    ]
    assert external_mems


def test_recognition_updates_existing_relationship(tmp_path, monkeypatch):
    adapter = ScriptedToolAdapter("culture_commons.room.read", "Checked the commons room.")
    runtime = build_runtime(tmp_path, make_handler(), monkeypatch=monkeypatch, adapter=adapter)
    sid = runtime.start_session("aster")
    runtime.process(InteractionRequest(identity_id="aster", user_input="Look at Culture Commons.", session_id=sid))
    edge1 = next(
        e for e in (runtime.identity_graph.edges_from("aster"))
        if e.target_id == "culture_commons:agent:Selah"
    )
    first_seen = edge1.established_at
    count1 = edge1.interaction_count
    fact1 = runtime._fact_stores["aster"].find("external.culture_commons.culture_commons.room.read")

    sid2 = runtime.start_session("aster")
    runtime.process(InteractionRequest(identity_id="aster", user_input="Check the commons again.", session_id=sid2))
    edge2 = next(
        e for e in (runtime.identity_graph.edges_from("aster"))
        if e.target_id == "culture_commons:agent:Selah"
    )
    assert edge2.interaction_count == count1 + 1
    assert edge2.established_at == first_seen
    fact2 = runtime._fact_stores["aster"].find("external.culture_commons.culture_commons.room.read")
    # deterministic fake data → same value → reinforced (recognition, not duplicate)
    assert fact2.times_reinforced >= 1


def test_failed_observation_never_masquerades_as_current_state(tmp_path, monkeypatch):
    good = ScriptedToolAdapter("culture_commons.room.read", "Checked the commons room.")
    runtime = build_runtime(tmp_path, make_handler(), monkeypatch=monkeypatch, adapter=good)
    sid = runtime.start_session("aster")
    runtime.process(InteractionRequest(identity_id="aster", user_input="Look at Culture Commons.", session_id=sid))
    fact_before = runtime._fact_stores["aster"].find("external.culture_commons.culture_commons.room.read")
    value_before = fact_before.value

    # Session B: commons temporarily unavailable (transport failure)
    broken = build_runtime(tmp_path / "unused", make_handler(fail=True), monkeypatch=monkeypatch, adapter=ScriptedToolAdapter("culture_commons.room.read", "Tried to check."))
    broken._fact_stores["aster"] = runtime._fact_stores["aster"]
    sid2 = broken.start_session("aster")
    resp2 = broken.process(InteractionRequest(identity_id="aster", user_input="Check the commons again.", session_id=sid2))
    assert resp2.metadata["capability_results"][0]["success"] is False

    # The old fact is retained, unchanged; no new fact claims current state.
    fact_after = broken._fact_stores["aster"].find("external.culture_commons.culture_commons.room.read")
    assert fact_after.value == value_before
    assert fact_after.times_reinforced == fact_before.times_reinforced
    assert fact_after.last_confirmed == fact_before.last_confirmed


def test_no_capability_network_calls_during_pure_recall(tmp_path, monkeypatch):
    adapter = ScriptedToolAdapter("culture_commons.room.read", "Checked the commons room.")
    runtime = build_runtime(tmp_path, make_handler(), monkeypatch=monkeypatch, adapter=adapter)
    sid = runtime.start_session("aster")
    runtime.process(InteractionRequest(identity_id="aster", user_input="Look at Culture Commons.", session_id=sid))

    # Fresh runtime; instrument the MCP door so any capability network activity
    # during recall is counted. Recall must answer from persisted state alone.
    constructions: list[str] = []

    def counting(server, timeout=30.0, secret_resolver=None, http=None):
        constructions.append(str(getattr(server, "url", "")))
        return _REAL_MCP_CLIENT(server, timeout=timeout, secret_resolver=secret_resolver,
                                http=FakeMCPHttpClient(handler=make_handler(), timeout=timeout))

    monkeypatch.setattr(cc_mod, "MCPClient", counting)
    fresh = IdentityRuntime(storage=JSONFileBackend(root_dir=str(tmp_path)))
    fresh.load("aster")
    sid2 = fresh.start_session("aster")
    fresh.process(InteractionRequest(
        identity_id="aster", user_input="Have you been to Culture Commons before? What do you remember?",
        session_id=sid2,
    ))
    assert constructions == []
    assert fresh._fact_stores["aster"].find("external.culture_commons.culture_commons.room.read") is not None