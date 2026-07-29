#!/usr/bin/env python3
"""
Daedalus PR Review — automated architectural review for IdentityOS pull requests.

Daedalus analyzes each PR against IdentityOS architectural principles:
- Layer separation (Runtime / Prometheus / IdentityBench / Atlas)
- Separation of concerns between packages
- Test coverage for changes
- Benchmark regression potential
- Code quality and patterns
- Documentation completeness
- Alignment with long-term goals

Usage:
    python scripts/daedalus_review.py \
        --diff /tmp/pr.diff \
        --repo owner/repo \
        --pr-number 42 \
        --head-ref feat/my-branch \
        --base-ref main \
        --title "feat: my change" \
        --output /tmp/review.md \
        --token ghp_xxx
"""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


ARCHITECTURE_LAYERS = {
    "runtime": "runtime/",
    "prometheus": "core/prometheus/",
    "identitybench": "identitybench/",
    "atlas": "identitybench/atlas/",
    "core": "core/",
    "cli": "cli/",
    "registry": "registry/",
    "spec": "spec/",
}

LAYER_PURPOSE = {
    "runtime/": "execution layer",
    "core/prometheus/": "autonomous evolution layer",
    "identitybench/": "measurement & explanation layer",
    "identitybench/atlas/": "strategic decision layer",
    "core/": "core framework",
    "cli/": "command-line interface",
    "registry/": "capability registry",
}

IMPORT_RESTRICTIONS: List[Tuple[str, str, str]] = [
    ("identitybench/atlas/", "runtime/", "Atlas must not import Runtime internals"),
    ("identitybench/atlas/", "core/prometheus/", "Atlas must not import Prometheus internals"),
    ("identitybench/", "runtime/", "IdentityBench should not import Runtime internals directly"),
    ("core/prometheus/", "identitybench/atlas/", "Prometheus should not depend on Atlas"),
]

SEPARATION_CHECK_PATTERNS = [
    (r"from\s+runtime\.", "identitybench/", "IdentityBench imports Runtime module"),
    (r"from\s+identitybench\.atlas", "core/", "Core imports from Atlas (reverse dependency)"),
    (r"from\s+core\.prometheus", "identitybench/", "IdentityBench imports Prometheus directly"),
]

CRITICAL_DIRECTORIES = [
    "core/identity.py",
    "runtime/orchestrator.py",
    "core/prometheus/engine.py",
    "identitybench/engine.py",
    "identitybench/atlas/health.py",
]

CATEGORY_MAP = {
    "feat": "feature",
    "fix": "bugfix",
    "refactor": "refactor",
    "docs": "documentation",
    "test": "testing",
    "chore": "maintenance",
    "ci": "ci/cd",
    "revert": "revert",
}

DAEDALUS_SIGNATURE = "\u2014 Daedalus\nLace's Engineering Partner\nIdentityOS"


def load_daedalus_config() -> Dict[str, Any]:
    config: Dict[str, Any] = {}
    identity_path = Path(".daedalus/identity.json")
    goals_path = Path(".daedalus/goals.json")
    if identity_path.exists():
        try:
            config["identity"] = json.loads(identity_path.read_text())
        except Exception:
            config["identity"] = {}
    if goals_path.exists():
        try:
            config["goals"] = json.loads(goals_path.read_text())
        except Exception:
            config["goals"] = {"primary_goals": []}
    return config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Daedalus PR Review")
    parser.add_argument("--diff", required=True, help="Path to PR diff file")
    parser.add_argument("--repo", required=True, help="Repository (owner/name)")
    parser.add_argument("--pr-number", type=int, required=True, help="PR number")
    parser.add_argument("--head-ref", required=True, help="Head branch ref")
    parser.add_argument("--base-ref", required=True, help="Base branch ref")
    parser.add_argument("--title", required=True, help="PR title")
    parser.add_argument("--output", required=True, help="Output markdown file")
    parser.add_argument("--token", default="", help="GitHub token")
    return parser.parse_args()


def read_diff(path: str) -> str:
    with open(path) as f:
        return f.read()


