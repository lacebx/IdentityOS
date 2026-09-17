"""Ephemeral handling for credentials supplied through conversational input.

The model proposes tool calls, but it must never receive or invent plaintext
credentials.  This module replaces explicitly labelled secrets with opaque,
single-interaction references before input reaches adapters or persistence.
Only the runtime tool gateway may resolve those references.
"""

from __future__ import annotations

import re
import secrets
from typing import Any, Mapping


SECRET_REFERENCE_PREFIX = "secret-ref://"

_SENSITIVE_ARGUMENTS = {
    "api_key",
    "access_token",
    "auth_token",
    "pass",
    "passcode",
    "passwd",
    "password",
    "secret",
    "token",
}

_LABEL = r"(?:password|passwd|passcode|api[ _-]?key|access[ _-]?token|auth[ _-]?token)"
_EXPLICIT_SECRET = re.compile(
    rf"(?P<label>\b{_LABEL}\b\s*(?:(?:is)\s+|[:=]\s*|\s+))"
    r"(?P<value>\"[^\"\r\n]+\"|'[^'\r\n]+'|[^\s,;]+)",
    re.IGNORECASE,
)


class SecretReferenceError(ValueError):
    """Raised when a model tool call contains an unbrokered secret."""


def protect_explicit_secrets(text: str) -> tuple[str, dict[str, str]]:
    """Replace explicitly labelled credentials with opaque references.

    Supported conversational forms include ``password=...``, ``password: ...``,
    ``password is ...``, and ``password ...``. Quoted values may contain spaces.
    The returned mapping must remain local to one interaction and must never be
    serialized, logged, or sent to a model provider.
    """
    protected: dict[str, str] = {}

    def _replace(match: re.Match[str]) -> str:
        raw = match.group("value")
        if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in {"'", '"'}:
            raw = raw[1:-1]
        reference = SECRET_REFERENCE_PREFIX + secrets.token_urlsafe(18)
        protected[reference] = raw
        return match.group("label") + reference

    return _EXPLICIT_SECRET.sub(_replace, text or ""), protected


# Skills that are allowed to receive resolved secret-ref values
_ALLOWED_SECRET_SKILLS = {
    "browser.login",
    # Add other skills that need credential resolution here
}


def _is_secret_ref(value: Any) -> bool:
    """Check if a value is a secret-ref:// pattern."""
    return isinstance(value, str) and value.startswith(SECRET_REFERENCE_PREFIX)


def resolve_sensitive_parameters(
    params: Mapping[str, Any],
    protected: Mapping[str, str],
    skill_name: str = "",
) -> dict[str, Any]:
    """Resolve brokered secrets and reject plaintext model tool arguments.

    Only credential-aware skills (e.g., browser.login) may resolve brokered
    secret references. Callers that do not name a skill (raw resolution during
    a brokered interaction) may also resolve them. Non-credential skills such
    as browser.fill, browser.type, and browser.eval_js will reject secret-ref
    values so credentials never leak into generic automation.
    """
    resolved: dict[str, Any] = {}
    allow_resolution = not skill_name or skill_name in _ALLOWED_SECRET_SKILLS
    for name, value in params.items():
        is_sensitive_param = name.lower() in _SENSITIVE_ARGUMENTS
        is_secret_ref = _is_secret_ref(value)

        if not is_sensitive_param and not is_secret_ref:
            resolved[name] = value
            continue

        if is_secret_ref and value not in protected:
            raise SecretReferenceError(
                f"Parameter '{name}' contains an unknown secret-ref:// value. "
                "Secret references must come from the current interaction's "
                "brokered credentials. Use plain text instead."
            )

        if is_sensitive_param and not is_secret_ref:
            raise SecretReferenceError(
                f"Sensitive parameter '{name}' must use an ephemeral secret reference. "
                "Provide it explicitly in the user request as password=<value> or use "
                "the SDK outside chat."
            )

        if not allow_resolution:
            raise SecretReferenceError(
                f"Parameter '{name}' contains a secret-ref:// value which is not allowed in skill '{skill_name}'. "
                f"Only credential-aware skills (e.g., browser.login) may use secret-ref. "
                f"Use plain text instead."
            )

        resolved[name] = protected[value]
    return resolved

