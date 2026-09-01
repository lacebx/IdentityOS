from __future__ import annotations

import ast
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.capabilities.base import Capability, Skill, object_schema
from core.capabilities.registry import register
from core.capabilities.result import CapabilityResult

from .thinking_engine import ThinkingEngine, Thought, load_memory, save_memory, record_recommendation, record_pr_review, summarize_recommendation_follow_through  # noqa: F401


DAEDALUS_VERSION = "1.0.0"
DAEDALUS_AUTHOR = "Daedalus"


# =========================================================================
# Architecture Analysis Capability
# =========================================================================

_ARCHITECTURE_LAYERS = {
    "runtime": "runtime/",
    "prometheus": "core/prometheus/",
    "identitybench": "identitybench/",
    "atlas": "identitybench/atlas/",
    "core": "core/",
    "cli": "cli/",
    "registry": "registry/",
}

_IMPORT_PATTERNS = [
    ("runtime/", "runtime/", "Runtime imports another runtime module"),
]


@register
class ArchitectureAnalysisCapability(Capability):
    id = "architecture_analysis"
    name = "Architecture Analysis"
    version = DAEDALUS_VERSION
    author = DAEDALUS_AUTHOR
    license = "MIT"
    homepage = "https://github.com/lacebx/IdentityOS"
    description = "Analyze codebase architecture, detect coupling, evaluate layer separation, identify weaknesses"
    permissions = ["public"]

    def install(self, identity_id: str, storage: Any) -> None:
        storage.save(identity_id, "capability.architecture_analysis", {"installed_at": None})

    def uninstall(self, identity_id: str, storage: Any) -> None:
        storage.delete(identity_id, "capability.architecture_analysis")

    def prompts(self, identity_id: str) -> list[str]:
        return [
            "## Architecture Analysis Skills",
            "You can analyze code architecture, detect coupling, evaluate layer separation, and produce reports.",
            "Use these skills when asked about architecture quality or codebase structure.",
        ]

    _SKILLS = [
        Skill(name="architecture_analysis.analyze_module", description="Analyze a specific module or package for architectural health", permission="public", input_schema=object_schema({"module_name": {"type": "string"}}), verification_params={"module_name": "core/capabilities/base.py"}),
        Skill(name="architecture_analysis.detect_coupling", description="Detect tight coupling between layers or modules", permission="public", input_schema=object_schema(), verification_params={}),
        Skill(name="architecture_analysis.evaluate_separation", description="Evaluate whether layers are properly separated with clean interfaces", permission="public", input_schema=object_schema(), verification_params={}),
        Skill(name="architecture_analysis.identify_weaknesses", description="Identify architectural weaknesses with evidence and recommended improvements", permission="public", input_schema=object_schema(), verification_params={}),
        Skill(name="architecture_analysis.produce_report", description="Produce comprehensive architecture health report", permission="public", input_schema=object_schema(), verification_params={}),
    ]

    def skills(self) -> list[Skill]:
        return list(self._SKILLS)

    def call(self, skill_name: str, **params: Any) -> CapabilityResult:
        t0 = time.monotonic()
        try:
            dispatch = {
                "architecture_analysis.analyze_module": self._analyze_module,
                "architecture_analysis.detect_coupling": self._detect_coupling,
                "architecture_analysis.evaluate_separation": self._evaluate_separation,
                "architecture_analysis.identify_weaknesses": self._identify_weaknesses,
                "architecture_analysis.produce_report": self._produce_report,
            }
            handler = dispatch.get(skill_name)
            if handler is None:
                return CapabilityResult.fail("architecture_analysis", skill_name, "unknown_skill", f"Unknown skill: {skill_name}")
            data = handler(**params)
            return CapabilityResult.from_data("architecture_analysis", skill_name, data, source="local analysis", duration_ms=(time.monotonic() - t0) * 1000)
        except Exception as e:
            return CapabilityResult.fail("architecture_analysis", skill_name, type(e).__name__, str(e), duration_ms=(time.monotonic() - t0) * 1000)

    def _find_module_path(self, module_name: str) -> Optional[Path]:
        base = Path(os.getcwd())
        candidates = [
            base / module_name,
            base / module_name.replace(".", "/"),
            base / "core" / module_name.replace(".", "/"),
            base / "identitybench" / module_name.replace(".", "/"),
            base / "runtime" / module_name.replace(".", "/"),
        ]
        for c in candidates:
            if c.exists() and (c.is_dir() or c.suffix == ".py"):
                return c
        return None

    def _analyze_module(self, module_name: str = "", **kwargs: Any) -> Dict[str, Any]:
        path = self._find_module_path(module_name) if module_name else Path(".")
        if not path:
            return {"error": f"Module '{module_name}' not found", "module": module_name}
        files = list(path.rglob("*.py")) if path.is_dir() else [path]
        total_lines = 0
        class_count = 0
        func_count = 0
        imports: List[str] = []
        for f in files:
            try:
                text = f.read_text()
                total_lines += len(text.splitlines())
                tree = ast.parse(text)
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        class_count += 1
                    elif isinstance(node, ast.FunctionDef):
                        func_count += 1
                    elif isinstance(node, (ast.Import, ast.ImportFrom)):
                        for alias in node.names:
                            imports.append(alias.name)
            except Exception:
                pass
        return {
            "module": str(path),
            "files": len(files),
            "total_lines": total_lines,
            "classes": class_count,
            "functions": func_count,
            "unique_imports": len(set(imports)),
            "imports": sorted(set(imports))[:20],
        }

    def _detect_coupling(self, **kwargs: Any) -> Dict[str, Any]:
        base = Path(os.getcwd())
        findings: List[Dict[str, Any]] = []
        for f in base.rglob("*.py"):
            if ".venv" in str(f) or "__pycache__" in str(f):
                continue
            try:
                text = f.read_text()
                tree = ast.parse(text)
                relative = f.relative_to(base)
                for node in ast.walk(tree):
                    if isinstance(node, ast.ImportFrom):
                        if node.module and ".." in str(relative):
                            findings.append({
                                "file": str(relative),
                                "type": "relative_import",
                                "target": node.module,
                                "line": node.lineno,
                            })
                        if node.module and "runtime" in str(relative) and "core" in node.module:
                            findings.append({
                                "file": str(relative),
                                "type": "cross_layer_import",
                                "target": node.module,
                                "line": node.lineno,
                            })
            except Exception:
                pass
        return {
            "total_findings": len(findings),
            "coupling_issues": findings[:20],
            "recommendation": "Review cross-layer imports and consider interface abstractions",
        }

    def _evaluate_separation(self, **kwargs: Any) -> Dict[str, Any]:
        base = Path(os.getcwd())
        layer_files: Dict[str, int] = {}
        for name, prefix in _ARCHITECTURE_LAYERS.items():
            path = base / prefix
            if path.exists():
                count = len(list(path.rglob("*.py")))
                layer_files[name] = count
        cross_imports: List[str] = []
        for f in base.rglob("*.py"):
            if ".venv" in str(f) or "__pycache__" in str(f):
                continue
            try:
                text = f.read_text()
                relative = f.relative_to(base)
                for name, prefix in _ARCHITECTURE_LAYERS.items():
                    if str(relative).startswith(prefix):
                        for other_name, other_prefix in _ARCHITECTURE_LAYERS.items():
                            if name == other_name:
                                continue
                            if other_prefix.replace("/", ".") in text or other_prefix in text:
                                if f"from {other_prefix.replace('/', '.')}" in text or f"import {other_prefix.replace('/', '.')}" in text:
                                    cross_imports.append(f"{relative} imports from {other_name}")
            except Exception:
                pass
        return {
            "layer_file_counts": layer_files,
            "cross_layer_imports": cross_imports[:15],
            "total_cross_imports": len(cross_imports),
            "separation_verdict": "adequate" if len(cross_imports) < 10 else "needs improvement",
        }

    def _identify_weaknesses(self, **kwargs: Any) -> Dict[str, Any]:
        base = Path(os.getcwd())
        weaknesses: List[Dict[str, Any]] = []
        for f in base.rglob("*.py"):
            if ".venv" in str(f) or "__pycache__" in str(f) or "site-packages" in str(f):
                continue
            try:
                relative = f.relative_to(base)
                text = f.read_text()
                if "pass" in text and "TODO" not in text and "def " not in text:
                    continue
                if "noqa" in text and "FIXME" not in text:
                    continue
                if "TODO" in text or "FIXME" in text or "HACK" in text:
                    weaknesses.append({
                        "file": str(relative),
                        "type": "todo_or_fixme",
                        "count": text.count("TODO") + text.count("FIXME") + text.count("HACK"),
                    })
            except Exception:
                pass
        return {
            "total_weaknesses": len(weaknesses),
            "items": sorted(weaknesses, key=lambda x: -x["count"])[:20],
            "recommendation": "Address TODO/FIXME items before major refactoring",
        }

    def _produce_report(self, **kwargs: Any) -> Dict[str, Any]:
        module_analysis = self._analyze_module()
        coupling = self._detect_coupling()
        separation = self._evaluate_separation()
        weaknesses = self._identify_weaknesses()
        return {
            "summary": f"Module analysis: {module_analysis['files']} files, {module_analysis['total_lines']} lines. "
                       f"Coupling issues: {coupling['total_findings']}. "
                       f"Cross-layer imports: {separation['total_cross_imports']}. "
                       f"TODOs/FIXMEs: {weaknesses['total_weaknesses']}.",
            "module_analysis": module_analysis,
            "coupling": coupling,
            "layer_separation": separation,
            "weaknesses": weaknesses,
        }


