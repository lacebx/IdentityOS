"""Tests for core.user_profile — structured user knowledge."""

from core.user_profile import UserProfile, extract_user_facts


class TestUserProfile:
    def test_add_and_update(self):
        profile = UserProfile("u1")
        profile.add_or_update("preferences.favorite_color", "blue", "My favorite color is blue", 0.9)
        fact = profile.get("preferences.favorite_color")
        assert fact.value == "blue"
        assert fact.confidence > 0.85
        assert not fact.uncertain

    def test_contradiction_adopts_latest_value(self):
        profile = UserProfile("u2")
        profile.add_or_update("preferences.favorite_color", "blue", "My favorite color is blue", 0.9)
        profile.add_or_update("preferences.favorite_color", "black", "Actually, make it black", 0.9)
        fact = profile.get("preferences.favorite_color")
        # The user's most recent disclosure wins the field value...
        assert fact.value == "black"
        # ...but the fact is flagged uncertain with lowered confidence.
        assert fact.uncertain
        assert fact.contradictions == 1
        assert fact.confidence < 0.85

    def test_agreement_keeps_high_confidence(self):
        profile = UserProfile("u3")
        for _ in range(4):
            profile.add_or_update("name", "dane", "My name is dane", 0.9)
        fact = profile.get("name")
        assert fact.value == "dane"
        assert not fact.uncertain
        assert fact.confidence >= 0.85

    def test_extract_favorite_color(self):
        facts = extract_user_facts("My favorite color is green")
        by_field = {f.field: f for f in facts}
        assert "preferences.favorite_color" in by_field
        assert by_field["preferences.favorite_color"].value == "green"


class TestContradictionConfidence:
    def test_winner_reflects_newest_statement(self):
        profile = UserProfile("u4")
        profile.add_or_update("preferences.drink", "coffee", "I like coffee", 0.9)
        profile.add_or_update("preferences.drink", "tea", "Actually I prefer tea", 0.9)
        fact = profile.get("preferences.drink")
        assert fact.value == "tea"
        assert fact.uncertain