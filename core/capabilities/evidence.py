from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .result import CapabilityResult, EvidenceOrigin, Fact


@dataclass
class EvidenceReport:
    identity_id: str
    facts: list[Fact] = field(default_factory=list)
    failures: list[CapabilityResult] = field(default_factory=list)
    total_ok: int = 0
    total_fail: int = 0
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def trust_metrics(self) -> dict[str, Any]:
        total = self.total_ok + self.total_fail
        return {
            "total_capability_calls": total,
            "successful": self.total_ok,
            "failed": self.total_fail,
            "success_rate": round(self.total_ok / total, 3) if total else 1.0,
            "verified_facts": sum(1 for f in self.facts if f.confidence >= 0.8),
            "low_confidence_facts": sum(1 for f in self.facts if f.confidence < 0.8),
            "failures_by_capability": self._failures_by_cap(),
        }

    def _failures_by_cap(self) -> dict[str, list[dict]]:
        by_cap: dict[str, list[dict]] = {}
        for f in self.failures:
            by_cap.setdefault(f.capability, []).append({
                "action": f.action,
                "error": f.error,
                "timestamp": f.timestamp,
            })
        return by_cap


class EvidenceManager:
    """Collects, validates, and exposes capability outputs as structured evidence.

    The LLM never sees raw capability results. It only sees Facts with
    provenance, confidence, and clear success/failure status.
    """

    def __init__(self, identity_id: str) -> None:
        self._identity_id = identity_id
        self._results: list[CapabilityResult] = []

    def collect(self, result: CapabilityResult) -> None:
        self._results.append(result)

    def collect_many(self, results: list[CapabilityResult]) -> None:
        self._results.extend(results)

    def report(self) -> EvidenceReport:
        facts: list[Fact] = []
        failures: list[CapabilityResult] = []
        ok_count = 0
        fail_count = 0

        for r in self._results:
            if r.success:
                facts.extend(Fact.from_result(r))
                ok_count += 1
            else:
                failures.append(r)
                fail_count += 1

        return EvidenceReport(
            identity_id=self._identity_id,
            facts=facts,
            failures=failures,
            total_ok=ok_count,
            total_fail=fail_count,
        )

    @property
    def call_history(self) -> list[dict]:
        """Serializable call records for persistence in trust dashboard."""
        records = []
        for r in self._results:
            records.append({
                "skill": f"{r.capability}.{r.action}",
                "success": r.success,
                "confidence": r.confidence,
                "source": r.source,
                "error": r.error.get("message", "") if r.error else None,
            })
        return records

    def build_context_block(self, report: EvidenceReport | None = None) -> str:
        """Build the factual context block from evidence, for LLM consumption."""
        rep = report or self.report()
        lines: list[str] = []

        if rep.facts:
            lines.append("## Live Capability Results (verified factual data)")
            for f in rep.facts[:6]:
                label = f"[{f.origin.value}]" if f.confidence < 1.0 else ""
                content = f.content[:2000] if isinstance(f.content, str) else str(f.content)[:2000]
                lines.append(f"  - {content} {label}".strip())
            lines.append("")

        if rep.failures:
            lines.append("## Capability Failures — you MUST acknowledge these")
            for fail in rep.failures[:8]:
                msg = (fail.error['message'] if fail.error else 'unknown error')[:300]
                lines.append(
                    f"  - {fail.capability}.{fail.action} failed: {msg}. "
                    f"Source: {fail.source}"
                )
            lines.append("  Do NOT fabricate data for failed capabilities.")
            lines.append("  Do NOT estimate values the capability was supposed to provide.")
            lines.append("  Explain the failure and offer alternatives.")
            lines.append("")

        if not rep.facts and not rep.failures:
            lines.append("## Capabilities")
            lines.append("No capabilities were invoked for this interaction.\n")

        return "\n".join(lines)

    def trust_block(self, rep: EvidenceReport | None = None) -> str:
        """Build a trust-metrics block shown to the user in verbose mode."""
        rep = rep or self.report()
        metrics = rep.trust_metrics()
        lines = [
            "## Evidence Sources",
        ]
        by_cap: dict[str, int] = {}
        for r in self._results:
            by_cap.setdefault(r.capability, 0)
            by_cap[r.capability] += 1
        for cap, count in sorted(by_cap.items()):
            lines.append(f"  - {cap}: {count} call(s)")

        lines.append("")
        lines.append("## Trust Metrics")
        lines.append(f"  - Verified facts (confidence >= 0.8): {metrics['verified_facts']}")
        lines.append(f"  - Low-confidence facts: {metrics['low_confidence_facts']}")
        lines.append(f"  - Capability failures: {metrics['failed']}")
        lines.append(f"  - Success rate: {metrics['success_rate'] * 100:.1f}%")

        if rep.failures:
            lines.append("")
            lines.append("## Recent Capability Errors")
            for fail in rep.failures:
                err = fail.error or {}
                lines.append(f"  - {fail.capability}.{fail.action}: {err.get('type', 'error')} — {err.get('message', '')}")

        return "\n".join(lines)
