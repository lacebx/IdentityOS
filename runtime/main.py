"""Identity Runtime — Unified FastAPI Service

Routes all interactions through the IdentityRuntime orchestrator,
which runs the full pipeline: policy → context → LLM → evaluate → store.
"""

import json
import logging
import os
from typing import Any, List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from core.evaluation import register_default_criteria
from runtime.orchestrator import IdentityRuntime, InteractionRequest, InteractionResponse
from runtime.persistence import JSONFileBackend

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Identity Runtime API",
    description="Portable AI identity layer — own your AI's soul, not just its prompt.",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize the runtime orchestrator with persistence and optional adapter
storage = JSONFileBackend(root_dir=".identity_store")

adapter_type = os.environ.get("IDENTITY_ADAPTER", "")
adapter = None
if adapter_type:
    try:
        from adapters import get_adapter
        adapter_config: dict[str, Any] = {}
        adapter_config_str = os.environ.get("IDENTITY_ADAPTER_CONFIG", "{}")
        if adapter_config_str:
            adapter_config = json.loads(adapter_config_str)
        adapter = get_adapter(adapter_type, **adapter_config)
        logger.info(f"Using adapter: {adapter_type} (model={adapter_config.get('model', 'default')})")
    except Exception as e:
        logger.warning(f"Failed to initialize adapter '{adapter_type}': {e}")

runtime = IdentityRuntime(storage=storage, adapter=adapter)
register_default_criteria(runtime.evaluation_engine)
loaded = runtime.load_persisted()
if loaded:
    logger.info(f"Loaded {loaded} persisted identity/ies from .identity_store/")


# --- Request / Response Models ---

class ContextRequest(BaseModel):
    message: str
    identity_id: str
    user_id: str
    session_id: Optional[str] = None

class ContextResponse(BaseModel):
    augmented_context: str
    identity_name: str
    memories_used: int
    session_id: str

class EvaluateRequest(BaseModel):
    message: str
    response: str
    identity_id: str
    user_id: str
    session_id: Optional[str] = None

class EvaluateResponse(BaseModel):
    memories_stored: int
    summary: str
    tags: List[str]

class MemoriesResponse(BaseModel):
    identity_id: str
    user_id: str
    memories: List[dict]
    total: int

class ProcessRequest(BaseModel):
    message: str
    identity_id: str
    user_id: str
    session_id: Optional[str] = None

class ProcessResponse(BaseModel):
    output: str
    identity_id: str
    session_id: str
    policy_passed: bool
    eval_score: Optional[float] = None


# --- Endpoints ---

@app.get("/")
def root():
    return {
        "service": "Identity Runtime",
        "version": "2.0.0",
        "status": "running",
        "tagline": "Every AI deserves its own soul.",
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/process", response_model=ProcessResponse)
async def process(req: ProcessRequest):
    """
    Full pipeline: resolve identity → policy check → compose context →
    (adapter) → policy check → evaluate → store → respond.

    Intended for SDK / agentic use where the caller wants the runtime
    to manage the entire lifecycle.
    """
    session_id = req.session_id or runtime.start_session(req.identity_id)

    request = InteractionRequest(
        identity_id=req.identity_id,
        user_input=req.message,
        session_id=session_id,
    )

    result: InteractionResponse = runtime.process(request)

    if not result.policy_passed and "not found" in result.output.lower():
        raise HTTPException(status_code=404, detail=result.output)

    return ProcessResponse(
        output=result.output,
        identity_id=result.identity_id,
        session_id=session_id,
        policy_passed=result.policy_passed,
        eval_score=result.eval_score,
    )


@app.post("/context", response_model=ContextResponse)
async def get_context(req: ContextRequest):
    """
    Compose identity context (without invoking an LLM).
    Useful when the caller manages their own LLM call externally.
    """
    identity = runtime.load(req.identity_id)
    if not identity:
        raise HTTPException(status_code=404, detail=f"Identity '{req.identity_id}' not found")

    session_id = req.session_id or f"{req.user_id}_{req.identity_id}"
    ctx = runtime.context_composer.compose(
        identity=identity,
        memory_store=runtime.memory_store,
        skill_registry=runtime.skill_registry,
        goal_engine=runtime.goal_engine,
        identity_graph=runtime.identity_graph,
        query=req.message,
    )

    memories_used = ctx.memory_block.count("\n  [") if ctx.memory_block else 0

    logger.info(f"Context built for identity={req.identity_id} user={req.user_id} memories={memories_used}")

    return ContextResponse(
        augmented_context=ctx.render(),
        identity_name=identity.name,
        memories_used=memories_used,
        session_id=session_id,
    )


@app.post("/evaluate", response_model=EvaluateResponse)
async def evaluate(req: EvaluateRequest):
    """
    Evaluate an exchange (user message + LLM response) and decide
    what's worth remembering. Called after every LLM response.

    Uses the same classification and storage pipeline as process()
    via IdentityRuntime._extract_and_store_semantic_memory().
    """
    identity = runtime.load(req.identity_id)
    if not identity:
        raise HTTPException(status_code=404, detail=f"Identity '{req.identity_id}' not found")

    session_id = req.session_id or f"{req.user_id}_{req.identity_id}"

    report = runtime.evaluation_engine.evaluate(
        identity_id=req.identity_id,
        interaction_id=session_id,
        input_data=req.message,
        output_data=req.response,
    )

    stored = runtime._extract_and_store_semantic_memory(
        user_input=req.message,
        output=req.response,
        identity_id=req.identity_id,
        session_id=session_id,
    )

    if stored:
        mem_type = stored.tags[-1] if len(stored.tags) > 1 else "general"
        logger.info(f"Stored {mem_type} memory for {req.identity_id}: {req.message[:60]}")
        return EvaluateResponse(
            memories_stored=1,
            summary=f"Stored {mem_type}: {req.message[:100]}",
            tags=[mem_type],
        )

    return EvaluateResponse(
        memories_stored=0,
        summary=f"Not memorable (score={report.overall_score:.2f})",
        tags=[],
    )


@app.get("/identity/{identity_id}")
def get_identity(identity_id: str):
    """Get a loaded identity spec by ID."""
    identity = runtime.load(identity_id)
    if not identity:
        raise HTTPException(status_code=404, detail=f"Identity '{identity_id}' not found")
    return identity.to_dict()


@app.get("/identity")
def list_identities():
    """List all available identity IDs (loaded + stored)."""
    loaded = {s.id for s in runtime.list_identities()}
    stored = set(storage.list_identities())
    all_ids = sorted(loaded | stored)
    return {"identities": all_ids}


@app.get("/memories/{user_id}/{identity_id}", response_model=MemoriesResponse)
def get_memories(user_id: str, identity_id: str, limit: int = 50):
    """Get stored memories for an identity."""
    memories = runtime.memory_store.by_identity(identity_id=identity_id)[:limit]
    return MemoriesResponse(
        identity_id=identity_id,
        user_id=user_id,
        memories=[m.to_dict() for m in memories],
        total=len(memories),
    )


@app.delete("/memories/{user_id}/{identity_id}")
def clear_memories(user_id: str, identity_id: str):
    """Clear all memories for an identity."""
    deleted = runtime.memory_store.clear_identity(identity_id)
    return {"deleted": deleted, "message": "Memories cleared."}


if __name__ == "__main__":
    uvicorn.run("runtime.main:app", host="0.0.0.0", port=8765, reload=False)
