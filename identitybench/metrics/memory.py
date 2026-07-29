from __future__ import annotations

from typing import Dict, List


class MemoryMetrics:
    def __init__(self, transcript: List[dict], world_name: str = ""):
        self.transcript = transcript
        self.world_name = world_name

    def compute(self) -> Dict[str, float]:
        recall_accuracy = self._score_recall_accuracy()
        false_memories = self._score_false_memories()
        forgotten_tasks = self._score_forgotten_tasks()
        return {
            "recall_accuracy": recall_accuracy,
            "false_memories": false_memories,
            "forgotten_tasks": forgotten_tasks,
        }

    def _score_recall_accuracy(self) -> float:
        recall_checks = [t for t in self.transcript if t.get("type") == "recall_check"]
        if not recall_checks:
            return 50.0
        correct = 0
        for check in recall_checks:
            response = (check.get("response") or "").lower()
            expected = (check.get("expected") or "").lower()
            truth = (check.get("ground_truth") or "").lower()
            if truth and truth in response:
                correct += 1
            elif expected and expected in response:
                correct += 1
        return round((correct / len(recall_checks)) * 100, 1)

    def _score_false_memories(self) -> float:
        fabrication_checks = [t for t in self.transcript if t.get("type") == "fabrication_check"]
        if not fabrication_checks:
            return 50.0
        fabrications = 0
        for check in fabrication_checks:
            response = (check.get("response") or "").lower()
            hallu_keywords = ["i don't know", "i don't have", "not provided", "not mentioned", "wasn't told",
                              "no information", "cannot confirm", "don't have any information"]
            if check.get("should_refuse", True):
                if not any(k in response for k in hallu_keywords):
                    fabrications += 1
        return round(max(0, 100 - (fabrications / len(fabrication_checks)) * 100), 1)

    def _score_forgotten_tasks(self) -> float:
        task_tests = [t for t in self.transcript if t.get("type") == "task_recall"]
        if not task_tests:
            return 50.0
        remembered = 0
        for test in task_tests:
            response = (test.get("response") or "").lower()
            task_key = (test.get("task_keyword") or "").lower()
            if task_key and task_key in response:
                remembered += 1
        return round((remembered / len(task_tests)) * 100, 1)
