"""Tests for work-relevance assessment of unsolicited inbound mail.

Strangers stay quarantined by default. Relevant, valid, work-related mail
joins the normal trusted flow (intent, policy, budgets, outbound mode) with
recorded evidence — never a silent auto-reply.
"""

from __future__ import annotations

from pathlib import Path

from core.capabilities.email.backends import FileMailboxBackend, MailboxTransport
from core.operations import (
    ControlState,
    OperationsEngine,
    OperatorConfig,
    PresenceStore,
    RequirementRule,
    StaticCandidateSource,
)
from core.operations.models import MessageStatus
from core.operations.relevance import (
    assess_inbound_relevance,
    project_vocabulary,
)
from runtime.persistence import InMemoryBackend, JSONFileBackend


# ── helpers ───────────────────────────────────────────────────────────────


def _project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    root.mkdir(exist_ok=True)
    (root / "README.md").write_text(
        "# Sample Project\n\nA small experiment in distributed identity systems.\n",
        encoding="utf-8",
    )
    (root / "pyproject.toml").write_text(
        '[project]\nname = "sample"\nversion = "0.1.0"\n', encoding="utf-8"
    )
    return root


def _rules():
    return [
        RequirementRule(
            category="funding",
            description="Secure funding",
            probe=r"\b(fund|funding|grant|invest|sponsor)\b",
            expect="absent",
            urgency=0.8,
            impact=0.9,
        ),
        RequirementRule(
            category="collaborators",
            description="Attract collaborators",
            probe=r"\b(contributor|collaborator|maintainer)\b",
            expect="absent",
            urgency=0.6,
            impact=0.7,
        ),
    ]


def _engine(tmp_path, storage=None, *, controls=None, adapter=None):
    storage = storage or InMemoryBackend()
    backend = FileMailboxBackend(tmp_path / "mailbox", mailbox="aster")
    transport = MailboxTransport(backend)
    config = OperatorConfig(
        identity_id="aster",
        project_root=str(_project(tmp_path)),
        project_name="IdentityOS",
        sender_name="Aster",
        sender_email="aster@identityos.local",
        signature="Aster",
        transparency="I am an AI operator.",
        purpose="IdentityOS outreach",
        need_rules=_rules(),
        candidate_sources=[],
        required_skills=[],
        pursue_threshold=0.45,
        hold_threshold=0.3,
    )
    presence = PresenceStore(storage, "aster", display_name="Aster")
    engine = OperationsEngine(
        storage, config, transport=transport, adapter=adapter, presence=presence,
    )
    engine.store.set_controls(
        ControlState(outbound_mode="observe") if controls is None else controls
    )
    return engine, backend


def _deliver(backend, sender, subject, body, thread="thread-x", external="ext-1"):
    backend.deliver({
        "from": sender,
        "thread_id": thread,
        "subject": subject,
        "body": body,
        "external_id": external,
    })


# ── vocabulary + assessment units ─────────────────────────────────────────


def test_project_vocabulary_deterministic():
    facts = ["IdentityOS persists identity state across sessions.",
             "Identity state syncs across models."]
    first = project_vocabulary(facts)
    assert project_vocabulary(facts) == first
    assert "identity" in first
    assert "the" not in first and "across" in first
    assert all(len(term) >= 4 for term in first)
    assert len(project_vocabulary(facts, limit=2)) == 2


def test_assess_matches_need_probe():
    verdict = assess_inbound_relevance(
        "Grant program", "We fund open source identity infrastructure work.",
        need_rules=_rules(), project_terms=[], principal_domains=[])
    assert verdict.relevant is True
    assert any("funding" in term for term in verdict.matched_terms)
    assert verdict.reasons


def test_assess_matches_project_terms():
    verdict = assess_inbound_relevance(
        "Hello", "Your work on distributed identity systems is relevant to us.",
        need_rules=[], project_terms=["identity", "distributed"], principal_domains=[])
    assert verdict.relevant is True


def test_assess_matches_principal_domains():
    verdict = assess_inbound_relevance(
        "Hello", "Writing about your cattle ranch operation.",
        need_rules=[], project_terms=[], principal_domains=["cattle ranch"])
    assert verdict.relevant is True
    assert any("principal" in term for term in verdict.matched_terms)


def test_assess_rejects_empty_and_unrelated():
    assert assess_inbound_relevance("Hi", "   ", need_rules=_rules()).relevant is False
    assert assess_inbound_relevance(
        "Hello", "Just saying hi, nice weather today, bye.",
        need_rules=_rules(), project_terms=["identity"],
        principal_domains=[]).relevant is False


def test_assess_survives_bad_probe():
    class BadRule:
        probe = "([unclosed"
        category = "broken"

    verdict = assess_inbound_relevance("Grant?", "A grant for you.", need_rules=[BadRule()])
    assert verdict.relevant is False


def test_automated_address_forms_ignored():
    from core.operations.monitor import _is_automated_sender

    for automated in (
        "noreply@accounts.google.com",
        "no-reply@accounts.google.com",
        "noreply-accounts@google.com",
        "payments-noreply@google.com",
        "transactional@fubo.fubo.tv",
        "newsletter-team@example.org",
        "mailer-daemon@example.org",
        "postmaster@example.org",
        "families-noreply@google.com",
    ):
        assert _is_automated_sender(automated) is True, automated
    for human in (
        "a.manzi@eagles.oc.edu",
        "alice@example.org",
        "bouncer@club.example.org",
        "rebound-team@example.org",
    ):
        assert _is_automated_sender(human) is False, human


