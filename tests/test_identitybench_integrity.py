from __future__ import annotations

import json

import pytest

from identitybench.cli import build_parser
from identitybench.integrity import (
    IntegrityError,
    append_ledger_record,
    build_trial_plan,
    canonical_digest,
    evaluate_promotion,
    evidence_digest,
    rescore_run,
    score_pair,
    verify_ledger,
    verify_trial_reveal,
)


BASE_SHA = "1" * 40
CANDIDATE_SHA = "2" * 40
EVALUATOR_DIGEST = "a" * 64
PROTECTED_DIGEST = "b" * 64


def _entry(response: str, request_id: str, *, latency: float = 100.0, prompt: int = 200):
    return {
        "tick": 1,
        "type": "recall_check",
        "user_input": "What color?",
        "response": response,
        "ground_truth": "green",
        "expected_hints": ["green"],
        "should_refuse": False,
        "runtime_evidence": {
            "request_id": request_id,
            "latency_ms": latency,
            "prompt_tokens": prompt,
            "policy_passed": True,
            "capability_results": [],
        },
    }


def _run(
    *,
    side: str,
    seed: int,
    commitment: str,
    trial_index: int,
    response: str,
    request_id: str,
    claimed_score: float = 0.0,
    suite_digest: str = EVALUATOR_DIGEST,
    latency: float = 100.0,
    prompt: int = 200,
):
    commit_sha = BASE_SHA if side == "base" else CANDIDATE_SHA
    world = {
        "world": "Memory",
        "error": None,
        "entries": [_entry(response, request_id, latency=latency, prompt=prompt)],
        "overall_score": claimed_score,
        "metrics": {"recall_accuracy": claimed_score},
        "category_scores": {"Memory": claimed_score},
    }
    run = {
        "schema_version": 3,
        "evidence_schema_version": 1,
        "status": "completed",
        "overall_score": claimed_score,
        "category_scores": {"Memory": claimed_score},
        "worlds": [world],
        "config": {
            "seed": seed,
            "seed_commitment": commitment,
            "trial_index": trial_index,
            "commit_sha": commit_sha,
            "worlds": ["Memory"],
            "adapter": {"providers": [{"adapter": "Fake", "model": "fixed"}]},
            "request_interval_seconds": 0.0,
            "context_tokens": 1200,
            "response_tokens": 256,
            "tool_result_chars": 1200,
            "tools_per_request": 3,
            "tool_rounds": 1,
            "cooldown_wait_seconds": 30.0,
            "suite_fingerprint": suite_digest,
            "evaluator_digest": EVALUATOR_DIGEST,
            "protected_suite_digest": PROTECTED_DIGEST,
            "lane": "protected",
        },
    }
    run["evidence_digest"] = evidence_digest(run)
    return run


def _plans(trials: int = 3):
    return build_trial_plan(
        base_sha=BASE_SHA,
        candidate_sha=CANDIDATE_SHA,
        window_id="2026-09-02T18:00Z",
        beacon="github-run-123:attempt-1",
        evaluator_digest=EVALUATOR_DIGEST,
        trial_count=trials,
    )


def _pair(revealed_trial, index: int):
    trial = {**revealed_trial, "base_sha": BASE_SHA, "candidate_sha": CANDIDATE_SHA}
    base = _run(
        side="base",
        seed=trial["seed"],
        commitment=trial["seed_commitment"],
        trial_index=index,
        response="blue",
        request_id=f"base-{index}",
    )
    candidate = _run(
        side="candidate",
        seed=trial["seed"],
        commitment=trial["seed_commitment"],
        trial_index=index,
        response="green",
        request_id=f"candidate-{index}",
    )
    return score_pair(base, candidate, trial, expected_evaluator_digest=EVALUATOR_DIGEST)


def test_trial_seed_plan_is_deterministic_and_verifiable():
    commitments, reveal = _plans()
    repeated_commitments, repeated_reveal = _plans()

    assert commitments == repeated_commitments
    assert reveal == repeated_reveal
    assert "seed" not in commitments["trials"][0]
    assert len({trial["seed"] for trial in reveal["trials"]}) == 3
    verify_trial_reveal(commitments, reveal)


