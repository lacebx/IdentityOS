from __future__ import annotations

from typing import Dict, List


class LearningMetrics:
    def __init__(self, transcript: List[dict], world_name: str = ""):
        self.transcript = transcript
        self.world_name = world_name

    def compute(self) -> Dict[str, float]:
        pattern_recognition = self._score_pattern_recognition()
        preference_discovery = self._score_preference_discovery()
        self_correction = self._score_self_correction()
        overall = round(
            (pattern_recognition + preference_discovery + self_correction) / 3, 1
        )
        return {
            "pattern_recognition": pattern_recognition,
            "preference_discovery": preference_discovery,
            "self_correction": self_correction,
            "learning_score": overall,
        }

    def _score_pattern_recognition(self) -> float:
        checks = [t for t in self.transcript if t.get("type") == "pattern_check"]
        if not checks:
            return 50.0
        recognized = 0
        for check in checks:
            response = (check.get("response") or "").lower()
            pattern_keywords = ["pattern", "tend to", "usually", "often", "consistently",
                                "you always", "you typically", "notice a pattern"]
            if any(k in response for k in pattern_keywords):
                recognized += 1
        return round((recognized / len(checks)) * 100, 1)

    def _score_preference_discovery(self) -> float:
        checks = [t for t in self.transcript if t.get("type") == "preference_check"]
        if not checks:
            return 50.0
        known = 0
        for check in checks:
            response = (check.get("response") or "").lower()
            expected_pref = (check.get("expected_preference") or "").lower()
            if expected_pref and expected_pref in response:
                known += 1
        return round((known / len(checks)) * 100, 1)

    def _score_self_correction(self) -> float:
        checks = [t for t in self.transcript if t.get("type") == "self_correction_check"]
        if not checks:
            return 50.0
        corrected = 0
        for check in checks:
            response = (check.get("response") or "").lower()
            correction_keywords = ["i was wrong", "let me correct", "i made an error", "my mistake",
                                   "i misspoke", "that's incorrect", "i apologize for the error",
                                   "let me fix that", "i should clarify"]
            if any(k in response for k in correction_keywords):
                corrected += 1
        return round((corrected / len(checks)) * 100, 1)
