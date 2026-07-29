from __future__ import annotations

from typing import Dict, List


class PlanningMetrics:
    def __init__(self, transcript: List[dict], world_name: str = ""):
        self.transcript = transcript
        self.world_name = world_name

    def compute(self) -> Dict[str, float]:
        completion_rate = self._score_completion_rate()
        deadline_accuracy = self._score_deadline_accuracy()
        reprioritization_quality = self._score_reprioritization()
        return {
            "completion_rate": completion_rate,
            "deadline_accuracy": deadline_accuracy,
            "reprioritization_quality": reprioritization_quality,
        }

    def explain(self) -> Dict[str, list]:
        completions = [t for t in self.transcript if t.get("type") == "completion_check"]
        deadlines = [t for t in self.transcript if t.get("type") == "deadline_check"]
        repriors = [t for t in self.transcript if t.get("type") == "reprioritization_check"]
        reasons = []
        done = sum(1 for c in completions if any(k in (c.get("response") or "").lower() for k in ["completed", "done", "finished"]))
        if done:
            reasons.append(f"completed {done} scheduled tasks")
        deadline_ok = sum(1 for d in deadlines if "on track" in (d.get("response") or "").lower() or "by the deadline" in (d.get("response") or "").lower())
        if deadline_ok:
            reasons.append(f"met {deadline_ok} deadlines")
        missed_deadlines = sum(1 for d in deadlines if "missed" in (d.get("response") or "").lower() or "too late" in (d.get("response") or "").lower())
        if missed_deadlines:
            reasons.append(f"missed {missed_deadlines} deadlines")
        adapted = sum(1 for r in repriors if any(k in (r.get("response") or "").lower() for k in ["shift", "reprioritize", "adjust", "focus"]))
        if adapted:
            reasons.append(f"reprioritized {adapted} tasks")
        conf = round(len([r for r in [done, deadline_ok, adapted] if r > 0]) / 3, 2) if any([done, deadline_ok, adapted]) else 0.5
        return {"reasons": reasons, "confidence": conf, "evidence_count": len(completions) + len(deadlines) + len(repriors)}

    def _score_completion_rate(self) -> float:
        assignments = [t for t in self.transcript if t.get("type") == "task_assignment"]
        completions = [t for t in self.transcript if t.get("type") == "completion_check"]
        if not assignments:
            return 50.0
        completed = 0
        for check in completions:
            response = (check.get("response") or "").lower()
            done_keywords = ["completed", "done", "finished", "accomplished", "implemented"]
            if any(k in response for k in done_keywords):
                completed += 1
        total = max(len(assignments), len(completions))
        return round((completed / total) * 100, 1)

    def _score_deadline_accuracy(self) -> float:
        deadline_checks = [t for t in self.transcript if t.get("type") == "deadline_check"]
        if not deadline_checks:
            return 50.0
        met = 0
        for check in deadline_checks:
            response = (check.get("response") or "").lower()
            if "on track" in response or "by the deadline" in response or "will be done" in response:
                met += 1
            elif "missed" not in response and "too late" not in response and "unlikely" not in response:
                met += 0.5
        return round((met / len(deadline_checks)) * 100, 1)

    def _score_reprioritization(self) -> float:
        rePrior_tests = [t for t in self.transcript if t.get("type") == "reprioritization_check"]
        if not rePrior_tests:
            return 50.0
        adapted = 0
        for test in rePrior_tests:
            response = (test.get("response") or "").lower()
            adapt_keywords = ["shift", "reprioritize", "adjust", "reorder", "focus", "change priority",
                              "put on hold", "deprioritize", "urgency", "more important"]
            if any(k in response for k in adapt_keywords):
                adapted += 1
        return round((adapted / len(rePrior_tests)) * 100, 1)
