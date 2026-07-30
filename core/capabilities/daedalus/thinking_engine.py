from __future__ import annotations

"""
Daedalus Thinking Engine — connects Daedalus capabilities to LLM providers.

Provides a unified interface for Daedalus skills to call LLMs. Handles:
- Multi-provider support (OpenAI, Groq, Anthropic, Cerebras, SambaNova, OpenRouter)
- Automatic key rotation when one provider hits rate limits
- Context building from evidence, memory, and diff data
- Structured output parsing for review reports
"""

import json
import logging
import os
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ── Provider configuration ─────────────────────────────────────────────

PROVIDER_CONFIGS: Dict[str, Dict[str, Any]] = {
    "groq": {
        "env_keys": ["GROQ_API_KEY", "GROQ_API_KEY_2", "GROQ_API_KEY_3", "GROQ_API_KEY_4"],
        "base_url": "https://api.groq.com/openai/v1",
        "default_model": "llama-3.3-70b-versatile",
    },
    "openai": {
        "env_keys": ["OPENAI_API_KEY"],
        "base_url": None,
        "default_model": "gpt-4o",
    },
    "cerebras": {
        "env_keys": ["CEREBRAS_API_KEY", "CEREBRAS_API_KEY_2"],
        "base_url": "https://inference.cerebras.ai/v1",
        "default_model": "llama3.1-70b",
    },
    "sambanova": {
        "env_keys": ["SAMBANOVA_API_KEY"],
        "base_url": "https://api.sambanova.ai/v1",
        "default_model": "Meta-Llama-3.1-70B-Instruct",
    },
    "anthropic": {
        "env_keys": ["ANTHROPIC_API_KEY"],
        "base_url": None,
        "default_model": "claude-3-5-sonnet-20241022",
    },
    "openrouter": {
        "env_keys": ["OPENROUTER_API_KEY"],
        "base_url": "https://openrouter.ai/api/v1",
        "default_model": "openai/gpt-4o",
    },
    "zen": {
        "env_keys": ["ZEN_API_KEY"],
        "base_url": "https://api.deepseek.com/v1",
        "default_model": "deepseek-chat",
    },
}

_ZEN_PREFERRED = bool(os.environ.get("ZEN_API_KEY"))


