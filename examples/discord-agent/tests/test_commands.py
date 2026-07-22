"""
Test all slash command outputs through the SDK.
"""

from conftest import make_agent
from services.summary import generate_team_status, generate_digest, format_evidence
from services.constitution import format_constitution


class TestCommands:
    def test_about(self):
        agent = make_agent("cmd-about")
        desc = agent.describe()
        assert desc["name"] == "cmd-about"
        assert "version" in desc

    def test_status(self):
        agent = make_agent("cmd-status")
        agent.infer_intentions("I'll do X.", author_id="alice")
        text = generate_team_status(agent)
        assert "Team Status" in text
        assert "alice" in text

    def test_goals(self):
        agent = make_agent("cmd-goals")
        agent.goal("Test goal", priority="high")
        goals = agent.goals(status="active")
        assert len(goals) >= 1
        assert goals[0]["title"] == "Test goal"

    def test_intentions(self):
        agent = make_agent("cmd-ints")
        agent.intention("Test intention", hours=24)
        ints = agent.intentions(status="active")
        assert any(i["description"] == "Test intention" for i in ints)

    def test_reminders(self):
        agent = make_agent("cmd-remind")
        agent.intention("Due soon", hours=0)
        r = agent.reminders()
        assert len(r) >= 1
        assert any(x["description"] == "Due soon" for x in r)

    def test_digest_daily(self):
        agent = make_agent("cmd-digest-d")
        text = generate_digest(agent, "daily")
        assert "Digest" in text

    def test_digest_weekly(self):
        agent = make_agent("cmd-digest-w")
        text = generate_digest(agent, "weekly")
        assert "Digest" in text

    def test_timeline(self):
        agent = make_agent("cmd-tl")
        agent.record_event("milestone", "Test event")
        events = agent.timeline(limit=5)
        assert any(e["title"] == "Test event" for e in events)

    def test_evidence(self):
        agent = make_agent("cmd-evidence")
        g = agent.goal("Evidence goal", priority="high")
        text = format_evidence(agent, g["id"])
        assert "Evidence" in text or "No evidence" in text

    def test_confidence(self):
        agent = make_agent("cmd-conf")
        g = agent.goal("Conf goal", priority="high")
        conf = agent.confidence(g["id"])
        assert conf["entity_id"] == g["id"]

    def test_constitution(self):
        agent = make_agent("cmd-con")
        text = format_constitution(agent)
        assert "Constitution" in text or "Laws" in text
