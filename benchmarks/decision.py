"""KEEP / REVERT decision for the IDOS capability ratchet.

This is the judge. It is intentionally boring. If the new run is not
strictly more useful on the frozen suite, the change does not stay.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from benchmarks.artifacts import summarize_tasks

DEFAULT_LATENCY_BUDGET = 1.25
DEFAULT_MAX_CATEGORY_DROP = 1  # absolute successful-task count


@dataclass
class Decision:
    keep: bool
    verdict: str  # KEEP | REVERT | BOOTSTRAP
    reasons: list[str] = field(default_factory=list)
    gates: dict[str, bool] = field(default_factory=dict)
    before: dict[str, Any] = field(default_factory=dict)
    after: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "keep": self.keep,
            "verdict": self.verdict,
            "reasons": list(self.reasons),
            "gates": dict(self.gates),
            "before": self.before,
            "after": self.after,
        }


def _stats(blob: dict[str, Any] | None) -> dict[str, Any]:
    if not blob:
        return summarize_tasks([])
    if "summary" in blob and isinstance(blob["summary"], dict) and "success_rate" in blob["summary"]:
        return blob["summary"]
    return summarize_tasks(blob.get("tasks") or [])


def _fail(gates: dict[str, bool], reasons: list[str], before: dict, after: dict) -> Decision:
    return Decision(
        keep=False,
        verdict="REVERT",
        reasons=reasons,
        gates=gates,
        before=before,
        after=after,
    )


def decide(
    *,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
    expected_n: int = 30,
    expected_model: str = "smollm2:360m-instruct-q4_0",
    latency_budget: float = DEFAULT_LATENCY_BUDGET,
    max_category_drop: int = DEFAULT_MAX_CATEGORY_DROP,
    bootstrap: bool = False,
) -> Decision:
    """Compare two IDOS result blobs.

    KEEP requires every gate to pass. A tie is a REVERT.
    ``bootstrap`` is only for the first frozen IDOS baseline.
    """
    after = after or {}
    after_stats = _stats(after)
    after_model = after.get("model") or ""
    after_n = int(after_stats.get("n") or 0)

    gates = {
        "has_after": bool(after.get("tasks")),
        "full_suite": after_n == expected_n,
        "model_frozen": after_model == expected_model if after_model else False,
        "success_improved": False,
        "hallucination_not_worse": False,
        "latency_within_budget": False,
        "categories_not_collapsed": False,
    }
    reasons: list[str] = []

    if not gates["has_after"]:
        return _fail(gates, ["no IDOS results to judge"], _stats(before), after_stats)
    if not gates["full_suite"]:
        reasons.append(f"partial suite: {after_n}/{expected_n} tasks (ratchet requires the frozen full suite)")
    if after_model and after_model != expected_model:
        reasons.append(f"model changed: {after_model!r} != locked {expected_model!r}")
    elif not after_model:
        reasons.append("after-run did not record a model id")

    if bootstrap:
        gates["success_improved"] = True
        gates["hallucination_not_worse"] = True
        gates["latency_within_budget"] = True
        gates["categories_not_collapsed"] = True
        keep = all(gates.values())
        if keep:
            return Decision(
                keep=True,
                verdict="BOOTSTRAP",
                reasons=["first IDOS baseline; no previous IDOS score to beat"],
                gates=gates,
                before=_stats(before),
                after=after_stats,
            )
        return _fail(gates, reasons or ["bootstrap failed gates"], _stats(before), after_stats)

    if not before or not (before.get("tasks") or before.get("summary")):
        return _fail(
            gates,
            reasons + ["no frozen IDOS baseline; run with --bootstrap once before ratcheting"],
            _stats(before),
            after_stats,
        )

    before_stats = _stats(before)
    before_n = int(before_stats.get("n") or 0)
    if before_n != expected_n:
        reasons.append(f"frozen IDOS baseline is partial ({before_n}/{expected_n}); refuse to ratchet on a broken baseline")
        return _fail(gates, reasons, before_stats, after_stats)

    before_success = float(before_stats.get("success_rate") or 0.0)
    after_success = float(after_stats.get("success_rate") or 0.0)
    gates["success_improved"] = after_success > before_success
    if not gates["success_improved"]:
        reasons.append(
            f"success did not improve: {before_success:.1%} → {after_success:.1%}"
        )

    before_hallu = float(before_stats.get("hallucination_rate") or 0.0)
    after_hallu = float(after_stats.get("hallucination_rate") or 0.0)
    gates["hallucination_not_worse"] = after_hallu <= before_hallu + 1e-12
    if not gates["hallucination_not_worse"]:
        reasons.append(
            f"hallucination got worse: {before_hallu:.1%} → {after_hallu:.1%}"
        )

    before_lat = before_stats.get("avg_latency_s")
    after_lat = after_stats.get("avg_latency_s")
    if before_lat is None or after_lat is None:
        gates["latency_within_budget"] = before_lat is None and after_lat is None
        if not gates["latency_within_budget"]:
            reasons.append("latency missing from before or after summary")
    else:
        limit = float(before_lat) * float(latency_budget)
        gates["latency_within_budget"] = float(after_lat) <= limit + 1e-9
        if not gates["latency_within_budget"]:
            reasons.append(
                f"latency exceeded budget: {after_lat}s > {limit:.4f}s "
                f"({latency_budget}× previous {before_lat}s)"
            )

    cat_reasons, cat_ok = _category_gate(
        before_stats.get("categories") or {},
        after_stats.get("categories") or {},
        max_drop=max_category_drop,
    )
    gates["categories_not_collapsed"] = cat_ok
    reasons.extend(cat_reasons)

    keep = all(gates.values())
    if keep:
        reasons = [
            f"success {before_success:.1%} → {after_success:.1%}",
            f"hallucination {before_hallu:.1%} → {after_hallu:.1%}",
            f"latency {before_lat}s → {after_lat}s",
        ]
        return Decision(
            keep=True,
            verdict="KEEP",
            reasons=reasons,
            gates=gates,
            before=before_stats,
            after=after_stats,
        )
    return _fail(gates, reasons, before_stats, after_stats)


def _category_gate(
    before_cats: dict[str, Any],
    after_cats: dict[str, Any],
    *,
    max_drop: int,
) -> tuple[list[str], bool]:
    reasons: list[str] = []
    ok = True
    for name, before_bucket in before_cats.items():
        after_bucket = after_cats.get(name)
        if not after_bucket:
            ok = False
            reasons.append(f"category {name} missing from after-run")
            continue
        drop = int(before_bucket.get("success") or 0) - int(after_bucket.get("success") or 0)
        if drop > max_drop:
            ok = False
            reasons.append(
                f"category {name} dropped {drop} successful tasks "
                f"({before_bucket.get('success')}/{before_bucket.get('n')} → "
                f"{after_bucket.get('success')}/{after_bucket.get('n')}); "
                f"max allowed drop is {max_drop}"
            )
    return reasons, ok
