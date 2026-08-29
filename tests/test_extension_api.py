"""
test_extension_api.py — Evidence 3: Chrome Extension API Contract

Validates the full API contract that the Chrome extension relies on:
  1. GET  /health          — runtime is reachable
  2. GET  /identity        — list identities
  3. POST /identity        — create a new identity
  4. POST /context         — get augmented context for prompt injection
  5. POST /evaluate        — store memories from an exchange
  6. GET  /identity/<id>   — get identity details

This proves the extension's backend surface works end-to-end.
"""

import asyncio
import os
import tempfile

import httpx
import pytest

from core.evaluation import register_default_criteria
from runtime.orchestrator import IdentityRuntime
from runtime.persistence import JSONFileBackend


@pytest.fixture(scope="module")
def api_app():
    """Exercise the ASGI contract in-process with isolated persistent state."""
    from runtime import main as runtime_main

    with tempfile.TemporaryDirectory(prefix="identity_test_store_") as store_dir:
        previous_store = os.environ.get("IDENTITY_STORE_PATH")
        previous_runtime = runtime_main.runtime
        previous_backend = runtime_main.storage
        storage = JSONFileBackend(root_dir=store_dir)
        runtime = IdentityRuntime(storage=storage, adapter=None)
        register_default_criteria(runtime.evaluation_engine)
        os.environ["IDENTITY_STORE_PATH"] = store_dir
        runtime_main.storage = storage
        runtime_main.runtime = runtime
        try:
            yield runtime_main.app
        finally:
            runtime_main.runtime = previous_runtime
            runtime_main.storage = previous_backend
            if previous_store is None:
                os.environ.pop("IDENTITY_STORE_PATH", None)
            else:
                os.environ["IDENTITY_STORE_PATH"] = previous_store


def _req(app, method, path, data=None):
    async def request():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.request(method, path, json=data)

    response = asyncio.run(request())
    try:
        body = response.json()
    except ValueError:
        body = response.text
    return response.status_code, body


class TestExtensionAPI:
    """Every endpoint the Chrome extension calls must work."""

    def test_health(self, api_app):
        status, data = _req(api_app, "GET", "/health")
        assert status == 200
        assert data["status"] == "ok"

    def test_list_identities(self, api_app):
        status, data = _req(api_app, "GET", "/identity")
        assert status == 200
        assert "identities" in data
        assert isinstance(data["identities"], list)

    def test_create_identity(self, api_app):
        status, data = _req(api_app, "POST", "/identity", {
            "identity_id": "ext-test-bot",
            "name": "Extension Test Bot",
            "persona": "A test identity for the Chrome extension",
            "role": "tester",
        })
        assert status == 200, f"Create failed: {data}"
        assert data["status"] == "created"
        assert data["id"] == "ext-test-bot"

    def test_get_identity(self, api_app):
        status, data = _req(api_app, "GET", "/identity/ext-test-bot")
        assert status == 200
        assert data.get("name") == "Extension Test Bot"

    def test_get_context(self, api_app):
        status, data = _req(api_app, "POST", "/context", {
            "message": "Hello!",
            "identity_id": "ext-test-bot",
            "user_id": "ext-user",
        })
        assert status == 200, f"Context failed: {data}"
        assert "augmented_context" in data
        assert "identity_name" in data
        assert data["identity_name"] == "Extension Test Bot"

    def test_evaluate(self, api_app):
        status, data = _req(api_app, "POST", "/evaluate", {
            "message": "What is your purpose?",
            "response": "I am a test identity for the Chrome extension.",
            "identity_id": "ext-test-bot",
            "user_id": "ext-user",
        })
        assert status == 200, f"Evaluate failed: {data}"
        assert "memories_stored" in data
        assert isinstance(data["memories_stored"], int)
        assert "summary" in data
