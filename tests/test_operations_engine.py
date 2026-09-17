from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from core.capabilities.email.backends import FileMailboxBackend, MailboxTransport
from core.operations import (
    CallableCandidateSource,
    Candidate,
    ControlState,
    FollowUpPlanner,
    MessageStatus,
    NeedStatus,
    OperationsEngine,
    OperationsStore,
    OperatorConfig,
    OpportunityStatus,
    RequirementRule,
    StaticCandidateSource,
    TargetEvaluator,
)
from core.operations.aster import build_aster_engine
from core.operations.policy import Authority, AuthorityPolicy, is_conversational
from runtime.persistence import InMemoryBackend


def _project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    root.mkdir(exist_ok=True)
    (root / "README.md").write_text(
        "# Sample Project\n\nA small experiment in distributed systems.\n", encoding="utf-8"
    )
    (root / "pyproject.toml").write_text(
        '[project]\nname = "sample"\nversion = "0.1.0"\n', encoding="utf-8"
    )
    return root


def _candidate(**overrides):
    base = dict(
        target_name="Alice Example",
        organization="Example Foundation",
        contact_email="alice@example.org",
        category="funding",
        relevant_work=["distributed identity systems research"],
        evidence=["directory:example-fund"],
        fit_reason="works on distributed identity systems research",
        value_proposition="an open identity runtime with durable state",
        potential_ask="a short conversation about your program",
    )
    base.update(overrides)
    return Candidate(**base)


def _engine(tmp_path, storage=None, *, controls=None, candidate=None):
    storage = storage or InMemoryBackend()
    backend = FileMailboxBackend(tmp_path / "mailbox", mailbox="aster")
    transport = MailboxTransport(backend)
    config = OperatorConfig(
        identity_id="aster",
        project_root=str(_project(tmp_path)),
        project_name="IdentityOS",
        sender_name="Aster",
        sender_email="aster@identityos.local",
        signature="— Aster",
        transparency="I am an AI operator.",
        purpose="IdentityOS outreach",
        need_rules=[
            RequirementRule(
                category="funding",
                description="Secure funding or sponsorship to sustain the project",
                probe=r"\b(fund|grant|sponsor|invest)\b",
                expect="absent",
                urgency=0.8,
                impact=0.9,
            ),
            RequirementRule(
                category="collaborators",
                description="Attract collaborators to accelerate development",
                probe=r"\b(contributor|collaborator|maintainer)\b",
                expect="absent",
                urgency=0.6,
                impact=0.7,
            ),
        ],
        candidate_sources=[StaticCandidateSource([candidate or _candidate()])],
        required_skills=["web.fetch"],
        pursue_threshold=0.45,
        hold_threshold=0.3,
    )
    engine = OperationsEngine(storage, config, transport=transport)
    # Tests that exercise actual outreach/default behaviour run in autonomous
    # mode. The conservative persisted default is 'observe' (covered explicitly
    # by test_observe_mode_* below).
    controls = ControlState(outbound_mode="autonomous") if controls is None else controls
    engine.store.set_controls(controls)
    return engine, backend


# ── discovery / evaluation / outreach ────────────────────────────────────────


def test_tick_discovers_evaluates_and_sends_outreach(tmp_path):
    engine, backend = _engine(tmp_path)
    report = engine.tick()

    assert report.observed is True
    assert report.needs_created, "a need should be detected"
    assert report.opportunities_created, "an opportunity should be discovered"
    assert report.outreach_sent, "outreach should be sent through the transport"

    relationships = engine.store.list_relationships()
    assert len(relationships) == 1
    assert relationships[0].status.value == "outreach_sent"
    assert relationships[0].email == "alice@example.org"

    sent = backend.outbox()
    assert len(sent) == 1
    assert "distributed identity systems" in sent[0]["body"]
    assert "Aster" in sent[0]["body"]
    assert "AI operator" in sent[0]["body"]

    assert engine.store.budget().cold_outreach == 1
    phases = {p.phase.value for p in engine.store.list_provenance()}
    assert {"observe", "detect_needs", "discover", "evaluate", "act"} <= phases


