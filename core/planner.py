from __future__ import annotations

import json
import re
from typing import Any, Optional

from core.capabilities.result import CapabilityResult
from core.capabilities.evidence import EvidenceManager


class SkillRouter:
    """Maps user intent to installed capability skills and executes them.

    Sits between input processing and the LLM call. When the user asks
    for something a capability can provide, the router:

    1. Matches the intent to a skill via keyword + description analysis
    2. Extracts parameters from the natural-language query
    3. Executes the skill
    4. Returns structured results via EvidenceManager for injection into context

    The LLM receives *factual data* with provenance and confidence,
    not *descriptions of available skills*.

    Multi-step compound requests are routed exclusively to the
    ``task_planner`` capability, which internally delegates to the
    individual sub-capabilities and returns a single consolidated result.
    """

    # Capabilities that the task_planner manages internally
    _PLANNER_MANAGED: frozenset[str] = frozenset({
        "file_tools", "skill_validator", "registry_manager",
    })

    _ACTION_VERBS: frozenset[str] = frozenset({
        "create", "build", "make", "write", "generate", "publish",
        "install", "validate", "check", "test", "deploy", "setup",
        "configure", "update", "remove", "delete", "add", "compile",
        "release", "package", "prepare", "scaffold", "init",
    })

    def __init__(self, capability_registry: Any, identity_id: str) -> None:
        self._registry = capability_registry
        self._identity_id = identity_id

    # ------------------------------------------------------------------
    # Compound-request detection (intent-based, not keyword-based)
    # ------------------------------------------------------------------

    @classmethod
    def _is_compound_request(cls, user_input: str) -> bool:
        """Detect whether the input describes a multi-step task.

        Heuristics:
        - Comma-separated action clauses (``create X, validate, publish``)
        - 3+ distinct action verbs (word-boundary — 'installed' ≠ 'install')
        - Sequential markers (``first X then Y``, ``create Z and publish``)
        """
        from core.claim_enforcement import (
            count_word_action_verbs,
            has_word_action_verb,
            is_explicit_deploy_request,
            is_gap_identify_only,
        )

        text = user_input.lower()
        # Gap-only questions must NOT become compound create/deploy routes
        if is_gap_identify_only(user_input) and not is_explicit_deploy_request(user_input):
            return False

        # Pattern 1: comma-separated actions (e.g. "create X, validate it, publish")
        clauses = [c.strip() for c in text.replace(" and ", ", ").replace(" then ", ", ").split(",") if c.strip()]
        action_clauses = sum(1 for c in clauses if cls._has_action_verb(c))
        if action_clauses >= 3:
            return True

        # Pattern 2: 3+ distinct action verbs anywhere in input (word boundary)
        found = count_word_action_verbs(text)
        if len(found) >= 3:
            return True

        # Pattern 3: sequential marker + at least one action
        sequential = re.search(r'(first|then|finally|next|after that|step|phase|stage)', text)
        if sequential and found:
            return True

        # Explicit create+publish+install style even with fewer verbs
        if is_explicit_deploy_request(user_input) and (
            has_word_action_verb(text, "create") or has_word_action_verb(text, "publish")
        ) and has_word_action_verb(text, "install"):
            return True

        return False

    @classmethod
    def _has_action_verb(cls, text: str) -> bool:
        from core.claim_enforcement import has_word_action_verb
        return any(has_word_action_verb(text, v) for v in cls._ACTION_VERBS)

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------

    def route(self, user_input: str) -> EvidenceManager:
        """Parse user input, find matching skills, execute them.

        Returns an EvidenceManager containing CapabilityResult objects
        with provenance, confidence, and error status.
        """
        evidence = EvidenceManager(self._identity_id)
        seen: set[str] = set()
        caps = self._registry.list(self._identity_id)
        text = user_input.strip().lower()

        from core.claim_enforcement import is_explicit_deploy_request, is_gap_identify_only

        # Gap-identify only: inventory, never create/deploy
        if is_gap_identify_only(user_input) and not is_explicit_deploy_request(user_input):
            for cap in caps:
                if getattr(cap, "id", "") == "registry_manager":
                    try:
                        result = cap.call(
                            "registry_manager.inventory",
                            identity_id=self._identity_id,
                        )
                    except Exception as e:
                        result = CapabilityResult.fail(
                            "registry_manager",
                            "registry_manager.inventory",
                            type(e).__name__,
                            str(e),
                        )
                    evidence.collect(result)
                    return evidence

        # ── Step 1: detect compound multi-step requests ─────────────
        is_multi_step = self._is_compound_request(text)

        # Multi-step evolution/create/install goals: ONLY task_planner.
        # Prevents github/file_tools spray that caused false evidence noise.
        if is_multi_step:
            planner_skill = "task_planner.plan_and_execute"
            for cap in caps:
                if getattr(cap, "id", "") == "task_planner":
                    try:
                        result = cap.call(
                            planner_skill,
                            goal=user_input,
                            identity_id=self._identity_id,
                        )
                    except Exception as e:
                        result = CapabilityResult.fail(
                            "task_planner",
                            planner_skill, type(e).__name__, str(e),
                        )
                    evidence.collect(result)
                    return evidence
            # fall through if planner not installed

        # ── Step 2: fire matching skills (precise HIGH confidence only) ──
        # Cap spray: at most 3 high-confidence skills; never fire medium/low/contextual.
        matched: list[tuple[float, str, Any, Any]] = []  # score, name, cap, skill
        for cap in caps:
            cap_id = getattr(cap, "id", "unknown")
            for skill in cap.skills():
                match = self._match(user_input, skill)
                if not match.get("matched"):
                    continue
                conf = match.get("confidence")
                if conf != "high":
                    continue
                # Hard domain filters — prevent github/filesystem spray on unrelated asks
                if cap_id == "github" and not any(
                    k in text for k in ("github", "repo", "pull request", "commit", "lacebx", "identityos")
                ):
                    continue
                if cap_id in ("filesystem", "file_tools") and not any(
                    k in text for k in ("file", "directory", "folder", "path", "write file", "read file", "mkdir")
                ):
                    continue
                if cap_id == "datetime" and not any(
                    k in text for k in ("time", "date", "timezone", "today", "clock")
                ):
                    continue
                if skill.name not in seen:
                    score = 3.0 if conf == "high" else 1.0
                    matched.append((score, skill.name, cap, skill))

        # Prefer web.search for natural-language lookup / browse-without-URL
        search_intent = any(
            k in text for k in (
                "search for", "look up", "who is", "browse", "find out about",
                "tell me who", "google", "spiderman", "theatre", "theater", "tickets",
            )
        ) and "http://" not in text and "https://" not in text
        if search_intent:
            for cap in caps:
                if getattr(cap, "id", "") == "web":
                    for skill in cap.skills():
                        if skill.name == "web.search" and skill.name not in {m[1] for m in matched}:
                            matched.insert(0, (10.0, skill.name, cap, skill))
                    break

        matched.sort(key=lambda x: -x[0])
        for _score, skill_name, cap, skill in matched[:3]:
            if skill_name in seen:
                continue
            seen.add(skill_name)
            try:
                params = self._extract_params(user_input, skill)
                if skill.name.startswith("registry_manager.") or skill.name.startswith("task_planner."):
                    params.setdefault("identity_id", self._identity_id)
                if skill.name == "web.search" and not params.get("query"):
                    # Use whole user input as query fallback
                    params["query"] = user_input.strip()[:200]
                result = cap.call(skill.name, **params)
            except Exception as e:
                result = CapabilityResult.fail(
                    getattr(cap, "id", "unknown"),
                    skill.name, type(e).__name__, str(e),
                )
            evidence.collect(result)

        return evidence

    def format_for_context(self, evidence: EvidenceManager) -> str:
        """Build a factual context block from evidence results."""
        return evidence.build_context_block()

    # ── Matching ──────────────────────────────────────────────────────

    _STOP_WORDS = frozenset({
        "the", "a", "an", "is", "it", "at", "my", "your", "our", "in", "on",
        "to", "for", "of", "and", "or", "this", "that", "with", "me", "you",
    })

    def _clean_param(self, raw: str) -> str:
        """Remove stop words and trivial tokens from an extracted parameter."""
        if not raw:
            return raw
        parts = re.findall(r'[A-Za-z]\w+', raw)
        filtered = [p for p in parts if p.lower() not in self._STOP_WORDS and len(p) > 1]
        return " ".join(filtered) if filtered else ""

    def _match(self, user_input: str, skill: Any) -> dict:
        """Check if user input matches this skill. Returns match + confidence."""
        text = user_input.lower()

        # Define strong trigger words per skill domain
        triggers: dict[str, list[str]] = {
            "time": ["time", "date", "today", "current time", "what day", "datetime", "what's the date", "tomorrow", "yesterday", "what day is it", "what's today"],
            "weather": ["weather", "temperature", "forecast", "raining", "sunny", "humidity", "rain", "cloudy", "wind", "degrees"],
            "calc": ["calculate", "evaluate", "what is", "compute", "plus", "minus", "times", "divided", "=", "how many", "% of", "percent"],
            "text": ["count words", "word count", "extract", "keywords", "analyze text", "summarize", "pattern", "stats"],
            "web": ["fetch http", "fetch https", "web page", "https://", "http://", "website url", "download page", "wikipedia.org"],
            "file": ["list files", "read file", "directory", "ls ", "file info", "list directory", "what files", "read the file", "open file"],
            "file_tools": ["write file", "create file", "save file", "write code", "create directory", "mkdir", "make directory", "append file", "edit file"],
            "github": ["github", "pull request", "github.com", "open source beginner", "lacebx", "identityos"],
            "system": ["operating system", "disk space", "disk usage", "how much disk", "what os", "system info", "cpu info"],
            "registry_manager": ["publish capability", "install capability", "list capabilities", "registry inventory", "publish skill", "install skill", "register skill", "add to registry", "capability inventory", "available capabilities", "installed capabilities"],
            "skill_validator": ["validate syntax", "syntax check", "check skill", "validate skill", "check capability interface"],
            "task_planner": ["create capability", "create a skill", "plan and execute", "deploy capability", "scaffold", "create_and_deploy", "publish and install"],
            "text_reverser": ["reverse the", "text_reverser", "reverser"],
            "word_counter": ["count words", "word count", "how many words"],
        }

        # GitHub only with explicit github/repo signals (not bare owner/repo false positives)
        if any(k in text for k in ("github", "pull request", "lacebx/", "identityos")):
            if "github" in skill.name.lower() or skill.name.lower().startswith("github."):
                return {"matched": True, "confidence": "high"}

        # Broad contextual queries disabled — they caused skill spray
        skill_name = skill.name.lower()
        skill_specific = {
            "registry_manager.list_capabilities": ["list capabilities", "list available", "show capabilities", "capability list"],
            "registry_manager.inventory": [
                "inventory", "installed capabilities", "available capabilities",
                "what can you", "what skills", "not installed", "installed versus",
            ],
            "registry_manager.publish_capability": ["publish capability", "publish skill", "register skill"],
            "registry_manager.install_capability": ["install capability", "install skill"],
            "registry_manager.create_and_deploy": ["create_and_deploy", "create and deploy", "deploy capability"],
            "task_planner.plan_and_execute": [
                "create capability", "create a skill", "create an actual skill",
                "plan and execute", "scaffold", "publish and install", "create a capability",
                "publish it to", "install it to yourself", "install it on myself",
            ],
            "web.search": [
                "search for", "look up", "who is", "browse", "find theatres",
                "find theaters", "ticket price", "spiderman", "without a url",
                "through what a user asks", "web search",
            ],
            "web.fetch": ["https://", "http://", "fetch url", "fetch the url"],
            "web.extract": ["extract from url", "extract text from http"],
        }
        if skill_name in skill_specific:
            for kw in skill_specific[skill_name]:
                if kw in text:
                    return {"matched": True, "confidence": "high"}
            return {"matched": False}

        for domain, keywords in triggers.items():
            if domain in skill_name:
                for kw in keywords:
                    if kw in text:
                        return {"matched": True, "confidence": "high"}

        # No medium/low fuzzy matches — they caused github/filesystem spray
        return {"matched": False}

    # ── Parameter extraction ──────────────────────────────────────────

    def _extract_params(self, user_input: str, skill: Any) -> dict[str, Any]:
        """Extract parameters from natural language for a specific skill."""
        name = skill.name
        text = user_input.strip()

        if name == "datetime.now":
            # "time in Tokyo" or "time in UTC" or just "time"
            tz_match = re.search(r'\bin\s+([A-Za-z/]+)', text)
            if tz_match:
                tz = self._clean_param(tz_match.group(1)).upper()
                if tz and len(tz) <= 5:
                    return {"tz_name": tz}
            return {"tz_name": "UTC"}

        if name == "datetime.diff":
            dates = re.findall(r'(\d{4}-\d{2}-\d{2})', text)
            if len(dates) >= 2:
                return {"date1": dates[0], "date2": dates[1]}
            return {}

        if name in ("weather.current", "weather.forecast"):
            loc_match = re.search(r'\bin\s+([A-Za-z]+)', text)
            if loc_match:
                cleaned = self._clean_param(loc_match.group(1))
                if cleaned:
                    return {"location": cleaned}
            words = text.split()
            for w in words:
                if w[0].isupper() and len(w) > 2 and w.lower() not in self._STOP_WORDS:
                    return {"location": w}
            return {"location": "London"}

        if name == "calc.evaluate":
            expr = text
            for prefix in ["calculate", "evaluate", "compute"]:
                if prefix in text.lower():
                    expr = text.lower().split(prefix, 1)[-1].strip()
                    break
            expr = expr.strip("?.!,;:")
            if expr and len(expr) > 2:
                return {"expression": expr}
            return {}

        if name == "system_info.disk":
            return {"path": "/"}

        if name in ("system_info.os", "system_info.cpu"):
            return {}

        if name in ("web.fetch", "web.extract"):
            urls = re.findall(r'https?://[^\s<>"\']+|www\.[^\s<>"\']+', text)
            if urls:
                return {"url": urls[0]}
            return {}

        if name == "github.search_repositories":
            clean = self._clean_param(text)
            return {"query": clean}

        if name == "github.get_repository":
            owner_repo = re.findall(r'([\w.-]+)/([\w.-]+)', text)
            if owner_repo:
                return {"owner": owner_repo[0][0], "repo": owner_repo[0][1]}
            return {}

        if name == "github.find_beginner_issue":
            owner_repo = re.findall(r'([\w.-]+)/([\w.-]+)', text)
            if owner_repo:
                return {"owner": owner_repo[0][0], "repo": owner_repo[0][1]}
            return {"query": text}

        if name in ("github.review_pull_request", "github.list_commits", "github.list_branches", "github.summarize_release"):
            owner_repo = re.findall(r'([\w.-]+)/([\w.-]+)', text)
            if owner_repo:
                return {"owner": owner_repo[0][0], "repo": owner_repo[0][1]}
            return {}

        if name == "filesystem.list_dir":
            path_match = re.search(r'\bin\s+([/\w.-]+)', text)
            if path_match:
                cleaned = self._clean_param(path_match.group(1))
                if cleaned:
                    return {"path": cleaned}
            return {"path": "."}

        if name == "filesystem.read_file":
            path_match = re.search(r'(?:read|open|show)\s+([/\w.-]+(?:\.[\w]+)?)', text)
            if path_match:
                return {"path": path_match.group(1)}
            return {}

        if name == "text.stats":
            return {"text": text}

        if name == "text.extract_pattern":
            pat_map = {"url": "urls", "email": "emails", "hashtag": "hashtags", "mention": "mentions"}
            for key, val in pat_map.items():
                if key in text.lower():
                    return {"text": text, "pattern": val}
            return {"text": text, "pattern": "urls"}

        if name == "web.fetch":
            url_match = re.search(r'(https?://\S+)', text)
            return {"url": url_match.group(1)} if url_match else {}

        if name == "web.extract":
            url_match = re.search(r'(https?://\S+)', text)
            return {"url": url_match.group(1)} if url_match else {}

        if name == "web.search":
            q = None
            m = re.search(
                r'(?:search(?:\s+the\s+web)?(?:\s+for)?|look\s+up|who\s+is|find(?:\s+out\s+about)?)\s+(.+)$',
                text,
                re.IGNORECASE,
            )
            if m:
                q = m.group(1).strip().rstrip(".")
            if not q:
                # Named entity after "for"
                m2 = re.search(r'\bfor\s+([A-Z][\w\'\-]+(?:\s+[A-Z][\w\'\-]+){0,4})', text)
                if m2:
                    q = m2.group(1).strip()
            if not q:
                # Quoted
                m3 = re.search(r"['\"]([^'\"]+)['\"]", text)
                if m3:
                    q = m3.group(1).strip()
            return {"query": q} if q else {"query": text[:200]}

        if name.endswith(".reverse") or name.endswith(".echo") or name.endswith(".upper") or name.endswith(".count") or name.endswith(".greet"):
            # Prefer quoted string, else last meaningful phrase
            q = re.search(r"['\"]([^'\"]+)['\"]", text)
            if q:
                return {"text": q.group(1), "message": q.group(1)}
            # "reverse the word Bones" / "reverse IdentityOS"
            m = re.search(r'(?:reverse|count|echo|uppercase)\s+(?:the\s+)?(?:word\s+|string\s+)?(.+)$', text, re.IGNORECASE)
            if m:
                val = m.group(1).strip().rstrip(".")
                return {"text": val, "message": val}
            return {}

        # ── File Tools ───────────────────────────────────────────────────
        if name == "file_tools.write_file":
            path_match = re.search(r'(?:to|at|in)\s+([/\w.-]+(?:\.[\w]+)?)', text)
            if path_match:
                return {"path": path_match.group(1), "content": ""}
            path_match = re.search(r'(?:file|path):\s*([/\w.-]+(?:\.[\w]+)?)', text, re.IGNORECASE)
            if path_match:
                return {"path": path_match.group(1), "content": ""}
            return {}

        if name == "file_tools.create_directory":
            path_match = re.search(r'(?:at|in|to|path:)?\s*([/\w.-]+)', text)
            if path_match:
                return {"path": path_match.group(1)}
            return {}

        # ── Registry Manager ─────────────────────────────────────────────
        if name == "registry_manager.list_capabilities":
            return {"identity_id": getattr(self, "_identity_id", "")}

        if name == "registry_manager.inventory":
            return {"identity_id": getattr(self, "_identity_id", "")}

        if name in ("registry_manager.publish_capability", "registry_manager.install_capability"):
            id_match = re.search(
                r'(?:capability|skill|publish|install)\s+([a-z][a-z0-9_]{2,64})',
                text,
                re.IGNORECASE,
            )
            params: dict[str, Any] = {"identity_id": getattr(self, "_identity_id", "")}
            if id_match:
                cand = id_match.group(1).lower()
                # Reject English debris / articles
                if cand not in self._STOP_WORDS and cand not in {
                    "capability", "skill", "existing", "available", "new", "the", "an", "a"
                }:
                    params["cap_id"] = cand
            return params

        if name == "registry_manager.create_and_deploy":
            params = {"identity_id": getattr(self, "_identity_id", "")}
            id_match = re.search(
                r'(?:capability|skill|create|deploy)\s+([a-z][a-z0-9]*_[a-z0-9_]+)',
                text,
                re.IGNORECASE,
            )
            if id_match:
                params["cap_id"] = id_match.group(1).lower()
            if "reverse" in text.lower():
                params["skill_kind"] = "reverse"
            elif "upper" in text.lower():
                params["skill_kind"] = "upper"
            return params

        if name == "task_planner.plan_and_execute":
            params = {"goal": text, "identity_id": getattr(self, "_identity_id", "")}
            id_match = re.search(r'\b([a-z][a-z0-9]*_[a-z0-9_]+)\b', text.lower())
            if id_match:
                params["cap_id"] = id_match.group(1)
            if "reverse" in text.lower():
                params["skill_kind"] = "reverse"
            return params
        # ── Skill Validator ──────────────────────────────────────────────
        if name == "skill_validator.validate_syntax":
            path_match = re.search(r'(?:file|path|validate):?\s*([/\w.-]+(?:\.[\w]+)?)', text, re.IGNORECASE)
            if path_match:
                return {"path": path_match.group(1)}
            return {}

        if name == "skill_validator.check_capability_interface":
            path_match = re.search(r'(?:file|path|check):?\s*([/\w.-]+(?:\.[\w]+)?)', text, re.IGNORECASE)
            if path_match:
                return {"path": path_match.group(1)}
            return {}

        return {}
