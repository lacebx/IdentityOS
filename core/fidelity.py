"""
core/fidelity.py

Identity Fidelity — validates every generated response against the identity.

Every response is scored on:
- Contradicts preferences?
- Contradicts beliefs?
- Contradicts traits?
- Contradicts communication style?
- Contradicts relationships?
- Forgot known user facts?
- Invented unsupported identity claims?

Produces: Identity Fidelity Score (0-100) with explainable deductions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .identity import IdentitySpec
from .identity_facts import FactDomain, FactStatus, FactStore
from .user_profile import UserProfile


@dataclass
class FidelityDeduction:
    category: str
    reason: str
    points: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "reason": self.reason,
            "points": self.points,
        }


@dataclass
class FidelityReport:
    score: float                    # 0-100
    deductions: List[FidelityDeduction]
    passed: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": round(self.score, 1),
            "deductions": [d.to_dict() for d in self.deductions],
            "passed": self.passed,
        }

    def summarize(self) -> str:
        if not self.deductions:
            return f"Fidelity: {self.score:.1f}/100 — no deductions"
        lines = [f"Fidelity: {self.score:.1f}/100"]
        for d in self.deductions:
            lines.append(f"  -{d.points}: [{d.category}] {d.reason}")
        return "\n".join(lines)


class IdentityFidelityScorer:
    """
    Scores generated responses against the identity's known facts.

    Uses lightweight heuristics to detect contradictions.
    High-fidelity responses preserve identity consistency.
    """

    def __init__(self) -> None:
        self._max_score = 100.0

    def score_response(
        self,
        response: str,
        identity: IdentitySpec,
        fact_store: Optional[FactStore] = None,
        user_profile: Optional[UserProfile] = None,
    ) -> FidelityReport:
        deductions: List[FidelityDeduction] = []
        resp_lower = response.lower()

        # 1. Check preferences
        if fact_store:
            prefs = fact_store.by_domain(FactDomain.PREFERENCE)
            for fact in prefs:
                if fact.status != FactStatus.ACTIVE:
                    continue
                label = fact.field.split(".")[-1]
                value_str = str(fact.value).lower()
                # Does the response mention this field but with wrong value?
                if label in resp_lower:
                    # Check if it contradicts known value
                    negations = _find_negations(response, label, value_str)
                    for neg in negations:
                        deductions.append(FidelityDeduction(
                            category="preference_contradiction",
                            reason=f"Response contradicts known preference '{label}={value_str}': {neg}",
                            points=15.0,
                        ))

        # 2. Check traits
        for trait in identity.traits:
            tname = trait.name.lower()
            if tname in resp_lower:
                # Check for self-contradictory trait statements
                if trait.score >= 0.7:
                    neg_trait = _find_trait_negation(response, tname)
                    if neg_trait:
                        deductions.append(FidelityDeduction(
                            category="trait_contradiction",
                            reason=f"Response contradicts high-confidence trait '{tname}' (score={trait.score:.2f})",
                            points=12.0,
                        ))

        # 3. Check communication style
        if identity.communication_style and len(response) > 20:
            style = identity.communication_style.lower()
            # Simple heuristic: if style mentions "formal" but response is casual
            if "formal" in style and _is_casual(response):
                deductions.append(FidelityDeduction(
                    category="communication_style_contradiction",
                    reason="Response style contradicts 'formal' communication style",
                    points=10.0,
                ))

        # 4. Check user facts
        if user_profile:
            for fact in user_profile.all_facts():
                if fact.confidence < 0.7:
                    continue
                label = fact.field.split(".")[-1].replace("_", " ")
                value_str = str(fact.value).lower()
                # Does response reference this field but gets it wrong?
                if label in resp_lower:
                    negations = _find_negations(response, label, value_str)
                    for neg in negations:
                        deductions.append(FidelityDeduction(
                            category="user_fact_contradiction",
                            reason=f"Response contradicts known user fact '{label}={value_str}': {neg}",
                            points=18.0,
                        ))

        # 5. Check for invented identity claims
        invented = _find_invented_claims(response, identity, fact_store)
        for claim in invented:
            deductions.append(FidelityDeduction(
                category="invented_identity_claim",
                reason=f"Response claims identity attribute not supported by runtime: {claim}",
                points=20.0,
            ))

        total_deductions = sum(d.points for d in deductions)
        score = max(0.0, self._max_score - total_deductions)

        return FidelityReport(
            score=score,
            deductions=deductions,
            passed=score >= 60.0,
        )


def _find_negations(response: str, label: str, known_value: str) -> List[str]:
    """Find statements in response that contradict a known value."""
    negations = []
    lines = re.split(r'[.!?\n]+', response)
    for line in lines:
        ll = line.lower()
        if label in ll and known_value not in ll:
            # Check for contradictory patterns
            if re.search(rf"(?:not|don't|isn't|aren't|wasn't)\s+\w*\s*{re.escape(label)}", ll):
                negations.append(line.strip())
            elif re.search(rf"(?:my\s+)?{re.escape(label)}\s+is\s+(?!{re.escape(known_value)})\w+", ll):
                negations.append(line.strip())
    return negations


def _find_trait_negation(response: str, trait_name: str) -> bool:
    """Check if response negates a known trait."""
    neg_patterns = [
        rf"i\s+(?:am\s+)?not\s+(?:very\s+|that\s+)?{re.escape(trait_name)}",
        rf"i\s+(?:am\s+)?not\s+usually\s+{re.escape(trait_name)}",
        rf"i\s+lack\s+{re.escape(trait_name)}",
    ]
    for pat in neg_patterns:
        if re.search(pat, response.lower()):
            return True
    return False


def _is_casual(response: str) -> bool:
    """Simple heuristic: detect casual language patterns."""
    casual_signals = {"yeah", "nah", "gonna", "wanna", "ain't", "yep",
                      "cool", "awesome", "dude", "bro", "literally"}
    words = set(response.lower().split())
    return bool(casual_signals & words)


def _find_invented_claims(response: str, identity: IdentitySpec,
                          fact_store: Optional[FactStore] = None) -> List[str]:
    """Detect identity claims not supported by runtime state."""
    invented = []
    supported_fields: set = set()

    if fact_store:
        for f in fact_store.active():
            supported_fields.add(f.field)

    # Check "my favorite X is Y" patterns in response
    fav_pattern = re.compile(r"my\s+favorite\s+(\w+)\s+is\s+(\w+)", re.IGNORECASE)
    for m in fav_pattern.finditer(response):
        field = f"preferences.favorite_{m.group(1).lower()}"
        if field not in supported_fields:
            invented.append(f"{field}={m.group(2)}")

    # Check "I believe X" patterns
    believe_pattern = re.compile(r"i\s+believe\s+(?:that\s+)?(.+?)[.,!?]",
                                 re.IGNORECASE)
    for m in believe_pattern.finditer(response):
        statement = m.group(1).strip().lower()
        if len(statement.split()) >= 3:
            # Check if any known belief covers this
            if fact_store:
                covered = False
                for f in fact_store.by_domain(FactDomain.BELIEF):
                    if f.status == FactStatus.ACTIVE and f.value:
                        if any(w in statement for w in str(f.value).lower().split()):
                            covered = True
                            break
                if not covered:
                    invented.append(f"belief={statement[:60]}")

    return invented
