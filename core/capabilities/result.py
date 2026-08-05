from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class EvidenceOrigin(Enum):
    USER_INPUT = "user_input"
    MEMORY = "memory"
    CAPABILITY = "capability"
    OBSERVATION = "observation"
    INFERENCE = "inference"
    SYSTEM = "system"
    SELF = "self"


@dataclass
class CapabilityResult:
    capability: str
    action: str
    success: bool
    confidence: float = 0.0
    source: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    data: Any = None
    error: Optional[dict] = None
    citations: list[str] = field(default_factory=list)
    duration_ms: float = 0.0
    metadata: dict = field(default_factory=dict)
    # call_ok is ``success``; goal_ok is whether postconditions of the *intent* passed.
    # None means "not applicable / not checked".
    goal_ok: Optional[bool] = None

    @staticmethod
    def ok(capability: str, action: str, data: Any, *,
           source: str = "", confidence: float = 1.0,
           citations: list[str] | None = None,
           duration_ms: float = 0.0,
           goal_ok: Optional[bool] = None) -> CapabilityResult:
        # If caller provided structured data with goal_ok / error, honor it.
        resolved_goal = goal_ok
        conf = confidence
        err = None
        if isinstance(data, dict):
            if "goal_ok" in data and resolved_goal is None:
                resolved_goal = bool(data.get("goal_ok"))
            if data.get("error") and resolved_goal is None:
                resolved_goal = False
            if data.get("valid") is False and resolved_goal is None:
                resolved_goal = False
            if resolved_goal is False and data.get("error"):
                err = {"type": "goal_failed", "message": str(data.get("error"))}
        if resolved_goal is False:
            conf = min(conf, 0.2)
        if resolved_goal is None:
            resolved_goal = True
        return CapabilityResult(
            capability=capability,
            action=action,
            success=resolved_goal,  # honesty: failed postconditions are not successes
            confidence=conf if resolved_goal else 0.0,
            source=source,
            data=data,
            citations=citations or [],
            duration_ms=duration_ms,
            goal_ok=resolved_goal,
            error=err,
        )

    @staticmethod
    def fail(capability: str, action: str, error_type: str, message: str, *,
             source: str = "", duration_ms: float = 0.0) -> CapabilityResult:
        return CapabilityResult(
            capability=capability,
            action=action,
            success=False,
            confidence=0.0,
            source=source,
            data=None,
            error={"type": error_type, "message": message},
            duration_ms=duration_ms,
            goal_ok=False,
        )

    def to_evidence_dict(self) -> dict:
        return {
            "capability": self.capability,
            "action": self.action,
            "success": self.success,
            "goal_ok": self.goal_ok,
            "confidence": self.confidence,
            "source": self.source,
            "timestamp": self.timestamp,
            "duration_ms": self.duration_ms,
            "error": self.error,
        }


@dataclass
class Fact:
    content: str
    origin: EvidenceOrigin
    confidence: float
    source: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    citations: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    @staticmethod
    def from_result(result: CapabilityResult) -> list[Fact]:
        if not result.success:
            return []
        text = str(result.data) if not isinstance(result.data, dict) else _summarize(result.data)
        if len(text) > 3000:
            text = text[:3000] + "\n... [truncated]"
        return [
            Fact(
                content=text,
                origin=EvidenceOrigin.CAPABILITY,
                confidence=result.confidence,
                source=result.source,
                timestamp=result.timestamp,
                citations=result.citations,
                metadata={"capability": result.capability, "action": result.action},
            )
        ]


def _summarize(data: dict, max_len: int = 2000) -> str:
    import json
    text = json.dumps(data, indent=2, default=str)
    if len(text) > max_len:
        text = text[:max_len] + "\n... [truncated]"
    return text
