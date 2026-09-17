"""Tests for runtime.sensitive secret brokering.

These verify the invariant that explicitly supplied credentials are
replaced with opaque single-interaction references before they reach a
model, and that only credential-aware skills may resolve them.
"""

from __future__ import annotations

import pytest

from runtime.sensitive import (
    SECRET_REFERENCE_PREFIX,
    SecretReferenceError,
    protect_explicit_secrets,
    resolve_sensitive_parameters,
)


def _credential_payload(label: str, value: str) -> str:
    """Render a single-token ``label=value`` pair as a model would emit it."""
    return label + "=" + value


class TestProtectExplicitSecrets:
    def test_password_equals_form_is_brokered(self):
        text, mapping = protect_explicit_secrets(
            "the " + _credential_payload("password", "fixture-a") + " is unsafe"
        )
        assert SECRET_REFERENCE_PREFIX in text
        assert "fixture-a" not in text
        assert "fixture-a" in mapping.values()
        assert all(ref.startswith(SECRET_REFERENCE_PREFIX) for ref in mapping)

    def test_password_colon_and_quoted_spaces_are_brokered(self):
        text, mapping = protect_explicit_secrets(
            'login password: "quoted value with spaces" now'
        )
        assert "quoted value with spaces" not in text
        assert "quoted value with spaces" in mapping.values()

    def test_no_secret_leaves_text_unchanged(self):
        text, mapping = protect_explicit_secrets("nothing sensitive here")
        assert text == "nothing sensitive here"
        assert mapping == {}


class TestResolveSensitiveParameters:
    def test_browser_login_resolves_brokered_secret(self):
        mapping, reference = self._broke_a_secret()
        resolved = resolve_sensitive_parameters(
            {"password": reference},
            mapping,
            skill_name="browser.login",
        )
        assert resolved["password"] == "fixture-a"

    def test_raw_resolution_without_skill_is_allowed(self):
        mapping, reference = self._broke_a_secret()
        resolved = resolve_sensitive_parameters({"password": reference}, mapping)
        assert resolved["password"] == "fixture-a"

    def test_generic_automation_skill_rejects_secret_ref(self):
        mapping, reference = self._broke_a_secret()
        with pytest.raises(SecretReferenceError, match="browser.fill"):
            resolve_sensitive_parameters(
                {"password": reference},
                mapping,
                skill_name="browser.fill",
            )
        with pytest.raises(SecretReferenceError, match="browser.eval_js"):
            resolve_sensitive_parameters(
                {"password": reference},
                mapping,
                skill_name="browser.eval_js",
            )

    def test_plaintext_sensitive_argument_is_rejected(self):
        with pytest.raises(SecretReferenceError, match="ephemeral secret reference"):
            resolve_sensitive_parameters(
                {"password": _credential_payload("password", "fixture-b")},
                {},
                skill_name="browser.login",
            )

    def test_unknown_secret_ref_is_rejected(self):
        with pytest.raises(SecretReferenceError, match="unknown secret-ref"):
            resolve_sensitive_parameters(
                {"password": "secret-ref://forged"},
                {},
                skill_name="browser.login",
            )

    @staticmethod
    def _broke_a_secret() -> tuple[dict[str, str], str]:
        _, mapping = protect_explicit_secrets(_credential_payload("password", "fixture-a"))
        (reference,) = mapping
        return mapping, reference