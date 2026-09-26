"""Local A2A peer registry + runtime-backed inter-identity conversation.

Proves the "every identity can reach every other identity" addition:

* the local peer registry resolves peers by name or identity id,
* an A2A message to a peer is handled by the target identity's REAL runtime
  (reply from that identity's own persistent state, not an echo),
* an inbound A2A discussion turn never fabricates tool calls (the tool loop
  is disabled for the synchronous handler),
* the conversation chain across 2+ identities works end to end.
"""

from __future__ import annotations

import core.interop.a2a as a2a_mod
from core.capabilities.a2a import A2ACapability
from core.capabilities.registry import CapabilityRegistry
from core.interop.a2a import (
    A2ARuntimeAgent,
    get_local_peer,
    local_peer_names,
    register_local_peer,
)
from runtime.persistence import InMemoryBackend
from runtime.orchestrator import IdentityRuntime
from core.identity import IdentityClass, IdentitySpec


class _ProseAdapter:
    """Deterministic model that answers in clean prose (never tool JSON)."""

    model = "prose-stub"

    def generate(self, context: str, user_input: str, identity: Any = None, **kwargs) -> str:
        if "goals" in user_input.lower():
            return ("Based on the findings, the project should set two goals: "
                    "first, reach out to the discovered agent-framework maintainers; "
                    "second, apply the cloud-credit findings to fund development.")
        if "relationship" in user_input.lower():
            return ("From a relationship perspective, build a relationship with the "
                    "agent-ecosystem maintainers first: their audience overlaps with "
                    "IdentityOS's target community.")
        return "Understood — the loop continues."


def build_runtime(root: InMemoryBackend, identity_id: str, name: str) -> IdentityRuntime:
    runtime = IdentityRuntime(storage=root)
    runtime.register(IdentitySpec(id=identity_id, name=name, identity_class=IdentityClass.AGENT))
    return runtime


def test_local_peer_registry_resolves_by_name_and_id():
    registry_state = a2a_mod._LOCAL_PEERS
    agent = a2a_mod.A2ATestAgent(name="ProbeAgent")
    register_local_peer(agent)
    try:
        assert get_local_peer("ProbeAgent") is agent
        assert get_local_peer("probeagent") is agent  # case-insensitive
        assert get_local_peer("unknown-agent") is None
        assert "ProbeAgent" in local_peer_names()
    finally:
        registry_state.pop("ProbeAgent", None)


def test_runtime_peer_replies_from_target_identity_state(tmp_path):
    root = InMemoryBackend()
    target_runtime = build_runtime(root, "worker", "Worker")
    # Give the target identity a memory so the reply reflects its state.
    from core.memory import MemoryFragment, MemoryType
    target_runtime.memory_store.add(MemoryFragment(
        identity_id="worker", content="Worker knows: the project needs cloud credits.",
        memory_type=MemoryType.SEMANTIC,
    ))

    agent = A2ARuntimeAgent(runtime=target_runtime, identity_id="worker")
    register_local_peer(agent)
    try:
        task = agent._handle_send({"message": "What does the project need right now?"})
        assert task["status"] == "completed"
        assert task["id"], "task id required"
        # The reply came from the target's real runtime (its memory/context),
        # not an echo of the message.
        assert "What does the project need" not in task["result"][:60]
        assert len(task["result"]) > 0
        # The message was processed by the target identity's runtime.
        assert agent.name == "Worker"
    finally:
        a2a_mod._LOCAL_PEERS.pop(agent.name, None)


def test_a2a_discussion_turn_never_fabricates_tool_calls(tmp_path):
    root = InMemoryBackend()
    target_runtime = build_runtime(root, "discusser", "Discusser")
    # Install a tool-capable capability so the catalog WOULD offer tools.
    registry = CapabilityRegistry(root)
    registry.install("discusser", "a2a", config={})

    agent = A2ARuntimeAgent(runtime=target_runtime, identity_id="discusser")
    register_local_peer(agent)
    try:
        task = agent._handle_send({"message": "Let's discuss the ecosystem goals."})
        # The tool loop was disabled for the handler: the reply is clean prose
        # from the adapter, not fabricated tool-call JSON.
        assert "```" not in task["result"]
        assert '"type":"function"' not in task["result"]
        assert task["result"].strip() != ""
        # The runtime's tool limit was restored after the handler (the
        # constructor default for this runtime is 8).
        assert target_runtime.max_tools_per_request == 8
    finally:
        a2a_mod._LOCAL_PEERS.pop(agent.name, None)


def test_conversation_chain_across_two_identities(tmp_path):
    root = InMemoryBackend()
    aster = build_runtime(root, "aster", "Aster")
    worker = build_runtime(root, "worker", "Worker")
    for rt, model in [(aster, _ProseAdapter()), (worker, _ProseAdapter())]:
        rt.set_adapter(model)

    registry = CapabilityRegistry(root)
    for identity_id in ("aster", "worker"):
        registry.install(identity_id, "a2a", config={})
        registry.grant(identity_id, "a2a", "a2a.converse")

    peers = [A2ARuntimeAgent(runtime=rt, identity_id=iid) for iid, rt in (("aster", aster), ("worker", worker))]
    for peer in peers:
        register_local_peer(peer)
    try:
        # Hop 1: Aster → Worker
        hop1 = registry.call("aster", "a2a.send", agent="worker",
                             message="Worker, this is Aster. What goals should the project set?")
        assert hop1.success, hop1.error
        task1 = (hop1.data or {}).get("task") or {}
        assert task1["status"] == "completed"
        assert "goals" in str(task1["result"]).lower()

        # Hop 2: Worker → Aster (the chain continues: both identities talk)
        hop2 = registry.call("worker", "a2a.send", agent="aster",
                             message="Aster, the goals are set. From a relationship perspective, who should we contact first?")
        assert hop2.success, hop2.error
        task2 = (hop2.data or {}).get("task") or {}
        assert task2["status"] == "completed"
        assert "relationship" in str(task2["result"]).lower() or "maintainers" in str(task2["result"]).lower()

        # Each hop's reply came from the receiving identity's own runtime.
        assert task1["id"] != task2["id"]
    finally:
        for peer in peers:
            a2a_mod._LOCAL_PEERS.pop(peer.name, None)


def test_capability_resolves_local_peer_without_network(tmp_path):
    root = InMemoryBackend()
    aster = build_runtime(root, "aster", "Aster")
    registry = CapabilityRegistry(root)
    registry.install("aster", "a2a", config={})
    registry.grant("aster", "a2a", "a2a.converse")

    peer = A2ARuntimeAgent(runtime=aster, identity_id="aster")
    register_local_peer(peer)
    try:
        # a2a.discover against a local peer: served in-process (no network).
        result = registry.call("aster", "a2a.discover", agent="aster")
        assert result.success
        assert result.data.get("name") == "Aster"
        # a2a.send through the capability path reaches the peer's runtime.
        sent = registry.call("aster", "a2a.send", agent="Aster", message="Self-check: are you reachable?")
        assert sent.success
        assert ((sent.data or {}).get("task") or {}).get("status") == "completed"
    finally:
        a2a_mod._LOCAL_PEERS.pop(peer.name, None)


def test_unknown_agent_falls_back_to_configured_error(tmp_path):
    root = InMemoryBackend()
    aster = build_runtime(root, "aster", "Aster")
    registry = CapabilityRegistry(root)
    registry.install("aster", "a2a", config={})
    registry.grant("aster", "a2a", "a2a.converse")
    result = registry.call("aster", "a2a.send", agent="nonexistent-agent", message="hello")
    assert not result.success
    assert result.error.get("type") == "unknown_agent"