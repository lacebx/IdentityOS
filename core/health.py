"""
health.py - Identity Health Monitoring

Tracks observable metrics for identity stability, resource usage, and operational
health. Unlike Evaluation (which measures performance), Health measures the
identity's internal state and well-being.

Metrics:
  - memory_saturation    : [0-1] how full the experience store is
  - knowledge_freshness  : [0-1] recency of knowledge packs
  - relationship_drift   : [0-1] stability of relationship graph
  - goal_completion      : [0-1] progress toward active motivations
  - identity_stability   : [0-1] consistency of behavior over time
  - policy_violations    : count of policy breaches

Usage:
    health = IdentityHealth()
    health.update_metric("memory_saturation", 0.92)
    health.update_metric("policy_violations", 0)

    status = health.status()
    # {"overall": "warning", "alerts": ["High memory saturation"]}
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class HealthStatus(Enum):
    """Overall health status."""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass
class HealthMetrics:
    """
    Normalized health metrics for an identity.

    All float metrics are normalized to [0, 1]:
      - 0.0 = worst
      - 1.0 = best

    Attributes:
        memory_saturation    : How full the experience store is (1.0 = full)
        knowledge_freshness  : Recency of knowledge packs (1.0 = very fresh)
        relationship_drift   : Graph stability (0.0 = stable, 1.0 = high churn)
        goal_completion      : Progress on active motivations (1.0 = all complete)
        identity_stability   : Behavioral consistency (1.0 = very stable)
        policy_violations    : Count of policy breaches (lower is better)
        last_evaluated       : Unix timestamp of last health check
    """
    memory_saturation: float = 0.0
    knowledge_freshness: float = 1.0
    relationship_drift: float = 0.0
    goal_completion: float = 0.0
    identity_stability: float = 1.0
    policy_violations: int = 0
    last_evaluated: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "memory_saturation": self.memory_saturation,
            "knowledge_freshness": self.knowledge_freshness,
            "relationship_drift": self.relationship_drift,
            "goal_completion": self.goal_completion,
            "identity_stability": self.identity_stability,
            "policy_violations": self.policy_violations,
            "last_evaluated": self.last_evaluated,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HealthMetrics":
        return cls(
            memory_saturation=data.get("memory_saturation", 0.0),
            knowledge_freshness=data.get("knowledge_freshness", 1.0),
            relationship_drift=data.get("relationship_drift", 0.0),
            goal_completion=data.get("goal_completion", 0.0),
            identity_stability=data.get("identity_stability", 1.0),
            policy_violations=data.get("policy_violations", 0),
            last_evaluated=data.get("last_evaluated", time.time()),
        )


class IdentityHealth:
    """
    Monitors and reports on identity health.

    Thresholds:
      - WARNING: any metric outside healthy range
      - CRITICAL: multiple metrics in danger zone or policy violations > 0
    """

    # Health thresholds
    MEMORY_SATURATION_WARNING = 0.8
    MEMORY_SATURATION_CRITICAL = 0.95
    KNOWLEDGE_FRESHNESS_WARNING = 0.5
    RELATIONSHIP_DRIFT_WARNING = 0.3
    IDENTITY_STABILITY_WARNING = 0.7

    def __init__(self, metrics: Optional[HealthMetrics] = None) -> None:
        self._metrics = metrics or HealthMetrics()

    def update_metric(self, name: str, value: Any) -> None:
        """Update a single health metric."""
        if hasattr(self._metrics, name):
            setattr(self._metrics, name, value)
            self._metrics.last_evaluated = time.time()

    def update_all(self, **kwargs: Any) -> None:
        """Batch update multiple metrics."""
        for name, value in kwargs.items():
            self.update_metric(name, value)

    def get_metric(self, name: str) -> Any:
        """Get the current value of a metric."""
        return getattr(self._metrics, name, None)

    def status(self) -> dict[str, Any]:
        """
        Compute overall health status and generate alerts.

        Returns:
            {
                "overall": HealthStatus,
                "alerts": [str],
                "warnings": [str],
                "metrics": HealthMetrics.to_dict()
            }
        """
        alerts = []
        warnings = []

        # Memory saturation
        if self._metrics.memory_saturation >= self.MEMORY_SATURATION_CRITICAL:
            alerts.append("CRITICAL: Memory saturation at {:.0f}% - pruning required".format(
                self._metrics.memory_saturation * 100
            ))
        elif self._metrics.memory_saturation >= self.MEMORY_SATURATION_WARNING:
            warnings.append("Memory saturation at {:.0f}% - consider pruning".format(
                self._metrics.memory_saturation * 100
            ))

        # Knowledge freshness
        if self._metrics.knowledge_freshness < self.KNOWLEDGE_FRESHNESS_WARNING:
            warnings.append(
                "Knowledge freshness low ({:.0f}%) - update knowledge packs".format(
                    self._metrics.knowledge_freshness * 100
                )
            )

        # Relationship drift
        if self._metrics.relationship_drift > self.RELATIONSHIP_DRIFT_WARNING:
            warnings.append(
                "High relationship drift ({:.0f}%) - graph instability detected".format(
                    self._metrics.relationship_drift * 100
                )
            )

        # Identity stability
        if self._metrics.identity_stability < self.IDENTITY_STABILITY_WARNING:
            warnings.append(
                "Identity stability low ({:.0f}%) - behavioral inconsistency".format(
                    self._metrics.identity_stability * 100
                )
            )

        # Policy violations
        if self._metrics.policy_violations > 0:
            alerts.append(
                f"CRITICAL: {self._metrics.policy_violations} policy violation(s) detected"
            )

        # Determine overall status
        if alerts:
            overall = HealthStatus.CRITICAL
        elif warnings:
            overall = HealthStatus.WARNING
        else:
            overall = HealthStatus.HEALTHY

        return {
            "overall": overall.value,
            "alerts": alerts,
            "warnings": warnings,
            "metrics": self._metrics.to_dict(),
        }

    def report(self) -> str:
        """
        Generate a human-readable health report.
        """
        status = self.status()
        lines = [
            f"Identity Health Report - {status['overall'].upper()}",
            "=" * 50,
            "",
            "Metrics:",
            f"  Memory Saturation    : {self._metrics.memory_saturation:.1%}",
            f"  Knowledge Freshness  : {self._metrics.knowledge_freshness:.1%}",
            f"  Relationship Drift   : {self._metrics.relationship_drift:.1%}",
            f"  Goal Completion      : {self._metrics.goal_completion:.1%}",
            f"  Identity Stability   : {self._metrics.identity_stability:.1%}",
            f"  Policy Violations    : {self._metrics.policy_violations}",
            "",
        ]

        if status["alerts"]:
            lines.append("🚨 ALERTS:")
            for alert in status["alerts"]:
                lines.append(f"  - {alert}")
            lines.append("")

        if status["warnings"]:
            lines.append("⚠️  WARNINGS:")
            for warning in status["warnings"]:
                lines.append(f"  - {warning}")
            lines.append("")

        if not status["alerts"] and not status["warnings"]:
            lines.append("✅ All systems operational")
            lines.append("")

        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to OIS format."""
        return self._metrics.to_dict()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IdentityHealth":
        """Deserialize from OIS format."""
        metrics = HealthMetrics.from_dict(data)
        return cls(metrics)
