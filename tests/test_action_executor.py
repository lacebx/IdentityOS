"""
test_action_executor.py — ActionExecutor + CapabilityResolver (Step 2).

The authoritative execution path:
    Resolver(installed) → validate → capability.call() → ActionResult

Invariants under test:
  * skills resolve ONLY against installed capabilities (never global lookup())
  * unknown / not-installed skills → FAILED (structural, safe)
  * capability failure / exception → FAILED (never EXECUTED)
  * a successful call is EXECUTED, never auto-SUCCEEDED (verifier-only upgrade)
  * tool_defs() list only installed skills
  * runtime system keys never pass through to the capability
"""

import json

import pytest

from core.capabilities.base import Capability, Skill
from core.capabilities.registry import CapabilityRegistry, register
from core.capabilities.result import CapabilityResult
from core.executive.action_executor import ActionExecutor
from core.executive.result import ActionResultStatus
from core.executive.resolver import CapabilityResolver


@pytest.fixture()
def storage(tmp_path):
    from runtime.persistence import JSONFileBackend
    return JSONFileBackend(root_dir=str(tmp_path / "store"))


@pytest.fixture()
def registry(storage):
    return CapabilityRegistry(storage=storage)


@pytest.fixture()
def executor(registry):
    return ActionExecutor(registry, "id-1")


# ── CapabilityResolver ──────────────────────────────────────────────────

def test_resolve_fq_skill_of_installed_capability(registry):
    registry.install("id-1", "resolver_echo")
    res = CapabilityResolver(registry, "id-1").resolve("resolver_echo.run")
    assert res.found is True
    assert res.capability_id == "resolver_echo"
    assert res.skill_name == "resolver_echo.run"


def test_resolve_not_installed_fails(registry):
    # registered globally but never installed → must NOT resolve
    res = CapabilityResolver(registry, "id-1").resolve("resolver_missing.run")
    assert res.found is False
    assert "no installed" in res.reason


def test_resolve_bare_skill_when_single_provider(registry):
    registry.install("id-1", "resolver_echo")
    res = CapabilityResolver(registry, "id-1").resolve("run")
    assert res.found is True
    assert res.skill_name == "resolver_echo.run"


def test_list_skills_only_installed(registry):
    registry.install("id-1", "resolver_echo")
    skills = CapabilityResolver(registry, "id-1").list_skills()
    assert "resolver_echo.run" in skills
    assert all(s.startswith("resolver_echo") for s in skills)


# ── ActionExecutor ──────────────────────────────────────────────────────

def test_execute_skill_produces_executed_never_succeeded(executor, registry):
    registry.install("id-1", "resolver_echo")
    ar = executor.execute("resolver_echo.run", text="hello")
    assert ar.status == ActionResultStatus.EXECUTED
    assert ar.output == {"echo": "hello"}
    assert ar.succeeded is False
    assert ar.verified_success is False
    assert len(ar.evidence) >= 1
    assert any(e.label == "execute" for e in ar.evidence)


def test_unknown_skill_fails_structurally(executor, registry):
    registry.install("id-1", "resolver_echo")
    ar = executor.execute("resolver_echo.does_not_exist")
    assert ar.status == ActionResultStatus.FAILED
    assert ar.succeeded is False


def test_not_installed_capability_fails(executor):
    ar = executor.execute("resolver_missing.run")
    assert ar.status == ActionResultStatus.FAILED
    assert "no installed" in (ar.error or "")


def test_capability_failure_is_failed(executor, registry):
    registry.install("id-1", "resolver_flaky")
    ar = executor.execute("resolver_flaky.run")
    assert ar.status == ActionResultStatus.FAILED
    assert "exploded" in (ar.error or "")
    assert ar.succeeded is False


def test_exception_in_call_is_failed_with_evidence(executor, registry):
    registry.install("id-1", "resolver_boom")
    ar = executor.execute("resolver_boom.run")
    assert ar.status == ActionResultStatus.FAILED
    assert "kaboom" in (ar.error or "")
    assert any(e.label == "execute" and not e.success for e in ar.evidence)


def test_tool_defs_only_include_installed(executor, registry):
    defs_before = [d["function"]["name"] for d in executor.tool_defs()]
    assert "resolver_echo.run" not in defs_before
    registry.install("id-1", "resolver_echo")
    defs_after = [d["function"]["name"] for d in executor.tool_defs()]
    assert "resolver_echo.run" in defs_after


def test_result_is_persistable_and_truthful(executor, registry):
    registry.install("id-1", "resolver_echo")
    ar = executor.execute("resolver_echo.run", text="hi")
    payload = json.loads(json.dumps(ar.to_dict(), default=str))
    assert payload["status"] == "executed"
    assert payload["verified"] is False
    assert payload["output"] == {"echo": "hi"}


def test_system_keys_never_passed_to_capability(executor, registry):
    registry.install("id-1", "resolver_probe")
    ar = executor.execute("resolver_probe.run", tool_call_id="tc-1", identity_id="id-1", text="x")
    assert ar.output == {"leak": False}


# ── Shared stub capabilities (module-level, globally registered) ────────

class CapBase(Capability):
    version = "1.0.0"
    author = "test"
    license = "MIT"
    _SKILLS: list = []

    def install(self, identity_id, storage):
        storage.save(identity_id, f"capability.{self.id}", {"installed_at": None})

    def uninstall(self, identity_id, storage):
        storage.delete(identity_id, f"capability.{self.id}")

    def prompts(self, identity_id):
        return []

    def skills(self):
        return list(self._SKILLS)

    def call(self, skill_name, **params):
        return self._call(skill_name, **params)


@register
class _ResolverEcho(CapBase):
    id = "resolver_echo"
    _SKILLS = [Skill(name="resolver_echo.run", description="echo")]
    def _call(self, skill_name, **params):
        return oks("resolver_echo", skill_name, {"echo": params.get("text")})


@register
class _ResolverFlaky(CapBase):
    id = "resolver_flaky"
    _SKILLS = [Skill(name="resolver_flaky.run", description="flaky")]
    def _call(self, skill_name, **params):
        return faill("resolver_flaky", skill_name, "boom", "exploded")


@register
class _ResolverBoom(CapBase):
    id = "resolver_boom"
    _SKILLS = [Skill(name="resolver_boom.run", description="boom")]
    def _call(self, skill_name, **params):
        raise RuntimeError("kaboom")


@register
class _ResolverProbe(CapBase):
    id = "resolver_probe"
    _SKILLS = [Skill(name="resolver_probe.run", description="probe")]
    def _call(self, skill_name, **params):
        return oks("resolver_probe", skill_name, {"leak": "tool_call_id" in params or "identity_id" in params})


def oks(capability: str, action: str, data):
    return CapabilityResult.ok(capability, action, data, source="test")


def faill(capability: str, action: str, errtype: str, msg: str):
    return CapabilityResult.fail(capability, action, errtype, msg)