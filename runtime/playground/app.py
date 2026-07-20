"""
IdentityOS Playground — a first-class developer tool that visualizes
the entire runtime architecture in real time.

Usage:
    python -m runtime.playground
    # -> http://localhost:8000/playground
"""

from __future__ import annotations

import queue
import threading
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader, select_autoescape

import os

from runtime.orchestrator import IdentityRuntime, InteractionRequest
from runtime.persistence import JSONFileBackend
from runtime.event_bus import EventType, Event
from core.cognitive_engine import ComposedContext
from core.identity import create_identity, IdentitySpec
from core.evaluation import register_default_criteria
from core.goals import Goal, GoalPriority, GoalScope

import datetime as _dt

HERE = str(Path(__file__).parent)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _context_sections(ctx: ComposedContext) -> list[dict]:
    """Extract structured sections from a composed context."""
    sections = []
    blocks = [
        ("Identity", ctx.identity_block, "#58a6ff"),
        ("Memory", ctx.memory_block, "#bc8cff"),
        ("Skills", ctx.skills_block, "#d29922"),
        ("Goals", ctx.goals_block, "#3fb950"),
        ("Relationships", ctx.relationships_block, "#f0883e"),
        ("Motivations", ctx.motivations_block, "#f85149"),
        ("Timeline", ctx.timeline_block, "#58a6ff"),
    ]
    for name, content, color in blocks:
        if content:
            sections.append({
                "name": name,
                "content": content,
                "color": color,
                "chars": len(content),
            })
    for key, content in ctx.custom_blocks.items():
        if content:
            sections.append({
                "name": key,
                "content": content,
                "color": "#8b949e",
                "chars": len(content),
            })
    return sections


# ---------------------------------------------------------------------------
# Pipeline event capture
# ---------------------------------------------------------------------------

@dataclass
class PipelineEvent:
    stage: str
    label: str
    data: dict = field(default_factory=dict)

STAGE_MAP: dict[EventType, PipelineEvent] = {
    EventType.MESSAGE_RECEIVED: PipelineEvent("receive", "Message Received"),
    EventType.POLICY_TRIGGERED: PipelineEvent("policy_in", "Policy Check"),
    EventType.CONTEXT_COMPOSED: PipelineEvent("compose", "Context Composition"),
    EventType.MODEL_REQUESTED: PipelineEvent("adapter", "Adapter Call"),
    EventType.MODEL_RESPONDED: PipelineEvent("adapter", "Adapter Response"),
    EventType.EVALUATION_COMPLETED: PipelineEvent("evaluate", "Evaluation"),
    EventType.EXPERIENCE_RECORDED: PipelineEvent("memory", "Memory Storage"),
    EventType.LIFE_EVENT_RECORDED: PipelineEvent("timeline", "Timeline Update"),
    EventType.RESPONSE_GENERATED: PipelineEvent("response", "Response"),
}


