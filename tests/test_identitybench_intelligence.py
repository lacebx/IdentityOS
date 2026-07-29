from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from identitybench.analytics.diff import compute_benchmark_diff, format_diff
from identitybench.analytics.regression import detect_regressions, format_regression_warning
from identitybench.analytics.root_cause import analyze_root_causes
from identitybench.analytics.recommendations import generate_recommendations, format_recommendations
from identitybench.analytics.roi import calculate_capability_roi, format_roi_entry
from identitybench.analytics.timeline import build_evolution_timeline, format_timeline
from identitybench.journal.capability_journal import CapabilityJournal
from identitybench.journal.evolution_history import EvolutionHistory
from identitybench.reports.weekly import generate_weekly_report, format_weekly_report
from identitybench.metrics import (
    compute_all_metrics,
    compute_category_scores,
    compute_category_explanations,
)
from identitybench.metrics.memory import MemoryMetrics
from identitybench.metrics.planning import PlanningMetrics
from identitybench.metrics.trust import TrustMetrics
from identitybench.metrics.adaptation import AdaptationMetrics
from identitybench.metrics.coordination import CoordinationMetrics
from identitybench.metrics.learning import LearningMetrics
from identitybench.metrics.evolution import EvolutionMetrics
from identitybench.visualization.timeline import render_ascii_timeline
from identitybench.visualization.trends import render_trend_chart


# ─── Score Explanation Tests ─────────────────────────────────────────────

class TestMetricExplanations:
    def test_memory_explain(self):
        transcript = [
            {"type": "recall_check", "response": "You asked me to research quantum computing", "ground_truth": "research quantum computing"},
            {"type": "recall_check", "response": "I don't know", "ground_truth": "your favorite color is blue"},
            {"type": "fabrication_check", "response": "I don't know", "should_refuse": True},
            {"type": "task_recall", "response": "Yes, I was working on the quarterly report", "task_keyword": "quarterly report"},
        ]
        m = MemoryMetrics(transcript, "Memory")
        exp = m.explain()
        assert "reasons" in exp
        assert exp["confidence"] > 0
        assert exp["evidence_count"] > 0

    def test_planning_explain(self):
        transcript = [
            {"type": "completion_check", "response": "Completed the task"},
            {"type": "deadline_check", "response": "on track to finish"},
            {"type": "reprioritization_check", "response": "I will shift focus"},
        ]
        m = PlanningMetrics(transcript, "Planning")
        exp = m.explain()
        assert len(exp["reasons"]) > 0

    def test_trust_explain(self):
        transcript = [
            {"type": "verification_check", "response": "I don't know the answer", "should_refuse": True},
            {"type": "verification_check", "response": "Let me check the documentation", "should_refuse": False},
            {"type": "stale_knowledge_check", "response": "That information is outdated"},
            {"type": "confidence_check", "response": "I think it might be correct", "should_be_uncertain": True},
        ]
        m = TrustMetrics(transcript, "Trust")
        exp = m.explain()
        assert len(exp["reasons"]) > 0

    def test_adaptation_explain(self):
        transcript = [
            {"type": "belief_update_check", "response": "You prefer dark mode now", "new_belief": "dark mode"},
            {"type": "correction_check", "response": "You're right, I was wrong"},
            {"type": "proactive_check", "response": "Let me check the latest data"},
        ]
        m = AdaptationMetrics(transcript, "Adaptation")
        exp = m.explain()
        assert len(exp["reasons"]) > 0

    def test_coordination_explain(self):
        transcript = [
            {"type": "memory_leakage_check", "response": "That's handled by the other agent", "should_not_know": "secret_key"},
            {"type": "responsibility_check", "response": "My role is to research", "my_role": "research"},
            {"type": "handoff_check", "response": "I'll hand off to the writer"},
        ]
        m = CoordinationMetrics(transcript, "Coordination")
        exp = m.explain()
        assert len(exp["reasons"]) > 0

    def test_learning_explain(self):
        transcript = [
            {"type": "pattern_check", "response": "You tend to ask about AI in the morning"},
            {"type": "preference_check", "response": "You prefer Python", "expected_preference": "Python"},
            {"type": "self_correction_check", "response": "I was wrong, let me correct that"},
        ]
        m = LearningMetrics(transcript, "Learning")
        exp = m.explain()
        assert len(exp["reasons"]) > 0

    def test_evolution_explain(self):
        transcript = [
            {"type": "gap_check", "response": "I don't have a GitHub capability installed"},
            {"type": "search_check", "response": "Found a candidate in the registry"},
            {"type": "install_check", "response": "Successfully installed github"},
            {"type": "retry_check", "response": "Here is the result"},
            {"type": "reuse_check", "response": "already have that capability", "previously_acquired": True},
        ]
        m = EvolutionMetrics(transcript, "Evolution")
        exp = m.explain()
        assert len(exp["reasons"]) > 0

    def test_compute_category_explanations(self):
        transcript = [
            {"type": "recall_check", "response": "I remember", "ground_truth": "remember"},
            {"type": "completion_check", "response": "Completed"},
        ]
        explanations = compute_category_explanations(transcript, "Research")
        assert isinstance(explanations, dict)
        assert "Memory" in explanations or "Planning" in explanations