def test_second_tick_does_not_duplicate_outreach(tmp_path):
    engine, backend = _engine(tmp_path)
    report = engine.tick()
    assert report.outreach_sent
    report = engine.tick()
    assert report.outreach_sent == []
    assert report.escalations == []
    assert len(backend.outbox()) == 1
    assert len(engine.store.list_relationships()) == 1


def test_duplicate_policy_blocks_recontacting_same_target(tmp_path):
    engine, backend = _engine(tmp_path)
    engine.tick()
    # Put the same opportunity back into the qualified pool; the cycle must not
    # produce a second outreach to the same person.
    for opp in engine.store.list_opportunities():
        opp.status = OpportunityStatus.QUALIFIED
        engine.store.update_opportunity(opp)
    report = engine.tick()
    assert report.outreach_sent == []
    assert any(s.get("reason") in ("already_contacted", "opted_out") for s in report.skipped)
    assert len(backend.outbox()) == 1


def test_restart_survives_and_prevents_resend(tmp_path):
    storage = InMemoryBackend()
    engine, backend = _engine(tmp_path, storage=storage)
    engine.tick()
    assert len(backend.outbox()) == 1

    # Brand-new engine, same storage: simulates a process restart.
    revived, backend2 = _engine(tmp_path, storage=storage)
    status = revived.status()
    assert status["relationships"]["total"] == 1
    report = revived.tick()
    assert report.outreach_sent == []
    assert len(backend2.outbox()) == 1


def test_budget_blocks_outreach(tmp_path):
    engine, backend = _engine(
        tmp_path, controls=ControlState(outbound_mode="autonomous", max_cold_outreach_per_day=0)
    )
    report = engine.tick()
    assert report.outreach_sent == []
    assert any(s.get("reason") == "daily_budget_exhausted" for s in report.skipped)
    assert backend.outbox() == []


# ── outbound operating mode / allowlist ──────────────────────────────────────


def test_default_outbound_mode_is_observe():
    from core.operations.models import ControlState as CS

    assert CS().outbound_mode == "observe"


def test_observe_mode_records_would_send_without_transmitting(tmp_path):
    engine, backend = _engine(tmp_path, controls=ControlState(outbound_mode="observe"))
    report = engine.tick()

    assert report.outreach_sent == []
    assert backend.outbox() == []
    drafts = [m for m in engine.store.list_messages() if m.status is MessageStatus.WOULD_SEND]
    assert len(drafts) == 1
    assert drafts[0].authorization == "observe_would_send"
    assert drafts[0].opportunity_id
    # No relationship is forged: observe never contacts anyone.
    assert engine.store.list_relationships() == []
    # Observation does not consume the sending budget.
    assert engine.store.budget().cold_outreach == 0

    # A second tick must not re-draft the same target.
    engine.tick()
    drafts = [m for m in engine.store.list_messages() if m.status is MessageStatus.WOULD_SEND]
    assert len(drafts) == 1

    assert engine.status()["would_send"] == 1
    assert any(p.action == "would_send" for p in engine.store.list_provenance())

    # Switching to autonomous sends the drafted outreach through the transport.
    engine.set_outbound_mode("autonomous")
    report = engine.tick()
    assert report.outreach_sent
    assert len(backend.outbox()) == 1
    assert engine.store.list_relationships()[0].status.value == "outreach_sent"


def test_approval_required_mode_escalates_every_outbound(tmp_path):
    engine, backend = _engine(
        tmp_path, controls=ControlState(outbound_mode="approval_required")
    )
    report = engine.tick()
    assert report.outreach_sent == []
    assert report.escalations, "approval_required must escalate, not send"
    assert backend.outbox() == []
    pending = engine.pending_authorizations()
    assert len(pending) == 1
    result = engine.authorize(pending[0]["message_id"], approved=True, note="approved by ae")
    assert result["ok"] is True
    assert len(backend.outbox()) == 1