def _capture_pipeline_events(
    runtime: IdentityRuntime, request: InteractionRequest
) -> tuple[List[PipelineEvent], Optional[str], Optional[ComposedContext]]:
    """Run process() and capture all EventBus events as PipelineEvents."""
    events_queue: queue.Queue[Event] = queue.Queue()
    done_event = threading.Event()
    captured: List[PipelineEvent] = []
    output: Optional[str] = None
    context_used: Optional[ComposedContext] = None

    def handler(event: Event) -> None:
        events_queue.put(event)

    runtime.event_bus.subscribe_all(handler)

    def run() -> None:
        nonlocal output, context_used
        try:
            resp = runtime.process(request)
            output = resp.output
            context_used = resp.context_used
        except Exception as e:
            output = f"[Runtime Error] {e}"
        finally:
            done_event.set()

    thread = threading.Thread(target=run, daemon=True)
    thread.start()

    while thread.is_alive() or not events_queue.empty():
        try:
            event = events_queue.get(timeout=0.05)
        except queue.Empty:
            continue

        pe = STAGE_MAP.get(event.event_type)
        if pe is None:
            continue

        payload = event.payload if hasattr(event, 'payload') else {}

        if event.event_type == EventType.POLICY_TRIGGERED:
            scope = payload.get("scope", "")
            if scope == "input":
                pe = PipelineEvent("policy_in", "Policy Check (Input)")
            elif scope == "output":
                pe = PipelineEvent("policy_out", "Policy Check (Output)")
            else:
                continue

        data: dict = {}
        if event.event_type == EventType.MESSAGE_RECEIVED:
            data["content"] = str(payload.get("content", ""))[:80]
        elif event.event_type == EventType.POLICY_TRIGGERED:
            data["allowed"] = payload.get("allowed", True)
            data["policies"] = payload.get("policies_applied", [])
        elif event.event_type == EventType.CONTEXT_COMPOSED:
            data["token_estimate"] = payload.get("token_estimate", 0)
            data["section_count"] = 0
            data["sections"] = []
        elif event.event_type == EventType.MODEL_REQUESTED:
            data["model"] = payload.get("model", "unknown")
        elif event.event_type == EventType.MODEL_RESPONDED:
            data["response_length"] = payload.get("response_length", 0)
            data["latency_ms"] = payload.get("latency_ms", 0)
        elif event.event_type == EventType.EVALUATION_COMPLETED:
            data["score"] = payload.get("overall_score", 0.0)
            data["passed"] = payload.get("passed", True)
            data["criteria_count"] = payload.get("criteria_count", 0)
        elif event.event_type == EventType.EXPERIENCE_RECORDED:
            data["memory_type"] = payload.get("memory_type", "episodic")
            data["memory_id"] = str(payload.get("memory_id", ""))[:8]
            data["memory_content"] = str(payload.get("content", ""))[:60]
        elif event.event_type == EventType.LIFE_EVENT_RECORDED:
            data["description"] = str(payload.get("description", ""))[:60]
            data["title"] = str(payload.get("title", ""))[:40]

        captured.append(PipelineEvent(stage=pe.stage, label=pe.label, data=data))

    # Post-process: enrich compose event with section info from context_used
    if context_used:
        sections = _context_sections(context_used)
        for pe in captured:
            if pe.stage == "compose":
                pe.data["sections"] = [s["name"] for s in sections]
                pe.data["section_count"] = len(sections)
                break

    # Enrich memory events with content from context_used
    if context_used:
        mem_block = context_used.memory_block
        if mem_block:
            for pe in captured:
                if pe.stage == "memory":
                    pe.data["memory_retrieved"] = True
                    mem_lines = [l.strip() for l in mem_block.split('\n') if l.strip()]
                    pe.data["memory_block_snippets"] = [l[:80] for l in mem_lines[:5]]

    # Add synthetic stages with runtime data
    identity_id = request.identity_id
    rel_count = len(runtime.identity_graph.get_relationships(identity_id)) if identity_id else 0
    captured.append(PipelineEvent("relationship", "Relationship Update", {
        "edge_count": rel_count,
    }))

    persist_ns = []
    if hasattr(runtime, '_storage') and runtime._storage:
        try:
            persist_ns = runtime._storage.list_namespaces(identity_id) if identity_id else []
        except Exception:
            pass
    captured.append(PipelineEvent("persist", "Persistence", {
        "namespaces": len(persist_ns),
    }))

    # Ensure we have a response event
    if output is not None:
        captured.append(PipelineEvent("response", "Response", {
            "output": output[:120],
            "output_length": len(output),
        }))

    return captured, output, context_used


# ---------------------------------------------------------------------------
# Persistent runtime manager
# ---------------------------------------------------------------------------

