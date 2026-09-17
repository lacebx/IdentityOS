"""
email — a reusable capability for sending and reading email.

The capability is provider-agnostic: a file-backed mailbox for deterministic
offline operation, or a real SMTP/IMAP backend when credentials are configured.
Credentials are read from the runtime environment or capability config and are
never written into identity state.
"""

from __future__ import annotations

import os
from typing import Any, Optional

from core.capabilities.base import Capability, Skill, object_schema
from core.capabilities.registry import register
from core.capabilities.result import CapabilityResult

from .backends import FileMailboxBackend, MailboxTransport, SMTPBackend


def build_transport(config: Optional[dict] = None, *, identity_id: str = "") -> MailboxTransport:
    """Build a transport from capability/skill config without touching state."""
    config = config or {}
    backend_name = str(config.get("backend", "file")).lower()
    if backend_name == "smtp":
        backend = SMTPBackend(
            host=str(config.get("smtp_host", os.environ.get("IDENTITY_SMTP_HOST", ""))),
            port=int(config.get("smtp_port", os.environ.get("IDENTITY_SMTP_PORT", 587))),
            username=str(config.get("smtp_user", os.environ.get("IDENTITY_SMTP_USER", ""))),
            password=str(config.get("smtp_password", os.environ.get("IDENTITY_SMTP_PASSWORD", ""))),
            sender=str(config.get("sender", os.environ.get("IDENTITY_EMAIL_FROM", ""))),
            use_tls=bool(config.get("smtp_tls", True)),
            imap_host=str(config.get("imap_host", os.environ.get("IDENTITY_IMAP_HOST", ""))),
            imap_port=int(config.get("imap_port", os.environ.get("IDENTITY_IMAP_PORT", 993))),
        )
        return MailboxTransport(backend)

    root = str(config.get("root", os.environ.get("IDENTITY_MAILBOX_ROOT", ".identity_mailbox")))
    mailbox = str(config.get("mailbox", identity_id or "default"))
    return MailboxTransport(FileMailboxBackend(root, mailbox=mailbox))


class CapabilityTransport:
    """Transport that goes through the capability permission gate.

    ``email.send`` / ``email.read_inbox`` are only invoked after the identity's
    capability registry authorizes them, so a model or autonomous loop can never
    send mail the identity has not been granted.
    """

    def __init__(self, registry: Any, identity_id: str) -> None:
        self._registry = registry
        self._identity_id = identity_id

    def send(self, *, to: str, subject: str, body: str, thread_id: str = "",
             in_reply_to: str = "", references=None) -> dict[str, Any]:
        result = self._registry.call(
            self._identity_id, "email.send",
            to=to, subject=subject, body=body, thread_id=thread_id,
            in_reply_to=in_reply_to, references=references,
        )
        if not result.success:
            message = (result.error or {}).get("message", "email.send denied")
            return {"ok": False, "error": message}
        return result.data

    def fetch_inbox(self) -> list[dict[str, Any]]:
        result = self._registry.call(self._identity_id, "email.read_inbox")
        if not result.success:
            return []
        data = result.data or {}
        return data.get("messages", [])


@register
class EmailCapability(Capability):
    id = "email"
    name = "Email"
    version = "1.0.0"
    author = "IdentityOS"
    license = "MIT"
    homepage = "https://github.com/lacebx/IdentityOS"
    description = "Send and receive email through a file mailbox or SMTP/IMAP"
    permissions = ["email.send", "email.read"]

    def __init__(self, config: Optional[dict] = None) -> None:
        super().__init__(config)
        self._transport = build_transport(config)

    def install(self, identity_id: str, storage: Any) -> None:
        # Rebuild transport scoped to this identity so file mailboxes are isolated.
        self._transport = build_transport(self._config, identity_id=identity_id)
        storage.save(identity_id, "capability.email", {"installed_at": None})

    def uninstall(self, identity_id: str, storage: Any) -> None:
        storage.delete(identity_id, "capability.email")

    def prompts(self, identity_id: str) -> list[str]:
        return [
            "## Email Skills",
            "Use email.send to send a message and email.read_inbox to read replies.",
            "Never include credentials or make binding commitments in an email unless explicitly authorized.",
        ]

    _SKILLS = [
        Skill(
            name="email.send",
            description="Send an email to a recipient",
            permission="email.send",
            effect="write",
            input_schema=object_schema(
                {
                    "to": {"type": "string", "minLength": 1},
                    "subject": {"type": "string"},
                    "body": {"type": "string"},
                    "thread_id": {"type": "string"},
                    "in_reply_to": {"type": "string"},
                    "references": {"type": "array", "items": {"type": "string"}},
                },
                required=("to", "body"),
            ),
        ),
        Skill(
            name="email.read_inbox",
            description="Read and consume unread inbound email",
            permission="email.read",
            effect="read",
            input_schema=object_schema({}),
        ),
    ]

    def skills(self) -> list[Skill]:
        return list(self._SKILLS)

    def call(self, skill_name: str, **params: Any) -> CapabilityResult:
        import time as _time

        _t0 = _time.monotonic()
        try:
            if skill_name == "email.send":
                result = self._transport.send(
                    to=str(params.get("to", "")),
                    subject=str(params.get("subject", "")),
                    body=str(params.get("body", "")),
                    thread_id=str(params.get("thread_id", "")),
                    in_reply_to=str(params.get("in_reply_to", "")),
                    references=list(params.get("references") or []),
                )
                return CapabilityResult.from_data(
                    "email", skill_name, result, source="email",
                    duration_ms=(_time.monotonic() - _t0) * 1000,
                )
            if skill_name == "email.read_inbox":
                messages = self._transport.fetch_inbox()
                return CapabilityResult.from_data(
                    "email", skill_name, {"messages": messages, "count": len(messages)},
                    source="email", duration_ms=(_time.monotonic() - _t0) * 1000,
                )
            return CapabilityResult.fail("email", skill_name, "unknown_skill", f"Unknown skill: {skill_name}")
        except Exception as exc:
            return CapabilityResult.fail(
                "email", skill_name, type(exc).__name__, str(exc),
                duration_ms=(_time.monotonic() - _t0) * 1000,
            )