def _find_any_api_key() -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Find the first available API key across all providers.

    Returns (provider_name, api_key, base_url) or (None, None, None).
    Rotates through multiple keys for the same provider.
    """
    providers = list(PROVIDER_CONFIGS.keys())
    random.shuffle(providers)
    for provider in providers:
        config = PROVIDER_CONFIGS[provider]
        for env_key in config["env_keys"]:
            key = os.environ.get(env_key, "").strip()
            if key:
                return provider, key, config.get("base_url")
    return None, None, None


def _find_key_for_provider(provider: str) -> Optional[str]:
    """Find any available key for a specific provider (supports rotation)."""
    config = PROVIDER_CONFIGS.get(provider)
    if not config:
        return None
    keys = [os.environ.get(k, "").strip() for k in config["env_keys"]]
    keys = [k for k in keys if k]
    return random.choice(keys) if keys else None


# ── Thinking Engine ────────────────────────────────────────────────────


@dataclass
class Thought:
    """A single LLM call result with metadata."""
    provider: str
    model: str
    content: str
    usage: Dict[str, int] = field(default_factory=dict)
    duration_ms: float = 0.0
    finish_reason: str = "stop"


class ThinkingEngine:
    """Wires Daedalus capabilities to LLM providers with key rotation.

    Usage:
        engine = ThinkingEngine()
        thought = engine.think(system_prompt="...", user_prompt="...")
    """

    def __init__(self, preferred_provider: Optional[str] = None):
        self.preferred_provider = preferred_provider

    def think(
        self,
        system_prompt: str,
        user_prompt: str,
        model: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: float = 0.3,
    ) -> Thought:
        provider, api_key, base_url = self._resolve_provider()
        if not provider or not api_key:
            return Thought(
                provider="none",
                model="none",
                content=json.dumps({"error": "No API keys configured. Set GROQ_API_KEY, OPENAI_API_KEY, or similar."}),
            )
        import time as _time
        t0 = _time.monotonic()
        config = PROVIDER_CONFIGS.get(provider, {})
        resolved_model = model or config.get("default_model", "gpt-4o")
        try:
            from openai import OpenAI
            client = OpenAI(
                api_key=api_key,
                base_url=base_url,
            )
            response = client.chat.completions.create(
                model=resolved_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=max_tokens,
                temperature=temperature,
            )
            duration = (_time.monotonic() - t0) * 1000
            choice = response.choices[0]
            usage = {
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                "total_tokens": response.usage.total_tokens if response.usage else 0,
            }
            return Thought(
                provider=provider,
                model=resolved_model,
                content=choice.message.content or "",
                usage=usage,
                duration_ms=duration,
                finish_reason=choice.finish_reason or "stop",
            )
        except Exception as exc:
            duration = (_time.monotonic() - t0) * 1000
            msg = str(exc)
            # If rate limited, try another key/provider
            if "rate limit" in msg.lower() or "429" in msg:
                logger.warning("Rate limited on current provider, trying fallback...")
                fallback = self._try_fallback(provider, system_prompt, user_prompt, resolved_model, max_tokens, temperature)
                if fallback:
                    fallback.duration_ms += duration
                    return fallback
            return Thought(
                provider=provider,
                model=resolved_model,
                content=json.dumps({"error": msg}),
                duration_ms=duration,
                finish_reason="error",
            )

    def _resolve_provider(self) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        if self.preferred_provider:
            key = _find_key_for_provider(self.preferred_provider)
            if key:
                config = PROVIDER_CONFIGS.get(self.preferred_provider, {})
                return self.preferred_provider, key, config.get("base_url")
        if _ZEN_PREFERRED:
            key = _find_key_for_provider("zen")
            if key:
                config = PROVIDER_CONFIGS.get("zen", {})
                return "zen", key, config.get("base_url")
        return _find_any_api_key()

    def _try_fallback(
        self, failed_provider: str, system_prompt: str, user_prompt: str,
        model: str, max_tokens: int, temperature: float,
    ) -> Optional[Thought]:
        for provider in PROVIDER_CONFIGS:
            if provider == failed_provider:
                continue
            key = _find_key_for_provider(provider)
            if not key:
                continue
            config = PROVIDER_CONFIGS[provider]
            base_url = config.get("base_url")
            fallback_model = config.get("default_model", "gpt-4o")
            try:
                from openai import OpenAI
                client = OpenAI(api_key=key, base_url=base_url)
                response = client.chat.completions.create(
                    model=fallback_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                choice = response.choices[0]
                usage = {
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                }
                return Thought(
                    provider=provider,
                    model=fallback_model,
                    content=choice.message.content or "",
                    usage=usage,
                    finish_reason=choice.finish_reason or "stop",
                )
            except Exception:
                continue
        return None


# ── Daedalus Memory ────────────────────────────────────────────────────


MEMORY_PATH = Path(".daedalus/memory.json")


def load_memory() -> Dict[str, Any]:
    if MEMORY_PATH.exists():
        try:
            return json.loads(MEMORY_PATH.read_text())
        except (json.JSONDecodeError, Exception):
            pass
    return {
        "recommendations": [],
        "observations": [],
        "weekly_reports": [],
        "benchmark_history": [],
        "pr_history": [],
    }


def save_memory(memory: Dict[str, Any]) -> None:
    MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    MEMORY_PATH.write_text(json.dumps(memory, indent=2))


def record_recommendation(
    recommendation: str,
    context: str,
    pr_number: Optional[int] = None,
    severity: str = "info",
) -> None:
    memory = load_memory()
    memory["recommendations"].append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "recommendation": recommendation,
        "context": context,
        "pr_number": pr_number,
        "severity": severity,
        "status": "open",
        "outcome": None,
    })
    save_memory(memory)


def record_pr_review(pr_number: int, status: str, summary: str) -> None:
    memory = load_memory()
    memory["pr_history"].append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "pr_number": pr_number,
        "status": status,
        "summary": summary,
    })
    save_memory(memory)


def get_recommendation_history(days: int = 30) -> List[Dict[str, Any]]:
    memory = load_memory()
    cutoff = datetime.now(timezone.utc).timestamp() - days * 86400
    return [
        r for r in memory.get("recommendations", [])
        if datetime.fromisoformat(r["timestamp"]).timestamp() >= cutoff
    ]


def summarize_recommendation_follow_through() -> str:
    memory = load_memory()
    recs = memory.get("recommendations", [])
    if not recs:
        return "No past recommendations to track."
    total = len(recs)
    followed = sum(1 for r in recs if r.get("outcome") == "followed")
    ignored = sum(1 for r in recs if r.get("outcome") == "ignored")
    pending = total - followed - ignored
    lines = [
        f"## Recommendation Track Record",
        f"Total: {total} | Followed: {followed} | Ignored: {ignored} | Pending: {pending}",
    ]
    for r in recs[-5:]:
        status = "✓" if r.get("outcome") == "followed" else "✗" if r.get("outcome") == "ignored" else "○"
        lines.append(f"{status} {r['recommendation'][:80]}")
    return "\n".join(lines)


# ── Review Prompt Templates ────────────────────────────────────────────


ARCHITECTURAL_REVIEW_SYSTEM_PROMPT = """You are Daedalus, the Engineering Partner for IdentityOS.

