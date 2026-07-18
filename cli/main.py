"""
cli/main.py - IdentityOS Command-Line Interface

The human-facing entry point for interacting with the Identity Runtime.
Provides commands to create, load, chat with, inspect, and version
any identity without writing a single line of code.

Usage:
    python -m cli.main --help
    python -m cli.main create --name "Mentor" --persona mentor
    python -m cli.main chat   --id mentor-01
    python -m cli.main inspect --id mentor-01
    python -m cli.main snapshot --id mentor-01 --label "after-session-3"
    python -m cli.main history  --id mentor-01
    python -m cli.main rollback --id mentor-01 --snap <snapshot_id>
    python -m cli.main diff     --id mentor-01 --from <snap_a> --to <snap_b>

Dependencies:
    Standard library only (argparse, json, sys, os, pathlib).
    Runtime imports are lazy so the CLI starts fast.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

DEFAULT_STORE = ".identity_store"
DEFAULT_BACKEND = "json"


def _get_storage(args: argparse.Namespace):
    """Lazy import + instantiate the chosen storage backend."""
    from runtime.persistence import get_backend
    backend_kwargs: dict = {}
    if args.backend == "sqlite":
        backend_kwargs["db_path"] = str(Path(args.store) / "identities.db")
    else:
        backend_kwargs["root_dir"] = args.store
    return get_backend(args.backend, **backend_kwargs)


def _get_snapshot_manager(storage, identity_id: str):
    from core.snapshot import SnapshotManager
    return SnapshotManager(storage, identity_id)


def _print_json(data: dict) -> None:
    print(json.dumps(data, indent=2, default=str))


def _confirm(prompt: str) -> bool:
    try:
        answer = input(f"{prompt} [y/N] ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        print()
        return False
    return answer in ("y", "yes")


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_create(args: argparse.Namespace) -> int:
    """
    Create a new identity and persist its initial snapshot.
    """
    import uuid, time

    identity_id = args.id or str(uuid.uuid4())[:8]
    storage = _get_storage(args)
    manager = _get_snapshot_manager(storage, identity_id)

    # Build a minimal initial identity spec
    initial_state = {
        "identity": {
            "id": identity_id,
            "name": args.name,
            "persona": args.persona,
            "created_at": time.time(),
            "version": "0.1.0",
        },
        "experience": {"entries": []},
        "knowledge": {"packs": []},
        "motivations": {"active": []},
        "timeline": {"events": []},
        "relationships": {"nodes": [], "edges": []},
    }

    snap_id = manager.capture(initial_state, label="initial")
    print(f"Identity created.")
    print(f"  id          : {identity_id}")
    print(f"  name        : {args.name}")
    print(f"  persona     : {args.persona}")
    print(f"  snapshot_id : {snap_id}")
    print(f"  store       : {args.store}")
    return 0


def cmd_inspect(args: argparse.Namespace) -> int:
    """
    Print the latest snapshot of an identity as JSON.
    """
    storage = _get_storage(args)
    manager = _get_snapshot_manager(storage, args.id)
    snap = manager.latest()
    if snap is None:
        print(f"No snapshots found for identity '{args.id}'.", file=sys.stderr)
        return 1
    _print_json(snap.to_dict())
    return 0


def cmd_snapshot(args: argparse.Namespace) -> int:
    """
    Manually trigger a snapshot of the current identity state.
    (Re-captures the latest state with an optional label.)
    """
    storage = _get_storage(args)
    manager = _get_snapshot_manager(storage, args.id)
    latest = manager.latest()
    if latest is None:
        print(f"Identity '{args.id}' has no state to snapshot.", file=sys.stderr)
        return 1
    snap_id = manager.capture(latest.modules, label=args.label or "manual")
    print(f"Snapshot captured: {snap_id}")
    return 0


def cmd_history(args: argparse.Namespace) -> int:
    """
    List all snapshots for an identity in chronological order.
    """
    storage = _get_storage(args)
    manager = _get_snapshot_manager(storage, args.id)
    history = manager.history()
    if not history:
        print(f"No snapshots found for identity '{args.id}'.")
        return 0
    print(f"Snapshot history for '{args.id}' ({len(history)} total):")
    for i, snap in enumerate(history, 1):
        print(f"  {i:3}. {snap.summary()}")
    return 0


def cmd_rollback(args: argparse.Namespace) -> int:
    """
    Roll back an identity to a prior snapshot (non-destructive).
    """
    storage = _get_storage(args)
    manager = _get_snapshot_manager(storage, args.id)

    if not _confirm(
        f"Roll back identity '{args.id}' to snapshot '{args.snap}'?"
    ):
        print("Cancelled.")
        return 0

    try:
        snap = manager.rollback(args.snap)
        print(f"Rolled back to snapshot {snap.snapshot_id[:8]}.")
        print(f"  captured : {snap.summary()}")
    except KeyError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 0


def cmd_diff(args: argparse.Namespace) -> int:
    """
    Show a diff between two snapshots.
    """
    storage = _get_storage(args)
    manager = _get_snapshot_manager(storage, args.id)
    try:
        result = manager.diff(args.from_snap, args.to_snap)
        _print_json(result)
    except KeyError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 0


def cmd_chat(args: argparse.Namespace) -> int:
    """
    Start an interactive REPL with a loaded identity.

    This is a lightweight terminal client. For production use,
    run the FastAPI service in runtime/main.py instead.
    """
    storage = _get_storage(args)
    manager = _get_snapshot_manager(storage, args.id)
    latest = manager.latest()
    if latest is None:
        print(f"Identity '{args.id}' not found. Run 'create' first.", file=sys.stderr)
        return 1

    identity_name = latest.modules.get("identity", {}).get("name", args.id)
    print(f"IdentityOS Chat - talking to: {identity_name}")
    print(f"Type 'exit' or Ctrl-C to quit. Type ':snapshot' to checkpoint.")
    print("-" * 60)

    # Lazy-import the orchestrator so the CLI stays light when not chatting
    try:
        from runtime.orchestrator import IdentityRuntime
        runtime = IdentityRuntime(identity_id=args.id, storage=storage)
    except Exception as e:
        # Graceful degradation: run as a bare echo loop if runtime unavailable
        print(f"[warn] Could not load runtime ({e}). Running in echo mode.")
        runtime = None

    session_turns = 0
    while True:
        try:
            user_input = input("you> ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye.")
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit", "bye"):
            print("Goodbye.")
            break
        if user_input == ":snapshot":
            snap_id = manager.capture(
                latest.modules,
                label=f"chat-turn-{session_turns}",
            )
            print(f"[snapshot saved: {snap_id[:8]}]")
            continue
        if user_input == ":history":
            for snap in manager.history():
                print(f"  {snap.summary()}")
            continue

        if runtime is not None:
            try:
                response = runtime.chat(user_input)
                print(f"{identity_name}> {response}")
            except Exception as e:
                print(f"[runtime error] {e}")
        else:
            print(f"{identity_name}> [echo] {user_input}")

        session_turns += 1

    return 0


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="identity-runtime",
        description="IdentityOS CLI - manage persistent digital identities",
    )
    parser.add_argument(
        "--store",
        default=DEFAULT_STORE,
        help=f"Path to the identity store directory (default: {DEFAULT_STORE})",
    )
    parser.add_argument(
        "--backend",
        choices=["json", "sqlite"],
        default=DEFAULT_BACKEND,
        help="Storage backend (default: json)",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # create
    p_create = sub.add_parser("create", help="Create a new identity")
    p_create.add_argument("--id", default=None, help="Custom identity id (auto-generated if omitted)")
    p_create.add_argument("--name", required=True, help="Human-readable name")
    p_create.add_argument("--persona", default="default", help="Persona archetype (e.g. mentor, analyst)")

    # inspect
    p_inspect = sub.add_parser("inspect", help="Print the latest snapshot of an identity")
    p_inspect.add_argument("--id", required=True, help="Identity id")

    # snapshot
    p_snapshot = sub.add_parser("snapshot", help="Manually capture a snapshot")
    p_snapshot.add_argument("--id", required=True, help="Identity id")
    p_snapshot.add_argument("--label", default="manual", help="Snapshot label")

    # history
    p_history = sub.add_parser("history", help="List all snapshots for an identity")
    p_history.add_argument("--id", required=True, help="Identity id")

    # rollback
    p_rollback = sub.add_parser("rollback", help="Roll back to a prior snapshot")
    p_rollback.add_argument("--id", required=True, help="Identity id")
    p_rollback.add_argument("--snap", required=True, help="Snapshot id to roll back to")

    # diff
    p_diff = sub.add_parser("diff", help="Diff two snapshots")
    p_diff.add_argument("--id", required=True, help="Identity id")
    p_diff.add_argument("--from", dest="from_snap", required=True, help="From snapshot id")
    p_diff.add_argument("--to", dest="to_snap", required=True, help="To snapshot id")

    # chat
    p_chat = sub.add_parser("chat", help="Start an interactive chat session with an identity")
    p_chat.add_argument("--id", required=True, help="Identity id")
    p_chat.add_argument("--model", default="gpt-4o", help="Model adapter to use")

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

COMMAND_MAP = {
    "create": cmd_create,
    "inspect": cmd_inspect,
    "snapshot": cmd_snapshot,
    "history": cmd_history,
    "rollback": cmd_rollback,
    "diff": cmd_diff,
    "chat": cmd_chat,
}


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = COMMAND_MAP.get(args.command)
    if handler is None:
        parser.print_help()
        return 1
    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