def test_trial_reveal_rejects_seed_substitution():
    commitments, reveal = _plans()
    reveal["trials"][0]["seed"] += 1

    with pytest.raises(IntegrityError, match="does not match commitment"):
        verify_trial_reveal(commitments, reveal)


def test_rescore_ignores_candidate_claimed_score():
    _, reveal = _plans(1)
    trial = reveal["trials"][0]
    run = _run(
        side="candidate",
        seed=trial["seed"],
        commitment=trial["seed_commitment"],
        trial_index=1,
        response="blue",
        request_id="candidate-1",
        claimed_score=100.0,
    )

    score = rescore_run(run)

    assert score["overall_score"] == 0.0
    assert score["claimed_score_matches"] is False


def test_rescore_rejects_evidence_modified_after_digest():
    _, reveal = _plans(1)
    trial = reveal["trials"][0]
    run = _run(
        side="candidate",
        seed=trial["seed"],
        commitment=trial["seed_commitment"],
        trial_index=1,
        response="blue",
        request_id="candidate-1",
    )
    run["worlds"][0]["entries"][0]["response"] = "green"

    with pytest.raises(IntegrityError, match="evidence digest"):
        rescore_run(run)


def test_pair_rejects_candidate_modified_benchmark_suite():
    _, reveal = _plans(1)
    trial = {**reveal["trials"][0], "base_sha": BASE_SHA, "candidate_sha": CANDIDATE_SHA}
    base = _run(
        side="base",
        seed=trial["seed"],
        commitment=trial["seed_commitment"],
        trial_index=1,
        response="blue",
        request_id="base-1",
    )
    candidate = _run(
        side="candidate",
        seed=trial["seed"],
        commitment=trial["seed_commitment"],
        trial_index=1,
        response="green",
        request_id="candidate-1",
        suite_digest="c" * 64,
    )

    result = score_pair(base, candidate, trial, expected_evaluator_digest=EVALUATOR_DIGEST)

    assert result["eligible"] is False
    assert any("suite differs" in reason for reason in result["ineligibility_reasons"])


def test_public_lane_can_never_authorize_promotion():
    _, reveal = _plans()
    pairs = [_pair(trial, index) for index, trial in enumerate(reveal["trials"], 1)]
    for pair in pairs:
        pair["lane"] = "public"

    decision = evaluate_promotion(
        pairs,
        protected=False,
        attestation_verified=True,
        provider_receipts_verified=True,
    )

    assert decision["verdict"] == "ADVISORY"
    assert decision["promotion_authorized"] is False


def test_protected_gate_promotes_only_complete_attested_paired_improvement():
    _, reveal = _plans()
    pairs = [_pair(trial, index) for index, trial in enumerate(reveal["trials"], 1)]

    decision = evaluate_promotion(
        pairs,
        protected=True,
        attestation_verified=True,
        provider_receipts_verified=True,
    )

    assert decision["verdict"] == "PROMOTE"
    assert decision["promotion_authorized"] is True
    assert decision["median_paired_delta"] == 100.0
    assert decision["confidence_interval_95"][0] > 0
    assert all(gate["passed"] for gate in decision["gates"])


@pytest.mark.parametrize("attested,receipts", [(False, True), (True, False), (False, False)])
def test_protected_gate_fails_closed_without_external_evidence(attested, receipts):
    _, reveal = _plans()
    pairs = [_pair(trial, index) for index, trial in enumerate(reveal["trials"], 1)]

    decision = evaluate_promotion(
        pairs,
        protected=True,
        attestation_verified=attested,
        provider_receipts_verified=receipts,
    )

    assert decision["verdict"] == "REJECT"
    assert decision["promotion_authorized"] is False


def test_gate_rejects_missing_trial_instead_of_cherry_picking_best_runs():
    _, reveal = _plans()
    pairs = [_pair(trial, index) for index, trial in enumerate(reveal["trials"][:2], 1)]

    decision = evaluate_promotion(
        pairs,
        protected=True,
        attestation_verified=True,
        provider_receipts_verified=True,
    )

    assert decision["verdict"] == "REJECT"
    attempts_gate = next(gate for gate in decision["gates"] if gate["name"] == "all_attempts_present")
    assert attempts_gate["passed"] is False


