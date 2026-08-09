from __future__ import annotations

import re
import time
from typing import Any, Dict, List, Optional, Set

from core.prometheus.models import (
    AcquisitionMode,
    AcquisitionRecord,
    AcquisitionStatus,
    CapabilityNeed,
    EvolutionResult,
    PrometheusConfig,
    RegistryCandidate,
)
from core.prometheus.stages.need_detector import (
    detect_need_from_input,
    detect_need_from_response,
)
from core.prometheus.stages.registry_searcher import search_registry, clear_cache
from core.prometheus.stages.candidate_ranker import rank_candidates, pick_best
from core.prometheus.stages.trust_verifier import is_trusted, verify_trust
from core.prometheus.stages.dependency_resolver import has_missing_dependencies
from core.prometheus.stages.installer import safe_install, rollback_install
from core.prometheus.stages.validator import validate_capability
from core.prometheus.stages.retry_handler import retry_original_task
from core.prometheus.stages.performance_evaluator import evaluate_performance
from core.prometheus.stages.learner import record_acquisition, has_previously_searched
from core.prometheus.stages.evidence_recorder import record_evidence


_QUESTION_PATTERNS = [
    re.compile(r"^(did|do|does|is|are|was|were|can|could|should|would|have|has|what|who|when|where|why|how)\b", re.IGNORECASE),
]


def _is_status_question(text: str) -> bool:
    """True when *text* asks about existing state rather than new work."""
    t = (text or "").strip()
    if not t:
        return False
    if t.endswith("?"):
        return True
    return any(p.match(t) for p in _QUESTION_PATTERNS)


