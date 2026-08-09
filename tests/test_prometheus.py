from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.prometheus import (
    AcquisitionMode,
    AcquisitionRecord,
    AcquisitionStatus,
    CapabilityNeed,
    EvolutionResult,
    PrometheusConfig,
    PrometheusEngine,
    RegistryCandidate,
)
from core.prometheus.pipeline import EvolutionPipeline
from core.prometheus.stages.need_detector import (
    detect_need_from_input,
    detect_need_from_response,
    _CAPABILITY_KEYWORDS,
)
from core.prometheus.stages.registry_searcher import (
    search_registry,
    clear_cache,
    _load_registry_index,
)
from core.prometheus.stages.candidate_ranker import rank_candidates, pick_best
from core.prometheus.stages.trust_verifier import verify_trust, is_trusted
from core.prometheus.stages.installer import safe_install, rollback_install
from core.prometheus.stages.validator import validate_capability
from core.prometheus.stages.performance_evaluator import evaluate_performance
from core.prometheus.stages.learner import (
    record_acquisition,
    get_success_rate,
    has_previously_searched,
    _load_learning_data,
    _get_learning_path,
)
from core.prometheus.stages.evidence_recorder import (
    record_evidence,
    get_evidence_history,
)


# ─── Need Detector Tests ───────────────────────────────────────────────

class TestNeedDetector:
    def test_detect_github_from_input(self):
        need = detect_need_from_input("Can you check the latest PR on GitHub?")
        assert need is not None
        assert "github" in need.suggested_capability_ids
        assert need.source == "user_input"
        assert need.confidence > 0

    def test_detect_weather_from_input(self):
        need = detect_need_from_input("What's the weather like in Paris?")
        assert need is not None
        assert "weather" in need.suggested_capability_ids

    def test_detect_calc_from_input(self):
        need = detect_need_from_input("Calculate 42 * 3.14")
        assert need is not None
        assert "calc" in need.suggested_capability_ids

    def test_no_need_for_normal_input(self):
        need = detect_need_from_input("Hello, how are you?")
        assert need is None

    def test_detect_from_response(self):
        response = "I don't currently have a GitHub capability installed."
        need = detect_need_from_response(response, "Check my repos")
        assert need is not None
        assert need.source == "response"
        assert "github" in need.suggested_capability_ids

    def test_detect_from_response_no_gap(self):
        need = detect_need_from_response("Here is the information you requested.", "Check weather")
        assert need is None

    def test_all_capabilities_have_keywords(self):
        assert "github" in _CAPABILITY_KEYWORDS
        assert "weather" in _CAPABILITY_KEYWORDS
        assert "calc" in _CAPABILITY_KEYWORDS
        assert "web" in _CAPABILITY_KEYWORDS
        assert "filesystem" in _CAPABILITY_KEYWORDS
        assert len(_CAPABILITY_KEYWORDS) >= 6

    def test_detect_multiple_capabilities(self):
        need = detect_need_from_input("Search GitHub for weather data and calculate the average")
        assert need is not None
        assert len(need.suggested_capability_ids) >= 2


# ─── Registry Searcher Tests ────────────────────────────────────────────