# =========================================================================
# Code Review Capability
# =========================================================================

@register
class CodeReviewCapability(Capability):
    id = "code_review"
    name = "Code Review"
    version = DAEDALUS_VERSION
    author = DAEDALUS_AUTHOR
    license = "MIT"
    homepage = "https://github.com/lacebx/IdentityOS"
    description = "Review PRs with architectural perspective, detect regressions, verify separation, assess readiness"
    permissions = ["public"]

    def install(self, identity_id: str, storage: Any) -> None:
        storage.save(identity_id, "capability.code_review", {"installed_at": None})

    def uninstall(self, identity_id: str, storage: Any) -> None:
        storage.delete(identity_id, "capability.code_review")

    def prompts(self, identity_id: str) -> list[str]:
        return [
            "## Code Review Skills",
            "You can review pull requests, check for regressions, verify layer separation, detect technical debt, and assess merge readiness.",
            "Use these skills when asked to review code changes or assess PR quality.",
        ]

    _SKILLS = [
        Skill(name="code_review.review_pr", description="Review a pull request with architectural perspective", permission="public", input_schema=object_schema({"diff_path": {"type": "string"}, "title": {"type": "string"}}), verification_params={}),
        Skill(name="code_review.check_regressions", description="Check for benchmark regressions in a change", permission="public", input_schema=object_schema()),
        Skill(name="code_review.verify_separation", description="Verify layer separation is maintained after a change", permission="public", input_schema=object_schema({"diff_path": {"type": "string"}}), verification_params={}),
        Skill(name="code_review.detect_technical_debt", description="Detect technical debt introduced or addressed by a change", permission="public", input_schema=object_schema({"diff_path": {"type": "string"}}), verification_params={}),
        Skill(name="code_review.assess_readiness", description="Assess whether a PR is ready for merge or needs changes", permission="public", input_schema=object_schema({"diff_path": {"type": "string"}}), verification_params={}),
    ]

    def skills(self) -> list[Skill]:
        return list(self._SKILLS)

    def call(self, skill_name: str, **params: Any) -> CapabilityResult:
        t0 = time.monotonic()
        try:
            dispatch = {
                "code_review.review_pr": self._review_pr,
                "code_review.check_regressions": self._check_regressions,
                "code_review.verify_separation": self._verify_separation,
                "code_review.detect_technical_debt": self._detect_technical_debt,
                "code_review.assess_readiness": self._assess_readiness,
            }
            handler = dispatch.get(skill_name)
            if handler is None:
                return CapabilityResult.fail("code_review", skill_name, "unknown_skill", f"Unknown skill: {skill_name}")
            data = handler(**params)
            return CapabilityResult.from_data("code_review", skill_name, data, source="local analysis", duration_ms=(time.monotonic() - t0) * 1000)
        except Exception as e:
            return CapabilityResult.fail("code_review", skill_name, type(e).__name__, str(e), duration_ms=(time.monotonic() - t0) * 1000)

    def _review_pr(self, diff_path: str = "", title: str = "", **kwargs: Any) -> Dict[str, Any]:
        base = Path(os.getcwd())
        if diff_path and Path(diff_path).exists():
            diff_text = Path(diff_path).read_text()
        else:
            diff_text = ""
        changes = {
            "files_changed": 0,
            "additions": 0,
            "deletions": 0,
        }
        if diff_text:
            for line in diff_text.splitlines():
                if line.startswith("--- a/") or line.startswith("+++ b/"):
                    changes["files_changed"] += 1
                elif line.startswith("+"):
                    changes["additions"] += 1
                elif line.startswith("-"):
                    changes["deletions"] += 1
        return {
            "title": title,
            "diff_stats": changes,
            "review_notes": [
                "Review each file for architectural consistency",
                "Ensure separation of concerns is maintained",
                "Check for appropriate test coverage",
                "Verify no breaking changes to public interfaces",
            ],
            "verdict": "pending",
        }

    def _check_regressions(self, **kwargs: Any) -> Dict[str, Any]:
        bench_dir = Path(".identitybench")
        if not bench_dir.exists():
            return {"error": "No benchmark data found", "regressions": []}
        return {
            "regressions": [],
            "benchmark_status": "No benchmark data to compare against",
        }

    def _verify_separation(self, diff_path: str = "", **kwargs: Any) -> Dict[str, Any]:
        forbidden_patterns = [
            ("identitybench/atlas/", "runtime/", "Atlas must not import Runtime internals"),
            ("identitybench/", "core/prometheus/", "IdentityBench must not import Prometheus"),
            ("core/prometheus/", "identitybench/atlas/", "Prometheus must not depend on Atlas"),
        ]
        violations = []
        diff_text = Path(diff_path).read_text() if diff_path and Path(diff_path).exists() else ""
        for src, forbidden, msg in forbidden_patterns:
            if f"+from {forbidden.replace('/', '.')}" in diff_text or f"+import {forbidden.replace('/', '.')}" in diff_text:
                for line in diff_text.splitlines():
                    if line.startswith("+") and (f"from {forbidden.replace('/', '.')}" in line or f"import {forbidden.replace('/', '.')}" in line):
                        violations.append({"message": msg, "line": line})
        return {
            "violations": violations,
            "verdict": "violations found" if violations else "clean",
        }

    def _detect_technical_debt(self, diff_path: str = "", **kwargs: Any) -> Dict[str, Any]:
        findings = []
        diff_text = Path(diff_path).read_text() if diff_path and Path(diff_path).exists() else ""
        debt_markers = ["TODO", "FIXME", "HACK", "XXX", "TEMP", "workaround", "hack"]
        for line in diff_text.splitlines():
            if line.startswith("+"):
                for marker in debt_markers:
                    if marker in line.upper():
                        findings.append({
                            "type": marker.upper(),
                            "line": line.strip(),
                        })
                        break
        return {
            "technical_debt_introduced": len(findings),
            "items": findings[:10],
            "recommendation": "Address technical debt markers before merging" if findings else "No new technical debt introduced",
        }

    def _assess_readiness(self, diff_path: str = "", **kwargs: Any) -> Dict[str, Any]:
        separation = self._verify_separation(diff_path=diff_path)
        debt = self._detect_technical_debt(diff_path=diff_path)
        issues = []
        if separation.get("violations"):
            issues.extend(separation["violations"])
        if debt.get("technical_debt_introduced", 0) > 0:
            issues.append(f"{debt['technical_debt_introduced']} technical debt marker(s) introduced")
        return {
            "ready": len(issues) == 0,
            "blockers": [i["message"] if isinstance(i, dict) else i for i in issues],
            "readiness_verdict": "READY" if len(issues) == 0 else "NEEDS_WORK",
        }