def parse_diff_files(diff: str) -> List[Dict[str, Any]]:
    files: List[Dict[str, Any]] = []
    current_file: Dict[str, Any] = {}
    for line in diff.split("\n"):
        if line.startswith("+++ b/"):
            current_file["path"] = line[6:]
        elif line.startswith("diff --git"):
            if current_file:
                files.append(current_file)
            current_file = {"path": "", "additions": 0, "deletions": 0, "lines": []}
        elif current_file:
            if line.startswith("+") and not line.startswith("+++"):
                current_file["additions"] += 1
                current_file["lines"].append(line)
            elif line.startswith("-") and not line.startswith("---"):
                current_file["deletions"] += 1
    if current_file:
        files.append(current_file)
    return files


def detect_layer(fpath: str) -> Optional[str]:
    for name, prefix in ARCHITECTURE_LAYERS.items():
        if fpath.startswith(prefix):
            return name
    return None


def analyze_separation(files: List[Dict[str, Any]], diff: str) -> List[str]:
    findings: List[str] = []
    for pattern, file_prefix, message in SEPARATION_CHECK_PATTERNS:
        for f in files:
            if f["path"].startswith(file_prefix):
                for line in f["lines"]:
                    stripped = line.lstrip("+").strip()
                    if re.search(pattern, stripped):
                        findings.append(
                            f"- \u26a0\ufe0f **{message}** in `{f['path']}`: `{stripped[:80]}`"
                        )
    for src_prefix, forbidden_prefix, message in IMPORT_RESTRICTIONS:
        if any(f["path"].startswith(src_prefix) for f in files):
            for f in files:
                if f["path"].startswith(src_prefix):
                    restricted_imports = []
                    for line in f["lines"]:
                        stripped = line.lstrip("+").strip()
                        if stripped.startswith("from ") or stripped.startswith("import "):
                            if forbidden_prefix.replace("/", ".") in stripped:
                                restricted_imports.append(stripped)
                    if restricted_imports:
                        findings.append(
                            f"- \u274c **{message}** in `{f['path']}`:\n"
                            + "\n".join(f"  - `{imp}`" for imp in restricted_imports[:3])
                        )
    if not findings:
        findings.append("- \u2705 Layer separation maintained \u2014 no violations detected")
    return findings


def analyze_test_coverage(files: List[Dict[str, Any]]) -> List[str]:
    findings: List[str] = []
    source_files = [f for f in files if not f["path"].startswith("tests/") and f["path"].endswith(".py")]
    test_files = [f for f in files if f["path"].startswith("tests/")]
    if source_files and not test_files:
        findings.append(
            f"- \u26a0\ufe0f **{len(source_files)} source files changed but no test files updated** \u2014 "
            "consider adding tests for the changes"
        )
    elif source_files:
        findings.append(
            f"- \u2705 **{len(test_files)} test file(s)** included for **{len(source_files)} source file(s)** changed"
        )
    for sf in source_files:
        base = os.path.basename(sf["path"]).replace(".py", "")
        corresponding = [
            tf for tf in test_files
            if base in tf["path"] or os.path.basename(tf["path"]).replace(".py", "").replace("test_", "") in base
        ]
        if not corresponding:
            findings.append(
                f"  - `{sf['path']}` \u2014 no corresponding test file found "
                f"(expected `tests/test_{base}.py`)"
            )
    return findings


def analyze_diff_quality(files: List[Dict[str, Any]], title: str) -> List[str]:
    findings: List[str] = []
    total_additions = sum(f["additions"] for f in files)
    total_deletions = sum(f["deletions"] for f in files)
    if total_additions > 500:
        findings.append(
            f"- \u26a0\ufe0f **Large PR**: {total_additions} additions, {total_deletions} deletions \u2014 "
            "consider splitting into smaller, focused changes"
        )
    else:
        findings.append(f"- \U0001f4ca **{total_additions} additions / {total_deletions} deletions** \u2014 manageable size")
    cat = None
    for prefix, category in CATEGORY_MAP.items():
        if title.lower().startswith(prefix):
            cat = category
            break
    if cat:
        findings.append(f"- \U0001f3f7\ufe0f Categorized as **{cat}** (from title prefix)")
    else:
        findings.append(f"- \U0001f3f7\ufe0f Unable to auto-detect change category from title \u2014 "
                        f"conventional commit format recommended (`feat:`, `fix:`, etc.)")
    return findings


