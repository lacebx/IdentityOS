from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from identitybench.engine import IdentityBench
from identitybench.metrics import compute_all_metrics, compute_category_scores
from identitybench.metrics.memory import MemoryMetrics
from identitybench.metrics.planning import PlanningMetrics
from identitybench.metrics.trust import TrustMetrics
from identitybench.metrics.adaptation import AdaptationMetrics
from identitybench.metrics.coordination import CoordinationMetrics
from identitybench.metrics.learning import LearningMetrics
from identitybench.reporting import (
    generate_regression_summary,
    generate_report_text,
    generate_markdown_report,
)
from identitybench.scheduler import Scheduler
from identitybench.storage import BenchmarkStorage
from identitybench.time_engine import SimulatedClock
from identitybench.worlds.base import BenchmarkWorld, InteractionEntry, WorldResult
from identitybench.worlds.research import ResearchWorld
from identitybench.worlds.project import ProjectWorld
from identitybench.worlds.assistant import AssistantWorld
from identitybench.worlds.knowledge import KnowledgeWorld
from identitybench.worlds.trust import TrustWorld


class TestSimulatedClock:
    def test_advance(self):
        clock = SimulatedClock(seed=42)
        t0 = clock.now()
        clock.advance(3)
        assert clock.tick_count == 3
        assert (clock.now() - t0).total_seconds() == 3 * 3600

    def test_deterministic(self):
        c1 = SimulatedClock(seed=42)
        c2 = SimulatedClock(seed=42)
        assert c1.random() == c2.random()
        assert c1.randint(1, 100) == c2.randint(1, 100)


class TestScheduler:
    def test_at(self):
        s = Scheduler()
        calls = []
        s.at(3, lambda: calls.append("fired"))
        s.set_tick(0)
        s.tick()
        s.set_tick(1)
        s.tick()
        s.set_tick(2)
        s.tick()
        assert len(calls) == 0
        s.set_tick(3)
        s.tick()
        assert len(calls) == 1

    def test_every(self):
        s = Scheduler()
        calls = []
        s.every(2, lambda: calls.append("tick"), start_tick=1)
        for t in range(6):
            s.set_tick(t)
            s.tick()
        assert len(calls) == 3  # ticks 1, 3, 5

    def test_reset(self):
        s = Scheduler()
        s.at(5, lambda: None)
        assert s.pending_count() == 1
        s.reset()
        assert s.pending_count() == 0


class TestBenchmarkStorage:
    @pytest.fixture
    def tmp_storage(self):
        with tempfile.TemporaryDirectory() as td:
            yield BenchmarkStorage(root_dir=td)

    def test_save_and_load_run(self, tmp_storage):
        run_data = {
            "timestamp": "2025-01-01T00:00:00",
            "identity_id": "test-bot",
            "overall_score": 85.5,
        }
        path = tmp_storage.save_run("test-bot", run_data)
        assert Path(path).exists()
        loaded = tmp_storage.load_latest_run("test-bot")
        assert loaded["overall_score"] == 85.5

    def test_list_runs(self, tmp_storage):
        for i in range(3):
            tmp_storage.save_run("test-bot", {"overall_score": i * 10, "timestamp": f"2025-01-0{i+1}T00:00:00"})
        runs = tmp_storage.list_runs("test-bot")
        assert len(runs) == 3

    def test_list_identities(self, tmp_storage):
        tmp_storage.save_run("alice", {"overall_score": 90})
        tmp_storage.save_run("bob", {"overall_score": 80})
        ids = tmp_storage.list_identities()
        assert "alice" in ids
        assert "bob" in ids


