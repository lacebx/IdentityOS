from __future__ import annotations

from core.prometheus.models import AcquisitionRecord


_EVIDENCE_NAMESPACE = "prometheus_evidence"


def record_evidence(
    identity_id: str,
    record: AcquisitionRecord,
    storage,
) -> None:
    load = getattr(storage, "load", None)
    save = getattr(storage, "save", None)
    if not callable(load) or not callable(save):
        return

    persisted = load(identity_id, _EVIDENCE_NAMESPACE)
    if isinstance(persisted, list):
        # Backward compatibility with the original direct JSON-file format.
        evidence = persisted
    elif isinstance(persisted, dict) and isinstance(persisted.get("entries"), list):
        evidence = persisted["entries"]
    else:
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
    save(identity_id, _EVIDENCE_NAMESPACE, {"entries": evidence})


def get_evidence_history(identity_id: str, storage) -> list:
    load = getattr(storage, "load", None)
    if not callable(load):
        return []
    persisted = load(identity_id, _EVIDENCE_NAMESPACE)
    if isinstance(persisted, list):
        return persisted
    if isinstance(persisted, dict) and isinstance(persisted.get("entries"), list):
        return persisted["entries"]
    return []