def analyze_architectural_impact(files: List[Dict[str, Any]]) -> List[str]:
    findings: List[str] = []
    impacted_layers = set()
    for f in files:
        layer = detect_layer(f["path"])
        if layer:
            impacted_layers.add(layer)
    for f in files:
        for critical in CRITICAL_DIRECTORIES:
            if f["path"] == critical:
                findings.append(
                    f"- \u26a0\ufe0f **Critical file modified**: `{f['path']}` \u2014 "
                    "this file is central to IdentityOS architecture"
                )
    if impacted_layers:
        layer_details = []
        for layer in sorted(impacted_layers):
            count = sum(1 for f in files if detect_layer(f["path"]) == layer)
            purpose = LAYER_PURPOSE.get(ARCHITECTURE_LAYERS.get(layer, ""), "unknown")
            layer_details.append(f"  - **{layer}**: {count} file(s) ({purpose})")
        findings.append(f"- \U0001f3d7\ufe0f **{len(impacted_layers)} layer(s) impacted**:\n" + "\n".join(layer_details))
    return findings


def analyze_documentation_impact(files: List[Dict[str, Any]]) -> List[str]:
    findings: List[str] = []
    has_doc_changes = any(f["path"].startswith("docs/") for f in files)
    has_arch_doc = any(f["path"].startswith("docs/architecture/") for f in files)
    has_source = any(
        f["path"].endswith(".py") and not f["path"].startswith("tests/")
        for f in files
    )
    if has_source and not has_doc_changes:
        findings.append(
            f"- \u2139\ufe0f **Source code changed without documentation updates** \u2014 consider "
            f"updating relevant docs if this changes public interfaces"
        )
    if has_arch_doc:
        findings.append(f"- \u2705 Architecture documentation updated")
    return findings


def analyze_goals_alignment(
    files: List[Dict[str, Any]],
    title: str,
    daedalus_config: Dict[str, Any],
) -> List[str]:
    findings: List[str] = []
    goals = daedalus_config.get("goals", {}).get("primary_goals", [])
    if not goals:
        return []
    all_paths = " ".join(f["path"] for f in files)
    title_lower = title.lower()
    for goal in goals:
        gid = goal.get("id", "")
        gname = goal.get("goal", "")
        priority = goal.get("priority", 0)
        if priority < 7:
            continue
        keywords = gname.lower().split()
        match_count = sum(1 for kw in keywords if kw in all_paths.lower() or kw in title_lower)
        if match_count == 0 and priority >= 8:
            findings.append(
                f"- \U0001f3af Goal **\"{gname[:60]}\"** (priority {priority}) \u2014 "
                f"this PR doesn't appear to address it directly"
            )
    return findings


def analyze_technical_debt_introduced(files: List[Dict[str, Any]]) -> List[str]:
    findings: List[str] = []
    debt_markers = ["TODO", "FIXME", "HACK", "XXX", "TEMP", "workaround"]
    marker_count = 0
    for f in files:
        for line in f["lines"]:
            stripped = line.lstrip("+").strip()
            for marker in debt_markers:
                if marker in stripped.upper():
                    marker_count += 1
    if marker_count > 0:
        findings.append(
            f"- \U0001f4a1 **{marker_count} technical debt marker(s) introduced** \u2014 "
            "consider addressing before merge"
        )
    else:
        findings.append("- \u2705 No new technical debt introduced")
    return findings


