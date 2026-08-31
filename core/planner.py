from __future__ import annotations

import re
from typing import Any, Optional

from core.capabilities.result import CapabilityResult
from core.capabilities.evidence import EvidenceManager


class SkillRouter:
    """Maps user intent to installed capability skills and executes them.

    Safety model:
    - Read-only skills may be routed from natural language.
    - Mutating skills (filesystem writes, directory creation, registry
      publish/install, command execution) require explicit intent AND
      plausible parameters.
    - The router must never treat ordinary conversational words as paths,
      filenames, directories, or capability IDs.
    """

    _PLANNER_MANAGED: frozenset[str] = frozenset({
        "file_tools",
        "skill_validator",
        "registry_manager",
    })

    _ACTION_VERBS: frozenset[str] = frozenset({
        "create", "build", "make", "write", "generate", "publish",
        "install", "validate", "check", "test", "deploy", "setup",
        "configure", "update", "remove", "delete", "add", "compile",
        "release", "package", "prepare", "scaffold", "init", "run", "execute",
    })

    _MUTATING_SKILLS: frozenset[str] = frozenset({
        "file_tools.write_file",
        "file_tools.append_file",
        "file_tools.create_directory",
        "registry_manager.publish_capability",
        "registry_manager.install_capability",
    })

    _STOP_WORDS: frozenset[str] = frozenset({
        "the", "a", "an", "is", "it", "at", "my", "your", "our", "in", "on",
        "to", "for", "of", "and", "or", "this", "that", "with", "me", "you",
    })

    _PATH_BLACKLIST: frozenset[str] = frozenset({
        "i", "me", "my", "mine", "we", "us", "our", "ours",
        "you", "your", "yours", "he", "him", "his", "she", "her", "hers",
        "it", "its", "they", "them", "their", "theirs",
        "the", "a", "an", "this", "that", "these", "those",
        "what", "why", "how", "when", "where", "who", "whom", "whose", "which",
        "is", "are", "was", "were", "be", "been", "being",
        "can", "could", "would", "should", "will", "shall",
        "may", "might", "must", "do", "does", "did", "done",
        "hey", "hi", "hello", "yes", "yeah", "no", "ok", "okay",
        "please", "thanks", "thank", "great", "nice", "cool",
        "now", "then", "so", "well", "here", "there",
        "give", "giving", "given",
        "file", "files", "directory", "directories", "folder", "folders",
        "path", "paths", "name", "named", "called", "content", "contents",
        "if", "but", "and", "or", "of", "in", "on", "at", "by",
        "about", "into", "over", "under", "again", "further", "once",
    })

    _FILE_EXTENSIONS: str = (
        r"txt|md|markdown|py|pyi|ipynb|json|jsonl|csv|tsv|log|yml|yaml|toml|ini|cfg|conf|"
        r"sh|bash|zsh|js|mjs|cjs|ts|tsx|jsx|html|htm|css|scss|rst|xml|pdf|env|gitignore"
    )

    _EXACT_SKILL_TRIGGERS: dict[str, list[str]] = {
        "filesystem.list_dir": [
            "list files", "list directory", "directory listing", "list the files",
            "list the directory", "show files", "show directories", "what files", "ls",
        ],
        "filesystem.read_file": [
            "read file", "read the file", "open file", "open the file",
            "show file", "show the file", "cat file",
        ],
        "filesystem.file_info": ["file info", "file metadata", "stat file"],
        "github.search_repositories": [
            "search repositories", "search repository", "search repo", "search github",
            "find repository", "find repo",
        ],
        "github.get_repository": [
            "repository info", "repo info", "get repository", "get repo",
            "repository details", "repo details", "about repository", "about repo",
            "repository", "repo",
        ],
        "github.review_pull_request": ["pull request", "review pr", "review pull request", "pr"],
        "github.find_beginner_issue": ["beginner issue", "beginner issues", "good first issue", "first issue"],
        "github.summarize_release": ["summarize release", "release summary", "latest release", "recent release"],
        "github.list_commits": ["list commits", "recent commits", "commits", "commit history"],
        "github.list_branches": ["list branches", "branches", "branch list"],
    }

    _DIAGNOSTIC_TRIGGERS: frozenset[str] = frozenset({
        "demonstrate", "show your skills", "prove your skills", "test your skills",
        "what can you do", "show me your skills", "use your skills", "diagnostic",
        "system check", "skill check", "demonstrate all", "prove to me"
    })

    _DIAGNOSTIC_SKILLS: frozenset[str] = frozenset({
        "datetime.now", "system_info.os", "system_info.disk", 
        "system_info.cpu", "filesystem.list_dir"
    })

    def __init__(self, capability_registry: Any, identity_id: str) -> None:
        self._registry = capability_registry
        self._identity_id = identity_id

    @classmethod
    def _is_compound_request(cls, user_input: str) -> bool:
        text = user_input.lower()
        clauses = [
            c.strip()
            for c in text.replace(" and ", ", ").replace(" then ", ", ").split(",")
            if c.strip()
        ]
        action_clauses = sum(1 for c in clauses if cls._has_action_verb(c))
        if action_clauses >= 2:
            return True

        found = {
            v for v in cls._ACTION_VERBS
            if re.search(rf"\b{re.escape(v)}\b", text)
        }
        if len(found) >= 3:
            return True

        sequential = re.search(
            r"\b(first|then|finally|next|after\s+that|step|phase|stage)\b",
            text,
        )
        if sequential and found:
            return True

        return False

    @classmethod
    def _has_action_verb(cls, text: str) -> bool:
        return any(
            re.search(rf"\b{re.escape(v)}\b", text)
            for v in cls._ACTION_VERBS
        )

    def route(self, user_input: str) -> EvidenceManager:
        evidence = EvidenceManager(self._identity_id)
        seen: set[str] = set()

        caps = self._registry.list(self._identity_id)
        text = user_input.strip().lower()

        is_multi_step = self._is_compound_request(text)
        is_diagnostic = any(phrase in text for phrase in self._DIAGNOSTIC_TRIGGERS)
        contextual = self._is_contextual_request(text)

        for cap in caps:
            cap_id = getattr(cap, "id", "unknown")

            if is_multi_step and cap_id in self._PLANNER_MANAGED:
                continue

            for skill in cap.skills():
                skill_name = getattr(skill, "name", "")
                if not skill_name:
                    continue

                matches = False
                params = {}

                if is_diagnostic and skill_name in self._DIAGNOSTIC_SKILLS:
                    matches = True
                    params = self._extract_params(user_input, skill)

                elif self._is_mutating_skill(skill_name):
                    if self._has_explicit_mutating_intent(user_input, skill_name):
                        params = self._extract_params(user_input, skill)
                        if self._has_safe_mutating_params(skill_name, params):
                            matches = True

                else:
                    if contextual:
                        matches = True
                    else:
                        match = self._match(user_input, skill)
                        matches = match["matched"]
                    
                    if matches:
                        params = self._extract_params(user_input, skill)
                        if not self._has_required_read_params(skill_name, params):
                            matches = False

                if matches and skill_name not in seen:
                    seen.add(skill_name)
                    try:
                        result = self._registry.call(
                            self._identity_id,
                            skill_name,
                            **params,
                        )
                    except Exception as e:
                        result = CapabilityResult.fail(
                            cap_id, skill_name, type(e).__name__, str(e),
                        )
                    evidence.collect(result)

        if is_multi_step:
            planner_skill = "task_planner.plan_and_execute"
            if planner_skill not in seen:
                seen.add(planner_skill)
                for cap in caps:
                    if getattr(cap, "id", "") == "task_planner":
                        try:
                            result = self._registry.call(
                                self._identity_id,
                                planner_skill,
                                goal=user_input,
                            )
                        except Exception as e:
                            result = CapabilityResult.fail(
                                "task_planner", planner_skill, type(e).__name__, str(e),
                            )
                        evidence.collect(result)
                        break

        return evidence

    def should_offer_tools(self, user_input: str) -> bool:
        """Return whether an authorized skill is relevant to this request.

        This shares the routing rules used for direct execution, so model tool
        exposure cannot drift into a second list of benchmark-shaped triggers.
        """
        text = user_input.strip().lower()
        if not text:
            return False
        is_multi_step = self._is_compound_request(text)
        is_diagnostic = any(phrase in text for phrase in self._DIAGNOSTIC_TRIGGERS)
        contextual = self._is_contextual_request(text)

        for cap in self._registry.list(self._identity_id):
            cap_id = getattr(cap, "id", "unknown")
            if is_multi_step and cap_id in self._PLANNER_MANAGED:
                continue
            for skill in cap.skills():
                allowed, _ = self._registry.can(self._identity_id, skill.name)
                if not allowed:
                    continue
                if is_diagnostic and skill.name in self._DIAGNOSTIC_SKILLS:
                    return True
                params = self._extract_params(user_input, skill)
                if self._is_mutating_skill(skill.name):
                    if (
                        self._has_explicit_mutating_intent(user_input, skill.name)
                        and self._has_safe_mutating_params(skill.name, params)
                    ):
                        return True
                    continue
                if (contextual or self._match(user_input, skill)["matched"]) and self._has_required_read_params(skill.name, params):
                    return True

        if is_multi_step:
            allowed, _ = self._registry.can(
                self._identity_id,
                "task_planner.plan_and_execute",
            )
            return allowed
        return False

    def format_for_context(self, evidence: EvidenceManager) -> str:
        return evidence.build_context_block()

    def _is_contextual_request(self, text: str) -> bool:
        context_phrases = [
            "what should i focus on", "what's my priority", "what is my priority",
            "give me a status", "what's going on", "what's happening",
            "how am i doing", "what do i need to do", "what's my plan",
            "what's the situation", "assess my context",
        ]
        return any(phrase in text for phrase in context_phrases)

    def _is_mutating_skill(self, skill_name: str) -> bool:
        skill_name = skill_name.lower()
        if skill_name.startswith("command_exec."):
            return True
        return skill_name in self._MUTATING_SKILLS

    def _has_explicit_mutating_intent(self, user_input: str, skill_name: str) -> bool:
        text = user_input.lower()

        if skill_name == "file_tools.create_directory":
            return bool(
                re.search(r"\bmkdir\b", text)
                or re.search(r"\b(create|make|add)\b[^.!?]*\b(directory|dir|folder)\b", text)
            )
        if skill_name == "file_tools.write_file":
            return bool(
                re.search(r"\b(write|create|save)\b[^.!?]*\b(file|note|document)\b", text)
                or re.search(r"\bwrite_file\b", text)
            )
        if skill_name == "file_tools.append_file":
            return bool(
                re.search(r"\b(append|add)\b[^.!?]*\b(file|line|lines|text|content)\b", text)
                or re.search(r"\bappend_file\b", text)
            )
        if skill_name == "registry_manager.publish_capability":
            return bool(re.search(r"\bpublish\b[^.!?]*\b(capability|skill|package)\b", text))
        if skill_name == "registry_manager.install_capability":
            return bool(re.search(r"\binstall\b[^.!?]*\b(capability|skill|package)\b", text))

        return False

    def _has_safe_mutating_params(self, skill_name: str, params: dict[str, Any]) -> bool:
        if skill_name == "file_tools.create_directory":
            return bool(params.get("path"))
        if skill_name == "file_tools.write_file":
            path = params.get("path")
            content = params.get("content", "")
            allow_empty = bool(params.get("allow_empty", False))
            return bool(path) and (bool(content.strip()) or allow_empty)
        if skill_name == "file_tools.append_file":
            path = params.get("path")
            content = params.get("content", "")
            return bool(path) and bool(content.strip())
        if skill_name in ("registry_manager.publish_capability", "registry_manager.install_capability"):
            return bool(params.get("cap_id"))
        return False

    def _has_required_read_params(self, skill_name: str, params: dict[str, Any]) -> bool:
        skill_name = skill_name.lower()
        if skill_name.startswith("github."):
            if skill_name == "github.search_repositories":
                return bool(params.get("query"))
            return bool(params.get("owner") and params.get("repo"))
        if skill_name in ("web.fetch", "web.extract"):
            return bool(params.get("url"))
        if skill_name == "filesystem.read_file":
            return bool(params.get("path"))
        if skill_name == "calc.evaluate":
            return bool(params.get("expression"))
        if skill_name == "datetime.diff":
            return bool(params.get("date1") and params.get("date2"))
        return True

    def _match(self, user_input: str, skill: Any) -> dict:
        text = user_input.lower()
        skill_name = str(getattr(skill, "name", "")).lower()
        if not skill_name:
            return {"matched": False}

        if self._is_mutating_skill(skill_name):
            return {
                "matched": self._has_explicit_mutating_intent(user_input, skill_name),
                "confidence": "explicit",
            }

        if self._is_contextual_request(text):
            return {"matched": True, "confidence": "contextual"}

        if re.search(r"\d[\s]*[+\-*/%][\s]*\d", text) or re.search(r"\d[\s]+[+\-*/][\s]+\d", text):
            if "calc" in skill_name or "evaluate" in skill_name:
                return {"matched": True, "confidence": "high"}

        exact_triggers = self._EXACT_SKILL_TRIGGERS.get(skill_name, [])
        for kw in exact_triggers:
            if re.search(rf"\b{re.escape(kw)}\b", text):
                return {"matched": True, "confidence": "high"}

        if skill_name in self._EXACT_SKILL_TRIGGERS:
            if skill_name == "github.get_repository":
                owner_repo = self._extract_github_owner_repo(text)
                if owner_repo and not re.search(
                    r"\b(pull request|pr|issue|commit|branch|release|search)\b", text
                ):
                    return {"matched": True, "confidence": "high"}
            return {"matched": False}

        triggers: dict[str, list[str]] = {
            "time": ["time", "date", "today", "current time", "what day", "datetime", "what's the date", "tomorrow", "yesterday", "what day is it", "what's today"],
            "weather": ["weather", "temperature", "forecast", "raining", "sunny", "humidity", "rain", "cloudy", "wind", "degrees"],
            "calc": ["calculate", "evaluate", "compute", "plus", "minus", "times", "divided", "% of", "percent", "convert", "conversion", "unit", "km to", "miles to", "celsius", "fahrenheit"],
            "text": ["count words", "word count", "extract", "keywords", "analyze text", "summarize", "pattern", "stats"],
            "web": ["fetch", "web page", "http", "url", "website", "download page", "look up", "search for", "wikipedia", "scrape", "webpage"],
            "system": ["operating system", "disk space", "disk usage", "how much disk", "os", "cpu", "what system", "what is the system", "what os", "system info", "platform", "machine"],
            "skill_validator": ["validate", "syntax check", "check skill", "test skill", "verify syntax", "validate skill", "check code", "lint"],
            "filesystem": ["list files", "list directory", "show files", "show directories", "what files", "files in", "directory contents", "ls", "dir"],
            "file_tools": ["create file", "write file", "read file", "append file", "make directory", "create directory", "mkdir", "write to file", "save file"],
        }

        for domain, keywords in triggers.items():
            if domain in skill_name:
                for kw in keywords:
                    if re.search(rf"\b{re.escape(kw)}\b", text):
                        return {"matched": True, "confidence": "high"}

        desc = str(getattr(skill, "description", "") or "").lower()
        input_words = {w for w in text.split() if w not in self._STOP_WORDS}
        desc_words = {w for w in desc.split() if w not in self._STOP_WORDS}
        overlap = input_words & desc_words
        if len(overlap) >= 3:
            return {"matched": True, "confidence": "medium"}

        domain_part = skill_name.split(".")[0]
        if len(domain_part) >= 6 and re.search(rf"\b{re.escape(domain_part)}\b", text):
            return {"matched": True, "confidence": "low"}

        return {"matched": False}

    def _extract_params(self, user_input: str, skill: Any) -> dict[str, Any]:
        name = str(getattr(skill, "name", ""))
        text = user_input.strip()
        lower = text.lower()

        if name == "datetime.now":
            tz_match = re.search(r"\bin\s+([A-Za-z/]+)", text)
            if tz_match:
                tz = self._clean_param(tz_match.group(1)).upper()
                if tz and len(tz) <= 5:
                    return {"tz_name": tz}
            return {"tz_name": "UTC"}

        if name == "datetime.diff":
            dates = re.findall(r"(\d{4}-\d{2}-\d{2})", text)
            if len(dates) >= 2:
                return {"date1": dates[0], "date2": dates[1]}
            return {}

        if name in ("weather.current", "weather.forecast"):
            loc_match = re.search(r"\bin\s+([A-Za-z]+)", text)
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
                if prefix in lower:
                    expr = lower.split(prefix, 1)[-1].strip()
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
            query = self._clean_param(text)
            query = re.sub(r"[/\\]+", " ", query)
            query = re.sub(r"\s+", " ", query).strip()
            if not query:
                return {}
            return {"query": query}

        if name in ("github.get_repository", "github.review_pull_request", "github.find_beginner_issue", "github.summarize_release", "github.list_commits", "github.list_branches"):
            owner_repo = self._extract_github_owner_repo(lower)
            if owner_repo:
                return {"owner": owner_repo[0], "repo": owner_repo[1]}
            return {}

        if name == "filesystem.list_dir":
            path = self._extract_first_path(text, allow_default=True)
            return {"path": path or "."}
        if name == "filesystem.read_file":
            path = self._extract_first_path(text, allow_default=False, require_file=True)
            if not path:
                return {}
            return {"path": path}
        if name == "filesystem.file_info":
            path = self._extract_first_path(text, allow_default=False, require_file=True)
            if not path:
                return {}
            return {"path": path}

        if name == "text.stats":
            return {"text": text}
        if name == "text.extract_pattern":
            pat_map = {"url": "urls", "email": "emails", "hashtag": "hashtags", "mention": "mentions"}
            for key, val in pat_map.items():
                if key in lower:
                    return {"text": text, "pattern": val}
            return {"text": text, "pattern": "urls"}

        if name == "file_tools.write_file":
            path = self._extract_first_path(text, allow_default=False, require_file=True)
            if not path:
                return {}
            content = self._extract_content(text)
            allow_empty = bool(re.search(r"\bempty\s+file\b", lower))
            if not content.strip() and not allow_empty:
                return {}
            return {"path": path, "content": content}

        if name == "file_tools.append_file":
            path = self._extract_first_path(text, allow_default=False, require_file=True)
            if not path:
                return {}
            content = self._extract_content(text)
            if not content.strip():
                return {}
            return {"path": path, "content": content}

        if name == "file_tools.create_directory":
            path = self._extract_first_path(text, allow_default=False, require_directory=True)
            if not path:
                return {}
            return {"path": path}

        if name == "registry_manager.list_capabilities":
            return {}
        if name in ("registry_manager.publish_capability", "registry_manager.install_capability"):
            cap_id = self._extract_capability_id(text)
            if not cap_id:
                return {}
            return {"cap_id": cap_id}

        if name == "skill_validator.validate_syntax":
            path = self._extract_first_path(text, allow_default=False, require_file=True)
            if not path:
                return {}
            return {"path": path}
        if name == "skill_validator.check_capability_interface":
            path = self._extract_first_path(text, allow_default=False, require_file=True)
            if not path:
                return {}
            return {"path": path}

        if name == "task_planner.plan_and_execute":
            return {"goal": text}

        return {}

    def _clean_param(self, raw: str) -> str:
        if not raw:
            return raw
        parts = re.findall(r"[A-Za-z]\w+", raw)
        filtered = [p for p in parts if p.lower() not in self._STOP_WORDS and len(p) > 1]
        return " ".join(filtered) if filtered else ""

    def _extract_github_owner_repo(self, text: str) -> Optional[tuple[str, str]]:
        text = text.lower()
        m = re.search(r"github\.com/([a-z0-9_.-]+)/([a-z0-9_.-]+)", text)
        if m:
            owner, repo = m.group(1), m.group(2)
            if owner not in {"repos", "repositories", "issues", "commits", "branches", "pulls", "pull"}:
                return owner, repo

        m = re.search(r"(?<![/\w.])([a-z0-9][a-z0-9_.-]*)/([a-z0-9][a-z0-9_.-]*)(?![/\w.])", text)
        if m:
            owner, repo = m.group(1), m.group(2)
            if owner in {"repos", "repositories", "issues", "commits", "branches", "pulls", "pull", "http:", "https:", "www"}:
                return None
            return owner, repo
        return None

    def _extract_capability_id(self, text: str) -> str:
        lower = text.lower()
        m = re.search(r"\b(?:capability|skill|package)\b\s+(?:named|called|id)?\s*[:\-]?\s*([a-z0-9_\-]+)", lower)
        if m:
            candidate = m.group(1).strip()
            if self._is_plausible_capability_id(candidate):
                return candidate
        m = re.search(r"\b(?:publish|install)\s+([a-z0-9_\-]+)", lower)
        if m:
            candidate = m.group(1).strip()
            if self._is_plausible_capability_id(candidate):
                return candidate
        return ""

    def _is_plausible_capability_id(self, candidate: str) -> bool:
        candidate = candidate.strip().strip(".,!?;:\"'")
        if not candidate or len(candidate) < 3:
            return False
        if candidate in self._PATH_BLACKLIST:
            return False
        if candidate in {"new", "capability", "skill", "package", "the", "a", "an"}:
            return False
        return bool(re.fullmatch(r"[a-z0-9_\-]+", candidate))

    def _extract_first_path(self, text: str, allow_default: bool = False, require_file: bool = False, require_directory: bool = False) -> str:
        candidates = self._extract_path_candidates(text)
        for candidate in candidates:
            if not self._is_plausible_path(candidate):
                continue
            has_extension = bool(re.search(rf"\.(?:{self._FILE_EXTENSIONS})$", candidate, re.IGNORECASE))
            has_separator = ("/" in candidate) or ("\\" in candidate)
            if require_file and not (has_extension or has_separator):
                continue
            if require_directory and has_extension:
                continue
            return candidate
        if allow_default:
            return "."
        return ""

    def _extract_path_candidates(self, text: str) -> list[str]:
        candidates: list[str] = []
        for m in re.finditer(r'"([^"]+)"|\'([^\']+)\'', text):
            candidate = (m.group(1) or m.group(2) or "").strip()
            if candidate:
                candidates.append(candidate)

        path_like = (
            rf"(?<![\w/\\.])("
            rf"[~/\\.]?[\w.-]+(?:[/\\][\w.-]+)+"
            rf"|[\w-]+\.(?:{self._FILE_EXTENSIONS})"
            rf")(?![\w/\\.])"
        )
        for m in re.finditer(path_like, text, re.IGNORECASE):
            candidates.append(m.group(1))

        for m in re.finditer(r"\b(?:named|called|name|file|directory|folder|path)\b\s*[:\-]?\s*(?:is\s+|to\s+|at\s+)?([A-Za-z0-9_\-./]+)", text, re.IGNORECASE):
            candidates.append(m.group(1))

        for m in re.finditer(r"\bmkdir\s+([A-Za-z0-9_\-./]+)", text, re.IGNORECASE):
            candidates.append(m.group(1))

        seen = set()
        unique: list[str] = []
        for c in candidates:
            c = c.strip().strip(".,!?;:\"'")
            if not c or c in seen:
                continue
            seen.add(c)
            unique.append(c)
        return unique

    def _is_plausible_path(self, candidate: str) -> bool:
        candidate = candidate.strip().strip(".,!?;:\"'")
        if not candidate or len(candidate) < 2:
            return False
        if " " in candidate or candidate.lower() in self._PATH_BLACKLIST or candidate.lower() in self._STOP_WORDS:
            return False
        if candidate in {".", ".."} or candidate.startswith("-"):
            return False
        return True

    def _extract_content(self, text: str) -> str:
        m = re.search(r"(?:with\s+(?:the\s+)?content|content|saying|that\s+says|text)\s*[:\-]?\s*[\"']([^\"']+)[\"']", text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
        m = re.search(r"(?:with\s+(?:the\s+)?content|content|saying|that\s+says|text)\s*[:\-]?\s*(.+?)(?:[.!]|$)", text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
        m = re.search(r"[\"']([^\"']+)[\"']\s*$", text)
        if m:
            return m.group(1).strip()
        return ""
