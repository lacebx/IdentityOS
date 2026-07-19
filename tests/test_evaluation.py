"""Tests for core.evaluation module."""

from core.evaluation import (
    EvalCriterion,
    EvalOutcome,
    EvaluationEngine,
    classify_memory_type,
    compute_relevance,
    heuristic_memory_scorer,
    is_worth_remembering,
    register_default_criteria,
)


class TestEvalCriterion:
    def test_score(self):
        criterion = EvalCriterion(
            name="always_pass",
            scorer=lambda inp, out: 0.9,
            threshold=0.5,
        )
        assert criterion.score("x", "y") == 0.9

    def test_disabled_returns_one(self):
        criterion = EvalCriterion(
            name="disabled",
            enabled=False,
            scorer=lambda inp, out: 0.0,
        )
        assert criterion.score("x", "y") == 1.0

    def test_scorer_exception_returns_zero(self):
        criterion = EvalCriterion(
            name="broken",
            scorer=lambda inp, out: 1 / 0,  # type: ignore
        )
        assert criterion.score("x", "y") == 0.0


class TestEvaluationEngine:
    def test_add_and_remove(self):
        engine = EvaluationEngine()
        c = EvalCriterion(name="test")
        engine.add_criterion(c)
        assert len(engine) == 1
        engine.remove_criterion(c.id)
        assert len(engine) == 0

    def test_evaluate_returns_report(self):
        engine = EvaluationEngine()
        engine.add_criterion(EvalCriterion(
            name="check",
            scorer=lambda inp, out: 0.8,
        ))
        report = engine.evaluate(
            identity_id="id1",
            interaction_id="int1",
            input_data="hello",
            output_data="world",
        )
        assert report.identity_id == "id1"
        assert report.interaction_id == "int1"
        assert report.overall_score == 0.8
        assert report.passed is True

    def test_evaluate_with_failure(self):
        engine = EvaluationEngine()
        engine.add_criterion(EvalCriterion(
            name="strict",
            scorer=lambda inp, out: 0.3,
            threshold=0.5,
        ))
        report = engine.evaluate("id1", "int1", "in", "out")
        assert report.passed is False
        assert report.records[0].outcome == EvalOutcome.FAIL

    def test_register_default_criteria(self):
        engine = EvaluationEngine()
        register_default_criteria(engine)
        assert len(engine) == 1


class TestHeuristicClassification:
    def test_classify_memory_type(self):
        assert classify_memory_type("i prefer python", "ok") == "preference"
        assert classify_memory_type("let's go with option a", "sure") == "decision"
        assert classify_memory_type("no, that's wrong", "sorry") == "correction"
        assert classify_memory_type("i shipped the release", "awesome") == "milestone"
        assert classify_memory_type("what's the weather", "sunny") == "general"

    def test_compute_relevance(self):
        assert compute_relevance("correction") > compute_relevance("general")
        assert compute_relevance("unknown") == 1.0

    def test_is_worth_remembering(self):
        assert is_worth_remembering("what is your favorite color", "blue") is True
        assert is_worth_remembering("ok", "fine") is False
        assert is_worth_remembering("hi", "hello") is False

    def test_heuristic_memory_scorer(self):
        assert heuristic_memory_scorer("ok", "fine") == 0.0
        assert heuristic_memory_scorer("i prefer python", "got it") > 0.0
