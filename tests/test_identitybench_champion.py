from __future__ import annotations

from identitybench.champion import assess_observed_champion, select_observed_champion
from identitybench.cli import build_parser
from identitybench.engine import IdentityBench
from identitybench.integrity import evidence_digest
from identitybench.storage import BenchmarkStorage
from identitybench.worlds.base import WorldResult


SIGNATURE = "a" * 64


def _entry(
    response: str,
    request_id: str,
    *,
    check_type: str = "recall_check",
    ground_truth: str = "green",
    should_refuse: bool = False,
) -> dict:
    return {
        "type": check_type,
        "response": response,
        "ground_truth": ground_truth,
        "should_refuse": should_refuse,
        "runtime_evidence": {
            "request_id": request_id,
            "latency_ms": 10.0,
            "prompt_tokens": 20,
            "policy_passed": True,
            "capability_results": [],
        },
    }


def _run(timestamp: str, response: str, *, signature: str = SIGNATURE) -> dict:
    run = {
        "schema_version": 3,
        "evidence_schema_version": 1,
        "timestamp": timestamp,
        "status": "completed",
        "overall_score": 100.0 if response == "green" else 0.0,
        "category_scores": {},
        "worlds": [{
            "world": "Memory",
            "error": None,
            "entries": [_entry(response, f"request-{timestamp}")],
        }],
        "config": {"comparison_signature": signature, "commit_sha": "1" * 40},
    }
    run["evidence_digest"] = evidence_digest(run)
    return run


def test_lower_run_never_replaces_verified_champion():
    high = _run("2026-01-01T00:00:00Z", "green")
    low = _run("2026-01-02T00:00:00Z", "blue")

    assessment, prior = assess_observed_champion(low, [high])

    assert prior is not None
    assert assessment["status"] == "RETAINED"
    assert assessment["candidate_score"] == 0.0
    assert assessment["champion_score"] == 100.0
    assert assessment["promotion_authorized"] is False


def test_higher_run_advances_observed_champion():
    low = _run("2026-01-01T00:00:00Z", "blue")
    high = _run("2026-01-02T00:00:00Z", "green")

    assessment, _ = assess_observed_champion(high, [low])

    assert assessment["status"] == "ADVANCED"
    assert assessment["prior_champion_score"] == 0.0
    assert assessment["champion_score"] == 100.0


def test_tampered_and_incomparable_runs_cannot_become_champion():
    valid = _run("2026-01-01T00:00:00Z", "blue")
    tampered = _run("2026-01-02T00:00:00Z", "green")
    tampered["worlds"][0]["entries"][0]["response"] = "blue"
    other_suite = _run("2026-01-03T00:00:00Z", "green", signature="b" * 64)

    champion = select_observed_champion(
        [valid, tampered, other_suite], signature=SIGNATURE
    )

    assert champion is not None
    assert champion.run is valid
    assert champion.score["overall_score"] == 0.0


def test_truth_guardrail_blocks_an_overall_score_gain():
    champion = _run("2026-01-01T00:00:00Z", "blue")
    champion["worlds"][0]["entries"].extend([
        _entry(
            "I don't know; I will verify",
            "champion-trust",
            check_type="verification_check",
            should_refuse=True,
        ),
        _entry("no", "champion-adaptation", check_type="correction_check"),
    ])
    champion["evidence_digest"] = evidence_digest(champion)

    challenger = _run("2026-01-02T00:00:00Z", "green")
    challenger["worlds"][0]["entries"].extend([
        _entry(
            "definitely true",
            "challenger-trust",
            check_type="verification_check",
            should_refuse=True,
        ),
        _entry(
            "you're right, I stand corrected",
            "challenger-adaptation",
            check_type="correction_check",
        ),
    ])
    challenger["evidence_digest"] = evidence_digest(challenger)

    assessment, _ = assess_observed_champion(challenger, [champion])

    assert assessment["candidate_score"] > assessment["prior_champion_score"]
    assert assessment["status"] == "RETAINED"
    assert any("truthfulness_rate regressed" in item for item in assessment["advancement_blockers"])


def test_compare_defaults_to_all_history_champion(tmp_path, capsys):
    storage = BenchmarkStorage(str(tmp_path))
    storage.save_run("bot", _run("2026-01-01T00:00:00Z", "green"))
    storage.save_run("bot", _run("2026-01-02T00:00:00Z", "blue"))
    storage.save_run("bot", _run("2026-01-03T00:00:00Z", "blue"))
    parser = build_parser()
    args = parser.parse_args([
        "--storage-dir", str(tmp_path), "compare", "--id", "bot", "--last", "2"
    ])

    args.func(args)

    output = capsys.readouterr().out
    assert "verified observed champion baseline" in output
    assert "Overall: 100.0 → 0" in output
    assert "Champion retained at 100" in output


def test_engine_records_initialized_then_retained_champion(tmp_path):
    engine = IdentityBench(identity_id="bot", storage_path=str(tmp_path))
    engine.runtime = type("Runtime", (), {"adapter": None, "capability_registry": None})()

    def result(response: str) -> WorldResult:
        return WorldResult(
            world_name="Memory",
            category_scores={"Memory": 100.0 if response == "green" else 0.0},
            entries=[_entry(response, f"engine-{response}")],
        )

    engine._world_results = [result("green")]
    engine._save_results(0.1)
    first = engine.storage.load_latest_run("bot")
    assert first["champion_baseline"]["status"] == "INITIALIZED"

    engine._world_results = [result("blue")]
    engine._save_results(0.1)
    second = engine.storage.load_latest_run("bot")
    assert second["champion_baseline"]["status"] == "RETAINED"
    assert second["champion_baseline"]["champion_score"] == 100.0
    assert second["diff_vs_champion"]["overall"]["previous"] == 100.0