def test_hash_chain_ledger_detects_mutation(tmp_path):
    ledger = tmp_path / "integrity-ledger.jsonl"
    first = append_ledger_record(ledger, {"verdict": "ADVISORY", "run": 1})
    second = append_ledger_record(ledger, {"verdict": "REJECT", "run": 2})

    records = verify_ledger(ledger)
    assert [record["record_hash"] for record in records] == [first["record_hash"], second["record_hash"]]

    raw = [json.loads(line) for line in ledger.read_text().splitlines()]
    raw[0]["payload"]["verdict"] = "PROMOTE"
    ledger.write_text("\n".join(json.dumps(item) for item in raw) + "\n")
    with pytest.raises(IntegrityError, match="payload digest"):
        verify_ledger(ledger)


def test_canonical_digest_is_order_independent_for_objects():
    assert canonical_digest({"b": 2, "a": 1}) == canonical_digest({"a": 1, "b": 2})


def test_integrity_cli_round_trip_emits_promotable_decision_and_ledger(tmp_path, monkeypatch):
    commitments, reveal = _plans()
    commitments_path = tmp_path / "commitments.json"
    reveal_path = tmp_path / "reveal.json"
    commitments_path.write_text(json.dumps(commitments))
    reveal_path.write_text(json.dumps(reveal))
    pairs_dir = tmp_path / "pairs"
    for index, revealed_trial in enumerate(reveal["trials"], 1):
        trial_dir = pairs_dir / f"trial-{index}"
        trial_dir.mkdir(parents=True)
        trial = {
            **revealed_trial,
            "base_sha": BASE_SHA,
            "candidate_sha": CANDIDATE_SHA,
        }
        base = _run(
            side="base",
            seed=trial["seed"],
            commitment=trial["seed_commitment"],
            trial_index=index,
            response="blue",
            request_id=f"base-{index}",
        )
        candidate = _run(
            side="candidate",
            seed=trial["seed"],
            commitment=trial["seed_commitment"],
            trial_index=index,
            response="green",
            request_id=f"candidate-{index}",
        )
        (trial_dir / "base.json").write_text(json.dumps(base))
        (trial_dir / "candidate.json").write_text(json.dumps(candidate))

    output = tmp_path / "decision.json"
    summary = tmp_path / "decision.md"
    ledger = tmp_path / "ledger.jsonl"
    parser = build_parser()
    args = parser.parse_args([
        "integrity",
        "gate",
        "--commitments", str(commitments_path),
        "--reveal", str(reveal_path),
        "--pairs-dir", str(pairs_dir),
        "--output", str(output),
        "--summary", str(summary),
        "--ledger", str(ledger),
        "--protected",
        "--evidence-attestations-verified",
        "--provider-receipts-verified",
        "--enforce",
    ])
    monkeypatch.setattr("identitybench.cli.suite_fingerprint", lambda: EVALUATOR_DIGEST)

    args.func(args)

    decision = json.loads(output.read_text())
    assert decision["verdict"] == "PROMOTE"
    assert decision["promotion_authorized"] is True
    assert "Promotion authorized: **true**" in summary.read_text()
    assert len(verify_ledger(ledger)) == 1


def test_integrity_trial_cli_verifies_reveal_before_writing_runner_outputs(tmp_path):
    commitments, reveal = _plans(1)
    commitments_path = tmp_path / "commitments.json"
    reveal_path = tmp_path / "reveal.json"
    outputs_path = tmp_path / "github-output.txt"
    commitments_path.write_text(json.dumps(commitments))
    reveal_path.write_text(json.dumps(reveal))
    parser = build_parser()
    args = parser.parse_args([
        "integrity",
        "trial",
        "--commitments", str(commitments_path),
        "--reveal", str(reveal_path),
        "--trial-index", "1",
        "--github-output", str(outputs_path),
    ])

    args.func(args)

    outputs = outputs_path.read_text()
    assert f"seed={reveal['trials'][0]['seed']}" in outputs
    assert f"seed_commitment={reveal['trials'][0]['seed_commitment']}" in outputs
