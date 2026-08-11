"""
result.py — The canonical ActionResult.

The runtime fact every interchange is built around:

    The LLM can REQUEST an action. It can never DECLARE an action successful.
    The runtime executes an action and produces an ``ActionResult`` whose status
    is a machine transition, plus a list of ``ActionEvidence`` items describing
    what was actually observed.  The model only interprets this result.

Status lifecycle::

    PENDING → EXECUTING → EXECUTED → SUCCEEDED   (via runtime verifier)
                        \→ FAILED
    PENDING → SKIPPED

    * ``EXECUTED`` means the runtime invoked the action and captured output —
      it is NOT a claim of goal success.
    * ``SUCCEEDED`` is ONLY reachable by an explicit verifier transition
      (``mark_succeeded``) after inspecting evidence.
    * Scaffolds / no-op callables CANNOT auto-verift: a "completed" payload
      from a capability never upgrades ``EXECUTED`` to ``SUCCEEDED``.

``ActionResult`` serializes losslessly (``to_dict`` / ``from_dict``) so it can
be persisted in task state and handed to the LLM as a factual context block.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Optional


class ActionResultStatus(str, Enum):
    """Machine lifecycle of an action execution."""

    PENDING = "pending"
    EXECUTING = "executing"
    EXECUTED = "executed"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"

    @property
    def terminal(self) -> bool:
        return self in (ActionResultStatus.SUCCEEDED, ActionResultStatus.FAILED, ActionResultStatus.SKIPPED)


@dataclass
class ActionEvidence:
    """A single observed fact about an action's execution."""

    label: str
    success: bool
    detail: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    source: str = "runtime"
    duration_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ActionEvidence":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class ActionResult:
    """Canonical outcome of executing one action (skill request)."""

    capability: str = ""
    skill: str = ""
    action_id: str = ""
    identity_id: str = ""
    status: ActionResultStatus = ActionResultStatus.PENDING
    output: Any = None
    error: Optional[str] = None
    evidence: list[ActionEvidence] = field(default_factory=list)
    created_at: float = 0.0
    updated_at: float = 0.0
    verified: bool = False

    # ── Predicates ──────────────────────────────────────────────────────

    @property
    def succeeded(self) -> bool:
        """True ONLY when the runtime verifier marked it SUCCEEDED."""
        return self.status == ActionResultStatus.SUCCEEDED

    @property
    def verified_success(self) -> bool:
        """SUCCEEDED and explicitly verified — the only truthful 'it worked'."""
        return self.succeeded and self.verified

    @property
    def executed(self) -> bool:
        return self.status in (ActionResultStatus.EXECUTED, ActionResultStatus.SUCCEEDED)

    # ── Transitions (runtime-only) ──────────────────────────────────────

    def mark_executed(self, output: Any = None, *, error: Optional[str] = None) -> "ActionResult":
        self.status = ActionResultStatus.EXECUTED
        self.output = output
        self.error = error
        return self

    def mark_succeeded(self, verified: bool = True) -> "ActionResult":
        """Only the runtime verifier may call this — after evidence review."""
        self.status = ActionResultStatus.SUCCEEDED
        self.verified = verified
        return self

    def mark_failed(self, error: Optional[str] = None) -> "ActionResult":
        self.status = ActionResultStatus.FAILED
        self.error = error
        return self

    def mark_skipped(self, error: Optional[str] = None) -> "ActionResult":
        self.status = ActionResultStatus.SKIPPED
        self.error = error
        return self

    def add_evidence(self, evidence: ActionEvidence) -> "ActionResult":
        self.evidence.append(evidence)
        return self

    # ── Compatibility bridge with CapabilityResult ─────────────────────

    def to_capability_result(self) -> Any:
        """Adapt into the legacy CapabilityResult shape used by the router.

        NEVER upgrades status: a FAILED/EXECUTED result cannot be reported as
        success just because this bridge exists.
        """
        from core.capabilities.result import CapabilityResult
        if self.status == ActionResultStatus.SUCCEEDED:
            return CapabilityResult.ok(
                self.capability, self.skill, self.output,
                source=self.evidence[0].source if self.evidence else "runtime",
            )
        return CapabilityResult.fail(
            self.capability, self.skill,
            "failed" if self.status != ActionResultStatus.SKIPPED else "skipped",
            self.error or f"action {self.action_id or self.skill}: {self.status.value}",
        )

    @classmethod
    def from_capability_result(cls, res: Any, *, capability: str = "", skill: str = "", identity_id: str = "") -> "ActionResult":
        """Wrap a raw capability result WITHOUT trusting its success flag.

        A raw capability that claims success still starts as EXECUTED; only a
        verifier can upgrade it.  If the capability explicitly failed, we read
        that machine signal and mark FAILED.
        """
        ok = bool(getattr(res, "success", False)) and not getattr(res, "error", None)
        err = getattr(res, "error", None) or getattr(res, "exc", None)
        ar = cls(
            capability=capability or str(getattr(res, "capability", "") or ""),
            skill=skill or str(getattr(res, "action", "") or ""),
            identity_id=identity_id,
            output=getattr(res, "data", None),
            error=str(err) if err else getattr(res, "message", None),
        )
        if ok:
            ar.mark_executed(output=ar.output)
            ar.add_evidence(ActionEvidence(
                label="capture",
                success=True,
                detail=f"{ar.capability}.{ar.skill} produced output",
                data={},
                source=str(getattr(res, "source", "capability") or "capability"),
                duration_ms=float(getattr(res, "duration_ms", 0) or 0.0),
            ))
        else:
            ar.mark_failed(error=ar.error or f"{ar.capability}.{ar.skill} reported failure")
            ar.add_evidence(ActionEvidence(
                label="capture",
                success=False,
                detail=ar.error or "capability reported failure",
            ))
        ar.verified = False
        return ar

    # ── Serialization ──────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "capability": self.capability,
            "skill": self.skill,
            "action_id": self.action_id,
            "identity_id": self.identity_id,
            "status": self.status.value,
            "output": self.output,
            "error": self.error,
            "evidence": [e.to_dict() for e in self.evidence],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "verified": self.verified,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ActionResult":
        evs = [ActionEvidence.from_dict(e) for e in d.get("evidence", [])]
        ar = cls(
            capability=d.get("capability", ""),
            skill=d.get("skill", ""),
            action_id=d.get("action_id", ""),
            identity_id=d.get("identity_id", ""),
            status=ActionResultStatus(d.get("status", "pending")),
            output=d.get("output"),
            error=d.get("error"),
            evidence=evs,
            created_at=float(d.get("created_at", 0) or 0),
            updated_at=float(d.get("updated_at", 0) or 0),
            verified=bool(d.get("verified", False)),
        )
        return ar

    def to_context_block(self, limit: int = 1200) -> str:
        """Facutal, LLM-interpretable rendering of the action outcome."""
        lines = [
            f"Action: {self.capability}.{self.skill} ({self.action_id})",
            f"Status: {self.status.value}" + (" [VERIFIED]" if self.verified else ""),
        ]
        if self.error:
            lines.append(f"Error: {self.error}")
        if self.output is not None:
            try:
                out = json.dumps(self.output, default=str)[:limit]
            except Exception:
                out = str(self.output)[:limit]
            lines.append(f"Output: {out}")
        if self.evidence:
            lines.append("Evidence:")
            for e in self.evidence[:10]:
                lines.append(f"  - {e.label}: {'ok' if e.success else 'FAILED'} {e.detail}")
        return "\n".join(lines)