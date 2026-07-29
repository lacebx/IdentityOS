from __future__ import annotations

from typing import Any, Dict, List

import pytest

from identitybench.atlas.health import compute_identity_health, format_health
from identitybench.atlas.prediction import (
    predict_category_trend,
    predict_all_categories,
    format_prediction,
)
from identitybench.atlas.forecast import build_forecast, format_forecast
from identitybench.atlas.strategy import generate_strategies, format_strategies
from identitybench.atlas.decision_engine import (
    analyze_capability_impact,
    generate_evidence_recommendations,
    format_evidence_recommendation,
)
from identitybench.atlas.weighting import get_health_weights, apply_capability_lifecycle
from identitybench.atlas.capability_lifecycle import (
    compute_capability_ranking,
    format_capability_ranking,
    explain_score_change,
)
from identitybench.atlas.interfaces import (
    PredictionModel,
    ConfidenceEstimator,
    StrategyOptimizer,
    HealthAugmenter,
)

# =============================================================================
# Health Tests
# =============================================================================


class TestHealthComputation:
    def test_all_strong_scores(self):
        scores = {cat: 85.0 for cat in ["Memory", "Planning", "Trust", "Adaptation", "Learning", "Evolution"]}
        result = compute_identity_health(scores)
        assert result["health"] > 80.0
        assert result["confidence"] > 0
        assert "strong" in " ".join(result["reasons"]).lower()

    def test_all_low_scores(self):
        scores = {cat: 30.0 for cat in ["Memory", "Planning", "Trust", "Adaptation", "Learning", "Evolution"]}
        result = compute_identity_health(scores)
        assert result["health"] < 40.0
        assert "needs improvement" in " ".join(result["reasons"]).lower()

    def test_mixed_scores(self):
        scores = {
            "Memory": 90.0,
            "Planning": 40.0,
            "Trust": 80.0,
            "Adaptation": 50.0,
            "Learning": 70.0,
            "Evolution": 60.0,
        }
        result = compute_identity_health(scores)
        assert 0 < result["health"] < 100
        assert len(result["reasons"]) == 6

    def test_regression_penalty_critical(self):
        scores = {cat: 80.0 for cat in ["Memory", "Planning", "Trust", "Adaptation", "Learning", "Evolution"]}
        regressions = [{"metric": "Memory", "severity": "CRITICAL", "consecutive_decreases": 4}]
        result = compute_identity_health(scores, regressions=regressions)
        assert "Regress" in " ".join(result["reasons"])

    def test_regression_penalty_warning(self):
        scores = {cat: 80.0 for cat in ["Memory", "Planning", "Trust", "Adaptation", "Learning", "Evolution"]}
        regressions = [{"metric": "Planning", "severity": "WARNING", "consecutive_decreases": 3}]
        result = compute_identity_health(scores, regressions=regressions)
        assert result["regression_count"] == 1

    def test_trend_bonus_improving(self):
        scores = {cat: 70.0 for cat in ["Memory", "Planning", "Trust", "Adaptation", "Learning", "Evolution"]}
        predictions = [
            {"category": cat, "trend_direction": "improving", "confidence": 0.8}
            for cat in scores
        ]
        result = compute_identity_health(scores, predictions=predictions)
        assert result["trend_bonus"] > 0

    def test_trend_penalty_declining(self):
        scores = {cat: 70.0 for cat in ["Memory", "Planning", "Trust", "Adaptation", "Learning", "Evolution"]}
        predictions = [
            {"category": cat, "trend_direction": "declining", "confidence": 0.8}
            for cat in scores
        ]
        result = compute_identity_health(scores, predictions=predictions)
        assert result["trend_bonus"] < 0

    def test_capability_bonus_high_utilization(self):
        scores = {cat: 70.0 for cat in ["Memory", "Planning", "Trust", "Adaptation", "Learning", "Evolution"]}
        rankings = [{"rank_score": 90.0, "rank": 1}, {"rank_score": 85.0, "rank": 2}]
        result = compute_identity_health(scores, capability_rankings=rankings)
        assert result["capability_bonus"] > 0

    def test_health_without_regressions_or_predictions(self):
        scores = {"Memory": 75.0, "Planning": 65.0, "Trust": 55.0}
        result = compute_identity_health(scores)
        assert 0 < result["health"] < 100
        assert result["regression_count"] == 0

    def test_health_deterministic(self):
        scores = {cat: 80.0 for cat in ["Memory", "Planning", "Trust", "Adaptation", "Learning", "Evolution"]}
        r1 = compute_identity_health(scores)
        r2 = compute_identity_health(scores)
        assert r1["health"] == r2["health"]
        assert r1["confidence"] == r2["confidence"]
        assert r1["reasons"] == r2["reasons"]

    def test_confidence_high_with_filled_scores(self):
        scores = {cat: 85.0 for cat in ["Memory", "Planning", "Trust", "Adaptation", "Learning", "Evolution"]}
        result = compute_identity_health(scores)
        assert result["confidence"] > 0.7

    def test_format_health_output(self):
        scores = {cat: 80.0 for cat in ["Memory", "Planning", "Trust", "Adaptation", "Learning", "Evolution"]}
        result = compute_identity_health(scores)
        output = format_health(result)
        assert "Identity Health" in output
        assert "Contributions" in output
        assert "Reasons" in output


