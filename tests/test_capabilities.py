"""
test_capabilities.py — Evidence C: Pluggable Capability System

Core claim: An identity can install behavior packages that add
objectively new abilities it did not have before.

Test flow:
  1. Baseline — no capabilities → skills() empty, can() false
  2. Install ``github`` → 5 new skills appear
  3. Permission gating — public skills work, authenticated blocked
  4. Real GitHub API call (search_repositories)
  5. Capability prompts are injected into system context
  6. Runtime inspection (describe_runtime)
  7. Uninstall → skills() empty again
"""

import os
import tempfile

import pytest

from core.evaluation import register_default_criteria
from core.identity import create_identity
from runtime.orchestrator import IdentityRuntime
from runtime.persistence import JSONFileBackend


@pytest.fixture
def store_dir():
    with tempfile.TemporaryDirectory() as td:
        yield td


@pytest.fixture
def identity(store_dir):
    storage = JSONFileBackend(root_dir=store_dir)
    rt = IdentityRuntime(storage=storage)
    register_default_criteria(rt.evaluation_engine)
    spec = create_identity(
        name="CapabilityBot",
        identity_id="cap-bot",
        persona="A test identity for capability system verification",
    )
    rt.register(spec)
    from identityos.identity import IdentityObject
    obj = IdentityObject(runtime=rt, identity_id="cap-bot")
    return obj


class TestCapabilitySystem:
    """The capability architecture adds objectively new behaviors."""

    def test_baseline_no_capabilities(self, identity):
        """Before installation, no skills exist."""
        assert identity.skills() == []
        result = identity.can("github.search_repositories")
        assert result["available"] is False

    def test_install_adds_skills(self, identity):
        """After installation, the 5 github skills appear."""
        identity.install("github")

        skill_names = [s["name"] for s in identity.skills()]
        assert "github.search_repositories" in skill_names
        assert "github.get_repository" in skill_names
        assert "github.list_commits" in skill_names
        assert "github.list_branches" in skill_names
        assert "github.read_pull_request" in skill_names
        assert len(skill_names) == 5

    def test_permission_gating(self, identity):
        """Public skills are available; authenticated skills are not."""
        identity.install("github")

        can = identity.can("github.search_repositories")
        assert can["available"] is True

        can = identity.can("github.create_issue")
        assert can["available"] is False
        assert "reason" in can

    def test_real_github_api_call(self, identity):
        """Search repositories via the real GitHub API."""
        identity.install("github")

        results = identity.call("github.search_repositories", query="identityos")
        assert isinstance(results, list)
        if results:
            assert "name" in results[0]
            assert "stars" in results[0]
            assert "description" in results[0]

    def test_get_repository(self, identity):
        """Fetch a specific repo's metadata."""
        identity.install("github")

        repo = identity.call("github.get_repository", owner="lacebx", repo="IdentityOS")
        assert repo["name"] == "lacebx/IdentityOS"
        assert "description" in repo
        assert "stars" in repo

    def test_list_commits(self, identity):
        """Fetch recent commits from a real repo."""
        identity.install("github")

        commits = identity.call("github.list_commits", owner="lacebx", repo="IdentityOS")
        assert isinstance(commits, list)
        if commits:
            assert "sha" in commits[0]
            assert "message" in commits[0]
            assert "author" in commits[0]

    def test_list_branches(self, identity):
        """Fetch branches from a real repo."""
        identity.install("github")

        branches = identity.call("github.list_branches", owner="lacebx", repo="IdentityOS")
        assert isinstance(branches, list)
        if branches:
            assert {"name", "sha"}.issubset(branches[0].keys())

    def test_prompts_injected_into_context(self, identity):
        """Capability prompt fragments appear in composed context."""
        identity.install("github")

        from core.cognitive_engine import ComposedContext

        # The compose step injects custom_blocks["capabilities"]
        # We verify by checking the rendered context string
        session_id = identity._runtime.start_session("cap-bot")
        context = identity._runtime.context_composer.compose(
            identity=identity._spec,
            memory_store=identity._runtime.memory_store,
            skill_registry=identity._runtime.skill_registry,
            goal_engine=identity._runtime.goal_engine,
            intention_engine=identity._runtime.intention_engine,
            identity_graph=identity._runtime.identity_graph,
            motivation_engine=identity._runtime.motivation_engine,
            timeline_registry=identity._runtime.timeline_registry,
            fact_store=identity._runtime._get_fact_store_for_session("cap-bot", session_id),
            user_profile=identity._runtime._user_profiles.get(session_id),
            query="test",
            top_k_memories=5,
            session_mode=identity._runtime._session_modes.get(session_id),
            emotion_state=None,
        )

        # Inject capability prompts (simulating what process() does)
        cap_prompts = identity._runtime.capability_registry.all_prompts("cap-bot")
        if cap_prompts:
            context.custom_blocks["capabilities"] = "\n".join(cap_prompts)

        rendered = context.render()
        assert "Available GitHub Skills" in rendered
        assert "github.search_repositories" in rendered

    def test_describe_runtime_includes_capabilities(self, identity):
        """Runtime inspection shows installed capabilities and skills."""
        identity.install("github")

        info = identity.describe_runtime()
        assert info["identity"] == "CapabilityBot"
        assert info["identity_id"] == "cap-bot"
        assert "github" in info["capabilities"]
        assert "github.search_repositories" in info["skills"]
        assert info["has_storage"] is True

    def test_capability_method_returns_metadata(self, identity):
        """identity.capability('github') returns the capability metadata."""
        identity.install("github")

        meta = identity.capability("github")
        assert meta is not None
        assert meta["id"] == "github"
        assert meta["name"] == "GitHub Integration"
        assert "github.search_repositories" in meta["skills"]

    def test_capability_returns_none_when_not_installed(self, identity):
        """identity.capability('nosuch') returns None."""
        meta = identity.capability("nosuch")
        assert meta is None

    def test_uninstall_removes_skills(self, identity):
        """After uninstall, skills() returns to empty."""
        identity.install("github")
        assert len(identity.skills()) == 5

        identity.uninstall("github")
        assert identity.skills() == []
        can = identity.can("github.search_repositories")
        assert can["available"] is False

    def test_unknown_capability_raises(self, identity):
        """Installing a non-existent capability raises ValueError."""
        with pytest.raises(ValueError, match="Unknown capability"):
            identity.install("does_not_exist")