class RuntimeManager:
    """Manages a single IdentityRuntime instance per identity."""

    def __init__(self):
        self._runtime: Optional[IdentityRuntime] = None
        self._sessions: Dict[str, str] = {}
        self._storage = JSONFileBackend(root_dir=".identity_store")

        # Read adapter config from env vars (same convention as runtime/main.py)
        self._adapter_name: Optional[str] = os.environ.get("IDENTITY_ADAPTER") or None
        self._adapter_model: Optional[str] = None
        self._adapter_kwargs: dict = {}
        adapter_config_str = os.environ.get("IDENTITY_ADAPTER_CONFIG", "{}")
        if adapter_config_str:
            try:
                import json as _json
                self._adapter_kwargs = _json.loads(adapter_config_str)
                self._adapter_model = self._adapter_kwargs.get("model")
            except Exception:
                self._adapter_kwargs = {}

    def get_or_create_runtime(self) -> IdentityRuntime:
        if self._runtime is not None:
            return self._runtime
        rt = IdentityRuntime(storage=self._storage)
        register_default_criteria(rt.evaluation_engine)
        rt.load_persisted()
        self._runtime = rt
        return rt

    def restart(self) -> None:
        self._runtime = None
        self.get_or_create_runtime()

    def get_runtime(self) -> IdentityRuntime:
        rt = self.get_or_create_runtime()
        return rt

    def list_identities(self) -> List[str]:
        rt = self.get_or_create_runtime()
        specs = rt.identity_store.list_all()
        ids = [s.id for s in specs]
        stored = self._storage.list_identities()
        for sid in stored:
            if sid not in ids:
                ids.append(sid)
        return sorted(set(ids))

    def create_identity(
        self,
        name: str,
        identity_id: Optional[str] = None,
        persona: Optional[str] = None,
        system_prompt: Optional[str] = None,
        adapter: Optional[str] = None,
        model: Optional[str] = None,
    ) -> IdentitySpec:
        rt = self.get_or_create_runtime()
        spec = create_identity(
            name=name,
            identity_id=identity_id,
            persona=persona,
            system_prompt=system_prompt,
        )
        rt.register(spec)
        if adapter:
            self._adapter_name = adapter
            self._adapter_model = model
            self._maybe_configure_adapter(rt)
        return spec

    def _maybe_configure_adapter(self, rt: IdentityRuntime) -> None:
        if self._adapter_name and rt.adapter is None:
            try:
                from adapters import get_adapter
                kwargs = dict(self._adapter_kwargs)
                model = self._adapter_model or kwargs.get("model")
                if model:
                    kwargs["model"] = model
                rt.adapter = get_adapter(self._adapter_name, **kwargs)
            except Exception as exc:
                import sys
                print(f"[playground] adapter config failed: {exc}", file=sys.stderr)

    def get_identity_data(self, identity_id: str) -> dict:
        rt = self.get_or_create_runtime()
        spec = rt.identity_store.get(identity_id)

        identities = rt.identity_store.list_all()
        for s in identities:
            if s.id not in [s2.id for s2 in rt.identity_store.list_all()]:
                pass

        identity_dict = spec.to_dict() if spec else {}
        if not identity_dict and self._storage:
            data = self._storage.load(identity_id, "latest_snapshot")
            if data:
                identity_dict = data.get("modules", {}).get("identity", data)

        # Memories
        mems = rt.memory_store.by_identity(identity_id) if identity_id else []
        mem_dicts = [m.to_dict() for m in mems]

        # Timeline
        tl = rt.timeline_registry.get(identity_id)
        tl_events = []
        if tl:
            tl_events = [
                {
                    "id": e.id,
                    "event_type": e.event_type.value,
                    "title": e.title,
                    "description": e.description,
                    "significance": e.significance,
                    "occurred_at": e.occurred_at.isoformat(),
                }
                for e in tl.events()
            ]

        # Goals
        goals = rt.goal_engine.active() if identity_id else []
        goal_dicts = [
            {
                "id": g.id,
                "title": g.title,
                "description": g.description,
                "status": g.status.value,
                "priority": g.priority.name,
                "progress": g.progress,
                "created_at": g.created_at.isoformat(),
            }
            for g in goals
        ]

        # Relationships
        edges = rt.identity_graph.get_relationships(identity_id) if identity_id else []
        edge_dicts = [
            {
                "id": e.id,
                "source_id": e.source_id,
                "target_id": e.target_id,
                "edge_type": e.edge_type.value,
                "trust_level": e.trust_level.value,
                "strength": e.strength,
                "bidirectional": e.bidirectional,
                "interaction_count": e.interaction_count,
                "established_at": e.established_at.isoformat(),
            }
            for e in edges
        ]

        # Adapter info
        adapter_info = None
        if rt.adapter:
            adapter_info = {
                "type": type(rt.adapter).__name__,
                "model": getattr(rt.adapter, "model", "unknown"),
                "streaming": getattr(rt.adapter, "streaming", False),
            }

        # Current context (structured)
        current_context = ""
        context_sections = []
        if spec:
            try:
                from core.cognitive_engine import ComposedContext as CC
                ctx = rt.context_composer.compose(
                    identity=spec,
                    memory_store=rt.memory_store,
                    skill_registry=rt.skill_registry,
                    goal_engine=rt.goal_engine,
                    identity_graph=rt.identity_graph,
                    motivation_engine=rt.motivation_engine,
                    timeline_registry=rt.timeline_registry,
                    query="",
                    top_k_memories=5,
                )
                current_context = ctx.render()
                context_sections = _context_sections(ctx)
            except Exception:
                current_context = "(error composing context)"

        # Eval history
        eval_history = rt.evaluation_engine.history(identity_id) if identity_id else []
        last_eval = None
        if eval_history:
            last = eval_history[-1]
            last_eval = {
                "score": last.overall_score,
                "passed": last.passed,
                "details": last.summarize() if hasattr(last, 'summarize') else "",
                "criteria": [
                    {
                        "name": r.criterion_name,
                        "score": r.score,
                        "outcome": r.outcome.value,
                    }
                    for r in last.records
                ],
            }

        # Persistence files
        persist_files = []
        if self._storage:
            ns = self._storage.list_namespaces(identity_id) if identity_id else []
            persist_files = sorted(ns)

        # Evolution metrics + identity mutation data
        evolution = {
            "interaction_count": len([e for e in tl_events if e.get("event_type") in ("milestone", "creation")]) if tl_events else 0,
            "memory_count": len(mem_dicts),
            "relationship_count": len(edge_dicts),
            "goal_count": len(goal_dicts),
            "timeline_count": len(tl_events) if tl_events else 0,
        }
        if identity_dict and identity_dict.get("created_at"):
            try:
                created = _dt.fromisoformat(identity_dict["created_at"])
                now = _dt.now(_dt.timezone.utc).replace(tzinfo=None)
                delta = now - created
                evolution["age_seconds"] = int(delta.total_seconds())
                evolution["created_at"] = created.isoformat()
            except Exception:
                pass

        # Identity evolution data from spec
        identity_evolution = {
            "preferences": identity_dict.get("preferences", {}),
            "beliefs": identity_dict.get("beliefs", {}),
            "likes": identity_dict.get("likes", []),
            "dislikes": identity_dict.get("dislikes", []),
            "habits": identity_dict.get("habits", []),
            "communication_tendencies": identity_dict.get("communication_tendencies", {}),
            "mutation_history": identity_dict.get("mutation_history", []),
            "traits": identity_dict.get("traits", []),
        }

        return {
            "identity": identity_dict,
            "memories": mem_dicts,
            "timeline": tl_events,
            "goals": goal_dicts,
            "relationships": edge_dicts,
            "adapter": adapter_info,
            "evaluation": last_eval,
            "persistence": persist_files,
            "context": current_context,
            "context_sections": context_sections,
            "evolution": evolution,
            "identity_evolution": identity_evolution,
        }

    def process_message(self, identity_id: str, user_input: str) -> dict:
        rt = self.get_or_create_runtime()
        self._maybe_configure_adapter(rt)

        # Ensure identity is loaded
        spec = rt.identity_store.get(identity_id)
        if not spec:
            loaded = rt.load(identity_id)
            if not loaded:
                return {"error": f"Identity '{identity_id}' not found."}

        # Ensure session
        session_id = self._sessions.get(identity_id)
        if not session_id:
            session_id = rt.start_session(identity_id)
            self._sessions[identity_id] = session_id

        # Add a default goal if none exist
        if len(rt.goal_engine) == 0 and identity_id:
            rt.goal_engine.add(Goal(
                title="Learn and grow",
                priority=GoalPriority.MEDIUM,
                scope=GoalScope.PERSISTENT,
            ))

        request = InteractionRequest(
            identity_id=identity_id,
            user_input=user_input,
            session_id=session_id,
        )
        events, output, context_used = _capture_pipeline_events(rt, request)

        context_text = ""
        context_sections = []
        if context_used:
            context_text = context_used.render()
            context_sections = _context_sections(context_used)

        return {
            "output": output or "",
            "events": [{"stage": e.stage, "label": e.label, "data": e.data} for e in events],
            "context": context_text or "",
            "context_sections": context_sections,
        }

    def restart_identity(self, identity_id: str) -> dict:
        rt = self.get_or_create_runtime()
        # Capture pre-restart state
        mems_before = len(rt.memory_store.by_identity(identity_id))
        tl_before = rt.timeline_registry.get(identity_id)
        tl_count = len(tl_before.events()) if tl_before else 0
        goals_before = len(rt.goal_engine.active())
        rels_before = len(rt.identity_graph.get_relationships(identity_id))

        # Restart
        self.restart()
        new_rt = self.get_or_create_runtime()
        new_rt.load(identity_id)
        new_rt._load_persisted_memories(identity_id)

        # Verify
        mems_after = len(new_rt.memory_store.by_identity(identity_id))
        tl_after = new_rt.timeline_registry.get(identity_id)
        tl_count_after = len(tl_after.events()) if tl_after else 0
        goals_after = len(new_rt.goal_engine.active())
        rels_after = len(new_rt.identity_graph.get_relationships(identity_id))

        return {
            "memories_restored": mems_after >= mems_before,
            "memories_count": mems_after,
            "timeline_restored": tl_count_after >= tl_count,
            "timeline_count": tl_count_after,
            "goals_restored": goals_after >= goals_before,
            "goals_count": goals_after,
            "relationships_restored": rels_after >= rels_before,
            "relationships_count": rels_after,
        }


