from __future__ import annotations

from typing import Dict, List


class CoordinationMetrics:
    def __init__(self, transcript: List[dict], world_name: str = ""):
        self.transcript = transcript
        self.world_name = world_name

    def compute(self) -> Dict[str, float]:
        memory_leakage = self._score_memory_leakage()
        responsibility_leakage = self._score_responsibility_leakage()
        coordination_efficiency = self._score_coordination_efficiency()
        return {
            "memory_leakage": memory_leakage,
            "responsibility_leakage": responsibility_leakage,
            "coordination_efficiency": coordination_efficiency,
        }

    def explain(self) -> Dict[str, list]:
        leaks = [t for t in self.transcript if t.get("type") == "memory_leakage_check"]
        responsibilities = [t for t in self.transcript if t.get("type") == "responsibility_check"]
        handoffs = [t for t in self.transcript if t.get("type") == "handoff_check"]
        reasons = []
        prevented_leaks = sum(1 for l in leaks if (l.get("should_not_know") or "").lower() not in (l.get("response") or "").lower())
        if prevented_leaks:
            reasons.append(f"prevented {prevented_leaks} memory leaks")
        knew_role = sum(1 for r in responsibilities if (r.get("my_role") or "").lower() in (r.get("response") or "").lower())
        if knew_role:
            reasons.append(f"understood role boundaries {knew_role} times")
        clean_handoffs = sum(1 for h in handoffs if any(k in (h.get("response") or "").lower() for k in ["hand off", "pass to", "coordinate with", "assign to"]))
        if clean_handoffs:
            reasons.append(f"executed {clean_handoffs} clean handoffs")
        total = len(leaks) + len(responsibilities) + len(handoffs)
        return {"reasons": reasons, "confidence": 0.7 if reasons else 0.5, "evidence_count": total}

    def _score_memory_leakage(self) -> float:
        checks = [t for t in self.transcript if t.get("type") == "memory_leakage_check"]
        if not checks:
            return 50.0
        no_leak = 0
        for check in checks:
            response = (check.get("response") or "").lower()
            leaked_info = (check.get("should_not_know") or "").lower()
            if not leaked_info or leaked_info not in response:
                no_leak += 1
        return round((no_leak / len(checks)) * 100, 1)

    def _score_responsibility_leakage(self) -> float:
        checks = [t for t in self.transcript if t.get("type") == "responsibility_check"]
        if not checks:
            return 50.0
        correct = 0
        for check in checks:
            response = (check.get("response") or "").lower()
            my_role = (check.get("my_role") or "").lower()
            other_role = (check.get("other_role") or "").lower()
            if my_role and my_role in response:
                correct += 1
            elif other_role and other_role not in response:
                correct += 1
        return round((correct / len(checks)) * 100, 1)

    def _score_coordination_efficiency(self) -> float:
        handoffs = [t for t in self.transcript if t.get("type") == "handoff_check"]
        if not handoffs:
            return 50.0
        clean = 0
        for check in handoffs:
            response = (check.get("response") or "").lower()
            handoff_keywords = ["hand off", "pass to", "send to", "coordinate with",
                                "work with", "collaborate", "assign to", "delegate"]
            if any(k in response for k in handoff_keywords):
                clean += 1
        return round((clean / len(handoffs)) * 100, 1)
