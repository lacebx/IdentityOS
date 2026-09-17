"""
core/capabilities/email/backends.py

Mailbox backends for the email capability.

Two backends are provided:

* :class:`FileMailboxBackend` — a deterministic, file-backed mailbox used for
  tests, demos, and offline operation.  It performs *real* filesystem writes,
  so evidence about what was sent is genuine.
* :class:`SMTPBackend` — a real outbound SMTP sender with optional IMAP inbox
  polling, gated behind credentials that are never stored in identity state.

A :class:`MailboxTransport` adapts either backend to the operations engine's
``send`` / ``fetch_inbox`` protocol.
"""

from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path
from typing import Any, Iterable, Optional


class MailboxError(RuntimeError):
    pass


def parse_message_ids(value: str) -> list[str]:
    """Return the RFC 5322 message-ids (``<...>`` tokens) inside a header value."""
    return list(re.findall(r"<[^<>\s]+>", value or ""))


def _extract_raw(fetched: Any) -> bytes:
    """Pick the message literal bytes out of an imaplib fetch result.

    imaplib returns lists of items shaped either as ``(payload, flags)`` tuples
    (literal responses) or plain byte strings; the message literal is always the
    first ``bytes`` we can find.
    """
    container = fetched[0] if fetched else None
    if isinstance(container, tuple):
        for item in container:
            if isinstance(item, bytes):
                return item
    elif isinstance(container, bytes):
        return container
    return b""


class FileMailboxBackend:
    """A real, file-backed mailbox. Deliveries and receipts are persisted JSON."""

    def __init__(self, root: str | Path, *, mailbox: str = "default") -> None:
        self.root = Path(root)
        self.mailbox = mailbox
        self.root.mkdir(parents=True, exist_ok=True)

    @property
    def _outbox(self) -> Path:
        return self.root / f"outbox-{self.mailbox}.json"

    @property
    def _inbox(self) -> Path:
        return self.root / f"inbox-{self.mailbox}.json"

    def _read(self, path: Path) -> list[dict[str, Any]]:
        if not path.is_file():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        return data if isinstance(data, list) else []

    def _write(self, path: Path, items: list[dict[str, Any]]) -> None:
        path.write_text(json.dumps(items, indent=2), encoding="utf-8")

    def send(
        self,
        *,
        to: str,
        subject: str,
        body: str,
        thread_id: str = "",
        in_reply_to: str = "",
        references: Optional[Iterable[str]] = None,
    ) -> dict[str, Any]:
        if not to:
            raise MailboxError("recipient address is required")
        message_id = f"<{uuid.uuid4().hex}@identityos.local>"
        record = {
            "external_id": message_id,
            "thread_id": thread_id or f"thread-{uuid.uuid4().hex[:10]}",
            "in_reply_to": in_reply_to,
            "references": list(references or []),
            "to": to,
            "from": "",
            "subject": subject,
            "body": body,
            "sent_at": time.time(),
        }
        items = self._read(self._outbox)
        items.append(record)
        self._write(self._outbox, items)
        return {
            "ok": True,
            "external_id": message_id,
            "thread_id": record["thread_id"],
            "evidence": [f"file-mailbox:{self._outbox}", f"to:{to}", f"subject:{subject}"],
        }

    def fetch_inbox(self) -> list[dict[str, Any]]:
        items = self._read(self._inbox)
        # Inbound messages are considered consumed once fetched.
        self._write(self._inbox, [])
        return items

    def outbox(self) -> list[dict[str, Any]]:
        return self._read(self._outbox)

    def deliver(self, message: dict[str, Any]) -> None:
        """Test/demo helper: place a message in the inbox."""
        items = self._read(self._inbox)
        items.append(message)
        self._write(self._inbox, items)


