"""
core.executive — IdentityOS Executive Runtime.

A persistent, generic task engine that gives every identity an executive
brain: the ability to commit to goals, execute them step-by-step with
evidence, survive interruption, and truthfully report progress until
completion.

Design:
  models        — Task / TaskStep / Evidence data structures
  state         — strict task state machine (no silent abandonment)
  store         — durable task persistence per identity
  workflow      — generic capability-acquisition plan builder
  templates     — generic capability scaffold generator
  executor      — generic step execution with evidence
  verification  — evidence-producing capability verification
  progress      — real progress reporting from task state
  recovery      — interruption recovery / resume
  scheduler     — background execution so identities can chat while working
  engine        — ExecutiveRuntime facade
"""

from __future__ import annotations

from core.executive.engine import (
    ExecutiveRuntime,
    get_executive_for,
    register_executive,
)
from core.executive.models import Evidence, Task, TaskStatus, TaskStep, TaskStepStatus
from core.executive.state import IllegalTransition, can_transition, transition
from core.executive.store import TaskStore
from core.executive.progress import compute_progress, render_progress_block
from core.executive.workflow import build_acquisition_plan, extract_capability_name, is_acquisition_goal

__all__ = [
    "ExecutiveRuntime",
    "get_executive_for",
    "register_executive",
    "Task",
    "TaskStep",
    "TaskStatus",
    "TaskStepStatus",
    "Evidence",
    "TaskStore",
    "IllegalTransition",
    "can_transition",
    "transition",
    "compute_progress",
    "render_progress_block",
    "build_acquisition_plan",
    "extract_capability_name",
    "is_acquisition_goal",
]