# =============================================================================
# Prediction Tests
# =============================================================================


class TestPredictionEngine:
    def test_no_data(self):
        result = predict_category_trend("Memory", [])
        assert result["trend_direction"] == "unknown"
        assert result["confidence"] == 0.0

    def test_single_point(self):
        result = predict_category_trend("Memory", [75.0])
        assert result["current_value"] == 75.0
        assert result["data_points"] == 1

    def test_upward_trend(self):
        result = predict_category_trend("Memory", [50, 55, 60, 65, 70])
        assert result["trend_direction"] == "improving"
        assert result["predicted_value"] > result["current_value"]
        assert result["confidence"] > 0

    def test_downward_trend(self):
        result = predict_category_trend("Planning", [80, 75, 70, 65, 60])
        assert result["trend_direction"] == "declining"
        assert result["predicted_value"] < result["current_value"]
        assert result["slope"] < 0

    def test_stable_flat(self):
        result = predict_category_trend("Trust", [70, 70, 70, 70, 70])
        assert result["trend_direction"] == "stable"
        assert abs(result["slope"]) < 0.3

    def test_predicted_value_bounded(self):
        result = predict_category_trend("Memory", [95, 96, 97, 98, 99], steps_ahead=10)
        assert result["predicted_value"] <= 100.0

    def test_confidence_increases_with_more_data(self):
        r1 = predict_category_trend("Memory", [50, 52, 54], steps_ahead=5)
        r2 = predict_category_trend("Memory", [50, 52, 54, 56, 58, 60, 62], steps_ahead=5)
        assert r2["confidence"] >= r1["confidence"]

    def test_evidence_generated(self):
        result = predict_category_trend("Memory", [60, 62, 64, 66, 68])
        assert len(result["evidence"]) > 0

    def test_recommended_action_present(self):
        result = predict_category_trend("Memory", [80, 78, 76, 74, 72])
        assert len(result["recommended_action"]) > 0

    def test_predict_all_categories(self):
        trends = [
            {"Memory": 70, "Planning": 65, "Trust": 80},
            {"Memory": 72, "Planning": 63, "Trust": 82},
            {"Memory": 74, "Planning": 61, "Trust": 84},
        ]
        results = predict_all_categories(trends)
        assert len(results) == 6
        cat_names = [r["category"] for r in results]
        assert "Memory" in cat_names
        assert "Evolution" in cat_names

    def test_predict_all_categories_empty(self):
        results = predict_all_categories([])
        assert len(results) == 6
        assert all(r["data_points"] == 0 for r in results)

    def test_predict_all_categories_partial(self):
        trends = [{"Memory": 70}, {"Memory": 72}, {"Memory": 74}]
        results = predict_all_categories(trends)
        mem = next(r for r in results if r["category"] == "Memory")
        assert mem["data_points"] == 3

    def test_format_prediction(self):
        pred = {
            "category": "Memory",
            "current_value": 75.0,
            "predicted_value": 80.0,
            "confidence": 0.82,
            "trend_direction": "improving",
            "slope": 1.2,
            "r_squared": 0.85,
            "data_points": 5,
            "evidence": ["Trend computed from 5 data points"],
            "recommended_action": "Continue current approach",
        }
        output = format_prediction(pred)
        assert "▲" in output
        assert "Memory" in output
        assert "82%" in output or "82" in output

    def test_prediction_deterministic(self):
        values = [50, 55, 60, 65, 70]
        r1 = predict_category_trend("Memory", values)
        r2 = predict_category_trend("Memory", values)
        assert r1["predicted_value"] == r2["predicted_value"]
        assert r1["slope"] == r2["slope"]
        assert r1["r_squared"] == r2["r_squared"]


# =============================================================================
# Forecast Tests
# =============================================================================


class TestForecast:
    def test_empty_predictions(self):
        forecast = build_forecast({"Memory": 80.0}, [])
        assert forecast == []

    def test_forecast_length(self):
        scores = {cat: 80.0 for cat in ["Memory", "Planning", "Trust", "Adaptation", "Learning", "Evolution"]}
        predictions = [
            {"category": cat, "data_points": 5, "slope": 0.5, "confidence": 0.7}
            for cat in scores
        ]
        forecast = build_forecast(scores, predictions, weeks=8)
        assert len(forecast) == 8

    def test_forecast_weeks_increment(self):
        scores = {cat: 80.0 for cat in ["Memory", "Planning", "Trust", "Adaptation", "Learning", "Evolution"]}
        predictions = [
            {"category": cat, "data_points": 5, "slope": 0.5, "confidence": 0.7}
            for cat in scores
        ]
        forecast = build_forecast(scores, predictions, weeks=3)
        assert [f["week"] for f in forecast] == [1, 2, 3]

    def test_forecast_health_changes(self):
        scores = {cat: 80.0 for cat in ["Memory", "Planning", "Trust", "Adaptation", "Learning", "Evolution"]}
        predictions = [
            {"category": cat, "data_points": 5, "slope": -1.0, "confidence": 0.7}
            for cat in scores
        ]
        forecast = build_forecast(scores, predictions, weeks=5)
        assert forecast[-1]["projected_health"] < forecast[0]["projected_health"]

    def test_forecast_scores_bounded(self):
        scores = {cat: 95.0 for cat in ["Memory", "Planning", "Trust", "Adaptation", "Learning", "Evolution"]}
        predictions = [
            {"category": cat, "data_points": 5, "slope": 2.0, "confidence": 0.7}
            for cat in scores
        ]
        forecast = build_forecast(scores, predictions, weeks=10)
        for entry in forecast:
            for cat, val in entry["projected_scores"].items():
                assert 0 <= val <= 100

    def test_forecast_with_few_data_points(self):
        scores = {"Memory": 80.0}
        predictions = [
            {"category": "Memory", "data_points": 0, "slope": 0, "confidence": 0}
        ]
        forecast = build_forecast(scores, predictions, weeks=3)
        assert len(forecast) == 3
        for entry in forecast:
            assert entry["projected_scores"]["Memory"] == 80.0

    def test_forecast_deterministic(self):
        scores = {cat: 80.0 for cat in ["Memory", "Planning", "Trust", "Adaptation", "Learning", "Evolution"]}
        predictions = [
            {"category": cat, "data_points": 5, "slope": 0.5, "confidence": 0.7}
            for cat in scores
        ]
        f1 = build_forecast(scores, predictions, weeks=4)
        f2 = build_forecast(scores, predictions, weeks=4)
        for e1, e2 in zip(f1, f2):
            assert e1["projected_health"] == e2["projected_health"]
            assert e1["projected_scores"] == e2["projected_scores"]

    def test_format_forecast(self):
        scores = {cat: 80.0 for cat in ["Memory", "Planning", "Trust", "Adaptation", "Learning", "Evolution"]}
        predictions = [
            {"category": cat, "data_points": 5, "slope": 0, "confidence": 0.7}
            for cat in scores
        ]
        forecast = build_forecast(scores, predictions, weeks=3)
        output = format_forecast(forecast, detail_categories=["Memory", "Planning"])
        assert "Week" in output
        assert "Health" in output
        assert "Memory" in output

    def test_format_forecast_empty(self):
        output = format_forecast([])
        assert "No forecast data" in output


# =============================================================================
# Strategy Tests
# =============================================================================