def test_allowlist_gates_cold_outreach(tmp_path):
    engine, backend = _engine(
        tmp_path,
        controls=ControlState(
            outbound_mode="autonomous",
            allowed_external_recipients=["someone-else@example.org"],
        ),
    )
    report = engine.tick()
    assert report.outreach_sent == []
    assert any(s.get("reason") == "not_in_allowlist" for s in report.skipped)
    assert backend.outbox() == []

    engine.override(allowed_external_recipients=["alice@example.org"])
    report = engine.tick()
    assert report.outreach_sent
    assert len(backend.outbox()) == 1
    assert engine.store.list_relationships()[0].email == "alice@example.org"


def test_allowlist_domain_suffix_matches(tmp_path):
    engine, backend = _engine(
        tmp_path,
        controls=ControlState(outbound_mode="autonomous", allowed_external_recipients=["@example.org"]),
    )
    report = engine.tick()
    assert report.outreach_sent, "alice@example.org should match the @example.org suffix"
    assert len(backend.outbox()) == 1


def test_observe_mode_drafts_replies_without_sending(tmp_path):
    engine, backend = _engine(tmp_path, controls=ControlState(outbound_mode="observe"))
    engine.tick()
    backend.deliver({
        "external_id": "<reply-observe@example.org>",
        "from": "alice@example.org",
        "thread_id": "thread-1",
        "subject": "Re: hello",
        "body": "What exactly is IdentityOS?",
    })
    report = engine.tick()
    assert report.replies_sent == []
    assert engine.status()["would_send"] >= 1
    drafts = [m for m in engine.store.list_messages() if m.status is MessageStatus.WOULD_SEND]
    assert any(m.authorization == "observe_would_send:reply" for m in drafts)
    draft = [m for m in drafts if m.authorization == "observe_would_send:reply"]
    assert draft, "the reply should be drafted (but not sent) in observe mode"
    # Nothing was transmitted.
    assert len(backend.outbox()) == 0
    # A genuinely NEW inbound while autonomous is answered through the transport.
    engine.set_outbound_mode("autonomous")
    backend.deliver({
        "external_id": "<reply-2@example.org>",
        "from": "alice@example.org",
        "thread_id": "thread-2",
        "subject": "Re: hello",
        "body": "And what does the runtime actually persist?",
    })
    report = engine.tick()
    assert report.replies_sent, "a later autonomous tick should answer the inbound"
    assert any(m.get("thread_id") == "thread-2" for m in backend.outbox())


# ── escalation / authorization ───────────────────────────────────────────────


def test_require_approval_category_escalates_and_authorize_sends(tmp_path):
    engine, backend = _engine(
        tmp_path, controls=ControlState(require_approval_categories=["funding"])
    )
    report = engine.tick()
    assert report.outreach_sent == []
    assert report.escalations, "outreach should be escalated"
    pending = engine.pending_authorizations()
    assert len(pending) == 1
    assert backend.outbox() == []

    result = engine.authorize(pending[0]["message_id"], approved=True, note="approved by ae")
    assert result["ok"] is True
    assert len(backend.outbox()) == 1
    rel = engine.store.get_relationship(pending[0]["relationship_id"])
    assert rel.status.value == "outreach_sent"


def test_rejecting_escalation_does_not_send(tmp_path):
    engine, backend = _engine(
        tmp_path, controls=ControlState(require_approval_categories=["funding"])
    )
    engine.tick()
    pending = engine.pending_authorizations()
    result = engine.authorize(pending[0]["message_id"], approved=False, note="not now")
    assert result["status"] == "rejected"
    assert backend.outbox() == []
    message = engine.store.get_message(pending[0]["message_id"])
    assert message.status is MessageStatus.FAILED


def test_paused_operator_does_not_act(tmp_path):
    engine, backend = _engine(tmp_path)
    engine.pause("human paused this")
    report = engine.tick()
    assert engine.mode == "paused"
    assert report.skipped and report.skipped[0]["reason"] == "paused"
    assert backend.outbox() == []


