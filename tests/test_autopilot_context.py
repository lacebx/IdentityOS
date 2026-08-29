"""Tests for autopilot context building (no API calls)."""

from __future__ import annotations

from benchmarks.autopilot_context import build_coder_prompt, failed_tasks


def test_failed_tasks_filters_success() -> None:
    blob = {
        "tasks": [
            {"task_id": "A01", "success": True, "category": "reasoning", "title": "ok"},
            {"task_id": "D04", "success": False, "category": "persistence", "title": "token", "output": "nope"},
        ],
        "summary": {"success": 1, "n": 2, "success_rate": 0.5},
    }
    fails = failed_tasks(blob)
    assert len(fails) == 1
    assert fails[0]["id"] == "D04"


def test_build_coder_prompt_contains_failures() -> None:
    blob = {
        "summary": {"success": 20, "n": 30, "success_rate": 0.67, "hallucination": 0},
        "tasks": [
            {"task_id": "D04", "success": False, "category": "persistence", "title": "token", "output": "77318"},
        ],
    }
    prompt = build_coder_prompt(results=blob, recent_experiments=[])
    assert "D04" in prompt
    assert "allowlisted" in prompt.lower()
