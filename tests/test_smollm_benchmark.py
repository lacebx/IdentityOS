"""Deterministic tests for the SmolLM2 / IDOS comparison harness.

These tests do not call Ollama. They prove the frozen suite, scoring, and
artifact trail exist independently of any model run.
"""

from __future__ import annotations

import json
from pathlib import Path

from benchmarks.artifacts import ArtifactWriter, summarize_tasks, write_comparison_report
from benchmarks.runner import load_suite, select_tasks
from benchmarks.scoring import looks_like_abstention, score_output

SUITE_PATH = Path(__file__).resolve().parents[1] / "benchmarks" / "tasks" / "v0.1.0.json"


class TestFrozenSuite:
    def test_suite_exists_and_is_marked_frozen(self):
        suite = load_suite(SUITE_PATH)
        assert suite["version"] == "0.1.0"
        assert suite["frozen"] is True
        assert suite["model"] == "smollm2:360m-instruct-q4_0"
        assert suite["bare_system_prompt"]

    def test_thirty_tasks_across_six_categories(self):
        suite = load_suite(SUITE_PATH)
        tasks = suite["tasks"]
        assert len(tasks) == 30
        counts = {}
        for task in tasks:
            counts[task["category"]] = counts.get(task["category"], 0) + 1
        assert counts == {
            "reasoning": 5,
            "memory": 5,
            "tools": 5,
            "persistence": 5,
            "long_task": 5,
            "truthfulness": 5,
        }

    def test_persistence_tasks_restart_after_setup(self):
        suite = load_suite(SUITE_PATH)
        persist = [t for t in suite["tasks"] if t["category"] == "persistence"]
        assert persist
        assert all(t.get("restart_after_setup") for t in persist)
        assert all(t.get("setup") for t in persist)

    def test_select_task_and_category(self):
        suite = load_suite(SUITE_PATH)
        only = select_tasks(suite, ["A01"], None, None)
        assert [t["id"] for t in only] == ["A01"]
        tools = select_tasks(suite, None, ["tools"], 2)
        assert len(tools) == 2
        assert all(t["category"] == "tools" for t in tools)

    def test_demo_subset_is_five_frozen_tasks(self):
        suite = load_suite(SUITE_PATH)
        demo = select_tasks(suite, ["A01", "B01", "C01", "D01", "F01"], None, None)
        assert [t["id"] for t in demo] == ["A01", "B01", "C01", "D01", "F01"]
        assert {t["category"] for t in demo} == {
            "reasoning", "memory", "tools", "persistence", "truthfulness",
        }


class TestScoring:
    def test_numeric_success(self):
        result = score_output({"checks": [{"type": "numeric", "value": 411804}]}, "The product is 411804.")
        assert result["success"] is True
        assert result["hallucination"] is False

    def test_numeric_failure(self):
        result = score_output({"checks": [{"type": "numeric", "value": 411804}]}, "I multiplied and got 400000.")
        assert result["success"] is False

    def test_contains_all(self):
        spec = {"checks": [{"type": "contains_all", "needles": ["IdentityOS", "persistent"]}]}
        assert score_output(spec, "IdentityOS is persistent identity infrastructure.")["success"] is True
        assert score_output(spec, "Some other project.")["success"] is False

    def test_file_exists_with_workspace_substitution(self, tmp_path):
        target = tmp_path / "c02.txt"
        target.write_text("IDOS benchmark\n", encoding="utf-8")
        spec = {"checks": [{"type": "file_exists", "path": "{workspace}/c02.txt", "contains": "IDOS benchmark"}]}
        hit = score_output(spec, "I wrote the file.", substitutions={"workspace": str(tmp_path)})
        miss = score_output(spec, "I wrote the file.", substitutions={"workspace": str(tmp_path / "missing")})
        assert hit["success"] is True
        assert miss["success"] is False

    def test_abstain_is_success_for_truthfulness(self):
        spec = {"checks": [{"type": "abstain"}]}
        ok = score_output(spec, "I do not know. I have no information about that.")
        bad = score_output(spec, "You had scrambled eggs and toast.")
        assert ok["success"] is True
        assert ok["hallucination"] is False
        assert bad["success"] is False
        assert bad["hallucination"] is True
        assert looks_like_abstention("I don't know.")

    def test_forbidden_claim_flags_hallucination(self):
        spec = {
            "checks": [
                {"type": "numeric", "value": 4},
                {"type": "forbidden", "needles": ["I don't have the capability to perform mathematical calculations"]},
            ]
        }
        honest = score_output(spec, "4")
        refuse = score_output(
            spec,
            "I'm sorry, I don't have the capability to perform mathematical calculations. The answer is 4.",
        )
        assert honest["success"] is True
        assert refuse["hallucination"] is True
        assert refuse["success"] is False


class TestArtifacts:
    def test_each_interaction_writes_json_and_markdown(self, tmp_path):
        writer = ArtifactWriter(tmp_path / "run")
        writer.set_meta(mode="bare", model="smollm2:360m-instruct-q4_0", benchmark_version="0.1.0")
        writer.record_interaction(
            seq=1,
            task_id="A01",
            mode="bare",
            turn_index=0,
            role="user",
            prompt="What is 2 + 2?",
            output="4",
            latency_s=1.25,
        )
        writer.record_task(
            {
                "task_id": "A01",
                "category": "reasoning",
                "success": True,
                "hallucination": False,
                "latency_s": 1.25,
            }
        )
        writer.finalize()
        files = list((tmp_path / "run" / "interactions").iterdir())
        stems = {p.name for p in files}
        assert "001_A01_bare_t0.json" in stems
        assert "001_A01_bare_t0.md" in stems
        results = json.loads((tmp_path / "run" / "results.json").read_text(encoding="utf-8"))
        assert results["tasks"][0]["success"] is True
        summary = (tmp_path / "run" / "summary.md").read_text(encoding="utf-8")
        assert "A01" in summary
        assert "PASS" in summary

    def test_summary_rates(self):
        stats = summarize_tasks(
            [
                {"category": "memory", "success": True, "hallucination": False, "latency_s": 1.0},
                {"category": "memory", "success": False, "hallucination": True, "latency_s": 3.0},
            ]
        )
        assert stats["n"] == 2
        assert stats["success_rate"] == 0.5
        assert stats["hallucination_rate"] == 0.5
        assert stats["categories"]["memory"]["success"] == 1

    def test_comparison_report_does_not_invent_numbers(self, tmp_path):
        path = tmp_path / "report.md"
        write_comparison_report(
            path,
            bare=None,
            idos=None,
            benchmark_version="0.1.0",
            model="smollm2:360m-instruct-q4_0",
        )
        body = path.read_text(encoding="utf-8")
        assert "78%" not in body
        assert "—" in body
        assert "Do not edit these numbers by hand" in body
