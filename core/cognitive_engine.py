from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from .goals import GoalEngine
    from .identity import IdentitySpec
    from .memory import MemoryStore
    from .relationships import IdentityGraph
    from .skills import SkillRegistry


@dataclass
class ComposedContext:
    """
    The assembled context block ready to be injected into an LLM prompt.
    Each section is optional and can be toggled per use case.
    """
    identity_block: str = ""
    memory_block: str = ""
    skills_block: str = ""
    goals_block: str = ""
    relationships_block: str = ""
    motivations_block: str = ""
    timeline_block: str = ""
    custom_blocks: Dict[str, str] = field(default_factory=dict)

    def render(self, separator: str = "\n\n") -> str:
        """
        Render the full context as a single string.
        Sections are included only if non-empty.
        """
        sections = []
        if self.identity_block:
            sections.append(self.identity_block)
        if self.memory_block:
            sections.append(self.memory_block)
        if self.skills_block:
            sections.append(self.skills_block)
        if self.goals_block:
            sections.append(self.goals_block)
        if self.relationships_block:
            sections.append(self.relationships_block)
        if self.motivations_block:
            sections.append(self.motivations_block)
        if self.timeline_block:
            sections.append(self.timeline_block)
        for block in self.custom_blocks.values():
            if block:
                sections.append(block)
        return separator.join(sections)

    def token_estimate(self, chars_per_token: float = 4.0) -> int:
        """Rough estimate of token usage for budget tracking."""
        return int(len(self.render()) / chars_per_token)


class ContextComposer:
    """
    Assembles runtime context from all identity modules.

    The ContextComposer is the bridge between the bounded modules
    (Identity, Memory, Knowledge, Skills, Goals, Relationships)
    and the LLM adapter layer. It does not call any LLM itself —
    it produces a ComposedContext that adapters inject into prompts.
    """

    def __init__(
        self,
        max_tokens: int = 4000,
        include_identity: bool = True,
        include_memory: bool = True,
        include_skills: bool = True,
        include_goals: bool = True,
        include_relationships: bool = False,
        include_motivations: bool = False,
        include_timeline: bool = False,
    ):
        self.max_tokens = max_tokens
        self.include_identity = include_identity
        self.include_memory = include_memory
        self.include_skills = include_skills
        self.include_goals = include_goals
        self.include_relationships = include_relationships
        self.include_motivations = include_motivations
        self.include_timeline = include_timeline

    def compose(
        self,
        identity: "IdentitySpec",
        memory_store: Optional["MemoryStore"] = None,
        skill_registry: Optional["SkillRegistry"] = None,
        goal_engine: Optional["GoalEngine"] = None,
        identity_graph: Optional["IdentityGraph"] = None,
        motivation_engine: Optional[Any] = None,
        timeline_registry: Optional[Any] = None,
        query: Optional[str] = None,
        top_k_memories: int = 5,
    ) -> ComposedContext:
        """
        Compose a full runtime context for the given identity.
        """
        ctx = ComposedContext()

        if self.include_identity:
            ctx.identity_block = self._render_identity(identity)

        if self.include_memory and memory_store:
            ctx.memory_block = self._render_memory(
                memory_store, identity.id, query, top_k_memories
            )

        if self.include_skills and skill_registry:
            ctx.skills_block = skill_registry.to_prompt_manifest()

        if self.include_goals and goal_engine:
            ctx.goals_block = goal_engine.to_prompt_summary()

        if self.include_relationships and identity_graph:
            ctx.relationships_block = identity_graph.to_prompt_block(identity.id)

        if self.include_motivations and motivation_engine:
            ctx.motivations_block = motivation_engine.to_prompt_block()

        if self.include_timeline and timeline_registry:
            timeline = timeline_registry.get(identity.id)
            if timeline:
                ctx.timeline_block = timeline.narrative()

        return ctx

    def _render_identity(self, identity: "IdentitySpec") -> str:
        lines = [
            f"## Identity: {identity.name}",
        ]
        if identity.role:
            lines.append(f"Role: {identity.role}")
        if identity.persona:
            lines.append(f"Persona: {identity.persona}")
        if identity.core_values:
            values_str = ", ".join(
                cv.name if hasattr(cv, 'name') else str(cv) for cv in identity.core_values
            )
            lines.append(f"Core Values: {values_str}")
        if identity.communication_style:
            lines.append(f"Style: {identity.communication_style}")
        if identity.system_prompt:
            lines.append(f"\n{identity.system_prompt}")
        return "\n".join(lines)

    def _render_memory(
        self,
        store: "MemoryStore",
        identity_id: str,
        query: Optional[str],
        top_k: int,
    ) -> str:
        if query:
            items = [
                f for f in store.all()
                if query.lower() in f.content.lower()
            ][:top_k]
        else:
            items = store.recent(n=top_k)
        if not items:
            return ""
        lines = ["## Relevant Memory"]
        for item in items:
            lines.append(f"  [{item.memory_type.value.upper()}] {item.content}")
        return "\n".join(lines)

    def _render_relationships(
        self, graph: "IdentityGraph", identity_id: str
    ) -> str:
        edges = graph.get_relationships(identity_id)
        if not edges:
            return ""
        lines = ["## Relationships"]
        for e in edges:
            lines.append(
                f"  -> {e.target_id} [{e.edge_type.value}] "
                f"trust={e.trust_level.name} strength={e.strength:.2f}"
            )
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Backward-compatible API (matches old ContextBuilder.build)
    # ------------------------------------------------------------------

    async def build_context_string(
        self,
        message: str,
        identity: "IdentitySpec",
        user_id: str = "",
        session_id: str = "",
        include_relationships: bool = False,
        top_k_memories: int = 5,
    ) -> Dict[str, Any]:
        """
        DEPRECATED: Legacy API matching ContextBuilder.build().
        Returns {'context': str, 'memories_used': int}.
        """
        ctx = self.compose(
            identity=identity,
            query=message,
            top_k_memories=top_k_memories,
        )
        memories_used = ctx.memory_block.count("\n  [") if ctx.memory_block else 0
        return {
            "context": ctx.render(),
            "memories_used": memories_used,
        }
