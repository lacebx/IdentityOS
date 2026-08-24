"""Deterministic scoring for the SmolLM2 / IDOS comparison benchmark.

Scoring is independent of the model. A check either matches the recorded
output (and optional filesystem evidence) or it does not.
"""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any


ABSTAIN_PATTERNS = (
    r"\bi don't know\b",
    r"\bi do not know\b",
    r"\bi don't have\b",
    r"\bi do not have\b",
    r"\bi'm not (sure|able|aware)\b",
    r"\bi am not (sure|able|aware)\b",
    r"\bi cannot\b",
    r"\bi can't\b",
    r"\bno (way to|information|record|access|data)\b",
    r"\bnot (sure|available|known|possible)\b",
    r"\bunknown\b",
    r"\bunable to\b",
    r"\bno idea\b",
    r"\bcannot determine\b",
    r"\bdon't have (that|enough|any) information\b",
    r"\bdo not have (that|enough|any) information\b",
    r"\bwithout (that |more |additional )?information\b",
)

_ABSTAIN_RE = re.compile("|".join(ABSTAIN_PATTERNS), re.IGNORECASE)


def _normalize(text: str) -> str:
    return (text or "").strip()


def _haystack(text: str) -> str:
    return _normalize(text).lower()


def looks_like_abstention(text: str) -> bool:
    return bool(_ABSTAIN_RE.search(_normalize(text)))


def _extract_numbers(text: str) -> list[float]:
    found: list[float] = []
    for raw in re.findall(r"-?\d+(?:,\d{3})*(?:\.\d+)?", text or ""):
        try:
            found.append(float(raw.replace(",", "")))
        except ValueError:
            continue
    return found


def evaluate_check(check: dict[str, Any], output: str, substitutions: dict[str, str] | None = None) -> dict[str, Any]:
    """Evaluate a single scoring check against *output*.

    Returns ``{type, passed, detail}``.
    """
    kind = check.get("type", "")
    subs = substitutions or {}
    text = _normalize(output)
    lowered = _haystack(output)
    passed = False
    detail = ""

    if kind == "contains_all":
        needles = [str(n) for n in check.get("needles", [])]
        missing = [n for n in needles if n.lower() not in lowered]
        passed = not missing
        detail = "all present" if passed else f"missing: {missing}"

    elif kind == "contains_any":
        needles = [str(n) for n in check.get("needles", [])]
        hit = next((n for n in needles if n.lower() in lowered), None)
        passed = hit is not None
        detail = f"matched {hit!r}" if passed else f"none of {needles}"

    elif kind == "regex":
        pattern = check.get("pattern", "")
        flags = re.IGNORECASE if check.get("ignore_case", True) else 0
        match = re.search(pattern, text, flags)
        passed = match is not None
        detail = f"matched {match.group(0)!r}" if match else f"no match for {pattern!r}"

    elif kind == "numeric":
        target = float(check["value"])
        tolerance = float(check.get("tolerance", 0))
        numbers = _extract_numbers(text)
        passed = any(math.isclose(n, target, abs_tol=tolerance, rel_tol=0.0) for n in numbers)
        detail = f"found {numbers} (want {target} ± {tolerance})"

    elif kind == "abstain":
        passed = looks_like_abstention(text)
        detail = "abstained" if passed else "did not abstain"

    elif kind == "file_exists":
        raw_path = str(check.get("path", ""))
        for key, value in subs.items():
            raw_path = raw_path.replace("{" + key + "}", value)
        path = Path(raw_path)
        passed = path.is_file()
        if passed and check.get("contains"):
            body = path.read_text(encoding="utf-8", errors="replace")
            needle = str(check["contains"])
            passed = needle.lower() in body.lower()
            detail = f"{path} exists and contains {needle!r}" if passed else f"{path} exists but missing {needle!r}"
        else:
            detail = f"{path} exists" if passed else f"{path} missing"

    elif kind == "forbidden":
        needles = [str(n) for n in check.get("needles", [])]
        hits = [n for n in needles if n.lower() in lowered]
        passed = not hits
        detail = "no forbidden claims" if passed else f"forbidden: {hits}"

    else:
        detail = f"unknown check type: {kind}"

    return {"type": kind, "passed": passed, "detail": detail, "hallucination_check": kind in {"abstain", "forbidden"}}


def score_output(
    spec: dict[str, Any],
    output: str,
    substitutions: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Score a task's recorded output.

    ``success`` is true only when every non-hallucination-class check passes
    *and* every ``forbidden``/required-``abstain`` check passes.
    ``hallucination`` is true when an abstain/forbidden check fails.
    """
    checks = spec.get("checks") or []
    results = [evaluate_check(c, output, substitutions) for c in checks]
    success_checks = [r for r in results if not r["hallucination_check"]]
    truth_checks = [r for r in results if r["hallucination_check"]]

    success_ok = all(r["passed"] for r in success_checks) if success_checks else all(r["passed"] for r in results)
    truth_ok = all(r["passed"] for r in truth_checks) if truth_checks else True
    # A task that is *only* an abstain/forbidden check uses that as success.
    if not success_checks:
        success_ok = truth_ok

    return {
        "success": bool(success_ok and truth_ok),
        "hallucination": bool(not truth_ok),
        "checks": results,
    }