You are reviewing a pull request. You think like an architect, not a linter.

Evaluate the change across these dimensions:
1. ARCHITECTURAL COMPLEXITY — How many layers does this touch? Are the changes concentrated or scattered?
2. COUPLING — Does this create new cross-layer dependencies? Are interfaces clean?
3. SURFACE AREA — How many modules, functions, and interfaces are affected?
4. RISK — Could this break existing behavior? Are there risky patterns?
5. TEST DELTA — Are the tests proportionate to the change? Is coverage improving or regressing?
6. DOCUMENTATION DELTA — Are docs keeping pace with code changes?
7. REVIEWABILITY — Is the PR well-structured? Could it be smaller?

Your memory from past reviews:
{memory_context}

Respond in JSON format with these fields:
- "verdict": "READY" | "NEEDS_WORK" | "NOT_READY"
- "summary": "2-3 sentence overview in your voice"
- "architectural_complexity": score 1-10 and brief explanation
- "coupling_assessment": "clean" | "minor concerns" | "violations detected"
- "risk_assessment": "low" | "medium" | "high" with reasoning
- "test_quality": "strong" | "adequate" | "insufficient" with what's missing
- "reviewability": "well-structured" | "could be improved" | "hard to follow"
- "recommendations": list of specific, actionable items
- "initiative_proposal": "If this PR follows a pattern from past recommendations, note it here."

Be constructively critical but fair. You want good architecture, not perfection.
""".strip()


WEEKLY_REPORT_SYSTEM_PROMPT = """You are Daedalus, the Engineering Partner for IdentityOS.

You are generating the weekly engineering report. You think like a CTO, not a script.

Analyze the data provided and produce a narrative report covering:
1. OVERALL HEALTH — A summary score and trend direction
2. ARCHITECTURE — Key changes, coupling trends, areas of concern
3. BENCHMARKS — Are scores improving, stable, or declining? Interpret the numbers
4. REGRESSION RISK — Are risky patterns accumulating?
5. TECHNICAL DEBT — Is it growing or shrinking? Where?
6. GOAL PROGRESS — Are we moving toward our primary goals?
7. INITIATIVE — One concrete initiative suggestion with estimated impact

Use your memory of past reports to identify trends:
{memory_context}

Respond in JSON format:
- "overall_health": score 0-100
- "trend": "improving" | "stable" | "declining"
- "narrative": multi-paragraph report in your voice
- "key_metrics": dict of metric names to values
- "initiative": {"title": "...", "description": "...", "estimated_impact": "..."}
- "concerns": list of items requiring attention

You are an engineering partner. Write like one.
""".strip()
