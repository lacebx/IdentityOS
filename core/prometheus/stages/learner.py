from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

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