class TestRegistrySearcher:
    def setup_method(self):
        clear_cache()

    def test_load_registry_index(self):
        entries = _load_registry_index()
        assert isinstance(entries, list)
        if entries:
            assert "id" in entries[0]

    def test_search_registry_returns_candidates(self):
        need = CapabilityNeed(
            suggested_capability_ids=["github"],
            skill_keywords=["github", "repository"],
        )
        candidates = search_registry(need, max_candidates=10)
        assert isinstance(candidates, list)
        for c in candidates:
            assert isinstance(c, RegistryCandidate)
            assert c.cap_id

    def test_search_registry_excludes_installed(self):
        need = CapabilityNeed(
            suggested_capability_ids=["weather"],
            skill_keywords=["weather"],
        )
        candidates = search_registry(need, installed_ids={"weather"})
        assert all(c.cap_id != "weather" for c in candidates)

    def test_search_registry_empty_need(self):
        need = CapabilityNeed(suggested_capability_ids=[], skill_keywords=[])
        candidates = search_registry(need)
        assert len(candidates) == 0

    def test_candidate_has_required_fields(self):
        need = CapabilityNeed(
            suggested_capability_ids=["calc"],
            skill_keywords=["calculate"],
        )
        candidates = search_registry(need)
        for c in candidates:
            assert c.cap_id
            assert c.name
            assert c.version
            assert c.author

    def test_rank_candidates(self):
        need = CapabilityNeed(suggested_capability_ids=["calc"], skill_keywords=["calculate"])
        candidates = search_registry(need, max_candidates=10)
        ranked = rank_candidates(candidates, need)
        if len(ranked) >= 2:
            assert ranked[0].relevance_score >= ranked[1].relevance_score

    def test_pick_best(self):
        need = CapabilityNeed(suggested_capability_ids=["calc"])
        candidates = search_registry(need)
        best = pick_best(candidates)
        assert best is not None
        assert best.cap_id

    def test_pick_best_empty(self):
        assert pick_best([]) is None


# ─── Trust Verifier Tests ───────────────────────────────────────────────

class TestTrustVerifier:
    def test_trusted_author_scores_high(self):
        c = RegistryCandidate(cap_id="test", name="Test", version="1.0.0",
                              author="IdentityOS", description="", skills=[],
                              permissions={}, manifest_url="")
        score = verify_trust(c)
        assert score >= 0.5

    def test_unknown_author_scores_lower(self):
        c = RegistryCandidate(cap_id="test", name="Test", version="0.1.0",
                              author="unknown_dev", description="", skills=[],
                              permissions={}, manifest_url="")
        score = verify_trust(c)
        assert score < 0.5

    def test_is_trusted_automatic_mode(self):
        c = RegistryCandidate(cap_id="test", name="Test", version="1.0.0",
                              author="IdentityOS", description="", skills=[],
                              permissions={}, manifest_url="")
        assert is_trusted(c, AcquisitionMode.AUTOMATIC, min_score=0.3)

    def test_not_trusted_read_only(self):
        c = RegistryCandidate(cap_id="test", name="Test", version="1.0.0",
                              author="IdentityOS", description="", skills=[],
                              permissions={}, manifest_url="")
        assert not is_trusted(c, AcquisitionMode.READ_ONLY)

    def test_network_permission_reduces_score(self):
        c1 = RegistryCandidate(cap_id="a", name="A", version="1.0.0",
                               author="IdentityOS", description="", skills=[],
                               permissions={"network": False}, manifest_url="")
        c2 = RegistryCandidate(cap_id="b", name="B", version="1.0.0",
                               author="IdentityOS", description="", skills=[],
                               permissions={"network": True}, manifest_url="")
        s1 = verify_trust(c1)
        s2 = verify_trust(c2)
        assert s1 >= s2

    def test_multiple_skills_boost_trust(self):
        c1 = RegistryCandidate(cap_id="a", name="A", version="1.0.0",
                               author="IdentityOS", description="", skills=[],
                               permissions={}, manifest_url="")
        c2 = RegistryCandidate(cap_id="b", name="B", version="1.0.0",
                               author="IdentityOS", description="",
                               skills=[{"name": "s1"}, {"name": "s2"}, {"name": "s3"}],
                               permissions={}, manifest_url="")
        s1 = verify_trust(c1)
        s2 = verify_trust(c2)
        assert s2 >= s1


# ─── Pipeline Tests ─────────────────────────────────────────────────────

