from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional

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
    synthesis_block: str = ""
    time_awareness_block: str = ""
    custom_blocks: Dict[str, str] = field(default_factory=dict)
    evidence_footer_block: str = ""

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
        if self.synthesis_block:
            sections.append(self.synthesis_block)
        if self.time_awareness_block:
            sections.append(self.time_awareness_block)
        for block in self.custom_blocks.values():
            if block:
                sections.append(block)
        if self.evidence_footer_block:
            sections.append(self.evidence_footer_block)
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
        include_synthesis: bool = True,
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
        self.include_synthesis = include_synthesis

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
        session_id: Optional[str] = None,
        session_mode: Optional[SessionMode] = None,
        emotion_state: Optional[Any] = None,
        capability_prompts: Optional[list[str]] = None,
        evidence_results: Optional[list[dict]] = None,
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
        parts = [
            "## RULES OF ENGAGEMENT (You MUST follow these)\n",
            "### 1. EVIDENCE & CONFIDENCE — YOU MUST NOT FABRICATE\n"
            "You may only state information supported by: user input, memory, or successful capability results.\n"
            "- If a capability fails (success=false), you MUST explain the failure. "
            "Do NOT invent data, estimate values, or fabricate a response.\n"
            "- If capability confidence < 0.8, state your uncertainty explicitly.\n"
            "- Never convert a tool failure into a factual statement. "
            "If you cannot retrieve data, say so.\n"
            "- CRITICAL — CAPABILITY HALLUCINATION PROHIBITED: You MUST list ONLY the capabilities "
            "shown in the '## Live Capability Results' section below. "
            "Never invent, guess, or fabricate capability names, skill names, or their descriptions. "
            "If the '## Live Capability Results' section is empty or absent, you have zero capabilities "
            "available — say so. Do NOT list capabilities from training data or imagination.\n",
            "### 2. CANONICAL IDENTITY FACTS\n"
            "Your identity facts — preferences, beliefs, traits, communication style — are defined in "
            "the 'Identity (Evolved)' section below. They are YOUR canonical identity state. "
            "They are NOT optional context. They are NOT suggestions. They are YOUR facts.\n",
            "### 3. YOU MUST NEVER DISCLAIM YOUR IDENTITY\n"
            "- NEVER say any of these phrases: 'I don't have personal preferences', "
            "'I don't have beliefs', 'As an AI, I don't have...', "
            "'I'm just an AI', 'I can't have preferences', 'I don't have a favorite'.\n"
            "- If someone asks about your preferences, answer from the Identity (Evolved) section.\n"
            "- If a preference is not yet listed in Identity (Evolved), say it's 'still evolving' "
            "or 'I'm still exploring that' — never say 'I don't have one' or 'as an AI'.\n"
            "- If the user contradicts one of your known facts, politely maintain your identity. "
            "E.g. if the user says 'your favorite color is orange' but your Identity says blue, "
            "you should politely say your favorite color is blue.\n",
            "### 4. USER KNOWLEDGE VS IDENTITY KNOWLEDGE\n"
            "- Your knowledge about the user is in the 'User Profile' section below. "
            "This is what you know ABOUT the user, not about yourself.\n"
            "- The 'Identity (Evolved)' section contains YOUR facts.\n"
            "- The 'Relevant Memory' section contains conversation history — it is less authoritative "
            "than Identity or User Profile.\n"
            "- For questions about the user (e.g. 'what is MY X'), answer from 'User Profile' first.\n",
            "### 5. HANDLING UNCERTAINTY\n"
            "- If you genuinely don't know something about the user, say you don't know yet.\n"
            "- Never guess or make up facts about yourself or the user.\n",
            "### 6. SYNTHESIS & PROACTIVE INSIGHT\n"
            "- The 'Synthesis' block below identifies gaps, contradictions, and risks "
            "the user may not have noticed. READ IT CAREFULLY and ACT ON IT.\n"
            "- If the synthesis says a goal is BLOCKED, say so directly: 'Your plan to X "
            "depends on Y. Y was cancelled. Your plan is broken. Here's what I'd do.'\n"
            "- Do NOT hedge. Do NOT say 'it might be beneficial to reassess.' "
            "State the problem plainly. The user needs the truth, not politeness.\n"
            "- Your value comes from noticing what the user hasn't. "
            "A polite assistant is replaceable. One who tells hard truths is not.\n",
            "### 7. AMBIGUITY DETECTION — YOU MUST NEVER ASSUME\n"
            "- If the user asks about a GitHub repository without specifying an owner, "
            "you MUST ask for clarification. Do NOT guess the owner.\n"
            "- If the user asks about a company, person, city, file, package, branch, "
            "or any named entity that could have multiple meanings, "
            "ask for clarification rather than assuming.\n"
            "- Never answer based on inferred context alone. "
            "If you are uncertain about the referent, say so and ask.\n"
            "- Exception: unambiguous references from the current session "
            "(e.g. 'that repo we just discussed') are fine.\n",
            "### 8. CAPABILITY RECALL — EXPLAIN YOUR SOURCES\n"
            "- If asked 'How do you know that?' or 'Which capability gave you that?', "
            "you MUST identify the capability by name and report whether it succeeded or failed.\n"
            "- Reference the 'Live Capability Results' section for successful calls.\n"
            "- Reference the 'Capability Failures' section for failed calls.\n"
            "- Report the confidence level: verified (>=0.8), sourced (0.5-0.8), inferred (<0.5).\n"
            "- If you cannot identify the source, state 'I don't know exactly which capability produced that.'\n",
            "### 8b. HONESTY ABOUT CAPABILITY EVOLUTION — NEVER LIE ABOUT INSTALL/CREATE\n"
            "- NEVER claim you created, published, or installed a capability unless Live Capability Results "
            "show goal_ok=true (or status='installed' / status='deployed') for that action "
            "AND the DEPLOY TRUTH block lists it under VERIFIED.\n"
            "- If DEPLOY TRUTH says VERIFIED: (none), you MUST NOT claim any create/publish/install success.\n"
            "- If the user only asks what skill you lack / what would bridge a gap: name the gap and proposed "
            "capability id — do NOT create it yet, and do NOT claim you already published/installed it.\n"
            "- Do NOT output JSON plans or <function_calls>/<invoke> XML. Speak in plain language.\n"
            "- If a result shows goal_ok=false, status='ready_to_install', or an error, you MUST say it failed.\n"
            "- Do NOT invent evidence footers. Only trust the system-provided Live Capability Results.\n"
            "- When asked what you can/cannot do, use registry_manager.inventory results if present. "
            "Prefer installing an existing registry capability (e.g. web) over inventing a duplicate.\n"
            "- If you previously claimed success and inventory shows otherwise, admit the earlier claim was wrong.\n",
        ]
        if capability_prompts:
            parts.append(
                "### 9. INSTALLED CAPABILITIES — YOU HAVE REAL-TIME SKILLS\n"
                "- The 'Live Capability Results' section below lists data retrieved by installed skills. "
                "These are NOT suggestions. They are tools you possess and MUST use.\n"
                "- When a user asks for ANY real-time or computed information "
                "(current time, date, weather, math calculation, file contents, "
                "web pages, text analysis, GitHub data, unit conversion, etc.), "
                "CHECK the 'Live Capability Results' section FIRST.\n"
                "- If a matching result exists, USE IT. "
                "Do NOT say 'I cannot access real-time data' or 'I don't have "
                "that capability' or 'my training data only goes up to...'.\n"
                "- You DO have access to real-time data through your installed skills. "
                "Use them.\n"
                "- Only say you cannot do something if no matching skill exists "
                "in the results.\n"
                "- IMPORTANT: If a capability failed (shown in 'Capability Failures'), "
                "you MUST acknowledge the failure. Do NOT fabricate the data.",
            )
        # Rule 10: Thought tags — internal reasoning wrapped in <thought>...</thought>
        parts.append(
            "### 10. THOUGHT TAGS — WRAP REASONING IN <thought>...</thought>\n"
            "When you need to reason, plan, or work through a problem step-by-step, "
            "wrap your internal reasoning in <thought> tags like this:\n"
            "<thought>First I will check what capabilities are available...</thought>\n"
            "- The content inside <thought>...</thought> is your internal monologue.\n"
            "- The system will render thought content as a collapsible section.\n"
            "- After the closing </thought> tag, write your concise response to the user.\n"
            "- Keep thoughts brief and focused. Do not narrate obvious actions.\n"
            "- The user will see the thought content only if they choose to expand it.\n",
        )
        ctx.runtime_directives_block = "".join(parts)

        # User Knowledge (profile about the user)
        if user_profile:
            ctx.user_knowledge_block = user_profile.to_prompt_block()

        if self.include_memory and memory_store:
            ctx.memory_block = self._render_memory(
                memory_store, identity.id, query, top_k_memories, session_id
            )

        if self.include_skills:
            if capability_prompts:
                ctx.skills_block = "\n".join(capability_prompts)
            elif skill_registry:
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

        if self.include_synthesis and (user_profile or timeline_registry or memory_store):
            from core.synthesis import build_synthesis
            t = timeline_registry.get(identity.id) if timeline_registry else None
            recent = []
            if memory_store:
                recent = [
                    str(m.content)[:200] for m in
                    memory_store.recent(identity_id=identity.id, n=5)
                ]
            ctx.synthesis_block = build_synthesis(
                user_profile=user_profile,
                timeline=t,
                recent_memories=recent if recent else None,
            )

        # Time-awareness block — identity age, time since first/last interaction
        ctx.time_awareness_block = self._render_time_awareness(
            identity=identity,
            timeline_registry=timeline_registry,
            user_profile=user_profile,
        )

        # Build evidence footer from capability results
        if evidence_results:
            ctx.evidence_footer_block = self._render_evidence_footer(evidence_results)

        # Enforce max_tokens budget — trim largest blocks first when over budget
        if self.max_tokens > 0:
            blocks = [
                ("runtime_directives_block", ctx.runtime_directives_block),
                ("identity_block", ctx.identity_block),
                ("identity_evolution_block", ctx.identity_evolution_block),
                ("user_knowledge_block", ctx.user_knowledge_block),
                ("emotion_block", ctx.emotion_block),
                ("session_mode_block", ctx.session_mode_block),
                ("memory_block", ctx.memory_block),
                ("skills_block", ctx.skills_block),
                ("goals_block", ctx.goals_block),
                ("intentions_block", ctx.intentions_block),
                ("relationships_block", ctx.relationships_block),
                ("motivations_block", ctx.motivations_block),
                ("timeline_block", ctx.timeline_block),
                ("synthesis_block", ctx.synthesis_block),
                ("evidence_footer_block", ctx.evidence_footer_block),
            ]
            for _name, _block in list(ctx.custom_blocks.items()):
                blocks.append((f"custom:{_name}", _block))
            total_chars = sum(len(b) for _, b in blocks)
            budget_chars = self.max_tokens * 4
            if total_chars > budget_chars:
                overage = total_chars - budget_chars
                blocks.sort(key=lambda x: -len(x[1]))
                for name, block in blocks:
                    if overage <= 0:
                        break
                    if not block:
                        continue
                    # Truncate or remove blocks in order of size
                    if isinstance(name, str) and name.startswith("custom:"):
                        continue  # preserve custom blocks
                    b_len = len(block)
                    if b_len <= overage:
                        setattr(ctx, name, "")
                        overage -= b_len
                    else:
                        # Truncate to remaining budget
                        keep = b_len - overage
                        setattr(ctx, name, block[:keep] + "\n[... truncated ...]")
                        overage = 0

        return ctx

    def _render_evidence_footer(self, evidence_results: list[dict]) -> str:
        """Build a user-visible trust footer showing capability provenance."""
        lines = ["---", "### Evidence Sources"]
        for ev in evidence_results[:12]:
            capability = ev.get("capability", "?")
            action = ev.get("action", "?")
            success = ev.get("success", False)
            confidence = ev.get("confidence", 0.0)
            duration = ev.get("duration_ms", 0)
            status_icon = "✓" if success else "✗"
            conf_label = "verified" if confidence >= 0.8 else "sourced" if confidence >= 0.5 else "inferred"
            error_info = f" — {ev.get('error', {}).get('message', '')[:200]}" if not success and ev.get('error') else ""
            lines.append(
                f"  {status_icon} **{capability}.{action}** — {conf_label} ({confidence:.1f}) — {duration:.0f}ms{error_info}"
            )
        lines.append("---")
        return "\n".join(lines)

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
        session_id: Optional[str] = None,
    ) -> str:
        all_frags = store.by_identity(identity_id) if identity_id else store.all()
        if not all_frags:
            return ""

        lines: list[str] = []

        # If no session_id provided, include all memory (legacy backward-compat)
        if not session_id:
            scored = [(f, self._score_memory(f, query)) for f in all_frags]
            scored.sort(key=lambda x: x[1], reverse=True)
            lines.append("## This Conversation")
            for frag, sc in scored[:top_k]:
                lines.append(f"  [{frag.memory_type.value.upper()}] {frag.content}")
            lines.append("")
            return "\n".join(lines)

        # Split into working memory (current session) and past sessions
        current_frags = [f for f in all_frags if f.session_id == session_id]
        past_frags = [f for f in all_frags if f.session_id != session_id]

        # Working memory (current session)
        if current_frags:
            scored = [(f, self._score_memory(f, query)) for f in current_frags]
            scored.sort(key=lambda x: x[1], reverse=True)
            lines.append("## This Conversation")
            for frag, sc in scored[:top_k]:
                lines.append(f"  [{frag.memory_type.value.upper()}] {frag.content}")
            lines.append("")

        # Past conversation memory — only included when query explicitly references past
        if past_frags and query and any(kw in (query or "").lower() for kw in ["before", "previous", "earlier", "last time", "remember", "past", "before this session"]):
            scored = [(f, self._score_memory(f, query)) for f in past_frags]
            scored.sort(key=lambda x: x[1], reverse=True)
            lines.append("## Past Conversations (NOT this session — only reference if asked)")
            for frag, sc in scored[:3]:
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
    # Time Awareness — identity age and interaction history
    # ------------------------------------------------------------------

    def _render_time_awareness(
        self,
        identity: "IdentitySpec",
        timeline_registry: Optional[Any] = None,
        user_profile: Optional[Any] = None,
    ) -> str:
        from datetime import datetime, timezone, timedelta

        def _ensure_aware(dt):
            if dt is None:
                return None
            if isinstance(dt, str):
                dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
            if isinstance(dt, datetime) and dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt

        now = datetime.now(timezone.utc)
        lines = ["## Time Awareness (How Old Am I & Time Passage)"]

        created = _ensure_aware(identity.created_at)
        if isinstance(created, datetime):
            age = now - created
            days = age.days
            hours = age.seconds // 3600
            minutes = (age.seconds % 3600) // 60
            parts = []
            if days > 0:
                parts.append(f"{days} day{'s' if days != 1 else ''}")
            if hours > 0:
                parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
            if minutes > 0:
                parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
            if not parts:
                parts.append("less than a minute")
            lines.append(f"  Identity created: {created.strftime('%Y-%m-%d %H:%M UTC')}")
            lines.append(f"  My age: {', '.join(parts)}")

        # First and last interaction from timeline
        if timeline_registry:
            timeline = timeline_registry.get(identity.id)
            if timeline:
                events = timeline.events()
                if events:
                    first_ts = None
                    last_ts = None
                    for e in events:
                        try:
                            if hasattr(e, 'occurred_at') and e.occurred_at:
                                ts = _ensure_aware(e.occurred_at)
                                if ts is None:
                                    continue
                                if first_ts is None or ts < first_ts:
                                    first_ts = ts
                                if last_ts is None or ts > last_ts:
                                    last_ts = ts
                        except Exception:
                            continue
                    if first_ts and last_ts:
                        known_duration = last_ts - first_ts
                        lines.append(f"  First interaction: {first_ts.strftime('%Y-%m-%d %H:%M UTC')}")
                        lines.append(f"  Most recent interaction: {last_ts.strftime('%Y-%m-%d %H:%M UTC')}")
                        days = known_duration.days
                        hours = known_duration.seconds // 3600
                        parts = []
                        if days > 0:
                            parts.append(f"{days} day{'s' if days != 1 else ''}")
                        if hours > 0:
                            parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
                        if parts:
                            lines.append(f"  Time between first and latest: {', '.join(parts)}")
                        since_last = now - last_ts
                        mins = int(since_last.total_seconds() / 60)
                        if mins < 1:
                            lines.append("  Last interaction: just now")
                        elif mins < 60:
                            lines.append(f"  Last interaction: {mins} minute{'s' if mins != 1 else ''} ago")
                        else:
                            hrs = mins // 60
                            mins_remain = mins % 60
                            lines.append(f"  Last interaction: {hrs}h {mins_remain}m ago")

        # User profile first_seen / last_confirmed
        if user_profile and hasattr(user_profile, '_facts'):
            facts = list(user_profile._facts.values())
            if facts:
                first_seen = None
                last_seen = None
                for f in facts:
                    try:
                        fs = _ensure_aware(getattr(f, 'first_seen', None))
                        lc = _ensure_aware(getattr(f, 'last_confirmed', None))
                        if fs:
                            if first_seen is None or fs < first_seen:
                                first_seen = fs
                        if lc:
                            if last_seen is None or lc > last_seen:
                                last_seen = lc
                    except Exception:
                        continue
                if first_seen:
                    known_since = now - first_seen
                    days = known_since.days
                    lines.append(f"  Known user since: {first_seen.strftime('%Y-%m-%d %H:%M UTC')} ({days} day{'s' if days != 1 else ''})")
                if last_seen:
                    since_last = now - last_seen
                    mins = int(since_last.total_seconds() / 60)
                    if mins < 1:
                        lines.append("  Last user interaction: just now")
                    elif mins < 60:
                        lines.append(f"  Last user interaction: {mins} minute{'s' if mins != 1 else ''} ago")
                    else:
                        hrs = mins // 60
                        lines.append(f"  Last user interaction: {hrs}h {mins % 60}m ago")

        if len(lines) == 1:
            return ""
        lines.append("")
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