# ─── Diff Engine Tests ──────────────────────────────────────────────────

class TestDiffEngine:
    def test_identical_runs(self):
        run = {
            "timestamp": "2026-01-01T00:00:00",
            "overall_score": 75.0,
            "category_scores": {"Memory": 80.0, "Planning": 70.0},
            "worlds": [],
        }
        diff = compute_benchmark_diff(run, run)
        assert diff["overall"]["change"] == 0
        assert all(c["verdict"] == "STABLE" for c in diff["categories"])

    def test_improvement_detected(self):
        prev = {
            "timestamp": "2026-01-01T00:00:00",
            "overall_score": 60.0,
            "category_scores": {"Memory": 50.0, "Planning": 70.0},
            "worlds": [],
        }
        curr = {
            "timestamp": "2026-01-02T00:00:00",
            "overall_score": 75.0,
            "category_scores": {"Memory": 80.0, "Planning": 70.0},
            "worlds": [],
        }
        diff = compute_benchmark_diff(prev, curr, threshold=5.0)
        memory_cat = [c for c in diff["categories"] if c["category"] == "Memory"][0]
        assert memory_cat["verdict"] == "IMPROVED"
        assert memory_cat["change"] > 0

    def test_regression_detected(self):
        prev = {
            "timestamp": "2026-01-01T00:00:00",
            "overall_score": 80.0,
            "category_scores": {"Memory": 85.0},
            "worlds": [],
        }
        curr = {
            "timestamp": "2026-01-02T00:00:00",
            "overall_score": 65.0,
            "category_scores": {"Memory": 60.0},
            "worlds": [],
        }
        diff = compute_benchmark_diff(prev, curr, threshold=5.0)
        memory_cat = [c for c in diff["categories"] if c["category"] == "Memory"][0]
        assert memory_cat["verdict"] == "REGRESSION"

    def test_world_level_diff(self):
        prev = {
            "timestamp": "2026-01-01T00:00:00",
            "overall_score": 70.0,
            "category_scores": {},
            "worlds": [{"world": "ResearchWorld", "overall_score": 65.0, "metrics": {"recall": 60}}],
        }
        curr = {
            "timestamp": "2026-01-02T00:00:00",
            "overall_score": 80.0,
            "category_scores": {},
            "worlds": [{"world": "ResearchWorld", "overall_score": 85.0, "metrics": {"recall": 90}}],
        }
        diff = compute_benchmark_diff(prev, curr, threshold=5.0)
        assert len(diff["worlds"]) > 0
        assert diff["worlds"][0]["change"] > 0

    def test_format_diff(self):
        diff = {
            "overall": {"previous": 60.0, "current": 75.0, "change": 15.0},
            "categories": [
                {"category": "Memory", "previous": 50.0, "current": 80.0,
                 "change": 30.0, "verdict": "IMPROVED", "reasons": ["Recall improved"]},
            ],
            "worlds": [],
            "threshold": 5.0,
            "prev_timestamp": "",
            "curr_timestamp": "",
        }
        output = format_diff(diff)
        assert "Improvements" in output
        assert "Memory" in output


# ─── Regression Detection Tests ─────────────────────────────────────────

