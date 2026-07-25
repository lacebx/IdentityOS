"""
test_capabilities.py — Evidence C: Pluggable Capability System

Core claim: An identity can install behavior packages that feel like
installed software — not RPC calls — and add objectively new abilities.

Test flow:
  1. Baseline — no capabilities → skills() empty, can() false
  2. Install ``github`` → 7 semantic skills appear
  3. Permission gating — public skills work, authenticated blocked
  4. Attribute access: ``identity.github.search_repositories(...)``
  5. Proxy access: ``identity.use("github").review_pull_request(...)``
  6. Capability access: ``identity.capability("github").find_beginner_issue(...)``
  7. Permissions system: grant, list
  8. Real GitHub API calls for all 7 skills
  9. Uninstall → cleanup
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
        can = identity.can("github.search_repositories")
        assert can["available"] is False

    def test_install_adds_semantic_skills(self, identity):
        """After installation, all 7 semantic skills appear."""
        identity.install("github")

        skill_names = [s["name"] for s in identity.skills()]
        assert "github.search_repositories" in skill_names
        assert "github.get_repository" in skill_names
        assert "github.review_pull_request" in skill_names
        assert "github.find_beginner_issue" in skill_names
        assert "github.summarize_release" in skill_names
        assert "github.list_commits" in skill_names
        assert "github.list_branches" in skill_names
        assert len(skill_names) == 7

    def test_permission_gating(self, identity):
        """Public skills are available; authenticated ones are not."""
        identity.install("github")

        can = identity.can("github.search_repositories")
        assert can["available"] is True

        can = identity.can("github.create_issue")
        assert can["available"] is False
        assert "reason" in can

    # ── Invocation patterns ────────────────────────────────────────────

    def test_attribute_access_identity_github(self, identity):
        """identity.github.search_repositories(...) works."""
        identity.install("github")

        results = identity.github.search_repositories(query="identityos")
        assert isinstance(results, list)

    def test_use_proxy_access(self, identity):
        """identity.use('github').get_repository(...) works."""
        identity.install("github")

        repo = identity.use("github").get_repository(owner="lacebx", repo="IdentityOS")
        assert repo["name"] == "lacebx/IdentityOS"

    def test_capability_proxy_access(self, identity):
        """identity.capability('github').list_commits(...) works."""
        identity.install("github")

        commits = identity.capability("github").list_commits(owner="lacebx", repo="IdentityOS")
        assert isinstance(commits, list)
        if commits:
            assert "sha" in commits[0]

    # ── Real GitHub API calls ──────────────────────────────────────────

    def test_search_repositories(self, identity):
        """github.search_repositories via proxy."""
        identity.install("github")
        results = identity.github.search_repositories(query="identityos")
        assert isinstance(results, list)
        if results:
            assert "name" in results[0]
            assert "stars" in results[0]

    def test_get_repository(self, identity):
        """github.get_repository via proxy."""
        identity.install("github")
        repo = identity.capability("github").get_repository(owner="lacebx", repo="IdentityOS")
        assert repo["name"] == "lacebx/IdentityOS"
        assert "stars" in repo

    def test_review_pull_request(self, identity):
        """github.review_pull_request fetches PR details with file stats."""
        identity.install("github")
        pr = identity.use("github").review_pull_request(
            owner="lacebx", repo="IdentityOS", number=1
        )
        assert pr["number"] == 1 or pr["number"] > 0
        assert "title" in pr
        assert "files_changed" in pr
        assert "total_additions" in pr
        assert "total_deletions" in pr

    def test_find_beginner_issue(self, identity):
        """github.find_beginner_issue finds 'good first issue' issues."""
        identity.install("github")
        issues = identity.github.find_beginner_issue(owner="lacebx", repo="IdentityOS")
        assert isinstance(issues, list)
        if issues:
            assert "number" in issues[0]
            assert "title" in issues[0]

    def test_summarize_release(self, identity):
        """github.summarize_release returns recent changes."""
        identity.install("github")
        summary = identity.capability("github").summarize_release(
            owner="lacebx", repo="IdentityOS"
        )
        assert "tag" in summary
        assert "total" in summary
        assert "commits_since_last_tag" in summary

    def test_list_commits(self, identity):
        """github.list_commits via proxy."""
        identity.install("github")
        commits = identity.use("github").list_commits(owner="lacebx", repo="IdentityOS")
        assert isinstance(commits, list)
        if commits:
            assert "sha" in commits[0]
            assert "message" in commits[0]
            assert "author" in commits[0]

    def test_list_branches(self, identity):
        """github.list_branches via proxy."""
        identity.install("github")
        branches = identity.github.list_branches(owner="lacebx", repo="IdentityOS")
        assert isinstance(branches, list)
        if branches:
            assert {"name", "sha"}.issubset(branches[0].keys())

    # ── Round-trip: install → call → uninstall ─────────────────────────

    def test_install_call_uninstall_roundtrip(self, identity):
        """Full round-trip: install, call via proxy, uninstall, confirm empty."""
        identity.install("github")
        repos = identity.github.search_repositories(query="identityos")
        assert isinstance(repos, list)
        assert len(identity.skills()) == 7

        identity.uninstall("github")
        assert identity.skills() == []
        with pytest.raises((AttributeError, ValueError)):
            _ = identity.github

    # ── Permissions system ─────────────────────────────────────────────

    def test_permissions_empty_by_default(self, identity):
        """No permissions granted by default."""
        assert identity.permissions() == []

    def test_grant_permission(self, identity):
        """Granting a permission persists it."""
        identity.grant("github", "repo:read")
        perms = identity.permissions()
        assert len(perms) == 1
        assert perms[0]["capability"] == "github"
        assert perms[0]["permission"] == "repo:read"
        assert "granted_at" in perms[0]

    def test_grant_multiple_permissions(self, identity):
        """Multiple grants accumulate."""
        identity.grant("github", "repo:read")
        identity.grant("github", "issues:write")
        identity.grant("calendar", "events:read")
        assert len(identity.permissions()) == 3

    # ── Capability metadata ────────────────────────────────────────────

    def test_capability_proxy_exposes_metadata(self, identity):
        """capability() returns a proxy with metadata properties."""
        identity.install("github")
        proxy = identity.capability("github")
        assert proxy.id == "github"
        assert proxy.name == "GitHub Integration"
        meta = proxy.metadata()
        assert meta["id"] == "github"
        assert "skills" in meta

    def test_capability_not_installed_raises(self, identity):
        """capability() raises ValueError for unknown caps."""
        with pytest.raises(ValueError, match="not installed"):
            identity.capability("does_not_exist")

    # ── Error handling ─────────────────────────────────────────────────

    def test_unknown_capability_raises(self, identity):
        """Installing a non-existent capability raises ValueError."""
        with pytest.raises(ValueError, match="Unknown capability"):
            identity.install("does_not_exist")

    def test_unknown_skill_raises(self, identity):
        """Calling a non-existent skill on a proxy raises AttributeError."""
        identity.install("github")
        with pytest.raises(AttributeError):
            identity.github.nonexistent_skill()
