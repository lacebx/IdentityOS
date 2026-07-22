"""
Stress test — 100 conversations without crashing.
"""

import random

from conftest import make_agent

_MESSAGES = [
    "Hello!", "Good morning!", "What's up?",
    "I'll fix the bug.", "I will deploy tonight.", "Let me review the PR.",
    "I'll finish authentication tomorrow.", "I will write docs next week.",
    "Let's meet Friday at 7.", "We should sync tomorrow.",
    "Can we schedule a meeting?",
    "I finished.", "Done.", "Completed.",
    "What is everyone working on?", "What's the status?",
    "Why do you think that?", "Show me the evidence.",
    "My favorite color is blue.", "I like Python.",
    "I'm collaborating with Sarah.", "I'm mentoring Bob.",
]


class TestStress:
    def test_100_conversations(self):
        agent = make_agent("stress-100")
        users = ["alice", "bob", "charlie", "diana"]

        for i in range(100):
            user = random.choice(users)
            msg = random.choice(_MESSAGES)

            from pipeline import run_pipeline
            result = run_pipeline(agent, msg, user, "ch", f"sess-{i}")
            assert result["reply"] is not None

            if i % 10 == 0:
                agent.team_status()
                agent.reminders()
                agent.digest("daily")
                agent.describe()

        assert agent.describe()["name"] == "stress-100"
        assert agent.export()["identity"]["name"] == "stress-100"

    def test_100_operations(self):
        agent = make_agent("stress-ops")

        for i in range(100):
            op = i % 11
            if op == 0:
                agent.chat("Hello")
            elif op == 1:
                agent.goal(f"G{i}", priority="medium")
            elif op == 2:
                agent.intention(f"I{i}", hours=24)
            elif op == 3:
                agent.remember(f"M{i}", tags=["t"])
            elif op == 4:
                agent.timeline(5)
            elif op == 5:
                agent.team_status()
            elif op == 6:
                agent.digest("daily")
            elif op == 7:
                agent.reminders()
            elif op == 8:
                agent.relationships()
            elif op == 9:
                agent.describe()
            elif op == 10:
                agent.export()

        assert agent.describe()["name"] == "stress-ops"
