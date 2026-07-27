"""
cli/main.py - IdentityOS Command-Line Interface

Single entry point for all IdentityOS operations.
Run `identity --help` after installing.

Usage:
    identity create --name "Mentor" --persona mentor    Create an identity
    identity chat --id mentor-01                         Chat with an identity
    identity inspect --id mentor-01                      Inspect identity state
    identity list                                        List all identities
    identity playground                                  Launch web UI
    identity registry list                               Browse identity registry
    identity cap list                                    Browse capabilities
    identity isp list                                    Browse skill packs
    identity explain <id> <question>                     Explain identity reasoning
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional

from cli.registry_cmds import (
    cmd_registry_list,
    cmd_registry_show,
    cmd_registry_install,
    cmd_registry_publish,
    cmd_cap_list,
    cmd_cap_show,
    cmd_cap_install,
    cmd_cap_search,
    cmd_cap_list_installed,
    cmd_isp_list,
    cmd_isp_show,
    cmd_isp_install,
    cmd_explain,
    cmd_inspect_dashboard,
)

# Load .env if present
_env_file = Path(__file__).resolve().parent.parent / ".env"
if _env_file.is_file():
    try:
        for _line in _env_file.read_text().splitlines():
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip().strip("\"'"))
    except Exception:
        pass

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


def _get_adapter(args: argparse.Namespace):
    from adapters import get_adapter
    import json
    config = json.loads(args.adapter_config) if args.adapter_config != "{}" else {}
    if args.adapter and "model" not in config:
        config["model"] = getattr(args, "model", None) or "gpt-4o"
    return get_adapter(args.adapter, **config)


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
    import time
    import uuid

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
    print("Identity created.")
    print(f"  id          : {identity_id}")
    print(f"  name        : {args.name}")
    print(f"  persona     : {args.persona}")
    print(f"  snapshot_id : {snap_id}")
    print(f"  store       : {args.store}")
    return 0


def cmd_inspect(args: argparse.Namespace) -> int:
    """
    Print the current persisted state of an identity.
    Use --dashboard for the rich visual dashboard.
    """
    if getattr(args, "dashboard", False):
        cmd_inspect_dashboard(args.id)
        return 0

    storage = _get_storage(args)
    identity_id = args.id

    identity_data = storage.load(identity_id, "latest_snapshot")
    if not identity_data:
        print(f"Identity '{identity_id}' not found.", file=sys.stderr)
        return 1

    identity_spec = identity_data.get("modules", {}).get("identity", identity_data)

    timeline_data = storage.load(identity_id, "timeline") or {"events": []}
    relationships_data = storage.load(identity_id, "relationships") or {"edges": []}
    goals_data = storage.load(identity_id, "goals") or {"goals": []}
    memories_data = storage.load_memories(identity_id) or []

    state = {
        "identity": identity_spec,
        "timeline": {
            "event_count": len(timeline_data.get("events", [])),
            "events": [
                {"title": e.get("title"), "event_type": e.get("event_type"), "occurred_at": e.get("occurred_at")}
                for e in timeline_data.get("events", [])
            ],
        },
        "relationships": {
            "edge_count": len(relationships_data.get("edges", [])),
            "edges": [
                {"source": e.get("source_id"), "target": e.get("target_id"),
                 "type": e.get("edge_type"), "strength": e.get("strength")}
                for e in relationships_data.get("edges", [])
            ],
        },
        "goals": {
            "goal_count": len(goals_data.get("goals", [])),
            "goals": [
                {"title": g.get("title"), "status": g.get("status"), "priority": g.get("priority"),
                 "progress": g.get("progress")}
                for g in goals_data.get("goals", [])
            ],
        },
        "memories": {
            "total": len(memories_data),
            "recent": [
                {"content": m.get("content", "")[:120], "type": m.get("memory_type"), "tags": m.get("tags")}
                for m in memories_data[-5:]
            ],
        },
    }
    _print_json(state)
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


def cmd_get(args: argparse.Namespace) -> int:
    """
    List all identities ranked by experience (interactions + memories + timeline events).
    Shows stats for each identity and sorts by total experience descending.
    """
    storage = _get_storage(args)
    ids = storage.list_identities()
    if not ids:
        print("No identities found.")
        return 0

    rows = []
    for identity_id in ids:
        identity_data = storage.load(identity_id, "latest_snapshot") or {}
        identity_spec = identity_data.get("modules", {}).get("identity", identity_data)
        name = identity_spec.get("name", identity_id)
        persona = identity_spec.get("persona") or ""

        timeline_data = storage.load(identity_id, "timeline") or {"events": []}
        rel_data = storage.load(identity_id, "relationships") or {"edges": []}
        mems = storage.load_memories(identity_id) or []
        goals_data = storage.load(identity_id, "goals") or {"goals": []}

        timeline_count = len(timeline_data.get("events", []))
        edges = rel_data.get("edges", [])
        interaction_count = sum(e.get("interaction_count", 0) for e in edges)
        memory_count = len(mems)
        goal_count = len(goals_data.get("goals", []))
        edge_count = len(edges)

        total_experience = interaction_count + timeline_count + memory_count

        rows.append({
            "id": identity_id,
            "name": name,
            "persona": persona,
            "experience": {
                "total": total_experience,
                "interactions": interaction_count,
                "timeline_events": timeline_count,
                "memories": memory_count,
                "relationships": edge_count,
                "goals": goal_count,
            },
        })

    rows.sort(key=lambda r: r["experience"]["total"], reverse=True)

    print(f"{'Rank':<5} {'ID':<18} {'Name':<18} {'Persona':<18} {'Exp':<5} {'Ints':<5} {'TL':<4} {'Mem':<4} {'Rel':<4}")
    print("-" * 85)
    for i, r in enumerate(rows, 1):
        e = r["experience"]
        print(f"{i:<5} {r['id']:<18} {r['name']:<18} {r['persona']:<18} {e['total']:<5} {e['interactions']:<5} {e['timeline_events']:<4} {e['memories']:<4} {e['relationships']:<4}")
    print(f"\n{len(rows)} identities total.")
    return 0


def cmd_playground(args: argparse.Namespace) -> int:
    """Launch the IdentityOS Playground web UI."""
    try:
        import uvicorn
        from runtime.playground.app import app
        print("  \u25B6 IdentityOS Playground")
        print("  \u2500" * 40)
        print(f"  Open http://localhost:{args.port}/playground")
        print()
        uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
    except ImportError:
        print("Install uvicorn: pip install uvicorn", file=sys.stderr)
        return 1
    return 0


def _probe_adapter(name: str, adapter_cls: type, model: str, **kwargs):
    """Try to create and health-check an adapter. Return (name, instance, error_or_None)."""
    try:
        inst = adapter_cls(model=model, **kwargs)
        ok = inst.health_check()
        if ok:
            return (name, inst, None)
        return (name, None, f"{name}: reachable but health check failed")
    except Exception as e:
        return (name, None, f"{name}: {e}")


def _interactive_adapter_select():
    """Scan env for configured adapters, health-check them, let user pick."""

    candidates = []

    # Groq (with key rotation)
    _groq_keys = [os.environ.get(k) for k in ("GROQ_API_KEY", "GROQ_API_KEY_2", "GROQ_API_KEY_3",
                                               "GROQ_API_KEY_4", "GROQ_API_KEY_5", "GROQ_API_KEY_6")]
    if any(k for k in _groq_keys if k and "PLACEHOLDER" not in k):
        from adapters.groq_adapter import GroqAdapter
        candidates.append(
            _probe_adapter("Groq", GroqAdapter, os.environ.get("IDENTITY_MODEL", "llama-3.3-70b-versatile"))
        )

    if os.environ.get("SAMBANOVA_API_KEY"):
        from adapters.sambanova_adapter import SambaNovaAdapter
        candidates.append(
            _probe_adapter("SambaNova", SambaNovaAdapter, os.environ.get("IDENTITY_MODEL", "DeepSeek-V3.1"))
        )

    if os.environ.get("OPENROUTER_API_KEY"):
        from adapters.openrouter_adapter import OpenRouterAdapter
        candidates.append(
            _probe_adapter("OpenRouter", OpenRouterAdapter, os.environ.get("IDENTITY_MODEL", "openai/gpt-4o"))
        )

    if os.environ.get("OPENAI_API_KEY"):
        from adapters.openai_adapter import OpenAIAdapter
        candidates.append(
            _probe_adapter("OpenAI", OpenAIAdapter, os.environ.get("IDENTITY_MODEL", "gpt-4o"))
        )

    if os.environ.get("ANTHROPIC_API_KEY"):
        from adapters.openai_adapter import AnthropicAdapter
        candidates.append(
            _probe_adapter("Anthropic", AnthropicAdapter, os.environ.get("IDENTITY_MODEL", "claude-3-5-sonnet-20241022"))
        )

    # Ollama is always worth trying if a base URL is set or default host is reachable
    if os.environ.get("OPENAI_BASE_URL", "").startswith("http://localhost"):
        from adapters.openai_adapter import OllamaAdapter
        candidates.append(
            _probe_adapter("Ollama (local)", OllamaAdapter, os.environ.get("IDENTITY_MODEL", "llama3.2"))
        )

    # Separate working from failed
    working = [(n, a) for n, a, e in candidates if a is not None]
    failed = [(n, e) for n, a, e in candidates if a is None and e]

    # Print failures so user knows what's wrong
    for name, err in failed:
        print(f"  ⚠ {err}", file=sys.stderr)

    if not working:
        print("  No working adapters found. Set an API key in .env or configure a local model.", file=sys.stderr)
        return None

    if len(working) == 1:
        name, adapter = working[0]
        print(f"  Using {name}")
        return adapter

    # Multiple working adapters — let user choose
    print("\n  Available adapters:")
    for i, (name, _) in enumerate(working, 1):
        print(f"    {i}. {name}")
    while True:
        try:
            choice = input("\n  Select adapter [1]: ").strip()
            if not choice:
                choice = "1"
            idx = int(choice) - 1
            if 0 <= idx < len(working):
                return working[idx][1]
            print(f"  Enter a number between 1 and {len(working)}.")
        except (ValueError, IndexError):
            print(f"  Enter a number between 1 and {len(working)}.")


def _resolve_identity(storage, identity_id_or_name: str) -> Optional[str]:
    """Resolve an identity by ID or name. Tries exact ID first, then scans names."""
    if storage.load(identity_id_or_name, "latest_snapshot"):
        return identity_id_or_name
    for candidate in storage.list_identities():
        data = storage.load(candidate, "latest_snapshot")
        if data:
            modules = data.get("modules") or data
            identity_data = modules.get("identity", modules)
            if identity_data.get("name") == identity_id_or_name:
                return candidate
    return None


def cmd_chat(args: argparse.Namespace) -> int:
    """
    Start an interactive REPL with a loaded identity.

    This is a lightweight terminal client. For production use,
    run the FastAPI service in runtime/main.py instead.
    """
    storage = _get_storage(args)
    resolved = _resolve_identity(storage, args.id)
    if resolved is None:
        print(f"Identity '{args.id}' not found. Run 'create' first.", file=sys.stderr)
        return 1
    if resolved != args.id:
        print(f"  Resolved '{args.id}' → identity {resolved}")

    # Load identity name from storage (handles both SnapshotManager and register() formats)
    identity_data = storage.load(resolved, "latest_snapshot") or {}
    modules = identity_data.get("modules") or identity_data
    identity_spec = modules.get("identity", modules) if isinstance(modules, dict) else modules
    identity_name = identity_spec.get("name", resolved) if isinstance(identity_spec, dict) else resolved
    manager = _get_snapshot_manager(storage, resolved)
    print(f"\n  \u25B6 IdentityOS Chat — {identity_name}")
    print(f"  Type 'exit' or Ctrl-C to quit. Type ':snapshot' to checkpoint.")
    print()

    # Resolve adapter
    adapter = None
    if args.adapter:
        adapter = _get_adapter(args)
    else:
        adapter = _interactive_adapter_select()

    # Lazy-import the orchestrator
    try:
        from runtime.orchestrator import IdentityRuntime, InteractionRequest
        runtime = IdentityRuntime(storage=storage, adapter=adapter)
        runtime.load(resolved)
        session_id = runtime.start_session(resolved)
        runtime_ok = True
    except Exception as e:
        print(f"[warn] Could not initialize runtime ({e}). Running in echo mode.")
        runtime_ok = False

    session_turns = 0
    while True:
        try:
            user_input = input("\nyou> ").strip()
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
            print(f"  [snapshot saved: {snap_id[:8]}]")
            continue
        if user_input == ":history":
            for snap in manager.history():
                print(f"  {snap.summary()}")
            continue

        if runtime_ok:
            try:
                req = InteractionRequest(
                    identity_id=resolved,
                    user_input=user_input,
                    session_id=session_id,
                )
                resp = runtime.process(req)
                print(f"\n{identity_name}> {resp.output}\n")
                print("─" * 40)
            except Exception as e:
                print(f"  [runtime error] {e}")
        else:
            print(f"\n{identity_name}> [echo] {user_input}\n")
            print("─" * 40)

        session_turns += 1

    return 0


def cmd_delete(args: argparse.Namespace) -> int:
    """Delete an identity and all its data from the store."""
    storage = _get_storage(args)
    resolved = _resolve_identity(storage, args.id)
    if resolved is None:
        print(f"Identity '{args.id}' not found.", file=sys.stderr)
        return 1
    if resolved != args.id:
        print(f"  Resolved '{args.id}' → identity {resolved}")

    import shutil
    from pathlib import Path
    store_root = Path(args.store)
    id_dir = store_root / resolved
    if id_dir.exists():
        shutil.rmtree(id_dir)
        print(f"  Identity '{resolved}' deleted.")
        return 0
    print(f"  Identity '{resolved}' not found in store.", file=sys.stderr)
    return 1


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="identity",
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
    p_inspect = sub.add_parser("inspect", help="Inspect identity state (JSON)")
    p_inspect.add_argument("--id", required=True, help="Identity id")
    p_inspect.add_argument("--dashboard", action="store_true", help="Show rich dashboard view")

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
    p_chat.add_argument("--id", required=True, help="Identity id (or name)")
    p_chat.add_argument("--adapter", default="", help="LLM adapter type: openai, anthropic, ollama, openrouter")
    p_chat.add_argument("--adapter-config", default="{}", help="JSON string with adapter config")
    p_chat.add_argument("--model", default="gpt-4o", help="Model adapter to use")

    # list
    p_get = sub.add_parser("list", aliases=["get"], help="List all identities ranked by experience")
    p_get.add_argument("--limit", type=int, default=0, help="Limit rows (0 = unlimited)")

    # delete
    p_delete = sub.add_parser("delete", aliases=["rm"], help="Delete an identity and all its data")
    p_delete.add_argument("--id", required=True, help="Identity id (or name)")

    # playground
    p_play = sub.add_parser(
        "playground",
        help="Launch the IdentityOS Playground (web UI)",
    )
    p_play.add_argument(
        "--port", type=int, default=8000,
        help="Port to serve on (default: 8000)",
    )
    p_play.add_argument(
        "--host", default="0.0.0.0",
        help="Host to bind (default: 0.0.0.0)",
    )

    # explain
    p_explain = sub.add_parser("explain", help="Explain why an identity behaves as it does")
    p_explain.add_argument("id", help="Identity id")
    p_explain.add_argument("question", nargs="+", help="Question to explain")

    # registry
    p_reg = sub.add_parser("registry", help="Identity registry operations")
    reg_sub = p_reg.add_subparsers(dest="registry_command")
    p_reg_list = reg_sub.add_parser("list", help="List identities in registry")
    p_reg_show = reg_sub.add_parser("show", help="Show registry entry details")
    p_reg_show.add_argument("id", help="Identity id")
    p_reg_install = reg_sub.add_parser("install", help="Install identity from registry")
    p_reg_install.add_argument("id", help="Identity id")
    p_reg_pub = reg_sub.add_parser("publish", help="Publish identity spec to registry")
    p_reg_pub.add_argument("path", help="Path to identity spec JSON file")

    # cap
    p_cap = sub.add_parser("cap", help="Capability marketplace operations")
    cap_sub = p_cap.add_subparsers(dest="cap_command")
    cap_sub.add_parser("list", help="List available capabilities")
    p_cap_show = cap_sub.add_parser("show", help="Show capability details")
    p_cap_show.add_argument("id", help="Capability id")
    p_cap_search = cap_sub.add_parser("search", help="Search capabilities")
    p_cap_search.add_argument("query", nargs="+", help="Search query")
    p_cap_install = cap_sub.add_parser("install", help="Install a capability")
    p_cap_install.add_argument("id", help="Capability id")
    p_cap_install.add_argument("--identity", required=True, help="Identity id to install on")
    p_cap_installed = cap_sub.add_parser("installed", help="List installed capabilities")
    p_cap_installed.add_argument("identity", help="Identity id")

    # isp
    p_isp = sub.add_parser("isp", help="Identity Skill Pack operations")
    isp_sub = p_isp.add_subparsers(dest="isp_command")
    isp_sub.add_parser("list", help="List available skill packs")
    p_isp_show = isp_sub.add_parser("show", help="Show skill pack details")
    p_isp_show.add_argument("id", help="Pack id")
    p_isp_install = isp_sub.add_parser("install", help="Install a skill pack")
    p_isp_install.add_argument("id", help="Pack id")
    p_isp_install.add_argument("--identity", required=True, help="Identity id to install on")

    return parser


# ---------------------------------------------------------------------------
# Wrapper functions (defined before COMMAND_MAP)
# ---------------------------------------------------------------------------

def cmd_explain_wrapper(args: argparse.Namespace) -> int:
    question = " ".join(args.question)
    cmd_explain(args.id, question)
    return 0


def cmd_registry_wrapper(args: argparse.Namespace) -> int:
    if args.registry_command == "list":
        cmd_registry_list()
    elif args.registry_command == "show":
        cmd_registry_show(args.id)
    elif args.registry_command == "install":
        cmd_registry_install(args.id)
    elif args.registry_command == "publish":
        cmd_registry_publish(args.path)
    else:
        print("Usage: identity registry <list|show|install|publish>")
        return 1
    return 0


def cmd_cap_wrapper(args: argparse.Namespace) -> int:
    if args.cap_command == "list":
        cmd_cap_list()
    elif args.cap_command == "show":
        cmd_cap_show(args.id)
    elif args.cap_command == "search":
        cmd_cap_search(" ".join(args.query))
    elif args.cap_command == "install":
        cmd_cap_install(args.id, args.identity)
    elif args.cap_command == "installed":
        cmd_cap_list_installed(args.identity)
    else:
        print("Usage: identity cap <list|show|install|search|installed>")
        return 1
    return 0


def cmd_isp_wrapper(args: argparse.Namespace) -> int:
    if args.isp_command == "list":
        cmd_isp_list()
    elif args.isp_command == "show":
        cmd_isp_show(args.id)
    elif args.isp_command == "install":
        cmd_isp_install(args.id, args.identity)
    else:
        print("Usage: identity isp <list|show|install>")
        return 1
    return 0


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
    "list": cmd_get,
    "get": cmd_get,
    "delete": cmd_delete,
    "rm": cmd_delete,
    "playground": cmd_playground,
    "explain": cmd_explain_wrapper,
    "registry": cmd_registry_wrapper,
    "cap": cmd_cap_wrapper,
    "isp": cmd_isp_wrapper,
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
