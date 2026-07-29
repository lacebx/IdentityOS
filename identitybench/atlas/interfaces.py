from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class PredictionModel(ABC):
    @abstractmethod
    def predict(
        self,
        category: str,
        historical_values: List[float],
        steps_ahead: int = 5,
    ) -> Dict[str, Any]:
        ...

    def supports_bayesian(self) -> bool:
        return False

    def supports_ml(self) -> bool:
        return False


class ConfidenceEstimator(ABC):
    @abstractmethod
    def estimate(
        self,
        data_quality: Dict[str, Any],
        historical_accuracy: Optional[float] = None,
    ) -> float:
        ...

    def supports_bayesian(self) -> bool:
        return False


class StrategyOptimizer(ABC):
    @abstractmethod
    def optimize(
        self,
        strategies: List[Dict[str, Any]],
        constraints: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        ...

    def supports_reinforcement_learning(self) -> bool:
        return False


class HealthAugmenter(ABC):
    @abstractmethod
    def augment(
        self,
        health_result: Dict[str, Any],
        extra_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        ...

    def supports_organization_dashboards(self) -> bool:
        return False

    def supports_multi_identity(self) -> bool:
        return False