class EvolutionPipeline:
    def __init__(self, config: Optional[PrometheusConfig] = None):
        self.config = config or PrometheusConfig()
        self._interaction_acquisitions: int = 0

    def run(
        self,
        need: CapabilityNeed,
        identity_id: str,
        capability_registry,
        runtime,
        storage,
        session_id: Optional[str] = None,
        mode: AcquisitionMode = AcquisitionMode.AUTOMATIC,
        installed_ids: Optional[Set[str]] = None,
        original_response: Optional[str] = None,
    ) -> EvolutionResult:
        start_time = time.time()
        record = AcquisitionRecord(
            need=need,
            identity_id=identity_id,
            mode=mode,
        )

        installed_ids = installed_ids or set()
        if need.capability_id and need.capability_id in installed_ids:
            record.status = AcquisitionStatus.FAILED
            record.error = f"Capability '{need.capability_id}' is already installed."
            return EvolutionResult(
                success=False,
                acquisition_record=record,
                duration_ms=(time.time() - start_time) * 1000,
            )

        # Executive delegation — when a persistent task engine is attached,
        # Prometheus creates the acquisition task and the executive executes
        # it (registry search, generate, validate, publish, install, verify).
        delegated = self._delegate_to_executive(
            need, identity_id, runtime, storage, session_id,
        )
        if delegated is not None:
            return delegated

        if self._interaction_acquisitions >= self.config.max_acquisitions_per_interaction:
            record.status = AcquisitionStatus.FAILED
            record.error = (
                f"Acquisition limit reached "
                f"({self.config.max_acquisitions_per_interaction} per interaction)."
            )
            return EvolutionResult(
                success=False,
                acquisition_record=record,
                duration_ms=(time.time() - start_time) * 1000,
            )

        record.status = AcquisitionStatus.SEARCHING
        candidates = search_registry(
            need=need,
            max_candidates=self.config.max_candidates,
            installed_ids=installed_ids,
        )
        if not candidates:
            record.status = AcquisitionStatus.FAILED
            record.error = "No candidates found in registry."
            return EvolutionResult(
                success=False,
                acquisition_record=record,
                duration_ms=(time.time() - start_time) * 1000,
            )

        record.candidates_found = candidates
        record.status = AcquisitionStatus.CANDIDATES_FOUND

        ranked = rank_candidates(candidates, need)
        best = pick_best(ranked)
        if not best:
            record.status = AcquisitionStatus.FAILED
            record.error = "No suitable candidate after ranking."
            return EvolutionResult(
                success=False,
                acquisition_record=record,
                duration_ms=(time.time() - start_time) * 1000,
            )

        record.chosen_candidate = best
        record.trust_score = verify_trust(
            best, mode=mode, min_score=self.config.min_trust_score
        )

        if not is_trusted(best, mode=mode, min_score=self.config.min_trust_score):
            record.status = AcquisitionStatus.FAILED
            record.error = (
                f"Trust verification failed (score={record.trust_score}, "
                f"required={self.config.min_trust_score})"
            )
            return EvolutionResult(
                success=False,
                acquisition_record=record,
                duration_ms=(time.time() - start_time) * 1000,
            )

        if has_missing_dependencies(best, installed_ids):
            record.status = AcquisitionStatus.FAILED
            record.error = f"Missing dependencies for '{best.cap_id}'."
            return EvolutionResult(
                success=False,
                acquisition_record=record,
                duration_ms=(time.time() - start_time) * 1000,
            )

        record.status = AcquisitionStatus.INSTALLING
        install_ok = safe_install(best, identity_id, capability_registry)
        record.installation_success = install_ok
        if not install_ok:
            record.status = AcquisitionStatus.ROLLED_BACK
            record.error = "Installation failed and was rolled back."
            return EvolutionResult(
                success=False,
                acquired=False,
                acquisition_record=record,
                duration_ms=(time.time() - start_time) * 1000,
            )

        record.status = AcquisitionStatus.VALIDATING
        valid = validate_capability(best, identity_id, capability_registry)
        record.validation_success = valid
        if not valid:
            rollback_install(best, identity_id, capability_registry)
            record.status = AcquisitionStatus.ROLLED_BACK
            record.error = "Validation failed; installation rolled back."
            return EvolutionResult(
                success=False,
                acquired=True,
                acquisition_record=record,
                duration_ms=(time.time() - start_time) * 1000,
            )

        record.status = AcquisitionStatus.RETRYING
        try:
            retry_response = retry_original_task(
                runtime, identity_id, need.original_request, session_id
            )
            record.retry_success = True
        except Exception as e:
            retry_response = None
            record.retry_success = False
            record.error = f"Retry failed: {e}"

        record.status = AcquisitionStatus.SUCCEEDED if record.retry_success else AcquisitionStatus.FAILED
        record.duration_ms = round((time.time() - start_time) * 1000, 1)

        if record.retry_success and retry_response:
            evaluate_performance(
                original_response or need.original_request,
                retry_response,
                record,
            )

        if storage and self.config.enable_learning:
            try:
                record_acquisition(identity_id, record, storage)
            except Exception:
                pass
            try:
                record_evidence(identity_id, record, storage)
            except Exception:
                pass
            if record.retry_success:
                try:
                    from core.prometheus.stages.learner import sync_learning_goal
                    goal_engine = getattr(runtime, "goal_engine", None)
                    sync_learning_goal(
                        identity_id, storage, goal_engine,
                        learning_target=self.config.learning_goal_target,
                    )
                except Exception:
                    pass

        self._interaction_acquisitions += 1

        return EvolutionResult(
            success=record.retry_success,
            acquired=True,
            acquisition_record=record,
            retry_response=retry_response,
            duration_ms=record.duration_ms,
        )

    # ── Executive delegation ─────────────────────────────────────────────

    def _delegate_to_executive(
        self,
        need: CapabilityNeed,
        identity_id: str,
        runtime,
        storage,
        session_id: Optional[str],
    ) -> Optional[EvolutionResult]:
        """Create an executive acquisition task instead of installing directly.

        Returns an EvolutionResult describing the created task, or None when
        no executive is attached (the legacy inline path then runs).
        """
        executive = getattr(runtime, "executive", None)
        if executive is None:
            return None
        from core.executive.engine import ExecutiveRuntime
        if not isinstance(executive, ExecutiveRuntime):
            return None

        cap_id = (
            need.capability_id
            or (need.suggested_capability_ids or [None])[0]
        )
        if not cap_id:
            return None

        # Don't create a task for a status question ("did you finish X?").
        # Prometheus keyword-matching can misfire on the words *about* a task;
        # the executive only commits to NEW work, and re-committing answered
        # requests is the re-commit anti-pattern.
        if _is_status_question(need.original_request):
            return EvolutionResult(
                success=False,
                acquired=False,
                acquisition_record=AcquisitionRecord(
                    need=need,
                    identity_id=identity_id,
                    mode=AcquisitionMode.AUTOMATIC,
                    status=AcquisitionStatus.SEARCHING,
                    error=f"'{cap_id}' is not an acquisition request (status question).",
                ),
            )

        # Idempotency: don't re-queue a task that is already active.
        for t in executive.active_tasks(identity_id):
            if t.capability_id == cap_id:
                return EvolutionResult(
                    success=False,
                    acquired=False,
                    acquisition_record=AcquisitionRecord(
                        need=need,
                        identity_id=identity_id,
                        mode=AcquisitionMode.AUTOMATIC,
                        status=AcquisitionStatus.SEARCHING,
                        error=f"Acquisition of '{cap_id}' already active (task {t.task_id}).",
                    ),
                )

        # Don't re-queue a capability that already reached a terminal state.
        from core.executive.models import TaskStatus
        for t in executive.store.load_terminal(identity_id):
            if t.capability_id == cap_id and t.status == TaskStatus.COMPLETED:
                return EvolutionResult(
                    success=False,
                    acquired=False,
                    acquisition_record=AcquisitionRecord(
                        need=need,
                        identity_id=identity_id,
                        mode=AcquisitionMode.AUTOMATIC,
                        status=AcquisitionStatus.SEARCHING,
                        error=f"Acquisition of '{cap_id}' already completed (task {t.task_id}).",
                    ),
                )

        goal = need.original_request or f"Acquire the {cap_id} capability"
        task = executive.create_acquisition_task(
            identity_id=identity_id,
            capability_id=cap_id,
            goal=goal,
            original_request=need.original_request or goal,
        )
        if executive.scheduler:
            executive.scheduler.start()

        record = AcquisitionRecord(
            need=need,
            identity_id=identity_id,
            mode=AcquisitionMode.AUTOMATIC,
            status=AcquisitionStatus.SEARCHING,
            error=None,
        )
        return EvolutionResult(
            success=True,
            acquired=False,  # the executive owns execution now
            acquisition_record=record,
            duration_ms=0.0,
        )
