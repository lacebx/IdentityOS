from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


class BenchmarkStorage:
    def __init__(self, root_dir: str = ".identitybench"):
        self.root = Path(root_dir)
        self.runs_dir = self.root / "runs"
        self.trends_dir = self.root / "trends"
        _ensure_dir(self.runs_dir)
        _ensure_dir(self.trends_dir)

    def save_run(self, identity_id: str, run_data: dict) -> str:
        identity_dir = self.runs_dir / identity_id
        _ensure_dir(identity_dir)
        timestamp = run_data.get("timestamp", datetime.now(timezone.utc).isoformat())
        safe_ts = timestamp.replace(":", "-").replace(".", "-")
        filename = f"{safe_ts}.json"
        filepath = identity_dir / filename
        with open(filepath, "w") as f:
            json.dump(run_data, f, indent=2, default=str)
        self._update_index(identity_id, timestamp, filename)
        return str(filepath)

    def _update_index(self, identity_id: str, timestamp: str, filename: str) -> None:
        index_path = self.root / "benchmark_index.json"
        index: Dict[str, list] = {}
        if index_path.exists():
            with open(index_path) as f:
                index = json.load(f)
        if identity_id not in index:
            index[identity_id] = []
        index[identity_id].append({"timestamp": timestamp, "filename": filename})
        index[identity_id] = sorted(
            index[identity_id], key=lambda x: x["timestamp"], reverse=True
        )
        with open(index_path, "w") as f:
            json.dump(index, f, indent=2)

    def load_run(self, identity_id: str, filename: str) -> Optional[dict]:
        filepath = self.runs_dir / identity_id / filename
        if filepath.exists():
            with open(filepath) as f:
                return json.load(f)
        return None

    def list_runs(self, identity_id: str) -> List[dict]:
        index_path = self.root / "benchmark_index.json"
        if index_path.exists():
            with open(index_path) as f:
                index = json.load(f)
            return index.get(identity_id, [])
        identity_dir = self.runs_dir / identity_id
        if identity_dir.exists():
            runs = []
            for fname in sorted(identity_dir.iterdir(), reverse=True):
                if fname.suffix == ".json":
                    runs.append({"timestamp": fname.stem, "filename": fname.name})
            return runs
        return []

    def load_latest_run(self, identity_id: str) -> Optional[dict]:
        runs = self.list_runs(identity_id)
        if not runs:
            return None
        return self.load_run(identity_id, runs[0]["filename"])

    def load_all_runs(self, identity_id: str) -> List[dict]:
        runs = []
        for entry in self.list_runs(identity_id):
            data = self.load_run(identity_id, entry["filename"])
            if data:
                runs.append(data)
        return runs

    def list_identities(self) -> List[str]:
        index_path = self.root / "benchmark_index.json"
        if index_path.exists():
            with open(index_path) as f:
                index = json.load(f)
            return list(index.keys())
        return [d.name for d in self.runs_dir.iterdir() if d.is_dir()]

    def save_trend(self, identity_id: str, trend_data: dict) -> None:
        filepath = self.trends_dir / f"{identity_id}.json"
        existing: dict = {"runs": []}
        if filepath.exists():
            with open(filepath) as f:
                existing = json.load(f)
        existing.setdefault("runs", []).append(trend_data)
        with open(filepath, "w") as f:
            json.dump(existing, f, indent=2)

    def load_trends(self, identity_id: str) -> List[dict]:
        filepath = self.trends_dir / f"{identity_id}.json"
        if filepath.exists():
            with open(filepath) as f:
                data = json.load(f)
            return data.get("runs", [])
        return []
