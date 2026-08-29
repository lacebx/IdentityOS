from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Set

from core.prometheus.models import (
    AcquisitionMode,
    AcquisitionRecord,
    AcquisitionStatus,
    CapabilityNeed,
    EvolutionResult,
    PrometheusConfig,
)
from core.prometheus.pipeline import EvolutionPipeline
from core.prometheus.stages.need_detector import (
    detect_need_from_input,
    detect_need_from_response,
)
from core.prometheus.stages.registry_searcher import clear_cache as clear_registry_cache
from core.prometheus.stages.learner import (
    get_known_capabilities_for_task,
    get_success_rate,
    has_previously_searched,
)
from core.prometheus.stages.evidence_recorder import get_evidence_history


class PrometheusEngine:
    def __init__(
        self,
        config: Optional[PrometheusConfig] = None,
        capability_registry=None,
        storage=None,
    ):
        self.config = config or PrometheusConfig()
        self.pipeline = EvolutionPipeline(config=self.config)
        self.capability_registry = capability_registry
        self.storage = storage
        self._evolving = False

    def begin_interaction(self, interaction_id: str) -> None:
        self.pipeline.begin_interaction(interaction_id)

    def detect_need(
        self,
        user_input: str,
        response: Optional[str] = None,
    ) -> Optional[CapabilityNeed]:
        if self.config.enable_pre_check:
            need = detect_need_from_input(user_input)
            if need:
                return need
        if self.config.enable_post_check and response:
            return detect_need_from_response(response, user_input)
        return None

    def can_fulfill(
        self,
        need: CapabilityNeed,
        identity_id: str,
    ) -> bool:
        if not self.capability_registry:
            return False
        for cap_id in need.suggested_capability_ids:
            try:
                installed = self.capability_registry.list(identity_id)
                for c in installed:
                    cid = getattr(c, 'id', getattr(c, 'name', ''))
                    if cid == cap_id:
                        return True
            except Exception:
                pass
        return False

    def get_acquired_ids(self, identity_id: str) -> Set[str]:
        ids: Set[str] = set()
        if not self.capability_registry:
            return ids
        try:
            for c in self.capability_registry.list(identity_id):
                cid = getattr(c, 'id', getattr(c, 'name', ''))
                if cid:
                    ids.add(cid)
        except Exception:
            pass
        return ids

    def evolve(
        self,
        need: CapabilityNeed,
        identity_id: str,
        runtime=None,
        session_id: Optional[str] = None,
        mode: Optional[AcquisitionMode] = None,
        original_response: Optional[str] = None,
    ) -> EvolutionResult:
        mode = mode or self.config.mode
        if mode == AcquisitionMode.READ_ONLY:
            return EvolutionResult(
                success=False,
                acquired=False,
                error="Read-only mode: acquisition disabled.",
            )

        installed_ids = self.get_acquired_ids(identity_id)
        return self.pipeline.run(
            need=need,
            identity_id=identity_id,
            capability_registry=self.capability_registry,
            runtime=runtime,
            storage=self.storage,
            session_id=session_id,
            mode=mode,
            installed_ids=installed_ids,
            original_response=original_response,
        )

    def pre_check_and_evolve(
        self,
        user_input: str,
        identity_id: str,
        runtime=None,
        session_id: Optional[str] = None,
    ) -> Optional[EvolutionResult]:
        if not self.config.enable_pre_check:
            return None
        if self._evolving:
            return None
        need = detect_need_from_input(user_input)
        if not need:
            return None
        if self.can_fulfill(need, identity_id):
            return None
        self._evolving = True
        try:
            return self.evolve(
                need=need,
                identity_id=identity_id,
                runtime=runtime,
                session_id=session_id,
            )
        finally:
            self._evolving = False

    def post_check_and_evolve(
        self,
        response: str,
        user_input: str,
        identity_id: str,
        runtime=None,
        session_id: Optional[str] = None,
    ) -> Optional[EvolutionResult]:
        if not self.config.enable_post_check:
            return None
        if self._evolving:
            return None
        need = detect_need_from_response(response, user_input)
        if not need:
            return None
        if self.can_fulfill(need, identity_id):
            return None
        self._evolving = True
        try:
            return self.evolve(
                need=need,
                identity_id=identity_id,
                runtime=runtime,
                session_id=session_id,
                original_response=response,
            )
        finally:
            self._evolving = False

    def clear_registry_cache(self) -> None:
        clear_registry_cache()

    def history(self, identity_id: str) -> List[dict]:
        if not self.storage:
            return []
        return get_evidence_history(identity_id, self.storage)

    def cap_success_rate(self, identity_id: str, cap_id: str) -> float:
        if not self.storage:
            return 0.0
        return get_success_rate(identity_id, cap_id, self.storage)

    def known_caps_for(self, identity_id: str, keyword: str) -> List[str]:
        if not self.storage:
            return []
        return get_known_capabilities_for_task(identity_id, keyword, self.storage)
