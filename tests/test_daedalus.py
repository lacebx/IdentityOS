from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

from scripts.daedalus_review import (
    parse_diff_files,
    analyze_separation,
    analyze_test_coverage,
    analyze_diff_quality,
    analyze_architectural_impact,
    analyze_documentation_impact,
    analyze_technical_debt_introduced,
    analyze_goals_alignment,
    assess_readiness,
    ARCHITECTURE_LAYERS,
    CATEGORY_MAP,
)


# ── Diff Parsing ─────────────────────────────────────────────────────


class TestDiffParsing:
    def test_empty_diff(self):
        files = parse_diff_files("")
        assert files == []

    def test_single_file_diff(self):
        diff = """diff --git a/file.py b/file.py
--- a/file.py
+++ b/file.py
@@ -1 +1 @@
+new line
-old line"""
        files = parse_diff_files(diff)
        assert len(files) == 1
        assert files[0]["path"] == "file.py"
        assert files[0]["additions"] == 1
        assert files[0]["deletions"] == 1

    def test_multi_file_diff(self):
        diff = """diff --git a/a.py b/a.py
--- a/a.py
+++ b/a.py
+line1
diff --git a/b.py b/b.py
--- a/b.py
+++ b/b.py
+line2
+line3"""
        files = parse_diff_files(diff)
        assert len(files) == 2
        assert files[0]["additions"] == 1
        assert files[1]["additions"] == 2

    def test_no_changes_diff(self):
        diff = """diff --git a/x.py b/x.py
--- a/x.py
+++ b/x.py"""
        files = parse_diff_files(diff)
        assert len(files) == 1
        assert files[0]["additions"] == 0


# ── Layer Separation ─────────────────────────────────────────────────


class TestLayerSeparation:
    def test_no_violations(self):
        files = [{"path": "identitybench/atlas/health.py", "lines": ["+from typing import Any"]}]
        result = analyze_separation(files, "")
        assert any("maintained" in r for r in result)

    def test_core_imports_atlas_false_positive_fixed(self):
        files = [{"path": "core/capabilities/__init__.py", "lines": ["+from . import daedalus"]}]
        result = analyze_separation(files, "+from identitybench.atlas.health import compute_identity_health")
        violations = [r for r in result if "Core imports from Atlas" in r]
        assert len(violations) == 0

    def test_core_actually_imports_atlas(self):
        files = [{"path": "core/foo.py", "lines": ["+from identitybench.atlas.health import compute"]}]
        result = analyze_separation(files, "+from identitybench.atlas.health import compute")
        violations = [r for r in result if "Core imports from Atlas" in r]
        assert len(violations) > 0

    def test_prometheus_imports_atlas(self):
        files = [{"path": "core/prometheus/stages/learner.py", "lines": ["+from identitybench.atlas.health import compute"]}]
        result = analyze_separation(files, "+from identitybench.atlas.health import compute")
        violations = [r for r in result if "Prometheus should not depend on Atlas" in r]
        assert len(violations) > 0

    def test_atlas_imports_runtime(self):
        files = [{"path": "identitybench/atlas/prediction.py", "lines": ["+from runtime.orchestrator import IdentityRuntime"]}]
        result = analyze_separation(files, "+from runtime.orchestrator import IdentityRuntime")
        violations = [r for r in result if "Atlas must not import Runtime" in r]
        assert len(violations) > 0

    def test_identitybench_imports_runtime(self):
        files = [{"path": "identitybench/engine.py", "lines": ["+from runtime.orchestrator import IdentityRuntime"]}]
        result = analyze_separation(files, "+from runtime.orchestrator import IdentityRuntime")
        violations = [r for r in result if "IdentityBench should not import Runtime" in r]
        assert len(violations) > 0


# ── Test Coverage ────────────────────────────────────────────────────


class TestTestCoverage:
    def test_source_without_tests(self):
        files = [
            {"path": "core/foo.py", "lines": ["+print('hello')"]},
        ]
        result = analyze_test_coverage(files)
        assert any("source files changed but no test files" in r for r in result)

    def test_source_with_tests(self):
        files = [
            {"path": "core/foo.py", "lines": ["+print('hello')"]},
            {"path": "tests/test_foo.py", "lines": ["+def test_foo(): pass"]},
        ]
        result = analyze_test_coverage(files)
        assert any("test file(s)" in r for r in result)

    def test_no_source_files(self):
        files = [{"path": "docs/readme.md", "lines": ["+# Docs"]}]
        result = analyze_test_coverage(files)
        assert all("source files changed" not in r for r in result)


# ── Diff Quality ─────────────────────────────────────────────────────


class TestDiffQuality:
    def test_small_pr(self):
        files = [{"path": "a.py", "additions": 10, "deletions": 2}]
        result = analyze_diff_quality(files, "feat: small change")
        assert any("10 additions" in r for r in result)

    def test_large_pr(self):
        files = [{"path": "a.py", "additions": 1000, "deletions": 0}]
        result = analyze_diff_quality(files, "fix: bug")
        assert any("Large PR" in r for r in result)

    def test_categorized_by_title(self):
        files = [{"path": "a.py", "additions": 10, "deletions": 0}]
        result = analyze_diff_quality(files, "feat: new feature")
        assert any("feature" in r for r in result)

    def test_uncategorized_title(self):
        files = [{"path": "a.py", "additions": 10, "deletions": 0}]
        result = analyze_diff_quality(files, "random change")
        assert any("Unable to auto-detect" in r for r in result)


# ── Architectural Impact ─────────────────────────────────────────────


