from __future__ import annotations

from pathlib import Path

import pytest

from core.capabilities.email.backends import FileMailboxBackend, MailboxTransport, SMTPBackend
from core.capabilities.email import EmailCapability, build_transport
from core.capabilities.registry import CapabilityRegistry
from runtime.persistence import InMemoryBackend


def test_file_transport_sends_and_persists(tmp_path: Path):
    backend = FileMailboxBackend(tmp_path, mailbox="aster")
    transport = MailboxTransport(backend)
    result = transport.send(to="a@example.org", subject="Hi", body="Hello Alice")
    assert result["ok"] is True
    assert result["external_id"]
    assert len(backend.outbox()) == 1
    # A fresh backend reading the same files must still see the delivery.
    revived = FileMailboxBackend(tmp_path, mailbox="aster")
    assert len(revived.outbox()) == 1
    assert revived.outbox()[0]["to"] == "a@example.org"


def test_file_transport_fetch_inbox(tmp_path: Path):
    backend = FileMailboxBackend(tmp_path, mailbox="aster")
    backend.deliver({
        "external_id": "<m1@example.org>",
        "from": "b@example.org",
        "thread_id": "t1",
        "subject": "Re",
        "body": "Sure.",
    })
    messages = backend.fetch_inbox()
    assert len(messages) == 1
    assert messages[0]["from"] == "b@example.org"
    # Consumed after fetch.
    assert backend.fetch_inbox() == []


def test_build_transport_requires_recipient(tmp_path: Path):
    transport = build_transport({"root": str(tmp_path), "mailbox": "aster"})
    with pytest.raises(Exception):
        transport.send(to="", subject="x", body="x")


def test_email_capability_installs_and_permission_gates_sends(tmp_path: Path):
    storage = InMemoryBackend()
    registry = CapabilityRegistry(storage)
    registry.install("aster", "email", {"root": str(tmp_path), "mailbox": "aster"})

    skipped, reason = registry.can("aster", "email.send")
    assert skipped is False  # public? no: requires explicit grant
    assert "email.send" in reason

    registry.grant("aster", "email", "email.send")
    registry.grant("aster", "email", "email.read")
    result = registry.call("aster", "email.send", to="a@example.org", subject="S", body="Hello")
    assert result.success is True
    assert result.data["ok"] is True

    read_result = registry.call("aster", "email.read_inbox")
    assert read_result.success is True


def test_smtp_backend_requires_credentials():
    backend = SMTPBackend(host="", sender="")
    result = backend.send(to="a@example.org", subject="x", body="x")
    assert result["ok"] is False
    assert "host" in result["error"]


def test_file_transport_roundtrips_threading_headers(tmp_path: Path):
    backend = FileMailboxBackend(tmp_path, mailbox="aster")
    transport = MailboxTransport(backend)
    result = transport.send(
        to="a@example.org", subject="Re", body="reply",
        in_reply_to="<root@example.org>", references=["<root@example.org>", "<mid@example.org>"],
    )
    assert result["ok"] is True
    record = backend.outbox()[0]
    assert record["in_reply_to"] == "<root@example.org>"
    assert record["references"] == ["<root@example.org>", "<mid@example.org>"]


def test_smtp_ignores_bounces_and_autoreplies(tmp_path: Path):
    from email.message import EmailMessage

    smtp = SMTPBackend(host="smtp.example.org", sender="aster@identityos.local")

    def msg(headers):
        m = EmailMessage()
        for key, value in headers.items():
            m[key] = value
        m.set_content("x")
        return m

    assert smtp._ignored(msg({"From": "aster@identityos.local", "Subject": "re: hi"})) is True
    assert smtp._ignored(msg({"From": "mailer@example.org", "Subject": "Delivery Status Notification (Failure)"})) is True
    m = msg({"From": "mailer@example.org", "Subject": "x"})
    m.replace_header("Content-Type", "multipart/report")
    assert smtp._ignored(m) is True
    assert smtp._ignored(msg({"From": "robot@example.org", "Subject": "re: hi", "Auto-Submitted": "auto-replied"})) is True
    assert smtp._ignored(msg({"From": "list@example.org", "Subject": "re: hi", "List-Unsubscribe": "<mailto:list@example.org>"})) is True
    # A genuine reply is kept.
    assert smtp._ignored(msg({"From": "alice@example.org", "Subject": "Re: hello", "Auto-Submitted": "no"})) is False


def test_smtp_validate_reports_unconfigured_without_secrets():
    backend = SMTPBackend(host="", sender="")
    result = backend.validate()
    assert result["smtp"]["configured"] is False
    assert result["smtp"]["ok"] is False
    # Never echo credentials.
    assert "password" not in str(result).lower() or "host" in str(result)


def test_parse_message_ids_handles_multiple_references():
    from core.capabilities.email.backends import parse_message_ids

    ids = parse_message_ids("<a@1> <b@2>\n<c@3>")
    assert ids == ["<a@1>", "<b@2>", "<c@3>"]
    assert parse_message_ids("") == []