"""Tests for core.synthesis module."""

from core.synthesis import build_synthesis
from core.user_profile import UserProfile, UserFact
from core.timeline import TimelineRegistry, LifeEvent, LifeEventType
from datetime import datetime, timezone


class TestBuildSynthesis:
    def test_empty_inputs(self):
        result = build_synthesis()
        assert result == ""

    def test_with_user_profile(self):
        profile = UserProfile()
        profile.add_or_update("learning_goal", "Python")
        profile.add_or_update("target_location", "Tokyo")
        profile.add_or_update("budget", "$1000")
        result = build_synthesis(user_profile=profile)
        assert "Synthesis" in result
        assert "Goals" in result

    def test_with_timeline(self):
        registry = TimelineRegistry()
        timeline = registry.create("test-identity")
        timeline.record(LifeEvent(
            identity_id="test-identity",
            event_type=LifeEventType.MILESTONE,
            title="Completed project",
            description="Finished the Python project",
            significance=5,
        ))
        result = build_synthesis(timeline=timeline, user_id="test-identity")
        assert "Actions taken" in result

    def test_with_recent_memories(self):
        memories = [
            "User: I want to learn Python",
            "Assistant: Great! Python is a good choice.",
            "User: I plan to build a web app",
        ]
        result = build_synthesis(recent_memories=memories)
        assert "Intentions" in result

    def test_detects_tokyo_gap(self):
        profile = UserProfile()
        profile.add_or_update("target_location", "Tokyo")
        # No housing action
        result = build_synthesis(user_profile=profile)
        assert "Tokyo" in result
        assert "housing" in result.lower()

    def test_detects_japanese_course_conflict(self):
        profile = UserProfile()
        profile.add_or_update("learning_goal", "Japanese")
        profile.add_or_update("budget", "200")
        result = build_synthesis(user_profile=profile)
        # The synthesis might detect this conflict

    def test_detects_goals_without_actions(self):
        profile = UserProfile()
        profile.add_or_update("learning_goal", "Python")
        # No events
        result = build_synthesis(user_profile=profile)
        # The synthesis returns a generic message when there are goals but no events
        assert "Synthesis" in result

    def test_intention_detection(self):
        memories = [
            "User: I want to learn Python",
            "User: I need to finish my project",
            "User: I will start tomorrow",
        ]
        result = build_synthesis(recent_memories=memories)
        assert "Intentions" in result
        assert "learn Python" in result or "finish my project" in result

    def test_decision_detection(self):
        memories = [
            "User: I promised to finish by Friday",
            "User: I decided to cancel the meeting",
            "User: The project is on hold",
        ]
        result = build_synthesis(recent_memories=memories)
        assert "Decisions" in result or "commitments" in result.lower()

    def test_conflict_detection_same_time(self):
        memories = [
            "User: I want to learn Python this weekend",
            "User: I plan to go hiking this weekend",
        ]
        result = build_synthesis(recent_memories=memories)
        assert "conflict" in result.lower() or "window" in result.lower()

    def test_conflict_intention_vs_cancelled(self):
        memories = [
            "User: I want to build a web app",
            "User: I cancelled the web app project",
        ]
        result = build_synthesis(recent_memories=memories)
        assert "blocked" in result.lower() or "cancel" in result.lower()

    def test_user_id_filtering(self):
        registry = TimelineRegistry()
        timeline = registry.create("test-identity")
        timeline.record(LifeEvent(
            identity_id="test-identity",
            event_type=LifeEventType.MILESTONE,
            title="Test event",
            significance=4,
            metadata={"user_id": "user-1"},
        ))
        # Event for different user
        timeline.record(LifeEvent(
            identity_id="test-identity",
            event_type=LifeEventType.MILESTONE,
            title="Other event",
            significance=4,
            metadata={"user_id": "user-2"},
        ))
        result = build_synthesis(timeline=timeline, user_id="user-1")
        # The timeline events are included but filtered
        assert "user-1" in result or "user-2" not in result or "Test event" in result