class TestEvolutionPipeline:
    @pytest.fixture
    def pipeline(self):
        return EvolutionPipeline()

    def test_pipeline_no_candidates(self, pipeline):
        need = CapabilityNeed(
            suggested_capability_ids=["nonexistent_xyz_999"],
            skill_keywords=["xyz"],
        )
        result = pipeline.run(
            need=need,
            identity_id="test-bot",
            capability_registry=MagicMock(),
            runtime=MagicMock(),
            storage=MagicMock(),
        )
        assert not result.success
        assert result.acquisition_record is not None
        assert "No candidates found" in (result.acquisition_record.error or "")

    def test_pipeline_with_mock_registry(self, pipeline):
        mock_registry = MagicMock()
        mock_cap_mock = MagicMock()
        mock_cap_mock.id = "github"
        mock_cap_mock.name = "GitHub"
        mock_cap_mock.skills.return_value = [{"name": "github.search_repositories"}]
        mock_registry.list.return_value = [mock_cap_mock]
        mock_registry.install.return_value = mock_cap_mock
        mock_registry.can.return_value = True

        need = CapabilityNeed(
            suggested_capability_ids=["github"],
            skill_keywords=["github"],
            original_request="Check GitHub releases",
        )

        with patch("core.prometheus.stages.registry_searcher.search_registry") as mock_search:
            mock_candidate = RegistryCandidate(
                cap_id="github", name="GitHub", version="1.0.0",
                author="IdentityOS", description="GitHub integration",
                skills=[{"name": "github.search_repositories"}],
                permissions={"network": True}, manifest_url="",
            )
            mock_search.return_value = [mock_candidate]

            mock_runtime = MagicMock()
            mock_response = MagicMock()
            mock_response.output = "Here is the latest release: v2.0.0"
            mock_runtime.process.return_value = mock_response

            result = pipeline.run(
                need=need,
                identity_id="test-bot",
                capability_registry=mock_registry,
                runtime=mock_runtime,
                storage=MagicMock(),
            )
            assert result.success
            assert result.acquired


# ─── PrometheusEngine Tests ─────────────────────────────────────────────

class TestPrometheusEngine:
    @pytest.fixture
    def engine(self):
        return PrometheusEngine(
            capability_registry=MagicMock(),
            storage=MagicMock(),
        )

    def test_detect_need_from_input(self, engine):
        need = engine.detect_need(user_input="Search GitHub for repos")
        assert need is not None
        assert "github" in need.suggested_capability_ids

    def test_detect_need_from_response(self, engine):
        need = engine.detect_need(
            user_input="Check weather",
            response="I don't have a weather capability installed",
        )
        assert need is not None

    def test_detect_no_need(self, engine):
        need = engine.detect_need(user_input="Hello, how are you?")
        assert need is None

    def test_evolve_read_only_mode(self, engine):
        need = CapabilityNeed(
            suggested_capability_ids=["github"],
            skill_keywords=["github"],
            original_request="Check GitHub",
        )
        result = engine.evolve(
            need=need,
            identity_id="test-bot",
            mode=AcquisitionMode.READ_ONLY,
        )
        assert not result.success
        assert "Read-only" in (result.error or "")

    def test_evolve_no_candidates(self, engine):
        need = CapabilityNeed(
            suggested_capability_ids=["nonexistent_xyz"],
            original_request="Test",
        )
        result = engine.evolve(
            need=need,
            identity_id="test-bot",
            runtime=MagicMock(),
        )
        assert not result.success

    def test_engine_pre_check_and_evolve(self, engine):
        result = engine.pre_check_and_evolve(
            user_input="Hello, how are you?",
            identity_id="test-bot",
        )
        assert result is None

    @pytest.fixture
    def engine_with_capabilities(self):
        mock_registry = MagicMock()
        mock_cap = MagicMock()
        mock_cap.id = "github"
        mock_registry.list.return_value = [mock_cap]
        return PrometheusEngine(
            capability_registry=mock_registry,
            storage=MagicMock(),
        )

    def test_can_fulfill(self, engine_with_capabilities):
        need = CapabilityNeed(suggested_capability_ids=["github"])
        assert engine_with_capabilities.can_fulfill(need, "test-bot")

    def test_cannot_fulfill(self, engine_with_capabilities):
        need = CapabilityNeed(suggested_capability_ids=["weather"])
        assert not engine_with_capabilities.can_fulfill(need, "test-bot")

    def test_recursive_evolution_blocked(self, engine):
        assert not engine._evolving
        result = engine.pre_check_and_evolve(
            user_input="Check my GitHub repos",
            identity_id="test-bot",
            runtime=MagicMock(),
        )
        assert result is None or not result.success
        assert not engine._evolving

    def test_evolving_flag_set_during_evolution(self, engine):
        need = CapabilityNeed(
            suggested_capability_ids=["nonexistent_cap_xyz_999"],
            original_request="Test",
        )
        assert not engine._evolving
        result = engine.evolve(need=need, identity_id="test-bot", runtime=MagicMock())
        assert not engine._evolving
        assert not result.success

    def test_post_check_skips_when_already_evolving(self, engine):
        engine._evolving = True
        result = engine.post_check_and_evolve(
            response="I don't have a GitHub capability",
            user_input="Check GitHub",
            identity_id="test-bot",
        )
        assert result is None
        engine._evolving = False

    def test_pre_check_skips_when_already_evolving(self, engine):
        engine._evolving = True
        result = engine.pre_check_and_evolve(
            user_input="Check my GitHub repos",
            identity_id="test-bot",
        )
        assert result is None
        engine._evolving = False

    def test_evolving_flag_cleared_on_exception(self, engine):
        original_run = engine.pipeline.run
        def broken_run(*a, **kw):
            raise RuntimeError("pipeline crash")
        engine.pipeline.run = broken_run
        assert not engine._evolving
        with pytest.raises(RuntimeError):
            engine.pre_check_and_evolve(
                user_input="Check my GitHub repos",
                identity_id="test-bot",
                runtime=MagicMock(),
            )
        assert not engine._evolving
        engine.pipeline.run = original_run


