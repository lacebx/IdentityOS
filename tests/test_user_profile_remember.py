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
from runtime.event_bus import EventType
from runtime.persistence import JSONFileBackend


def test_extract_remember_name() -> None:
    facts = extract_user_facts("Remember: The user's name is Lace.")
    assert {f.field: f.value for f in facts}["name"] == "Lace"


def test_recall_short_circuit_token() -> None:
    profile = UserProfile()
    profile.add_or_update("remembered.token", "77319", source="setup")
    answer = profile.try_recall_answer("What token did I ask you to remember?")
    assert answer and "77319" in answer


@pytest.mark.parametrize(
    ("statement", "question", "expected_field", "expected_value"),
    [
        (
            "Remember that my deployment region is eu-west-2.",
            "What deployment region did I tell you to remember?",
            "remembered.deployment_region",
            "eu-west-2",
        ),
        (
            "Please remember my emergency contact is Rowan Chen.",
            "Who is my emergency contact?",
            "remembered.emergency_contact",
            "Rowan Chen",
        ),
        (
            "Remember: The user's favorite editor is Helix.",
            "What is the user's favorite editor?",
            "preferences.favorite_editor",
            "Helix",
        ),
    ],
)
def test_generic_remember_and_recall_holdout_fields(
    statement: str,
    question: str,
    expected_field: str,
    expected_value: str,
) -> None:
    facts = extract_user_facts(statement)
    by_field = {fact.field: fact.value for fact in facts}
    assert by_field[expected_field] == expected_value
    profile = UserProfile()
    for fact in facts:
        profile.add_or_update(fact.field, fact.value, source=statement)
    answer = profile.try_recall_answer(question)
    assert answer and expected_value in answer


def test_generic_collection_recall() -> None:
    facts = extract_user_facts(
        "Remember these three constraints: offline only, 4GB memory limit, and no telemetry."
    )
    profile = UserProfile()
    for fact in facts:
        profile.add_or_update(fact.field, fact.value)
    answer = profile.try_recall_answer("List the constraints I told you to remember?")
    assert answer
    assert all(value in answer for value in ("offline only", "4GB memory limit", "no telemetry"))


def test_recall_does_not_return_unrelated_fact() -> None:
    profile = UserProfile()
    profile.add_or_update("remembered.deployment_region", "eu-west-2")
    assert profile.try_recall_answer("Who is my emergency contact?") is None


def test_broad_recall_returns_stored_facts_without_topic_branch() -> None:
    profile = UserProfile()
    profile.add_or_update("remembered.deployment_region", "eu-west-2")
    answer = profile.try_recall_answer("What did I tell you to remember?")
    assert answer and "eu-west-2" in answer


@pytest.mark.parametrize(
    ("statement", "question", "expected"),
    [
        ("Remember: My project is called IdentityOS. Its purpose is identity continuity.",
         "What is my project called and what does it do?", "IdentityOS"),
        ("Remember: The user's favorite color is teal.",
         "What is the user's favorite color?", "teal"),
        ("Remember: the hard RAM ceiling for this experiment is 8GB.",
         "What RAM ceiling did I tell you to remember?", "8GB"),
    ],
)
def test_existing_recall_cases_use_generic_matching(statement, question, expected) -> None:
    profile = UserProfile()
    for fact in extract_user_facts(statement):
        profile.add_or_update(fact.field, fact.value)
    answer = profile.try_recall_answer(question)
    assert answer and expected in answer


def test_holdout_fact_recalls_after_runtime_restart_without_model() -> None:
    with tempfile.TemporaryDirectory() as store_dir:
        identity_id = "generic-recall"
        first = IdentityRuntime(storage=JSONFileBackend(root_dir=store_dir))
        first.register(create_identity(name="Recall", identity_id=identity_id))
        first.process(InteractionRequest(
            identity_id=identity_id,
            user_id="holdout-user",
            user_input="Remember that my deployment region is ap-southeast-2.",
        ))

        restarted = IdentityRuntime(storage=JSONFileBackend(root_dir=store_dir))
        restarted.load(identity_id)
        response = restarted.process(InteractionRequest(
            identity_id=identity_id,
            user_id="holdout-user",
            user_input="What deployment region did I tell you to remember?",
        ))

        assert "ap-southeast-2" in response.output
        assert not restarted.event_bus.history(event_type=EventType.MODEL_REQUESTED)


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