# =========================================================================
# Changelog Generator Capability
# =========================================================================

@register
class ChangelogGenCapability(Capability):
    id = "changelog_gen"
    name = "Changelog Generator"
    version = DAEDALUS_VERSION
    author = DAEDALUS_AUTHOR
    license = "MIT"
    homepage = "https://github.com/lacebx/IdentityOS"
    description = "Generate structured changelogs from git history, detect breaking changes, format releases"
    permissions = ["public"]

    def install(self, identity_id: str, storage: Any) -> None:
        storage.save(identity_id, "capability.changelog_gen", {"installed_at": None})

    def uninstall(self, identity_id: str, storage: Any) -> None:
        storage.delete(identity_id, "capability.changelog_gen")

    def prompts(self, identity_id: str) -> list[str]:
        return [
            "## Changelog Generator Skills",
            "You can generate changelogs from git history, detect breaking changes, categorize commits, and format releases.",
            "Use these skills when asked to generate release notes or changelogs.",
        ]

    _SKILLS = [
        Skill(name="changelog_gen.generate", description="Generate changelog from git history between two refs", permission="public", input_schema=object_schema({"from_ref": {"type": "string"}, "to_ref": {"type": "string"}}), verification_params={"from_ref": "HEAD", "to_ref": "HEAD"}),
        Skill(name="changelog_gen.detect_breaking", description="Detect breaking changes from commit history", permission="public", input_schema=object_schema({"from_ref": {"type": "string"}, "to_ref": {"type": "string"}}), verification_params={"from_ref": "HEAD", "to_ref": "HEAD"}),
        Skill(name="changelog_gen.categorize", description="Categorize changes by type (feat, fix, refactor, etc.)", permission="public", input_schema=object_schema({"from_ref": {"type": "string"}, "to_ref": {"type": "string"}}), verification_params={"from_ref": "HEAD", "to_ref": "HEAD"}),
        Skill(name="changelog_gen.format_release", description="Format changelog for a specific release version", permission="public", input_schema=object_schema({"version": {"type": "string"}, "from_ref": {"type": "string"}, "to_ref": {"type": "string"}}), verification_params={"version": "0.0.0", "from_ref": "HEAD", "to_ref": "HEAD"}),
    ]

    def skills(self) -> list[Skill]:
        return list(self._SKILLS)

    def call(self, skill_name: str, **params: Any) -> CapabilityResult:
        t0 = time.monotonic()
        try:
            dispatch = {
                "changelog_gen.generate": self._generate,
                "changelog_gen.detect_breaking": self._detect_breaking,
                "changelog_gen.categorize": self._categorize,
                "changelog_gen.format_release": self._format_release,
            }
            handler = dispatch.get(skill_name)
            if handler is None:
                return CapabilityResult.fail("changelog_gen", skill_name, "unknown_skill", f"Unknown skill: {skill_name}")
            data = handler(**params)
            return CapabilityResult.from_data("changelog_gen", skill_name, data, source="git history", duration_ms=(time.monotonic() - t0) * 1000)
        except Exception as e:
            return CapabilityResult.fail("changelog_gen", skill_name, type(e).__name__, str(e), duration_ms=(time.monotonic() - t0) * 1000)

    def _run_git(self, cmd: List[str]) -> str:
        try:
            return subprocess.check_output(["git"] + cmd, stderr=subprocess.STDOUT, text=True).strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            return ""

    def _generate(self, from_ref: str = "HEAD~10", to_ref: str = "HEAD", **kwargs: Any) -> Dict[str, Any]:
        log = self._run_git(["log", f"{from_ref}..{to_ref}", "--oneline", "--no-decorate"])
        commits = [l.strip() for l in log.split("\n") if l.strip()] if log else []
        return {"from": from_ref, "to": to_ref, "commits": commits[:50], "total": len(commits)}

    def _detect_breaking(self, from_ref: str = "HEAD~10", to_ref: str = "HEAD", **kwargs: Any) -> Dict[str, Any]:
        log = self._run_git(["log", f"{from_ref}..{to_ref}", "--oneline", "--no-decorate"])
        breaking = []
        for line in log.split("\n"):
            if any(marker in line.lower() for marker in ["breaking", "breaking change", "!"]) or "!" in line[:60]:
                breaking.append(line.strip())
        return {"breaking_changes": breaking, "total": len(breaking)}

    def _categorize(self, from_ref: str = "HEAD~10", to_ref: str = "HEAD", **kwargs: Any) -> Dict[str, List[str]]:
        log = self._run_git(["log", f"{from_ref}..{to_ref}", "--oneline", "--no-decorate"])
        categories: Dict[str, List[str]] = {"feat": [], "fix": [], "refactor": [], "docs": [], "test": [], "chore": [], "other": []}
        for line in log.split("\n"):
            line = line.strip()
            if not line:
                continue
            found = False
            for prefix in ["feat", "fix", "refactor", "docs", "test", "chore"]:
                if line.lower().startswith(prefix):
                    categories[prefix].append(line)
                    found = True
                    break
            if not found:
                categories["other"].append(line)
        return categories

    def _format_release(self, version: str = "0.0.0", from_ref: str = "HEAD~10", to_ref: str = "HEAD", **kwargs: Any) -> str:
        cats = self._categorize(from_ref=from_ref, to_ref=to_ref)
        lines = [f"## [{version}]", ""]
        for category, commits in cats.items():
            if commits:
                lines.append(f"### {category.capitalize()}")
                for c in commits:
                    lines.append(f"- {c}")
                lines.append("")
        return "\n".join(lines)