# ─── Pipeline Safety Tests ──────────────────────────────────────────────

class TestPipelineSafety:
    @pytest.fixture
    def pipeline(self):
        return EvolutionPipeline()

    def test_acquisition_limit_enforced(self, pipeline):
        pipeline._interaction_acquisitions = 5
        pipeline.config.max_acquisitions_per_interaction = 1
        need = CapabilityNeed(suggested_capability_ids=["github"], skill_keywords=["github"])
        result = pipeline.run(
            need=need,
            identity_id="test-bot",
            capability_registry=MagicMock(),
            runtime=MagicMock(),
            storage=MagicMock(),
        )
        assert not result.success
        assert result.acquisition_record is not None
        assert "Acquisition limit" in (result.acquisition_record.error or "")

    def test_acquisition_limit_allows_first(self, pipeline):
        pipeline._interaction_acquisitions = 0
        pipeline.config.max_acquisitions_per_interaction = 1
        with patch("core.prometheus.stages.registry_searcher.search_registry") as mock_search:
            mock_candidate = RegistryCandidate(
                cap_id="github", name="GitHub", version="1.0.0",
                author="IdentityOS", description="", skills=[],
                permissions={}, manifest_url="",
            )
            mock_search.return_value = [mock_candidate]
            mock_registry = MagicMock()
            mock_cap_mock = MagicMock()
            mock_cap_mock.id = "github"
            mock_cap_mock.skills.return_value = [{"name": "github.search_repositories"}]
            mock_registry.list.return_value = [mock_cap_mock]
            mock_registry.install.return_value = mock_cap_mock
            mock_registry.can.return_value = True
            result = pipeline.run(
                need=CapabilityNeed(suggested_capability_ids=["github"], original_request="Check repos"),
                identity_id="test-bot",
                capability_registry=mock_registry,
                runtime=MagicMock(),
                storage=MagicMock(),
            )
            assert result.error != "Acquisition limit reached"

    def test_already_installed_skipped(self, pipeline):
        need = CapabilityNeed(capability_id="github")
        result = pipeline.run(
            need=need,
            identity_id="test-bot",
            capability_registry=MagicMock(),
            runtime=MagicMock(),
            storage=MagicMock(),
            installed_ids={"github"},
        )
        assert not result.success
        assert result.acquisition_record is not None
        assert "already installed" in (result.acquisition_record.error or "")


# ─── AcquisitionRecord Tests ────────────────────────────────────────────