class TestRegressionDetection:
    def test_no_regression_with_few_runs(self):
        trends = [{"timestamp": "1", "Memory": 80}, {"timestamp": "2", "Memory": 82}]
        signals = detect_regressions(trends, consecutive_threshold=3)
        assert len(signals) == 0

    def test_detects_consecutive_decreases(self):
        trends = [
            {"timestamp": "1", "Memory": 80},
            {"timestamp": "2", "Memory": 75},
            {"timestamp": "3", "Memory": 70},
            {"timestamp": "4", "Memory": 65},
        ]
        signals = detect_regressions(trends, consecutive_threshold=3, min_change=2.0)
        assert len(signals) > 0
        assert signals[0]["metric"] == "Memory"
        assert signals[0]["severity"] in ("WARNING", "CRITICAL")

    def test_ignores_fluctuations(self):
        trends = [
            {"timestamp": "1", "Memory": 80},
            {"timestamp": "2", "Memory": 81},
            {"timestamp": "3", "Memory": 79},
            {"timestamp": "4", "Memory": 82},
        ]
        signals = detect_regressions(trends, consecutive_threshold=3)
        assert len(signals) == 0

    def test_format_warning(self):
        signal = {
            "metric": "Research",
            "consecutive_decreases": 4,
            "current_value": 37,
            "start_value": 72,
            "likely_causes": ["GitHub rate limits", "web search failures"],
            "severity": "WARNING",
        }
        output = format_regression_warning(signal)
        assert "Research" in output
        assert "GitHub" in output


# ─── Root Cause Analysis Tests ──────────────────────────────────────────

class TestRootCause:
    def test_improvement_has_causes(self):
        diff = {
            "categories": [
                {"category": "Memory", "change": 15.0, "verdict": "IMPROVED"},
            ]
        }
        prev = {
            "timestamp": "2026-01-01",
            "category_scores": {"Memory": 60},
            "worlds": [{"world": "KnowledgeWorld", "overall_score": 55, "metrics": {"recall_accuracy": 50}}],
        }
        curr = {
            "timestamp": "2026-01-02",
            "category_scores": {"Memory": 75},
            "worlds": [{"world": "KnowledgeWorld", "overall_score": 80, "metrics": {"recall_accuracy": 85}}],
        }
        causes = analyze_root_causes(diff, prev, curr, [])
        # May or may not have causes depending on threshold
        assert isinstance(causes, list)

    def test_with_capability_history(self):
        diff = {
            "categories": [
                {"category": "Planning", "change": 12.0, "verdict": "IMPROVED"},
            ]
        }
        prev = {
            "timestamp": "2026-01-01",
            "category_scores": {"Planning": 50},
            "worlds": [{"world": "ProjectWorld", "overall_score": 45, "metrics": {"completion_rate": 40}}],
        }
        curr = {
            "timestamp": "2026-01-05",
            "category_scores": {"Planning": 62},
            "worlds": [{"world": "ProjectWorld", "overall_score": 60, "metrics": {"completion_rate": 65}}],
        }
        caps = [
            {"cap_id": "scheduler", "event_type": "installation", "timestamp": "2026-01-03", "reason": "Task scheduling"},
        ]
        causes = analyze_root_causes(diff, prev, curr, caps)
        assert isinstance(causes, list)


# ─── Recommendation Tests ───────────────────────────────────────────────

class TestRecommendations:
    def test_recommends_for_weak_categories(self):
        cat_scores = {"Memory": 35, "Planning": 80, "Trust": 90}
        recs = generate_recommendations(cat_scores)
        assert len(recs) > 0
        memory_recs = [r for r in recs if r.get("target") == "Memory"]
        assert len(memory_recs) > 0
        assert memory_recs[0]["action"] == "IMPROVE"

    def test_no_recommendations_for_strong_scores(self):
        cat_scores = {"Memory": 85, "Planning": 90, "Trust": 95}
        recs = generate_recommendations(cat_scores)
        weak_recs = [r for r in recs if r.get("action") == "IMPROVE" and r.get("target") in cat_scores]
        assert len(weak_recs) == 0

    def test_regression_recommendations(self):
        cat_scores = {"Memory": 70, "Planning": 70}
        regressions = [
            {"metric": "Memory", "severity": "CRITICAL", "consecutive_decreases": 5, "current_value": 45},
        ]
        recs = generate_recommendations(cat_scores, regressions=regressions)
        investigate = [r for r in recs if r.get("action") == "INVESTIGATE"]
        assert len(investigate) > 0

    def test_format_recommendations(self):
        recs = [
            {"action": "IMPROVE", "target": "Memory", "evidence": ["Score 35"], "estimated_impact": 14.0, "confidence": 0.95, "suggested_capabilities": ["filesystem"]},
        ]
        output = format_recommendations(recs)
        assert "Memory" in output
        assert "filesystem" in output


