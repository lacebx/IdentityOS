"""
Test export/import round-trip.
"""

from .conftest import make_agent


class TestExportImport:
    def test_export_returns_dict(self):
        agent = make_agent("export-1")
        exported = agent.export()
        assert "identity" in exported
        assert "memories" in exported
        assert "goals" in exported
        assert "intentions" in exported

    def test_export_contains_identity(self):
        agent = make_agent("export-2")
        exported = agent.export()
        assert exported["identity"]["name"] == "export-2"

    def test_export_to_file(self):
        import tempfile, os
        agent = make_agent("export-3")
        agent.intention("Persist me", hours=24)
        agent.goal("Persist goal", priority="medium")
        path = os.path.join(tempfile.gettempdir(), "agent-export-test.json")
        agent.export(path)
        assert os.path.exists(path)
        os.remove(path)

    def test_import_restores_data(self):
        agent = make_agent("import-1")
        agent.goal("Original goal", priority="high")
        agent.intention("Original intention", hours=24)
        exported = agent.export()

        agent2 = make_agent("import-2")
        count = agent2.import_(exported)
        assert count > 0

        goals = agent2.goals("all")
        assert any(g["title"] == "Original goal" for g in goals)

    def test_from_file_roundtrip(self):
        import tempfile, os
        from identityos import Identity

        agent = make_agent("roundtrip")
        agent.intention("Survive export", hours=48)
        path = os.path.join(tempfile.gettempdir(), "roundtrip-test.json")
        agent.export(path)

        restored = Identity.from_file(path)
        assert restored.name == "roundtrip"
        os.remove(path)

    def test_export_with_metadata(self):
        agent = make_agent("metadata-test")
        agent.infer_intentions("I'll finish the docs.", author_id="alice")
        exported = agent.export()
        intentions = exported.get("intentions", [])
        metadata_found = any(
            i.get("metadata", {}).get("author_id") == "alice"
            for i in intentions
        )
        assert metadata_found
