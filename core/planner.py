from __future__ import annotations

import json
import re
from typing import Any, Optional


class SkillRouter:
    """Maps user intent to installed capability skills and executes them.

    Sits between input processing and the LLM call. When the user asks
    for something a capability can provide, the router:

    1. Matches the intent to a skill via keyword + description analysis
    2. Extracts parameters from the natural-language query
    3. Executes the skill
    4. Returns structured results for injection into the LLM context

    The LLM receives *factual data*, not *descriptions of available skills*.
    This prevents it from falling back to "I don't have real-time access."
    """

    def __init__(self, capability_registry: Any, identity_id: str) -> None:
        self._registry = capability_registry
        self._identity_id = identity_id

    def route(self, user_input: str) -> list[dict[str, Any]]:
        """Parse user input, find matching skills, execute them.

        Returns a list of dicts, each with:
          - skill: skill name
          - success: bool
          - data: the result (or error message)
        """
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        caps = self._registry.list(self._identity_id)

        # First pass: check if ANY skill matches with contextual confidence
        contextual = False
        for cap in caps:
            for skill in cap.skills():
                match = self._match(user_input, skill)
                if match.get("confidence") == "contextual":
                    contextual = True
                    break

        for cap in caps:
            for skill in cap.skills():
                if contextual:
                    # Execute ALL skills — broad contextual query
                    matches = True
                else:
                    match = self._match(user_input, skill)
                    matches = match["matched"]

                if matches and skill.name not in seen:
                    seen.add(skill.name)
                    try:
                        params = self._extract_params(user_input, skill)
                        data = cap.call(skill.name, **params)
                        results.append({
                            "skill": skill.name,
                            "success": True,
                            "data": data,
                            "params": params,
                        })
                    except Exception as e:
                        results.append({
                            "skill": skill.name,
                            "success": False,
                            "data": {"error": str(e)},
                            "params": {},
                        })

        return results

    def format_for_context(self, results: list[dict[str, Any]]) -> str:
        """Format skill results as a factual data block for the LLM context."""
        if not results:
            return ""

        lines = ["## Factual Data from Installed Skills (this is LIVE data, use it directly):"]
        for r in results:
            if r["success"]:
                pretty = json.dumps(r["data"], indent=2, default=str)
                lines.append(f"### {r['skill']} returned:")
                lines.append(pretty)
            else:
                lines.append(f"### {r['skill']} error:")
                lines.append(str(r["data"]["error"]))
        lines.append("")
        lines.append("Use the data above to answer the user. Do NOT say you lack real-time access.")
        return "\n".join(lines)

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
            "web": ["fetch", "web page", "http", "url", "website", "download page", "look up", "search for", "find", "wikipedia"],
            "file": ["list files", "read file", "directory", "ls ", "file info", "list directory", "what files", "read the file", "show me"],
            "github": ["github", "repository", "repo", "pull request", "issue", "commit", "stars", "open source", "beginner", "trending", "lacebx", "identityos", "repo info"],
            "system": ["operating system", "disk space", "disk usage", "how much disk", "os", "cpu", "what system", "what os", "system info", "platform"],
        }

        # Additional pattern-based matching for GitHub repo references
        if re.search(r'[\w-]+/[\w-]+', user_input):  # owner/repo pattern
            for domain, keywords in triggers.items():
                if domain == "github":
                    return {"matched": True, "confidence": "high"}

        # Broad contextual queries — match ALL capabilities
        context_phrases = [
            "what should i focus on", "what's my priority", "what is my priority",
            "give me a status", "what's going on", "what's happening",
            "how am i doing", "what do i need to do", "what's my plan",
            "what's the situation", "assess my context",
        ]
        for phrase in context_phrases:
            if phrase in text:
                # Return a special sentinel — caller executes all skills
                return {"matched": True, "confidence": "contextual"}

        # Check skill name
        skill_name = skill.name.lower()
        for domain, keywords in triggers.items():
            if domain in skill_name:
                for kw in keywords:
                    if kw in text:
                        return {"matched": True, "confidence": "high"}

        # Check description
        desc = skill.description.lower()
        input_words = set(text.split())
        desc_words = set(desc.split())
        overlap = input_words & desc_words
        if len(overlap) >= 2:
            return {"matched": True, "confidence": "medium"}

        # Fallback: check if a significant word from the skill name appears
        name_parts = skill_name.replace(".", " ").split()
        for part in name_parts:
            if len(part) > 3 and part in text:
                return {"matched": True, "confidence": "low"}

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

        return {}