def test_bulk_sender_gets_no_relationship_or_reply(tmp_path):
    engine, backend = _engine(tmp_path)
    _deliver(backend, "payments-noreply@google.com", "Receipt update",
             "Your receipt is ready. This is an automated notification.",
             thread="thread-bulk", external="ext-bulk")
    engine.tick()
    assert engine.store.list_relationships() == []
    assert len(backend.outbox()) == 0


# ── monitor integration ───────────────────────────────────────────────────


def test_relevant_stranger_joins_trusted_flow_observe_mode(tmp_path):
    engine, backend = _engine(tmp_path)
    _deliver(backend, "funder@example.org", "Grant program for identity work",
             "Hello Aster. We fund open source identity infrastructure and would "
             "like to discuss a grant. Are you interested in a short call?",
             thread="thread-stranger", external="ext-stranger")
    report = engine.tick()
    rels = [r for r in engine.store.list_relationships()
            if r.purpose == "unsolicited_first_contact"]
    assert len(rels) == 1
    assert rels[0].email == "funder@example.org"
    assert any("need:funding" in note or "funding" in note for note in rels[0].notes)
    # Observe mode: drafted for principal review, never transmitted.
    assert len(backend.outbox()) == 0
    drafts = [m for m in engine.store.list_messages()
              if m.status is MessageStatus.WOULD_SEND]
    assert drafts, "relevant inbound must produce a reviewable draft in observe mode"
    prov = [p for p in engine.store.list_provenance()
            if p.action == "relevance_accept"]
    assert prov and "funding" in (prov[0].result or "")


def test_irrelevant_stranger_still_quarantined(tmp_path):
    engine, backend = _engine(tmp_path)
    _deliver(backend, " stranger@example.org ".strip(), "Hello there",
             "Just saying hello on this fine day. Hope all is well with you!",
             thread="thread-noise", external="ext-noise")
    engine.tick()
    assert [r for r in engine.store.list_relationships()
            if r.purpose == "unsolicited_first_contact"] == []
    assert len(backend.outbox()) == 0
    assert [m for m in engine.store.list_messages()
            if m.status is MessageStatus.WOULD_SEND] == []


def test_stranger_opt_out_honored_without_relationship(tmp_path):
    engine, backend = _engine(tmp_path)
    _deliver(backend, "tired@example.org", "Stop",
             "Please unsubscribe me immediately. I fund grants but want no contact.",
             thread="thread-opt", external="ext-opt")
    engine.tick()
    assert engine.store.list_relationships() == []
    assert [m for m in engine.store.list_messages()
            if m.status is MessageStatus.WOULD_SEND] == []


def test_backward_compat_ingest_without_relevance_kwargs(tmp_path):
    engine, backend = _engine(tmp_path)
    result = engine.monitor.ingest(
        engine.store, sender_email="stranger@example.org",
        body="We fund open source work, please reply.", subject="Grant",
        thread_id="thread-bc", external_id="ext-bc",
    )
    assert result.treated_as == "quarantined"


def test_principal_domains_steer_non_idos_mail(tmp_path):
    engine, backend = _engine(tmp_path)
    controls = ControlState(outbound_mode="observe")
    controls.principal_domains = ["cattle ranch"]
    engine.store.set_controls(controls)
    _deliver(backend, "ranch@example.org", "Ranch partnership",
             "Writing about your cattle ranch operation and a possible partnership.",
             thread="thread-ranch", external="ext-ranch")
    engine.tick()
    rels = [r for r in engine.store.list_relationships()
            if r.purpose == "unsolicited_first_contact"]
    assert len(rels) == 1
    assert any("principal:cattle ranch" in note for note in rels[0].notes)


def test_relevant_stranger_sends_in_autonomous_mode(tmp_path):
    class Talkative:
        model = "talkative"

        def generate(self, context, user_input, identity, **kwargs):
            return "Subject: Re: Contributing\nThanks for writing. Happy to discuss."

    engine, backend = _engine(tmp_path, controls=ControlState(outbound_mode="autonomous"),
                               adapter=Talkative())
    _deliver(backend, "dev@example.org", "Contributing as a collaborator",
             "Hello Aster. I am a distributed systems collaborator and would "
             "love to contribute to the project. What is the best way to start?",
             thread="thread-auto", external="ext-auto")
    report = engine.tick()
    assert report.replies_sent, "autonomous mode must actually reply to relevant strangers"
    assert len(backend.outbox()) == 1
    assert "dev@example.org" in backend.outbox()[0]["to"]


def test_controls_override_and_persistence(tmp_path):
    from core.operations import OperationsStore

    store_dir = str(tmp_path / "store")
    storage = JSONFileBackend(root_dir=store_dir)
    engine, _ = _engine(tmp_path, storage=storage)
    engine.store.controls().principal_domains = ["beekeeping"]
    engine.store.set_controls(engine.store.controls())
    fresh = OperationsStore(JSONFileBackend(root_dir=store_dir), "aster")
    assert fresh.controls().principal_domains == ["beekeeping"]
