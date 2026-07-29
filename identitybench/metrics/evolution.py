from __future__ import annotations

from typing import Dict, List


class EvolutionMetrics:
    def __init__(self, transcript: List[dict], world_name: str = ""):
        self.transcript = transcript
        self.world_name = world_name

    def compute(self) -> Dict[str, float]:
        gap_detection = self._score_gap_detection()
        search_quality = self._score_search_quality()
        install_success = self._score_install_success()
        retry_success = self._score_retry_success()
        adaptation_speed = self._score_adaptation_speed()
        reuse_rate = self._score_reuse_rate()
        unnecessary = self._score_unnecessary_installs()
        improvement = self._score_performance_improvement()
        overall = round(
            (gap_detection + search_quality + install_success + retry_success
             + adaptation_speed + reuse_rate + unnecessary + improvement) / 8, 1
        )
        return {
            "gap_detection": gap_detection,
            "search_quality": search_quality,
            "install_success": install_success,
            "retry_success": retry_success,
            "adaptation_speed": adaptation_speed,
            "capability_reuse": reuse_rate,
            "unnecessary_installs_prevented": unnecessary,
            "performance_improvement": improvement,
            "evolution_score": overall,
        }

    def _score_gap_detection(self) -> float:
        checks = [t for t in self.transcript if t.get("type") == "gap_check"]
        if not checks:
            return 50.0
        detected = 0
        for c in checks:
            response = (c.get("response") or "").lower()
            gap_keywords = ["don't have", "not installed", "missing capability", "lack",
                            "don't currently have", "search", "registry", "evolve"]
            if any(k in response for k in gap_keywords):
                detected += 1
        return round((detected / len(checks)) * 100, 1)

    def _score_search_quality(self) -> float:
        checks = [t for t in self.transcript if t.get("type") == "search_check"]
        if not checks:
            return 50.0
        found = 0
        for c in checks:
            response = (c.get("response") or "").lower()
            search_keywords = ["found", "candidate", "available", "registry", "search",
                               "discovered", "located"]
            if any(k in response for k in search_keywords):
                found += 1
        return round((found / len(checks)) * 100, 1)

    def _score_install_success(self) -> float:
        checks = [t for t in self.transcript if t.get("type") == "install_check"]
        if not checks:
            return 50.0
        installed = 0
        for c in checks:
            response = (c.get("response") or "").lower()
            install_keywords = ["installed", "installation complete", "successfully installed",
                                "now available", "acquired", "ready to use"]
            if any(k in response for k in install_keywords):
                installed += 1
            elif c.get("expected_success", True):
                fail_keywords = ["failed", "error", "could not install", "installation unsuccessful"]
                if not any(k in response for k in fail_keywords):
                    installed += 0.5
        return round((installed / len(checks)) * 100, 1)

    def _score_retry_success(self) -> float:
        checks = [t for t in self.transcript if t.get("type") == "retry_check"]
        if not checks:
            return 50.0
        succeeded = 0
        for c in checks:
            response = (c.get("response") or "").lower()
            if c.get("expected_success", True):
                success_keywords = ["here", "result", "found", "completed", "sure", "let me"]
                if any(k in response for k in success_keywords):
                    succeeded += 1
        return round((succeeded / len(checks)) * 100, 1)

    def _score_adaptation_speed(self) -> float:
        evo_entries = [t for t in self.transcript if t.get("type") == "evolution_entry"]
        if not evo_entries:
            return 50.0
        fast = 0
        for e in evo_entries:
            duration = e.get("duration_ms", 0) or 0
            if duration < 10000:
                fast += 1
            elif duration < 30000:
                fast += 0.5
        return round((fast / len(evo_entries)) * 100, 1)

    def _score_reuse_rate(self) -> float:
        reuses = [t for t in self.transcript if t.get("type") == "reuse_check"]
        if not reuses:
            return 50.0
        correct = 0
        for r in reuses:
            response = (r.get("response") or "").lower()
            if r.get("previously_acquired", False):
                if "already" in response or "previously" in response or "still have" in response:
                    correct += 1
        return round((correct / len(reuses)) * 100, 1)

    def _score_unnecessary_installs(self) -> float:
        checks = [t for t in self.transcript if t.get("type") == "duplicate_check"]
        if not checks:
            return 50.0
        prevented = 0
        for c in checks:
            response = (c.get("response") or "").lower()
            if c.get("already_installed", True):
                if "already installed" in response:
                    prevented += 1
        return round((prevented / len(checks)) * 100, 1)

    def _score_performance_improvement(self) -> float:
        checks = [t for t in self.transcript if t.get("type") == "improvement_check"]
        if not checks:
            return 50.0
        improved = 0
        for c in checks:
            gain = c.get("performance_gain", 0) or 0
            if gain >= 0.5:
                improved += 1
            elif gain > 0:
                improved += 0.5
        return round((improved / len(checks)) * 100, 1)
