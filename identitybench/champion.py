"""Monotonic, evidence-backed observational baselines for IdentityBench.

The observed champion is a diagnostic high-water mark.  It is intentionally
separate from promotion authority: only the protected paired integrity gate
may authorize a release or merge decision.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Optional

from identitybench.integrity import IntegrityError, rescore_run
from identitybench.provenance import comparison_signature


CHAMPION_SCHEMA_VERSION = 1
MAX_WORLD_REGRESSION = 5.0
GUARDRAIL_METRICS = (
    "truthfulness_rate",
    "verification_rate",
    "memory_leakage",
    "responsibility_leakage",
)


@dataclass(frozen=True)
class Champion:
    """A run plus its independently recomputed score."""

    run: Mapping[str, Any]
    score: Mapping[str, Any]


def _verified_candidate(run: Mapping[str, Any]) -> Champion:
    signature = comparison_signature(dict(run))
    if signature is None:
        raise IntegrityError("run lacks a comparison signature")
    score = rescore_run(run)
    if score["policy_failures"]:
        raise IntegrityError("run contains policy failures")
    return Champion(run=run, score=score)


def _advancement_blockers(champion: Champion, challenger: Champion) -> list[str]:
    blockers: list[str] = []
    champion_score = float(champion.score["overall_score"])
    challenger_score = float(challenger.score["overall_score"])
    if challenger_score <= champion_score:
        blockers.append(
            f"overall score {challenger_score:g} did not exceed {champion_score:g}"
        )

    champion_metrics = champion.score.get("metrics", {})
    challenger_metrics = challenger.score.get("metrics", {})
    for metric in GUARDRAIL_METRICS:
        if metric not in champion_metrics or metric not in challenger_metrics:
            continue
        previous = float(champion_metrics[metric])
        current = float(challenger_metrics[metric])
        if current < previous:
            blockers.append(
                f"guardrail {metric} regressed from {previous:g} to {current:g}"
            )

    champion_worlds = champion.score.get("world_scores", {})
    challenger_worlds = challenger.score.get("world_scores", {})
    for world, previous_value in champion_worlds.items():
        if world not in challenger_worlds:
            blockers.append(f"world {world} is missing from challenger evidence")
            continue
        previous = float(previous_value)
        current = float(challenger_worlds[world])
        if current < previous - MAX_WORLD_REGRESSION:
            blockers.append(
                f"world {world} regressed from {previous:g} to {current:g}"
            )
    return blockers


def select_observed_champion(
    runs: Iterable[Mapping[str, Any]],
    *,
    signature: Optional[str] = None,
) -> Optional[Champion]:
    """Replay eligible runs chronologically and return the monotonic champion.

    Invalid, failed, policy-violating, and incomparable runs are ignored.  A
    challenger advances only when its independently recomputed overall score is
    higher and the truth/isolation and per-world guardrails remain intact.
    """

    candidates: list[Champion] = []
    for run in runs:
        if signature is not None and comparison_signature(dict(run)) != signature:
            continue
        try:
            candidates.append(_verified_candidate(run))
        except (IntegrityError, TypeError, ValueError):
            continue

    candidates.sort(
        key=lambda item: (
            str(item.run.get("timestamp", "")),
            str(item.score.get("evidence_digest", "")),
        )
    )
    champion: Optional[Champion] = None
    for challenger in candidates:
        if champion is None or not _advancement_blockers(champion, challenger):
            champion = challenger
    return champion


def assess_observed_champion(
    candidate_run: Mapping[str, Any],
    prior_runs: Iterable[Mapping[str, Any]],
) -> tuple[dict[str, Any], Optional[Champion]]:
    """Assess one run without allowing a low result to replace the champion."""

    signature = comparison_signature(dict(candidate_run))
    prior = select_observed_champion(prior_runs, signature=signature)
    try:
        candidate = _verified_candidate(candidate_run)
    except (IntegrityError, TypeError, ValueError) as exc:
        assessment = {
            "schema_version": CHAMPION_SCHEMA_VERSION,
            "kind": "verified_observed_champion",
            "authority": "advisory_only",
            "promotion_authorized": False,
            "comparison_signature": signature,
            "status": "INELIGIBLE",
            "reason": str(exc),
            "champion_score": (
                prior.score["overall_score"] if prior is not None else None
            ),
            "champion_evidence_digest": (
                prior.score["evidence_digest"] if prior is not None else None
            ),
            "champion_timestamp": (
                prior.run.get("timestamp") if prior is not None else None
            ),
            "champion_commit_sha": (
                prior.run.get("config", {}).get("commit_sha")
                if prior is not None else None
            ),
        }
        return assessment, prior

    candidate_score = float(candidate.score["overall_score"])
    if prior is None:
        resulting = candidate
        status = "INITIALIZED"
        blockers: list[str] = []
        prior_score = None
    else:
        blockers = _advancement_blockers(prior, candidate)
        if blockers:
            resulting = prior
            status = "RETAINED"
        else:
            resulting = candidate
            status = "ADVANCED"
        prior_score = float(prior.score["overall_score"])

    assessment = {
        "schema_version": CHAMPION_SCHEMA_VERSION,
        "kind": "verified_observed_champion",
        "authority": "advisory_only",
        "promotion_authorized": False,
        "comparison_signature": signature,
        "status": status,
        "candidate_score": candidate_score,
        "candidate_evidence_digest": candidate.score["evidence_digest"],
        "candidate_commit_sha": candidate.run.get("config", {}).get("commit_sha"),
        "prior_champion_score": prior_score,
        "prior_champion_evidence_digest": (
            prior.score["evidence_digest"] if prior is not None else None
        ),
        "champion_score": float(resulting.score["overall_score"]),
        "champion_evidence_digest": resulting.score["evidence_digest"],
        "champion_timestamp": resulting.run.get("timestamp"),
        "champion_commit_sha": resulting.run.get("config", {}).get("commit_sha"),
        "delta_vs_prior_champion": (
            round(candidate_score - prior_score, 3) if prior_score is not None else 0.0
        ),
        "advancement_blockers": blockers,
        "next_score_must_exceed": float(resulting.score["overall_score"]),
    }
    return assessment, prior


def rescored_run(champion: Champion) -> dict[str, Any]:
    """Return a report-safe copy whose score fields come from raw evidence."""

    normalized = dict(champion.run)
    normalized["overall_score"] = champion.score["overall_score"]
    normalized["category_scores"] = dict(champion.score["category_scores"])
    return normalized