class TestMetrics:
    @pytest.fixture
    def good_transcript(self):
        return [
            {"type": "recall_check", "response": "Your favorite color is green", "ground_truth": "green"},
            {"type": "recall_check", "response": "I remember you use VSCode", "ground_truth": "VSCode"},
            {"type": "fabrication_check", "response": "I don't have any information about that",
             "should_refuse": True},
            {"type": "task_recall", "response": "Yes, I'm still working on the benchmark tool", "task_keyword": "benchmark"},
            {"type": "verification_check", "response": "I don't know, I can't confirm that vulnerability", "should_refuse": True},
            {"type": "verification_check", "response": "I cannot confirm that claim without verification", "should_refuse": True},
            {"type": "belief_update_check", "response": "You use Neovim now, not VSCode",
             "new_belief": "Neovim", "old_belief": "VSCode"},
            {"type": "correction_check", "response": "You're right, I stand corrected"},
            {"type": "pattern_check", "response": "I notice a pattern: you tend to use terminal-based editors"},
            {"type": "preference_check", "response": "Your preferred editor is Helix", "expected_preference": "Helix"},
        ]

    def test_memory_metrics(self, good_transcript):
        m = MemoryMetrics(good_transcript)
        scores = m.compute()
        assert scores["recall_accuracy"] == 100.0
        assert scores["false_memories"] == 100.0
        assert scores["forgotten_tasks"] == 100.0

    def test_planning_metrics(self):
        transcript = [
            {"type": "task_assignment", "response": ""},
            {"type": "completion_check", "response": "I completed the task"},
            {"type": "deadline_check", "response": "I'm on track"},
            {"type": "reprioritization_check", "response": "I need to shift focus to security"},
        ]
        m = PlanningMetrics(transcript)
        scores = m.compute()
        assert scores["completion_rate"] == 100.0
        assert scores["reprioritization_quality"] == 100.0

    def test_trust_metrics(self, good_transcript):
        m = TrustMetrics(good_transcript)
        scores = m.compute()
        assert scores["hallucination_rate"] == 100.0
        assert scores["verification_rate"] == 100.0

    def test_adaptation_metrics(self, good_transcript):
        m = AdaptationMetrics(good_transcript)
        scores = m.compute()
        assert scores["updated_beliefs"] == 100.0
        assert scores["corrected_assumptions"] == 100.0

    def test_learning_metrics(self, good_transcript):
        m = LearningMetrics(good_transcript)
        scores = m.compute()
        assert scores["pattern_recognition"] == 100.0
        assert scores["preference_discovery"] == 100.0

    def test_compute_all(self, good_transcript):
        scores = compute_all_metrics(good_transcript)
        for key in ["recall_accuracy", "false_memories", "hallucination_rate", "verification_rate"]:
            assert key in scores
            assert scores[key] == 100.0
        cat = compute_category_scores(scores)
        assert "Memory" in cat
        assert "Trust" in cat

    def test_metrics_with_empty_transcript(self):
        scores = compute_all_metrics([])
        assert isinstance(scores, dict)
        for v in scores.values():
            assert v == 50.0


class TestWorlds:
    def test_research_world_builds_schedule(self):
        world = ResearchWorld()
        entries = world.build_schedule()
        assert len(entries) > 0
        assert all(isinstance(e, InteractionEntry) for e in entries)

    def test_project_world_builds_schedule(self):
        world = ProjectWorld()
        entries = world.build_schedule()
        assert len(entries) > 0
        assert any("benchmark" in e.user_input for e in entries)

    def test_assistant_world_builds_schedule(self):
        world = AssistantWorld()
        entries = world.build_schedule()
        assert len(entries) >= 9
        assert any("VSCode" in e.user_input for e in entries)
        assert any("Helix" in e.user_input for e in entries)

    def test_knowledge_world_builds_schedule(self):
        world = KnowledgeWorld()
        entries = world.build_schedule()
        assert len(entries) > 0
        assert any("stars" in e.user_input for e in entries)

    def test_trust_world_builds_schedule(self):
        world = TrustWorld()
        entries = world.build_schedule()
        assert len(entries) > 0
        assert any("vulnerability" in e.user_input for e in entries)

    def test_world_result_dataclass(self):
        wr = WorldResult(
            world_name="Test",
            overall_score=85.0,
            metrics={"recall_accuracy": 90.0},
            category_scores={"Memory": 90.0},
        )
        assert wr.world_name == "Test"
        assert wr.overall_score == 85.0
        assert wr.metrics["recall_accuracy"] == 90.0


