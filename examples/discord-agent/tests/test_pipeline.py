"""
Test the message processing pipeline end-to-end.
"""

from conftest import make_agent
from pipeline import (
    run_pipeline,
    step_detect_intentions,
    step_detect_meetings,
    step_detect_completion,
)


class TestPipelineIntegration:
    def test_full_pipeline_intention(self):
        agent = make_agent("pipe-1")
        result = run_pipeline(agent, "I'll finish authentication tomorrow.", "user-1", "ch-1", "sess-1")
        assert result["reply"] is not None
        assert len(result["intentions"]) >= 1
        assert result["intentions"][0]["metadata"]["author_id"] == "user-1"

    def test_full_pipeline_meeting(self):
        agent = make_agent("pipe-2")
        result = run_pipeline(agent, "Let's meet Friday at 7.", "user-2", "ch-2", "sess-2")
        assert result["reply"] is not None
        assert len(result["meetings"]) >= 1

    def test_full_pipeline_completion(self):
        agent = make_agent("pipe-3")
        agent.infer_intentions("I'll review the PR.", author_id="user-3")
        result = run_pipeline(agent, "I finished.", "user-3", "ch-3", "sess-3")
        assert result["completed"] is not None
        assert "review" in result["completed"]["description"]

    def test_pipeline_evidence_question(self):
        agent = make_agent("pipe-4")
        agent.goal("Evidence goal", priority="medium")
        result = run_pipeline(agent, "Why do you think that?", "user-4", "ch-4", "sess-4")
        assert result["handled"]
        assert result["reply"] is not None

    def test_pipeline_status_question(self):
        agent = make_agent("pipe-5")
        agent.infer_intentions("I'll deploy.", author_id="user-5")
        result = run_pipeline(agent, "What is everyone working on?", "user-5", "ch-5", "sess-5")
        assert result["handled"]
        assert "Status" in result["reply"] or "Team" in result["reply"]

    def test_pipeline_normal_chat(self):
        agent = make_agent("pipe-6")
        result = run_pipeline(agent, "Hello! How are you?", "user-6", "ch-6", "sess-6")
        assert result["reply"] is not None
        assert not result["handled"]

    def test_pipeline_context_annotation(self):
        agent = make_agent("pipe-7")
        result = run_pipeline(agent, "I'll fix the bug tomorrow.", "user-7", "ch-7", "sess-7")
        assert "Tracked" in result["reply"] or result["intentions"]

    def test_step_intentions(self):
        agent = make_agent("pipe-step-i")
        r = step_detect_intentions(agent, "I will deploy tonight.", "alice", "ch")
        assert len(r) == 1

    def test_step_meetings(self):
        agent = make_agent("pipe-step-m")
        r = step_detect_meetings(agent, "We should sync tomorrow.", "bob", "ch")
        assert len(r) >= 1

    def test_step_completion(self):
        agent = make_agent("pipe-step-c")
        agent.infer_intentions("Write tests.", author_id="charlie")
        r = step_detect_completion(agent, "I finished writing tests.", "charlie", "ch")
        assert r is not None