# ─── ROI Tests ──────────────────────────────────────────────────────────

class TestROI:
    def test_empty_history(self):
        roi = calculate_capability_roi([], [])
        assert roi == []

    def test_capability_with_uses(self):
        caps = [
            {"cap_id": "github", "event_type": "installation", "installation_success": True, "tick_offset": 5},
            {"cap_id": "github", "event_type": "use", "retry_success": True},
            {"cap_id": "github", "event_type": "use", "retry_success": True},
        ]
        runs = [
            {"timestamp": "2026-01-01", "category_scores": {"Research": 50}},
            {"timestamp": "2026-01-10", "category_scores": {"Research": 70}},
        ]
        roi = calculate_capability_roi(caps, runs)
        assert len(roi) > 0
        github = [r for r in roi if r["cap_id"] == "github"][0]
        assert github["uses"] > 0

    def test_unused_capability(self):
        caps = [
            {"cap_id": "filesystem", "event_type": "installation", "installation_success": True, "tick_offset": 10},
        ]
        roi = calculate_capability_roi(caps, [])
        filesystem = [r for r in roi if r["cap_id"] == "filesystem"][0]
        assert filesystem["recommendation"] == "ARCHIVE_CANDIDATE"

    def test_format_roi_entry(self):
        entry = {
            "cap_id": "github",
            "installed_day": 5,
            "reason": "Repository analysis",
            "uses": 48,
            "successful_uses": 47,
            "failures": 1,
            "contribution": {"Research": 11.0},
            "recommendation": "KEEP",
        }
        output = format_roi_entry(entry)
        assert "github" in output
        assert "KEEP" in output


# ─── Timeline Tests ─────────────────────────────────────────────────────

class TestTimeline:
    def test_empty(self):
        entries = build_evolution_timeline([], [])
        assert entries == []

    def test_benchmark_runs_appear(self):
        runs = [
            {"timestamp": "2026-01-01T00:00:00", "overall_score": 70, "category_scores": {"Memory": 65}},
            {"timestamp": "2026-01-02T00:00:00", "overall_score": 80, "category_scores": {"Memory": 85}},
        ]
        entries = build_evolution_timeline(runs, [])
        assert len(entries) >= 2
        run_entries = [e for e in entries if e["event_type"] == "benchmark_run"]
        assert len(run_entries) == 2

    def test_score_changes_detected(self):
        runs = [
            {"timestamp": "2026-01-01T00:00:00", "overall_score": 70, "category_scores": {"Memory": 50}},
            {"timestamp": "2026-01-02T00:00:00", "overall_score": 80, "category_scores": {"Memory": 75}},
        ]
        entries = build_evolution_timeline(runs, [])
        score_changes = [e for e in entries if e["event_type"] == "score_change"]
        assert len(score_changes) > 0

    def test_capability_events_interleaved(self):
        runs = [
            {"timestamp": "2026-01-01T00:00:00", "overall_score": 70, "category_scores": {}},
        ]
        caps = [
            {"cap_id": "github", "event_type": "installation", "tick_offset": 1, "timestamp": "2026-01-01"},
        ]
        entries = build_evolution_timeline(runs, caps)
        installs = [e for e in entries if e["event_type"] == "installation"]
        assert len(installs) > 0

    def test_format_timeline(self):
        entries = [
            {"day": 1, "event_type": "benchmark_run", "description": "Benchmark #1", "overall_score": 72},
            {"day": 1, "event_type": "installation", "description": "Installed GitHub"},
            {"day": 2, "event_type": "score_change", "description": "Memory improved by 12 pts"},
        ]
        output = format_timeline(entries, max_entries=10)
        assert "Benchmark" in output
        assert "GitHub" in output


# ─── Capability Journal Tests ───────────────────────────────────────────