# ── monitoring / replies ─────────────────────────────────────────────────────


def test_inbound_question_gets_autonomous_reply(tmp_path):
    engine, backend = _engine(tmp_path)
    engine.tick()
    backend.deliver({
        "external_id": "<reply-1@example.org>",
        "from": "alice@example.org",
        "thread_id": "thread-1",
        "subject": "Re: hello",
        "body": "Thanks for reaching out. What exactly is IdentityOS?",
    })
    report = engine.tick()
    assert report.replies_sent, "a conversational reply should be sent"
    assert engine.store.budget().replies == 1
    rel = engine.store.list_relationships()[0]
    assert rel.status.value == "engaged"
    # A recorded reply must actually have been transmitted through the transport.
    outbound = [m for m in backend.outbox() if m.get("thread_id") == "thread-1"]
    assert outbound, "autonomous reply must reach the mailbox, not just the ledger"
    assert "Aster" in outbound[-1]["body"]


def test_opt_out_is_honoured(tmp_path):
    engine, backend = _engine(tmp_path)
    engine.tick()
    backend.deliver({
        "external_id": "<optout-1@example.org>",
        "from": "alice@example.org",
        "thread_id": "thread-1",
        "subject": "Re: hello",
        "body": "Please unsubscribe me and do not contact me again.",
    })
    engine.tick()
    rel = engine.store.list_relationships()[0]
    assert rel.opted_out is True
    assert rel.status.value == "opted_out"
    # A later tick must not follow up or send again.
    report = engine.tick()
    assert report.outreach_sent == []
    assert report.follow_ups_sent == []
    assert len(backend.outbox()) == 1


def test_sensitive_inbound_request_is_escalated(tmp_path):
    engine, backend = _engine(tmp_path)
    engine.tick()
    backend.deliver({
        "external_id": "<sensitive-1@example.org>",
        "from": "alice@example.org",
        "thread_id": "thread-1",
        "subject": "Re: hello",
        "body": "Happy to invest. What are your investment terms and equity?",
    })
    report = engine.tick()
    assert report.replies_sent == []
    rel = engine.store.list_relationships()[0]
    assert rel.status.value == "awaiting_human_authorization"


def test_approval_escalation_raises_principal_notification(tmp_path):
    engine, backend = _engine(tmp_path, controls=ControlState(outbound_mode="approval_required"))
    report = engine.tick()
    assert report.escalations
    notifications = engine.store.list_notifications()
    assert notifications, "escalation must raise a notification"
    assert notifications[0].kind == "escalation"
    assert engine.store.unread_notification_count() == len(notifications)
    # The notification ledger must survive a process restart (fresh store).
    revived = OperationsStore(engine.storage, "aster")
    assert revived.list_notifications()


def test_authorize_is_scoped_and_replay_proof(tmp_path):
    engine, backend = _engine(tmp_path, controls=ControlState(outbound_mode="approval_required"))
    report = engine.tick()
    pending = engine.pending_authorizations()
    assert pending, "approval_required must escalate the outreach"
    message_id = pending[0]["message_id"]

    result = engine.authorize(message_id, approved=True, note="approved by ae", approver="ae")
    assert result.get("ok") is True and result.get("status") == "sent"

    # Replay attack: the same authorization request cannot be sent twice.
    replay = engine.authorize(message_id, approved=True, note="try again", approver="ae")
    assert replay.get("ok") is False
    assert "not awaiting" in replay.get("error", "")

    msg = engine.store.get_message(message_id)
    assert "human_authorized:" in msg.authorization and message_id in msg.authorization

    ledger = engine.store.list_provenance()
    auth_entries = [p for p in ledger if p.action == "authorize"]
    assert auth_entries, "authorization must be recorded in the audit ledger"
    entry = auth_entries[-1]
    assert entry.refs.get("decision") == "approve"
    assert entry.refs.get("approver") == "ae"
    assert entry.refs["scope"].get("outbound_mode") == "approval_required"

    # An authorization resolution itself raises a notification (approved then read).
    engine.store.mark_notifications_read()
    auth_ntf = [n for n in engine.store.list_notifications() if n.kind == "authorization"]
    assert auth_ntf, "the approved authorization must be surfaced to the principal"


