"""Generic Agent-to-Agent (A2A) protocol client and a controlled local peer.

A2A lets agents expose themselves behind a well-known *agent card* and
exchange messages through the ``/tasks`` resource.  This module implements the
read side (card discovery + capability inspection) and the messaging side
(```send`` + ``receive``) over the shared HTTP transport, keeping everything
injectable so tests can pair two in-process agents with zero network access.

All card content is treated as *provider-supplied data*: the runtime decides
what to do with a listed capability; it never assumes one exists somewhere.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Optional

from .http import HttpClient, Transport, parse_body

CARD_PATH = "/.well-known/agent.json"
CARD_FALLBACK = "/agent.json"

TASK_STATUSES = ("submitted", "working", "input-required", "completed", "failed", "canceled")


class A2AError(Exception):
    """A2A protocol or transport error."""


class A2ANotFound(A2AError):
    """No agent card was published at the given base URL."""


def discover_agent_card(base_url: str, http: Optional[HttpClient] = None) -> dict[str, Any]:
    """Fetch an agent card: ``/.well-known/agent.json`` with ``/agent.json`` fallback."""
    client = http or HttpClient()
    for path in (CARD_PATH, CARD_FALLBACK):
        try:
            response = client.get(f"{base_url.rstrip('/')}{path}")
        except Exception as exc:  # transport-level failures are retried on fallback
            raise A2AError(f"agent card fetch failed: {exc}") from exc
        if response.status == 200 and response.text.strip():
            card = parse_body(response.text, response.content_type)
            if isinstance(card, dict):
                return card
    raise A2ANotFound(f"No agent card found for {base_url}")


@dataclass
class A2ATask:
    id: str
    status: str
    result: Any = None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def completed(self) -> bool:
        return self.status == "completed"

    @property
    def failed(self) -> bool:
        return self.status == "failed"

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "status": self.status, "result": self.result}


class A2AClient:
    """Client for one remote agent reached over the A2A well-known card + tasks surface."""

    def __init__(
        self,
        base_url: str,
        *,
        http: Optional[HttpClient] = None,
        agent_card: Optional[dict[str, Any]] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._http = http or HttpClient()
        self._card = agent_card

    def card(self) -> dict[str, Any]:
        if self._card is None:
            self._card = discover_agent_card(self.base_url, http=self._http)
        return self._card

    def name(self) -> str:
        return str(self.card().get("name") or self.card().get("title") or self.base_url)

    def capabilities(self) -> list[dict[str, Any]]:
        """Inspect the capabilities the agent advertises (treated as data only)."""
        raw = self.card().get("capabilities") or []
        inspected: list[dict[str, Any]] = []
        for entry in raw if isinstance(raw, list) else []:
            if not isinstance(entry, dict):
                continue
            name = str(entry.get("name") or entry.get("id") or "")
            if not name:
                continue
            inspected.append(
                {
                    "name": name,
                    "description": str(entry.get("description", "")),
                    "input_modes": list(entry.get("inputModes") or entry.get("input_modes") or []),
                }
            )
        return inspected

    def send_message(self, message: str, *, session_id: str = "") -> A2ATask:
        """Send a message and create a task (non-blocking submission)."""
        body: dict[str, Any] = {"message": message}
        if session_id:
            body["sessionId"] = session_id
        response = self._http.post(f"{self.base_url}/tasks", body=body)
        if response.status < 200 or response.status >= 300:
            raise A2AError(f"send failed: HTTP {response.status}")
        payload = parse_body(response.text, response.content_type)
        if not isinstance(payload, dict):
            raise A2AError("send response was not an object")
        return _task_from_payload(payload)

    def receive(self, task_id: str) -> A2ATask:
        """Fetch the current state of a previously created task."""
        response = self._http.get(f"{self.base_url}/tasks/{task_id}")
        if response.status == 404:
            raise A2ANotFound(f"task {task_id} not found")
        if response.status < 200 or response.status >= 300:
            raise A2AError(f"receive failed: HTTP {response.status}")
        payload = parse_body(response.text, response.content_type)
        if not isinstance(payload, dict):
            raise A2AError("task response was not an object")
        return _task_from_payload(payload)

    def exchange(self, message: str, *, session_id: str = "", poll_max: int = 10) -> A2ATask:
        """Send a message and poll the presented task to completion."""
        task = self.send_message(message, session_id=session_id)
        attempts = 0
        while task.status in ("submitted", "working") and attempts < poll_max:
            task = self.receive(task.id)
            attempts += 1
        if task.status in ("submitted", "working"):
            raise A2AError(f"task {task.id} did not reach a terminal state")
        return task


def _task_from_payload(payload: dict[str, Any]) -> A2ATask:
    task_id = str(payload.get("id") or payload.get("task_id") or "")
    if not task_id:
        raise A2AError("task payload did not include an id")
    status = str(payload.get("status") or payload.get("state") or "submitted").lower()
    if status not in TASK_STATUSES and status != "completed":
        status = "submitted"
    result = payload.get("result") or payload.get("output") or payload.get("message")
    return A2ATask(id=task_id, status=status, result=result, raw=payload)


# ─────────────────────────────────────────────────────────────────────────────
# Controlled local peer (in-process transport) — no network required.
# ─────────────────────────────────────────────────────────────────────────────


def _clean_handle(value: str) -> str:
    # Session / task handles must be inert strings; printable ASCII only.
    return re.sub(r"[^A-Za-z0-9._~:-]", "", value)[:96]


class A2ATestAgent:
    """Deterministic in-process A2A agent for local, offline proofs.

    Serves the well-known card, accepts ``POST /tasks`` (creating a task that
    completes with the handler's reply), and answers ``GET /tasks/<id>``.
    Wrap it with :func:`a2a_local_transport` to run an :class:`A2AClient`
    against it without any network.
    """

    def __init__(
        self,
        *,
        name: str = "local-test-agent",
        description: str = "Controlled in-process A2A peer used to validate IdentityOS agent interoperability.",
        handler: Optional[Callable[[str, str], str]] = None,
        url: str = "http://local.invalid",
    ) -> None:
        self.name = name
        self.description = description
        self.url = url
        self.handler = handler or (lambda message, session_id: f"echo: {message}")
        self._tasks: dict[str, dict[str, Any]] = {}

    def card(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "title": self.name,
            "description": self.description,
            "url": self.url,
            "version": "1.0.0",
            "capabilities": [
                {
                    "name": "echo",
                    "description": "Respond to a message deterministically.",
                    "inputModes": ["text/plain"],
                }
            ],
        }

    def _handle_send(self, body: Any) -> dict[str, Any]:
        if not isinstance(body, dict):
            body = {}
        message = str(body.get("message") or "")
        if not message.strip():
            raise A2AError("empty message")
        session_id = _clean_handle(str(body.get("sessionId") or ""))
        task_id = _clean_handle(str(uuid.uuid4()))
        reply = str(self.handler(message, session_id))
        self._tasks[task_id] = {
            "id": task_id,
            "status": "completed",
            "result": reply,
            "message": message,
            "sessionId": session_id,
        }
        return self._tasks[task_id]

    def _handle_receive(self, task_id: str) -> Optional[dict[str, Any]]:
        return self._tasks.get(task_id)

    def transport(self) -> Transport:
        """Return an in-process transport callable compatible with HttpClient."""
        from .http import MAX_RESPONSE_BYTES

        def serve(request: Mapping[str, Any], timeout: float) -> tuple[int, str, str, dict[str, str]]:
            url = str(request.get("url", self.url))
            method = str(request.get("method", "GET")).upper()
            raw = request.get("body")
            body = None
            if raw:
                try:
                    body = json.loads(raw.decode("utf-8"))
                except (ValueError, UnicodeDecodeError):
                    body = None
            path = url[len(self.url.rstrip("/")):] if url.startswith(self.url.rstrip("/")) else url
            path = path.split("?", 1)[0]
            result: Any = {"error": "not_found"}
            status = 404
            if path in (CARD_PATH, CARD_FALLBACK):
                result = self.card()
                status = 200
            elif path == "/tasks" and method == "POST":
                result = self._handle_send(body)
                status = 200
            elif path.startswith("/tasks/") and method == "GET":
                task = self._handle_receive(path.rsplit("/", 1)[-1])
                if task is not None:
                    result = task
                    status = 200
            text = json.dumps(result)
            return status, "application/json", text[:MAX_RESPONSE_BYTES], {"content-type": "application/json"}

        return serve


def a2a_local_transport(agent: A2ATestAgent) -> Transport:
    """In-process transport that routes HTTP to the given local A2A agent."""
    return agent.transport()


# ─────────────────────────────────────────────────────────────────────────────
# Local peer registry — every identity can reach every other identity.
# ─────────────────────────────────────────────────────────────────────────────

_LOCAL_PEERS: dict[str, "A2ATestAgent"] = {}


def register_local_peer(agent: A2ATestAgent) -> A2ATestAgent:
    """Register an in-process A2A peer.

    Registration is name-keyed and idempotent: once registered, any identity's
    ``a2a`` capability can address this peer by name (or its identity id)
    without network access.
    """
    _LOCAL_PEERS[agent.name] = agent
    return agent


def get_local_peer(name: str) -> Optional[A2ATestAgent]:
    """Resolve a local peer by agent name or identity id (case-insensitive)."""
    candidate = (name or "").strip().lower()
    if not candidate:
        return None
    for key, peer in _LOCAL_PEERS.items():
        if key.lower() == candidate:
            return peer
    for peer in _LOCAL_PEERS.values():
        identity_id = str(getattr(peer, "_identity_id", "") or "")
        if identity_id.lower() == candidate:
            return peer
    return None


def local_peer_names() -> list[str]:
    return sorted(_LOCAL_PEERS)


class A2ARuntimeAgent(A2ATestAgent):
    """An in-process A2A peer backed by a live identity runtime.

    Messages sent to this peer are handled by the receiving identity's *real*
    runtime (policy → context → model → memory), so the reply comes from that
    identity's own persistent state — never a template echo.
    """

    def __init__(
        self,
        *,
        runtime: Any,
        identity_id: str,
        description: str = "",
        url: str = "",
    ) -> None:
        self._runtime = runtime
        self._identity_id = identity_id
        spec = None
        loader = getattr(runtime, "load", None)
        if loader is not None:
            spec = loader(identity_id)
        name = str(getattr(spec, "name", "") or identity_id)
        super().__init__(
            name=name,
            description=description or f"{name} — an IdentityOS agent reachable over A2A.",
            url=url or f"a2a://identityos/{identity_id}",
            handler=None,
        )

    def card(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "title": self.name,
            "description": self.description,
            "url": self.url,
            "version": "1.0.0",
            "capabilities": [
                {
                    "name": "converse",
                    "description": "Discuss and collaborate with this identity over A2A; replies come from the identity's own persistent runtime state.",
                    "inputModes": ["text/plain"],
                }
            ],
        }

    def _handle_send(self, body: Any) -> dict[str, Any]:
        if not isinstance(body, dict):
            body = {}
        message = str(body.get("message") or "")
        if not message.strip():
            raise A2AError("empty message")
        session_id = _clean_handle(str(body.get("sessionId") or ""))
        from runtime.orchestrator import InteractionRequest

        # An inbound A2A conversation is a *discussion* turn: the receiving
        # identity answers from its own persistent state. Offering tool
        # catalogs here makes the model fabricate tool calls (observed: a2a
        # calls with invented task ids) instead of conversing, so the tool
        # loop is disabled for the duration of this synchronous handler.
        prior_limit = getattr(self._runtime, "max_tools_per_request", None)
        try:
            self._runtime.max_tools_per_request = 0
            reply = self._runtime.process(
                InteractionRequest(
                    identity_id=self._identity_id, user_input=message,
                    session_id=session_id or None,
                ),
                top_k_memories=4,
            )
        finally:
            if prior_limit is not None:
                self._runtime.max_tools_per_request = prior_limit
        output = str(getattr(reply, "output", "") or "")
        task_id = _clean_handle(str(uuid.uuid4()))
        self._tasks[task_id] = {
            "id": task_id,
            "status": "completed",
            "result": output,
            "message": message,
            "sessionId": session_id,
        }
        return self._tasks[task_id]