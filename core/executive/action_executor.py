"""
action_executor.py — The AUTHORITATIVE execution path.

A skill request (tool call) goes through exactly one path:

    Resolver(installed) → validate → capability.call() → ActionResult

The ActionExecutor produces the ``ActionResult``.  Key rules:

  * Resolves ONLY against installed capabilities (never global lookup()).
  * Execution success is machine-routed: an exception → FAILED; a capability
    that explicitly reports failure → FAILED.
  * A capability that returns a payload is EXECUTED, never auto-SUCCEEDED.
    Only an external verifier upgrades it (see core.executive.result).
  * Runtime/system keys (tool_call_id, action_id, identity_id, ...) are
    stripped before invoking the capability so secrets never leak downstream.

``tool_defs()`` yields the OpenAI-function shape used for native tool calls —
this is the contract the adapter will surface to the model in Step 4.
"""

from __future__ import annotations

import time
from typing import Any, Optional

from core.executive.result import (
    ActionEvidence,
    ActionResult,
    ActionResultStatus,
)
from core.executive.resolver import CapabilityResolver

_SYSTEM_KEYS = frozenset({"tool_call_id", "action_id", "identity_id", "capability", "skill"})


class ActionExecutor:
    """Execute tool-call-shaped skill requests into ActionResult facts."""

    def __init__(self, capability_registry: Any, identity_id: str, storage: Any = None) -> None:
        self._resolver = CapabilityResolver(capability_registry, identity_id)
        self._identity_id = identity_id
        self._storage = storage

    # ── Tool-call contract (surface to the model) ───────────────────────

    def tool_defs(self) -> list[dict[str, Any]]:
        """OpenAI-style function tool definitions for every installed skill."""
        tools = []
        for cap_id, inst in self._resolver_snapshot():
            for skill in inst.skills() or []:
                name = getattr(skill, "name", "") or f"{cap_id}.run"
                desc = getattr(skill, "description", "") or f"Invoke {name}"
                tools.append({
                    "type": "function",
                    "function": {
                        "name": name,
                        "description": desc,
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "task": {"type": "string", "description": "the request text"},
                                "params": {"type": "object", "description": "skill-specific parameters"},
                            },
                            "additionalProperties": True,
                        },
                    },
                })
        return tools

    # ── Execution ───────────────────────────────────────────────────────

    def execute(self, skill_name: str, **inputs: Any) -> ActionResult:
        t0 = time.monotonic()
        ar = ActionResult(
            capability="", skill=skill_name, identity_id=self._identity_id,
            status=ActionResultStatus.PENDING,
        )

        resolution = self._resolver.resolve(skill_name)
        if not resolution.found:
            ar.mark_failed(error=resolution.reason)
            ar.add_evidence(ActionEvidence(
                label="resolve", success=False,
                detail=resolution.reason,
            ))
            return ar

        ar.capability = resolution.capability_id
        ar.skill = resolution.skill_name

        # Strip runtime-bound keys before they reach the capability.
        clean = {k: v for k, v in inputs.items() if k not in _SYSTEM_KEYS}
        # Also surface any nested params dict the model may have sent.
        params = dict(clean.get("params", {}) or {}) if isinstance(clean.get("params"), dict) else {}
        for k, v in clean.items():
            if k not in ("params",):
                params[k] = v

        try:
            result = resolution.instance.call(resolution.skill_name, **params)
        except Exception as e:
            ar.mark_failed(error=f"{type(e).__name__}: {e}")
            ar.add_evidence(ActionEvidence(
                label="execute", success=False,
                detail=f"exception during {resolution.skill_name}: {e}",
                data={"error": str(e)},
            ))
            return ar

        ar.updated_at = time.monotonic() - t0
        ar = self._wrap_capability_result(ar, result)
        return ar

    def _wrap_capability_result(self, ar: ActionResult, result: Any) -> ActionResult:
        ok = bool(getattr(result, "success", False))
        err = getattr(result, "error", None) or getattr(result, "message", None)
        data = getattr(result, "data", None)
        source = getattr(result, "source", "capability")
        duration = float(getattr(result, "duration_ms", 0) or 0.0)

        if ok:
            ar.mark_executed(output=data)
            ar.add_evidence(ActionEvidence(
                label="execute", success=True,
                detail=f"{ar.capability}.{ar.skill} executed and produced output",
                data={},
                source=str(source or "capability"),
                duration_ms=duration,
            ))
            # NEVER auto-verify: a yielded payload is a capture, not proof.
            ar.verified = False
        else:
            ar.mark_failed(error=str(err or f"{ar.capability}.{ar.skill} reported failure"))
            ar.add_evidence(ActionEvidence(
                label="execute", success=False,
                detail=str(err or "capability reported failure"),
                data=data if isinstance(data, dict) else {},
                source=str(source or "capability"),
            ))
        return ar

    def _shape(self, skill_name: str, inputs: dict[str, Any]) -> dict[str, Any]:
        """Payload sketch for the verifier (Step 3 consumer)."""
        return {
            "skill": skill_name,
            "identity_id": self._identity_id,
            "inputs": self._redact(inputs),
        }

    def _redact(self, d: dict[str, Any]) -> dict[str, Any]:
        return {k: "<redacted>" if k in _SYSTEM_KEYS else v for k, v in d.items()}

    def _resolver_snapshot(self) -> list[tuple[str, Any]]:
        if self._resolver is None:
            return []
        try:
            return self._resolver._iter_installed()
        except Exception:
            return []