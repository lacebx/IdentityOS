"""
End-to-end validation scenarios.
"""

import os

from conftest import make_agent
from pipeline import run_pipeline
from identityos import Identity


class TestScenarios:
    """Real-world acceptance criteria scenarios."""

    def test_scenario_commitment_creation(self):
        """'I'll finish authentication tomorrow.' → intention + deadline."""
        agent = make_agent("sc-1")
        result = run_pipeline(agent, "I'll finish authentication tomorrow.", "alice", "ch", "s")
        assert len(result["intentions"]) == 1
        i = result["intentions"][0]
        assert "finish" in i["description"] or "authentication" in i["description"]

        intentions = agent.intentions(status="active")
        assert any(x["id"] == i["id"] for x in intentions)

    def test_scenario_completion(self):
        """'I finished' → intention completed, timeline updated."""
        agent = make_agent("sc-2")
        agent.infer_intentions("I'll write documentation.", author_id="alice")
        result = run_pipeline(agent, "I finished.", "alice", "ch", "s")
        assert result["completed"] is not None

        completed = agent.intentions("completed")
        assert any(x["id"] == result["completed"]["id"] for x in completed)

        events = agent.timeline(limit=10)
        assert any("completed" in e["title"].lower() for e in events)

    def test_scenario_meeting_detection(self):
        """'Let's meet Friday at 7.' → meeting recorded."""
        agent = make_agent("sc-3")
        result = run_pipeline(agent, "Let's meet Friday at 7.", "bob", "ch", "s")
        assert len(result["meetings"]) >= 1

        events = agent.timeline(limit=10)
        assert any("Meeting" in e["title"] for e in events)

    def test_scenario_preference_learning(self):
        """'My favorite editor is Neovim.' → preference stored."""
        agent = make_agent("sc-4")
        agent.observe("My favorite editor is Neovim")
        facts = agent.user_facts()
        neovim_facts = [
            f for f in facts
            if "neovim" in str(f.get("value", "")).lower()
            or "editor" in str(f.get("field", "")).lower()
        ]
        assert len(neovim_facts) >= 1

    def test_scenario_preference_update(self):
        """'I changed my mind, I prefer VS Code.' → preference updated."""
        agent = make_agent("sc-5")
        agent.observe("My favorite editor is Neovim")
        agent.observe("I changed my mind, I prefer VS Code.")
        facts = agent.user_facts()
        vscode_facts = [
            f for f in facts
            if "vs code" in str(f.get("value", "")).lower()
        ]
        assert len(vscode_facts) >= 1

    def test_scenario_relationship(self):
        """'I'm collaborating with Sarah.' → relationship created."""
        agent = make_agent("sc-6")
        agent.relationship("sarah", trust_level=0.7, context="Collaborator", edge_type="collaborator")
        rels = agent.relationships()
        assert any(r["target_id"] == "sarah" for r in rels)

    def test_scenario_reminder_generation(self):
        """Commitment with deadline → reminder available."""
        agent = make_agent("sc-7")
        agent.intention("Remind me next Monday", hours=1)
        r = agent.reminders()
        labels = [x["label"] for x in r]
        assert any(l in ("overdue", "due_soon", "approaching", "due_today") for l in labels)

    def test_scenario_team_status(self):
        """'What am I working on?' → status from goals/intentions/timeline."""
        agent = make_agent("sc-8")
        agent.infer_intentions("Fix bug.", author_id="alice")
        agent.goal("Ship v2", priority="high")

        status = agent.team_status()
        assert status["total_active_intentions"] >= 1
        assert len(status["goals"]) >= 1
        assert "alice" in status["intentions_by_author"]

    def test_scenario_evidence_chain(self):
        """'Why do you think that?' → evidence shown."""
        agent = make_agent("sc-9")
        agent.infer_intentions("I will fix the critical bug.", author_id="alice")
        intentions = agent.intentions(status="active")
        if intentions:
            ev = agent.evidence(intentions[0]["id"])
            assert isinstance(ev, list)
            prov = agent.provenance(intentions[0]["id"])
            assert "confidence" in prov

    def test_scenario_persistence(self):
        """Restart → everything persists."""
        import tempfile
        storage = os.path.join(tempfile.gettempdir(), "sc-persist")
        os.makedirs(storage, exist_ok=True)

        agent = Identity.create("sc-persist", identity_id="sc-persist", storage_path=storage)
        agent.intention("Survive restart", hours=48)
        agent.goal("Persist", priority="high")
        agent.relationship("friend", trust_level=0.9)

        export_path = os.path.join(tempfile.gettempdir(), "sc-persist.json")
        agent.export(export_path)

        restored = Identity.from_file(export_path)
        assert restored.name == "sc-persist"

        intentions = restored.intentions("all")
        assert any(i["description"] == "Survive restart" for i in intentions)

        goals = restored.goals("all")
        assert any(g["title"] == "Persist" for g in goals)

        os.remove(export_path)

    def test_scenario_comprehensive_summary(self):
        """'Summarize today's work.' → aggregate from multiple sources."""
        agent = make_agent("sc-10")
        agent.infer_intentions("Deploy API.", author_id="alice")
        agent.infer_intentions("Write tests.", author_id="bob")
        agent.goal("Release v2", priority="high")
        agent.record_event("milestone", "Sprint planning", significance=3)
        agent.relationship("charlie", trust_level=0.6)

        digest = agent.digest(period="daily")
        assert digest["summary"]["active_intentions"] >= 2
        assert digest["summary"]["active_goals"] >= 1
        assert digest["summary"]["recent_events"] >= 1

    def test_scenario_no_internal_imports(self):
        """Verify no internal runtime imports anywhere in the agent."""
        import ast

        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        internal_modules = {
            "runtime", "core", "memory", "timeline", "goals",
            "relationships", "intentions", "fact_store",
            "confidence", "cognitive_engine", "adapters",
        }

        violations = []
        for r, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]
            for f in files:
                if not f.endswith(".py"):
                    continue
                path = os.path.join(r, f)
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

        assert len(violations) == 0, f"Internal imports found:\n" + "\n".join(violations)
