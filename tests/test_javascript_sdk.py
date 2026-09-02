import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_javascript_sdk_targets_only_the_public_api():
    source = (ROOT / "clients/javascript/index.js").read_text()
    for route in ("/identity", "/chat", "/memory", "/goal", "/export"):
        assert route in source
    assert "runtime/" not in source
    assert "core/" not in source
    assert "X-API-Key" in source


def test_vscode_extension_uses_sdk_and_project_partitions():
    package = json.loads((ROOT / "vscode-extension/package.json").read_text())
    source = (ROOT / "vscode-extension/extension.js").read_text()

    assert package["dependencies"]["@identityos/sdk"].startswith("file:")
    assert "require('@identityos/sdk')" in source
    assert "fetch(" not in source
    assert "sha256" in source
    assert "workspaceState" in source
    assert "globalState" in source
    for command in ("chat", "selectIdentity", "rememberSelection", "addProjectGoal", "showStatus"):
        assert f"identityos.{command}" in source


def test_javascript_sdk_contract_matches_openapi():
    from runtime.main import app

    paths = app.openapi()["paths"]
    assert "post" in paths["/chat"]
    assert "post" in paths["/memory"]
    assert "post" in paths["/goal"]
    assert "get" in paths["/identity"]
