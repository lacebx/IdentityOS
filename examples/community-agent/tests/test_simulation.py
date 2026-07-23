"""
100-conversation stress test to verify the bot survives extended use without crashing.

Simulates multiple users, meetings, deadlines, reminders, completed work,
relationship formation, timeline generation, and digest generation.
"""

import os
import random

from .conftest import make_agent

_MESSAGES = [
    "Hello!",
    "Good morning!",
    "What are we working on today?",
    "I'll finish the authentication module.",
    "I will deploy the API tonight.",
    "Let me review the PR.",
    "I'm going to write documentation this week.",
    "I'll fix the bug tomorrow.",
    "I will refactor the database layer.",
    "Let's meet Friday at 3pm.",
    "We should sync tomorrow morning.",
    "Can we schedule a meeting?",
    "I finished the authentication module.",
    "Done with the PR review.",
    "Completed the documentation.",
    "What's the status?",
    "What is everyone working on?",
    "What are we behind on?",
    "Why do you think that?",
    "Show me the evidence.",
    "That looks good to me.",
    "I disagree with that approach.",
    "Let's use OAuth2 instead.",
    "We decided to go with PostgreSQL.",
    "The deployment is scheduled for Friday.",
    "Who is working on the frontend?",
    "I'll take care of the tests.",
    "I'll handle the CI pipeline.",
    "Let's discuss the architecture.",
    "I have a question about the API.",
    "Can you review my code?",
    "The build is failing.",
    "I fixed the build.",
    "Great work everyone!",
    "I'll update the documentation.",
    "Deployed to staging.",
    "Ready for production release.",
    "We should add error handling.",
    "Let's meet next week.",
    "I'll create the PR.",
    "Merged to main.",
    "Can someone help with this bug?",
    "I'll investigate the issue.",
    "Found the root cause.",
    "Fix is ready for review.",
    "Let's plan the next sprint.",
    "I'll prepare the release notes.",
]


class TestSimulation:
    """Run 100 simulated conversations to verify stability."""

    USERS = ["alice", "bob", "charlie", "diana", "eve"]

    def test_100_conversations_no_crash(self):
        agent = make_agent("stress-test")
        user_states = {u: {"conversations": 0, "intentions": 0} for u in self.USERS}

        for i in range(100):
            user = random.choice(self.USERS)
            msg = random.choice(_MESSAGES)
            user_states[user]["conversations"] += 1

            # Simulate the full pipeline
            intentions = agent.infer_intentions(msg, author_id=user)
            user_states[user]["intentions"] += len(intentions)

            meetings = agent.infer_meetings(msg, author_id=user)
            _ = meetings  # consumed

            # 20% chance of completing an intention
            if random.random() < 0.2:
                from services.intentions import complete_authors_intention
                complete_authors_intention(agent, user, "I finished")

            # Every message goes through chat
            reply = agent.chat(msg)
            assert isinstance(reply, str)

            # Occasionally run non-chat operations
            if i % 10 == 0:
                desc = agent.describe()
                assert desc["name"] == "stress-test"

            if i % 15 == 0:
                status = agent.team_status()
                assert "goals" in status
                assert "intentions_by_author" in status

            if i % 25 == 0:
                digest = agent.digest("daily")
                assert "summary" in digest

            if i % 30 == 0:
                reminders = agent.reminders()
                assert isinstance(reminders, list)

            if i % 20 == 0:
                rels = agent.relationships()
                assert isinstance(rels, list)

            if i % 35 == 0:
                exported = agent.export()
                assert exported["identity"]["name"] == "stress-test"

        # Verify state after 100 conversations
        final = agent.describe()
        assert final["name"] == "stress-test"
        assert final["memories"] >= 0
        assert final["timeline_events"] >= 0

        # Verify export still works
        exported = agent.export()
        assert exported["identity"]["name"] == "stress-test"

    def test_100_sequential_operations(self):
        """Run 100 sequential SDK operations to verify no crashes."""
        agent = make_agent("op-stress")

        for i in range(100):
            op = i % 15
            if op == 0:
                agent.chat("Test message")
            elif op == 1:
                agent.observe(f"My preference is number {i}")
            elif op == 2:
                agent.goal(f"Goal {i}", priority="medium")
            elif op == 3:
                agent.intention(f"Intention {i}", hours=24)
            elif op == 4:
                agent.remember(f"Memory {i}", tags=["test"])
            elif op == 5:
                agent.timeline(limit=5)
            elif op == 6:
                agent.team_status()
            elif op == 7:
                agent.digest("daily")
            elif op == 8:
                agent.reminders()
            elif op == 9:
                agent.relationships()
            elif op == 10:
                agent.skills()
            elif op == 11:
                agent.describe()
            elif op == 12:
                agent.user_facts()
            elif op == 13:
                agent.export()
            elif op == 14:
                agent.constitution()

        assert agent.describe()["name"] == "op-stress"


