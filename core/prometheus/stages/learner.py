from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from core.prometheus.models import AcquisitionRecord


_LEARNING_NAMESPACE = "prometheus_learning"


def _storage_root(storage) -> Path:
    """Resolve a real filesystem root from storage, falling back to a temp dir.

    Real backends expose ``.root`` (a ``Path`` or ``str``).  Mock/test storages
    may expose a MagicMock ``.root`` that cannot be used as a path; in that
    case fall back to a temp dir instead of scattering files into the CWD.
    """
    raw = getattr(storage, "root", None)
    if isinstance(raw, (str, Path)):
        root = Path(raw)
        try:
            root.mkdir(parents=True, exist_ok=True)
            return root
        except OSError:
            pass
    fallback = Path(tempfile.mkdtemp(prefix="identityos_learning_"))
    return fallback


def _get_learning_path(identity_id: str, storage) -> Path:
    base = _storage_root(storage)
    path = base / identity_id / f"{_LEARNING_NAMESPACE}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _load_learning_data(identity_id: str, storage) -> Dict[str, Any]:
    path = _get_learning_path(identity_id, storage)
    if path.exists():
        try:
            with open(path) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {
        "acquisitions": [],
        "capability_success": {},
        "task_capability_map": {},
    }


def _save_learning_data(identity_id: str, storage, data: dict) -> None:
    path = _get_learning_path(identity_id, storage)
    try:
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    except IOError:
        pass


def record_acquisition(
    identity_id: str,
    record: AcquisitionRecord,
    storage,
) -> None:
    if not storage:
        return
    data = _load_learning_data(identity_id, storage)
    data["acquisitions"].append(record.to_dict())
    data["acquisitions"] = data["acquisitions"][-100:]

    cap_id = record.chosen_candidate.cap_id if record.chosen_candidate else "unknown"
    if cap_id not in data["capability_success"]:
        data["capability_success"][cap_id] = {"successes": 0, "failures": 0, "uses": 0}
    cs = data["capability_success"][cap_id]
    cs["uses"] += 1
    if record.installation_success and record.retry_success:
        cs["successes"] += 1
    else:
        cs["failures"] += 1

    for keyword in record.need.skill_keywords:
        if keyword not in data["task_capability_map"]:
            data["task_capability_map"][keyword] = {}
        tc = data["task_capability_map"][keyword]
        tc[cap_id] = tc.get(cap_id, 0) + 1

    _save_learning_data(identity_id, storage, data)


def get_success_rate(identity_id: str, cap_id: str, storage) -> float:
    data = _load_learning_data(identity_id, storage)
    cs = data.get("capability_success", {}).get(cap_id, {})
    total = cs.get("successes", 0) + cs.get("failures", 0)
    if total == 0:
        return 0.0
    return cs.get("successes", 0) / total


def get_known_capabilities_for_task(identity_id: str, task_keyword: str, storage) -> List[str]:
    data = _load_learning_data(identity_id, storage)
    tc = data.get("task_capability_map", {}).get(task_keyword, {})
    sorted_caps = sorted(tc.items(), key=lambda x: -x[1])
    return [cap_id for cap_id, _ in sorted_caps]


def has_previously_searched(identity_id: str, cap_id: str, storage) -> bool:
    data = _load_learning_data(identity_id, storage)
    for acq in data.get("acquisitions", []):
        if acq.get("chosen_candidate", {}).get("cap_id") == cap_id:
            return True
    return False


def learned_capabilities(identity_id: str, storage) -> List[str]:
    """Return the set of capabilities this identity has successfully learned.

    Order is stable: successful acquisitions first (by timestamp), then any
    `capability_success` keys not backed by an acquisition record.
    """
    data = _load_learning_data(identity_id, storage)
    learned: List[str] = []
    seen: Set[str] = set()
    for acq in data.get("acquisitions", []):
        if not acq.get("installation_success"):
            continue
        cap_id = (acq.get("chosen_candidate") or {}).get("cap_id")
        if cap_id and cap_id not in seen:
            seen.add(cap_id)
            learned.append(cap_id)
    for cap_id in data.get("capability_success", {}):
        if data["capability_success"][cap_id].get("successes", 0) > 0 and cap_id not in seen:
            seen.add(cap_id)
            learned.append(cap_id)
    return learned


def sync_learning_goal(identity_id: str, storage, goal_engine, learning_target: int = 5) -> bool:
    """Sync the identity's 'Learn and grow' goal with its acquired skills.

    Adds a milestone per distinct successfully-learned capability and
    recomputes goal progress (`milestones / learning_target`), so a goal that
    starts at 0% finally moves as the identity actually learns.

    Returns True when a matching goal was found and updated.
    """
    if goal_engine is None:
        return False
    learned = learned_capabilities(identity_id, storage)
    learned_set = set(learned)
    updated = False
    for goal in goal_engine.all():
        if goal.title.lower() != "learn and grow":
            continue
        milestone_descs = {m.description for m in goal.milestones}
        for cap_id in learned:
            if cap_id not in milestone_descs:
                goal.add_milestone(f"Acquire {cap_id}")
        if learning_target > 0:
            goal.progress = min(1.0, len(learned) / learning_target)
        goal.metadata["learned_capabilities"] = learned_set
        goal.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        updated = True
    return updated