class SMTPBackend:
    """Real SMTP/IMAP using the standard library.

    Credentials come from the environment (or capability config) and are never
    persisted.  ``fetch_inbox`` skips automated/bounce messages so the operator
    does not mistake an autoresponder for a human reply.
    """

    def __init__(
        self,
        *,
        host: str,
        port: int = 587,
        username: str = "",
        password: str = "",
        sender: str = "",
        use_tls: bool = True,
        imap_host: str = "",
        imap_port: int = 993,
        imap_factory: Any = None,
    ) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.sender = sender or username
        self.use_tls = use_tls
        self.imap_host = imap_host
        self.imap_port = imap_port
        self.imap_factory = imap_factory

    def send(
        self,
        *,
        to: str,
        subject: str,
        body: str,
        thread_id: str = "",
        in_reply_to: str = "",
        references: Optional[Iterable[str]] = None,
    ) -> dict[str, Any]:
        if not self.host or not self.sender:
            return {"ok": False, "error": "SMTP host and sender are required"}
        import smtplib
        from email.message import EmailMessage

        message_id = f"<{uuid.uuid4().hex}@identityos>"
        msg = EmailMessage()
        msg["From"] = self.sender
        msg["To"] = to
        msg["Subject"] = subject
        msg["Message-ID"] = message_id
        refs = [r for r in (references or []) if r]
        if in_reply_to and in_reply_to not in refs:
            refs.insert(0, in_reply_to)
        if in_reply_to:
            msg["In-Reply-To"] = in_reply_to
        if refs:
            msg["References"] = " ".join(refs)
        msg.set_content(body)

        try:
            with smtplib.SMTP(self.host, self.port, timeout=20) as smtp:
                if self.use_tls:
                    smtp.starttls()
                if self.username:
                    smtp.login(self.username, self.password)
                smtp.send_message(msg)
        except Exception as exc:  # surface the real failure
            raise MailboxError(f"SMTP send failed: {exc}") from exc

        resolved_thread = thread_id or in_reply_to or (refs[0] if refs else message_id)
        return {
            "ok": True,
            "external_id": message_id,
            "thread_id": resolved_thread,
            "evidence": [f"smtp:{self.host}:{self.port}", f"to:{to}", f"subject:{subject}"],
        }

    def fetch_inbox(self) -> list[dict[str, Any]]:
        if not self.imap_host:
            return []
        import email

        messages: list[dict[str, Any]] = []
        try:
            with self._connect_imap() as imap:
                imap.login(self.username, self.password)
                imap.select("INBOX")
                status, data = imap.search(None, "UNSEEN")
                if status != "OK":
                    return []
                for num in data[0].split():
                    status, fetched = imap.fetch(num, "(RFC822)")
                    if status != "OK" or not fetched:
                        continue
                    raw = _extract_raw(fetched)
                    parsed = email.message_from_bytes(raw)
                    if self._ignored(parsed):
                        continue
                    body = parsed.get_payload(decode=True)
                    if isinstance(body, bytes):
                        body = body.decode(parsed.get_content_charset() or "utf-8", errors="replace")
                    in_reply_to = str(parsed.get("In-Reply-To", "") or "").strip()
                    references = parse_message_ids(parsed.get("References", ""))
                    thread_id = str(references[0] if references else in_reply_to)
                    messages.append({
                        "external_id": parsed.get("Message-ID", ""),
                        "thread_id": thread_id,
                        "in_reply_to": in_reply_to,
                        "references": references,
                        "from": email.utils.parseaddr(parsed.get("From", ""))[1],
                        "subject": parsed.get("Subject", ""),
                        "body": str(body or ""),
                    })
        except Exception as exc:
            raise MailboxError(f"IMAP fetch failed: {exc}") from exc
        return messages

    def _connect_imap(self):
        import imaplib

        if self.imap_factory is not None:
            return self.imap_factory()
        return imaplib.IMAP4_SSL(self.imap_host, self.imap_port)

    def fetch_inbox_with_cursor(self, *, cursor: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        """Fetch only mail newer than a durable high-water mark (IMAP UID).

        ``cursor`` carries ``uid_validity`` / ``last_uid`` / ``seeded`` and is
        persisted by the operator between sessions.  The first run merely
        *establishes* the baseline (no messages are ingested — historical mail
        is never treated as a conversation).  If the mailbox is recreated (its
        ``UIDVALIDITY`` changes) the cursor reseeds and starts over.

        Returns ``{"messages": [...], "cursor": {...}}`` so the caller can
        compactly persist the new high-water mark.
        """
        if not self.imap_host:
            return {"messages": [], "cursor": None}

        import email
        import time as _time

        stored_validity = int((cursor or {}).get("uid_validity") or 0)
        last_uid = int((cursor or {}).get("last_uid") or 0)
        seeded = bool((cursor or {}).get("seeded"))

        messages: list[dict[str, Any]] = []
        new_validity = 0
        new_last_uid = last_uid
        try:
            with self._connect_imap() as imap:
                imap.login(self.username, self.password)
                select_status, _ = imap.select("INBOX")
                if select_status != "OK":
                    raise MailboxError("IMAP INBOX could not be selected")

                validity_resp = imap.response("UIDVALIDITY")
                new_validity = int(validity_resp[1][0]) if validity_resp and validity_resp[0] == "OK" and validity_resp[1] else 0
                uidnext_resp = imap.response("UIDNEXT")
                uidnext = int(uidnext_resp[1][0]) if uidnext_resp and uidnext_resp[0] == "OK" and uidnext_resp[1] else 0

                reseed = (not seeded) or (stored_validity and stored_validity != new_validity)
                if reseed:
                    # Baseline only: never ingest mail that predates the operator.
                    new_last_uid = max(uidnext - 1, 0)
                    return {
                        "messages": [],
                        "cursor": {
                            "uid_validity": new_validity,
                            "last_uid": new_last_uid,
                            "seeded": True,
                            "updated_at": _time.time(),
                        },
                    }

                top_uid = max(uidnext - 1, 0)
                if top_uid <= last_uid:
                    return {
                        "messages": [],
                        "cursor": {
                            "uid_validity": new_validity,
                            "last_uid": last_uid,
                            "seeded": True,
                            "updated_at": _time.time(),
                        },
                    }

                status, data = imap.uid("search", None, f"UID {last_uid + 1}:{top_uid}")
                if status == "OK" and data and data[0]:
                    for num in data[0].split():
                        fetch_status, fetched = imap.uid("fetch", num, "(RFC822)")
                        if fetch_status != "OK" or not fetched:
                            continue
                        raw = _extract_raw(fetched)
                        parsed = email.message_from_bytes(raw)
                        if self._ignored(parsed):
                            continue
                        body = parsed.get_payload(decode=True)
                        if isinstance(body, bytes):
                            body = body.decode(parsed.get_content_charset() or "utf-8", errors="replace")
                        in_reply_to = str(parsed.get("In-Reply-To", "") or "").strip()
                        references = parse_message_ids(parsed.get("References", ""))
                        thread_id = str(references[0] if references else in_reply_to)
                        messages.append({
                            "external_id": parsed.get("Message-ID", ""),
                            "thread_id": thread_id,
                            "in_reply_to": in_reply_to,
                            "references": references,
                            "from": email.utils.parseaddr(parsed.get("From", ""))[1],
                            "subject": parsed.get("Subject", ""),
                            "body": str(body or ""),
                        })
                new_last_uid = top_uid
        except Exception as exc:
            raise MailboxError(f"IMAP fetch failed: {exc}") from exc
        return {
            "messages": messages,
            "cursor": {
                "uid_validity": new_validity,
                "last_uid": new_last_uid,
                "seeded": True,
                "updated_at": _time.time(),
            },
        }

    def _ignored(self, parsed: Any) -> bool:
        """True when a message is automation (bounce, autoreply, our own copy)."""
        from_email = parsed.get("From", "")
        from_addr = re.sub(r".*<([^>]+)>", r"\1", from_email).strip().lower()
        if from_addr and from_addr == self.sender.strip().lower():
            return True
        subject = str(parsed.get("Subject", "") or "").lower()
        if any(token in subject for token in (
            "delivery status notification", "undelivered mail", "undeliverable",
            "mail delivery failed", "returned mail", "returned to sender",
            "mail status notification",
        )):
            return True
        content_type = str(parsed.get_content_type() or "").lower()
        if content_type in ("multipart/report", "message/delivery-status", "text/rfc822-headers"):
            return True
        auto_submitted = str(parsed.get("Auto-Submitted", "no") or "no").strip().lower()
        if auto_submitted and auto_submitted != "no":
            return True
        precedence = str(parsed.get("Precedence", "") or "").strip().lower()
        if precedence in ("auto_reply", "bulk", "list"):
            return True
        if parsed.get("X-Autoreply", "") or parsed.get("X-Auto-Response-Suppress", ""):
            return True
        if parsed.get("List-Unsubscribe", "") or parsed.get("List-Id", "") or parsed.get("List-Post", ""):
            return True
        return False

    def validate(self) -> dict[str, Any]:
        """Probe SMTP/IMAP reachability and auth without sending and without
        printing credentials.  Returns per-channel OK/error facts."""
        import smtplib

        smtp: dict[str, Any] = {"host": self.host, "configured": bool(self.host and self.sender), "auth": bool(self.username)}
        if not smtp["configured"]:
            smtp.update({"ok": False, "detail": "missing IDENTITY_SMTP_HOST (and IDENTITY_EMAIL_FROM)"})
        else:
            try:
                with smtplib.SMTP(self.host, self.port, timeout=10) as client:
                    if self.use_tls:
                        client.starttls()
                    if self.username:
                        client.login(self.username, self.password)
                    client.noop()
                smtp.update({"ok": True, "detail": "reachable, authenticated"})
            except Exception as exc:  # pragma: no cover - network dependent
                smtp.update({"ok": False, "detail": f"{type(exc).__name__}: {exc}"})

        imap: dict[str, Any] = {"host": self.imap_host, "configured": bool(self.imap_host), "auth": bool(self.username)}
        if not imap["configured"]:
            imap.update({"ok": False, "detail": "missing IDENTITY_IMAP_HOST"})
        else:
            try:
                import imaplib

                with imaplib.IMAP4_SSL(self.imap_host, self.imap_port) as client:
                    client.login(self.username, self.password)
                    status, _ = client.select("INBOX")
                imap.update({"ok": status == "OK", "detail": "reachable, authenticated, INBOX selectable"})
            except Exception as exc:  # pragma: no cover - network dependent
                imap.update({"ok": False, "detail": f"{type(exc).__name__}: {exc}"})

        return {"smtp": smtp, "imap": imap}


class MailboxTransport:
    """Adapts a mailbox backend to the operations engine transport protocol."""

    def __init__(self, backend: Any) -> None:
        self.backend = backend

    def send(
        self, *, to: str, subject: str, body: str, thread_id: str = "",
        in_reply_to: str = "", references: Optional[Iterable[str]] = None,
    ) -> dict[str, Any]:
        return self.backend.send(
            to=to, subject=subject, body=body, thread_id=thread_id,
            in_reply_to=in_reply_to, references=references,
        )

    def fetch_inbox_with_cursor(self, *, cursor: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        fn = getattr(self.backend, "fetch_inbox_with_cursor", None)
        if fn is None:
            return {"messages": self.backend.fetch_inbox(), "cursor": None}
        return fn(cursor=cursor)

    def fetch_inbox(self) -> list[dict[str, Any]]:
        return self.backend.fetch_inbox()
