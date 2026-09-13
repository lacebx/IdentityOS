from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.prometheus.models import AcquisitionRecord


_LEARNING_NAMESPACE = "prometheus_learning"


def _empty_learning_data() -> Dict[str, Any]:
    return {
        "acquisitions": [],
        "capability_success": {},
        "task_capability_map": {},
    }


def _load_learning_data(identity_id: str, storage) -> Dict[str, Any]:
    load = getattr(storage, "load", None)
    if not callable(load):
        return _empty_learning_data()
    persisted = load(identity_id, _LEARNING_NAMESPACE)
    if not isinstance(persisted, dict):
        return _empty_learning_data()
    data = _empty_learning_data()
    for key in data:
        value = persisted.get(key)
        if isinstance(value, type(data[key])):
            data[key] = value
    return data


def _save_learning_data(identity_id: str, storage, data: dict) -> None:
    save = getattr(storage, "save", None)
    if callable(save):
        save(identity_id, _LEARNING_NAMESPACE, data)


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