# =========================================================================
# Repository Health Capability
# =========================================================================

@register
class RepoHealthCapability(Capability):
    id = "repo_health"
    name = "Repository Health"
    version = DAEDALUS_VERSION
    author = DAEDALUS_AUTHOR
    license = "MIT"
    homepage = "https://github.com/lacebx/IdentityOS"
    description = "Assess code quality, test health, documentation freshness, benchmark trends, produce reports"
    permissions = ["public"]

    def install(self, identity_id: str, storage: Any) -> None:
        storage.save(identity_id, "capability.repo_health", {"installed_at": None})

    def uninstall(self, identity_id: str, storage: Any) -> None:
        storage.delete(identity_id, "capability.repo_health")

    def prompts(self, identity_id: str) -> list[str]:
        return [
            "## Repository Health Skills",
            "You can assess code quality, test health, documentation freshness, benchmark trends, and produce comprehensive health reports.",
            "Use these skills when asked about repository quality or health status.",
        ]

    _SKILLS = [
        Skill(name="repo_health.assess_code_quality", description="Assess code quality metrics from repository analysis", permission="public", input_schema=object_schema(), verification_params={}),
        Skill(name="repo_health.check_test_health", description="Analyze test coverage and test reliability", permission="public", input_schema=object_schema(), verification_params={}),
        Skill(name="repo_health.evaluate_documentation", description="Evaluate documentation freshness and completeness", permission="public", input_schema=object_schema(), verification_params={}),
        Skill(name="repo_health.analyze_benchmark_trend", description="Analyze IdentityBench benchmark trends over time", permission="public", input_schema=object_schema()),
        Skill(name="repo_health.produce_report", description="Produce comprehensive repository health report", permission="public", input_schema=object_schema()),
    ]

    def skills(self) -> list[Skill]:
        return list(self._SKILLS)

    def call(self, skill_name: str, **params: Any) -> CapabilityResult:
        t0 = time.monotonic()
        try:
            dispatch = {
                "repo_health.assess_code_quality": self._assess_code_quality,
                "repo_health.check_test_health": self._check_test_health,
                "repo_health.evaluate_documentation": self._evaluate_documentation,
                "repo_health.analyze_benchmark_trend": self._analyze_benchmark_trend,
                "repo_health.produce_report": self._produce_report,
            }
            handler = dispatch.get(skill_name)
            if handler is None:
                return CapabilityResult.fail("repo_health", skill_name, "unknown_skill", f"Unknown skill: {skill_name}")
            data = handler(**params)
            return CapabilityResult.from_data("repo_health", skill_name, data, source="local analysis", duration_ms=(time.monotonic() - t0) * 1000)
        except Exception as e:
            return CapabilityResult.fail("repo_health", skill_name, type(e).__name__, str(e), duration_ms=(time.monotonic() - t0) * 1000)

    def _assess_code_quality(self, **kwargs: Any) -> Dict[str, Any]:
        base = Path(os.getcwd())
        py_files = list(base.rglob("*.py"))
        total = len(py_files)
        total_lines = 0
        has_docstring = 0
        for f in py_files:
            if ".venv" in str(f) or "__pycache__" in str(f):
                continue
            try:
                text = f.read_text()
                total_lines += len(text.splitlines())
                tree = ast.parse(text)
                for node in ast.iter_child_nodes(tree):
                    if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
                        if ast.get_docstring(node):
                            has_docstring += 1
            except Exception:
                pass
        return {
            "python_files": total,
            "total_lines": total_lines,
            "docstring_coverage": round(has_docstring / max(total, 1) * 100, 1),
            "quality_verdict": "good" if has_docstring > total * 0.3 else "needs improvement",
        }

    def _check_test_health(self, **kwargs: Any) -> Dict[str, Any]:
        base = Path(os.getcwd())
        test_files = list(base.rglob("tests/test_*.py"))
        source_files = list(base.rglob("*.py"))
        source_excluding_tests = [f for f in source_files if "tests/" not in str(f) and ".venv" not in str(f)]
        return {
            "test_files": len(test_files),
            "source_files": len(source_excluding_tests),
            "test_ratio": round(len(test_files) / max(len(source_excluding_tests), 1), 2),
        }

    def _evaluate_documentation(self, **kwargs: Any) -> Dict[str, Any]:
        base = Path(os.getcwd())
        doc_files = list(base.rglob("*.md"))
        docs_dir = base / "docs"
        arch_docs = list(docs_dir.rglob("*.md")) if docs_dir.exists() else []
        return {
            "total_markdown_files": len(doc_files),
            "architecture_docs": len(arch_docs),
            "readme_exists": (base / "README.md").exists(),
        }

    def _analyze_benchmark_trend(self, **kwargs: Any) -> Dict[str, Any]:
        bench_dir = Path(".identitybench")
        if not bench_dir.exists():
            return {"error": "No benchmark data found", "status": "no_data"}
        trend_files = list(bench_dir.rglob("*trend*"))
        return {
            "trend_files_found": len(trend_files),
            "status": "available" if trend_files else "no_trend_data",
        }

    def _produce_report(self, **kwargs: Any) -> Dict[str, Any]:
        code = self._assess_code_quality()
        tests = self._check_test_health()
        docs = self._evaluate_documentation()
        bench = self._analyze_benchmark_trend()
        return {"code_quality": code, "test_health": tests, "documentation": docs, "benchmark_trends": bench}