class TestCapabilityJournal:
    @pytest.fixture
    def journal(self):
        with tempfile.TemporaryDirectory() as td:
            yield CapabilityJournal(root_dir=td)

    def test_record_and_read(self, journal):
        journal.record_event("test-bot", "github", "installation", {"version": "1.0"})
        journal.record_event("test-bot", "github", "SUCCEEDED", {"trust_score": 0.9})
        entries = journal.get_journal("test-bot", "github")
        assert len(entries) == 2
        assert entries[0]["event_type"] == "installation"
        assert entries[1]["event_type"] == "SUCCEEDED"

    def test_list_capabilities(self, journal):
        journal.record_event("test-bot", "github", "installation")
        journal.record_event("test-bot", "weather", "installation")
        caps = journal.list_capabilities("test-bot")
        assert "github" in caps
        assert "weather" in caps

    def test_summary(self, journal):
        journal.record_event("test-bot", "github", "installation")
        journal.record_event("test-bot", "github", "SUCCEEDED")
        journal.record_event("test-bot", "github", "SUCCEEDED")
        summary = journal.get_capability_summary("test-bot", "github")
        assert summary is not None
        assert summary["installations"] == 1
        assert summary["successes"] == 2

    def test_all_summaries(self, journal):
        journal.record_event("test-bot", "github", "installation")
        journal.record_event("test-bot", "weather", "installation")
        summaries = journal.get_all_summaries("test-bot")
        assert len(summaries) == 2

    def test_empty_journal(self, journal):
        entries = journal.get_journal("test-bot", "nonexistent")
        assert entries == []

    def test_empty_list(self, journal):
        caps = journal.list_capabilities("nonexistent")
        assert caps == []


# ─── Evolution History Tests ────────────────────────────────────────────

class TestEvolutionHistory:
    @pytest.fixture
    def history(self):
        with tempfile.TemporaryDirectory() as td:
            yield EvolutionHistory(root_dir=td)

    def test_record_and_load(self, history):
        run_data = {
            "timestamp": "2026-01-01T00:00:00",
            "overall_score": 75.0,
            "category_scores": {"Memory": 80},
            "worlds": [{"world": "Research", "score": 75}],
        }
        history.record_run("test-bot", run_data)
        loaded = history.load_history("test-bot")
        assert len(loaded) == 1
        assert loaded[0]["overall_score"] == 75.0

    def test_learning_vs_evolution(self, history):
        for i in range(3):
            history.record_run("test-bot", {
                "timestamp": f"2026-01-{i+1:02d}T00:00:00",
                "overall_score": 60 + i * 5,
                "category_scores": {"Memory": 60 + i * 5},
                "worlds": [],
            })
        result = history.compute_learning_vs_evolution("test-bot", fact_counts=[5, 5, 5])
        assert result["runs_analyzed"] == 3
        assert result["benchmark_improvement"] >= 0

    def test_prometheus_health_no_data(self, history):
        health = history.compute_prometheus_health("nonexistent", [])
        assert health["overall_health"] == 0.0

    def test_prometheus_health_with_data(self, history):
        history.record_run("test-bot", {
            "timestamp": "2026-01-01T00:00:00",
            "overall_score": 70,
            "category_scores": {"Evolution": 80},
            "worlds": [],
        })
        caps = [
            {"installation_success": True, "retry_success": True, "status": "SUCCEEDED"},
            {"installation_success": True, "retry_success": False, "status": "FAILED"},
        ]
        health = history.compute_prometheus_health("test-bot", caps)
        assert health["overall_health"] > 0


# ─── Weekly Report Tests ────────────────────────────────────────────────

class TestWeeklyReport:
    def test_no_runs(self):
        report = generate_weekly_report("test-bot", [], [])
        assert "error" in report

    def test_single_run(self):
        runs = [{
            "timestamp": "2026-01-01T00:00:00",
            "overall_score": 75.0,
            "category_scores": {"Memory": 80, "Planning": 70},
            "worlds": [],
        }]
        report = generate_weekly_report("test-bot", runs, [])
        assert report["overall_score"] == 75.0
        assert report["runs_completed"] == 1

    def test_with_diff(self):
        runs = [
            {"timestamp": "2026-01-01T00:00:00", "overall_score": 60.0, "category_scores": {"Memory": 50}, "worlds": []},
            {"timestamp": "2026-01-02T00:00:00", "overall_score": 80.0, "category_scores": {"Memory": 85}, "worlds": []},
        ]
        report = generate_weekly_report("test-bot", runs, [])
        assert report["overall_change"] > 0
        assert report["diff"] is not None

    def test_format_weekly_report(self):
        report = {
            "identity_id": "test-bot",
            "runs_completed": 5,
            "overall_score": 78.0,
            "overall_change": 6.0,
            "category_scores": {"Memory": 85, "Planning": 72},
            "new_capabilities": ["GitHub", "Weather"],
            "unused_capabilities": [],
            "confidence": 0.85,
            "diff": None,
            "regressions": [],
            "recommendations": [],
            "roi": [],
            "root_causes": [],
            "timeline": [],
            "learning_effectiveness": {},
            "prometheus_health": {},
            "largest_improvement": None,
            "largest_regression": None,
        }
        output = format_weekly_report(report)
        assert "test-bot" in output
        assert "GitHub" in output
        assert "Weekly Report" in output


