"""
core/operations/monitor.py

Conversation monitoring and reply handling.

The monitor ingests inbound messages, classifies their *disposition*, associates
them with a persistent relationship when the sender is within trusted scope, and
decides whether the operator may respond autonomously.

Disposition is the primary inbound boundary.  Only messages in a trusted thread
or from an approved (already-known) sender may be answered autonomously.
Automated, bounce, self-copy, spam/bulk, and unsolicited-unknown messages are
never answered — they are recorded so the audit trail stays complete.
Anything that touches a consequential commitment is escalated and the
relationship is marked ``AWAITING_HUMAN_AUTHORIZATION`` rather than answered.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from .composition import OutreachComposer
from .models import (
    Message,
    MessageDirection,
    MessageStatus,
    NotificationEntry,
    ProvenanceEntry,
    ProvenancePhase,
    Relationship,
    RelationshipStatus,
    normalize_outbound_mode,
    utcnow,
)
from .policy import AuthorityPolicy, is_conversational
from .store import OperationsStore, _norm

_OPT_OUT_PATTERNS = (
    r"\bunsubscribe\b", r"\bopt[ -]?out\b", r"\bstop (emailing|contacting)\b",
    r"\bremove me\b", r"\bdo not contact\b", r"\bdon'?t contact\b",
)

_DECLINE_PATTERNS = (
    r"\bnot interested\b", r"\bno thank you\b", r"\bno thanks\b",
    r"\bnot a fit\b", r"\bpass on this\b", r"\bdecline\b",
)

_INTENT_PATTERNS: list[tuple[str, tuple[str, ...]]] = [
    ("scheduling", (r"\bschedul", r"\bmeet(ing)?\b", r"\bcalendar\b", r"\btime (next|this) week\b", r"\bcall\b")),
    ("documentation_request", (r"\bdocs?\b", r"\bdocumentation\b", r"\bwhitepaper\b", r"\bdeck\b", r"\bmore (info|information|details)\b", r"\bsend .*(link|material)\b")),
    ("intro_request", (r"\bintro(duction)?\b", r"\bconnect me\b", r"\bwho else\b", r"\brefer\b")),
    ("interest", (r"\binterested\b", r"\blove to\b", r"\bwould like to\b", r"\bhappy to\b", r"\bexcited\b", r"\btell me more\b")),
    ("decline", _DECLINE_PATTERNS),
    ("thanks", (r"\bthank(s| you)\b", r"\bappreciate\b", r"\bgreat,? thanks\b")),
    ("question", (r"\?", r"\bhow\b", r"\bwhat\b", r"\bwhen\b", r"\bwhere\b", r"\bwhy\b", r"\bcan you\b", r"\bcould you\b")),
]


class InboundDisposition(str, Enum):
    """Why an inbound message deserves (or does not deserve) a response.

    Only ``TRUSTED_THREAD`` and ``APPROVED_SENDER`` may reach an autonomous
    reply.  The remaining dispositions are recorded but never answered.
    """

    TRUSTED_THREAD = "trusted_thread"
    APPROVED_SENDER = "approved_sender"
    UNSOLICITED_UNKNOWN = "unsolicited_unknown"
    AUTOMATED = "automated"
    BOUNCE = "bounce"
    SELF_COPY = "self_copy"
    SPAM_OR_BULK = "spam_or_bulk"


# Secondary defensive filter: recognizable automated/unmailable sender aliases.
# Trust scope (thread/relationship) is the *primary* boundary; these patterns
# only tighten it.
_AUTOMATED_SENDER_RE = re.compile(
    r"^(?:no[-_.]?reply|do[-_.]?not[-_.]?reply|donotreply|noreply|"
    r"mailer[-_.]?daemon|postmaster|delivery[-_.]?(?:status|failure)|"
    r"auto[-_.]?reply|bounce|mail[-_.]?administrator)@",
    re.IGNORECASE,
)

_BOUNCE_SUBJECT_RE = (
    r"delivery status notification", r"undelivered(?: mail)?", r"undeliverable",
    r"mail delivery (?:failed|failure)", r"returned mail", r"returned to sender",
    r"mail status notification", r"delivery has failed", r"failure notice",
    r"non[- ]delivery",
)
_BOUNCE_BODY_RE = (
    r"this is the mail system at host", r"delivery status notification",
    r"message could not be delivered", r"permanent(?: delivery)? failure",
    r"the mime part of the returned message", r"mail delivery failed",
    r"cannot deliver|was not delivered", r"remote host has closed the connection",
)

_AUTOMATED_SUBJECT_RE = (
    r"auto[-\s]?gen", r"automated message", r"automatic reply", r"autorespond",
    r"out[- ]of[- ]office", r"auto[- ]reply", r"automated response",
    r"this mailbox (?:is|isn'?t) monitored", r"e?mail (?:status|notification)",
)
_AUTOMATED_BODY_RE = (
    r"this is (?:a|an) (?:automated|automatic) message",
    r"auto[- ]?generated (?:reply|email|message|response)",
    r"out[- ]of[- ]office(?: autoreply)?", r"i am currently (?:away|out of the office)",
    r"automatic response", r"no one(?: is)? (?:reads|monitors) this mailbox",
)

_SPAM_SUBJECT_RE = (
    r"^\[[^\]]+\](\s|:)", r"\bnewsletter\b", r"(?:limited time|act now)",
    r"congratulations!?", r"you'?ve won", r"\bviagra\b|\bcialis\b",
    r"\bcrypto\b.{0,40}\b(?:gift|win)\b", r"\bbitcoin\b.{0,40}\b(?:double|gift)\b",
    r"\bsponsored\b", r"\bpromo(?:tion)?\b.*\b\d+%?\s+off\b",
)
_SPAM_BODY_RE = (
    r"unsubscribe.{0,80}(?:click|link)", r"this email is (?:an|a) advertisement",
    r"you are subscribed to", r"to (?:unsubscribe|stop receiving)",
    r"\bviagra\b|\bcialis\b", r"\bcasino\b|\blottery\b", r"earn \$\d",
)


def classify_intent(body: str) -> str:
    text = (body or "").lower()
    for intent, patterns in _INTENT_PATTERNS:
        for pattern in patterns:
            if re.search(pattern, text):
                return intent
    return "question"


def _matches_any(patterns: tuple[str, ...], text: str) -> bool:
    return any(re.search(p, text, flags=re.IGNORECASE) for p in patterns)


@dataclass
class InboundResult:
    relationship: Optional[Relationship]
    message: Message
    intent: str
    treated_as: str        # "opt_out" | "decline" | "reply" | "escalated" | "ignored" | "quarantined" | "deferred"
    responded: bool = False
    escalated: bool = False
    reason: str = ""
    disposition: Optional[InboundDisposition] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "relationship_id": self.relationship.id if self.relationship else "",
            "message_id": self.message.id,
            "intent": self.intent,
            "treated_as": self.treated_as,
            "responded": self.responded,
            "escalated": self.escalated,
            "reason": self.reason,
            "disposition": self.disposition.value if self.disposition else "",
        }


class ConversationMonitor:
    """Associates inbound messages with relationships and decides responses."""

    def __init__(
        self,
        composer: OutreachComposer,
        *,
        transport: Any = None,
        identity: Any = None,
        adapter: Any = None,
        self_address: str = "",
    ) -> None:
        self._composer = composer
        self._transport = transport
        self._identity = identity
        self._adapter = adapter
        self._self_address = self_address or self._derive_self_address(transport)

    @staticmethod
    def _derive_self_address(transport: Any) -> str:
        sender = ""
        if transport is not None:
            backend = getattr(transport, "backend", None)
            if backend is not None:
                sender = str(getattr(backend, "sender", "") or "")
            if not sender:
                sender = str(getattr(transport, "sender", "") or "")
        return sender

    def ingest(
        self,
        store: OperationsStore,
        *,
        sender_email: str,
        body: str,
        subject: str = "",
        thread_id: str = "",
        external_id: str = "",
        in_reply_to: str = "",
        references: Optional[list[str]] = None,
        raw_body: str = "",
    ) -> InboundResult:
        message_ids = [i for i in [*list(references or []), in_reply_to] if i]
        disposition, relationship = self._classify(
            store, sender_email=sender_email, thread_id=thread_id,
            message_ids=message_ids, subject=subject, body=body,
        )

        if disposition in (
            InboundDisposition.SELF_COPY, InboundDisposition.BOUNCE,
            InboundDisposition.AUTOMATED, InboundDisposition.SPAM_OR_BULK,
        ):
            message = self._record_inbound(
                store, relationship_id=relationship.id if relationship else "",
                sender_email=sender_email, body=body, subject=subject,
                thread_id=thread_id, external_id=external_id, in_reply_to=in_reply_to,
                references=references, raw_body=raw_body,
            )
            return InboundResult(
                relationship, message, "ignored", "ignored",
                disposition=disposition,
                reason=f"{disposition.value}: excluded from autonomous response",
            )

        if disposition is InboundDisposition.UNSOLICITED_UNKNOWN:
            message = self._record_inbound(
                store, relationship_id="", sender_email=sender_email, body=body,
                subject=subject, thread_id=thread_id, external_id=external_id,
                in_reply_to=in_reply_to, references=references, raw_body=raw_body,
            )
            return InboundResult(
                None, message, "unsolicited", "quarantined",
                disposition=disposition,
                reason="unsolicited unknown sender: quarantined, no autonomous reply",
            )

        # Trusted scope from here on.
        if relationship is None:
            relationship = Relationship(
                display_name=sender_email.split("@")[0] if sender_email else "unknown",
                email=sender_email,
                status=RelationshipStatus.ENGAGED,
            )
            store.add_relationship(relationship)

        message = self._record_inbound(
            store, relationship_id=relationship.id, sender_email=sender_email,
            body=body, subject=subject, thread_id=thread_id, external_id=external_id,
            in_reply_to=in_reply_to, references=references, raw_body=raw_body,
        )
        relationship.message_ids.append(message.id)
        if thread_id and thread_id not in relationship.thread_ids:
            relationship.thread_ids.append(thread_id)
        relationship.last_inbound_at = message.received_at
        relationship.touch()

        # A message inside a trusted thread but written by a *different* sender is
        # still not autonomous scope: we record it for context but never reply to
        # the intruder on the principal's behalf.
        if relationship.email and _norm(relationship.email) != _norm(sender_email):
            store.update_relationship(relationship)
            return InboundResult(
                relationship, message, "unsolicited", "quarantined",
                disposition=disposition,
                reason=f"unexpected sender '{sender_email}' in an existing thread: quarantined",
            )

        # Empty-body gate: if no readable text could be extracted, do NOT
        # classify, do NOT fall back to a template, and do NOT reply — defer
        # and notify the principal instead.
        if not (body or "").strip():
            relationship.status = RelationshipStatus.ENGAGED
            relationship.next_action = "deferred: message body unavailable"
            store.update_relationship(relationship)
            store.append_notification(
                NotificationEntry(
                    kind="inbound_body_unavailable",
                    summary="An inbound message had no readable text body; deferred with no reply.",
                    refs={"message_id": message.id, "relationship_id": relationship.id,
                          "recipient": relationship.email, "external_id": external_id},
                )
            )
            store.append_provenance(
                ProvenanceEntry(
                    phase=ProvenancePhase.MONITOR,
                    summary="inbound message with no readable text body; no reply sent",
                    action="monitor",
                    result="inbound_body_unavailable",
                    refs={"message_id": message.id, "relationship_id": relationship.id},
                )
            )
            return InboundResult(
                relationship, message, "unknown", "deferred",
                reason="inbound_body_unavailable: message body could not be extracted",
                disposition=disposition,
            )

        text = body or ""
        if _matches_any(_OPT_OUT_PATTERNS, text):
            relationship.opted_out = True
            relationship.status = RelationshipStatus.OPTED_OUT
            relationship.next_action = "closed (opt-out)"
            relationship.follow_up_due_at = None
            store.update_relationship(relationship)
            return InboundResult(relationship, message, "opt_out", "opt_out", disposition=disposition, reason="sender opted out")

        if _matches_any(_DECLINE_PATTERNS, text):
            relationship.status = RelationshipStatus.DECLINED
            relationship.next_action = "closed (declined)"
            relationship.follow_up_due_at = None
            store.update_relationship(relationship)
            intent = classify_intent(text)
            subject_out, reply_body, reply_mode = self._composer.compose_reply(
                relationship, text, intent="decline",
                facts=self._verified_facts(store),
                adapter=self._adapter, identity=self._identity,
            )
            _, transmitted, escalated = self._dispatch_reply(
                store, relationship, subject_out, reply_body, kind="decline", source=message,
                mode=reply_mode,
            )
            relationship.status = RelationshipStatus.DECLINED
            store.update_relationship(relationship)
            reason = (
                "respectful close sent; no further outreach" if transmitted else
                "respectful close drafted (observe mode); no further outreach" if not escalated else
                "respectful close requires human approval"
            )
            return InboundResult(
                relationship, message, intent, "decline", responded=transmitted,
                escalated=escalated, reason=reason, disposition=disposition,
            )

        intent = classify_intent(text)
        decision = AuthorityPolicy(store.controls()).evaluate(
            f"reply to {relationship.email}", category=relationship.purpose, content=text
        )
        relationship.status = RelationshipStatus.ENGAGED
        relationship.next_action = "reply" if is_conversational(intent) and decision.autonomous else "human review"
        store.update_relationship(relationship)

        if decision.requires_human or not is_conversational(intent):
            relationship.status = RelationshipStatus.AWAITING_AUTHORIZATION
            store.update_relationship(relationship)
            return InboundResult(
                relationship, message, intent, "escalated", escalated=True,
                reason=decision.reason if decision.requires_human else f"intent '{intent}' requires human",
                disposition=disposition,
            )

        facts = self._verified_facts(store)
        knowledge_intents = ("question", "documentation_request", "intro_request")
        if intent in knowledge_intents and not facts:
            # Knowledge-readiness gate: without verified project facts any
            # substantive reply would be an ungrounded acknowledgement. Defer
            # instead of pretending.
            relationship.status = RelationshipStatus.ENGAGED
            relationship.next_action = "deferred: project context unavailable"
            store.update_relationship(relationship)
            store.append_notification(
                NotificationEntry(
                    kind="project_context_unavailable",
                    summary="Inbound request could not be answered: no verified project facts observed",
                    refs={"message_id": message.id, "relationship_id": relationship.id, "recipient": relationship.email},
                )
            )
            return InboundResult(
                relationship, message, intent, "deferred",
                reason="project_context_unavailable: no verified project facts",
                disposition=disposition,
            )

        subject_out, reply_body, reply_mode = self._composer.compose_reply(
            relationship, text, intent=intent, facts=facts,
            adapter=self._adapter, identity=self._identity,
        )
        if reply_mode == "unavailable":
            # Substantive reply requires a working model runtime. Never send a
            # canned answer as if it were a model answer — fail explicitly by
            # deferring and notifying the principal.
            relationship.status = RelationshipStatus.ENGAGED
            relationship.next_action = "deferred: reply generation unavailable (no model runtime)"
            store.update_relationship(relationship)
            store.append_notification(
                NotificationEntry(
                    kind="reply_generation_unavailable",
                    summary="A substantive inbound could not be answered: no model runtime is configured for reply generation.",
                    refs={"message_id": message.id, "relationship_id": relationship.id,
                          "recipient": relationship.email},
                )
            )
            return InboundResult(
                relationship, message, intent, "deferred",
                reason="reply_generation_unavailable: no model runtime for substantive reply",
                disposition=disposition,
            )
        _, transmitted, escalated = self._dispatch_reply(
            store, relationship, subject_out, reply_body, kind="reply", source=message,
            mode=reply_mode, policy_reason=decision.reason,
        )
        if escalated:
            return InboundResult(
                relationship, message, intent, "escalated", escalated=True,
                reason="outbound mode requires human approval", disposition=disposition,
            )
        if not transmitted:
            return InboundResult(
                relationship, message, intent, "reply", responded=False,
                reason="observe mode: reply drafted, not sent", disposition=disposition,
            )
        return InboundResult(
            relationship, message, intent, "reply", responded=True,
            reason=decision.reason, disposition=disposition,
        )

    # ── helpers ───────────────────────────────────────────────────────

    def _record_inbound(
        self, store: OperationsStore, *, relationship_id: str, sender_email: str,
        body: str, subject: str, thread_id: str, external_id: str,
        in_reply_to: str, references: Optional[list[str]], raw_body: str = "",
    ) -> Message:
        raw = raw_body or body or ""
        message = Message(
            relationship_id=relationship_id,
            direction=MessageDirection.INBOUND,
            subject=subject,
            body=body,
            raw_body=raw,
            body_sha256=hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest() if raw else "",
            received_at=utcnow().isoformat(),
            external_id=external_id,
            thread_id=thread_id,
            in_reply_to=in_reply_to,
            references=list(references or []),
            status=MessageStatus.RECEIVED,
        )
        store.append_message(message)
        return message

    def _classify(
        self, store: OperationsStore, *, sender_email: str, thread_id: str,
        message_ids: list[str], subject: str, body: str,
    ) -> tuple[InboundDisposition, Optional[Relationship]]:
        sender = _norm(sender_email)
        self_addr = _norm(self._self_address)
        if self_addr and sender and sender == self_addr:
            return InboundDisposition.SELF_COPY, None
        if sender and _AUTOMATED_SENDER_RE.search(sender_email):
            return InboundDisposition.AUTOMATED, None
        if _matches_any(_BOUNCE_SUBJECT_RE, subject) or _matches_any(_BOUNCE_BODY_RE, body):
            return InboundDisposition.BOUNCE, None
        if _matches_any(_AUTOMATED_SUBJECT_RE, subject) or _matches_any(_AUTOMATED_BODY_RE, body):
            return InboundDisposition.AUTOMATED, None
        if _matches_any(_SPAM_SUBJECT_RE, subject) or _matches_any(_SPAM_BODY_RE, body):
            return InboundDisposition.SPAM_OR_BULK, None
        # Primary boundary: trusted thread / known relationship scope.
        relationship = self._resolve_thread_relationship(store, thread_id, message_ids)
        if relationship is not None:
            return InboundDisposition.TRUSTED_THREAD, relationship
        if sender:
            relationship = store.find_relationship_by_email(sender_email)
            if relationship is not None:
                return InboundDisposition.APPROVED_SENDER, relationship
        return InboundDisposition.UNSOLICITED_UNKNOWN, None

    def _resolve_thread_relationship(
        self, store: OperationsStore, thread_id: str, message_ids: list[str],
    ) -> Optional[Relationship]:
        for candidate in ([thread_id] if thread_id else []) + list(message_ids or []):
            if not candidate:
                continue
            found = store.find_relationship_by_thread(candidate)
            if found is not None:
                return found
        return None

    def _verified_facts(self, store: OperationsStore) -> list[str]:
        """Verified project facts a reply may reference (from real observation)."""
        state = store.project_state()
        return list(state.facts) if state else []

    def _dispatch_reply(
        self, store: OperationsStore, relationship: Relationship, subject: str, body: str,
        *, kind: str, source: Optional[Message] = None,
        mode: str = "template_fallback", policy_reason: str = "",
    ) -> tuple[Optional[Message], bool, bool]:
        """Route a composed reply through the outbound operating mode.

        Returns ``(message, transmitted, escalated)``.  ``observe`` records a
        WOULD_SEND draft without transmitting; ``approval_required`` records an
        escalation; ``autonomous`` transmits through the transport.  Every
        record carries ``generation`` metadata so a template reply can never be
        confused with a model-backed one.
        """
        outbound_mode = normalize_outbound_mode(store.controls().outbound_mode)
        thread, in_reply_to, references = self._threading_for(source, relationship)
        generation = self._generation_meta(store, mode, source, policy_reason=policy_reason)

        if outbound_mode == "approval_required":
            if self._has_draft(store, relationship.id, kind):
                return None, False, False
            record = Message(
                relationship_id=relationship.id,
                direction=MessageDirection.OUTBOUND,
                subject=subject,
                body=body,
                status=MessageStatus.AWAITING_AUTHORIZATION,
                authorization=f"awaiting_human_authorization:{kind}",
                thread_id=thread,
                in_reply_to=in_reply_to,
                references=list(references),
                generation=generation,
            )
            store.append_message(record)
            relationship.message_ids.append(record.id)
            relationship.status = RelationshipStatus.AWAITING_AUTHORIZATION
            relationship.next_action = "human authorization required"
            store.update_relationship(relationship)
            store.append_notification(
                NotificationEntry(
                    kind="escalation",
                    summary=f"reply requires human authorization: {kind}",
                    refs={"message_id": record.id, "relationship_id": relationship.id,
                          "recipient": relationship.email},
                )
            )
            return record, False, True

        if outbound_mode == "observe":
            if self._has_draft(store, relationship.id, kind):
                return None, False, False
            record = Message(
                relationship_id=relationship.id,
                direction=MessageDirection.OUTBOUND,
                subject=subject,
                body=body,
                status=MessageStatus.WOULD_SEND,
                authorization=f"observe_would_send:{kind}",
                thread_id=thread,
                in_reply_to=in_reply_to,
                references=list(references),
                generation=generation,
            )
            store.append_message(record)
            relationship.message_ids.append(record.id)
            store.update_relationship(relationship)
            store.append_provenance(
                ProvenanceEntry(
                    phase=ProvenancePhase.PLAN,
                    summary=f"reply drafted in observation mode (not sent): {kind}",
                    action="would_send",
                    result=f"to={relationship.email} mode=observe",
                    refs={"relationship_id": relationship.id, "message_id": record.id},
                )
            )
            return record, False, False

        reply = self._send_reply(
            store, relationship, subject, body,
            thread=thread, in_reply_to=in_reply_to, references=list(references),
            generation=generation,
        )
        return reply, reply is not None, False

    def _generation_meta(
        self, store: OperationsStore, reply_mode: str, source: Optional[Message],
        *, policy_reason: str = "",
    ) -> dict[str, Any]:
        """Provenance for how an outbound reply was produced.

        Distinguishes ``identity_model_generation`` (model adapter wrote it)
        from ``template_fallback`` and records provider/model, the inbound
        messages being answered, the policy decision, and the verified facts
        the model could cite.  Compact keys only (no credentials).
        """
        meta: dict[str, Any] = {
            "mode": reply_mode,
            "adapter": type(self._adapter).__name__ if self._adapter is not None else "",
            "model": str(getattr(self._adapter, "model", "") or "") if self._adapter is not None else "",
            "inbound_message_ids": [source.id] if source else [],
            "inbound_external_ids": [source.external_id] if source and source.external_id else [],
        }
        if policy_reason:
            meta["policy"] = policy_reason
        state = store.project_state()
        if state is not None:
            meta["verified_fact_ids"] = [f.id for f in state.fact_details]
        return {k: v for k, v in meta.items() if v not in ("", [], None)}

    def _threading_for(self, source: Optional[Message], relationship: Relationship) -> tuple[str, str, list[str]]:
        """Derive the RFC threading context for a reply to ``source``."""
        if source is not None:
            thread = source.thread_id or (relationship.thread_ids[-1] if relationship.thread_ids else "")
            in_reply_to = source.external_id or source.in_reply_to or source.thread_id
            references = [r for r in [*list(source.references or []), in_reply_to] if r]
            return thread, in_reply_to, references
        thread = relationship.thread_ids[-1] if relationship.thread_ids else ""
        return thread, "", []

    def _has_draft(self, store: OperationsStore, relationship_id: str, kind: str) -> bool:
        for existing in store.list_messages():
            if existing.relationship_id != relationship_id:
                continue
            if existing.status not in (MessageStatus.WOULD_SEND, MessageStatus.AWAITING_AUTHORIZATION):
                continue
            if kind in (existing.authorization or ""):
                return True
        return False

    def _send_reply(
        self, store: OperationsStore, relationship: Relationship, subject: str, body: str,
        *, thread: str = "", in_reply_to: str = "", references: Optional[list[str]] = None,
        generation: Optional[dict[str, Any]] = None,
    ) -> Optional[Message]:
        """Transmit a reply through the transport, so 'sent' is runtime-verified.

        Returns the recorded message on success, or None when nothing was
        transmitted (no transport or send failed); in that case a FAILED record
        is persisted so the failure is observable, never silently 'sent'.

        A standards-compliant RFC 5322 ``Message-ID`` is generated *before*
        transmission and persisted verbatim in ``Message.external_id`` (falling
        back to the transport's identifier only if it overrides ours).  The
        relationship is re-persisted on every path so ``message_ids`` and
        ``last_outbound_at`` are never lost to an unsaved in-memory append.
        """
        if not thread:
            thread = relationship.thread_ids[-1] if relationship.thread_ids else ""
        generation = dict(generation or {})

        def _record_failure(reason: str) -> None:
            record = Message(
                relationship_id=relationship.id,
                direction=MessageDirection.OUTBOUND,
                subject=subject,
                body=body,
                status=MessageStatus.FAILED,
                authorization=reason,
                thread_id=thread,
                in_reply_to=in_reply_to,
                references=list(references or []),
                generation=generation,
            )
            store.append_message(record)
            relationship.message_ids.append(record.id)
            store.update_relationship(relationship)

        if self._transport is None:
            _record_failure("dry_run_no_transport")
            return None

        from core.capabilities.email.backends import generate_message_id

        message_id = generate_message_id()
        try:
            result = self._transport.send(
                to=relationship.email, subject=subject, body=body, thread_id=thread,
                in_reply_to=in_reply_to, references=list(references or []),
                message_id=message_id,
            )
        except Exception as exc:
            generation["error"] = f"{type(exc).__name__}: {exc}"
            _record_failure("conversational_autonomous")
            return None
        if isinstance(result, dict) and not result.get("ok"):
            generation["error"] = str(result.get("error", "send_not_ok"))
            _record_failure("conversational_autonomous")
            return None

        external_id = str(result.get("external_id") or message_id)
        generation["mode"] = generation.get("mode") or "identity_model_generation"
        generation["message_id"] = external_id
        message = Message(
            relationship_id=relationship.id,
            direction=MessageDirection.OUTBOUND,
            subject=subject,
            body=body,
            sent_at=utcnow().isoformat(),
            status=MessageStatus.SENT,
            authorization="conversational_autonomous",
            external_id=external_id,
            thread_id=result.get("thread_id") or thread,
            in_reply_to=result.get("in_reply_to") or in_reply_to,
            references=references or [],
            generation=generation,
        )
        store.append_message(message)
        relationship.message_ids.append(message.id)
        resolved_thread = message.thread_id
        if resolved_thread and resolved_thread not in relationship.thread_ids:
            relationship.thread_ids.append(resolved_thread)
        relationship.last_outbound_at = message.sent_at
        store.update_relationship(relationship)
        store.record_usage("replies")
        return message