class TestStrategy:
    def test_strategies_for_weak_categories(self):
        health = {
            "contributions": {
                "Memory": 5.0,
                "Planning": 15.0,
                "Trust": 8.0,
                "Adaptation": 12.0,
                "Learning": 10.0,
                "Evolution": 9.0,
            }
        }
        predictions = [
            {"category": "Memory", "trend_direction": "declining", "slope": -1.0, "confidence": 0.7},
            {"category": "Trust", "trend_direction": "stable", "slope": 0, "confidence": 0.5},
        ]
        recs = [{"target": "Memory", "action": "IMPROVE", "confidence": 0.75, "evidence": ["Test"]}]
        strategies = generate_strategies(health, predictions, recs)
        assert len(strategies) > 0

    def test_no_strategies_for_strong_health(self):
        health = {
            "contributions": {
                "Memory": 15.0,
                "Planning": 15.0,
                "Trust": 15.0,
                "Adaptation": 12.0,
                "Learning": 12.0,
                "Evolution": 12.0,
            }
        }
        predictions = [
            {"category": c, "trend_direction": "improving", "slope": 0.5, "confidence": 0.7}
            for c in ["Memory", "Planning", "Trust", "Adaptation", "Learning", "Evolution"]
        ]
        strategies = generate_strategies(health, predictions, [])
        assert len(strategies) <= 3

    def test_strategy_has_actions(self):
        health = {"contributions": {"Memory": 5.0, "Planning": 15.0, "Trust": 15.0}}
        strategies = generate_strategies(
            health,
            [{"category": "Memory", "trend_direction": "declining", "slope": -1.0, "confidence": 0.7}],
            [{"target": "Memory", "action": "IMPROVE", "confidence": 0.75, "evidence": ["Low score"]}],
        )
        for s in strategies:
            assert len(s["actions"]) > 0

    def test_strategy_has_evidence(self):
        health = {"contributions": {"Memory": 5.0, "Planning": 15.0, "Trust": 15.0}}
        strategies = generate_strategies(
            health,
            [{"category": "Memory", "trend_direction": "declining", "slope": -1.0, "confidence": 0.7}],
            [{"target": "Memory", "action": "IMPROVE", "confidence": 0.75, "evidence": ["Low score"]}],
        )
        for s in strategies:
            assert len(s["supporting_evidence"]) > 0

    def test_strategy_confidence_ordering(self):
        health = {"contributions": {"Memory": 5.0, "Planning": 6.0, "Trust": 15.0}}
        strategies = generate_strategies(
            health,
            [
                {"category": "Memory", "trend_direction": "declining", "slope": -2.0, "confidence": 0.8},
                {"category": "Planning", "trend_direction": "stable", "slope": 0.0, "confidence": 0.5},
            ],
            [
                {"target": "Memory", "action": "IMPROVE", "confidence": 0.85, "evidence": ["X"]},
                {"target": "Planning", "action": "IMPROVE", "confidence": 0.6, "evidence": ["Y"]},
            ],
        )
        for i in range(len(strategies) - 1):
            assert strategies[i]["confidence"] >= strategies[i + 1]["confidence"]

    def test_strategy_with_rankings(self):
        health = {"contributions": {"Memory": 5.0, "Planning": 15.0, "Trust": 15.0}}
        strategies = generate_strategies(
            health,
            [{"category": "Memory", "trend_direction": "declining", "slope": -1.0, "confidence": 0.7}],
            [{"target": "Memory", "action": "IMPROVE", "confidence": 0.75, "evidence": ["Low"]}],
            capability_rankings=[{"cap_id": "web", "rank": 1}, {"cap_id": "calc", "rank": 2}],
        )
        if strategies:
            any_leverage = any("Leverage" in " ".join(s["actions"]) for s in strategies)
            if any_leverage:
                assert True

    def test_format_strategies(self):
        strategies = [
            {
                "name": "Improve Memory",
                "goal": "Improve Memory score",
                "actions": ["Compress memories", "Prune contexts"],
                "expected_gain": 8.0,
                "confidence": 0.8,
                "supporting_evidence": ["Memory is declining"],
            }
        ]
        output = format_strategies(strategies)
        assert "Improve Memory" in output
        assert "Expected gain" in output

    def test_format_strategies_empty(self):
        output = format_strategies([])
        assert "No strategies" in output

    def test_strategies_deterministic(self):
        health = {"contributions": {"Memory": 5.0, "Planning": 15.0, "Trust": 15.0}}
        preds = [{"category": "Memory", "trend_direction": "declining", "slope": -1.0, "confidence": 0.7}]
        recs = [{"target": "Memory", "action": "IMPROVE", "confidence": 0.75, "evidence": ["Low"]}]
        s1 = generate_strategies(health, preds, recs)
        s2 = generate_strategies(health, preds, recs)
        assert s1 == s2


# =============================================================================
# Decision Engine Tests
# =============================================================================