# =========================================================================
# Dependency Graph Capability
# =========================================================================

@register
class DependencyGraphCapability(Capability):
    id = "dependency_graph"
    name = "Dependency Graph"
    version = DAEDALUS_VERSION
    author = DAEDALUS_AUTHOR
    license = "MIT"
    homepage = "https://github.com/lacebx/IdentityOS"
    description = "Analyze module dependencies, detect circular deps, map capability network, visualize graphs"
    permissions = ["public"]

    def install(self, identity_id: str, storage: Any) -> None:
        storage.save(identity_id, "capability.dependency_graph", {"installed_at": None})

    def uninstall(self, identity_id: str, storage: Any) -> None:
        storage.delete(identity_id, "capability.dependency_graph")

    def prompts(self, identity_id: str) -> list[str]:
        return [
            "## Dependency Graph Skills",
            "You can analyze module dependencies, detect circular dependencies, map capability networks, and generate visualizations.",
            "Use these skills when asked about dependency structure or module relationships.",
        ]

    _SKILLS = [
        Skill(name="dependency_graph.analyze_module_deps", description="Analyze import dependencies for a specific module", permission="public", input_schema=object_schema({"module_path": {"type": "string"}}), verification_params={"module_path": "core/capabilities/base.py"}),
        Skill(name="dependency_graph.detect_cycles", description="Detect circular dependencies in the codebase", permission="public", input_schema=object_schema(), verification_params={}),
        Skill(name="dependency_graph.map_capability_deps", description="Map dependencies between capabilities", permission="public", input_schema=object_schema(), verification_params={}),
        Skill(name="dependency_graph.visualize", description="Generate dependency graph visualization", permission="public", input_schema=object_schema({"format": {"type": "string", "enum": ["text"]}}), verification_params={"format": "text"}),
    ]

    def skills(self) -> list[Skill]:
        return list(self._SKILLS)

    def call(self, skill_name: str, **params: Any) -> CapabilityResult:
        t0 = time.monotonic()
        try:
            dispatch = {
                "dependency_graph.analyze_module_deps": self._analyze_module_deps,
                "dependency_graph.detect_cycles": self._detect_cycles,
                "dependency_graph.map_capability_deps": self._map_capability_deps,
                "dependency_graph.visualize": self._visualize,
            }
            handler = dispatch.get(skill_name)
            if handler is None:
                return CapabilityResult.fail("dependency_graph", skill_name, "unknown_skill", f"Unknown skill: {skill_name}")
            data = handler(**params)
            return CapabilityResult.from_data("dependency_graph", skill_name, data, source="static analysis", duration_ms=(time.monotonic() - t0) * 1000)
        except Exception as e:
            return CapabilityResult.fail("dependency_graph", skill_name, type(e).__name__, str(e), duration_ms=(time.monotonic() - t0) * 1000)

    def _analyze_module_deps(self, module_path: str = "", **kwargs: Any) -> Dict[str, Any]:
        base = Path(os.getcwd())
        target = Path(module_path) if module_path else base
        if not target.exists():
            return {"error": f"Path '{module_path}' not found"}
        imports: Dict[str, List[str]] = {}
        for f in (target.rglob("*.py") if target.is_dir() else [target]):
            if ".venv" in str(f) or "__pycache__" in str(f):
                continue
            try:
                text = f.read_text()
                tree = ast.parse(text)
                for node in ast.walk(tree):
                    if isinstance(node, ast.ImportFrom):
                        if node.module:
                            for alias in node.names:
                                imports.setdefault(str(f.relative_to(base)), []).append(f"{node.module}.{alias.name}")
                    elif isinstance(node, ast.Import):
                        for alias in node.names:
                            imports.setdefault(str(f.relative_to(base)), []).append(alias.name)
            except Exception:
                pass
        return {"files": len(imports), "dependencies": imports}

    def _detect_cycles(self, **kwargs: Any) -> Dict[str, Any]:
        deps = self._analyze_module_deps()
        cycles = []
        files = list(deps.get("dependencies", {}).keys())
        for f1 in files:
            for f2 in files:
                if f1 == f2:
                    continue
                f1_deps = deps["dependencies"].get(f1, [])
                f2_deps = deps["dependencies"].get(f2, [])
                for dep in f1_deps:
                    if f2.replace(".py", "").replace("/", ".") in dep:
                        for dep2 in f2_deps:
                            if f1.replace(".py", "").replace("/", ".") in dep2:
                                cycles.append({"a": f1, "b": f2})
        return {"cycles_found": len(cycles), "cycles": cycles[:10], "recommendation": "Review circular dependencies and consider interface extraction"}

    def _map_capability_deps(self, **kwargs: Any) -> Dict[str, Any]:
        registry_path = Path("registry/capabilities")
        if not registry_path.exists():
            return {"error": "Registry path not found"}
        caps = {}
        for cap_dir in registry_path.iterdir():
            manifest_path = cap_dir / "manifest.json"
            if manifest_path.exists():
                try:
                    data = json.loads(manifest_path.read_text())
                    caps[data["id"]] = {
                        "name": data.get("name", ""),
                        "skills": len(data.get("skills", [])),
                        "permissions": data.get("permissions", {}),
                    }
                except Exception:
                    pass
        return {"capabilities": caps, "total": len(caps)}

    def _visualize(self, format: str = "text", **kwargs: Any) -> str:
        deps = self._map_capability_deps()
        caps = deps.get("capabilities", {})
        if not caps:
            return "No capabilities found in registry."
        lines = ["Capability Dependency Map", "=" * 40, ""]
        for cap_id, info in sorted(caps.items()):
            lines.append(f"  {cap_id:25s}  {info['name'][:30]:30s}  {info['skills']} skills")
        return "\n".join(lines)
