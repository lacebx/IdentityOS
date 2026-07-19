"""
core/identity.py

The Identity module — the foundational bounded context of IdentityOS.

An Identity is WHO an entity is. It does NOT contain memories, knowledge,
or skills directly. It holds the immutable core (name, id, version, values)
and references to the modules that attach to it.

Design principle: Identity is the kernel. Everything else is a loadable module.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

# ─── Enums ────────────────────────────────────────────────────────────────────

class IdentityStatus(str, Enum):
    ACTIVE = "active"
    DORMANT = "dormant"
    ARCHIVED = "archived"
    BRANCHED = "branched"


class IdentityClass(str, Enum):
    """
    Broad classification of what kind of entity this identity represents.
    IdentityOS is class-agnostic — a robot, a person, a company, or a concept
    can all be represented as identities.
    """
    PERSON = "person"
    ROBOT = "robot"
    AGENT = "agent"
    ORGANIZATION = "organization"
    CONCEPT = "concept"
    CUSTOM = "custom"


# ─── CoreValue ────────────────────────────────────────────────────────────────

@dataclass
class CoreValue:
    """
    An immutable value that defines this identity's ethical/behavioral bedrock.
    Core values are NOT traits (which can fluctuate). They are stable axioms.

    Example: CoreValue(name="non-maleficence", strength=1.0)
    """
    name: str
    description: str = ""
    strength: float = 1.0  # 0.0 – 1.0; 1.0 = inviolable


# ─── Trait ────────────────────────────────────────────────────────────────────

@dataclass
class Trait:
    """
    A personality or behavioral trait that can evolve over time.
    Unlike CoreValues, traits can be measured and updated by the Evaluation module.

    Example: Trait(name="curiosity", score=0.85, last_updated=...)
    """
    name: str
    score: float = 0.5           # 0.0 – 1.0
    description: str = ""
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    history: List[Dict[str, Any]] = field(default_factory=list)

    def update(self, delta: float, reason: str = "") -> None:
        """Apply a trait score delta and record it in history."""
        old_score = self.score
        self.score = max(0.0, min(1.0, self.score + delta))
        self.last_updated = datetime.now(timezone.utc)
        self.history.append({
            "timestamp": self.last_updated.isoformat(),
            "old_score": old_score,
            "new_score": self.score,
            "delta": delta,
            "reason": reason,
        })


# ─── IdentityVersion ──────────────────────────────────────────────────────────

@dataclass
class IdentityVersion:
    """
    Immutable snapshot of an identity at a point in time.
    Think: git commit for an identity.

    When an identity evolves significantly, a new version is created.
    Old versions are never deleted — they are the identity's history.
    """
    version: str                    # semver e.g. "1.2.0"
    created_at: datetime
    fingerprint: str                # SHA-256 of identity state at this version
    changelog: str = ""             # What changed from previous version
    branch: Optional[str] = None    # e.g. "hospital-edition", None = main trunk


# ─── IdentitySpec ─────────────────────────────────────────────────────────────

@dataclass
class IdentitySpec:
    """
    The canonical, serializable representation of a single Identity.

    This is the "source of truth" stored on disk/DB and passed between services.
    All other modules (Memory, Knowledge, etc.) reference this by identity_id.

    IMPORTANT: This class intentionally does NOT embed memory, knowledge, or
    relationships. Those are separate modules loaded on demand by the Runtime.
    """

    # ── Core identity fields ─────────────────────────────────────────────────
    id: str
    name: str
    identity_class: IdentityClass = IdentityClass.AGENT

    # ── Versioning ───────────────────────────────────────────────────────────
    version: str = "1.0.0"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    status: IdentityStatus = IdentityStatus.ACTIVE

    # ── Appearance & persona ─────────────────────────────────────────────────
    avatar: str = "⬡"
    tagline: str = ""               # One-line description
    origin_story: str = ""          # Backstory / formation context

    # ── Persona & communication ─────────────────────────────────────────────
    role: str = ""
    persona: str = ""
    communication_style: str = ""
    system_prompt: str = ""

    # ── Behavioral bedrock ───────────────────────────────────────────────────
    core_values: List[CoreValue] = field(default_factory=list)
    traits: List[Trait] = field(default_factory=list)

    # ── Module references (loaded separately by Runtime) ─────────────────────
    # These are IDs/handles pointing to external stores, NOT embedded data.
    memory_store_id: Optional[str] = None
    knowledge_pack_ids: List[str] = field(default_factory=list)
    skill_pack_ids: List[str] = field(default_factory=list)
    policy_set_id: Optional[str] = None
    relationship_graph_id: Optional[str] = None
    goal_set_id: Optional[str] = None

    # ── Adapter preferences ──────────────────────────────────────────────────
    preferred_adapter: str = "openai"
    preferred_model: str = "gpt-4o"
    adapter_overrides: Dict[str, Any] = field(default_factory=dict)

    # ── Version history ──────────────────────────────────────────────────────
    version_history: List[IdentityVersion] = field(default_factory=list)

    # ── Evaluation baseline ──────────────────────────────────────────────────
    # Set by the Evaluation module after first comprehensive eval
    fidelity_baseline: Optional[float] = None

    # ── Metadata ─────────────────────────────────────────────────────────────
    tags: List[str] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)

    # ─────────────────────────────────────────────────────────────────────────

    def fingerprint(self) -> str:
        """
        Generate a deterministic SHA-256 fingerprint of the identity's
        current state. Used for versioning and integrity checks.
        """
        state = (
            f"{self.id}:{self.name}:{self.version}:"
            f"{[v.name for v in self.core_values]}:"
            f"{[(t.name, round(t.score, 4)) for t in self.traits]}"
        )
        return hashlib.sha256(state.encode()).hexdigest()[:16]

    def snapshot(self, changelog: str = "", branch: Optional[str] = None) -> IdentityVersion:
        """
        Create an immutable version snapshot of this identity's current state.
        Should be called by the Runtime whenever the identity evolves meaningfully.
        """
        v = IdentityVersion(
            version=self.version,
            created_at=datetime.now(timezone.utc),
            fingerprint=self.fingerprint(),
            changelog=changelog,
            branch=branch,
        )
        self.version_history.append(v)
        return v

    def bump_version(self, level: str = "patch", changelog: str = "") -> str:
        """
        Bump semver version and create a snapshot.
        level: 'major' | 'minor' | 'patch'
        """
        major, minor, patch = map(int, self.version.split("."))
        if level == "major":
            major += 1
            minor = 0
            patch = 0
        elif level == "minor":
            minor += 1
            patch = 0
        else:
            patch += 1
        self.version = f"{major}.{minor}.{patch}"
        self.updated_at = datetime.now(timezone.utc)
        self.snapshot(changelog=changelog)
        return self.version

    def branch_to(self, branch_name: str, changelog: str = "") -> "IdentitySpec":
        """
        Fork this identity into a new branch (e.g. 'hospital-edition').
        Returns a new IdentitySpec with a new ID derived from the branch.
        """
        import copy
        fork = copy.deepcopy(self)
        fork.id = f"{self.id}-{branch_name}"
        fork.name = f"{self.name} ({branch_name})"
        fork.version = "1.0.0"
        fork.created_at = datetime.now(timezone.utc)
        fork.updated_at = fork.created_at
        fork.version_history = []
        fork.status = IdentityStatus.ACTIVE
        # Record the branch origin in the fork's first snapshot
        fork.snapshot(
            changelog=f"Branched from {self.id}@{self.version}. {changelog}",
            branch=branch_name,
        )
        return fork

    def get_trait(self, name: str) -> Optional[Trait]:
        for t in self.traits:
            if t.name == name:
                return t
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a plain dict for storage/transport."""
        return {
            "id": self.id,
            "name": self.name,
            "identity_class": self.identity_class.value,
            "version": self.version,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "status": self.status.value,
            "avatar": self.avatar,
            "tagline": self.tagline,
            "origin_story": self.origin_story,
            "role": self.role,
            "persona": self.persona,
            "communication_style": self.communication_style,
            "system_prompt": self.system_prompt,
            "core_values": [
                {"name": cv.name, "description": cv.description, "strength": cv.strength}
                for cv in self.core_values
            ],
            "traits": [
                {"name": t.name, "score": t.score, "description": t.description}
                for t in self.traits
            ],
            "memory_store_id": self.memory_store_id,
            "knowledge_pack_ids": self.knowledge_pack_ids,
            "skill_pack_ids": self.skill_pack_ids,
            "policy_set_id": self.policy_set_id,
            "relationship_graph_id": self.relationship_graph_id,
            "goal_set_id": self.goal_set_id,
            "preferred_adapter": self.preferred_adapter,
            "preferred_model": self.preferred_model,
            "adapter_overrides": self.adapter_overrides,
            "fidelity_baseline": self.fidelity_baseline,
            "tags": self.tags,
            "extra": self.extra,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IdentitySpec":
        """Deserialize from a plain dict."""
        core_values = [
            CoreValue(
                name=cv["name"],
                description=cv.get("description", ""),
                strength=cv.get("strength", 1.0),
            )
            for cv in data.get("core_values", [])
        ]
        traits = [
            Trait(
                name=t["name"],
                score=t.get("score", 0.5),
                description=t.get("description", ""),
            )
            for t in data.get("traits", [])
        ]
        return cls(
            id=data["id"],
            name=data["name"],
            identity_class=IdentityClass(data.get("identity_class", "agent")),
            version=data.get("version", "1.0.0"),
            created_at=(
                datetime.fromisoformat(data["created_at"])
                if "created_at" in data
                else datetime.now(timezone.utc)
            ),
            updated_at=(
                datetime.fromisoformat(data["updated_at"])
                if "updated_at" in data
                else datetime.now(timezone.utc)
            ),
            status=IdentityStatus(data.get("status", "active")),
            role=data.get("role", ""),
            persona=data.get("persona", ""),
            communication_style=data.get("communication_style", ""),
            system_prompt=data.get("system_prompt", ""),
            avatar=data.get("avatar", "⬡"),
            tagline=data.get("tagline", ""),
            origin_story=data.get("origin_story", ""),
            core_values=core_values,
            traits=traits,
            memory_store_id=data.get("memory_store_id"),
            knowledge_pack_ids=data.get("knowledge_pack_ids", []),
            skill_pack_ids=data.get("skill_pack_ids", []),
            policy_set_id=data.get("policy_set_id"),
            relationship_graph_id=data.get("relationship_graph_id"),
            goal_set_id=data.get("goal_set_id"),
            preferred_adapter=data.get("preferred_adapter", "openai"),
            preferred_model=data.get("preferred_model", "gpt-4o"),
            adapter_overrides=data.get("adapter_overrides", {}),
            fidelity_baseline=data.get("fidelity_baseline"),
            tags=data.get("tags", []),
            extra=data.get("extra", {}),
        )


# ─── Factory ──────────────────────────────────────────────────────────────────

def create_identity(
    name: str,
    identity_id: Optional[str] = None,
    identity_class: IdentityClass = IdentityClass.AGENT,
    core_values: Optional[List[Dict]] = None,
    traits: Optional[List[Dict]] = None,
    **kwargs: Any,
) -> IdentitySpec:
    """
    Convenience factory for creating a new IdentitySpec with sane defaults.
    Also generates default module store IDs so the Runtime can initialize them.
    """
    id_ = identity_id or name.lower().replace(" ", "-")
    spec = IdentitySpec(
        id=id_,
        name=name,
        identity_class=identity_class,
        memory_store_id=f"mem:{id_}",
        relationship_graph_id=f"graph:{id_}",
        goal_set_id=f"goals:{id_}",
        policy_set_id=f"policy:{id_}",
        **kwargs,
    )
    if core_values:
        spec.core_values = [CoreValue(**cv) for cv in core_values]
    if traits:
        spec.traits = [Trait(**t) for t in traits]
    spec.snapshot(changelog="Initial creation")
    return spec


# ─── Backward-compatible alias ──────────────────────────────────────────────

Identity = IdentitySpec


# ─── IdentityStore ────────────────────────────────────────────────────────────

class IdentityStore:
    """Simple in-memory store for Identity objects."""

    def __init__(self) -> None:
        self._identities: Dict[str, IdentitySpec] = {}

    def save(self, identity: IdentitySpec) -> None:
        self._identities[identity.id] = identity

    def get(self, identity_id: str) -> Optional[IdentitySpec]:
        return self._identities.get(identity_id)

    def delete(self, identity_id: str) -> bool:
        return bool(self._identities.pop(identity_id, None))

    def list_all(self) -> List[IdentitySpec]:
        return list(self._identities.values())

    def __len__(self) -> int:
        return len(self._identities)