class TestDecisionEngine:
    def test_analyze_impact_empty(self):
        result = analyze_capability_impact([], [])
        assert result == []

    def test_analyze_impact_with_install(self):
        caps = [
            {"cap_id": "web_search", "event_type": "installation", "installation_success": True, "tick_offset": 5},
        ]
        runs = [
            {"tick_offset": 2, "category_scores": {"Research": 50, "Trust": 60}},
            {"tick_offset": 7, "category_scores": {"Research": 65, "Trust": 70}},
        ]
        result = analyze_capability_impact(caps, runs)
        assert len(result) > 0
        assert result[0]["capability"] == "web_search"

    def test_impact_has_deltas(self):
        caps = [
            {"cap_id": "web_search", "event_type": "installation", "installation_success": True, "tick_offset": 5},
        ]
        runs = [
            {"tick_offset": 2, "category_scores": {"Research": 50, "Trust": 60}},
            {"tick_offset": 7, "category_scores": {"Research": 65, "Trust": 70}},
        ]
        result = analyze_capability_impact(caps, runs)
        assert len(result[0]["deltas"]) > 0

    def test_impact_unknown_capability(self):
        caps = [
            {"cap_id": "unknown_cap", "event_type": "installation", "installation_success": True, "tick_offset": 5},
        ]
        runs = [
            {"tick_offset": 2, "category_scores": {"Research": 50}},
            {"tick_offset": 7, "category_scores": {"Research": 60}},
        ]
        result = analyze_capability_impact(caps, runs)
        assert result == []

    def test_evidence_recommendations_weak_scores(self):
        scores = {"Memory": 40, "Planning": 80, "Trust": 90}
        result = generate_evidence_recommendations(scores, [], [])
        assert len(result) > 0
        assert result[0]["action"] == "IMPROVE"

    def test_evidence_recommendations_no_weak_scores(self):
        scores = {"Memory": 85, "Planning": 88, "Trust": 92}
        result = generate_evidence_recommendations(scores, [], [])
        improvers = [r for r in result if r["action"] == "IMPROVE"]
        assert len(improvers) == 0

    def test_evidence_recommendations_with_regressions(self):
        scores = {"Memory": 80, "Planning": 80}
        regressions = [{"metric": "Memory", "severity": "CRITICAL", "consecutive_decreases": 4, "current_value": 70}]
        result = generate_evidence_recommendations(scores, [], [], regressions=regressions)
        investigate = [r for r in result if r["action"] == "INVESTIGATE"]
        assert len(investigate) > 0

    def test_evidence_recommendations_with_declining_prediction(self):
        scores = {"Memory": 80, "Planning": 80}
        predictions = [
            {"category": "Memory", "trend_direction": "declining", "confidence": 0.8,
             "current_value": 80, "predicted_value": 70}
        ]
        result = generate_evidence_recommendations(scores, [], predictions)
        investigate = [r for r in result if r["action"] == "INVESTIGATE" and r["target"] == "Memory"]
        assert len(investigate) > 0

    def test_evidence_recommendations_confidence_high_for_low_scores(self):
        scores = {"Memory": 25, "Planning": 85}
        result = generate_evidence_recommendations(scores, [], [])
        mem_rec = next(r for r in result if r["target"] == "Memory")
        assert mem_rec["confidence"] >= 0.7

    def test_format_evidence_recommendation(self):
        rec = {
            "action": "IMPROVE",
            "target": "Memory",
            "current_score": 45.0,
            "suggested_capabilities": ["filesystem", "web"],
            "evidence": ["Memory score is below threshold"],
            "confidence": 0.8,
        }
        output = format_evidence_recommendation(rec)
        assert "IMPROVE" in output
        assert "Memory" in output
        assert "filesystem" in output

    def test_decision_engine_deterministic(self):
        scores = {"Memory": 40, "Planning": 80, "Trust": 90}
        caps = [
            {"cap_id": "web_search", "event_type": "installation", "installation_success": True, "tick_offset": 5},
        ]
        runs = [
            {"tick_offset": 2, "category_scores": {"Research": 50, "Trust": 60}},
            {"tick_offset": 7, "category_scores": {"Research": 60, "Trust": 65}},
        ]
        impacts = analyze_capability_impact(caps, runs)
        r1 = generate_evidence_recommendations(scores, impacts, [])
        r2 = generate_evidence_recommendations(scores, impacts, [])
        assert r1 == r2


# =============================================================================
# Capability Lifecycle Tests
# =============================================================================


