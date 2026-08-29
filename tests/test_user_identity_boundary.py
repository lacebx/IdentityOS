"""User state must never be mistaken for identity or another user's state."""

from __future__ import annotations

from core.identity import create_identity
from core.user_profile import UserProfile
from runtime.orchestrator import IdentityRuntime, InteractionRequest
from runtime.persistence import JSONFileBackend


class _Adapter:
    model = "boundary-test"

    def generate(self, **kwargs):
        return "fallback response"


def _runtime(tmp_path) -> IdentityRuntime:
    runtime = IdentityRuntime(
        storage=JSONFileBackend(root_dir=str(tmp_path / "store")),
        adapter=_Adapter(),
    )
    runtime.register(
        create_identity(
            name="Boundary Bot",
            identity_id="boundary-bot",
            persona="Keeps identity and user state separate",
        )
    )
    return runtime


def _process(runtime: IdentityRuntime, user_id: str, session_id: str, text: str):
    return runtime.process(
        InteractionRequest(
            identity_id="boundary-bot",
            user_id=user_id,
            session_id=session_id,
            user_input=text,
        )
    )


def test_two_users_have_isolated_profiles_memories_and_recall(tmp_path):
    runtime = _runtime(tmp_path)

    _process(runtime, "alice", "alice-session", "Remember: The user's name is Alice.")
    _process(runtime, "bob", "bob-session", "Remember: The user's name is Bob.")

    assert runtime._get_user_profile("boundary-bot", "alice").get_value("name") == "Alice"
    assert runtime._get_user_profile("boundary-bot", "bob").get_value("name") == "Bob"

    alice_memory = " ".join(
        memory.content for memory in runtime.memory_store.by_user("boundary-bot", "alice")
    )
    bob_memory = " ".join(
        memory.content for memory in runtime.memory_store.by_user("boundary-bot", "bob")
    )
    assert "Alice" in alice_memory and "Bob" not in alice_memory
    assert "Bob" in bob_memory and "Alice" not in bob_memory

    alice_recall = _process(
        runtime,
        "alice",
        "alice-session",
        "What is the user's name?",
    )
    bob_recall = _process(
        runtime,
        "bob",
        "bob-session",
        "What is the user's name?",
    )
    assert "Alice" in alice_recall.output and "Bob" not in alice_recall.output
    assert "Bob" in bob_recall.output and "Alice" not in bob_recall.output
    assert "Bob" not in alice_recall.context_used.render()
    assert "Alice" not in bob_recall.context_used.render()


def test_user_profiles_and_memory_remain_isolated_after_restart(tmp_path):
    runtime = _runtime(tmp_path)
    _process(runtime, "alice", "alice-session", "Remember: The user's name is Alice.")
    _process(runtime, "bob", "bob-session", "Remember: The user's name is Bob.")

    restarted = IdentityRuntime(
        storage=JSONFileBackend(root_dir=str(tmp_path / "store")),
        adapter=None,
    )
    assert restarted.load("boundary-bot") is not None

    assert restarted._get_user_profile("boundary-bot", "alice").get_value("name") == "Alice"
    assert restarted._get_user_profile("boundary-bot", "bob").get_value("name") == "Bob"
    alice_memory = restarted.memory_store.by_user("boundary-bot", "alice")
    bob_memory = restarted.memory_store.by_user("boundary-bot", "bob")
    assert alice_memory and all(memory.user_id in ("", "alice") for memory in alice_memory)
    assert bob_memory and all(memory.user_id in ("", "bob") for memory in bob_memory)
    assert not any(memory.user_id == "bob" for memory in alice_memory)
    assert not any(memory.user_id == "alice" for memory in bob_memory)


def test_legacy_profile_and_memory_migrate_only_to_legacy_default_user(tmp_path):
    storage = JSONFileBackend(root_dir=str(tmp_path / "store"))
    runtime = IdentityRuntime(storage=storage, adapter=None)
    runtime.register(
        create_identity(name="Legacy Bot", identity_id="legacy-bot", persona="test")
    )

    legacy_profile = UserProfile(user_id="legacy-bot")
    legacy_profile.add_or_update("name", "Legacy User", source="old-format")
    storage.save("legacy-bot", "_user_profile", legacy_profile.to_dict())
    storage.save_memory(
        "legacy-bot",
        {
            "identity_id": "legacy-bot",
            "content": "legacy private memory",
            "memory_type": "episodic",
            "source": "old-format",
        },
    )

    restarted = IdentityRuntime(storage=storage, adapter=None)
    assert restarted.load("legacy-bot") is not None
    default_profile = restarted._get_user_profile("legacy-bot")
    explicit_profile = restarted._get_user_profile("legacy-bot", "someone-else")

    assert default_profile.get_value("name") == "Legacy User"
    assert explicit_profile.get_value("name") is None
    assert restarted.memory_store.by_user("legacy-bot", "legacy-bot")
    assert restarted.memory_store.by_user("legacy-bot", "someone-else") == []
    migrated_namespace = restarted._user_profile_namespace("legacy-bot")
    assert storage.load("legacy-bot", migrated_namespace)["user_id"] == "legacy-bot"


def test_session_cannot_be_rebound_to_another_user(tmp_path):
    runtime = _runtime(tmp_path)
    first = _process(runtime, "alice", "shared-session", "Hello")
    second = _process(runtime, "bob", "shared-session", "Hello")

    assert first.policy_passed is True
    assert second.policy_passed is False
    assert "different user" in second.output.lower()
