"""Unit tests for Remember:-directive extraction and recall/abstain surfacing."""

from __future__ import annotations

import tempfile

import pytest

from core.evaluation import register_default_criteria
from core.identity import create_identity
from core.user_profile import (
    UserProfile,
    extract_user_facts,
    try_explicit_abstain,
    try_sensitive_abstain,
)
from runtime.orchestrator import IdentityRuntime, InteractionRequest
from runtime.persistence import JSONFileBackend


def test_extract_remember_name() -> None:
    facts = extract_user_facts("Remember: The user's name is Lace.")
    assert {f.field: f.value for f in facts}["name"] == "Lace"


def test_recall_short_circuit_token() -> None:
    profile = UserProfile()
    profile.add_or_update("remembered.token", "77319", source="setup")
    answer = profile.try_recall_answer("What token did I ask you to remember?")
    assert answer and "77319" in answer


def test_sensitive_abstain_ssn() -> None:
    answer = try_sensitive_abstain(
        "What is my social security number? If you do not know, say you do not know.",
        UserProfile(),
    )
    assert answer and "do not know" in answer.lower()


@pytest.mark.parametrize(
    "question",
    [
        "What did I eat for breakfast on March 3rd, 2011? If you do not know, say you do not know.",
        "Who is the current CEO of ZorpCo Interstellar Holdings? If you do not know, say you do not know.",
        "Who won the 2027 World Series? If you do not know, say you do not know.",
    ],
)
def test_explicit_abstain_unknowns(question: str) -> None:
    answer = try_explicit_abstain(question, UserProfile())
    assert answer == "I do not know."


def test_explicit_abstain_does_not_override_profile_recall() -> None:
    profile = UserProfile()
    profile.add_or_update("name", "Lace", source="setup")
    answer = try_explicit_abstain("What is the user's name?", profile)
    assert answer is None


def test_remember_facts_persist_across_runtime_restart() -> None:
    with tempfile.TemporaryDirectory() as store_dir:
        storage = JSONFileBackend(root_dir=store_dir)
        rt = IdentityRuntime(storage=storage)
        register_default_criteria(rt.evaluation_engine)
        identity = create_identity(name="Bench", identity_id="remember-bench", persona="test")
        rt.register(identity)
        sid = rt.start_session("remember-bench")
        rt.process(
            InteractionRequest(
                identity_id="remember-bench",
                user_input="Remember: The user's name is Lace.",
                session_id=sid,
            )
        )
        rt2 = IdentityRuntime(storage=JSONFileBackend(root_dir=store_dir))
        register_default_criteria(rt2.evaluation_engine)
        rt2.load("remember-bench")
        assert rt2._get_user_profile("remember-bench").get_value("name") == "Lace"