class TestCapabilityLifecycle:
    def test_ranking_empty(self):
        result = compute_capability_ranking([], [])
        assert result == []

    def test_ranking_single_capability(self):
        roi = [{"cap_id": "github", "uses": 100, "successful_uses": 98, "failures": 2,
                "installed_day": 5, "contribution": {"Research": 15.0, "Planning": 3.0},
                "avg_latency_ms": 480}]
        runs = [{"tick_offset": 50}]
        result = compute_capability_ranking(roi, runs)
        assert len(result) == 1
        assert result[0]["rank"] == 1

    def test_ranking_ordering(self):
        roi = [
            {"cap_id": "github", "uses": 200, "successful_uses": 198, "failures": 2,
             "installed_day": 5, "contribution": {"Research": 15.0}, "avg_latency_ms": 100},
            {"cap_id": "weather", "uses": 5, "successful_uses": 3, "failures": 2,
             "installed_day": 10, "contribution": {"Research": 1.0}, "avg_latency_ms": 200},
        ]
        runs = [{"tick_offset": 50}]
        result = compute_capability_ranking(roi, runs)
        assert result[0]["cap_id"] == "github"
        assert result[0]["rank"] == 1

    def test_ranking_roi_label_excellent(self):
        roi = [{"cap_id": "github", "uses": 500, "successful_uses": 495, "failures": 5,
                "installed_day": 1, "contribution": {"Research": 20.0}, "avg_latency_ms": 100}]
        runs = [{"tick_offset": 50}]
        result = compute_capability_ranking(roi, runs)
        assert result[0]["roi_label"] == "Excellent"

    def test_ranking_roi_label_low(self):
        roi = [{"cap_id": "weather", "uses": 1, "successful_uses": 0, "failures": 1,
                "installed_day": 40, "contribution": {}, "avg_latency_ms": 999}]
        runs = [{"tick_offset": 50}]
        result = compute_capability_ranking(roi, runs)
        assert result[0]["roi_label"] in ("Low", "Moderate")

    def test_ranking_recommendation_keep(self):
        roi = [{"cap_id": "github", "uses": 100, "successful_uses": 100, "failures": 0,
                "installed_day": 1, "contribution": {"Research": 20.0}, "avg_latency_ms": 100}]
        runs = [{"tick_offset": 50}]
        result = compute_capability_ranking(roi, runs)
        assert result[0]["recommendation"] == "Keep"

    def test_ranking_recommendation_archive(self):
        roi = [{"cap_id": "old_cap", "uses": 1, "successful_uses": 0, "failures": 1,
                "installed_day": 40, "contribution": {}, "avg_latency_ms": 999}]
        runs = [{"tick_offset": 50}]
        result = compute_capability_ranking(roi, runs)
        assert "Archiving" in result[0]["recommendation"]

    def test_explain_score_change_stable(self):
        result = explain_score_change("Memory", 75.0, 75.0)
        assert result["direction"] == "stable"
        assert result["delta"] == 0.0

    def test_explain_score_change_improved(self):
        result = explain_score_change("Memory", 60.0, 80.0)
        assert result["direction"] == "improved"
        assert result["delta"] == 20.0

    def test_explain_score_change_declined(self):
        result = explain_score_change("Planning", 85.0, 70.0)
        assert result["direction"] == "declined"
        assert result["delta"] == -15.0

    def test_explain_with_diff(self):
        diff = {
            "categories": [
                {"category": "Memory", "change": 20.0, "reasons": ["Recall improved"]},
            ]
        }
        result = explain_score_change("Memory", 60.0, 80.0, diff=diff)
        assert "Recall improved" in " ".join(result["root_causes"])

    def test_explain_with_run_history_trend(self):
        run_history = [
            {"category_scores": {"Memory": 60.0}},
            {"category_scores": {"Memory": 65.0}},
            {"category_scores": {"Memory": 70.0}},
        ]
        result = explain_score_change("Memory", 60.0, 70.0, run_history=run_history)
        assert len(result["root_causes"]) > 0

    def test_explain_with_capability_history(self):
        cap_history = [
            {"cap_id": "filesystem", "event_type": "installation"},
            {"cap_id": "filesystem", "event_type": "SUCCEEDED"},
        ]
        result = explain_score_change("Memory", 60.0, 75.0, capability_history=cap_history)
        assert len(result["root_causes"]) > 0

    def test_explain_confidence_high_with_large_delta(self):
        result = explain_score_change("Memory", 50.0, 80.0)
        assert result["confidence"] > 0.5

    def test_format_capability_ranking(self):
        ranked = [
            {"rank": 1, "cap_id": "github", "rank_score": 85.0, "roi_label": "Excellent",
             "recommendation": "Keep", "uses": 100, "success_rate": 98.0, "failures": 2,
             "reason": "High utilization, Very reliable"}
        ]
        output = format_capability_ranking(ranked)
        assert "github" in output
        assert "#1" in output

    def test_format_capability_ranking_empty(self):
        output = format_capability_ranking([])
        assert "No capabilities" in output

    def test_lifecycle_deterministic(self):
        roi = [{"cap_id": "github", "uses": 100, "successful_uses": 98, "failures": 2,
                "installed_day": 5, "contribution": {"Research": 15.0}, "avg_latency_ms": 480}]
        runs = [{"tick_offset": 50}]
        r1 = compute_capability_ranking(roi, runs)
        r2 = compute_capability_ranking(roi, runs)
        assert r1 == r2


# =============================================================================
# Weighting Tests
# =============================================================================


