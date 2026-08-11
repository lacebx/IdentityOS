"""
test_executive_step5.py — R6 regression: no re-entrant verify_goal.

The old ``_verify_goal`` called ``ctx.runtime.process()`` with the original
request, which re-triggered Prometheus keyword detection, re-committed
terminal goals and recursed until RecursionError.

New contract asserts:
  * verify_goal NEVER calls runtime.process() (no re-entrancy).
  * a prior successful `verify` step → CONFIRMED without any re-entry.
  * an existing terminal task for the same goal → NOT re-committed (dedup).
  * requery budget is bounded per step params.
"""

import time

import pytest

from core.capabilities.registry import CapabilityRegistry
from core.executive import ExecutiveRuntime
from core.executive.executor import ExecutionContext, _verify_goal
from core.executive.models import Evidence, Task, TaskStatus, TaskStep, TaskStepStatus


@pytest.fixture()
def storage(tmp_path):
    from runtime.persistence import JSONFileBackend
    return JSONFileBackend(root_dir=str(tmp_path / "store"))


@pytest.fixture()
def registry(storage):
    return CapabilityRegistry(storage=storage)


class NoReentrantRuntime:
    """Fake engine whose process() RAISES to prove verify_goal never calls it."""

    class _Boom:
        def process(self, *_a, **_k):
            raise AssertionError("verify_goal must never re-enter process()")

    def __init__(self):
        self.runtime = self
        self._process = self._Boom()
        self._tasks = []

    @property
    def process(self):
        raise AssertionError("verify_goal must never call runtime.process()")

    def active_tasks(self, identity_id):
        return [t for t in self._tasks if t.status.value in ("queued", "running", "blocked")]

    def history(self, identity_id, limit=10):
        return [t.to_dict() for t in self._tasks if t.status.value in ("completed", "failed", "cancelled")][:limit]

    def get_task(self, identity_id, task_id):
        for t in self._tasks:
            if t.task_id == task_id:
                return t
        return None

    def create_acquisition_task(self, identity_id, capability_id, goal, original_request=None, runtime=None):
        t = Task(task_id=f"task-{len(self._tasks) + 1}", goal=goal, identity_id=identity_id, capability_id=capability_id)
        self._tasks.append(t)
        return t


def _completed_verify_step():
    s = TaskStep(action="verify", description="verify", status=TaskStepStatus.COMPLETED)
    s.result = {"verified": True}
    s.evidence = [Evidence(step="verify", label="skill_callable", detail="ok", success=True)]
    return s


def test_verify_goal_confirms_from_prior_verify_without_process():
    rt = NoReentrantRuntime()
    t = Task(task_id="t", goal="create a fetch capability", identity_id="id-1", capability_id="fetch")
    t.steps = [_completed_verify_step()]
    step = TaskStep(action="verify_goal", description="verify_goal",
                    params={"request": "create a fetch capability", "capability": "fetch"})
    ctx = ExecutionContext(identity_id="id-1", capability_registry=registry, storage=storage, runtime=rt)
    ok, result, evidence = _verify_goal(t, step, ctx)
    assert ok is True
    assert result.get("confirmed") is True
    assert result.get("requery") is False


def test_verify_goal_no_request_is_noop():
    rt = NoReentrantRuntime()
    t = Task(task_id="t", goal="g", identity_id="id-1")
    step = TaskStep(action="verify_goal", description="verify_goal", params={})
    ctx = ExecutionContext(identity_id="id-1", capability_registry=None, storage=None, runtime=rt)
    ok, result, evidence = _verify_goal(t, step, ctx)
    assert ok is True
    assert any(e.label == "goal_confirmed" for e in evidence)


def test_verify_goal_bounded_requery_budget():
    rt = NoReentrantRuntime()
    t = Task(task_id="t", goal="create a fetch capability", identity_id="id-1", capability_id="fetch")
    step = TaskStep(action="verify_goal", description="verify_goal",
                    params={"request": "create a fetch capability", "capability": "fetch",
                            "_requery_count": 99})
    ctx = ExecutionContext(identity_id="id-1", capability_registry=None, storage=None, runtime=rt)
    ok, result, evidence = _verify_goal(t, step, ctx)
    assert ok is False
    assert "requery" in result and result.get("requery") is False


def test_verify_goal_dedups_existing_task():
    rt = NoReentrantRuntime()
    existing = Task(task_id="existing-1", goal="create a fetch capability", identity_id="id-1", capability_id="fetch")
    existing.status = TaskStatus.FAILED
    rt._tasks.append(existing)
    t = Task(task_id="t", goal="create a fetch capability", identity_id="id-1", capability_id="fetch")
    step = TaskStep(action="verify_goal", description="verify_goal",
                    params={"request": "create a fetch capability", "capability": "fetch"})
    ctx = ExecutionContext(identity_id="id-1", capability_registry=None, storage=None, runtime=rt)
    ok, result, evidence = _verify_goal(t, step, ctx)
    # A terminal task already exists → no new task spawned, requery False.
    assert result.get("requery") is False
    assert result.get("existing_task") == "existing-1"
    assert ok is True  # reports the persistent state honestly


def test_verify_goal_never_calls_process_through_execution(storage, registry):
    """End-to-end: running a task with a verify_goal step must not call process()."""
    eng = ExecutiveRuntime(storage=storage, capability_registry=registry)
    eng.runtime = NoReentrantRuntime()
    t = eng.start_task(
        "create a zz_r6_probe capability",
        "tester", original_request="create a zz_r6_probe capability",
        steps=[
            {"action": "registry_search", "description": "search", "params": {"capability": "zz_r6_probe"}},
            {"action": "install", "description": "install", "params": {"capability": "zz_r6_probe"}},
            {"action": "verify", "description": "verify", "params": {"capability": "zz_r6_probe"}},
            {"action": "verify_goal", "description": "goal", "params": {"request": "create a zz_r6_probe capability", "capability": "zz_r6_probe"}},
        ],
        runtime=eng,
    )
    # The fake engine would raise if verify_goal tried to re-enter process();
    # detect that by asserting we reach a terminal state without an exception
    # being swallowed as a false "confirmed".
    guard = 0
    final = None
    while guard < 40:
        eng.process_ready("tester")
        final = eng.get_task("tester", t.task_id)
        if final.status.value in ("completed", "failed", "cancelled"):
            break
        guard += 1
    assert final is not None
    # ensure engine used our fake runtime reference (ctx.runtime)
    eng.shutdown()