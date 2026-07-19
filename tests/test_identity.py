"""Tests for core.identity module."""

from core.identity import IdentitySpec, IdentityStore


class TestIdentitySpec:
    def test_defaults(self):
        ident = IdentitySpec(id="d1", name="Default")
        assert ident.role == ""
        assert ident.persona == ""
        assert ident.communication_style == ""
        assert ident.system_prompt == ""

    def test_to_dict_roundtrip(self):
        from core.identity import CoreValue
        cv1 = CoreValue(name="honesty", description="Tell the truth", strength=0.9)
        cv2 = CoreValue(name="kindness", description="Be kind", strength=0.8)
        ident = IdentitySpec(
            id="test-id",
            name="Test",
            role="assistant",
            persona="friendly",
            communication_style="casual",
            system_prompt="Be helpful",
            core_values=[cv1, cv2],
        )
        data = ident.to_dict()
        restored = IdentitySpec.from_dict(data)
        assert restored.id == ident.id
        assert restored.name == ident.name
        assert restored.role == ident.role
        assert restored.persona == ident.persona
        assert restored.communication_style == ident.communication_style
        assert restored.system_prompt == ident.system_prompt
        assert len(restored.core_values) == 2
        assert restored.core_values[0].name == "honesty"
        assert restored.core_values[1].name == "kindness"


class TestIdentityStore:
    def test_save_and_get(self):
        store = IdentityStore()
        ident = IdentitySpec(id="a1", name="Alpha")
        store.save(ident)
        assert store.get("a1") is ident
        assert store.get("missing") is None

    def test_delete(self):
        store = IdentityStore()
        ident = IdentitySpec(id="b1", name="Beta")
        store.save(ident)
        assert store.delete("b1") is True
        assert store.delete("b1") is False
        assert store.get("b1") is None

    def test_len(self):
        store = IdentityStore()
        assert len(store) == 0
        store.save(IdentitySpec(id="x1", name="X"))
        assert len(store) == 1
