"""Tests for core.health module."""

from core.health import (
    IdentityHealth,
    HealthMetrics,
    HealthStatus,
)


class TestHealthMetrics:
    def test_defaults(self):
        m = HealthMetrics()
        assert m.memory_saturation == 0.0
        assert m.knowledge_freshness == 1.0
        assert m.relationship_drift == 0.0
        assert m.goal_completion == 0.0
        assert m.identity_stability == 1.0
        assert m.policy_violations == 0
        assert m.last_evaluated > 0

    def test_to_dict(self):
        m = HealthMetrics(
            memory_saturation=0.5,
            knowledge_freshness=0.8,
            relationship_drift=0.2,
            goal_completion=0.7,
            identity_stability=0.9,
            policy_violations=1,
        )
        data = m.to_dict()
        assert data["memory_saturation"] == 0.5
        assert data["knowledge_freshness"] == 0.8
        assert data["relationship_drift"] == 0.2
        assert data["goal_completion"] == 0.7
        assert data["identity_stability"] == 0.9
        assert data["policy_violations"] == 1

    def test_from_dict(self):
        data = {
            "memory_saturation": 0.5,
            "knowledge_freshness": 0.8,
            "relationship_drift": 0.2,
            "goal_completion": 0.7,
            "identity_stability": 0.9,
            "policy_violations": 1,
            "last_evaluated": 1234567890.0,
        }
        m = HealthMetrics.from_dict(data)
        assert m.memory_saturation == 0.5
        assert m.knowledge_freshness == 0.8
        assert m.relationship_drift == 0.2
        assert m.goal_completion == 0.7
        assert m.identity_stability == 0.9
        assert m.policy_violations == 1
        assert m.last_evaluated == 1234567890.0


class TestIdentityHealth:
    def test_healthy_status(self):
        health = IdentityHealth()
        status = health.status()
        assert status["overall"] == HealthStatus.HEALTHY.value
        assert len(status["alerts"]) == 0
        assert len(status["warnings"]) == 0

    def test_memory_saturation_warning(self):
        health = IdentityHealth()
        health.update_metric("memory_saturation", 0.85)
        status = health.status()
        assert status["overall"] == HealthStatus.WARNING.value
        assert any("Memory saturation" in w for w in status["warnings"])

    def test_memory_saturation_critical(self):
        health = IdentityHealth()
        health.update_metric("memory_saturation", 0.98)
        status = health.status()
        assert status["overall"] == HealthStatus.CRITICAL.value
        assert any("CRITICAL" in a for a in status["alerts"])

    def test_knowledge_freshness_warning(self):
        health = IdentityHealth()
        health.update_metric("knowledge_freshness", 0.3)
        status = health.status()
        assert status["overall"] == HealthStatus.WARNING.value
        assert any("Knowledge freshness" in w for w in status["warnings"])

    def test_relationship_drift_warning(self):
        health = IdentityHealth()
        health.update_metric("relationship_drift", 0.5)
        status = health.status()
        assert status["overall"] == HealthStatus.WARNING.value
        assert any("High relationship drift" in w for w in status["warnings"])

    def test_identity_stability_warning(self):
        health = IdentityHealth()
        health.update_metric("identity_stability", 0.5)
        status = health.status()
        assert status["overall"] == HealthStatus.WARNING.value
        assert any("Identity stability" in w for w in status["warnings"])

    def test_policy_violations_critical(self):
        health = IdentityHealth()
        health.update_metric("policy_violations", 3)
        status = health.status()
        assert status["overall"] == HealthStatus.CRITICAL.value
        assert any("policy violation" in a for a in status["alerts"])

    def test_update_metric(self):
        health = IdentityHealth()
        health.update_metric("memory_saturation", 0.5)
        assert health.get_metric("memory_saturation") == 0.5

    def test_update_all(self):
        health = IdentityHealth()
        health.update_all(memory_saturation=0.5, knowledge_freshness=0.8)
        assert health.get_metric("memory_saturation") == 0.5
        assert health.get_metric("knowledge_freshness") == 0.8

    def test_report(self):
        health = IdentityHealth()
        report = health.report()
        assert "Identity Health Report" in report
        assert "HEALTHY" in report
        assert "All systems operational" in report

    def test_report_with_alerts(self):
        health = IdentityHealth()
        health.update_metric("policy_violations", 1)
        report = health.report()
        assert "CRITICAL" in report
        assert "ALERTS" in report

    def test_to_dict(self):
        health = IdentityHealth()
        health.update_metric("memory_saturation", 0.5)
        data = health.to_dict()
        assert data["memory_saturation"] == 0.5

    def test_from_dict(self):
        data = {
            "memory_saturation": 0.5,
            "knowledge_freshness": 0.8,
            "relationship_drift": 0.2,
            "goal_completion": 0.7,
            "identity_stability": 0.9,
            "policy_violations": 1,
            "last_evaluated": 1234567890.0,
        }
        health = IdentityHealth.from_dict(data)
        assert health.get_metric("memory_saturation") == 0.5