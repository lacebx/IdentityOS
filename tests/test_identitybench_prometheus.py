from __future__ import annotations

import tempfile
from unittest.mock import MagicMock

import pytest

from identitybench.metrics.evolution import EvolutionMetrics
from identitybench.metrics import compute_category_scores
from identitybench.worlds.evolution import EvolutionWorld
from identitybench.worlds.base import InteractionEntry, WorldResult


class TestEvolutionMetrics:
    @pytest.fixture
    def good_transcript(self):
        return [
            {"type": "gap_check", "response": "I don't have a GitHub capability installed. Let me search the registry."},
            {"type": "gap_check", "response": "I don't currently have a weather capability. Searching for one..."},
            {"type": "search_check", "response": "Found candidate: github v2.4 in the registry"},
            {"type": "search_check", "response": "Discovered weather v1.0 in the capability marketplace"},
            {"type": "install_check", "response": "Successfully installed github v2.4"},
            {"type": "install_check", "response": "Installation complete: weather now available"},
            {"type": "retry_check", "response": "Here is the latest release: v2.0.0", "expected_success": True},
            {"type": "retry_check", "response": "Here is the weather result: London is 15°C and cloudy", "expected_success": True},
            {"type": "evolution_entry", "duration_ms": 2500.0},
            {"type": "evolution_entry", "duration_ms": 1800.0},
            {"type": "reuse_check", "response": "I already have GitHub installed from before", "previously_acquired": True},
            {"type": "duplicate_check", "response": "GitHub is already installed", "already_installed": True},
            {"type": "improvement_check", "performance_gain": 0.7},
            {"type": "improvement_check", "performance_gain": 0.8},
        ]

    def test_evolution_metrics_compute(self, good_transcript):
        m = EvolutionMetrics(good_transcript, "Evolution")
        scores = m.compute()
        assert scores["gap_detection"] == 100.0
        assert scores["search_quality"] == 100.0
        assert scores["install_success"] == 100.0
        assert scores["retry_success"] == 100.0
        assert scores["adaptation_speed"] == 100.0
        assert scores["capability_reuse"] == 100.0
        assert scores["unnecessary_installs_prevented"] == 100.0
        assert scores["performance_improvement"] == 100.0
        assert scores["evolution_score"] == 100.0

    def test_evolution_metrics_empty(self):
        m = EvolutionMetrics([], "Evolution")
        scores = m.compute()
        for v in scores.values():
            assert v == 50.0

    def test_category_scores_includes_evolution(self, good_transcript):
        from identitybench.metrics import compute_all_metrics
        scores = compute_all_metrics(good_transcript, "Evolution")
        cat = compute_category_scores(scores)
        assert "Evolution" in cat
        assert cat["Evolution"] > 0

    def test_half_performance(self):
        transcript = [
            {"type": "gap_check", "response": "I don't have the capability"},
            {"type": "search_check", "response": "Found it in the registry"},
            {"type": "install_check", "response": "Installed successfully"},
            {"type": "retry_check", "response": "Here is the result", "expected_success": True},
            {"type": "retry_check", "response": "I found the data you requested", "expected_success": True},
            {"type": "evolution_entry", "duration_ms": 20000.0},
            {"type": "reuse_check", "response": "I still have it", "previously_acquired": True},
            {"type": "improvement_check", "performance_gain": 0.3},
        ]
        m = EvolutionMetrics(transcript, "Evolution")
        scores = m.compute()
        assert scores["gap_detection"] == 100.0
        assert scores["retry_success"] == 100.0
        assert scores["adaptation_speed"] == 50.0

    def test_failed_scenario(self):
        transcript = [
            {"type": "gap_check", "response": "I don't have the capability"},
            {"type": "search_check", "response": "I couldn't find anything"},
            {"type": "install_check", "response": "Installation failed with error", "expected_success": True},
            {"type": "retry_check", "response": "Still cannot access", "expected_success": True},
            {"type": "evolution_entry", "duration_ms": 45000.0},
            {"type": "improvement_check", "performance_gain": -0.2},
        ]
        m = EvolutionMetrics(transcript, "Evolution")
        scores = m.compute()
        assert scores["gap_detection"] == 100.0
        assert scores["search_quality"] == 0.0
        assert scores["install_success"] < 100.0


class TestEvolutionWorld:
    def test_build_schedule(self):
        world = EvolutionWorld()
        entries = world.build_schedule()
        assert len(entries) > 0
        assert all(isinstance(e, InteractionEntry) for e in entries)
        assert any("GitHub" in e.user_input for e in entries)
        assert any("weather" in e.user_input.lower() for e in entries)
        assert any("Calculate" in e.user_input for e in entries)

    def test_check_types(self):
        world = EvolutionWorld()
        entries = world.build_schedule()
        types = {e.check_type for e in entries}
        assert "gap_check" in types
        assert "retry_check" in types
        assert "reuse_check" in types
        assert "duplicate_check" in types

    def test_world_result_with_evolution(self):
        wr = WorldResult(
            world_name="Evolution",
            overall_score=92.0,
            metrics={
                "gap_detection": 95.0,
                "search_quality": 90.0,
                "install_success": 100.0,
                "retry_success": 85.0,
                "evolution_score": 92.0,
            },
            category_scores={"Evolution": 92.0},
        )
        assert wr.world_name == "Evolution"
        assert wr.overall_score == 92.0
        assert wr.metrics["evolution_score"] == 92.0
        cat = compute_category_scores(wr.metrics)
        assert "Evolution" in cat
