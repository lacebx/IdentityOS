"""Tests for multi-provider coder helpers (no live API calls)."""

from __future__ import annotations

import os

import pytest

from benchmarks.coder_llm import CoderError, _extract_json, _validate_proposal, _coder_order


def test_extract_json_plain() -> None:
    blob = _extract_json('{"hypothesis": "h", "change": "c", "edits": []}')
    assert blob["hypothesis"] == "h"


def test_extract_json_fenced() -> None:
    blob = _extract_json('```json\n{"hypothesis": "h", "change": "c", "edits": []}\n```')
    assert blob["edits"] == []


def test_validate_proposal_requires_keys() -> None:
    with pytest.raises(CoderError):
        _validate_proposal({"hypothesis": "x"})


def test_coder_order_default() -> None:
    os.environ.pop("AUTOPILOT_CODER_ORDER", None)
    assert _coder_order()[0] == "gemini"
    assert "groq" in _coder_order()
    assert "deepseek" in _coder_order()


def test_coder_order_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTOPILOT_CODER_ORDER", "deepseek, groq")
    assert _coder_order() == ["deepseek", "groq"]