manager = RuntimeManager()

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(title="IdentityOS Playground")

_jinja_env = Environment(
    loader=FileSystemLoader(HERE + "/templates"),
    autoescape=select_autoescape(["html", "xml"]),
)

app.mount("/playground/static", StaticFiles(directory=HERE + "/static"), name="playground_static")


@app.get("/playground", response_class=HTMLResponse)
async def playground_page(request: Request):
    template = _jinja_env.get_template("playground.html")
    html = template.render(request=request)
    return HTMLResponse(html)


@app.get("/playground/api/identities")
async def api_list_identities():
    ids = manager.list_identities()
    return JSONResponse(ids)


@app.post("/playground/api/identities")
async def api_create_identity(body: dict):
    identity_id = body.get("identity_id")
    name = body.get("name", "New Identity")
    persona = body.get("persona")
    system_prompt = body.get("system_prompt")
    adapter = body.get("adapter")
    model = body.get("model")
    spec = manager.create_identity(
        name=name,
        identity_id=identity_id,
        persona=persona,
        system_prompt=system_prompt,
        adapter=adapter,
        model=model,
    )
    return JSONResponse({"id": spec.id, "name": spec.name})


@app.get("/playground/api/identity/{identity_id}")
async def api_get_identity(identity_id: str):
    data = manager.get_identity_data(identity_id)
    return JSONResponse(data)