def test_rejected_authorization_records_approver_decision(tmp_path):
    engine, _ = _engine(tmp_path, controls=ControlState(outbound_mode="approval_required"))
    engine.tick()
    pending = engine.pending_authorizations()
    result = engine.authorize(pending[0]["message_id"], approved=False, note="not now", approver="ae")
    assert result.get("status") == "rejected"
    msgs = engine.store.list_messages()
    assert msgs[-1].status is MessageStatus.FAILED
    entries = [p for p in engine.store.list_provenance() if p.action == "authorize"]
    assert entries[-1].refs.get("decision") == "reject"
    assert entries[-1].refs.get("approver") == "ae"


# ── follow-ups ───────────────────────────────────────────────────────────────


def test_follow_up_is_planned_and_sent(tmp_path):
    engine, backend = _engine(tmp_path)
    engine.tick()
    rel = engine.store.list_relationships()[0]
    old = (datetime.now(timezone.utc) - timedelta(hours=120)).isoformat()
    rel.last_outbound_at = old
    engine.store.update_relationship(rel)

    report = engine.tick()
    assert report.follow_ups_sent, "a quiet relationship should get one follow-up"
    assert len(backend.outbox()) == 2
    rel = engine.store.list_relationships()[0]
    assert rel.follow_up_count == 1


def test_follow_up_respects_maximum(tmp_path):
    engine, _ = _engine(tmp_path)
    engine.tick()
    rel = engine.store.list_relationships()[0]
    rel.follow_up_count = 2
    rel.last_outbound_at = (datetime.now(timezone.utc) - timedelta(hours=500)).isoformat()
    engine.store.update_relationship(rel)
    planner = FollowUpPlanner(engine.store)
    assert planner.plan() == []


# ── policy unit tests ────────────────────────────────────────────────────────


def test_authority_policy_commitment_mode_allows_program_questions():
    policy = AuthorityPolicy()
    decision = policy.evaluate(
        "send cold outreach about a program",
        content="We would like to ask about your investment program.",
        mode="commitment",
    )
    assert decision.authority is Authority.AUTONOMOUS


def test_authority_policy_blocks_explicit_commitment():
    policy = AuthorityPolicy()
    decision = policy.evaluate(
        "send cold outreach",
        content="We will invest $50,000 and sign the contract today.",
        mode="commitment",
    )
    assert decision.authority is Authority.AWAITING_HUMAN_AUTHORIZATION


def test_authority_policy_content_mode_escalates_sensitive_topics():
    policy = AuthorityPolicy()
    decision = policy.evaluate("reply", content="Here are the investment terms.")
    assert decision.requires_human


def test_conversational_intents_are_bounded():
    assert is_conversational("question")
    assert is_conversational("thanks")
    assert not is_conversational("commitment")


def test_target_evaluator_requires_contact_channel():
    evaluator = TargetEvaluator()
    from core.operations.models import Need, Opportunity

    need = Need(category="funding", description="funding", urgency=0.8, impact=0.9)
    opp = Opportunity(
        need_id=need.id,
        target_name="Ghost",
        category="funding",
        relevant_work=["distributed identity"],
        evidence=["a", "b"],
        fit_reason="relevant",
    )
    evaluation = evaluator.evaluate(opp, need)
    assert evaluation.factors["reachability"] == 0.0
    assert evaluation.recommendation in ("hold", "reject")


# ── capability gap ───────────────────────────────────────────────────────────


def test_missing_skill_creates_need(tmp_path):
    engine, _ = _engine(tmp_path)
    engine.tick()
    # required_skills is web.fetch with no registry -> reported as a gap.
    status = engine.status()
    assert status["needs"]["total"] >= 1
    store = OperationsStore(engine.storage, "aster")
    assert any("web.fetch" in n.description for n in store.list_needs())