class TestArchitecturalImpact:
    def test_detects_critical_file(self):
        files = [{"path": "runtime/orchestrator.py", "lines": ["+pass"]}]
        result = analyze_architectural_impact(files)
        assert any("Critical file" in r for r in result)

    def test_detects_layers(self):
        files = [{"path": "identitybench/atlas/health.py", "lines": ["+pass"]}]
        result = analyze_architectural_impact(files)
        assert any("layer(s)" in r for r in result)

    def test_no_impact(self):
        files = [{"path": "docs/readme.md", "lines": ["+# Docs"]}]
        result = analyze_architectural_impact(files)
        assert all("layer" not in r.lower() for r in result)


# ── Documentation ────────────────────────────────────────────────────


class TestDocumentation:
    def test_source_without_docs(self):
        files = [{"path": "core/foo.py", "lines": ["+pass"]}]
        result = analyze_documentation_impact(files)
        assert any("documentation update" in r for r in result)

    def test_source_with_docs(self):
        files = [
            {"path": "core/foo.py", "lines": ["+pass"]},
            {"path": "docs/architecture/foo.md", "lines": ["+# Docs"]},
        ]
        result = analyze_documentation_impact(files)
        assert any("Architecture documentation updated" in r for r in result)

    def test_docs_only(self):
        files = [{"path": "docs/readme.md", "lines": ["+# Docs"]}]
        result = analyze_documentation_impact(files)
        assert all("documentation update" not in r for r in result)


# ── Technical Debt ───────────────────────────────────────────────────


class TestTechnicalDebt:
    def test_no_debt_introduced(self):
        files = [{"path": "a.py", "lines": ["+print('clean code')"]}]
        result = analyze_technical_debt_introduced(files)
        assert any("No new technical debt" in r for r in result)

    def test_todo_introduced(self):
        files = [{"path": "a.py", "lines": ["+# TODO: fix this later"]}]
        result = analyze_technical_debt_introduced(files)
        assert any("technical debt marker" in r for r in result)

    def test_fixme_introduced(self):
        files = [{"path": "a.py", "lines": ["+    # FIXME: hack"]}]
        result = analyze_technical_debt_introduced(files)
        assert any("marker" in r for r in result)


# ── Goal Alignment ───────────────────────────────────────────────────


class TestGoalAlignment:
    def test_empty_config(self):
        result = analyze_goals_alignment([], "fix: bug", {})
        assert result == []

    def test_no_goals_key(self):
        result = analyze_goals_alignment([], "fix: bug", {"goals": {}})
        assert result == []

    def test_high_priority_goal_not_addressed(self):
        config = {"goals": {"primary_goals": [
            {"id": "test", "goal": "Increase benchmark scores", "priority": 9, "status": "active"}
        ]}}
        files = [{"path": "docs/readme.md", "lines": ["+# Docs"]}]
        result = analyze_goals_alignment(files, "docs: update readme", config)
        assert any("doesn't appear to address" in r for r in result)

    def test_low_priority_goal_skipped(self):
        config = {"goals": {"primary_goals": [
            {"id": "test", "goal": "Minor cleanup", "priority": 5, "status": "active"}
        ]}}
        files = [{"path": "docs/readme.md", "lines": ["+# Docs"]}]
        result = analyze_goals_alignment(files, "docs: update readme", config)
        assert len(result) == 0


# ── Readiness Assessment ─────────────────────────────────────────────


class TestReadiness:
    def test_ready(self):
        result = assess_readiness({"separation": ["✅ maintained"], "test": []})
        assert result[0] == "READY"

    def test_needs_work(self):
        result = assess_readiness({"separation": ["⚠️ warning"]})
        assert result[0] == "NEEDS_WORK"

    def test_not_ready(self):
        result = assess_readiness({"separation": ["❌ blocker"]})
        assert result[0] == "NOT_READY"


# ─── Daedalus Actions Tests ──────────────────────────────────────────


class TestDaedalusActions:
    def test_goals_lifecycle(self):
        from scripts.daedalus_actions import complete_goal, save_goals, load_goals
        goals = {
            "primary_goals": [
                {"id": "test-goal", "goal": "Test", "priority": 5, "status": "active",
                 "created_at": "2026-07-29", "metrics": [], "evidence": [], "observations": []}
            ],
            "observations": [],
            "initiatives": [],
        }
        save_goals(goals)
        result = complete_goal("test-goal", ["Achieved via test run"])
        assert result is True
        loaded = load_goals()
        target = [g for g in loaded["primary_goals"] if g["id"] == "test-goal"][0]
        assert target["status"] == "completed"
        assert "completed_at" in target
        assert "Achieved via test run" in target["evidence"]

    def test_load_goals_default(self):
        from scripts.daedalus_actions import load_goals
        orig = Path(".daedalus/goals.json")
        if orig.exists():
            backup = orig.read_text()
            orig.unlink()
        try:
            result = load_goals()
            assert "primary_goals" in result
        finally:
            if orig.exists() is False and backup:
                orig.write_text(backup)

    def test_check_benchmark_health_no_data(self):
        from scripts.daedalus_actions import check_benchmark_health
        result = check_benchmark_health()
        assert result == []

    def test_benchmark_declining_detection(self):
        from scripts.daedalus_actions import check_benchmark_health
        class FakeTrends:
            def rglob(self, pat):
                return []
        orig = __import__("pathlib").Path
        bench_dir = orig(".identitybench")
        if not bench_dir.exists():
            bench_dir.mkdir(parents=True)
        trend_file = bench_dir / "trend_test.json"
        trend_file.write_text(json.dumps([
            {"Memory": 80}, {"Memory": 78}, {"Memory": 76},
        ]))
        try:
            result = check_benchmark_health()
            declining = [r for r in result if r.get("type") == "declining_trend"]
            assert len(declining) > 0
        finally:
            trend_file.unlink()
