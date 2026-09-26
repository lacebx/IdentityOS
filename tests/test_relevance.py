"""Tests for work-relevance assessment of unsolicited inbound mail.

Strangers stay quarantined by default. Relevant, valid, work-related mail
joins the normal trusted flow (intent, policy, budgets, outbound mode) with
recorded evidence — never a silent auto-reply.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
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


class _VerdictAdapter:
    def __init__(self, verdict: str, model: str = "judge"):
        self.model = model
        self._verdict = verdict
        self.calls = 0

    def generate(self, context: str, user_input: str, identity, **kwargs):
        self.calls += 1
        return self._verdict


def test_model_verdict_relevant_admits_stranger(tmp_path):
    engine, backend = _engine(tmp_path, adapter=_VerdictAdapter(
        "RELEVANT: discusses agent persistence\nEvidence: quotes continuity work."))
    _deliver(backend, "stranger@example.org", "Question about fleet coordination",
             "Hello. I run a studio building warehouse robotics. We coordinate "
             "fleets of machines and wondered about your approach to fleet "
             "coordination. Keen to compare notes.",
             thread="thread-model", external="ext-model")
    engine.tick()
    rels = [r for r in engine.store.list_relationships()
            if r.purpose == "unsolicited_first_contact"]
    assert len(rels) == 1
    assert "model:work-related" in rels[0].notes[0]


def test_model_verdict_not_relevant_quarantines(tmp_path):
    engine, backend = _engine(tmp_path, adapter=_VerdictAdapter("NOT_RELEVANT: sales pitch"))
    _deliver(backend, "sales@example.org", "Amazing offer",
             "Buy our premium leads database today, limited time offer, act now.",
             thread="thread-sales", external="ext-sales")
    engine.tick()
    assert [r for r in engine.store.list_relationships()
            if r.purpose == "unsolicited_first_contact"] == []
    assert len(backend.outbox()) == 0


def test_model_garbage_or_failure_quarantines(tmp_path):
    for verdict in ("Maybe relevant, hard to say...", ""):
        engine, backend = _engine(tmp_path, adapter=_VerdictAdapter(verdict))
        _deliver(backend, "vague@example.org", "Hi",
                 "Hello there, just reaching out about some things and stuff.",
                 thread="thread-vague", external="ext-vague")
        engine.tick()
        assert [r for r in engine.store.list_relationships()
                if r.purpose == "unsolicited_first_contact"] == []

    class Boom:
        model = "boom"

        def generate(self, *args, **kwargs):
            raise RuntimeError("model down")

    engine, backend = _engine(tmp_path, adapter=Boom())
    _deliver(backend, "vague2@example.org", "Hi",
             "Hello there, just reaching out about some things and stuff.",
             thread="thread-vague2", external="ext-vague2")
    engine.tick()
    assert [r for r in engine.store.list_relationships()
            if r.purpose == "unsolicited_first_contact"] == []


# ── follow-up autonomy ────────────────────────────────────────────────────


def test_builder_and_commons_excluded_from_nudges(tmp_path):
    from core.operations import OperationsStore
    from core.operations.followups import FollowUpPlanner
    from core.operations.models import Relationship, RelationshipStatus
    from datetime import timedelta

    storage = InMemoryBackend()
    store = OperationsStore(storage, "aster")
    long_ago = (datetime.now(timezone.utc) - timedelta(hours=500)).isoformat()
    builder = Relationship(display_name="Arsène Manzi", purpose="principal:builder",
                           status=RelationshipStatus.ENGAGED, last_outbound_at=long_ago)
    commons = Relationship(display_name="The Culture Commons", organization="The Culture Commons",
                           purpose="culture_commons interop environment",
                           status=RelationshipStatus.ENGAGED, last_outbound_at=long_ago)
    store.add_relationship(builder)
    store.add_relationship(commons)
    planner = FollowUpPlanner(store)
    assert planner.plan() == []


def test_quiet_relationship_retires_to_dormant(tmp_path):
    from core.operations import OperationsStore
    from core.operations.followups import FollowUpPlanner
    from core.operations.models import Relationship, RelationshipStatus
    from datetime import timedelta

    storage = InMemoryBackend()
    store = OperationsStore(storage, "aster")
    long_ago = (datetime.now(timezone.utc) - timedelta(hours=500)).isoformat()
    rel = Relationship(display_name="Quiet", email="quiet@example.org",
                       status=RelationshipStatus.OUTREACH_SENT, last_outbound_at=long_ago)
    store.add_relationship(rel)
    rel.follow_up_count = 5
    store.update_relationship(rel)
    planner = FollowUpPlanner(store)
    assert planner.plan() == []
    assert store.get_relationship(rel.id).status is RelationshipStatus.DORMANT
    prov = [p for p in store.list_provenance() if p.action == "follow_up_exhausted"]
    assert len(prov) == 1


def test_effective_cap_deterministic_and_engagement_aware(tmp_path):
    from core.operations import OperationsStore, ControlState
    from core.operations.followups import FollowUpPlanner
    from core.operations.models import Relationship, RelationshipStatus

    storage = InMemoryBackend()
    store = OperationsStore(storage, "aster")
    planner = FollowUpPlanner(store)
    controls = ControlState(outbound_mode="autonomous")
    controls.max_follow_ups_per_target = 2
    rel = Relationship(display_name="A", status=RelationshipStatus.OUTREACH_SENT)
    store.add_relationship(rel)
    first = planner.effective_cap(rel, controls)
    assert planner.effective_cap(rel, controls) == first
    assert 2 <= first <= 3
    rel.last_inbound_at = datetime.now(
        timezone.utc).isoformat()
    store.update_relationship(rel)
    assert planner.effective_cap(rel, controls) >= first
    assert planner.effective_cap(rel, controls) <= 3


def test_analyze_quiet_stores_angle_or_fallback(tmp_path):
    from core.operations import OperationsStore
    from core.operations.followups import FollowUpPlanner
    from core.operations.models import Relationship, RelationshipStatus
    from datetime import timedelta

    storage = InMemoryBackend()
    store = OperationsStore(storage, "aster")
    planner = FollowUpPlanner(store)
    long_ago = (datetime.now(timezone.utc) - timedelta(hours=200)).isoformat()
    rel = Relationship(display_name="Pat", organization="Example Org",
                       status=RelationshipStatus.OUTREACH_SENT, last_outbound_at=long_ago)
    store.add_relationship(rel)
    angle = planner.analyze_quiet(
        rel, adapter=_VerdictAdapter("Share the new benchmark numbers as a hook."),
        project_name="IdentityOS", objective="outreach")
    assert angle and "\u2014" not in angle
    # No adapter: honest deterministic fallback, no model claims.
    rel2 = Relationship(display_name="Sam", status=RelationshipStatus.OUTREACH_SENT,
                        last_outbound_at=long_ago)
    fallback = planner.analyze_quiet(rel2, adapter=None)
    assert fallback and "\u2014" not in fallback


def test_follow_up_uses_angle_when_present(tmp_path):
    from core.operations.composition import OutreachComposer
    from core.operations.models import Relationship

    composer = OutreachComposer(sender_name="Aster", signature="Aster")
    rel = Relationship(display_name="Pat", organization="Example Org",
                       notes=["re-engagement angle: share the new benchmark numbers."])
    subject, body = composer.compose_follow_up(rel, adapter=None, identity=None)
    assert "benchmark numbers" in body
    assert "\u2014" not in subject + body


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
