"""Tests for core.experience module."""

from core.experience import (
    Experience,
    ExperienceStore,
    ExperienceType,
    ExperienceImpact,
)


class TestExperience:
    def test_creation_defaults(self):
        exp = Experience(
            identity_id="test",
            experience_type=ExperienceType.CONVERSATION,
            title="Test conversation",
        )
        assert exp.id
        assert exp.identity_id == "test"
        assert exp.experience_type == ExperienceType.CONVERSATION
        assert exp.title == "Test conversation"
        assert exp.impact == ExperienceImpact.MINOR
        assert exp.emotional_valence == 0.0
        assert exp.skills_involved == []
        assert exp.goals_involved == []
        assert exp.relationships_involved == []
        assert exp.knowledge_acquired == []
        assert exp.tags == []

    def test_creation_with_all_fields(self):
        exp = Experience(
            identity_id="test",
            experience_type=ExperienceType.ACHIEVEMENT,
            title="Solved case",
            description="Successfully solved case #123",
            impact=ExperienceImpact.FORMATIVE,
            emotional_valence=0.8,
            skills_involved=["deduction"],
            goals_involved=["goal-1"],
            relationships_involved=["rel-1"],
            knowledge_acquired=["pack-1"],
            raw_content="Full transcript...",
            tags=["important", "case"],
        )
        assert exp.experience_type == ExperienceType.ACHIEVEMENT
        assert exp.impact == ExperienceImpact.FORMATIVE
        assert exp.emotional_valence == 0.8
        assert exp.skills_involved == ["deduction"]
        assert exp.goals_involved == ["goal-1"]

    def test_is_formative(self):
        exp1 = Experience(identity_id="test", experience_type=ExperienceType.ACHIEVEMENT, impact=ExperienceImpact.FORMATIVE)
        exp2 = Experience(identity_id="test", experience_type=ExperienceType.CONVERSATION, impact=ExperienceImpact.MODERATE)
        assert exp1.is_formative()
        assert not exp2.is_formative()

    def test_summary(self):
        exp = Experience(
            identity_id="test",
            experience_type=ExperienceType.CONVERSATION,
            title="Test conversation",
            impact=ExperienceImpact.SIGNIFICANT,
            emotional_valence=0.5,
        )
        summary = exp.summary()
        assert "[conversation]" in summary
        assert "Test conversation" in summary
        assert "SIGNIFICANT" in summary
        assert "+0.5" in summary


