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

import os
import time
import urllib.request
import urllib.error
import json
import subprocess
import sys
from pathlib import Path

import pytest


API_BASE = "http://localhost:8000"
SERVER_WAIT = 5


@pytest.fixture(scope="module")
def runtime_server():
    """Start a live runtime server for the test session."""
    repo_root = Path(__file__).resolve().parent.parent
    env = os.environ.copy()
    env["OPENROUTER_API_KEY"] = env.get("OPENROUTER_API_KEY", "")
    env["GROQ_API_KEY"] = env.get("GROQ_API_KEY", "")

    proc = subprocess.Popen(
        [sys.executable, "-m", "runtime.main"],
        cwd=str(repo_root),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(SERVER_WAIT)

    # Verify server started
    for _ in range(10):
        try:
            resp = urllib.request.urlopen(f"{API_BASE}/health", timeout=2)
            if resp.status == 200:
                break
        except Exception:
            time.sleep(1)
    else:
        proc.kill()
        pytest.fail("Runtime server failed to start")

    yield

    proc.kill()
    proc.wait()


def _req(method, path, data=None):
    url = f"{API_BASE}{path}"
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


class TestExtensionAPI:
    """Every endpoint the Chrome extension calls must work."""

    def test_health(self, runtime_server):
        status, data = _req("GET", "/health")
        assert status == 200
        assert data["status"] == "ok"

    def test_list_identities(self, runtime_server):
        status, data = _req("GET", "/identity")
        assert status == 200
        assert "identities" in data
        assert isinstance(data["identities"], list)

    def test_create_identity(self, runtime_server):
        status, data = _req("POST", "/identity", {
            "identity_id": "ext-test-bot",
            "name": "Extension Test Bot",
            "persona": "A test identity for the Chrome extension",
            "role": "tester",
        })
        assert status == 200, f"Create failed: {data}"
        assert data["status"] == "created"
        assert data["id"] == "ext-test-bot"

    def test_get_identity(self, runtime_server):
        status, data = _req("GET", "/identity/ext-test-bot")
        assert status == 200
        assert data.get("name") == "Extension Test Bot"

    def test_get_context(self, runtime_server):
        status, data = _req("POST", "/context", {
            "message": "Hello!",
            "identity_id": "ext-test-bot",
            "user_id": "ext-user",
        })
        assert status == 200, f"Context failed: {data}"
        assert "augmented_context" in data
        assert "identity_name" in data
        assert data["identity_name"] == "Extension Test Bot"

    def test_evaluate(self, runtime_server):
        status, data = _req("POST", "/evaluate", {
            "message": "What is your purpose?",
            "response": "I am a test identity for the Chrome extension.",
            "identity_id": "ext-test-bot",
            "user_id": "ext-user",
        })
        assert status == 200, f"Evaluate failed: {data}"
        assert "memories_stored" in data
        assert isinstance(data["memories_stored"], int)
        assert "summary" in data
