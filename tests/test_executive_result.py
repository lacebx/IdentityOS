"""
test_executive_result.py — ActionResult canonical schema (Step 1).

Core invariants:
  * EXECUTED ≠ SUCCEEDED.
  * Only an explicit verifier call upgrades EXECUTED → SUCCEEDED.
  * A scaffold that wraps raw capability output NEVER auto-verifies
    even when the underlying result claims success ("completed").
  * Capability failures and exceptions map to FAILED.
  * to_dict/from_dict round-trip losslessly (persistence).
"""

import json

import pytest

from core.executive.result import (
    ActionEvidence,
    ActionResult,
    ActionResultStatus,
)


def test_executed_is_not_succeeded():
    ar = ActionResult(capability="c", skill="c.run").mark_executed(output={"echo": "hi"})
    assert ar.status == ActionResultStatus.EXECUTED
    assert ar.succeeded is False
    assert ar.verified_success is False


def test_only_verifier_upgrades_to_succeeded():
    ar = ActionResult(capability="c", skill="c.run").mark_executed(output={"ok": True})
    ar.mark_succeeded(verified=True)
    assert ar.status == ActionResultStatus.SUCCEEDED
    assert ar.succeeded is True
    assert ar.verified_success is True


def test_mark_succeeded_without_verification_is_not_verified_success():
    ar = ActionResult(capability="c", skill="c.run").mark_executed(output={})
    ar.mark_succeeded(verified=False)
    assert ar.succeeded is True
    assert ar.verified_success is False


def test_failure_transition():
    ar = ActionResult(capability="c", skill="c.run").mark_failed("boom")
    assert ar.status == ActionResultStatus.FAILED
    assert ar.succeeded is False
    assert ar.error == "boom"
    assert ar.status.terminal is True


def test_skipped_transition():
    ar = ActionResult(capability="c", skill="c.run").mark_skipped("no-op")
    assert ar.status == ActionResultStatus.SKIPPED
    assert ar.succeeded is False
    assert ar.status.terminal is True


def test_scaffold_completed_capability_result_never_auto_verifies():
    """A capability can CLAIM completed; the ActionResult stays EXECUTED."""
    ok_result = _FakeResult(
        success=True, capability="speech", action="speech.run",
        data={"capability": "speech", "status": "completed", "detail": "speech executed: x"},
    )
    ar = ActionResult.from_capability_result(ok_result, capability="speech", skill="speech.run")
    assert ar.status == ActionResultStatus.EXECUTED
    assert ar.succeeded is False
    assert ar.verified_success is False
    assert any(e.label == "capture" for e in ar.evidence)


def test_explicit_failure_maps_to_failed():
    bad = _FakeResult(success=False, capability="c", action="c.run", error="exploded")
    ar = ActionResult.from_capability_result(bad, capability="c", skill="c.run")
    assert ar.status == ActionResultStatus.FAILED
    assert "exploded" in (ar.error or "")


def test_round_trip_preserves_all_fields():
    ar = ActionResult(
        capability="calc", skill="calc.add", action_id="ac-1", identity_id="id-1",
        status=ActionResultStatus.EXECUTED, output={"sum": 3}, error=None,
        evidence=[ActionEvidence(label="execute", success=True, detail="ran", data={"n": 1})],
    )
    ar.verified = False
    restored = ActionResult.from_dict(json.loads(json.dumps(ar.to_dict())))
    assert restored.to_dict() == ar.to_dict()


def test_to_capability_result_bridge_never_upgrades():
    ar = ActionResult(capability="c", skill="c.run").mark_executed(output={"x": 1})
    legacy = ar.to_capability_result()
    assert legacy.success is False  # EXECUTED must NOT report success
    ar2 = ActionResult(capability="c", skill="c.run").mark_executed(output={}).mark_succeeded(verified=True)
    assert ar2.to_capability_result().success is True


class _FakeResult:
    def __init__(self, success, capability="", action="", data=None, error=None):
        self.success = success
        self.capability = capability
        self.action = action
        self.data = data
        self.error = error
        self.source = "test"
        self.duration_ms = 1.0