"""
core/operations/engine.py

The Operations engine — a durable, evidence-recording operator loop.

Each :meth:`OperationsEngine.tick` runs a sequence of phases against persisted
state:

    observe → capability-gap check → detect needs → discover opportunities
    → evaluate → act (outreach, within budget) → monitor replies → follow up

Every phase appends to an append-only provenance ledger.  Because all state is
loaded from storage at construction, a brand-new process with the same identity
resumes exactly where the previous one stopped: no duplicate outreach, no lost
conversations, no in-memory-only progress.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Optional, Mapping

from .capability_gap import CapabilityGap, CapabilityGapDetector, CapabilityStatus
from .composition import OutreachBrief, OutreachComposer
from .config import OperatorConfig
from .discovery import OpportunityDiscoverer
from .evaluation import DuplicateContactPolicy, TargetEvaluator
from .followups import FollowUpPlanner
from .models import (
    Evaluation,
    Message,
    MessageDirection,
    MessageStatus,
    NotificationEntry,
    Opportunity,
    OpportunityStatus,
    ProvenanceEntry,
    ProvenancePhase,
    Relationship,
    RelationshipStatus,
    utcnow,
)
from .monitor import ConversationMonitor, InboundDisposition, InboundResult
from .needs import NeedDetector
from .observer import ProjectStateObserver
from .policy import AuthorityPolicy
from .presence import PresenceStatus
from .store import OperationsStore, _norm

logger = logging.getLogger("identityos.operations")


@dataclass
class TickReport:
    observed: bool = False
    capability_gaps: list[dict[str, Any]] = field(default_factory=list)
    needs_created: list[str] = field(default_factory=list)
    opportunities_created: list[str] = field(default_factory=list)
    evaluated: list[str] = field(default_factory=list)
    qualified: list[str] = field(default_factory=list)
    outreach_sent: list[str] = field(default_factory=list)
    escalations: list[str] = field(default_factory=list)
    replies_sent: list[str] = field(default_factory=list)
    follow_ups_sent: list[str] = field(default_factory=list)
    principal_processed: list[str] = field(default_factory=list)
    principal_deferred: list[str] = field(default_factory=list)
    skipped: list[dict[str, Any]] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "observed": self.observed,
            "capability_gaps": list(self.capability_gaps),
            "needs_created": list(self.needs_created),
            "opportunities_created": list(self.opportunities_created),
            "evaluated": list(self.evaluated),
            "qualified": list(self.qualified),
            "outreach_sent": list(self.outreach_sent),
            "escalations": list(self.escalations),
            "replies_sent": list(self.replies_sent),
            "follow_ups_sent": list(self.follow_ups_sent),
            "principal_processed": list(self.principal_processed),
            "principal_deferred": list(self.principal_deferred),
            "skipped": list(self.skipped),
            "errors": list(self.errors),
        }


class OperationsEngine:
    def __init__(
        self,
        storage: Any,
        config: OperatorConfig,
        *,
        transport: Any = None,
        adapter: Any = None,
        identity: Any = None,
        capability_registry: Any = None,
        acquisition: Any = None,
        search_fn: Any = None,
        secret_store: Any = None,
        surfaces: Iterable[Any] = (),
        presence: Any = None,
    ) -> None:
        self.config = config
        self.storage = storage
        self.store = OperationsStore(storage, config.identity_id)
        self._mode = "live" if transport is not None else "dry-run"
        self._transport = transport
        self._adapter = adapter
        self._identity = identity
        self._capability_registry = capability_registry
        self._acquisition = acquisition
        self._search_fn = search_fn
        self._secret_store = secret_store
        self._surfaces = list(surfaces)
        self._presence = presence

        # Adaptive polling state
        self._last_observation_fingerprint: Optional[str] = None
        self._current_poll_interval = float(config.poll_interval or 300.0)
        self._min_poll_interval = 300.0  # 5 minutes
        self._max_poll_interval = 3600.0  # 1 hour
        self._adaptive_polling = bool(config.adaptive_polling)
        self._consecutive_unchanged = 0

        self.observer = ProjectStateObserver(config.project_root)
        self.detector = NeedDetector(config.need_rules)
        sources = list(config.candidate_sources)
        self.discoverer = OpportunityDiscoverer(sources)
        self.evaluator = TargetEvaluator(
            pursue_threshold=config.pursue_threshold,
            hold_threshold=config.hold_threshold,
        )
        self.duplicates = DuplicateContactPolicy(self.store)
        self.composer = OutreachComposer(
            sender_name=config.sender_name,
            project_name=config.project_name,
            signature=config.signature,
            transparency=config.transparency,
        )
        self.monitor = ConversationMonitor(
            self.composer,
            transport=self._transport,
            identity=self._identity,
            adapter=self._adapter,
            self_address=self.config.sender_email,
        )
        self.follow_ups = FollowUpPlanner(self.store)
        # Bind only an explicitly initialized service world. No schema writes or
        # identity creation on ordinary runtime startup.
        from core.services.integration import runtime_for
        self.services = runtime_for(storage, capability_registry) if capability_registry else None
        delegation = None
        if self.services and storage.load(config.identity_id, 'identity_spec'):
            session = self.services.bind(config.identity_id)
            delegation = lambda gap: self.services.escalate_gap(session, gap)
        self.gap_detector = CapabilityGapDetector(
            capability_registry=capability_registry,
            identity_id=config.identity_id,
            acquisition=acquisition,
            store=self.store,
            delegation=delegation,
        )

    def _compute_observation_fingerprint(self, state: Any) -> str:
        """Compute a deterministic fingerprint of the observed state."""
        import hashlib
        content_parts = []
        if hasattr(state, 'facts') and state.facts:
            content_parts.extend(sorted(state.facts))
        if hasattr(state, 'metadata') and state.metadata:
            for k, v in sorted(state.metadata.items()):
                content_parts.append(f"{k}:{v}")
        if hasattr(state, 'observed_at'):
            content_parts.append(f"observed_at:{state.observed_at}")
        fingerprint = hashlib.sha256("|".join(content_parts).encode()).hexdigest()[:32]
        return fingerprint

    def _update_poll_interval(self, state_changed: bool) -> None:
        """Adaptively adjust poll interval based on state changes."""
        if not self._adaptive_polling:
            return
        if state_changed:
            self._current_poll_interval = max(self._min_poll_interval, self._current_poll_interval * 0.5)
            self._consecutive_unchanged = 0
        else:
            self._consecutive_unchanged += 1
            if self._consecutive_unchanged >= 2:
                self._current_poll_interval = min(self._max_poll_interval, self._current_poll_interval * 1.5)

    def get_current_poll_interval(self) -> float:
        """Return the current adaptive poll interval in seconds."""
        return self._current_poll_interval

    # ── lifecycle helpers ─────────────────────────────────────────────

    # ── lifecycle helpers ─────────────────────────────────────────────

    @property
    def mode(self) -> str:
        if self.store.controls().paused:
            return "paused"
        return self._mode

    def pause(self, note: str = "") -> None:
        controls = self.store.controls()
        controls.paused = True
        if note:
            controls.notes = note
        self.store.set_controls(controls)
        self._provenance(ProvenancePhase.CONTROL, "operator paused", action="pause", result=note)

    def resume(self, note: str = "") -> None:
        controls = self.store.controls()
        controls.paused = False
        if note:
            controls.notes = note
        self.store.set_controls(controls)
        self._provenance(ProvenancePhase.CONTROL, "operator resumed", action="resume", result=note)

    def override(self, **changes: Any) -> dict[str, Any]:
        """Update control constraints (never-contact, budgets, approval categories)."""
        controls = self.store.controls()
        for key, value in changes.items():
            if not hasattr(controls, key):
                raise ValueError(f"Unknown control field: {key}")
            setattr(controls, key, value)
        self.store.set_controls(controls)
        self._provenance(
            ProvenancePhase.CONTROL,
            "human override applied",
            action="override",
            result=", ".join(f"{k}={v}" for k, v in changes.items()),
        )
        return controls.to_dict()

    def set_outbound_mode(self, mode: str) -> dict:
        """Switch the outbound operating mode (observe/autonomous/approval_required)."""
        from .models import normalize_outbound_mode

        controls = self.store.controls()
        prior = controls.outbound_mode
        controls.outbound_mode = normalize_outbound_mode(mode)
        self.store.set_controls(controls)
        self._provenance(
            ProvenancePhase.CONTROL,
            "outbound mode changed",
            action="outbound_mode",
            result=f"{prior} -> {controls.outbound_mode}",
        )
        return controls.to_dict()

    # ── the loop ──────────────────────────────────────────────────────

    def tick(
        self,
        now: Optional[datetime] = None,
        *,
        observe: bool = True,
        detect_needs: bool = True,
        discover: bool = True,
        evaluate: bool = True,
        act: bool = True,
        monitor: bool = True,
        follow_ups: bool = True,
        surfaces: bool = False,
    ) -> TickReport:
        now = now or datetime.now(timezone.utc)
        report = TickReport()

        if self.store.controls().paused:
            self._provenance(ProvenancePhase.CONTROL, "tick skipped: operator paused", action="tick")
            report.skipped.append({"reason": "paused"})
            self._presence_update(
                "set_status",
                PresenceStatus.PAUSED,
                activity="Operator paused by principal",
            )
            return report

        self._presence_update(
            "heartbeat",
            phase=PresenceStatus.OBSERVING.value,
            activity="Observing project state" + (" and external surfaces" if surfaces else ""),
            last_tick_at=now.isoformat(),
        )

        if surfaces:
            report.observed = self._phase_surfaces(report) or report.observed
        
        # Observe and check for state changes
        state_changed = False
        if observe:
            # Capture previous fingerprint
            prev_fingerprint = self._last_observation_fingerprint
            report.observed = self._phase_observe()
            # Compute new fingerprint
            current_state = self.store.project_state()
            if current_state:
                new_fingerprint = self._compute_observation_fingerprint(current_state)
                self._last_observation_fingerprint = new_fingerprint
                if prev_fingerprint is not None and new_fingerprint != prev_fingerprint:
                    state_changed = True
        
        # Adaptive polling interval
        self._update_poll_interval(state_changed)
        
        if detect_needs:
            self._presence_update(
                "set_status",
                PresenceStatus.THINKING,
                activity="Evaluating project needs and opportunities",
            )
            if self.services:
                from core.services.worker import requester_tick
                requester_tick(self.services, self.config.identity_id)
            self._phase_gaps(report)
            report.needs_created = [n.id for n in self.detector.detect(self.store, self.store.project_state())] if self.store.project_state() else []
            if report.needs_created:
                self._provenance(
                    ProvenancePhase.DETECT_NEEDS,
                    f"detected {len(report.needs_created)} new need(s)",
                    action="detect_needs",
                    result=", ".join(report.needs_created),
                )
                self._presence_update(
                    "mark_meaningful_action",
                    f"Detected {len(report.needs_created)} new need(s)",
                )
        if discover:
            report.opportunities_created = self._phase_discover(report)
        if evaluate:
            report.evaluated, report.qualified = self._phase_evaluate()
        if act:
            self._presence_update(
                "set_status",
                PresenceStatus.ACTING,
                activity="Evaluating autonomous action opportunities",
            )
            report.outreach_sent, report.escalations, act_skips = self._phase_act(report)
            report.skipped.extend(act_skips)
        if monitor:
            _, report.replies_sent, monitor_skips = self._phase_monitor()
            report.skipped.extend(monitor_skips)
            principal_results = self._phase_principal(now)
            report.principal_processed = [r["message_id"] for r in principal_results if r.get("outcome") == "completed"]
            report.principal_deferred = [r["message_id"] for r in principal_results if r.get("outcome") != "completed"]
        if follow_ups:
            report.follow_ups_sent, follow_skips = self._phase_follow_ups(now)
            report.skipped.extend(follow_skips)

        self._presence_after_tick(report, state_changed, now)
        return report

    # ── presence ──────────────────────────────────────────────────────

    def _presence_update(self, method: str, *args: Any, **kwargs: Any) -> None:
        """Update presence without ever breaking the operator loop.

        A presence write failure must stay observable (logged) but must never
        crash a tick; a failed write surfaces honestly as staleness on the
        next read.
        """
        if self._presence is None:
            return
        try:
            getattr(self._presence, method)(*args, **kwargs)
        except Exception as exc:
            logger.warning("presence update failed (%s): %s", method, exc)

    def _presence_after_tick(self, report: TickReport, state_changed: bool, now: datetime) -> None:
        """Derive the resting presence state from what this tick actually did."""
        if self._presence is None:
            return
        budget_wait = any(s.get("reason") == "daily_budget_exhausted" for s in report.skipped)
        acted = bool(report.outreach_sent or report.replies_sent or report.follow_ups_sent
                     or report.needs_created or report.opportunities_created)
        if report.escalations:
            status = PresenceStatus.WAITING
            activity = f"Awaiting principal review of {len(report.escalations)} escalation(s)"
            next_planned = "Check for principal authorization decisions"
        elif budget_wait:
            status = PresenceStatus.WAITING
            activity = "Outreach paused: daily budget exhausted"
            next_planned = "Resume outreach after budget reset"
        elif report.errors:
            # _phase_act already recorded DEGRADED with the send failure.
            return
        else:
            status = PresenceStatus.IDLE
            if state_changed:
                activity = "Observed changes to project state"
            elif acted:
                activity = "Awaiting next observation"
            else:
                activity = "No meaningful environmental changes"
            next_planned = f"Observe again in {max(1, int(self._current_poll_interval // 60))} minute(s)"
        self._presence_update(
            "set_status",
            status,
            activity=activity,
            next_planned_action=next_planned,
            next_check_at=(now + timedelta(seconds=self._current_poll_interval)).isoformat(),
            last_tick_at=now.isoformat(),
        )
        self._presence_update("set_counts", opportunity_count=len(self.store.list_opportunities()))
        for surface in self._surfaces:
            if getattr(surface, "name", "") != "culture_commons":
                continue
            try:
                self._presence_update("set_subsystem", "commons_standing", surface.standing_state())
            except Exception as exc:
                logger.warning("presence commons_standing update failed: %s", exc)

    # ── phases ────────────────────────────────────────────────────────

    def _phase_observe(self) -> bool:
        state = self.observer.observe()
        self.store.set_project_state(state)
        self._provenance(
            ProvenancePhase.OBSERVE,
            f"observed project '{state.name}' with {len(state.facts)} fact(s)",
            action="observe_project",
            result=state.summary[:200],
            evidence=state.evidence[:8],
            refs={"project_id": state.project_id},
        )
        return True

    def _phase_surfaces(self, report: TickReport) -> bool:
        """Poll optional external surfaces (opt-in per tick; default off).

        Surfaces never block a normal conversational or operator tick: they are
        wired only when a caller explicitly asks for them.
        """
        observed_any = False
        for surface in self._surfaces:
            try:
                observed = bool((surface.observe() or {}).get("observed"))
            except Exception as exc:  # pragma: no cover - defensive
                report.skipped.append({"surface": surface.name, "reason": "observe_failed", "error": str(exc)})
                self._provenance(
                    ProvenancePhase.OBSERVE,
                    f"surface '{surface.name}' observe failed",
                    action="surface.observe",
                    result=str(exc),
                    refs={"surface": surface.name},
                )
                continue
            if observed:
                observed_any = True
        return observed_any

    def _phase_gaps(self, report: TickReport) -> None:
        gaps = self.gap_detector.check(self.config.required_skills)
        for gap in gaps:
            resolved = self.gap_detector.resolve(gap)
            report.capability_gaps.append(resolved.to_dict())
            self._provenance(
                ProvenancePhase.CONTROL,
                f"capability gap: {gap.required_skill} [{gap.status}]",
                action="capability_gap",
                result=gap.resolution or "unresolved",
                evidence=gap.evidence,
                refs={"required_skill": gap.required_skill, "resolved": gap.resolved, "status": gap.status},
            )
            self._notify_gap(gap)

        if report.capability_gaps:
            unresolved = [g for g in report.capability_gaps if not g.get("resolved")]
            limited = sorted({g.get("required_skill", "") for g in unresolved if g.get("required_skill")})
            required = list(getattr(self.config, "required_skills", []) or [])
            healthy = max(0, len(required) - len(limited))
            # Permission-limited skills are reported, never hidden — but on
            # their own they do not degrade global health. Only a material
            # failure (e.g. a failed send, marked "degraded" in _phase_act)
            # does that. Reconciling the marker every tick also self-heals
            # stale markers from earlier runs.
            self._presence_update("set_capability_summary", healthy=healthy, limited=limited)
            if not unresolved:
                self._presence_update("set_subsystem", "capability_health", "healthy")
                skill = report.capability_gaps[-1].get("required_skill", "")
                self._presence_update("mark_meaningful_action", f"Resolved capability gap: {skill}")
            else:
                self._presence_update("set_subsystem", "capability_health", "limited")

    def _notify_gap(self, gap: "CapabilityGap") -> None:
        """Notify the principal about gaps that need a human decision, once per
        (kind, skill) — re-ticking must not re-notify."""
        if gap.resolved:
            return
        if gap.status == CapabilityStatus.INSTALLED_PERMISSION_MISSING.value:
            kind, summary = "permission_required", (
                f"Required skill '{gap.required_skill}' is installed but permission is denied: {gap.reason}"
            )
        elif gap.status == CapabilityStatus.AVAILABLE_NOT_INSTALLED.value:
            kind, summary = "capability_available", (
                f"A built-in capability provides required skill '{gap.required_skill}' but it is not installed"
            )
        else:
            return
        existing = self.store.list_notifications()
        for entry in existing:
            if entry.kind != kind:
                continue
            if str((entry.refs or {}).get("required_skill", "")) == gap.required_skill:
                return
        self._notify(kind=kind, summary=summary, refs={
            "required_skill": gap.required_skill, "capability_gap_status": gap.status,
        })

    def _phase_discover(self, report: TickReport) -> list[str]:
        from .models import NeedStatus

        created: list[str] = []
        open_needs = self.store.list_needs(status=NeedStatus.OPEN)[: self.config.max_needs_per_tick]
        for need in open_needs:
            for opportunity in self.discoverer.discover(self.store, need):
                created.append(opportunity.id)
                self._provenance(
                    ProvenancePhase.DISCOVER,
                    f"discovered opportunity '{opportunity.target_name or opportunity.organization}'",
                    action="discover",
                    result=opportunity.id,
                    evidence=opportunity.evidence[:6],
                    refs={"need_id": need.id, "opportunity_id": opportunity.id},
                )
        if created:
            self._provenance(
                ProvenancePhase.DISCOVER,
                f"discovered {len(created)} new opportunity(ies)",
                action="discover",
                result=", ".join(created),
            )
        return created

    def _phase_evaluate(self) -> tuple[list[str], list[str]]:
        evaluated: list[str] = []
        qualified: list[str] = []
        for opportunity in self.store.list_opportunities(status=OpportunityStatus.DISCOVERED):
            need = self.store.get_need(opportunity.need_id)
            if need is None:
                opportunity.status = OpportunityStatus.REJECTED
                self.store.update_opportunity(opportunity)
                continue
            evaluation = self.evaluator.evaluate(opportunity, need)
            self.store.save_evaluation(evaluation)
            evaluated.append(opportunity.id)
            if evaluation.recommendation == "pursue":
                opportunity.status = OpportunityStatus.QUALIFIED
                qualified.append(opportunity.id)
            elif evaluation.recommendation == "reject":
                opportunity.status = OpportunityStatus.REJECTED
            else:
                opportunity.status = OpportunityStatus.EVALUATING
            self.store.update_opportunity(opportunity)
            self._provenance(
                ProvenancePhase.EVALUATE,
                f"evaluated '{opportunity.target_name or opportunity.organization}': {evaluation.recommendation} (score {evaluation.score})",
                action="evaluate",
                result=evaluation.recommendation,
                evidence=evaluation.evidence[:6],
                refs={"opportunity_id": opportunity.id, "score": evaluation.score},
            )
        return evaluated, qualified

    def _phase_act(self, report: TickReport) -> tuple[list[str], list[str], list[dict[str, Any]]]:
        sent: list[str] = []
        escalations: list[str] = []
        skips: list[dict[str, Any]] = []
        controls = self.store.controls()
        budget = self.store.budget()

        qualified = [
            o for o in self.store.list_opportunities(status=OpportunityStatus.QUALIFIED)
        ]
        qualified.sort(
            key=lambda o: (
                self.store.get_evaluation(o.id).score if self.store.get_evaluation(o.id) else 0.0
            ),
            reverse=True,
        )

        for opportunity in qualified[: self.config.max_outreach_per_tick]:
            decision = self.duplicates.evaluate(opportunity)
            if not decision.allowed:
                opportunity.status = OpportunityStatus.CLOSED
                self.store.update_opportunity(opportunity)
                skips.append({"opportunity_id": opportunity.id, "reason": decision.code})
                self._provenance(
                    ProvenancePhase.PLAN,
                    "outreach blocked by duplicate-contact policy",
                    action="duplicate_check",
                    result=decision.reason,
                    refs={"opportunity_id": opportunity.id, "code": decision.code},
                )
                continue

            if not opportunity.contact_email:
                skips.append({"opportunity_id": opportunity.id, "reason": "no_contact_email"})
                self._provenance(
                    ProvenancePhase.PLAN,
                    "no contact email discovered; cannot send individualized outreach",
                    action="outreach_blocked",
                    result="no_contact_email",
                    refs={"opportunity_id": opportunity.id},
                )
                continue

            if budget.cold_outreach >= controls.max_cold_outreach_per_day:
                skips.append({"opportunity_id": opportunity.id, "reason": "daily_budget_exhausted"})
                self._presence_update(
                    "set_status",
                    PresenceStatus.WAITING,
                    activity="Outreach paused: daily budget exhausted",
                )
                self._provenance(
                    ProvenancePhase.CONTROL,
                    "daily cold-outreach budget exhausted",
                    action="budget",
                    result=f"{budget.cold_outreach}/{controls.max_cold_outreach_per_day}",
                )
                break

            if float(opportunity.confidence or 0.0) <= 0 and not opportunity.test_candidate:
                # Defense in depth: an autonomous operator never pursues a candidate
                # with no source confidence unless explicitly marked test_candidate.
                skips.append({"opportunity_id": opportunity.id, "reason": "confidence_zero"})
                self._provenance(
                    ProvenancePhase.PLAN,
                    "outreach skipped: source confidence is zero",
                    action="confidence_gate",
                    result="candidate not marked test_candidate=true",
                    refs={"opportunity_id": opportunity.id, "confidence": opportunity.confidence},
                )
                continue

            need = self.store.get_need(opportunity.need_id)
            if need is None:
                continue
            brief = OutreachBrief.from_opportunity(
                opportunity, need,
                sender_name=self.config.sender_name,
                transparency=self.config.transparency,
                signature=self.config.signature,
            )
            subject, body = self.composer.compose(brief, adapter=self._adapter, identity=self._identity)

            auth = AuthorityPolicy(controls).evaluate(
                "send cold outreach about a program",
                category=opportunity.category,
                content=f"{subject}\n{body}",
                mode="commitment",
            )

            if not self._allowlist_allows(opportunity.contact_email):
                skips.append({"opportunity_id": opportunity.id, "reason": "not_in_allowlist"})
                self._provenance(
                    ProvenancePhase.PLAN,
                    "cold outreach gated by recipient allowlist",
                    action="allowlist",
                    result=f"recipient {opportunity.contact_email} is not allowlisted",
                    refs={"opportunity_id": opportunity.id, "recipient": opportunity.contact_email},
                )
                continue

            message = Message(
                relationship_id="",
                direction=MessageDirection.OUTBOUND,
                subject=subject,
                body=body,
                status=MessageStatus.DRAFT,
                need_id=need.id,
                opportunity_id=opportunity.id,
            )

            relationship = Relationship(
                display_name=opportunity.target_name or opportunity.organization,
                organization=opportunity.organization,
                email=opportunity.contact_email,
                purpose=self.config.purpose,
                need_id=need.id,
                opportunity_id=opportunity.id,
                status=RelationshipStatus.NEW,
            )

            approval_mode = controls.outbound_mode == "approval_required"
            if auth.requires_human or approval_mode or self._transport is None:
                reason = (
                    auth.reason if auth.requires_human else
                    "outbound_mode requires human approval" if approval_mode else
                    "no transport configured (dry-run)"
                )
                message.status = MessageStatus.AWAITING_AUTHORIZATION
                message.authorization = "awaiting_human_authorization"
                store_rel = self.store.add_relationship(relationship)
                store_rel.status = RelationshipStatus.AWAITING_AUTHORIZATION
                store_rel.next_action = "human authorization required"
                self.store.update_relationship(store_rel)
                message.relationship_id = store_rel.id
                self.store.append_message(message)
                escalations.append(message.id)
                self._presence_update("mark_meaningful_action", "Escalated outreach for human authorization")
                self._presence_update(
                    "set_status",
                    PresenceStatus.WAITING,
                    activity="Escalated outreach: awaiting human authorization",
                )
                self._notify(kind="escalation", summary=f"outreach requires human authorization ({auth.reason})",
                             refs={"message_id": message.id, "opportunity_id": opportunity.id})
                self._provenance(
                    ProvenancePhase.ESCALATE,
                    "outreach requires human authorization",
                    action="escalate",
                    result=reason,
                    evidence=[f"matched:{auth.matched_terms}"] if auth.matched_terms else [f"mode:{controls.outbound_mode}"],
                    refs={"message_id": message.id, "opportunity_id": opportunity.id, "notify": "principal:escalation"},
                )
                continue

            if controls.outbound_mode == "observe":
                if self._has_would_send(opportunity_id=opportunity.id):
                    skips.append({"opportunity_id": opportunity.id, "reason": "would_send_already_recorded"})
                    continue
                message.status = MessageStatus.WOULD_SEND
                message.authorization = "observe_would_send"
                message.evidence = [f"policy:{auth.reason}"]
                self.store.append_message(message)
                self._provenance(
                    ProvenancePhase.PLAN,
                    "outreach drafted in observation mode (not sent)",
                    action="would_send",
                    result=auth.reason,
                    evidence=[f"mode=observe", f"to={opportunity.contact_email}"],
                    refs={"message_id": message.id, "opportunity_id": opportunity.id},
                )
                continue

            if budget.cold_outreach >= controls.max_cold_outreach_per_day:
                skips.append({"opportunity_id": opportunity.id, "reason": "daily_budget_exhausted"})
                self._presence_update(
                    "set_status",
                    PresenceStatus.WAITING,
                    activity="Outreach paused: daily budget exhausted",
                )
                self._provenance(
                    ProvenancePhase.CONTROL,
                    "daily cold-outreach budget exhausted",
                    action="budget",
                    result=f"{budget.cold_outreach}/{controls.max_cold_outreach_per_day}",
                )
                break

            send_result = self._send(
                to=opportunity.contact_email,
                subject=subject,
                body=body,
            )
            if not send_result.get("ok"):
                message.status = MessageStatus.FAILED
                message.evidence = [f"send_error:{send_result.get('error')}"]
                store_rel = self.store.add_relationship(relationship)
                message.relationship_id = store_rel.id
                self.store.append_message(message)
                report.errors.append({"message_id": message.id, "error": send_result.get("error")})
                self._presence_update("set_subsystem", "capability_health", "degraded")
                self._presence_update(
                    "set_status",
                    PresenceStatus.DEGRADED,
                    activity=f"Outreach send failed: {send_result.get('error')}",
                )
                self._provenance(
                    ProvenancePhase.ACT,
                    "outreach send failed",
                    action="send",
                    result=str(send_result.get("error")),
                    refs={"message_id": message.id, "opportunity_id": opportunity.id},
                )
                continue

            message.external_id = str(send_result.get("external_id", ""))
            message.thread_id = str(send_result.get("thread_id", ""))
            message.status = MessageStatus.SENT
            message.sent_at = utcnow().isoformat()
            message.authorization = "autonomous_outreach"
            message.evidence = list(send_result.get("evidence", []))
            store_rel = self.store.add_relationship(relationship)
            store_rel.status = RelationshipStatus.OUTREACH_SENT
            store_rel.first_contacted_at = message.sent_at
            store_rel.last_outbound_at = message.sent_at
            if message.thread_id:
                store_rel.thread_ids.append(message.thread_id)
            store_rel.message_ids.append(message.id)
            store_rel.next_action = "await reply; follow up if quiet"
            self.store.update_relationship(store_rel)
            message.relationship_id = store_rel.id
            self.store.append_message(message)

            opportunity.status = OpportunityStatus.CONTACTED
            self.store.update_opportunity(opportunity)
            self.store.record_usage("cold_outreach")
            budget = self.store.budget()
            sent.append(message.id)
            self._presence_update(
                "set_status",
                PresenceStatus.ACTING,
                activity=f"Sent individualized outreach to '{relationship.display_name}'",
            )
            self._presence_update(
                "mark_meaningful_action",
                f"Sent individualized outreach to '{relationship.display_name}'",
            )
            self._provenance(
                ProvenancePhase.ACT,
                f"sent individualized outreach to '{relationship.display_name}'",
                action="send",
                result=message.external_id or "sent",
                evidence=message.evidence[:5],
                refs={"message_id": message.id, "opportunity_id": opportunity.id, "relationship_id": store_rel.id},
            )
        return sent, escalations, skips

    def _phase_monitor(self) -> tuple[list[InboundResult], list[str], list[dict[str, Any]]]:
        results: list[InboundResult] = []
        replies: list[str] = []
        skips: list[dict[str, Any]] = []
        if self._transport is None or not hasattr(self._transport, "fetch_inbox"):
            return results, replies, skips
        try:
            incoming, new_cursor = self._fetch_inbox()
        except Exception as exc:  # pragma: no cover - defensive
            skips.append({"reason": "inbox_fetch_failed", "error": str(exc)})
            return results, replies, skips
        if new_cursor is not None:
            self.store.set_mailbox_cursor(new_cursor)

        for item in incoming:
            external_id = str(item.get("external_id", "") or item.get("id", ""))
            if external_id and self._already_processed(external_id):
                continue
            relationship_id = ""
            raw_sender = str(item.get("from", item.get("sender_email", "")) or "unknown")
            display = raw_sender
            body_text = str(item.get("body", item.get("text", "")))
            result = self.monitor.ingest(
                self.store,
                sender_email=raw_sender,
                body=body_text,
                raw_body=str(item.get("raw_body", body_text)),
                subject=str(item.get("subject", "")),
                thread_id=str(item.get("thread_id", "")),
                external_id=external_id,
                in_reply_to=str(item.get("in_reply_to", "")),
                references=list(item.get("references") or []),
            )
            results.append(result)
            if result.responded and result.relationship is not None:
                replies.append(result.relationship.id)
                self._presence_update(
                    "mark_meaningful_action",
                    f"Replied to inbound from '{result.relationship.display_name}'",
                )
            if result.relationship is not None:
                relationship_id = result.relationship.id
                # Name real trusted senders by their relationship, but always
                # surface the *actual* address when the message is automated,
                # quarantined (thread intrusion), or from any sender mismatch.
                if result.disposition in (InboundDisposition.TRUSTED_THREAD, InboundDisposition.APPROVED_SENDER) and (
                    _norm(raw_sender) == _norm(result.relationship.email or "")
                ):
                    display = result.relationship.display_name
            if result.disposition is not None:
                display = f"{display} [{result.disposition.value}]"
            self._provenance(
                ProvenancePhase.MONITOR if not result.escalated else ProvenancePhase.ESCALATE,
                f"inbound from '{display}': {result.treated_as}",
                action="monitor",
                result=result.reason,
                refs={"relationship_id": relationship_id, "message_id": result.message.id},
            )
        return results, replies, skips

    def _fetch_inbox(self) -> tuple[list[dict[str, Any]], Optional[dict[str, Any]]]:
        """Fetch the inbox, advancing the durable high-water-mark cursor when the
        transport supports cursor-based delivery (so historical mail is never
        reprocessed after a restart or a first-run backfill)."""
        fetcher = getattr(self._transport, "fetch_inbox_with_cursor", None)
        if fetcher is None:
            return list(self._transport.fetch_inbox() or []), None
        cursor = self.store.mailbox_cursor()
        result = fetcher(cursor=cursor.to_dict() if cursor else None)
        messages = list(result.get("messages") or [])
        new_cursor = result.get("cursor")
        return messages, new_cursor

    def _phase_principal(self, now: datetime) -> list[dict[str, Any]]:
        """Process queued principal (Aster Control) messages as the operator.

        Every transition is written by actual execution: RECEIVED/QUEUED →
        PROCESSING → COMPLETED, or DEFERRED / PERMISSION_REQUIRED / FAILED.
        A substantive reply REQUIRES a working model runtime; without one the
        message is DEFERRED, never answered by a template masquerading as
        Aster. Existing permissions, budgets, and escalation rules remain
        authoritative — the phone UI cannot bypass them.
        """
        from .principal import (
            CONTROL_CHANNEL,
            CommandClass,
            build_principal_context,
            classify_command,
            pending_principal_messages,
            thread_messages,
        )

        outcomes: list[dict[str, Any]] = []
        # Cross-process visibility: the control server persists inbound
        # principal messages through its own store instance. Refresh before
        # scanning or this long-lived process would never see them.
        self.store.refresh_messages()
        self.store.refresh_relationships()
        pending = pending_principal_messages(self.store)
        if not pending:
            return outcomes
        self._presence_update(
            "set_status", PresenceStatus.THINKING,
            activity=f"Processing {len(pending)} principal message(s)",
        )
        for inbound in pending:
            outcomes.append(self._process_principal_message(inbound, now))
        return outcomes

    def _process_principal_message(self, inbound: Message, now: datetime) -> dict[str, Any]:
        from .principal import (
            CONTROL_CHANNEL,
            CommandClass,
            build_principal_context,
            classify_command,
            thread_messages,
        )

        inbound.status = MessageStatus.PROCESSING
        self.store.update_message(inbound)
        command = classify_command(inbound.body or "")

        if command in (CommandClass.EXECUTE, CommandClass.COMMUNICATE):
            gate = self._principal_policy_gate(inbound, command)
            if gate is not None:
                return gate

        if self._adapter is None:
            return self._settle_principal(
                inbound, MessageStatus.DEFERRED,
                reason="no model runtime configured; substantive replies require a working model",
                notify=False,
            )
        response_text, generation = self._generate_principal_response(inbound, command)
        if response_text is None:
            return self._settle_principal(
                inbound, MessageStatus.DEFERRED,
                reason=generation.get("detail", "model unavailable; will retry on a later tick"),
                notify=False,
            )
        relationship = self.store.get_relationship(inbound.relationship_id)
        response = Message(
            relationship_id=inbound.relationship_id,
            direction=MessageDirection.OUTBOUND,
            channel=CONTROL_CHANNEL,
            subject="",
            body=response_text,
            sent_at=utcnow().isoformat(),
            thread_id=inbound.thread_id or "principal",
            in_reply_to=inbound.id,
            status=MessageStatus.SENT,
            authorization="principal:response",
            generation=generation,
        )
        self.store.append_message(response)
        if relationship is not None:
            relationship.message_ids.append(response.id)
            relationship.last_outbound_at = response.sent_at
            relationship.next_action = "awaiting principal message"
            self.store.update_relationship(relationship)
        self._provenance(
            ProvenancePhase.PRINCIPAL,
            "replied to principal via Aster Control",
            action="principal.respond",
            result=f"command={command.value} mode={generation.get('mode', '')}",
            refs={"message_id": inbound.id, "response_id": response.id,
                  "relationship_id": inbound.relationship_id},
        )
        self._presence_update(
            "mark_meaningful_action", "Replied to Arsène via Aster Control"
        )
        return self._settle_principal(
            inbound, MessageStatus.COMPLETED,
            reason=f"responded ({command.value})",
            response_id=response.id,
            notify=False,
        )

    def _principal_policy_gate(self, inbound: Message, command: CommandClass) -> Optional[dict[str, Any]]:
        """Enforce existing policy on COMMUNICATE/EXECUTE instructions.

        Returns None when the instruction may proceed to response generation
        (which for these classes includes executing the allowed action first);
        otherwise settles the message as PERMISSION_REQUIRED and returns the
        outcome. The phone UI never bypasses IdentityOS permissions.
        """
        from .principal import CommandClass

        controls = self.store.controls()
        decision = AuthorityPolicy(controls).evaluate(
            f"principal instruction ({command.value}): {(inbound.body or '')[:200]}",
            category="principal_instruction",
            content=inbound.body or "",
            mode="commitment",
        )
        if decision.requires_human:
            self._notify(
                kind="principal_instruction",
                summary=f"principal instruction requires authorization ({command.value})",
                refs={"message_id": inbound.id},
            )
            self._provenance(
                ProvenancePhase.PRINCIPAL,
                "principal instruction held for authorization",
                action="principal.gate",
                result=decision.reason,
                refs={"message_id": inbound.id, "command": command.value,
                      "notify": "principal:instruction"},
            )
            return self._settle_principal(
                inbound, MessageStatus.PERMISSION_REQUIRED,
                reason=decision.reason or "authorization required by policy",
                notify=False,
            )
        if command is CommandClass.EXECUTE:
            lowered = (inbound.body or "").strip().lower()
            if re.search(r"\bpause\b", lowered) and "operator" in lowered:
                self.pause(note="principal instruction via Aster Control")
                return None
            if re.search(r"\bresume\b", lowered) and "operator" in lowered:
                self.resume(note="principal instruction via Aster Control")
                return None
            return self._settle_principal(
                inbound, MessageStatus.DEFERRED,
                reason="policy allows autonomous action but no safe executor is wired "
                       "for this instruction; recorded for principal review",
                notify=False,
            )
        return None

    def _generate_principal_response(
        self, inbound: Message, command: CommandClass
    ) -> tuple[Optional[str], dict[str, Any]]:
        from .principal import build_principal_context, thread_messages

        presence_summary = ""
        if self._presence is not None:
            try:
                view = self._presence.public_view()
                presence_summary = (
                    f"activity={view.get('status')}: {view.get('activity')}; "
                    f"last heartbeat {view.get('heartbeat_age_seconds')}s ago; "
                    f"last meaningful action: {view.get('last_meaningful_action')}; "
                    f"commons={view.get('commons_standing')}; "
                    f"opportunities={view.get('opportunity_count')}"
                )
            except Exception:
                presence_summary = ""
        history = thread_messages(self.store, limit=10)
        context, user_input = build_principal_context(
            identity_name=self.config.sender_name or "Aster",
            objective=self.config.purpose,
            history=history,
            command=command,
            presence_summary=presence_summary,
        )
        from core.self_knowledge import SelfKnowledge, needs_grounding, grounding_context, guard_response
        reader = SelfKnowledge(self.storage, self.config.identity_id,
                               scrub=self._secret_store.scrub if self._secret_store else None)
        snapshot = reader.snapshot() if needs_grounding(inbound.body) else None
        if snapshot is not None:
            context += grounding_context(snapshot)
        try:
            text = self._adapter.generate(context, user_input, self._identity)
        except Exception as exc:
            return None, {"mode": "unavailable", "detail": f"model call failed: {exc}"}
        text = (text or "").strip()
        if not text:
            return None, {"mode": "unavailable", "detail": "model returned an empty response"}
        metadata = self._generation_metadata()
        if snapshot is not None:
            text, grounding = guard_response(text, snapshot, current=reader.snapshot())
            metadata['grounding'] = grounding
            if grounding['guard'] == 'fallback':
                metadata['mode'] = 'runtime_grounded_fallback'
        return text, metadata

    def _generation_metadata(self) -> dict[str, Any]:
        # Attribute the provider that ACTUALLY generated. A ChainAdapter
        # records its winning leaf in last_selection; naively naming the
        # first chain entry misattributes fall-through responses.
        selection = getattr(self._adapter, "last_selection", None) or {}
        if selection.get("provider"):
            return {
                "mode": "identity_model_generation",
                "adapter": selection.get("provider", ""),
                "model": selection.get("model", ""),
                "latency_ms": selection.get("latency_ms"),
            }
        try:
            from adapters.configuration import describe_adapter

            described = describe_adapter(self._adapter)
            providers = described.get("providers") or []
            first = providers[0] if providers else {}
            return {
                "mode": "identity_model_generation",
                "adapter": first.get("adapter", type(self._adapter).__name__),
                "model": first.get("model", str(getattr(self._adapter, "model", "") or "")),
            }
        except Exception:
            return {
                "mode": "identity_model_generation",
                "adapter": type(self._adapter).__name__,
                "model": str(getattr(self._adapter, "model", "") or ""),
            }

    def _settle_principal(
        self,
        inbound: Message,
        status: MessageStatus,
        *,
        reason: str = "",
        response_id: str = "",
        notify: bool = False,
    ) -> dict[str, Any]:
        from .principal import CommandClass, classify_command

        command = classify_command(inbound.body or "")
        inbound.status = status
        if response_id:
            inbound.evidence = list(inbound.evidence or []) + [f"response:{response_id}"]
        if reason and status is not MessageStatus.COMPLETED:
            inbound.evidence = list(inbound.evidence or []) + [reason[:300]]
        self.store.update_message(inbound)
        if notify:
            self._notify(
                kind="principal_instruction",
                summary=f"principal message {status.value}: {reason[:140]}",
                refs={"message_id": inbound.id},
            )
        self._provenance(
            ProvenancePhase.PRINCIPAL,
            f"principal message {status.value}",
            action="principal.settle",
            result=reason[:300],
            refs={"message_id": inbound.id, "command": command.value,
                  "response_id": response_id},
        )
        return {
            "message_id": inbound.id,
            "outcome": "completed" if status is MessageStatus.COMPLETED else status.value,
            "command": command.value,
            "response_id": response_id,
            "reason": reason,
        }

    def _phase_follow_ups(self, now: datetime) -> tuple[list[str], list[dict[str, Any]]]:
        sent: list[str] = []
        skips: list[dict[str, Any]] = []
        controls = self.store.controls()
        for follow_up in self.follow_ups.plan(now):
            self._provenance(
                ProvenancePhase.FOLLOW_UP,
                "scheduled follow-up",
                action="schedule_follow_up",
                result=follow_up.reason,
                refs={"follow_up_id": follow_up.id, "relationship_id": follow_up.relationship_id},
            )

        for follow_up in self.follow_ups.due(now):
            relationship = self.store.get_relationship(follow_up.relationship_id)
            if relationship is None or relationship.opted_out or relationship.status in (
                RelationshipStatus.DECLINED, RelationshipStatus.OPTED_OUT
            ):
                self.follow_ups.cancel(relationship, "relationship closed") if relationship else None
                continue
            subject, body = self.composer.compose_follow_up(
                relationship, adapter=self._adapter, identity=self._identity
            )
            auth = AuthorityPolicy(controls).evaluate(
                "send follow-up", category=relationship.purpose, content=f"{subject}\n{body}", mode="commitment"
            )
            if auth.requires_human:
                skips.append({"follow_up_id": follow_up.id, "reason": "requires_authorization"})
                continue
            thread = relationship.thread_ids[-1] if relationship.thread_ids else ""

            if controls.outbound_mode == "approval_required":
                if self._has_would_send(relationship_id=follow_up.relationship_id, kind="follow_up_approval"):
                    skips.append({"follow_up_id": follow_up.id, "reason": "already_awaiting_authorization"})
                    continue
                message = Message(
                    relationship_id=relationship.id,
                    direction=MessageDirection.OUTBOUND,
                    subject=subject,
                    body=body,
                    status=MessageStatus.AWAITING_AUTHORIZATION,
                    authorization="awaiting_human_authorization",
                    thread_id=thread,
                )
                self.store.append_message(message)
                relationship.message_ids.append(message.id)
                relationship.status = RelationshipStatus.AWAITING_AUTHORIZATION
                relationship.next_action = "human authorization required"
                self.store.update_relationship(relationship)
                skips.append({"follow_up_id": follow_up.id, "reason": "outbound_mode_requires_approval"})
                self._notify(kind="escalation", summary="follow-up requires human authorization",
                             refs={"message_id": message.id, "follow_up_id": follow_up.id, "relationship_id": relationship.id})
                self._provenance(
                    ProvenancePhase.ESCALATE,
                    "follow-up requires human authorization",
                    action="escalate",
                    result="outbound_mode requires human approval",
                    refs={"message_id": message.id, "follow_up_id": follow_up.id, "relationship_id": relationship.id, "notify": "principal:escalation"},
                )
                continue

            if controls.outbound_mode == "observe":
                if self._has_would_send(relationship_id=follow_up.relationship_id, kind="follow_up"):
                    skips.append({"follow_up_id": follow_up.id, "reason": "would_send_already_recorded"})
                    continue
                message = Message(
                    relationship_id=relationship.id,
                    direction=MessageDirection.OUTBOUND,
                    subject=subject,
                    body=body,
                    status=MessageStatus.WOULD_SEND,
                    authorization="observe_would_send:follow_up",
                    thread_id=thread,
                )
                self.store.append_message(message)
                relationship.message_ids.append(message.id)
                self.store.update_relationship(relationship)
                self._provenance(
                    ProvenancePhase.FOLLOW_UP,
                    "follow-up drafted in observation mode (not sent)",
                    action="would_send",
                    result="mode=observe",
                    refs={"message_id": message.id, "follow_up_id": follow_up.id, "relationship_id": relationship.id},
                )
                continue

            if self._transport is None:
                skips.append({"follow_up_id": follow_up.id, "reason": "dry_run"})
                continue
            if self.store.budget().follow_ups >= controls.max_follow_ups_per_target * max(controls.max_cold_outreach_per_day, 1):
                skips.append({"follow_up_id": follow_up.id, "reason": "daily_budget_exhausted"})
                self._presence_update(
                    "set_status",
                    PresenceStatus.WAITING,
                    activity="Follow-ups paused: daily budget exhausted",
                )
                break
            result = self._send(
                to=relationship.email,
                subject=subject,
                body=body,
                thread_id=thread,
            )
            if not result.get("ok"):
                skips.append({"follow_up_id": follow_up.id, "reason": result.get("error", "send_failed")})
                continue
            message = Message(
                relationship_id=relationship.id,
                direction=MessageDirection.OUTBOUND,
                subject=subject,
                body=body,
                sent_at=utcnow().isoformat(),
                status=MessageStatus.SENT,
                authorization="autonomous_follow_up",
                external_id=str(result.get("external_id", "")),
                thread_id=str(result.get("thread_id", "")),
            )
            self.store.append_message(message)
            relationship.message_ids.append(message.id)
            relationship.last_outbound_at = message.sent_at
            self.store.update_relationship(relationship)
            self.follow_ups.complete(follow_up, now=now)
            self.store.record_usage("follow_ups")
            sent.append(message.id)
            self._presence_update(
                "mark_meaningful_action",
                f"Sent follow-up to '{relationship.display_name}'",
            )
            self._provenance(
                ProvenancePhase.FOLLOW_UP,
                f"sent follow-up to '{relationship.display_name}'",
                action="send_follow_up",
                result=message.external_id or "sent",
                refs={"message_id": message.id, "relationship_id": relationship.id},
            )
        return sent, skips

    # ── authorization queue ───────────────────────────────────────────

    def pending_authorizations(self) -> list[dict[str, Any]]:
        pending: list[dict[str, Any]] = []
        for message in self.store.list_messages():
            if message.status is MessageStatus.AWAITING_AUTHORIZATION:
                relationship = self.store.get_relationship(message.relationship_id)
                pending.append({
                    "message_id": message.id,
                    "subject": message.subject,
                    "body": message.body,
                    "opportunity_id": message.opportunity_id,
                    "need_id": message.need_id,
                    "recipient": relationship.email if relationship else "",
                    "relationship_id": relationship.id if relationship else "",
                })
        return pending

    def authorize(self, message_id: str, *, approved: bool = True, note: str = "", approver: str = "principal") -> dict[str, Any]:
        message = self.store.get_message(message_id)
        if message is None:
            return {"ok": False, "error": f"unknown message: {message_id}"}
        if message.status is not MessageStatus.AWAITING_AUTHORIZATION:
            return {"ok": False, "error": f"message is not awaiting authorization: {message.status.value}"}

        relationship = self.store.get_relationship(message.relationship_id)
        if not approved:
            message.status = MessageStatus.FAILED
            message.authorization = f"human_rejected:{note}" if note else "human_rejected"
            self.store.update_message(message)
            if relationship is not None:
                relationship.status = RelationshipStatus.NEW
                relationship.next_action = "human rejected outreach"
                self.store.update_relationship(relationship)
            self._notify(kind="authorization", summary="authorization request rejected by principal",
                         refs={"message_id": message.id})
            self._provenance(
                ProvenancePhase.AUTHORIZE,
                "human rejected outreach",
                action="authorize",
                result=f"{note or 'rejected'} (approver={approver})",
                refs={"message_id": message.id, "decision": "reject", "approver": approver,
                      "scope": {"relationship_id": message.relationship_id}, "authorization": message.authorization},
            )
            return {"ok": True, "status": "rejected", "message_id": message.id}

        if relationship is None:
            return {"ok": False, "error": "message has no relationship"}
        if self._transport is None:
            return {"ok": False, "error": "no transport configured; cannot send"}

        result = self._send(
            to=relationship.email,
            subject=message.subject,
            body=message.body,
            thread_id=message.thread_id or (relationship.thread_ids[-1] if relationship.thread_ids else ""),
            in_reply_to=message.in_reply_to,
            references=message.references,
        )
        if not result.get("ok"):
            message.status = MessageStatus.FAILED
            message.evidence = [f"send_error:{result.get('error')}"]
            self.store.update_message(message)
            return {"ok": False, "error": result.get("error", "send failed")}

        message.status = MessageStatus.SENT
        message.sent_at = utcnow().isoformat()
        message.external_id = str(result.get("external_id", ""))
        message.thread_id = str(result.get("thread_id", ""))
        message.authorization = f"human_authorized:{note}:{message_id}" if note else f"human_authorized:{message_id}"
        self.store.update_message(message)
        relationship.status = RelationshipStatus.OUTREACH_SENT
        relationship.first_contacted_at = message.sent_at
        relationship.last_outbound_at = message.sent_at
        if message.thread_id:
            relationship.thread_ids.append(message.thread_id)
        relationship.next_action = "await reply; follow up if quiet"
        self.store.update_relationship(relationship)
        self.store.record_usage("cold_outreach")
        self._notify(kind="authorization", summary="authorization request approved; message sent",
                     refs={"message_id": message.id, "external_id": message.external_id})
        self._provenance(
            ProvenancePhase.AUTHORIZE,
            "human authorized outreach; sent",
            action="authorize",
            result=f"{note or 'approved'} (approver={approver})",
            refs={"message_id": message.id, "relationship_id": relationship.id, "decision": "approve",
                  "approver": approver,
                  "scope": {"relationship_id": relationship.id, "opportunity_id": message.opportunity_id,
                            "need_id": message.need_id, "outbound_mode": self.store.controls().outbound_mode},
                  "authorization": message.authorization},
        )
        return {"ok": True, "status": "sent", "message_id": message.id, "external_id": message.external_id}

    # ── inspection ────────────────────────────────────────────────────

    def status(self) -> dict[str, Any]:
        state = self.store.project_state()
        needs = self.store.list_needs()
        opportunities = self.store.list_opportunities()
        relationships = self.store.list_relationships()
        messages = self.store.list_messages()
        return {
            "identity_id": self.config.identity_id,
            "mode": self.mode,
            "project": state.to_dict() if state else None,
            "needs": {
                "total": len(needs),
                "open": sum(1 for n in needs if n.status.value == "open"),
                "items": [n.to_dict() for n in needs],
            },
            "opportunities": {
                "total": len(opportunities),
                "by_status": _count_by(o.status.value for o in opportunities),
                "items": [o.to_dict() for o in opportunities],
            },
            "relationships": {
                "total": len(relationships),
                "by_status": _count_by(r.status.value for r in relationships),
                "items": [r.to_dict() for r in relationships],
            },
            "messages": {
                "total": len(messages),
                "outbound": sum(1 for m in messages if m.direction.value == "outbound"),
                "inbound": sum(1 for m in messages if m.direction.value == "inbound"),
            },
            "pending_authorizations": len(self.pending_authorizations()),
            "notifications": {"unread": self.store.unread_notification_count()},
            "would_send": sum(1 for m in messages if m.status is MessageStatus.WOULD_SEND),
            "budget": self.store.budget().to_dict(),
            "controls": self.store.controls().to_dict(),
            "provenance_count": len(self.store.list_provenance()),
        }

    def provenance(self, limit: int = 50) -> list[dict[str, Any]]:
        return [p.to_dict() for p in self.store.list_provenance(limit=limit)]

    def would_send(self, limit: int = 50) -> list[dict[str, Any]]:
        """Composed messages recorded in observation mode but never transmitted."""
        items = [m.to_dict() for m in self.store.list_messages() if m.status is MessageStatus.WOULD_SEND]
        return items[-limit:]

    # ── internals ─────────────────────────────────────────────────────

    def _allowlist_allows(self, email: str) -> bool:
        """Gate cold outreach against the recipient allowlist (exact or @domain)."""
        controls = self.store.controls()
        allow = [entry for entry in controls.allowed_external_recipients if entry and str(entry).strip()]
        if not allow:
            return True
        target = _norm(email)
        if not target:
            return False
        for entry in allow:
            pattern = _norm(entry)
            if not pattern:
                continue
            if pattern == target:
                return True
            if pattern.startswith("@") and target.endswith(pattern):
                return True
        return False

    def _has_would_send(self, *, opportunity_id: str = "", relationship_id: str = "", kind: str = "") -> bool:
        """Already-recorded observation draft for this target / relationship."""
        for message in self.store.list_messages():
            if message.status is not MessageStatus.WOULD_SEND:
                continue
            if opportunity_id and message.opportunity_id == opportunity_id:
                return True
            if relationship_id and message.relationship_id == relationship_id:
                if not kind or kind in message.authorization:
                    return True
        return False

    def _send(self, *, to: str, subject: str, body: str, thread_id: str = "",
              in_reply_to: str = "", references=None) -> dict[str, Any]:
        if self._transport is None:
            return {"ok": False, "error": "no transport configured"}
        try:
            result = self._transport.send(
                to=to, subject=subject, body=body, thread_id=thread_id,
                in_reply_to=in_reply_to, references=list(references or []),
            )
        except Exception as exc:
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
        if isinstance(result, dict):
            result.setdefault("ok", True)
            return result
        return {"ok": True, "external_id": str(result)}

    def _already_processed(self, external_id: str) -> bool:
        if not external_id:
            return False
        return any(m.external_id == external_id for m in self.store.list_messages())

    def _provenance(
        self,
        phase: ProvenancePhase,
        summary: str,
        *,
        action: str = "",
        result: str = "",
        evidence: Optional[list[str]] = None,
        refs: Optional[dict[str, Any]] = None,
    ) -> ProvenanceEntry:
        scrub = self._secret_scrub if self._secret_store is not None else None
        if scrub is not None:
            summary = scrub(summary)
            result = scrub(result)
            action = scrub(action)
            evidence = [scrub(e) for e in (evidence or [])]
            if refs:
                refs = {
                    k: scrub(v) if isinstance(v, str)
                    else [scrub(i) for i in v] if isinstance(v, list)
                    else v
                    for k, v in refs.items()
                }
        return self.store.append_provenance(
            ProvenanceEntry(
                phase=phase,
                summary=summary,
                action=action,
                result=result,
                evidence=list(evidence or []),
                refs=dict(refs or {}),
            )
        )

    def _secret_scrub(self, text: str) -> str:
        if self._secret_store is None:
            return text
        try:
            return self._secret_store.scrub(text)
        except Exception:  # pragma: no cover - defensive scrub never blocks provenance
            return text

    def _notify(
        self, *, kind: str = "escalation", summary: str, refs: Optional[dict[str, Any]] = None
    ) -> None:
        """Record a principal notification (durable ledger; future push hook)."""
        self.store.append_notification(
            NotificationEntry(kind=kind, summary=summary, refs=dict(refs or {}))
        )


def _count_by(values: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts
