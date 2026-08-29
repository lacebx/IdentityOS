"""Identity Runtime — Unified FastAPI Service

Routes all interactions through the IdentityRuntime orchestrator,
which runs the full pipeline: policy → context → LLM → evaluate → store.
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from adapters import ChainAdapter
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

# Try reading API keys from .env file if present
_env_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
if os.path.isfile(_env_file):
    try:
        with open(_env_file) as _f:
            for _line in _f:
                _line = _line.strip()
                if _line and not _line.startswith("#") and "=" in _line:
                    _k, _v = _line.split("=", 1)
                    os.environ.setdefault(_k.strip(), _v.strip().strip("\"'"))
    except Exception:
        pass

# Initialize the runtime orchestrator with persistence and optional adapter
_store_path = os.environ.get("IDENTITY_STORE_PATH", ".identity_store")
storage = JSONFileBackend(root_dir=_store_path)

adapter = None
adapter_type = os.environ.get("IDENTITY_ADAPTER", "")

# Build a chain of available adapters, tried in priority order
_candidates: list[Any] = []

# Priority 0: SambaNova (multi-key rotation)
if os.environ.get("SAMBANOVA_API_KEY"):
    try:
        from adapters.sambanova_adapter import SambaNovaAdapter
        model = os.environ.get("IDENTITY_MODEL", "DeepSeek-V3.1")
        _candidates.append(SambaNovaAdapter(model=model))
        logger.info("Added SambaNova adapter to chain (model=%s)", model)
    except Exception as e:
        logger.warning("Failed to initialize SambaNova adapter: %s", e)

# Priority 1: Groq (multi-key rotation)
_groq_keys = [os.environ.get(k) for k in ("GROQ_API_KEY", "GROQ_API_KEY_2", "GROQ_API_KEY_3",
                                           "GROQ_API_KEY_4", "GROQ_API_KEY_5", "GROQ_API_KEY_6")]
if any(k for k in _groq_keys if k and "PLACEHOLDER" not in k):
    try:
        from adapters.groq_adapter import GroqAdapter
        model = os.environ.get("IDENTITY_MODEL", "openai/gpt-oss-120b")
        _candidates.append(GroqAdapter(model=model))
        logger.info("Added Groq adapter to chain (model=%s)", model)
    except Exception as e:
        logger.warning("Failed to initialize Groq adapter: %s", e)

# Priority 2: Explicit IDENTITY_ADAPTER env var
if adapter_type:
    try:
        from adapters import get_adapter
        adapter_config: dict[str, Any] = {}
        adapter_config_str = os.environ.get("IDENTITY_ADAPTER_CONFIG", "{}")
        if adapter_config_str:
            adapter_config = json.loads(adapter_config_str)
        _candidates.append(get_adapter(adapter_type, **adapter_config))
        logger.info("Added explicit adapter: %s (model=%s)", adapter_type, adapter_config.get("model", "default"))
    except Exception as e:
        logger.warning("Failed to initialize adapter '%s': %s", adapter_type, e)

# Priority 3: Cerebras (multi-key rotation)
_cerebras_keys = [os.environ.get(k) for k in ("CEREBRAS_API_KEY", "CEREBRAS_API_KEY_2",
                                               "CEREBRAS_API_KEY_3", "CEREBRAS_API_KEY_4")]
if any(k for k in _cerebras_keys if k):
    try:
        from adapters.cerebras_adapter import CerebrasAdapter
        _candidates.append(CerebrasAdapter())
        logger.info("Added Cerebras adapter to chain")
    except Exception as e:
        logger.warning("Failed to initialize Cerebras adapter: %s", e)

# Priority 4: OpenAI fallback
if os.environ.get("OPENAI_API_KEY"):
    try:
        from adapters.openai_adapter import OpenAIAdapter
        _candidates.append(OpenAIAdapter(model=os.environ.get("IDENTITY_MODEL", "gpt-4o")))
        logger.info("Added OpenAI adapter to chain")
    except Exception as e:
        logger.warning("Failed to initialize OpenAI adapter: %s", e)

if _candidates:
    if len(_candidates) == 1:
        adapter = _candidates[0]
    else:
        adapter = ChainAdapter(_candidates)
        logger.info("Chained %d adapters: %s", len(_candidates), adapter)

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

class CreateIdentityRequest(BaseModel):
    identity_id: str
    name: str
    identity_class: str = "agent"
    persona: str = ""
    role: str = ""

class ProcessRequest(BaseModel):
    message: str
    identity_id: str
    user_id: str
    session_id: Optional[str] = None

class ProcessResponse(BaseModel):
    output: str
    identity_id: str
    user_id: str
    session_id: str
    policy_passed: bool
    eval_score: Optional[float] = None
    session_mode: str = "normal"
    timings_ms: Dict[str, float] = Field(default_factory=dict)


# --- Endpoints ---

@app.get("/")
async def root():
    return {
        "service": "Identity Runtime",
        "version": "2.0.0",
        "status": "running",
        "tagline": "Every AI deserves its own soul.",
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/process", response_model=ProcessResponse)
async def process(req: ProcessRequest):
    """
    Full pipeline: resolve identity → policy check → compose context →
    (adapter) → policy check → evaluate → store → respond.

    Intended for SDK / agentic use where the caller wants the runtime
    to manage the entire lifecycle.
    """
    session_id = req.session_id or runtime.start_session(
        req.identity_id,
        user_id=req.user_id,
    )

    # Auto-load identity from disk if not already in memory.
    # The /identity POST endpoint writes to disk but does not register
    # with the runtime, so we must load on first use.
    if not runtime.identity_store.get(req.identity_id):
        runtime.load(req.identity_id)

    request = InteractionRequest(
        identity_id=req.identity_id,
        user_id=req.user_id,
        user_input=req.message,
        session_id=session_id,
    )

    result: InteractionResponse = runtime.process(request)

    if not result.policy_passed and "not found" in result.output.lower():
        raise HTTPException(status_code=404, detail=result.output)

    return ProcessResponse(
        output=result.output,
        identity_id=result.identity_id,
        user_id=result.user_id,
        session_id=session_id,
        policy_passed=result.policy_passed,
        eval_score=result.eval_score,
        session_mode=runtime.get_session_mode(session_id).value,
        timings_ms=result.metadata.get("timings_ms", {}),
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
    user_id = runtime._resolved_user_id(req.identity_id, req.user_id)
    ctx = runtime.context_composer.compose(
        identity=identity,
        memory_store=runtime.memory_store,
        skill_registry=runtime.skill_registry,
        goal_engine=runtime.goal_engine,
        identity_graph=runtime.identity_graph,
        user_profile=runtime._get_user_profile(req.identity_id, user_id),
        user_id=user_id,
        query=req.message,
        session_id=session_id,
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
        user_id=req.user_id,
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


@app.post("/identity")
async def create_identity(req: CreateIdentityRequest):
    """Create a new identity."""
    from identityos import Identity
    identity = Identity.create(
        name=req.name,
        identity_id=req.identity_id,
        identity_class=req.identity_class,
        persona=req.persona,
        role=req.role,
        storage_path=os.environ.get("IDENTITY_STORE_PATH", ".identity_store"),
    )
    logger.info(f"Identity created via API: {req.identity_id} ({req.name})")
    return {"id": identity.id, "name": identity.name, "status": "created"}


@app.get("/identity/{identity_id}")
async def get_identity(identity_id: str):
    """Get a loaded identity spec by ID."""
    identity = runtime.load(identity_id)
    if not identity:
        raise HTTPException(status_code=404, detail=f"Identity '{identity_id}' not found")
    return identity.to_dict()


@app.get("/identity")
async def list_identities():
    """List all available identity IDs (loaded + stored)."""
    loaded = {s.id for s in runtime.list_identities()}
    stored = set(storage.list_identities())
    all_ids = sorted(loaded | stored)
    return {"identities": all_ids}


@app.get("/memories/{user_id}/{identity_id}", response_model=MemoriesResponse)
async def get_memories(user_id: str, identity_id: str, limit: int = 50):
    """Get stored memories for an identity."""
    memories = runtime.memory_store.by_user(
        identity_id=identity_id,
        user_id=user_id,
    )[:limit]
    return MemoriesResponse(
        identity_id=identity_id,
        user_id=user_id,
        memories=[m.to_dict() for m in memories],
        total=len(memories),
    )


@app.delete("/memories/{user_id}/{identity_id}")
async def clear_memories(user_id: str, identity_id: str):
    """Clear one user's memories without erasing other users or shared state."""
    deleted = runtime.memory_store.clear_user(identity_id, user_id)
    if runtime._storage is not None:
        runtime._storage.delete_user_memories(identity_id, user_id)
    return {"deleted": deleted, "message": "Memories cleared."}


@app.get("/session/{session_id}")
async def get_session(session_id: str):
    """Inspect session state (mode, active identity)."""
    identity_id = runtime._sessions.get(session_id)
    user_id = runtime._session_users.get(session_id)
    mode = runtime.get_session_mode(session_id)
    return {
        "session_id": session_id,
        "identity_id": identity_id,
        "user_id": user_id,
        "session_mode": mode.value,
        "is_isolated": mode.value != "normal",
    }


if __name__ == "__main__":
    uvicorn.run("runtime.main:app", host="0.0.0.0", port=8000, reload=False)
