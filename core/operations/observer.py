"""
core/operations/observer.py

Project understanding for an operator identity.

The observer produces an evidence-backed :class:`ProjectState` from real,
inspectable artifacts (README, package metadata, docs, optional git history).
It never trusts a model's description of the project; every fact carries a
file path or command as evidence.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any, Callable, Optional

from .models import ProjectState, utcnow


class ProjectStateObserver:
    """Reads a project directory and summarizes it with verifiable evidence."""

    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root)

    # ── public API ────────────────────────────────────────────────────

    def observe(
        self,
        *,
        extra_facts: Optional[list[str]] = None,
        extra_evidence: Optional[list[str]] = None,
        evidence_provider: Optional[Callable[[], list[str]]] = None,
    ) -> ProjectState:
        facts: list[str] = []
        evidence: list[str] = []

        name = self._read_package_name()
        if name:
            facts.append(f"Project name: {name}")
            evidence.append("pyproject.toml / package metadata")

        readme = self._read_first("README.md", "README.rst", "readme.md")
        if readme:
            summary = self._summarize_text(readme)
            facts.append(f"README summary: {summary}")
            evidence.append("README.md")

        version = self._read_version()
        if version:
            facts.append(f"Declared version: {version}")
            evidence.append("pyproject.toml")

        docs = self._list_docs()
        if docs:
            facts.append(f"Documentation files: {', '.join(docs[:12])}")
            evidence.append("docs/")

        capabilities = self._list_capabilities()
        if capabilities:
            facts.append(f"Declared capabilities: {', '.join(capabilities[:20])}")
            evidence.append("registry/capabilities/index.json")

        tests = self._count_tests()
        if tests:
            facts.append(f"Test functions detected: {tests}")
            evidence.append("tests/")

        git_head = self._git_last_commit()
        if git_head:
            facts.append(f"Latest commit: {git_head}")
            evidence.append("git log -1")

        if extra_facts:
            facts.extend(extra_facts)
        if extra_evidence:
            evidence.extend(extra_evidence)
        if evidence_provider is not None:
            provided = evidence_provider() or []
            facts.extend(provided)
            evidence.extend(provided)

        return ProjectState(
            project_id=name or self.project_root.name,
            name=name or self.project_root.name,
            summary=facts[0] if facts else "",
            facts=facts,
            evidence=evidence,
            observed_at=utcnow().isoformat(),
        )

    # ── internals ─────────────────────────────────────────────────────

    def _read_first(self, *names: str) -> str:
        for name in names:
            path = self.project_root / name
            if path.is_file():
                try:
                    return path.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
        return ""

    def _read_package_name(self) -> str:
        data = self._read_pyproject()
        project = data.get("project", {}) if isinstance(data, dict) else {}
        return str(project.get("name", "") or "")

    def _read_version(self) -> str:
        data = self._read_pyproject()
        project = data.get("project", {}) if isinstance(data, dict) else {}
        return str(project.get("version", "") or "")

    def _read_pyproject(self) -> dict[str, Any]:
        text = self._read_first("pyproject.toml")
        if not text:
            return {}
        # Prefer a real TOML parser when available; fall back to a tiny regex.
        try:
            import tomllib  # type: ignore

            return tomllib.loads(text)
        except Exception:
            pass
        name = re.search(r'name\s*=\s*"([^"]+)"', text)
        version = re.search(r'version\s*=\s*"([^"]+)"', text)
        project: dict[str, Any] = {}
        if name:
            project["name"] = name.group(1)
        if version:
            project["version"] = version.group(1)
        return {"project": project} if project else {}

    def _summarize_text(self, text: str, limit: int = 400) -> str:
        lines = [ln.strip() for ln in text.splitlines()]
        # Drop the title line and badge-only lines.
        body = [
            ln for ln in lines
            if ln and not ln.startswith("#") and not ln.startswith("[!")
            and not ln.startswith("![")
        ]
        return " ".join(body)[:limit]

    def _list_docs(self) -> list[str]:
        docs_dir = self.project_root / "docs"
        if not docs_dir.is_dir():
            return []
        return sorted(p.name for p in docs_dir.iterdir() if p.is_file())

    def _list_capabilities(self) -> list[str]:
        index = self.project_root / "registry" / "capabilities" / "index.json"
        if not index.is_file():
            return []
        try:
            data = json.loads(index.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        entries = data if isinstance(data, list) else data.get("capabilities", [])
        names: list[str] = []
        for entry in entries:
            if isinstance(entry, dict) and entry.get("id"):
                names.append(str(entry["id"]))
        return names

    def _count_tests(self) -> int:
        tests_dir = self.project_root / "tests"
        if not tests_dir.is_dir():
            return 0
        count = 0
        for path in tests_dir.glob("test_*.py"):
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            count += len(re.findall(r"^\s*def test_", text, flags=re.MULTILINE))
        return count

    def _git_last_commit(self) -> str:
        git_dir = self.project_root / ".git"
        if not git_dir.exists():
            return ""
        try:
            result = subprocess.run(
                ["git", "log", "-1", "--pretty=%h %s"],
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (OSError, subprocess.SubprocessError):
            return ""
        return result.stdout.strip() if result.returncode == 0 else ""