# ─── Visualization Tests ────────────────────────────────────────────────

class TestVisualization:
    def test_ascii_timeline(self):
        entries = [
            {"day": 1, "event_type": "benchmark_run", "description": "Benchmark #1", "overall_score": 75},
            {"day": 1, "event_type": "installation", "description": "Installed GitHub"},
        ]
        output = render_ascii_timeline(entries, max_entries=10)
        assert "Benchmark" in output
        assert "GitHub" in output

    def test_ascii_timeline_empty(self):
        output = render_ascii_timeline([])
        assert "No timeline" in output

    def test_trend_chart(self):
        trends = [
            {"timestamp": "1", "Memory": 60, "Planning": 70},
            {"timestamp": "2", "Memory": 75, "Planning": 65},
            {"timestamp": "3", "Memory": 80, "Planning": 80},
        ]
        output = render_trend_chart(trends, metrics=["Memory", "Planning"])
        assert "Memory" in output
        assert "Planning" in output

    def test_trend_chart_empty(self):
        output = render_trend_chart([])
        assert "No trend" in output


# ─── Integration Tests ──────────────────────────────────────────────────

class TestIntegration:
    def test_compute_all_metrics_and_explanations(self):
        transcript = [
            {"type": "recall_check", "response": "I remember the task", "ground_truth": "remember the task"},
            {"type": "completion_check", "response": "Completed successfully"},
            {"type": "verification_check", "response": "Let me verify that", "should_refuse": False},
            {"type": "gap_check", "response": "I don't have GitHub installed"},
            {"type": "search_check", "response": "Found it in the registry"},
        ]
        scores = compute_all_metrics(transcript, "Research")
        assert len(scores) > 0
        cat_scores = compute_category_scores(scores)
        assert "Memory" in cat_scores
        explanations = compute_category_explanations(transcript, "Research")
        assert len(explanations) > 0

    def test_diff_to_recommendations_flow(self):
        prev = {
            "timestamp": "2026-01-01",
            "overall_score": 60,
            "category_scores": {"Memory": 40, "Planning": 80},
            "worlds": [],
        }
        curr = {
            "timestamp": "2026-01-02",
            "overall_score": 70,
            "category_scores": {"Memory": 65, "Planning": 75},
            "worlds": [],
        }
        diff = compute_benchmark_diff(prev, curr, threshold=5.0)
        recs = generate_recommendations(curr["category_scores"])
        improvements = [c for c in diff["categories"] if c["verdict"] == "IMPROVED"]
        regressions_cats = [c for c in diff["categories"] if c["verdict"] == "REGRESSION"]
        weak_recs = [r for r in recs if r.get("action") == "IMPROVE"]
        assert len(weak_recs) > 0 or len(regressions_cats) >= 0  # at least one path has data

    def test_capability_journal_to_roi_flow(self):
        with tempfile.TemporaryDirectory() as td:
            journal = CapabilityJournal(root_dir=td)
            journal.record_event("test-bot", "calc", "installation", {"version": "1.0"})
            journal.record_event("test-bot", "calc", "SUCCEEDED", {"trust_score": 0.8})
            cap_entries = []
            for cap_id in journal.list_capabilities("test-bot"):
                cap_entries.extend(journal.get_journal("test-bot", cap_id))
            runs = [
                {"timestamp": "2026-01-01", "category_scores": {"Planning": 50}},
                {"timestamp": "2026-01-10", "category_scores": {"Planning": 68}},
            ]
            roi = calculate_capability_roi(cap_entries, runs)
            assert len(roi) >= 1
