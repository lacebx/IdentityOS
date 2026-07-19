from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class SkillType(Enum):
    TOOL = "tool"           # Executable function/API call
    REASONING = "reasoning" # Reasoning pattern or heuristic
    DOMAIN = "domain"       # Domain-specific knowledge application
    SOCIAL = "social"       # Interpersonal/communication skill
    META = "meta"           # Skills about using skills


class SkillStatus(Enum):
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    EXPERIMENTAL = "experimental"
    DISABLED = "disabled"


@dataclass
class SkillParameter:
    """Defines a parameter for a skill invocation."""
    name: str
    type: str
    description: str
    required: bool = True
    default: Any = None


@dataclass
class SkillResult:
    """Result returned from a skill execution."""
    skill_id: str
    success: bool
    output: Any
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Skill:
    """
    A discrete, executable capability an identity can perform.
    Skills are composable and can depend on other skills or knowledge packs.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    skill_type: SkillType = SkillType.TOOL
    status: SkillStatus = SkillStatus.ACTIVE
    version: str = "1.0.0"
    parameters: List[SkillParameter] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    depends_on_skills: List[str] = field(default_factory=list)  # skill IDs
    depends_on_knowledge: List[str] = field(default_factory=list)  # knowledge pack IDs
    handler: Optional[Callable] = field(default=None, repr=False)
    usage_count: int = 0
    last_used: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def invoke(self, **kwargs) -> SkillResult:
        """Execute this skill with the given parameters."""
        if self.status == SkillStatus.DISABLED:
            return SkillResult(
                skill_id=self.id,
                success=False,
                output=None,
                error=f"Skill '{self.name}' is disabled."
            )
        if not self.handler:
            return SkillResult(
                skill_id=self.id,
                success=False,
                output=None,
                error=f"Skill '{self.name}' has no handler registered."
            )
        start = datetime.utcnow()
        try:
            result = self.handler(**kwargs)
            elapsed = (datetime.utcnow() - start).total_seconds() * 1000
            self.usage_count += 1
            self.last_used = datetime.utcnow()
            return SkillResult(
                skill_id=self.id,
                success=True,
                output=result,
                execution_time_ms=elapsed
            )
        except Exception as e:
            elapsed = (datetime.utcnow() - start).total_seconds() * 1000
            return SkillResult(
                skill_id=self.id,
                success=False,
                output=None,
                error=str(e),
                execution_time_ms=elapsed
            )


class SkillRegistry:
    """
    Registry for all skills available to an identity.
    Skills can be loaded from skill packs or registered directly.
    """

    def __init__(self):
        self._skills: Dict[str, Skill] = {}
        self._name_index: Dict[str, str] = {}  # name -> id

    def register(self, skill: Skill) -> None:
        """Register a skill in the registry."""
        self._skills[skill.id] = skill
        self._name_index[skill.name] = skill.id

    def unregister(self, skill_id: str) -> bool:
        """Remove a skill from the registry."""
        skill = self._skills.pop(skill_id, None)
        if skill:
            self._name_index.pop(skill.name, None)
            return True
        return False

    # Backward-compatible aliases used by SDK
    def load(self, item: Any) -> None:
        self.register(item)

    def unload(self, item_id: str) -> bool:
        return self.unregister(item_id)

    def get(self, skill_id: str) -> Optional[Skill]:
        return self._skills.get(skill_id)

    def get_by_name(self, name: str) -> Optional[Skill]:
        sid = self._name_index.get(name)
        return self._skills.get(sid) if sid else None

    def list_by_type(self, skill_type: SkillType) -> List[Skill]:
        return [s for s in self._skills.values() if s.skill_type == skill_type]

    def list_active(self) -> List[Skill]:
        return [s for s in self._skills.values() if s.status == SkillStatus.ACTIVE]

    def invoke(self, skill_name: str, **kwargs) -> SkillResult:
        """Invoke a skill by name."""
        skill = self.get_by_name(skill_name)
        if not skill:
            return SkillResult(
                skill_id="unknown",
                success=False,
                output=None,
                error=f"Skill '{skill_name}' not found in registry."
            )
        return skill.invoke(**kwargs)

    def to_prompt_manifest(self) -> str:
        """Generate a prompt-ready manifest of available skills."""
        active = self.list_active()
        if not active:
            return "No skills available."
        lines = ["Available Skills:"]
        for skill in active:
            params = ", ".join(p.name for p in skill.parameters)
            lines.append(f"  - {skill.name}({params}): {skill.description}")
        return "\n".join(lines)

    def __len__(self) -> int:
        return len(self._skills)
