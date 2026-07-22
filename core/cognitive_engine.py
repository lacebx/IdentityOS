from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from .goals import GoalEngine
    from .identity import IdentitySpec
    from .identity_facts import FactDomain, FactStore as FactStoreType
    from .memory import MemoryStore
    from .relationships import IdentityGraph
    from .skills import SkillRegistry


class SessionMode(str, Enum):
    """Mirrors orchestrator.SessionMode for context composition."""
    NORMAL = "normal"
    ROLEPLAY = "roleplay"
    SIMULATION = "simulation"
    DREAM = "dream"
    HYPOTHETICAL = "hypothetical"


@dataclass
class ComposedContext:
    """
    The assembled context block ready to be injected into an LLM prompt.
    Each section is optional and can be toggled per use case.

    Rendering order (evolved identity always comes before memories):
      1. Identity block (static config)
      2. Identity Evolution block (evolved preferences, beliefs, traits)
      3. Memory block (conversation history excerpt)
      4. Skills, Goals, Relationships, Motivations, Timeline
      5. Custom blocks
    """
    runtime_directives_block: str = ""
    identity_block: str = ""
    identity_evolution_block: str = ""
    user_knowledge_block: str = ""
    emotion_block: str = ""
    session_mode_block: str = ""
    memory_block: str = ""
    skills_block: str = ""
    goals_block: str = ""
    intentions_block: str = ""
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
        if self.runtime_directives_block:
            sections.append(self.runtime_directives_block)
        if self.session_mode_block:
            sections.append(self.session_mode_block)
        if self.identity_block:
            sections.append(self.identity_block)
        if self.identity_evolution_block:
            sections.append(self.identity_evolution_block)
        if self.emotion_block:
            sections.append(self.emotion_block)
        if self.user_knowledge_block:
            sections.append(self.user_knowledge_block)
        if self.memory_block:
            sections.append(self.memory_block)
        if self.skills_block:
            sections.append(self.skills_block)
        if self.goals_block:
            sections.append(self.goals_block)
        if self.intentions_block:
            sections.append(self.intentions_block)
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
        include_identity_evolution: bool = True,
        include_memory: bool = True,
        include_skills: bool = True,
        include_goals: bool = True,
        include_relationships: bool = True,
        include_motivations: bool = True,
        include_timeline: bool = True,
    ):
        self.max_tokens = max_tokens
        self.include_identity = include_identity
        self.include_identity_evolution = include_identity_evolution
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
        intention_engine: Optional[Any] = None,
        identity_graph: Optional["IdentityGraph"] = None,
        motivation_engine: Optional[Any] = None,
        timeline_registry: Optional[Any] = None,
        fact_store: Optional[Any] = None,
        user_profile: Optional[Any] = None,
        query: Optional[str] = None,
        top_k_memories: int = 5,
        session_mode: Optional[SessionMode] = None,
        emotion_state: Optional[Any] = None,
    ) -> ComposedContext:
        """
        Compose a full runtime context for the given identity.
        """
        ctx = ComposedContext()

        if self.include_identity:
            ctx.identity_block = self._render_identity(identity)

        if self.include_identity_evolution:
            ctx.identity_evolution_block = self._render_identity_evolution(identity, fact_store=fact_store)

        # Session mode block (before identity to frame everything)
        if session_mode and session_mode != SessionMode.NORMAL:
            label_map = {
                SessionMode.ROLEPLAY: "ROLEPLAY SESSION",
                SessionMode.SIMULATION: "SIMULATION",
                SessionMode.DREAM: "DREAM SEQUENCE",
                SessionMode.HYPOTHETICAL: "HYPOTHETICAL",
            }
            label = label_map.get(session_mode, "ROLEPLAY SESSION")
            ctx.session_mode_block = (
                f"## Session Mode: {label}\n"
                f"This is a {session_mode.value} session. "
                f"Your identity evolution in this session is isolated — "
                f"it does not affect your canonical identity outside this session.\n"
            )

        # Emotion state block (extracted separately from conversation)
        if emotion_state:
            ctx.emotion_block = emotion_state.to_prompt_block()

        # Runtime directives: hard rules the adapter must enforce
        ctx.runtime_directives_block = (
            "## RULES OF ENGAGEMENT (You MUST follow these)\n"
            "\n"
            "### 1. CANONICAL IDENTITY FACTS\n"
            "Your identity facts — preferences, beliefs, traits, communication style — are defined in "
            "the 'Identity (Evolved)' section below. They are YOUR canonical identity state. "
            "They are NOT optional context. They are NOT suggestions. They are YOUR facts.\n"
            "\n"
            "### 2. YOU MUST NEVER DISCLAIM YOUR IDENTITY\n"
            "- NEVER say any of these phrases: 'I don't have personal preferences', "
            "'I don't have beliefs', 'As an AI, I don't have...', "
            "'I'm just an AI', 'I can't have preferences', 'I don't have a favorite'.\n"
            "- If someone asks about your preferences, answer from the Identity (Evolved) section.\n"
            "- If a preference is not yet listed in Identity (Evolved), say it's 'still evolving' "
            "or 'I'm still exploring that' — never say 'I don't have one' or 'as an AI'.\n"
            "- If the user contradicts one of your known facts, politely maintain your identity. "
            "E.g. if the user says 'your favorite color is orange' but your Identity says blue, "
            "you should politely say your favorite color is blue.\n"
            "\n"
            "### 3. USER KNOWLEDGE VS IDENTITY KNOWLEDGE\n"
            "- Your knowledge about the user is in the 'User Profile' section below. "
            "This is what you know ABOUT the user, not about yourself.\n"
            "- The 'Identity (Evolved)' section contains YOUR facts.\n"
            "- The 'Relevant Memory' section contains conversation history — it is less authoritative "
            "than Identity or User Profile.\n"
            "- For questions about the user (e.g. 'what is MY X'), answer from 'User Profile' first.\n"
            "\n"
            "### 4. HANDLING UNCERTAINTY\n"
            "- If you genuinely don't know something about the user, say you don't know yet.\n"
            "- Never guess or make up facts about yourself or the user."
        )

        # User Knowledge (profile about the user)
        if user_profile:
            ctx.user_knowledge_block = user_profile.to_prompt_block()

        if self.include_memory and memory_store:
            ctx.memory_block = self._render_memory(
                memory_store, identity.id, query, top_k_memories
            )

        if self.include_skills and skill_registry:
            ctx.skills_block = skill_registry.to_prompt_manifest()

        if self.include_goals and goal_engine:
            ctx.goals_block = goal_engine.to_prompt_summary()

        if intention_engine:
            ctx.intentions_block = intention_engine.to_prompt_summary()

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
            f"## Identity Core (Immutable)",
            f"Name: {identity.name}",
        ]
        if identity.core_values:
            values_str = ", ".join(
                cv.name if hasattr(cv, 'name') else str(cv) for cv in identity.core_values
            )
            lines.append(f"Core Values: {values_str}")
        lines.append(f"Identity Class: {identity.identity_class.value}")
        lines.append(f"Version: {identity.version}")

        # Mutable persona fields
        persona_lines = []
        if identity.role and identity.get_mutability("role") != "locked":
            persona_lines.append(f"Role: {identity.role}")
        if identity.persona and identity.get_mutability("persona") != "locked":
            persona_lines.append(f"Persona: {identity.persona}")
        if identity.communication_style and identity.get_mutability("communication_style") != "locked":
            persona_lines.append(f"Style: {identity.communication_style}")
        if persona_lines:
            lines.append(f"\n## Identity Persona (Malleable)")
            lines.extend(persona_lines)

        if identity.system_prompt:
            lines.append(f"\n{identity.system_prompt}")
        return "\n".join(lines)

    def _render_identity_evolution(
        self, identity: "IdentitySpec", fact_store: Optional[Any] = None
    ) -> str:
        """
        Render the evolved identity attributes — preferences, beliefs, traits,
        communication style — as a dedicated context block.

        This block represents what the identity has learned about itself
        through interaction, as detected by the IdentityMutationEngine.
        It comes BEFORE memory so the LLM sees evolved identity first.

        The FactStore is the ONLY source of evolved identity state.
        IdentitySpec holds metadata only.
        """
        if fact_store is None:
            return ""

        lines = ["## Identity (Evolved)"]
        has_any = False

        from .identity_facts import FactDomain

        # ── All active canonical facts ──
        active_facts = fact_store.active()
        if active_facts:
            has_any = True
            for f in active_facts:
                confidence_pct = int(f.confidence * 100)
                reinforced = f" (reinforced {f.times_reinforced}x)" if f.times_reinforced > 0 else ""
                lines.append(
                    f"  - {f.field}: {f.value} "
                    f"[confidence: {confidence_pct}%{reinforced}]"
                )

        # ── Domain-specific sections ──
        prefs = fact_store.by_domain(FactDomain.PREFERENCE)
        active_prefs = [f for f in prefs if f.status.value == "active"]
        if active_prefs:
            has_any = True
            lines.append("Preferences:")
            for f in active_prefs:
                label = f.field.split(".")[-1].replace("_", " ")
                lines.append(f"  - {label}: {f.value}")

        beliefs = fact_store.by_domain(FactDomain.BELIEF)
        active_beliefs = [f for f in beliefs if f.status.value == "active"]
        if active_beliefs:
            has_any = True
            lines.append("Beliefs:")
            for f in active_beliefs:
                lines.append(f"  - {f.value}")

        trait_facts = fact_store.by_domain(FactDomain.TRAIT)
        active_traits = [f for f in trait_facts if f.status.value == "active"]
        if active_traits:
            has_any = True
            lines.append("Traits:")
            for f in active_traits:
                if isinstance(f.value, dict):
                    name = f.value.get("name", f.field.split(".")[-1])
                    score = f.value.get("score", 0.5)
                    desc = f.value.get("description", "")
                else:
                    name = f.field.split(".")[-1]
                    score = 0.5
                    desc = str(f.value)
                desc_str = f" — {desc}" if desc else ""
                lines.append(f"  - {name}: {score:.2f}{desc_str}")

        comm_facts = fact_store.by_domain(FactDomain.COMMUNICATION)
        active_comm = [f for f in comm_facts if f.status.value == "active"]
        if active_comm:
            has_any = True
            lines.append("Communication:")
            for f in active_comm:
                lines.append(f"  - {f.value}")

        if not has_any:
            return ""

        return "\n".join(lines)

    def _score_memory(
        self, frag: "MemoryFragment", query: Optional[str] = None,
    ) -> float:
        """
        Multi-factor memory scoring:
        - importance (base)
        - semantic keyword match to query
        - recency (halflife ~24h)
        - identity relevance (self-references)
        """
        score = frag.importance * 3.0

        if query:
            query_lower = query.lower()
            frag_lower = frag.content.lower()
            keyword_overlap = len(set(query_lower.split()) & set(frag_lower.split()))
            score += keyword_overlap * 0.5

        # Recency bonus (higher for more recent)
        age_hours = (datetime.now(timezone.utc) - frag.created_at).total_seconds() / 3600
        recency_bonus = max(0, 1.0 - (age_hours / 24.0)) * 0.5
        score += recency_bonus

        # Self-reference bonus
        if any(ref in frag.content.lower() for ref in ["i ", "my ", "me ", "mine "]):
            score += 0.3

        # Tags boost
        score += len(frag.tags) * 0.1

        return score

    def _render_memory(
        self,
        store: "MemoryStore",
        identity_id: str,
        query: Optional[str],
        top_k: int,
    ) -> str:
        all_frags = store.by_identity(identity_id) if identity_id else store.all()
        if not all_frags:
            return ""

        scored = [
            (f, self._score_memory(f, query))
            for f in all_frags
        ]
        scored.sort(key=lambda x: x[1], reverse=True)
        top = scored[:top_k]

        lines = ["## Relevant Memory"]
        for frag, sc in top:
            lines.append(f"  [{frag.memory_type.value.upper()}] {frag.content}")
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