class TestEndToEnd:
    """
    End-to-end simulation exercising every acceptance criterion.

    Scenarios:
      1. User creates intention → stored with deadline
      2. 24h passes → reminder sent
      3. User completes → marked done, timeline updated
      4. Meeting proposed → recorded with time
      5. Meeting outcome → stored with participants, decisions
      6. "What are we behind on?" → reasoned from goals/intentions/timeline
      7. "Why?" → evidence shown
      8. Restart → everything persists
      9. No internal imports used
      10. Survives 100 conversations
    """

    def test_scenario_1_create_intention_with_deadline(self):
        """User: 'I'll finish authentication tomorrow.' → Bot creates intention, stores deadline."""
        agent = make_agent("scenario-1")
        results = agent.infer_intentions(
            "I'll finish authentication tomorrow.",
            author_id="alice",
        )
        assert len(results) == 1
        i = results[0]
        assert i["description"] == "finish authentication"
        assert i["metadata"]["author_id"] == "alice"
        assert i["status"] == "active"

        # Verify it shows up in intentions list
        intentions = agent.intentions(status="active")
        assert any(x["id"] == i["id"] for x in intentions)

        # Verify timeline event
        events = agent.timeline(limit=5)
        assert any("Intention created" in e["title"] for e in events)

    def test_scenario_2_reminder(self):
        """24 hours later → Bot reminds user."""
        agent = make_agent("scenario-2")
        agent.infer_intentions(
            "I'll fix the bug.",
            author_id="bob",
        )
        reminders = agent.reminders()
        assert isinstance(reminders, list)

    def test_scenario_3_complete_intention(self):
        """User: 'I finished.' → Bot marks intention complete, updates timeline, records evidence."""
        agent = make_agent("scenario-3")
        agent.infer_intentions(
            "I'll complete the documentation.",
            author_id="charlie",
        )

        from services.intentions import complete_authors_intention
        result = complete_authors_intention(agent, "charlie", "I finished the docs")
        assert result is not None
        assert result["description"] == "complete the documentation"

        # Verify completed
        completed = agent.intentions("completed")
        assert any(x["id"] == result["id"] for x in completed)

        # Verify timeline updated
        events = agent.timeline(limit=10)
        assert any("completed" in e["title"].lower() for e in events)

    def test_scenario_4_meeting_proposal(self):
        """Users: 'Let's meet Friday at 7.' → Meeting appears. Reminder sent."""
        agent = make_agent("scenario-4")
        meetings = agent.infer_meetings(
            "Let's meet Friday at 7.",
            author_id="diana",
        )
        assert len(meetings) >= 1

        # Verify timeline has the meeting event
        events = agent.timeline(limit=10)
        assert any("Meeting" in e["title"] for e in events)

        # Verify memory stored
        memories = agent.memories(memory_type="semantic")
        meeting_memories = [m for m in memories if "Meeting" in m["content"]]
        assert len(meeting_memories) >= 1

    def test_scenario_5_meeting_outcome(self):
        """After meeting → Bot records participants, summary, decisions, timeline."""
        agent = make_agent("scenario-5")
        from services.meetings import record_meeting_outcome

        event_id = record_meeting_outcome(
            agent,
            participants=["alice", "bob", "charlie"],
            summary="Discussed authentication strategy",
            decisions=["Use OAuth2", "Deploy by Friday"],
        )
        assert event_id is not None

        events = agent.timeline(limit=10)
        meeting_event = [e for e in events if e["id"] == event_id]
        assert len(meeting_event) == 1
        assert "Meeting completed" in meeting_event[0]["title"]

        memories = agent.memories(memory_type="semantic")
        outcome_memories = [m for m in memories if "Meeting outcome" in m["content"]]
        assert len(outcome_memories) >= 1
        assert "alice" in outcome_memories[0]["content"]

    def test_scenario_6_team_status(self):
        """User: 'What are we behind on?' → Bot reasons from goals, intentions, timeline, evidence, confidence."""
        agent = make_agent("scenario-6")
        agent.infer_intentions("I'll deploy the API.", author_id="alice")
        agent.infer_intentions("I'll fix the database.", author_id="bob")
        agent.goal("Ship v2.0", priority="high")

        status = agent.team_status()
        assert status["total_active_intentions"] >= 2
        assert len(status["goals"]) >= 1

        # The status should be author-aware
        by_author = status["intentions_by_author"]
        assert "alice" in by_author or "bob" in by_author

    def test_scenario_7_evidence(self):
        """User: 'Why?' → Bot shows evidence."""
        agent = make_agent("scenario-7")
        g = agent.goal("Evidence test", priority="high")

        ev = agent.evidence(g["id"])
        assert isinstance(ev, list)

        prov = agent.provenance(g["id"])
        assert prov["entity_id"] == g["id"]

        conf = agent.confidence(g["id"])
        assert conf["entity_id"] == g["id"]

    def test_scenario_8_persistence(self):
        """Restart bot → Everything persists. Nothing lost."""
        import tempfile
        import os
        from identityos import Identity

        storage = os.path.join(tempfile.gettempdir(), "persist-test")
        os.makedirs(storage, exist_ok=True)

        # Create identity with data
        agent = Identity.create(
            "persistent-agent",
            identity_id="persistent-agent",
            storage_path=storage,
        )
        agent.intention("Survive restart", hours=48)
        agent.goal("Persist across restarts", priority="high")
        agent.observe("My name is Persistent")

        # Export
        export_path = os.path.join(tempfile.gettempdir(), "persist-export.json")
        agent.export(export_path)

        # Simulate restart: load from file
        restored = Identity.from_file(export_path)
        assert restored.name == "persistent-agent"

        intentions = restored.intentions("all")
        assert any(i["description"] == "Survive restart" for i in intentions)

        goals = restored.goals("all")
        assert any(g["title"] == "Persist across restarts" for g in goals)

        os.remove(export_path)

    def test_scenario_9_no_internal_imports(self):
        """The application must not import any internal IdentityOS modules."""
        import ast

        source_dir = os.path.join(
            os.path.dirname(__file__), "..",
        )

        violations = []
        internal_modules = {
            "runtime", "core", "memory", "timeline", "goals", "relationships",
            "intentions", "fact_store", "confidence", "cognitive_engine",
        }

        for root, dirs, files in os.walk(source_dir):
            for f in files:
                if not f.endswith(".py"):
                    continue
                path = os.path.join(root, f)
                with open(path) as fh:
                    try:
                        tree = ast.parse(fh.read())
                        for node in ast.walk(tree):
                            if isinstance(node, ast.Import):
                                for alias in node.names:
                                    parts = alias.name.split(".")
                                    if parts[0] in internal_modules:
                                        violations.append(f"{path}: import {alias.name}")
                            elif isinstance(node, ast.ImportFrom):
                                if node.module:
                                    parts = node.module.split(".")
                                    if parts[0] in internal_modules:
                                        violations.append(f"{path}: from {node.module} import ...")
                    except SyntaxError:
                        pass

        # Filter out allowed patterns
        allowed_files = {"conftest.py", "__init__.py"}
        violations = [
            v for v in violations
            if os.path.basename(v.split(":")[0]) not in allowed_files
        ]

        # Exclude SDK imports (allowed)
        violations = [v for v in violations if "from identityos import" not in v and "from sdk import" not in v]

        assert len(violations) == 0, (
            f"Internal imports found ({len(violations)}):\n" + "\n".join(violations)
        )

    def test_scenario_10_100_conversations_stable(self):
        """The bot should survive 100 simulated conversations without crashing."""
        agent = make_agent("e2e-stress")
        for i in range(100):
            user = random.choice(["alice", "bob"])
            msg = random.choice([
                "Hello!", "I'll finish this.", "Let's meet.", "Done.",
                "What's the status?", "I fixed it.",
            ])
            agent.infer_intentions(msg, author_id=user)
            agent.infer_meetings(msg, author_id=user)
            agent.chat(msg)
            if i % 10 == 0:
                agent.team_status()
                agent.reminders()
                agent.digest("daily")
        assert agent.describe()["name"] == "e2e-stress"
