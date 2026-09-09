"""Tests for core.timeline module."""

from core.timeline import (
    LifeEvent,
    LifeEventType,
    IdentityTimeline,
    TimelineRegistry,
)
from datetime import datetime, timezone, timedelta


class TestLifeEvent:
    def test_creation_defaults(self):
        event = LifeEvent(
            identity_id="test",
            event_type=LifeEventType.MILESTONE,
            title="Test milestone",
        )
        assert event.id
        assert event.identity_id == "test"
        assert event.event_type == LifeEventType.MILESTONE
        assert event.title == "Test milestone"
        assert event.significance == 3
        assert event.linked_entity_id is None

    def test_creation_with_all_fields(self):
        event = LifeEvent(
            identity_id="test",
            event_type=LifeEventType.RELATIONSHIP_FORMED,
            title="Met Alice",
            description="Met Alice at a conference",
            significance=5,
            linked_entity_id="alice-id",
            metadata={"location": "conference"},
        )
        assert event.event_type == LifeEventType.RELATIONSHIP_FORMED
        assert event.significance == 5
        assert event.linked_entity_id == "alice-id"
        assert event.metadata["location"] == "conference"

    def test_age_label_today(self):
        event = LifeEvent(
            identity_id="test",
            event_type=LifeEventType.CREATION,
            title="Created",
            occurred_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        assert event.age_label() == "today"

    def test_age_label_days(self):
        past = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=3)
        event = LifeEvent(
            identity_id="test",
            event_type=LifeEventType.CREATION,
            title="Created",
            occurred_at=past,
        )
        assert "3 day" in event.age_label()

    def test_age_label_weeks(self):
        past = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=14)
        event = LifeEvent(
            identity_id="test",
            event_type=LifeEventType.CREATION,
            title="Created",
            occurred_at=past,
        )
        assert "2 week" in event.age_label()

    def test_age_label_months(self):
        past = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=60)
        event = LifeEvent(
            identity_id="test",
            event_type=LifeEventType.CREATION,
            title="Created",
            occurred_at=past,
        )
        assert "month" in event.age_label()

    def test_age_label_years(self):
        past = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=400)
        event = LifeEvent(
            identity_id="test",
            event_type=LifeEventType.CREATION,
            title="Created",
            occurred_at=past,
        )
        assert "year" in event.age_label()


class TestIdentityTimeline:
    def test_creation(self):
        timeline = IdentityTimeline(identity_id="test")
        assert timeline.identity_id == "test"
        assert timeline.created_at is not None
        assert len(timeline) == 1  # Creation event
        assert timeline._events[0].event_type == LifeEventType.CREATION

    def test_creation_with_custom_time(self):
        past = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=10)
        timeline = IdentityTimeline(identity_id="test", created_at=past)
        assert timeline.age.days >= 10

    def test_age(self):
        timeline = IdentityTimeline(identity_id="test")
        assert timeline.age.total_seconds() >= 0

    def test_age_label(self):
        timeline = IdentityTimeline(identity_id="test")
        label = timeline.age_label
        assert "day" in label or "month" in label or "year" in label

    def test_record(self):
        timeline = IdentityTimeline(identity_id="test")
        event = LifeEvent(
            identity_id="test",
            event_type=LifeEventType.MILESTONE,
            title="Achieved goal",
        )
        timeline.record(event)
        assert len(timeline) == 2

    def test_events(self):
        timeline = IdentityTimeline(identity_id="test")
        timeline.record(LifeEvent(identity_id="test", event_type=LifeEventType.MILESTONE, title="First"))
        timeline.record(LifeEvent(identity_id="test", event_type=LifeEventType.KNOWLEDGE_ACQUIRED, title="Second"))
        events = timeline.events()
        assert len(events) == 3
        assert events[0].event_type == LifeEventType.CREATION
        assert events[1].title == "First"
        assert events[2].title == "Second"

    def test_recent(self):
        timeline = IdentityTimeline(identity_id="test")
        for i in range(10):
            timeline.record(LifeEvent(identity_id="test", event_type=LifeEventType.MILESTONE, title=f"Event {i}"))
        recent = timeline.recent(3)
        assert len(recent) == 3
        assert recent[-1].title == "Event 9"

    def test_by_type(self):
        timeline = IdentityTimeline(identity_id="test")
        timeline.record(LifeEvent(identity_id="test", event_type=LifeEventType.MILESTONE, title="M1"))
        timeline.record(LifeEvent(identity_id="test", event_type=LifeEventType.KNOWLEDGE_ACQUIRED, title="A1"))
        timeline.record(LifeEvent(identity_id="test", event_type=LifeEventType.MILESTONE, title="M2"))
        milestones = timeline.by_type(LifeEventType.MILESTONE)
        assert len(milestones) == 2
        assert all(e.event_type == LifeEventType.MILESTONE for e in milestones)

    def test_significant(self):
        timeline = IdentityTimeline(identity_id="test")
        timeline.record(LifeEvent(identity_id="test", event_type=LifeEventType.MILESTONE, title="Low", significance=2))
        timeline.record(LifeEvent(identity_id="test", event_type=LifeEventType.KNOWLEDGE_ACQUIRED, title="High", significance=5))
        significant = timeline.significant(4)
        # Creation event also has significance 5, so we get 2
        assert len(significant) == 2
        titles = [e.title for e in significant]
        assert "High" in titles
        assert "Identity Created" in titles

    def test_narrative(self):
        timeline = IdentityTimeline(identity_id="test")
        timeline.record(LifeEvent(identity_id="test", event_type=LifeEventType.MILESTONE, title="Test event", significance=4))
        narrative = timeline.narrative()
        assert "Timeline" in narrative
        assert "Test event" in narrative

    def test_narrative_with_user_id(self):
        timeline = IdentityTimeline(identity_id="test")
        timeline.record(LifeEvent(identity_id="test", event_type=LifeEventType.MILESTONE, title="User 1 event", significance=4, metadata={"user_id": "user-1"}))
        timeline.record(LifeEvent(identity_id="test", event_type=LifeEventType.MILESTONE, title="User 2 event", significance=4, metadata={"user_id": "user-2"}))
        narrative = timeline.narrative(user_id="user-1")
        assert "User 1 event" in narrative
        assert "User 2 event" not in narrative

    def test_len(self):
        timeline = IdentityTimeline(identity_id="test")
        assert len(timeline) == 1
        timeline.record(LifeEvent(identity_id="test", event_type=LifeEventType.MILESTONE))
        assert len(timeline) == 2


class TestTimelineRegistry:
    def test_create(self):
        registry = TimelineRegistry()
        timeline = registry.create("test-identity")
        assert timeline.identity_id == "test-identity"

    def test_get(self):
        registry = TimelineRegistry()
        registry.create("test-identity")
        timeline = registry.get("test-identity")
        assert timeline is not None

    def test_get_or_create(self):
        registry = TimelineRegistry()
        timeline = registry.get_or_create("test-identity")
        assert timeline.identity_id == "test-identity"
        timeline2 = registry.get_or_create("test-identity")
        assert timeline is timeline2

    def test_record_event(self):
        registry = TimelineRegistry()
        event = LifeEvent(identity_id="test-identity", event_type=LifeEventType.MILESTONE, title="Test")
        registry.record_event("test-identity", event)
        timeline = registry.get("test-identity")
        assert len(timeline) == 2  # Creation + test event

    def test_len(self):
        registry = TimelineRegistry()
        assert len(registry) == 0
        registry.create("test-1")
        assert len(registry) == 1
        registry.create("test-2")
        assert len(registry) == 2