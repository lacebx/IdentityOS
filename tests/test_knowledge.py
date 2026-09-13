"""Tests for core.knowledge module."""

from core.knowledge import (
    KnowledgeEntry,
    KnowledgePack,
    KnowledgeRegistry,
    KnowledgeFormat,
    KnowledgeTier,
)


class TestKnowledgeEntry:
    def test_creation_defaults(self):
        entry = KnowledgeEntry(title="Test", content="Test content")
        assert entry.id
        assert entry.title == "Test"
        assert entry.content == "Test content"
        assert entry.format == KnowledgeFormat.TEXT
        assert entry.confidence == 1.0
        assert entry.tags == []

    def test_creation_with_all_fields(self):
        entry = KnowledgeEntry(
            title="Python Guide",
            content="Python is a programming language...",
            format=KnowledgeFormat.MARKDOWN,
            source_url="https://python.org",
            tags=["python", "guide"],
            confidence=0.9,
        )
        assert entry.format == KnowledgeFormat.MARKDOWN
        assert entry.source_url == "https://python.org"
        assert entry.tags == ["python", "guide"]
        assert entry.confidence == 0.9

    def test_to_dict(self):
        entry = KnowledgeEntry(title="Test", content="Content")
        data = entry.to_dict()
        assert data["title"] == "Test"
        assert data["content"] == "Content"
        assert data["format"] == "text"
        assert data["confidence"] == 1.0


class TestKnowledgePack:
    def test_creation_defaults(self):
        pack = KnowledgePack(name="Test Pack")
        assert pack.id
        assert pack.name == "Test Pack"
        assert pack.version == "1.0.0"
        assert pack.tier == KnowledgeTier.DOMAIN
        assert pack.entries == []
        assert pack.depends_on == []

    def test_creation_with_all_fields(self):
        pack = KnowledgePack(
            name="Python Best Practices",
            description="Best practices for Python development",
            version="2.0.0",
            tier=KnowledgeTier.CORE,
            author="IdentityOS Team",
            tags=["python", "best-practices"],
            compatible_classes=["agent", "assistant"],
            estimated_tokens=1000,
        )
        assert pack.name == "Python Best Practices"
        assert pack.tier == KnowledgeTier.CORE
        assert pack.author == "IdentityOS Team"

    def test_add_entry(self):
        pack = KnowledgePack(name="Test")
        entry = pack.add_entry("Python uses indentation", title="Indentation")
        assert len(pack.entries) == 1
        assert entry.title == "Indentation"
        assert entry.content == "Python uses indentation"

    def test_search(self):
        pack = KnowledgePack(name="Test")
        pack.add_entry("Python is great for scripting", title="Scripting")
        pack.add_entry("Java is compiled", title="Java")
        results = pack.search("python")
        assert len(results) == 1
        assert "Python" in results[0].content

    def test_to_context_string(self):
        pack = KnowledgePack(name="Test Pack", description="A test pack")
        pack.add_entry("Entry 1 content", title="Entry 1")
        pack.add_entry("Entry 2 content", title="Entry 2")
        context = pack.to_context_string()
        assert "Test Pack" in context
        assert "A test pack" in context
        assert "Entry 1 content" in context
        assert "Entry 2 content" in context

    def test_to_context_string_with_limit(self):
        pack = KnowledgePack(name="Test")
        for i in range(5):
            pack.add_entry(f"Content {i}", title=f"Entry {i}")
        context = pack.to_context_string(max_entries=2)
        assert "Entry 0" in context
        assert "Entry 1" in context
        assert "Entry 2" not in context

    def test_to_dict(self):
        pack = KnowledgePack(name="Test", description="Desc")
        pack.add_entry("Content", title="Entry")
        data = pack.to_dict()
        assert data["name"] == "Test"
        assert data["description"] == "Desc"
        assert len(data["entries"]) == 1

    def test_from_dict(self):
        data = {
            "id": "pack-1",
            "name": "Test",
            "description": "Desc",
            "version": "1.0.0",
            "tier": "domain",
            "author": "Author",
            "entries": [
                {"id": "e1", "title": "Entry", "content": "Content", "format": "text", "source_url": "", "tags": [], "confidence": 1.0, "created_at": "2024-01-01T00:00:00", "extra": {}}
            ],
            "depends_on": [],
            "compatible_classes": [],
            "tags": [],
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:00:00",
            "estimated_tokens": 0,
            "extra": {},
        }
        pack = KnowledgePack.from_dict(data)
        assert pack.id == "pack-1"
        assert pack.name == "Test"
        assert len(pack.entries) == 1
        assert pack.entries[0].title == "Entry"


class TestKnowledgeRegistry:
    def test_register_and_get(self):
        registry = KnowledgeRegistry()
        pack = KnowledgePack(name="Test Pack")
        registry.register(pack)
        retrieved = registry.get(pack.id)
        assert retrieved is pack

    def test_get_by_name(self):
        registry = KnowledgeRegistry()
        pack1 = KnowledgePack(name="Test Pack")
        pack2 = KnowledgePack(name="test pack")  # case insensitive
        registry.register(pack1)
        registry.register(pack2)
        found = registry.get_by_name("Test Pack")
        assert len(found) == 2

    def test_list_packs(self):
        registry = KnowledgeRegistry()
        registry.register(KnowledgePack(name="Pack 1"))
        registry.register(KnowledgePack(name="Pack 2"))
        packs = registry.list_packs()
        assert len(packs) == 2

    def test_load_for_identity(self):
        registry = KnowledgeRegistry()
        core_pack = KnowledgePack(name="Core Pack", tier=KnowledgeTier.CORE)
        domain_pack = KnowledgePack(name="Domain Pack", tier=KnowledgeTier.DOMAIN, depends_on=[core_pack.id])
        context_pack = KnowledgePack(name="Context Pack", tier=KnowledgeTier.CONTEXT)
        ephemeral_pack = KnowledgePack(name="Ephemeral Pack", tier=KnowledgeTier.TEMP)
        registry.register(core_pack)
        registry.register(domain_pack)
        registry.register(context_pack)
        registry.register(ephemeral_pack)
        loaded = registry.load_for_identity([domain_pack.id, ephemeral_pack.id])
        # Should include transitive dependencies and sort by tier
        assert len(loaded) >= 2
        # The first should be CORE (from dependency of domain_pack)
        assert loaded[0].tier == KnowledgeTier.CORE  # CORE first

    def test_load_for_identity_with_dependencies(self):
        registry = KnowledgeRegistry()
        core = KnowledgePack(name="Core", tier=KnowledgeTier.CORE)
        domain = KnowledgePack(name="Domain", tier=KnowledgeTier.DOMAIN, depends_on=[core.id])
        registry.register(core)
        registry.register(domain)
        loaded = registry.load_for_identity([domain.id])
        assert len(loaded) == 2
        assert loaded[0].tier == KnowledgeTier.CORE
        assert loaded[1].tier == KnowledgeTier.DOMAIN

    def test_len(self):
        registry = KnowledgeRegistry()
        assert len(registry) == 0
        registry.register(KnowledgePack(name="Pack 1"))
        assert len(registry) == 1