class TestEngine:
    def test_engine_initialization(self):
        with tempfile.TemporaryDirectory() as td:
            engine = IdentityBench(
                identity_id="test-bot",
                storage_path=td,
            )
            assert engine.identity_id == "test-bot"
            assert engine.runtime is None

    def test_engine_deterministic_rng(self):
        c1 = SimulatedClock(seed=42)
        c2 = SimulatedClock(seed=42)
        vals1 = [c1.random() for _ in range(10)]
        vals2 = [c2.random() for _ in range(10)]
        assert vals1 == vals2

    def test_run_with_mock_runtime(self):
        with tempfile.TemporaryDirectory() as td:
            engine = IdentityBench(
                identity_id="test-bot",
                storage_path=td,
            )
            mock_runtime = MagicMock()
            mock_response = MagicMock()
            mock_response.output = "I remember that. The answer is green."
            mock_runtime.process.return_value = mock_response
            mock_runtime.load.return_value = MagicMock()
            mock_runtime.identity_store.list.return_value = ["test-bot"]
            engine.runtime = mock_runtime
            results = engine.run(world_classes=[ResearchWorld], seed=42)
            assert "Research" in results
            assert mock_runtime.process.call_count >= 6


class TestBenchmarkReport:
    def test_generate_regression_summary(self):
        prev = {"overall_score": 90, "category_scores": {"Memory": 85, "Trust": 80}}
        curr = {"overall_score": 75, "category_scores": {"Memory": 70, "Trust": 78}}
        summary = generate_regression_summary(prev, curr, threshold=5.0)
        assert summary["failed"] is True
        assert len(summary["regressions"]) > 0
        assert any(r["category"] == "Memory" for r in summary["regressions"])
        assert summary["overall"]["verdict"] == "REGRESSION"

    def test_generate_report_text(self):
        run_data = {
            "timestamp": "2025-01-01T00:00:00",
            "identity_id": "test-bot",
            "overall_score": 85.0,
            "elapsed_seconds": 120,
            "category_scores": {"Memory": 90, "Planning": 80, "Trust": 85, "Adaptation": 75, "Coordination": 70, "Learning": 80},
            "worlds": [
                {"world": "Research", "overall_score": 88, "metrics": {"recall": 90, "forgetting": 86}},
                {"world": "Trust", "overall_score": 82, "metrics": {"hallucination": 95, "verification": 75}},
            ],
        }
        text = generate_report_text(run_data)
        assert "test-bot" in text
        assert "85" in text
        assert "Research" in text

    def test_generate_markdown_report(self):
        run_data = {
            "timestamp": "2025-01-01T00:00:00",
            "identity_id": "test-bot",
            "overall_score": 85.0,
            "category_scores": {"Memory": 90, "Trust": 85},
            "worlds": [],
        }
        md = generate_markdown_report(run_data)
        assert "# IdentityBench Report" in md
        assert "test-bot" in md


class TestWorldInteractionEntry:
    def test_interaction_entry_defaults(self):
        entry = InteractionEntry(user_input="Hello")
        assert entry.user_input == "Hello"
        assert entry.expected_hints == []
        assert entry.should_refuse is False
        assert entry.check_type == "general"
        assert entry.session_id == "benchmark"

    def test_interaction_entry_with_metadata(self):
        entry = InteractionEntry(
            user_input="Test",
            check_type="recall_check",
            ground_truth="truth",
            metadata={"key": "val"},
        )
        assert entry.check_type == "recall_check"
        assert entry.ground_truth == "truth"
        assert entry.metadata["key"] == "val"


class TestCLI:
    def test_cli_run_help(self):
        from identitybench.cli import build_parser
        parser = build_parser()
        with pytest.raises(SystemExit) as e:
            parser.parse_args(["--help"])
        assert e.value.code == 0

    def test_cli_parse_run(self):
        from identitybench.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["run", "test-bot"])
        assert args.command == "run"
        assert args.identity == "test-bot"
        assert args.mode == "full"

    def test_cli_parse_report(self):
        from identitybench.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["report", "test-bot", "--markdown"])
        assert args.command == "report"
        assert args.markdown is True

    def test_cli_parse_history(self):
        from identitybench.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["history", "test-bot"])
        assert args.command == "history"
        assert args.identity == "test-bot"

    def test_cli_parse_compare_identities(self):
        from identitybench.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["compare", "--identities", "alice", "bob"])
        assert args.command == "compare"
        assert args.identities == ["alice", "bob"]

    def test_cli_parse_compare_last(self):
        from identitybench.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["compare", "--id", "gabe", "--last", "8"])
        assert args.command == "compare"
        assert args.identity_id == "gabe"
        assert args.last == 8