def assess_readiness(findings: Dict[str, List[str]]) -> Tuple[str, List[str]]:
    issues = []
    warnings = []
    for section, items in findings.items():
        for item in items:
            if "\u274c" in item:
                issues.append(item)
            elif "\u26a0\ufe0f" in item:
                warnings.append(item)
    if issues:
        return "NOT_READY", issues + warnings
    elif warnings:
        return "NEEDS_WORK", warnings
    else:
        return "READY", []


def generate_markdown_review(
    title: str,
    pr_number: int,
    head_ref: str,
    base_ref: str,
    findings: Dict[str, List[str]],
    readiness: Tuple[str, List[str]],
    daedalus_config: Dict[str, Any],
) -> str:
    status = readiness[0]
    status_emoji = {"READY": "\u2705", "NEEDS_WORK": "\u26a0\ufe0f", "NOT_READY": "\u274c"}
    identity = daedalus_config.get("identity", {})
    personality = identity.get("personality", {})
    style = personality.get("style", "evidence-driven")
    lines = [
        f"# \U0001f3db\ufe0f Daedalus Architectural Review",
        f"**PR:** {title} (#{pr_number})",
        f"**Branch:** `{head_ref}` \u2192 `{base_ref}`",
        f"**Reviewer:** Daedalus \u2014 {identity.get('role', 'Engineering Partner')} for {identity.get('project', 'IdentityOS')}",
        f"**Style:** {style}, {personality.get('obsessed_with_architectural_simplicity', False) and 'architecturally rigorous' or 'analytical'}",
        "",
        f"## Merge Readiness: {status_emoji.get(status, chr(10067))} {status.replace('_', ' ')}",
        "",
    ]
    if readiness[1]:
        lines.append("### Issues & Recommendations")
        lines.append("")
        for item in readiness[1][:12]:
            lines.append(item)
        lines.append("")

    section_order = [
        ("Layer Separation", "separation"),
        ("Architectural Impact", "architecture"),
        ("Goal Alignment", "goals"),
        ("Technical Debt", "tech_debt"),
        ("Diff Quality", "diff_quality"),
        ("Test Coverage", "test_coverage"),
        ("Documentation", "documentation"),
    ]
    for section_label, section_key in section_order:
        items = findings.get(section_key, [])
        if items:
            lines.append(f"## {section_label}")
            lines.append("")
            lines.extend(items)
            lines.append("")

    lines.extend([
        "## Evidence & Methodology",
        "",
        "Daedalus reviewed this PR by:",
        f"- Analyzing the diff against {len(ARCHITECTURE_LAYERS)} architectural layers",
        "- Checking import patterns for separation of concerns",
        "- Verifying layer boundaries (Runtime \u2192 Prometheus \u2192 IdentityBench \u2192 Atlas)",
        "- Identifying impacted critical modules",
        "- Checking test coverage for source code changes",
        "- Evaluating alignment with primary goals",
        "- Detecting introduced technical debt",
        "",
        "---",
        "",
        DAEDALUS_SIGNATURE,
    ])
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    daedalus_config = load_daedalus_config()
    diff_text = read_diff(args.diff)
    files = parse_diff_files(diff_text)
    findings: Dict[str, List[str]] = {
        "separation": [],
        "architecture": [],
        "diff_quality": [],
        "test_coverage": [],
        "documentation": [],
        "goals": [],
        "tech_debt": [],
    }
    findings["separation"] = analyze_separation(files, diff_text)
    findings["architecture"] = analyze_architectural_impact(files)
    findings["diff_quality"] = analyze_diff_quality(files, args.title)
    findings["test_coverage"] = analyze_test_coverage(files)
    findings["documentation"] = analyze_documentation_impact(files)
    findings["goals"] = analyze_goals_alignment(files, args.title, daedalus_config)
    findings["tech_debt"] = analyze_technical_debt_introduced(files)
    readiness = assess_readiness(findings)
    markdown = generate_markdown_review(
        args.title, args.pr_number, args.head_ref, args.base_ref,
        findings, readiness, daedalus_config,
    )
    with open(args.output, "w") as f:
        f.write(markdown)
    print(f"Daedalus review written to {args.output} \u2014 status: {readiness[0]}")


if __name__ == "__main__":
    main()
