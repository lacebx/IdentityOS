from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from core.prometheus.models import AcquisitionRecord


_EVIDENCE_NAMESPACE = "prometheus_evidence"


def _storage_root(storage) -> Optional[Path]:
    """Resolve a real filesystem root from storage, else None.

    Falls back to None (caller skips writing) when storage exposes only a
    MagicMock ``.root`` or no usable path, so evidence is never scattered into
    the current working directory.
    """
    raw = getattr(storage, "root", None)
    if isinstance(raw, (str, Path)):
        root = Path(raw)
        try:
            root.mkdir(parents=True, exist_ok=True)
            return root
        except OSError:
            return None
    return None


def _get_evidence_path(identity_id: str, storage) -> Optional[Path]:
    base = _storage_root(storage)
    if base is None:
        return None
    path = base / identity_id / f"{_EVIDENCE_NAMESPACE}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def record_evidence(
    identity_id: str,
    record: AcquisitionRecord,
    storage,
) -> None:
    path = _get_evidence_path(identity_id, storage)
    if not path:
        return

    evidence = []
    if path.exists():
        try:
            with open(path) as f:
                evidence = json.load(f)
        except (json.JSONDecodeError, IOError):
            evidence = []

    entry = {
        "timestamp": record.timestamp,
        "need": record.need.to_dict(),
        "candidates_found": len(record.candidates_found),
        "chosen_capability": record.chosen_candidate.cap_id if record.chosen_candidate else None,
        "chosen_author": record.chosen_candidate.author if record.chosen_candidate else None,
        "chosen_version": record.chosen_candidate.version if record.chosen_candidate else None,
        "trust_score": record.trust_score,
        "relevance_score": record.chosen_candidate.relevance_score if record.chosen_candidate else 0,
        "installation_success": record.installation_success,
        "validation_success": record.validation_success,
        "retry_success": record.retry_success,
        "performance_gain": record.performance_gain,
        "duration_ms": record.duration_ms,
        "status": record.status.value,
        "mode": record.mode.value,
        "error": record.error,
    }
    evidence.append(entry)
    evidence = evidence[-200:]

    try:
        with open(path, "w") as f:
            json.dump(evidence, f, indent=2)
    except IOError:
        pass


def get_evidence_history(identity_id: str, storage) -> list:
    path = _get_evidence_path(identity_id, storage)
    if not path or not path.exists():
        return []
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []
