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

    @staticmethod
    def ok(capability: str, action: str, data: Any, *,
           source: str = "", confidence: float = 1.0,
           citations: list[str] | None = None,
           duration_ms: float = 0.0) -> CapabilityResult:
        return CapabilityResult(
            capability=capability,
            action=action,
            success=True,
            confidence=confidence,
            source=source,
            data=data,
            citations=citations or [],
            duration_ms=duration_ms,
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
        )


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
