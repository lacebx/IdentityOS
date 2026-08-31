"""Tests for core.memory module."""

from core.memory import (
    MemoryConfidence,
    MemoryFragment,
    MemoryStore,
    MemoryType,
    PersistentMemoryStore,
    make_memory,
)


class TestMemoryFragment:
    def test_create(self):
        frag = MemoryFragment(
            identity_id="test-id",
            content="Hello, world!",
            memory_type=MemoryType.EPISODIC,
        )
        assert frag.id
        assert frag.identity_id == "test-id"
        assert frag.content == "Hello, world!"
        assert frag.memory_type == MemoryType.EPISODIC
        assert frag.confidence == MemoryConfidence.MEDIUM

    def test_touch(self):
        frag = MemoryFragment()
        count_before = frag.access_count
        frag.touch()
        assert frag.access_count == count_before + 1

    def test_to_dict_roundtrip(self):
        frag = MemoryFragment(
            identity_id="r1",
            content="roundtrip test",
            memory_type=MemoryType.SEMANTIC,
            confidence=MemoryConfidence.HIGH,
            tags=["test"],
        )
        data = frag.to_dict()
        restored = MemoryFragment.from_dict(data)
        assert restored.id == frag.id
        assert restored.content == frag.content
        assert restored.memory_type == MemoryType.SEMANTIC
        assert restored.confidence == MemoryConfidence.HIGH
        assert restored.tags == ["test"]

    def test_user_id_roundtrip(self):
        frag = MemoryFragment(identity_id="agent", user_id="alice", content="private")
        restored = MemoryFragment.from_dict(frag.to_dict())
        assert restored.user_id == "alice"


class TestMemoryStore:
    def test_add_and_get(self):
        store = MemoryStore()
        frag = MemoryFragment(identity_id="id1", content="test memory")
        store.add(frag)
        assert store.get(frag.id) is frag

    def test_remove(self):
        store = MemoryStore()
        frag = MemoryFragment()
        store.add(frag)
        assert store.remove(frag.id) is True
        assert store.remove("nonexistent") is False

    def test_by_identity(self):
        store = MemoryStore()
        a = MemoryFragment(identity_id="id-a", content="a")
        b = MemoryFragment(identity_id="id-b", content="b")
        store.add(a)
        store.add(b)
        assert len(store.by_identity("id-a")) == 1
        assert len(store.by_identity("id-b")) == 1
        assert len(store.by_identity("id-c")) == 0

    def test_by_user_includes_shared_but_not_other_users(self):
        store = MemoryStore()
        store.add(MemoryFragment(identity_id="agent", user_id="alice", content="alice"))
        store.add(MemoryFragment(identity_id="agent", user_id="bob", content="bob"))
        store.add(MemoryFragment(identity_id="agent", user_id="", content="shared"))

        visible = {fragment.content for fragment in store.by_user("agent", "alice")}
        assert visible == {"alice", "shared"}

    def test_clear_user_retains_other_users_and_shared_memory(self):
        store = MemoryStore()
        store.add(MemoryFragment(identity_id="agent", user_id="alice", content="alice"))
        store.add(MemoryFragment(identity_id="agent", user_id="bob", content="bob"))
        store.add(MemoryFragment(identity_id="agent", user_id="", content="shared"))

        assert store.clear_user("agent", "alice") == 1
        assert {fragment.content for fragment in store.by_identity("agent")} == {
            "bob",
            "shared",
        }

    def test_recent(self):
        store = MemoryStore()
        for i in range(5):
            store.add(MemoryFragment(identity_id="id1", content=f"mem {i}"))
        recent = store.recent(identity_id="id1", n=3)
        assert len(recent) == 3

    def test_search_keywords(self):
        store = MemoryStore()
        store.add(MemoryFragment(identity_id="id1", content="python programming"))
        store.add(MemoryFragment(identity_id="id1", content="cooking recipes"))
        results = store.search_keywords("python", identity_id="id1")
        assert len(results) == 1
        assert "python" in results[0].content

    def test_len(self):
        store = MemoryStore()
        assert len(store) == 0
        store.add(MemoryFragment())
        assert len(store) == 1


class TestMakeMemory:
    def test_factory(self):
        frag = make_memory("test", identity_id="id1", tags=["hello"])
        assert frag.content == "test"
        assert frag.identity_id == "id1"
        assert frag.tags == ["hello"]
        assert frag.memory_type == MemoryType.EPISODIC


def test_persistent_store_filters_users_after_restart(tmp_path):
    db_path = str(tmp_path / "memory.db")
    store = PersistentMemoryStore(db_path)
    store.add(MemoryFragment(identity_id="agent", user_id="alice", content="alice"))
    store.add(MemoryFragment(identity_id="agent", user_id="bob", content="bob"))
    store.add(MemoryFragment(identity_id="agent", user_id="", content="shared"))

    restarted = PersistentMemoryStore(db_path)
    visible = {fragment.content for fragment in restarted.by_user("agent", "alice")}
    assert visible == {"alice", "shared"}
    assert restarted.clear_user("agent", "alice") == 1
    assert {fragment.content for fragment in restarted.by_identity("agent")} == {
        "bob",
        "shared",
    }
