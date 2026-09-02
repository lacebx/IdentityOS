"""Static contract tests for the privacy-aware cross-browser bridge."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "extension"


def test_manifest_covers_supported_browsers_and_sites():
    manifest = json.loads((EXTENSION / "manifest.json").read_text())
    matches = manifest["content_scripts"][0]["matches"]

    for host in (
        "chatgpt.com",
        "claude.ai",
        "gemini.google.com",
        "grok.com",
        "github.com",
        "www.reddit.com",
        "www.youtube.com",
    ):
        assert any(host in match for match in matches)

    assert manifest["manifest_version"] == 3
    assert manifest["browser_specific_settings"]["gecko"]["id"]
    assert set(manifest["background"].values()) >= {"background.js"}
    for script in manifest["content_scripts"][0]["js"]:
        assert (EXTENSION / script).is_file()


def test_content_script_uses_only_the_background_broker():
    script = (EXTENSION / "content_universal.js").read_text()

    assert "GET_CONTEXT" in script
    assert "SUBMIT_EVAL" in script
    for private_value in ("localhost:8000", "extension-user", "apiKey"):
        assert private_value not in script

    # Social profiles expose a private sidecar but never modify public inputs.
    for host in ("github.com", "www.reddit.com", "www.youtube.com"):
        profile = next(line for line in script.splitlines() if f"'{host}'" in line)
        assert "inject: false" in profile


def test_background_owns_privacy_partitioning_cache_and_retry_queue():
    script = (EXTENSION / "background.js").read_text()

    for contract in (
        "siteAccess",
        "partitionByPlatform",
        "identity_context_cache",
        "pending_evaluations",
        "X-API-Key",
        "slice(-200)",
    ):
        assert contract in script


def test_popup_exposes_every_privacy_control():
    html = (EXTENSION / "popup.html").read_text()

    for site in ("chatgpt", "claude", "gemini", "grok", "github", "reddit", "youtube"):
        assert f'data-site="{site}"' in html
    assert 'id="partition-platform"' in html
    assert 'id="api-key"' in html


def test_legacy_site_specific_scripts_are_removed():
    assert not (EXTENSION / "content_chatgpt.js").exists()
    assert not (EXTENSION / "content_grok.js").exists()
