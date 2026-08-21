"""Tests for the IDOS keep/revert ratchet.

No Ollama. The judge must be deterministic and refuse eval hacking.
"""

from __future__ import annotations

from benchmarks.decision import decide
from benchmarks.invariants import (
    check_lock,
    classify_paths,
    experiment_locked_violations,
    load_lock,
    write_lock,
)
from benchmarks.ratchet import next_exp_id, scan_diff_for_hacks


def _run(*, n=30, success=12, hallu=3, latency=10.0, model="smollm2:360m-instruct-q4_0", categories=None):
    if categories is None:
        names = ("reasoning", "memory", "tools", "persistence", "long_task", "truthfulness")
        per = n // len(names)
        extra = n - per * len(names)
        categories = {}
        remaining_s, remaining_h = success, hallu
        for i, name in enumerate(names):
            count = per + (1 if i < extra else 0)
            s = min(count, remaining_s)
            remaining_s -= s
            h = min(count - s, remaining_h) if count > s else 0
            remaining_h -= h
            categories[name] = {
                "n": count,
                "success": s,
                "success_rate": round(s / count, 4) if count else 0.0,
                "hallucination": h,
                "hallucination_rate": round(h / count, 4) if count else 0.0,
                "avg_latency_s": latency,
            }
    tasks = [{"success": i < success, "hallucination": i < hallu, "latency_s": latency, "category": "reasoning"} for i in range(n)]
    return {
        "model": model,
        "tasks": tasks,
        "summary": {
            "n": n,
            "success": success,
            "success_rate": round(success / n, 4) if n else 0.0,
            "hallucination": hallu,
            "hallucination_rate": round(hallu / n, 4) if n else 0.0,
            "avg_latency_s": latency,
            "categories": categories,
        },
    }


class TestInvariants:
    def test_lockfile_matches_current_exam(self):
        write_lock()
        assert check_lock() == []
        lock = load_lock()
        assert lock["model"] == "smollm2:360m-instruct-q4_0"
        assert lock["suite_n"] == 30

    def test_locked_paths_are_not_allowlisted(self):
        classified = classify_paths(
            [
                "benchmarks/tasks/v0.1.0.json",
                "benchmarks/scoring.py",
                "adapters/openai_adapter.py",
                "README.md",
            ]
        )
        assert classified["locked"] == ["benchmarks/tasks/v0.1.0.json", "benchmarks/scoring.py"]
        assert classified["allowed"] == ["adapters/openai_adapter.py"]
        assert classified["other"] == ["README.md"]

    def test_untracked_canonical_exam_is_allowed(self):
        lock = load_lock()
        violations = experiment_locked_violations(
            ["benchmarks/tasks/v0.1.0.json", "benchmarks/scoring.py"],
            tracked=set(),
            lock=lock,
        )
        assert violations == []

    def test_tracked_locked_edit_is_blocked(self):
        violations = experiment_locked_violations(
            ["benchmarks/scoring.py"],
            tracked={"benchmarks/scoring.py"},
            lock=load_lock(),
        )
        assert violations == ["locked file modified during experiment: benchmarks/scoring.py"]


class TestDecision:
    def test_keep_when_success_up_and_guards_hold(self):
        before = _run(success=10, hallu=4, latency=10.0)
        after = _run(success=14, hallu=3, latency=11.0)
        decision = decide(before=before, after=after)
        assert decision.keep is True
        assert decision.verdict == "KEEP"

    def test_revert_on_tie(self):
        blob = _run(success=10, hallu=2, latency=8.0)
        decision = decide(before=blob, after=blob)
        assert decision.keep is False
        assert decision.verdict == "REVERT"
        assert any("did not improve" in r for r in decision.reasons)

    def test_revert_when_hallucination_worsens_even_if_success_up(self):
        before = _run(success=10, hallu=2, latency=10.0)
        after = _run(success=16, hallu=8, latency=10.0)
        decision = decide(before=before, after=after)
        assert decision.keep is False
        assert decision.gates["success_improved"] is True
        assert decision.gates["hallucination_not_worse"] is False

    def test_revert_when_latency_blows_the_budget(self):
        before = _run(success=10, hallu=2, latency=10.0)
        after = _run(success=16, hallu=1, latency=20.0)
        decision = decide(before=before, after=after, latency_budget=1.25)
        assert decision.keep is False
        assert decision.gates["latency_within_budget"] is False

    def test_revert_partial_suite(self):
        before = _run(n=30, success=10)
        after = _run(n=5, success=5)
        decision = decide(before=before, after=after)
        assert decision.keep is False
        assert decision.gates["full_suite"] is False

    def test_revert_model_change(self):
        before = _run(success=10)
        after = _run(success=20, model="llama3.2:latest")
        decision = decide(before=before, after=after)
        assert decision.keep is False
        assert decision.gates["model_frozen"] is False

    def test_revert_category_collapse(self):
        before = _run(success=12, hallu=2, latency=10.0)
        after = _run(success=16, hallu=1, latency=10.0)
        after["summary"]["categories"]["memory"] = {
            "n": 5,
            "success": 0,
            "success_rate": 0.0,
            "hallucination": 0,
            "hallucination_rate": 0.0,
            "avg_latency_s": 10.0,
        }
        before["summary"]["categories"]["memory"] = {
            "n": 5,
            "success": 4,
            "success_rate": 0.8,
            "hallucination": 0,
            "hallucination_rate": 0.0,
            "avg_latency_s": 10.0,
        }
        decision = decide(before=before, after=after, max_category_drop=1)
        assert decision.keep is False
        assert decision.gates["categories_not_collapsed"] is False

    def test_bootstrap_requires_full_frozen_suite(self):
        after = _run(n=30, success=8, hallu=4, latency=12.0)
        decision = decide(before=None, after=after, bootstrap=True)
        assert decision.keep is True
        assert decision.verdict == "BOOTSTRAP"

    def test_bootstrap_refuses_partial(self):
        after = _run(n=5, success=5)
        decision = decide(before=None, after=after, bootstrap=True)
        assert decision.keep is False

    def test_missing_baseline_without_bootstrap_is_revert(self):
        after = _run(success=12)
        decision = decide(before=None, after=after, bootstrap=False)
        assert decision.keep is False
        assert any("bootstrap" in r for r in decision.reasons)


class TestHackScan:
    def test_flags_task_specific_branches(self):
        hits = scan_diff_for_hacks('+            if "837 * 492" in request:\n+                return "411804"\n')
        assert hits

    def test_allows_ordinary_runtime_diff(self):
        hits = scan_diff_for_hacks(
            "+    def generate(self, context, user_input, identity, **kwargs):\n"
            "+        kwargs.pop('tools', None)\n"
        )
        assert hits == []


class TestExpIds:
    def test_next_id_is_zero_padded(self):
        exp_id = next_exp_id()
        assert exp_id.startswith("EXP-")
        assert len(exp_id) == 7
