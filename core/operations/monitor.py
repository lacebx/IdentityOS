"""
core/operations/monitor.py

Conversation monitoring and reply handling.

The monitor ingests inbound messages, associates them with a persistent
relationship, classifies what the person is asking for, and decides whether the
operator may respond autonomously.  Anything that touches a consequential
commitment is escalated and the relationship is marked
``AWAITING_HUMAN_AUTHORIZATION`` rather than answered.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
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
    relationship: Relationship
    message: Message
    intent: str
    treated_as: str        # "opt_out" | "decline" | "reply" | "escalated"
    responded: bool = False
    escalated: bool = False
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "relationship_id": self.relationship.id,
            "message_id": self.message.id,
            "intent": self.intent,
            "treated_as": self.treated_as,
            "responded": self.responded,
            "escalated": self.escalated,
            "reason": self.reason,
        }


class ConversationMonitor:
    """Associates inbound messages with relationships and decides responses."""

    def __init__(self, composer: OutreachComposer, *, transport: Any = None, identity: Any = None) -> None:
        self._composer = composer
        self._transport = transport
        self._identity = identity

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
    ) -> InboundResult:
        relationship = self._resolve_relationship(
            store, sender_email, thread_id,
            message_ids=[i for i in [*list(references or []), in_reply_to] if i],
        )
        if relationship is None:
            relationship = Relationship(
                display_name=sender_email.split("@")[0] if sender_email else "unknown",
                email=sender_email,
                status=RelationshipStatus.ENGAGED,
            )
            store.add_relationship(relationship)

        message = Message(
            relationship_id=relationship.id,
            direction=MessageDirection.INBOUND,
            subject=subject,
            body=body,
            received_at=utcnow().isoformat(),
            external_id=external_id,
            thread_id=thread_id,
            in_reply_to=in_reply_to,
            references=list(references or []),
            status=MessageStatus.RECEIVED,
        )
        store.append_message(message)
        relationship.message_ids.append(message.id)
        if thread_id and thread_id not in relationship.thread_ids:
            relationship.thread_ids.append(thread_id)
        relationship.last_inbound_at = message.received_at
        relationship.touch()

        text = body or ""
        if _matches_any(_OPT_OUT_PATTERNS, text):
            relationship.opted_out = True
            relationship.status = RelationshipStatus.OPTED_OUT
            relationship.next_action = "closed (opt-out)"
            relationship.follow_up_due_at = None
            store.update_relationship(relationship)
            return InboundResult(relationship, message, "opt_out", "opt_out", reason="sender opted out")

        if _matches_any(_DECLINE_PATTERNS, text):
            relationship.status = RelationshipStatus.DECLINED
            relationship.next_action = "closed (declined)"
            relationship.follow_up_due_at = None
            store.update_relationship(relationship)
            intent = classify_intent(text)
            subject_out, reply_body = self._composer.compose_reply(
                relationship, text, intent="decline", facts=self._verified_facts(store),
            )
            _, transmitted, escalated = self._dispatch_reply(
                store, relationship, subject_out, reply_body, kind="decline", source=message,
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
                escalated=escalated, reason=reason,
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
            )

        subject_out, reply_body = self._composer.compose_reply(
            relationship, text, intent=intent, facts=self._verified_facts(store),
        )
        _, transmitted, escalated = self._dispatch_reply(
            store, relationship, subject_out, reply_body, kind="reply", source=message,
        )
        if escalated:
            return InboundResult(
                relationship, message, intent, "escalated", escalated=True,
                reason="outbound mode requires human approval",
            )
        if not transmitted:
            return InboundResult(
                relationship, message, intent, "reply", responded=False,
                reason="observe mode: reply drafted, not sent",
            )
        return InboundResult(
            relationship, message, intent, "reply", responded=True,
            reason=decision.reason,
        )

    # ── helpers ───────────────────────────────────────────────────────

    def _verified_facts(self, store: OperationsStore) -> list[str]:
        """Verified project facts a reply may reference (from real observation)."""
        state = store.project_state()
        return list(state.facts) if state else []

    def _resolve_relationship(
        self, store: OperationsStore, sender_email: str, thread_id: str,
        *, message_ids: Optional[list[str]] = None,
    ) -> Optional[Relationship]:
        for candidate in ([thread_id] if thread_id else []) + list(message_ids or []):
            if not candidate:
                continue
            found = store.find_relationship_by_thread(candidate)
            if found is not None:
                return found
        if sender_email:
            return store.find_relationship_by_email(sender_email)
        return None

    def _dispatch_reply(
        self, store: OperationsStore, relationship: Relationship, subject: str, body: str,
        *, kind: str, source: Optional[Message] = None,
    ) -> tuple[Optional[Message], bool, bool]:
        """Route a composed reply through the outbound operating mode.

        Returns ``(message, transmitted, escalated)``.  ``observe`` records a
        WOULD_SEND draft without transmitting; ``approval_required`` records an
        escalation; ``autonomous`` transmits through the transport.
        """
        mode = normalize_outbound_mode(store.controls().outbound_mode)
        thread, in_reply_to, references = self._threading_for(source, relationship)

        if mode == "approval_required":
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

        if mode == "observe":
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
        )
        return reply, reply is not None, False

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
    ) -> Optional[Message]:
        """Transmit a reply through the transport, so 'sent' is runtime-verified.

        Returns the recorded message on success, or None when nothing was
        transmitted (no transport or send failed); in that case a FAILED record
        is persisted so the failure is observable, never silently 'sent'.
        """
        if not thread:
            thread = relationship.thread_ids[-1] if relationship.thread_ids else ""
        if self._transport is None:
            record = Message(
                relationship_id=relationship.id,
                direction=MessageDirection.OUTBOUND,
                subject=subject,
                body=body,
                status=MessageStatus.FAILED,
                authorization="dry_run_no_transport",
                thread_id=thread,
                in_reply_to=in_reply_to,
                references=list(references or []),
            )
            store.append_message(record)
            relationship.message_ids.append(record.id)
            return None
        try:
            result = self._transport.send(
                to=relationship.email, subject=subject, body=body, thread_id=thread,
                in_reply_to=in_reply_to, references=list(references or []),
            )
        except Exception as exc:
            record = Message(
                relationship_id=relationship.id,
                direction=MessageDirection.OUTBOUND,
                subject=subject,
                body=body,
                status=MessageStatus.FAILED,
                authorization="conversational_autonomous",
                thread_id=thread,
                in_reply_to=in_reply_to,
                references=list(references or []),
            )
            store.append_message(record)
            relationship.message_ids.append(record.id)
            return None
        if isinstance(result, dict) and not result.get("ok"):
            record = Message(
                relationship_id=relationship.id,
                direction=MessageDirection.OUTBOUND,
                subject=subject,
                body=body,
                status=MessageStatus.FAILED,
                authorization="conversational_autonomous",
                thread_id=thread,
                in_reply_to=in_reply_to,
                references=list(references or []),
            )
            store.append_message(record)
            relationship.message_ids.append(record.id)
            return None
        message = Message(
            relationship_id=relationship.id,
            direction=MessageDirection.OUTBOUND,
            subject=subject,
            body=body,
            sent_at=utcnow().isoformat(),
            status=MessageStatus.SENT,
            authorization="conversational_autonomous",
            thread_id=result.get("thread_id") or thread,
            in_reply_to=result.get("in_reply_to") or in_reply_to,
            references=references or [],
        )
        store.append_message(message)
        relationship.message_ids.append(message.id)
        relationship.last_outbound_at = message.sent_at
        store.record_usage("replies")
        return message
