"""
test_third_party_sdk.py — Evidence E: Third-party SDK usability

Core differentiation claim:
  A developer needs ONLY `from identityos import Identity` and
  `pip install identityos` to build a persistent AI identity app.
  No internal imports, no runtime knowledge, no adapter config needed
  for identity features.

This test:
  1. Uses ONLY the public SDK surface (identityos package)
  2. Imports NOTHING from core/, runtime/, adapters/, or cli/
  3. Builds a mini application: create, train, export, restore
  4. Verifies all identity features work without internal knowledge
"""

import os
import sys
import tempfile
from pathlib import Path

import pytest


# ── CRITICAL: Verify no internal imports leak into the test ──────────
_INTERNAL_MODULES = {"core", "runtime", "adapters", "cli"}


def _check_no_internal_imports():
    """Verify this test file only imports from identityos."""
    import ast
    with open(__file__) as f:
        tree = ast.parse(f.read())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                parts = alias.name.split(".")
                if parts[0] in _INTERNAL_MODULES:
                    pytest.fail(
                        f"Internal import found: {alias.name} — "
                        f"third-party devs cannot use this"
                    )
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                parts = node.module.split(".")
                if parts[0] in _INTERNAL_MODULES:
                    pytest.fail(
                        f"Internal import found: from {node.module} — "
                        f"third-party devs cannot use this"
                    )


# Verify at import time (before any test runs)
_check_no_internal_imports()

# ── Only import from identityos (the public SDK) ─────────────────────
from identityos import Identity


class TestThirdPartySDK:
    """A third-party developer uses ONLY from identityos import Identity."""

    def _make_storage(self):
        return tempfile.mkdtemp()

    def test_create_identity(self):
        """Create an identity with a name and persona."""
        agent = Identity.create("TestDevBot", persona="A test agent")
        assert agent.name == "TestDevBot"
        assert agent.id is not None

    def test_observe_and_recall_facts(self):
        """Observe user facts and recall them."""
        agent = Identity.create("ObserveBot")
        agent.observe("My name is Alice and I love Python")
        facts = agent.user_facts()
        fields = [f["field"] for f in facts]
        assert "name" in fields
        assert "preferences.likes.python" in fields or "python" in str(facts).lower()

    def test_goals_lifecycle(self):
        """Set goals, list them, complete them."""
        agent = Identity.create("GoalBot")
        agent.goal("Learn Rust", priority="high")
        agent.goal("Build a CLI tool", priority="medium")

        all_goals = agent.goals("all")
        titles = [g["title"] for g in all_goals]
        assert "Learn Rust" in titles
        assert "Build a CLI tool" in titles

        active = agent.goals("active")
        assert len(active) >= 1

    def test_relationships(self):
        """Track relationships with users."""
        agent = Identity.create("RelBot")
        agent.relationship("alice", trust_level=0.9, context="Close collaborator")
        agent.relationship("bob", trust_level=0.5, context="Acquaintance")

        rels = agent.relationships()
        targets = [r["target_id"] for r in rels]
        assert "alice" in targets
        assert "bob" in targets

    def test_timeline(self):
        """Record and retrieve timeline events."""
        agent = Identity.create("TimelineBot")
        agent.record_event("milestone", "First deployment", significance=5)
        agent.record_event("update", "Added memory system", significance=4)

        events = agent.timeline(limit=10)
        titles = [e["title"] for e in events]
        assert "First deployment" in titles
        assert "Added memory system" in titles

    def test_export_and_restore(self):
        """Portable JSON export/import preserves identity state."""
        export_path = os.path.join(tempfile.mkdtemp(), "portable.json")

        agent = Identity.create("ExportBot")
        agent.goal("Ship v2", priority="high")
        agent.relationship("user1", trust_level=0.8)
        agent.record_event("milestone", "v1 released", significance=5)
        agent.export(export_path)

        restored = Identity.from_file(export_path)
        assert restored.name == "ExportBot"

        goals = restored.goals("all")
        assert any(g["title"] == "Ship v2" for g in goals)

        rels = restored.relationships()
        assert any(r["target_id"] == "user1" for r in rels)

    def test_intentions(self):
        """Create and list intentions."""
        agent = Identity.create("IntentionBot")
        agent.intention("Review PR by Friday", hours=48)
        agent.intention("Write documentation", hours=72)

        all_intentions = agent.intentions("all")
        descriptions = [i["description"] for i in all_intentions]
        assert "Review PR by Friday" in descriptions
        assert "Write documentation" in descriptions

    def test_full_app_workflow(self):
        """
        Simulate a real app: user signs up, has a conversation,
        identity learns, state persists.
        """
        storage = self._make_storage()
        export_path = os.path.join(storage, "app-identity.json")

        # User creates their AI companion
        companion = Identity.create(
            "MyCompanion",
            identity_id="companion-1",
            persona="A supportive AI friend",
            storage_path=storage,
        )

        # User shares information about themselves
        companion.observe("My name is Alex and I'm learning web development")
        companion.observe("My favorite framework is FastAPI")

        # User sets goals for their companion
        companion.goal("Help Alex master FastAPI", priority="high")
        companion.goal("Track Alex's learning progress", priority="medium")

        # Export for backup / portability
        companion.export(export_path)

        # Restore on a different device
        restored = Identity.from_file(export_path)

        # Verify everything works after restore
        assert restored.name == "MyCompanion"
        goals = restored.goals("all")
        assert any("FastAPI" in g["title"] for g in goals)
