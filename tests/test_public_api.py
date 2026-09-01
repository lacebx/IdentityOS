"""Executable contract for the public IdentityOS REST API."""

from __future__ import annotations

import asyncio

import httpx
import pytest

from core.evaluation import register_default_criteria
from runtime.orchestrator import IdentityRuntime
from runtime.persistence import JSONFileBackend


@pytest.fixture()
def public_api(tmp_path, monkeypatch):
    from runtime import main as runtime_main

    previous_runtime = runtime_main.runtime
    previous_storage = runtime_main.storage
    store_path = tmp_path / "store"
    storage = JSONFileBackend(root_dir=str(store_path))
    runtime = IdentityRuntime(storage=storage, adapter=None)
    register_default_criteria(runtime.evaluation_engine)
    monkeypatch.setenv("IDENTITY_STORE_PATH", str(store_path))
    monkeypatch.delenv("IDENTITY_API_KEY", raising=False)
    monkeypatch.delenv("IDENTITY_API_KEYS", raising=False)
    monkeypatch.setenv("IDENTITY_RATE_LIMIT_PER_MINUTE", "120")
    runtime_main.runtime = runtime
    runtime_main.storage = storage
    runtime_main._rate_limiter.reset()
    try:
        yield runtime_main, storage
    finally:
        runtime_main._rate_limiter.reset()
        runtime_main.runtime = previous_runtime
        runtime_main.storage = previous_storage


def _request(app, method, path, data=None, headers=None):
    async def request():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.request(method, path, json=data, headers=headers)

    return asyncio.run(request())


def _create_identity(app):
    response = _request(
        app,
        "POST",
        "/identity",
        {
            "identity_id": "public-api-test",
            "name": "Public API Test",
            "persona": "evidence driven",
        },
    )
    assert response.status_code == 200, response.text


def test_public_mutation_endpoints_persist_real_state(public_api):
    runtime_main, storage = public_api
    app = runtime_main.app
    _create_identity(app)

    chat = _request(
        app,
        "POST",
        "/chat",
        {
            "identity_id": "public-api-test",
            "user_id": "api-user",
            "message": "Hello",
        },
    )
    assert chat.status_code == 200, chat.text
    assert chat.json()["identity_id"] == "public-api-test"

    memory = _request(
        app,
        "POST",
        "/memory",
        {
            "identity_id": "public-api-test",
            "user_id": "api-user",
            "content": "The API stores real memories.",
            "tags": ["api"],
        },
    )
    assert memory.status_code == 200, memory.text
    assert memory.json()["status"] == "stored"

    goal = _request(
        app,
        "POST",
        "/goal",
        {
            "identity_id": "public-api-test",
            "title": "Ship the public API",
            "priority": "high",
        },
    )
    assert goal.status_code == 200, goal.text
    assert goal.json()["goal"]["title"] == "Ship the public API"

    relationship = _request(
        app,
        "POST",
        "/relationship",
        {
            "identity_id": "public-api-test",
            "entity_id": "api-user",
            "trust_level": 0.8,
            "edge_type": "collaborator",
            "context": "Built through the public API",
        },
    )
    assert relationship.status_code == 200, relationship.text
    assert relationship.json()["relationship"]["trust_level"] == 3

    timeline = _request(
        app,
        "POST",
        "/timeline",
        {
            "identity_id": "public-api-test",
            "event_type": "milestone",
            "title": "API verified",
            "significance": 4,
        },
    )
    assert timeline.status_code == 200, timeline.text
    assert timeline.json()["event_id"]

    constitution = _request(
        app,
        "POST",
        "/constitution",
        {"identity_id": "public-api-test"},
    )
    assert constitution.status_code == 200, constitution.text
    assert constitution.json()["constitution"]
    assert constitution.json()["laws"]

    exported = _request(
        app,
        "POST",
        "/export",
        {"identity_id": "public-api-test"},
    )
    assert exported.status_code == 200, exported.text
    body = exported.json()
    assert body["identity"]["id"] == "public-api-test"
    assert any(m["content"] == "The API stores real memories." for m in body["memories"])
    assert any(g["title"] == "Ship the public API" for g in body["goals"])
    assert any(r["target_id"] == "api-user" for r in body["relationships"])
    assert any(e["title"] == "API verified" for e in body["timeline"]["events"])

    restarted = IdentityRuntime(storage=storage, adapter=None)
    assert restarted.load("public-api-test") is not None
    assert any(
        memory.content == "The API stores real memories."
        for memory in restarted.memory_store.by_identity("public-api-test")
    )
    assert any(goal.title == "Ship the public API" for goal in restarted.goal_engine.all())
    assert any(
        edge.target_id == "api-user"
        for edge in restarted.identity_graph.get_relationships("public-api-test")
    )
    assert any(
        event.title == "API verified"
        for event in restarted.timeline_registry.get("public-api-test").events()
    )


def test_api_key_authentication_and_health_exemption(public_api, monkeypatch):
    runtime_main, _ = public_api
    monkeypatch.setenv("IDENTITY_API_KEY", "test-secret")

    denied = _request(runtime_main.app, "GET", "/identity")
    assert denied.status_code == 401
    assert denied.json()["error"] == "unauthorized"

    allowed = _request(
        runtime_main.app,
        "GET",
        "/identity",
        headers={"Authorization": "Bearer test-secret"},
    )
    assert allowed.status_code == 200

    health = _request(runtime_main.app, "GET", "/health")
    assert health.status_code == 200


def test_rate_limit_returns_retryable_error(public_api, monkeypatch):
    runtime_main, _ = public_api
    monkeypatch.setenv("IDENTITY_API_KEY", "rate-test")
    monkeypatch.setenv("IDENTITY_RATE_LIMIT_PER_MINUTE", "1")
    runtime_main._rate_limiter.reset()
    headers = {"X-API-Key": "rate-test"}

    first = _request(runtime_main.app, "GET", "/identity", headers=headers)
    second = _request(runtime_main.app, "GET", "/identity", headers=headers)

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.headers["retry-after"] == "60"
    assert second.json()["error"] == "rate_limit_exceeded"


def test_openapi_exposes_all_issue_16_operations(public_api):
    runtime_main, _ = public_api
    schema = _request(runtime_main.app, "GET", "/openapi.json").json()
    for path in (
        "/chat",
        "/identity",
        "/memory",
        "/goal",
        "/relationship",
        "/timeline",
        "/constitution",
        "/export",
        "/health",
    ):
        assert path in schema["paths"]