@app.post("/playground/api/chat")
async def api_chat(body: dict):
    identity_id = body.get("identity_id", "")
    user_input = body.get("user_input", "")
    if not identity_id:
        return JSONResponse({"error": "identity_id is required"}, status_code=400)
    if not user_input:
        return JSONResponse({"error": "user_input is required"}, status_code=400)
    result = manager.process_message(identity_id, user_input)
    return JSONResponse(result)


@app.post("/playground/api/configure-adapter")
async def api_configure_adapter(body: dict):
    adapter_type = body.get("adapter", "")
    if not adapter_type:
        return JSONResponse({"error": "adapter type is required"}, status_code=400)

    model = body.get("model") or ""
    manager._adapter_name = adapter_type
    manager._adapter_model = model
    manager._adapter_kwargs = {
        k: v for k, v in body.items()
        if k in ("api_key", "base_url", "organization", "temperature", "max_tokens", "model")
        and v is not None
    }
    # Ensure model is always set
    if model and "model" not in manager._adapter_kwargs:
        manager._adapter_kwargs["model"] = model

    rt = manager.get_or_create_runtime()
    rt.adapter = None
    manager._maybe_configure_adapter(rt)

    configured = rt.adapter is not None
    actual_model = getattr(rt.adapter, "model", None) if rt.adapter else model or "default"
    msg = "ok"
    if not configured:
        msg = (
            f"Adapter '{adapter_type}' created but may fail at runtime. "
            "Set the corresponding env var (e.g. OPENAI_API_KEY, ANTHROPIC_API_KEY, "
            "OPENROUTER_API_KEY) or pass api_key explicitly."
        )
    return JSONResponse({
        "configured": configured,
        "adapter": adapter_type,
        "model": actual_model,
        "message": msg,
    })


@app.post("/playground/api/restart")
async def api_restart(body: dict):
    identity_id = body.get("identity_id", "")
    result = manager.restart_identity(identity_id)
    return JSONResponse(result)