class TestExperienceStore:
    def test_record_and_get(self):
        store = ExperienceStore()
        exp = Experience(identity_id="test", experience_type=ExperienceType.CONVERSATION, title="Test")
        store.record(exp)
        retrieved = store.get(exp.id)
        assert retrieved is exp

    def test_delete(self):
        store = ExperienceStore()
        exp = Experience(identity_id="test", experience_type=ExperienceType.CONVERSATION, title="Test")
        store.record(exp)
        assert store.delete(exp.id) is True
        assert store.get(exp.id) is None
        assert store.delete(exp.id) is False

    def test_all_for(self):
        store = ExperienceStore()
        exp1 = Experience(identity_id="test", experience_type=ExperienceType.CONVERSATION, title="First")
        exp2 = Experience(identity_id="test", experience_type=ExperienceType.OBSERVATION, title="Second")
        exp3 = Experience(identity_id="other", experience_type=ExperienceType.CONVERSATION, title="Third")
        store.record(exp1)
        store.record(exp2)
        store.record(exp3)
        all_for_test = store.all_for("test")
        assert len(all_for_test) == 2
        assert all(e.identity_id == "test" for e in all_for_test)

    def test_recent(self):
        store = ExperienceStore()
        for i in range(15):
            store.record(Experience(identity_id="test", experience_type=ExperienceType.CONVERSATION, title=f"Exp {i}"))
        recent = store.recent("test", limit=5)
        assert len(recent) == 5
        assert recent[-1].title == "Exp 14"

    def test_by_type(self):
        store = ExperienceStore()
        exp1 = Experience(identity_id="test", experience_type=ExperienceType.CONVERSATION, title="Conv")
        exp2 = Experience(identity_id="test", experience_type=ExperienceType.OBSERVATION, title="Obs")
        exp3 = Experience(identity_id="test", experience_type=ExperienceType.CONVERSATION, title="Conv2")
        store.record(exp1)
        store.record(exp2)
        store.record(exp3)
        conversations = store.by_type("test", ExperienceType.CONVERSATION)
        assert len(conversations) == 2
        assert all(e.experience_type == ExperienceType.CONVERSATION for e in conversations)

    def test_formative(self):
        store = ExperienceStore()
        exp1 = Experience(identity_id="test", experience_type=ExperienceType.ACHIEVEMENT, impact=ExperienceImpact.FORMATIVE, title="Formative")
        exp2 = Experience(identity_id="test", experience_type=ExperienceType.CONVERSATION, impact=ExperienceImpact.MINOR, title="Minor")
        store.record(exp1)
        store.record(exp2)
        formative = store.formative("test")
        assert len(formative) == 1
        assert formative[0].impact == ExperienceImpact.FORMATIVE

    def test_above_impact(self):
        store = ExperienceStore()
        exp1 = Experience(identity_id="test", experience_type=ExperienceType.CONVERSATION, impact=ExperienceImpact.TRIVIAL, title="Trivial")
        exp2 = Experience(identity_id="test", experience_type=ExperienceType.ACHIEVEMENT, impact=ExperienceImpact.SIGNIFICANT, title="Significant")
        exp3 = Experience(identity_id="test", experience_type=ExperienceType.FAILURE, impact=ExperienceImpact.FORMATIVE, title="Formative")
        store.record(exp1)
        store.record(exp2)
        store.record(exp3)
        significant = store.above_impact("test", ExperienceImpact.SIGNIFICANT)
        assert len(significant) == 2
        assert all(e.impact.value >= ExperienceImpact.SIGNIFICANT.value for e in significant)

    def test_search(self):
        store = ExperienceStore()
        exp1 = Experience(identity_id="test", experience_type=ExperienceType.CONVERSATION, title="Python talk", description="Discussed Python", tags=["python"])
        exp2 = Experience(identity_id="test", experience_type=ExperienceType.OBSERVATION, title="Java talk", description="Discussed Java", tags=["java"])
        store.record(exp1)
        store.record(exp2)
        results = store.search("python", identity_id="test")
        assert len(results) == 1
        assert "python" in results[0].title.lower() or "python" in results[0].tags

    def test_experience_count(self):
        store = ExperienceStore()
        assert store.experience_count("test") == 0
        store.record(Experience(identity_id="test", experience_type=ExperienceType.CONVERSATION))
        assert store.experience_count("test") == 1

    def test_growth_profile(self):
        store = ExperienceStore()
        exp1 = Experience(identity_id="test", experience_type=ExperienceType.CONVERSATION, impact=ExperienceImpact.MODERATE, emotional_valence=0.5)
        exp2 = Experience(identity_id="test", experience_type=ExperienceType.ACHIEVEMENT, impact=ExperienceImpact.FORMATIVE, emotional_valence=0.8)
        exp3 = Experience(identity_id="test", experience_type=ExperienceType.FAILURE, impact=ExperienceImpact.SIGNIFICANT, emotional_valence=-0.3)
        store.record(exp1)
        store.record(exp2)
        store.record(exp3)
        profile = store.growth_profile("test")
        assert profile["total"] == 3
        assert profile["by_type"]["conversation"] == 1
        assert profile["by_type"]["achievement"] == 1
        assert profile["by_type"]["failure"] == 1
        assert profile["formative_count"] == 1

    def test_to_prompt_summary(self):
        store = ExperienceStore()
        exp = Experience(identity_id="test", experience_type=ExperienceType.CONVERSATION, title="Test", impact=ExperienceImpact.MODERATE, emotional_valence=0.2)
        store.record(exp)
        summary = store.to_prompt_summary("test", limit=1)
        assert "Recent Experiences" in summary
        assert "Test" in summary

    def test_len(self):
        store = ExperienceStore()
        assert len(store) == 0
        store.record(Experience(identity_id="test", experience_type=ExperienceType.CONVERSATION))
        store.record(Experience(identity_id="other", experience_type=ExperienceType.OBSERVATION))
        assert len(store) == 2