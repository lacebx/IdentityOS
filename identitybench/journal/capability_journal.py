from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


class CapabilityJournal:
    def __init__(self, root_dir: str = ".identitybench"):
        self.root = Path(root_dir) / "journals"
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, identity_id: str, cap_id: str) -> Path:
        safe = cap_id.replace("/", "_").replace("\\", "_")
        return self.root / identity_id / f"{safe}.json"

    def record_event(
        self,
        identity_id: str,
        cap_id: str,
        event_type: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        path = self._path(identity_id, cap_id)
        path.parent.mkdir(parents=True, exist_ok=True)

        journal: List[Dict[str, Any]] = []
        if path.exists():
            try:
                with open(path) as f:
                    journal = json.load(f)
            except (json.JSONDecodeError, IOError):
                journal = []

        from datetime import datetime, timezone
        entry = {
            "event_type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "details": details or {},
        }
        journal.append(entry)
        journal = journal[-500:]

        try:
            with open(path, "w") as f:
                json.dump(journal, f, indent=2)
        except IOError:
            pass

    def get_journal(self, identity_id: str, cap_id: str) -> List[Dict[str, Any]]:
        path = self._path(identity_id, cap_id)
        if not path.exists():
            return []
        try:
            with open(path) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []

    def list_capabilities(self, identity_id: str) -> List[str]:
        id_dir = self.root / identity_id
        if not id_dir.exists():
            return []
        return [p.stem for p in sorted(id_dir.iterdir()) if p.suffix == ".json"]

    def get_capability_summary(
        self,
        identity_id: str,
        cap_id: str,
    ) -> Optional[Dict[str, Any]]:
        journal = self.get_journal(identity_id, cap_id)
        if not journal:
            return None

        install_events = [e for e in journal if e.get("event_type") == "installation"]
        success_events = [e for e in journal if e.get("event_type") in ("SUCCEEDED", "retry_success")]
        failures = [e for e in journal if e.get("event_type") in ("FAILED", "ROLLED_BACK", "validation_failure")]

        confidence_trend: List[float] = []
        for e in journal:
            score = e.get("details", {}).get("trust_score") or e.get("details", {}).get("score")
            if score is not None:
                confidence_trend.append(float(score))

        return {
            "cap_id": cap_id,
            "total_events": len(journal),
            "installations": len(install_events),
            "successes": len(success_events),
            "failures": len(failures),
            "success_rate": round(
                len(success_events) / (len(success_events) + len(failures)) * 100, 1
            ) if (success_events or failures) else 0.0,
            "confidence_trend": confidence_trend[-20:] if confidence_trend else [],
            "latest_event": journal[-1] if journal else None,
            "first_event": journal[0] if journal else None,
        }

    def get_all_summaries(self, identity_id: str) -> List[Dict[str, Any]]:
        caps = self.list_capabilities(identity_id)
        summaries = []
        for cap_id in caps:
            summary = self.get_capability_summary(identity_id, cap_id)
            if summary:
                summaries.append(summary)
        return summaries
