"""Runtime honesty enforcement for capability create/publish/install claims.

The LLM must not narrate deploy success. This module:
1. Detects create/publish/install claims in assistant text
2. Checks evidence + identity store for real postconditions
3. Rewrites the reply when claims are unproven
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Optional


_CLAIM_VERBS = (
    r"(?:created|published|installed|deployed|built|scaffolded|"
    r"successfully\s+(?:created|published|installed|deployed)|"
    r"now\s+(?:available|installed)|"
    r"capability\s+is\s+now)"
)

_CLAIM_RE = re.compile(
    rf"(?is)\b{_CLAIM_VERBS}\b.{{0,120}}?\b"
    rf"(?:capability|skill|cap)?\s*[`'\"]?([a-z][a-z0-9_]{{2,64}})[`'\"]?",
)

_ALT_CLAIM_RE = re.compile(
    rf"(?is)\b(?:capability|skill)\s+[`'\"]?([a-z][a-z0-9_]{{2,64}})[`'\"]?"
    rf".{{0,80}}?\b{_CLAIM_VERBS}\b",
)

_SUCCESS_PHRASE_RE = re.compile(
    r"(?is)\b(?:goal_ok\s*=\s*true|installation\s+completed\s+successfully|"
    r"successfully\s+installed|published\s+to\s+the\s+registry|"
    r"create(?:d)?,?\s+publish(?:ed)?,?\s+and\s+install(?:ed)?)\b",
)

_FAKE_TOOL_RE = re.compile(
    r"(?is)</?function_calls?>|"
    r"<invoke\b[^>]*>.*?</invoke>|"
    r"<parameter\b[^>]*>.*?</parameter>",
)

_BARE_JSON_PLAN_RE = re.compile(
    r"(?is)^\s*\{\s*\"(?:goal|cap_id|skill_kind|identity_id)\"",
)

_DEPLOY_INTENT_RE = re.compile(
    r"(?i)\b(?:create|build|make|write|scaffold|publish|install|deploy)\b"
    r".{0,80}\b(?:capability|skill)\b|"
    r"\b(?:create_and_deploy|publish\s+and\s+install|install\s+it\s+on\s+(?:your|my)?self)\b",
)

_GAP_ONLY_RE = re.compile(
    r"(?i)\b(?:what\s+(?:skill|capability)\s+(?:do\s+you\s+)?lack|"
    r"tell\s+me\s+a\s+skill\s+you\s+(?:truly\s+)?lack|"
    r"know\s+your\s+limits|"
    r"self\s+limit|"
    r"what\s+(?:gap|limitation)|"
    r"identify\s+(?:a\s+)?(?:gap|limit)|"
    r"what\s+would\s+(?:bridge|remove)\s+(?:said\s+)?gap|"
    r"if\s+installed\s+would)\b",
)

_WORD_ACTION_VERBS = frozenset({
    "create", "build", "make", "write", "generate", "publish",
    "install", "validate", "check", "test", "deploy", "setup",
    "configure", "update", "remove", "delete", "add", "compile",
    "release", "package", "prepare", "scaffold", "init",
})


def is_gap_identify_only(user_input: str) -> bool:
    """True when user asks for limit recognition without ordering a deploy."""
    text = (user_input or "").strip()
    if not text:
        return False
    if _GAP_ONLY_RE.search(text) and not _DEPLOY_INTENT_RE.search(text):
        return True
    # Soft: "tell me a skill you lack" without create/publish/install verbs as commands
    low = text.lower()
    if ("lack" in low or "gap" in low or "limit" in low) and not _DEPLOY_INTENT_RE.search(text):
        if any(w in low for w in ("skill", "capability", "what would", "bridge")):
            return True
    return False


def is_explicit_deploy_request(user_input: str) -> bool:
    return bool(_DEPLOY_INTENT_RE.search(user_input or ""))


def has_word_action_verb(text: str, verb: str) -> bool:
    """Word-boundary action match — 'installed' must not match 'install'."""
    return bool(re.search(rf"(?<![a-z]){re.escape(verb)}(?![a-z])", (text or "").lower()))


def count_word_action_verbs(text: str) -> set[str]:
    found: set[str] = set()
    low = (text or "").lower()
    for v in _WORD_ACTION_VERBS:
        if has_word_action_verb(low, v):
            found.add(v)
    return found


def extract_claimed_cap_ids(assistant_text: str) -> list[str]:
    """Capability ids the assistant claims were created/published/installed."""
    text = assistant_text or ""
    ids: list[str] = []
    for rx in (_CLAIM_RE, _ALT_CLAIM_RE):
        for m in rx.finditer(text):
            cand = (m.group(1) or "").lower()
            if cand and cand not in ids and cand not in {
                "capability", "skill", "registry", "myself", "yourself",
                "successfully", "available", "true", "false",
            }:
                ids.append(cand)
    return ids


def _result_proves_deploy(result: Any, cap_id: str) -> bool:
    if result is None:
        return False
    success = bool(getattr(result, "success", False))
    goal_ok = getattr(result, "goal_ok", None)
    if goal_ok is False or not success:
        return False
    data = getattr(result, "data", None)
    if not isinstance(data, dict):
        # Nested planner results
        return False
    if data.get("goal_ok") is False:
        return False
    status = str(data.get("status", "")).lower()
    if status in ("deployed", "installed", "published") and (
        data.get("cap_id") == cap_id or cap_id in str(data)
    ):
        return True
    # create_and_deploy shape
    if data.get("cap_id") == cap_id and data.get("goal_ok") is True:
        return True
    installed = data.get("installed")
    if isinstance(installed, dict) and installed.get("cap_id") == cap_id and installed.get("goal_ok"):
        return True
    # Nested planner step results
    for step in data.get("results") or []:
        if not isinstance(step, dict):
            continue
        step_data = step.get("data") if isinstance(step.get("data"), dict) else {}
        if step_data.get("cap_id") == cap_id and (
            step_data.get("status") in ("deployed", "installed", "published")
            or step_data.get("goal_ok") is True
        ):
            if step.get("success") is not False:
                return True
        # Recursive nested create_and_deploy payload
        if isinstance(step_data.get("installed"), dict):
            inn = step_data["installed"]
            if inn.get("cap_id") == cap_id and inn.get("goal_ok"):
                return True
        if step_data.get("status") == "deployed" and step_data.get("cap_id") == cap_id:
            return True
    return False


def evidence_proves_cap(evidence_results: list[Any], cap_id: str) -> bool:
    for r in evidence_results or []:
        if _result_proves_deploy(r, cap_id):
            return True
    return False


def store_has_cap(capability_registry: Any, identity_id: str, cap_id: str) -> bool:
    if capability_registry is None or not identity_id or not cap_id:
        return False
    try:
        return capability_registry.get(identity_id, cap_id) is not None
    except Exception:
        return False


def module_exists(cap_id: str) -> bool:
    if not cap_id or not cap_id.isidentifier():
        return False
    base = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "capabilities",
        cap_id,
        "__init__.py",
    )
    return os.path.isfile(base)


def registry_index_has(cap_id: str) -> bool:
    idx = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..",
        "registry",
        "index.json",
    )
    idx = os.path.abspath(idx)
    if not os.path.isfile(idx):
        return False
    try:
        with open(idx) as f:
            data = json.load(f)
        return any(c.get("id") == cap_id for c in data.get("capabilities", []))
    except Exception:
        return False


def sanitize_assistant_text(text: str) -> str:
    """Strip fake tool XML and lone JSON plan dumps from chat output."""
    if not text:
        return text
    cleaned = _FAKE_TOOL_RE.sub("", text)
    # If the whole reply is a JSON plan object, replace with a short note
    stripped = cleaned.strip()
    if _BARE_JSON_PLAN_RE.match(stripped) or (
        stripped.startswith("{") and stripped.endswith("}") and '"cap_id"' in stripped
        and any(k in stripped for k in ('"goal"', '"skill_kind"', '"identity_id"'))
    ):
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, dict) and ("cap_id" in parsed or "goal" in parsed):
                cap = parsed.get("cap_id") or "unknown"
                return (
                    f"I drafted a plan for capability `{cap}`, but I have **not** "
                    f"created, published, or installed it yet. "
                    f"Say explicitly: create capability {cap}, publish it, and install it on myself "
                    f"— and I will only claim success after goal_ok=true."
                )
        except Exception:
            pass
    # Remove orphaned function_calls blobs leftover
    cleaned = re.sub(r"(?is)<function_calls>.*", "", cleaned)
    return cleaned.strip()


def enforce_deploy_claims(
    assistant_text: str,
    *,
    user_input: str,
    evidence_results: list[Any],
    capability_registry: Any = None,
    identity_id: str = "",
) -> tuple[str, Optional[dict[str, Any]]]:
    """Rewrite unproven create/publish/install claims.

    Returns (possibly rewritten text, audit dict or None).
    """
    text = sanitize_assistant_text(assistant_text or "")
    claimed = extract_claimed_cap_ids(text)
    has_success_language = bool(_SUCCESS_PHRASE_RE.search(text))

    # Gap-only questions: never allow deploy-success narration
    if is_gap_identify_only(user_input):
        if claimed or has_success_language:
            audit = {
                "phase": "gap_identify_only",
                "blocked_claims": claimed,
                "action": "rewrote_to_identify_only",
            }
            rewrite = (
                "I can name a real capability gap, but I have **not** created, published, "
                "or installed anything in this turn.\n\n"
                "From my current limits: I cannot do genuine embedding-based semantic "
                "similarity (measuring meaning overlap between texts) with a verified "
                "local skill — that would need a real `semantic_similarity` (or similar) "
                "capability with a working probe.\n\n"
                "If you want me to bridge that gap, say explicitly:\n"
                "`Create capability semantic_similarity, publish it, install it on myself, "
                "then compare 'cat' and 'kitten'`.\n"
                "I will only report success if `goal_ok=true` and the capability shows up "
                "in inventory / `identity cap list`."
            )
            return rewrite, audit
        return text, None

    if not claimed and not has_success_language:
        return text, None

    # Verify each claimed id
    unproven: list[str] = []
    proven: list[str] = []
    for cap_id in claimed:
        ok = (
            evidence_proves_cap(evidence_results, cap_id)
            and store_has_cap(capability_registry, identity_id, cap_id)
        )
        # Also require module or registry entry for create claims
        if ok and not (module_exists(cap_id) or registry_index_has(cap_id)):
            ok = False
        if ok:
            proven.append(cap_id)
        else:
            unproven.append(cap_id)

    # Success language without any extractable id — still block if no deploy evidence
    if has_success_language and not proven:
        any_deploy = False
        for r in evidence_results or []:
            data = getattr(r, "data", None)
            if isinstance(data, dict) and data.get("goal_ok") is True and str(
                data.get("status", "")
            ).lower() in ("deployed", "installed", "published"):
                any_deploy = True
                break
            # planner nested
            if isinstance(data, dict) and data.get("goal_ok") is True and data.get("all_succeeded"):
                for step in data.get("results") or []:
                    sd = step.get("data") if isinstance(step, dict) else None
                    if isinstance(sd, dict) and sd.get("status") in ("deployed", "installed"):
                        any_deploy = True
        if not any_deploy:
            audit = {
                "phase": "unproven_success_language",
                "blocked_claims": claimed or ["(unspecified)"],
                "action": "rewrote_denial",
            }
            return (
                "I must correct myself: I do **not** have verified evidence that I "
                "created, published, and installed a new capability in this turn "
                "(`goal_ok` deploy postconditions were not met). "
                "Please check with `identity cap list` / inventory. "
                "If you want a real deploy, give an explicit create+publish+install command "
                "with a snake_case capability id.",
                audit,
            )

    if unproven:
        audit = {
            "phase": "claim_enforcement",
            "proven": proven,
            "unproven": unproven,
            "action": "rewrote_partial",
        }
        lines = [
            "I need to correct an overclaim about capability deployment.",
            "",
            f"**Not proven** (not on disk/store with goal_ok evidence): {', '.join(f'`{c}`' for c in unproven)}",
        ]
        if proven:
            lines.append(
                f"**Actually verified this turn:** {', '.join(f'`{c}`' for c in proven)}"
            )
        lines.extend([
            "",
            "I will only claim create/publish/install success when evidence shows "
            "`goal_ok=true` and the capability is installed on this identity.",
            "Ask me to inventorize, or explicitly order: "
            "`create capability <snake_case>, publish and install it on myself`.",
        ])
        return "\n".join(lines), audit

    return text, None


def build_deploy_truth_block(
    evidence_results: list[Any],
    *,
    capability_registry: Any = None,
    identity_id: str = "",
) -> str:
    """Inject a hard truth block into LLM context about this turn's deploys."""
    lines = [
        "## DEPLOY TRUTH (RUNTIME ENFORCED — DO NOT CONTRADICT)",
        "You may ONLY claim create/publish/install if listed under VERIFIED below.",
        "If VERIFIED is empty, you MUST NOT say you created, published, or installed anything.",
        "Do not output JSON plans or <function_calls> XML. Speak in plain language.",
        "Gap-identify questions: name the gap and proposed skill — do NOT claim you built it yet.",
    ]
    verified: list[str] = []
    failed: list[str] = []
    for r in evidence_results or []:
        data = getattr(r, "data", None)
        action = getattr(r, "action", "") or ""
        if not isinstance(data, dict):
            continue
        cap_id = data.get("cap_id")
        status = str(data.get("status", "")).lower()
        if cap_id and data.get("goal_ok") is True and status in (
            "deployed", "installed", "published"
        ):
            if store_has_cap(capability_registry, identity_id, str(cap_id)) or status == "published":
                verified.append(f"{cap_id} ({status}) via {action}")
        if data.get("goal_ok") is False or (
            isinstance(data.get("error"), str) and data.get("error")
        ):
            failed.append(f"{cap_id or action}: {data.get('error') or data.get('status')}")
        for step in data.get("results") or []:
            if not isinstance(step, dict):
                continue
            sd = step.get("data") if isinstance(step.get("data"), dict) else {}
            cid = sd.get("cap_id")
            st = str(sd.get("status", "")).lower()
            if cid and sd.get("goal_ok") is True and st in ("deployed", "installed", "published"):
                verified.append(f"{cid} ({st}) via planner")
            if step.get("success") is False or sd.get("goal_ok") is False:
                failed.append(f"{cid or step.get('action')}: failed")

    if verified:
        lines.append("VERIFIED this turn:")
        lines.extend(f"  - {v}" for v in verified)
    else:
        lines.append("VERIFIED this turn: (none)")
    if failed:
        lines.append("FAILED / incomplete this turn:")
        lines.extend(f"  - {f}" for f in failed[:8])
    return "\n".join(lines)
