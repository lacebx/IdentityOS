from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List, Optional

from identitybench.engine import IdentityBench, DEFAULT_WORLDS, SMOKE_WORLDS
from identitybench.reporting import (
    build_comparison_data,
    generate_markdown_report,
    generate_regression_summary,
    generate_report_text,
)
from identitybench.storage import BenchmarkStorage


def cmd_run(args: argparse.Namespace) -> None:
    engine = IdentityBench(
        identity_id=args.identity,
        storage_path=args.storage_dir,
    )
    engine.load_identity()
    world_classes = DEFAULT_WORLDS if args.mode == "full" else SMOKE_WORLDS
    if args.worlds:
        world_map = {w.name.lower(): w for w in DEFAULT_WORLDS}
        selected = []
        for name in args.worlds:
            name_lower = name.lower()
            if name_lower in world_map:
                selected.append(world_map[name_lower])
            else:
                print(f"Unknown world: {name}. Available: {list(world_map.keys())}")
                return
        world_classes = selected
    print(f"Running IdentityBench [{args.mode}] for {args.identity}...")
    engine.run(world_classes=world_classes, seed=args.seed)


def cmd_report(args: argparse.Namespace) -> None:
    storage = BenchmarkStorage(root_dir=args.storage_dir)
    if args.identity:
        identities = [args.identity]
    else:
        identities = storage.list_identities()
    for identity_id in identities:
        run = storage.load_latest_run(identity_id)
        if not run:
            print(f"No benchmark runs found for '{identity_id}'.")
            continue
        trends = storage.load_trends(identity_id)
        if args.markdown:
            report = generate_markdown_report(run, trend_data=trends)
            if args.output:
                with open(args.output, "w") as f:
                    f.write(report)
                print(f"Markdown report written to {args.output}")
            else:
                print(report)
        else:
            comparison = None
            if args.compare:
                ids = args.compare.split(",")
                comparison = build_comparison_data(storage, ids)
            text = generate_report_text(run, trend_data=trends, comparison_data=comparison)
            print(text)


def cmd_history(args: argparse.Namespace) -> None:
    storage = BenchmarkStorage(root_dir=args.storage_dir)
    identity_id = args.identity
    runs = storage.list_runs(identity_id)
    if not runs:
        print(f"No benchmark history for '{identity_id}'.")
        return
    print(f"Benchmark history for {identity_id}:")
    print(f"  {'#':>4s}  {'Date':>25s}  {'Score':>7s}")
    print(f"  {'-'*40}")
    for i, r in enumerate(runs, 1):
        run_data = storage.load_run(identity_id, r["filename"])
        score = run_data.get("overall_score", "?") if run_data else "?"
        ts = r["timestamp"][:19]
        print(f"  {i:>4d}  {ts:>25s}  {score:>7s}")


def cmd_compare(args: argparse.Namespace) -> None:
    storage = BenchmarkStorage(root_dir=args.storage_dir)
    if args.identities:
        ids = args.identities
        comparison = build_comparison_data(storage, ids)
        report = generate_report_text({}, comparison_data=comparison)
        report = report.replace("IdentityBench Report", "IdentityBench Comparison")
        print(report)
    elif args.last and args.identity_id:
        identity_id = args.identity_id
        trends = storage.load_trends(identity_id)
        sorted_trends = sorted(trends, key=lambda x: x.get("timestamp", ""))
        recent = sorted_trends[-args.last:] if args.last < len(sorted_trends) else sorted_trends
        if len(recent) < 2:
            print(f"Need at least 2 runs to compare. Found {len(recent)}.")
            return
        curr_run_data = None
        prev_run_data = None
        runs = storage.list_runs(identity_id)
        recent_filenames = [r["filename"] for r in runs[:args.last]]
        if len(recent_filenames) >= 2:
            curr_run_data = storage.load_run(identity_id, recent_filenames[0])
            prev_run_data = storage.load_run(identity_id, recent_filenames[1])
        if curr_run_data and prev_run_data:
            summary = generate_regression_summary(prev_run_data, curr_run_data)
            print(f"Comparison for {identity_id} (last {args.last} runs):\n")
            ov = summary["overall"]
            arrow = "▲" if ov["change"] > 0 else ("▼" if ov["change"] < 0 else "─")
            print(f"  Overall: {ov['previous']} → {ov['current']} ({arrow}{ov['change']:+g}) [{ov['verdict']}]")
            if summary["regressions"]:
                print(f"\n  Regressions:")
                for r in summary["regressions"]:
                    print(f"    ▼ {r['category']:20s} {r['previous']} → {r['current']} ({r['change']:+g})")
            if summary["improvements"]:
                print(f"\n  Improvements:")
                for r in summary["improvements"]:
                    print(f"    ▲ {r['category']:20s} {r['previous']} → {r['current']} ({r['change']:+g})")
            if not summary["regressions"] and not summary["improvements"]:
                print(f"\n  No significant changes (threshold: {summary['threshold']} pts).")
    else:
        print("Specify --identities for cross-identity comparison or --id with --last for historical comparison.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="identitybench",
        description="IdentityBench — Benchmarking framework for IdentityOS identities",
    )
    parser.add_argument("--storage-dir", default=".identitybench", help="Benchmark data directory")
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="Run benchmarks against an identity")
    p_run.add_argument("identity", help="Identity ID to benchmark")
    p_run.add_argument("--mode", choices=["full", "smoke"], default="full", help="Benchmark mode")
    p_run.add_argument("--worlds", nargs="*", help="Specific worlds to run")
    p_run.add_argument("--seed", type=int, default=42, help="RNG seed for determinism")
    p_run.set_defaults(func=cmd_run)

    p_report = sub.add_parser("report", help="Generate benchmark report")
    p_report.add_argument("identity", nargs="?", default=None, help="Identity ID (omit for all)")
    p_report.add_argument("--markdown", action="store_true", help="Output Markdown")
    p_report.add_argument("-o", "--output", help="Write report to file")
    p_report.add_argument("--compare", help="Comma-separated identity IDs to compare")
    p_report.set_defaults(func=cmd_report)

    p_history = sub.add_parser("history", help="Show benchmark history")
    p_history.add_argument("identity", help="Identity ID")
    p_history.set_defaults(func=cmd_history)

    p_compare = sub.add_parser("compare", help="Compare identities or historical runs")
    p_compare.add_argument("--identities", nargs="+", default=[], help="Identity IDs to compare across identities")
    p_compare.add_argument("--id", dest="identity_id", default=None, help="Identity ID (for --last)")
    p_compare.add_argument("--last", type=int, default=0, help="Compare last N runs of identity")
    p_compare.set_defaults(func=cmd_compare)

    return parser


def main(argv: Optional[List[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
