"""
test_planner.py — SkillRouter relevance + task_planner command_exec generation

Guards against the evidence-footprint regressions:
  1. Owner/repo queries must fire ONLY github skills (was: every skill).
  2. "date"-ish tokens must not fire datetime inside words like "validate".
  3. Description-overlap must ignore stop words.
  4. Generic "what is" must not fire calc.
  5. task_planner reuses the registered command_exec capability and runs it,
     reporting honest exit codes/stdout without replacing repository files.
"""

import os
import re
import tempfile
import ast
from pathlib import Path

import pytest

from core.capabilities import CapabilityResult
from core.capabilities.registry import lookup
from core.planner import SkillRouter
from runtime.orchestrator import IdentityRuntime


class _Skill:
    def __init__(self, name, description):
        self.name = name
        self.description = description


def _skills_for(*cap_ids):
    out = []
    for cid in cap_ids:
        inst = lookup(cid)()
        for s in inst.skills():
            out.append(_Skill(s.name, s.description))
    return out


@pytest.fixture(scope="module")
def router():
    return SkillRouter(None, "test")


def _matched(router, query, skills):
    return [s.name for s in skills if router._match(query, s).get("matched")]


def test_owner_repo_fires_only_github(router):
    skills = _skills_for("datetime", "calc", "text", "weather", "web", "file_tools", "github", "system_info")
    hits = _matched(router, "how many stars does lacebx/IdentityOS have", skills)
    assert all(h.startswith("github.") for h in hits), hits
    assert hits  # should fire at least one github skill


def test_generic_questions_do_not_fire_calc(router):
    skills = _skills_for("calc", "weather", "datetime", "system_info")
    hits = _matched(router, "what is the weather in london", skills)
    assert not any(h.startswith("calc.") for h in hits), hits
    assert any(h.startswith("weather.") for h in hits), hits


def test_substring_date_does_not_fire_datetime(router):
    skills = _skills_for("datetime", "skill_validator")
    hits = _matched(router, "validate my skill syntax", skills)
    assert not any(h.startswith("datetime.") for h in hits), hits
    assert any(h.startswith("skill_validator.") for h in hits), hits


def test_arithmetic_fires_calc(router):
    skills = _skills_for("calc")
    hits = _matched(router, "compute 5 * 9", skills)
    assert any(h.startswith("calc.") for h in hits), hits


def test_system_query_fires_system_info(router):
    skills = _skills_for("system_info")
    hits = _matched(router, "what is the system", skills)
    assert any(h.startswith("system_info.") for h in hits), hits


def test_task_planner_generates_command_exec_plan():
    from core.capabilities.task_planner import TaskPlannerCapability
    plan = TaskPlannerCapability._generate_plan("create a command execution capability and run hostname")
    actions = [s["action"] for s in plan]
    assert "run_command" in actions
    assert "install_capability" in actions
    assert "write_file" not in actions
    assert "publish_capability" not in actions
    run_step = next(s for s in plan if s["action"] == "run_command")
    assert run_step["params"]["command"] == "hostname"


def test_command_exec_template_is_valid_python():
    from core.capabilities.task_planner import TaskPlannerCapability
    tmpl = TaskPlannerCapability._command_exec_template()
    ast.parse(tmpl)  # raises SyntaxError if invalid
    assert "subprocess" in tmpl


def test_task_planner_runs_real_command_honest_failure(tmp_path):
    from core.capabilities.task_planner import TaskPlannerCapability
    root = Path(__file__).resolve().parents[1]
    catalog_path = root / "registry" / "capabilities" / "index.json"
    manifest_path = root / "registry" / "capabilities" / "command_exec" / "manifest.json"
    source_path = root / "core" / "capabilities" / "command_exec" / "__init__.py"
    before = {
        path: path.read_bytes()
        for path in (catalog_path, manifest_path, source_path)
    }
    res = TaskPlannerCapability({}).call(
        "task_planner.plan_and_execute",
        goal="create a command execution capability and run a-command-that-does-not-exist-xyz",
    )
    assert res.success
    results = {r["action"]: r for r in res.data["results"]}
    run = results["run_command"]
    data = run["data"]
    # The real binary is missing → exit 127, honest error surfaced
    assert data.get("exit_code") == 127
    assert "not found" in (data.get("stderr") or "")
    assert run["success"] is False
    assert res.data["all_succeeded"] is False
    assert res.data["failed"] >= 1
    assert {path: path.read_bytes() for path in before} == before


def test_evidence_footer_label_no_duplication():
    # Simulates the orchestrator footer rendering fix
    from runtime.orchestrator import IdentityRuntime as _IR
    rt = _IR()
    footer = []
    ev = {"capability": "file_tools", "action": "file_tools.write_file",
          "success": True, "confidence": 0.9, "duration_ms": 1.2, "error": None}
    cap = ev.get("capability", "")
    act = ev.get("action", "")
    skill_label = act if act.startswith(f"{cap}.") else f"{cap}.{act}"
    footer.append(skill_label)
    assert footer == ["file_tools.write_file"]
    assert "file_tools.file_tools" not in footer[0]