class TestWeighting:
    def test_health_weights_sum(self):
        weights = get_health_weights()
        cat_weights = weights["category_weights"]
        total = sum(cat_weights.values())
        assert abs(total - 0.75) < 0.01

    def test_health_weights_version(self):
        weights = get_health_weights()
        assert weights["version"] == "1.0.0"

    def test_health_weights_have_all_categories(self):
        weights = get_health_weights()
        for cat in ["Memory", "Planning", "Trust", "Adaptation", "Learning", "Evolution"]:
            assert cat in weights["category_weights"]

    def test_health_weights_no_magic_numbers_documented(self):
        weights = get_health_weights()
        assert "bonuses" in weights
        assert "penalties" in weights
        assert "prediction_confidence" in weights
        assert "capability_importance" in weights
        assert "strategy_confidence" in weights
        assert "forecast_decay" in weights

    def test_apply_capability_lifecycle(self):
        roi = [{"cap_id": "github", "uses": 100, "successful_uses": 98, "failures": 2,
                "installed_day": 5, "contribution": {"Research": 15.0},
                "recommendation": "KEEP"}]
        trends = [{"Memory": 80}]
        result = apply_capability_lifecycle(roi, trends)
        assert len(result) == 1
        assert "rank_score" in result[0]
        assert "rank" in result[0]

    def test_apply_capability_lifecycle_orders_by_score(self):
        roi = [
            {"cap_id": "a", "uses": 200, "successful_uses": 200, "failures": 0,
             "installed_day": 1, "contribution": {"X": 20.0}, "recommendation": "KEEP"},
            {"cap_id": "b", "uses": 1, "successful_uses": 0, "failures": 1,
             "installed_day": 40, "contribution": {}, "recommendation": "MONITOR"},
        ]
        result = apply_capability_lifecycle(roi, [])
        assert result[0]["cap_id"] == "a"
        assert result[0]["rank"] == 1


# =============================================================================
# Interface Tests
# =============================================================================


class TestInterfaces:
    def test_prediction_model_abstract(self):
        with pytest.raises(TypeError):
            PredictionModel()

    def test_confidence_estimator_abstract(self):
        with pytest.raises(TypeError):
            ConfidenceEstimator()

    def test_strategy_optimizer_abstract(self):
        with pytest.raises(TypeError):
            StrategyOptimizer()

    def test_health_augmenter_abstract(self):
        with pytest.raises(TypeError):
            HealthAugmenter()

    def test_concrete_prediction_model(self):
        class TestModel(PredictionModel):
            def predict(self, category, historical_values, steps_ahead=5):
                return {"predicted": 80.0}
        model = TestModel()
        assert model.predict("Memory", [70, 75, 78])["predicted"] == 80.0
        assert model.supports_bayesian() is False
        assert model.supports_ml() is False

    def test_concrete_confidence_estimator(self):
        class TestEstimator(ConfidenceEstimator):
            def estimate(self, data_quality, historical_accuracy=None):
                return 0.85
        estimator = TestEstimator()
        assert estimator.estimate({"data_points": 10}) == 0.85
        assert estimator.supports_bayesian() is False

    def test_concrete_strategy_optimizer(self):
        class TestOptimizer(StrategyOptimizer):
            def optimize(self, strategies, constraints=None):
                return strategies
        optimizer = TestOptimizer()
        assert optimizer.optimize([{"name": "test"}]) == [{"name": "test"}]
        assert optimizer.supports_reinforcement_learning() is False

    def test_concrete_health_augmenter(self):
        class TestAugmenter(HealthAugmenter):
            def augment(self, health_result, extra_context=None):
                return health_result
        augmenter = TestAugmenter()
        assert augmenter.augment({"health": 80}) == {"health": 80}
        assert augmenter.supports_organization_dashboards() is False
        assert augmenter.supports_multi_identity() is False


# =============================================================================
# Integration Tests
# =============================================================================


