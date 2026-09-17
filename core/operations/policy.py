"""
core/operations/policy.py

Authority policy — the hard boundary between autonomous action and escalation.

The operator may act autonomously on low-risk, reversible communication.  It may
*never* autonomously commit the principal to anything consequential.  This module
turns that boundary into an inspectable decision so the engine can mark work as
``AWAITING_HUMAN_AUTHORIZATION`` instead of guessing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable

from .models import ControlState


class Authority(str, Enum):
    AUTONOMOUS = "autonomous"
    AWAITING_HUMAN_AUTHORIZATION = "awaiting_human_authorization"


@dataclass
class AuthorizationDecision:
    authority: Authority
    reason: str
    category: str = ""
    matched_terms: list[str] = field(default_factory=list)

    @property
    def autonomous(self) -> bool:
        return self.authority is Authority.AUTONOMOUS

    @property
    def requires_human(self) -> bool:
        return self.authority is Authority.AWAITING_HUMAN_AUTHORIZATION


# Categories that always require explicit human authorization, regardless of
# operator configuration.  These are commitments that bind the principal.
SENSITIVE_CATEGORIES: dict[str, tuple[str, ...]] = {
    "financial": (
        "invest", "investment", "valuation", "equity", "wire", "transfer funds",
        "payment", "invoice", "price", "pricing", "fee", "budget commit",
        "purchase", "payment terms",
    ),
    "legal": (
        "contract", "agreement", "terms and conditions", "nda", "liability",
        "indemn", "warranty", "legal", "jurisdiction", "binding",
    ),
    "employment": (
        "job offer", "employment", "salary", "compensation", "hire", "hiring",
        "contractor agreement",
    ),
    "access": (
        "credentials", "password", "api key", "token", "ssh key", "repo access",
        "repository access", "admin access", "private key", "secret",
    ),
    "ip": (
        "intellectual property", "assign copyright", "license", "licensing",
        "ownership", "patent", "exclusive", "exclusivity", "transfer rights",
    ),
    "commitment": (
        "we commit", "we guarantee", "we promise", "we will deliver by",
        "deadline commitment", "sla", "service level",
    ),
    "strategy": (
        "strategy change", "pivot", "price change", "acquire", "acquisition",
        "merge", "partnership terms",
    ),
    "privacy": (
        "personal data", "private information", "confidential", "user data",
    ),
}


# Explicit acts that bind the principal or disclose protected material.  These
# are scanned in *every* mode, including routine outreach, because merely asking
# about a funding program is allowed but agreeing to terms is not.
COMMITMENT_PHRASES = (
    "we commit", "we guarantee", "we promise", "we will pay", "we agree to pay",
    "our price is", "we will invest", "we will fund", "wire the funds",
    "transfer funds", "sign the contract", "enter into an agreement",
    "we accept the terms", "binding agreement", "here is the api key",
    "here is the password", "the password is", "the token is", "ssh key is",
    "we assign copyright", "transfer ownership", "grant exclusive",
    "exclusive license", "we offer you the position", "salary of",
    "we will deliver by", "service level agreement",
)


class AuthorityPolicy:
    """Decides whether an action is autonomous or must be escalated."""

    def __init__(self, controls: ControlState | None = None) -> None:
        self._controls = controls or ControlState()

    def update_controls(self, controls: ControlState) -> None:
        self._controls = controls

    def evaluate(
        self,
        action: str,
        *,
        category: str = "",
        content: str = "",
        mode: str = "content",
    ) -> AuthorizationDecision:
        """Return the authority decision for an action.

        ``mode="content"`` scans the full text for any consequential topic
        (used when replying, where the subject matter itself may require care).
        ``mode="commitment"`` scans only explicit binding/disclosure phrases
        (used for outbound outreach, where asking about money or programs is
        permitted but committing is not).
        """
        haystack = f"{action}\n{category}\n{content}".lower()

        if category and category.lower() in {
            c.lower() for c in self._controls.require_approval_categories
        }:
            return AuthorizationDecision(
                Authority.AWAITING_HUMAN_AUTHORIZATION,
                f"category '{category}' is set to require human approval",
                category=category,
            )

        commitment_matches = [p for p in COMMITMENT_PHRASES if p in haystack]
        if commitment_matches:
            return AuthorizationDecision(
                Authority.AWAITING_HUMAN_AUTHORIZATION,
                "message makes a binding commitment or discloses protected material",
                category=category,
                matched_terms=sorted(set(commitment_matches)),
            )

        if mode == "commitment":
            return AuthorizationDecision(
                Authority.AUTONOMOUS,
                "outreach asks about a program without committing the principal",
                category=category,
            )

        matched: list[str] = []
        matched_categories: list[str] = []
        for cat, terms in SENSITIVE_CATEGORIES.items():
            for term in terms:
                if term in haystack:
                    matched.append(term)
                    matched_categories.append(cat)
        if matched:
            return AuthorizationDecision(
                Authority.AWAITING_HUMAN_AUTHORIZATION,
                "message touches consequential commitments: "
                + ", ".join(sorted(set(matched_categories))),
                category=matched_categories[0],
                matched_terms=sorted(set(matched)),
            )

        return AuthorizationDecision(
            Authority.AUTONOMOUS,
            "low-risk communication within delegated authority",
            category=category,
        )


# Intent classes a reply can fall into.  Conversational/reversible intents are
# autonomous; the rest are escalated.
CONVERSATIONAL_INTENTS = {
    "question": "answered from verified project facts",
    "thanks": "acknowledgement",
    "scheduling": "proposing times",
    "documentation_request": "sharing public links",
    "intro_request": "routing to a public link",
    "interest": "expressing appreciation and offering next step",
    "decline": "acknowledging decision and closing respectfully",
}


def is_conversational(intent: str) -> bool:
    return intent in CONVERSATIONAL_INTENTS