class TestAcquisitionRecord:
    def test_to_dict(self):
        need = CapabilityNeed(
            capability_id="github",
            skill_keywords=["github", "repo"],
            confidence=0.8,
            source="user_input",
            original_request="Check repos",
        )
        record = AcquisitionRecord(
            need=need,
            status=AcquisitionStatus.SUCCEEDED,
            trust_score=0.9,
            installation_success=True,
            validation_success=True,
            retry_success=True,
            performance_gain=0.5,
            duration_ms=1500.0,
            identity_id="test-bot",
        )
        d = record.to_dict()
        assert d["status"] == "succeeded"
        assert d["trust_score"] == 0.9
        assert d["need"]["capability_id"] == "github"


# ─── Performance Evaluator Tests ────────────────────────────────────────

class TestPerformanceEvaluator:
    def test_helpful_retry_scores_high(self):
        record = AcquisitionRecord()
        gain = evaluate_performance(
            original_response="I can't do that, I lack a GitHub capability.",
            retry_response="Here is the latest release of IdentityOS v2.0.0 with several improvements.",
            record=record,
        )
        assert gain > 0
        assert record.performance_gain > 0

    def test_unhelpful_retry_scores_low(self):
        record = AcquisitionRecord()
        gain = evaluate_performance(
            original_response="I can't do that.",
            retry_response="Still can't access the capability.",
            record=record,
        )
        assert gain <= 0


# ─── Learner Tests ──────────────────────────────────────────────────────

class TestLearner:
    @pytest.fixture
    def tmp_storage(self):
        with tempfile.TemporaryDirectory() as td:
            from runtime.persistence import JSONFileBackend
            yield JSONFileBackend(root_dir=td)

    def test_mock_storage_never_writes_into_cwd(self, tmp_path):
        from core.prometheus.stages.evidence_recorder import (
            _get_evidence_path,
        )
        mock_storage = MagicMock()
        learning = _get_learning_path("tester", mock_storage)
        assert isinstance(learning, Path)
        assert str(learning) != ""
        assert not learning.as_posix().startswith((".identity_store", "MagicMock"))
        evidence = _get_evidence_path("tester", mock_storage)
        assert evidence is None

    def test_record_and_retrieve(self, tmp_storage):
        record = AcquisitionRecord(
            need=CapabilityNeed(skill_keywords=["github"], original_request="Check repos"),
            chosen_candidate=RegistryCandidate(
                cap_id="github", name="GitHub", version="1.0.0",
                author="IdentityOS", description="", skills=[],
                permissions={}, manifest_url="",
            ),
            installation_success=True,
            retry_success=True,
        )
        record_acquisition("test-bot", record, tmp_storage)
        rate = get_success_rate("test-bot", "github", tmp_storage)
        assert rate == 1.0

    def test_has_previously_searched(self, tmp_storage):
        record = AcquisitionRecord(
            need=CapabilityNeed(skill_keywords=["weather"], original_request="Check weather"),
            chosen_candidate=RegistryCandidate(
                cap_id="weather", name="Weather", version="1.0.0",
                author="IdentityOS", description="", skills=[],
                permissions={}, manifest_url="",
            ),
        )
        record_acquisition("test-bot", record, tmp_storage)
        assert has_previously_searched("test-bot", "weather", tmp_storage)


# ─── Evidence Recorder Tests ────────────────────────────────────────────

class TestEvidenceRecorder:
    @pytest.fixture
    def tmp_storage(self):
        with tempfile.TemporaryDirectory() as td:
            from runtime.persistence import JSONFileBackend
            yield JSONFileBackend(root_dir=td)

    def test_record_and_get_history(self, tmp_storage):
        record = AcquisitionRecord(
            need=CapabilityNeed(skill_keywords=["github"]),
            chosen_candidate=RegistryCandidate(
                cap_id="github", name="GitHub", version="1.0.0",
                author="IdentityOS", description="", skills=[],
                permissions={}, manifest_url="",
            ),
            installation_success=True,
            validation_success=True,
            retry_success=True,
            trust_score=0.9,
        )
        record_evidence("test-bot", record, tmp_storage)
        history = get_evidence_history("test-bot", tmp_storage)
        assert len(history) == 1
        assert history[0]["chosen_capability"] == "github"
        assert history[0]["installation_success"] is True