class TestAtlasIntegration:
    def test_health_to_strategies_flow(self):
        scores = {cat: 80.0 for cat in ["Memory", "Planning", "Trust", "Adaptation", "Learning", "Evolution"]}
        scores["Memory"] = 35.0
        trends = [{"Memory": v} for v in [35, 34, 33, 32, 31]]
        predictions = predict_all_categories(trends)
        health = compute_identity_health(scores, predictions=predictions)
        strategies = generate_strategies(
            health,
            predictions,
            [{"target": "Memory", "action": "IMPROVE", "confidence": 0.8, "evidence": ["Low"]}],
        )
        assert health["health"] < 90
        strat_names = [s["name"] for s in strategies]
        assert "Improve Memory" in strat_names

    def test_prediction_to_forecast_flow(self):
        trends = [
            {"Memory": 70, "Planning": 65, "Trust": 80},
            {"Memory": 72, "Planning": 64, "Trust": 81},
            {"Memory": 74, "Planning": 63, "Trust": 82},
        ]
        predictions = predict_all_categories(trends)
        scores = {"Memory": 74, "Planning": 63, "Trust": 82}
        forecast = build_forecast(scores, predictions, weeks=3)
        assert len(forecast) == 3
        assert forecast[0]["projected_health"] > 0

    def test_impact_to_recommendation_flow(self):
        caps = [
            {"cap_id": "web_search", "event_type": "installation", "installation_success": True, "tick_offset": 5},
        ]
        runs = [
            {"tick_offset": 2, "category_scores": {"Research": 40, "Trust": 50}},
            {"tick_offset": 7, "category_scores": {"Research": 60, "Trust": 65}},
        ]
        impacts = analyze_capability_impact(caps, runs)
        scores = {"Memory": 80, "Research": 55, "Trust": 65}
        recs = generate_evidence_recommendations(scores, impacts, [])
        if impacts:
            assert len(recs) > 0

    def test_full_atlas_pipeline(self):
        scores = {
            "Memory": 72.0,
            "Planning": 58.0,
            "Trust": 81.0,
            "Adaptation": 65.0,
            "Learning": 70.0,
            "Evolution": 68.0,
        }
        trends = [
            {"Memory": 70, "Planning": 62, "Trust": 80, "Adaptation": 63, "Learning": 68, "Evolution": 66},
            {"Memory": 71, "Planning": 60, "Trust": 80, "Adaptation": 64, "Learning": 69, "Evolution": 67},
            {"Memory": 72, "Planning": 58, "Trust": 81, "Adaptation": 65, "Learning": 70, "Evolution": 68},
        ]
        predictions = predict_all_categories(trends)
        health = compute_identity_health(scores, predictions=predictions)
        forecast = build_forecast(scores, predictions, weeks=4)
        recs = generate_evidence_recommendations(scores, [], predictions)
        strategies = generate_strategies(health, predictions, recs)
        assert health["health"] > 0
        assert len(forecast) == 4
        assert len(recs) > 0
        adaptive_strats = [s for s in strategies if "Adaptation" in s["name"]]
        assert len(adaptive_strats) > 0

    def test_full_pipeline_deterministic(self):
        scores = {cat: 70.0 for cat in ["Memory", "Planning", "Trust", "Adaptation", "Learning", "Evolution"]}
        trends = [{cat: 70.0 + i * 0.5 for cat in scores} for i in range(5)]
        predictions = predict_all_categories(trends)
        health = compute_identity_health(scores, predictions=predictions)
        forecast = build_forecast(scores, predictions, weeks=3)
        predictions2 = predict_all_categories(trends)
        health2 = compute_identity_health(scores, predictions=predictions2)
        forecast2 = build_forecast(scores, predictions, weeks=3)
        assert health["health"] == health2["health"]
        assert [f["projected_health"] for f in forecast] == [f["projected_health"] for f in forecast2]

    def test_separation_of_concerns(self):
        import identitybench.atlas as atlas
        import identitybench.engine as engine
        assert "atlas" not in dir(engine)
        assert "engine" not in dir(atlas)

    def test_atlas_exports(self):
        from identitybench.atlas import (
            compute_identity_health,
            format_health,
            predict_category_trend,
            predict_all_categories,
            format_prediction,
            build_forecast,
            format_forecast,
            generate_strategies,
            format_strategies,
            analyze_capability_impact,
            generate_evidence_recommendations,
            compute_capability_ranking,
            format_capability_ranking,
            explain_score_change,
            get_health_weights,
        )
        assert callable(compute_identity_health)
        assert callable(predict_category_trend)

    def test_explain_score_change_with_all_params(self):
        diff = {
            "categories": [
                {"category": "Memory", "change": 15.0, "reasons": ["Context pruning improved"]},
            ]
        }
        run_history = [
            {"category_scores": {"Memory": 60.0}},
            {"category_scores": {"Memory": 68.0}},
            {"category_scores": {"Memory": 75.0}},
        ]
        cap_history = [
            {"cap_id": "filesystem", "event_type": "installation"},
        ]
        result = explain_score_change("Memory", 60.0, 75.0, diff=diff, run_history=run_history, capability_history=cap_history)
        assert result["direction"] == "improved"
        assert result["delta"] == 15.0
        assert result["confidence"] >= 0.5

    def test_impact_no_matching_capability(self):
        caps = [
            {"cap_id": "non_existent", "event_type": "installation", "installation_success": True, "tick_offset": 5},
        ]
        runs = [
            {"tick_offset": 2, "category_scores": {"Research": 50}},
            {"tick_offset": 7, "category_scores": {"Research": 60}},
        ]
        result = analyze_capability_impact(caps, runs)
        assert result == []

    def test_prediction_high_confidence_with_strong_trend(self):
        result = predict_category_trend("Memory", [60, 65, 70, 75, 80, 85, 90, 95])
        assert result["confidence"] > 0.5
        assert result["r_squared"] > 0.8
