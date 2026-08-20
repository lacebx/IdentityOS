"""Gemini API client for ratchet autopilot code proposals."""

from __future__ import annotations

import json
import os
import re
from typing import Any

import httpx

DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")
API_BASE = "https://generativelanguage.googleapis.com/v1beta"


class CoderError(RuntimeError):
    pass


def _api_key() -> str:
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        raise CoderError(
            "Set GEMINI_API_KEY (or GOOGLE_API_KEY) in the environment. "
            "Never commit API keys to the repository."
        )
    return key


def _extract_json(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            raise CoderError(f"Gemini response was not JSON: {text[:400]}") from exc
        return json.loads(match.group(0))


def propose_edits(prompt: str, *, model: str | None = None, timeout_s: float = 180.0) -> dict[str, Any]:
    """Call Gemini generateContent and parse a JSON edit proposal."""
    model = model or DEFAULT_MODEL
    url = f"{API_BASE}/models/{model}:generateContent"
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.15,
            "maxOutputTokens": 8192,
            "responseMimeType": "application/json",
        },
    }
    with httpx.Client(timeout=timeout_s) as client:
        resp = client.post(url, params={"key": _api_key()}, json=payload)
    if resp.status_code >= 400:
        raise CoderError(f"Gemini API error {resp.status_code}: {resp.text[:500]}")
    data = resp.json()
    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as exc:
        raise CoderError(f"Unexpected Gemini response shape: {data!r}") from exc
    proposal = _extract_json(text)
    for key in ("hypothesis", "change", "edits"):
        if key not in proposal:
            raise CoderError(f"Gemini proposal missing {key!r}")
    if not isinstance(proposal["edits"], list):
        raise CoderError("edits must be a list")
    return proposal
