from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class PolicyEffect(Enum):
    ALLOW = "allow"
    DENY = "deny"
    TRANSFORM = "transform"  # Modify the action/output
    ESCALATE = "escalate"    # Require additional review/approval


class PolicyScope(Enum):
    INPUT = "input"       # Applied before processing
    OUTPUT = "output"     # Applied after response generation
    MEMORY = "memory"     # Applied on memory operations
    SKILL = "skill"       # Applied when invoking skills
    RELATIONSHIP = "relationship"  # Applied on relationship formation


@dataclass
class PolicyViolation:
    """Represents a policy violation that was detected."""
    policy_id: str
    policy_name: str
    scope: PolicyScope
    effect: PolicyEffect
    reason: str
    input_data: Any = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class PolicyResult:
    """Result of evaluating a set of policies against input."""
    allowed: bool
    transformed_data: Any = None
    violations: List[PolicyViolation] = field(default_factory=list)
    applied_policies: List[str] = field(default_factory=list)


@dataclass
class Policy:
    """
    A behavioral rule that governs identity actions.
    Policies are the ethical/safety/operational boundaries.
    They can allow, deny, transform, or escalate any operation.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    scope: PolicyScope = PolicyScope.OUTPUT
    effect: PolicyEffect = PolicyEffect.DENY
    priority: int = 0          # Higher = evaluated first
    enabled: bool = True
    condition: Optional[Callable[[Any], bool]] = field(default=None, repr=False)
    transformer: Optional[Callable[[Any], Any]] = field(default=None, repr=False)
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def evaluate(self, data: Any) -> Optional[PolicyViolation]:
        """
        Evaluate this policy against the given data.
        Returns a PolicyViolation if the policy is triggered, else None.
        """
        if not self.enabled:
            return None
        if self.condition and not self.condition(data):
            return None
        return PolicyViolation(
            policy_id=self.id,
            policy_name=self.name,
            scope=self.scope,
            effect=self.effect,
            reason=self.description,
            input_data=data
        )


class PolicyEngine:
    """
    Evaluates a stack of policies against data at runtime.
    Policies are sorted by priority and evaluated in order.
    A single DENY terminates the chain (fail-fast).
    """

    def __init__(self):
        self._policies: Dict[str, Policy] = {}

    def add(self, policy: Policy) -> None:
        self._policies[policy.id] = policy

    def remove(self, policy_id: str) -> bool:
        return bool(self._policies.pop(policy_id, None))

    def get(self, policy_id: str) -> Optional[Policy]:
        return self._policies.get(policy_id)

    def evaluate(
        self, data: Any, scope: Optional[PolicyScope] = None
    ) -> PolicyResult:
        """
        Run all matching policies against data.
        Returns a PolicyResult indicating final allow/deny and transformations.
        """
        applicable = [
            p for p in self._policies.values()
            if p.enabled and (scope is None or p.scope == scope)
        ]
        applicable.sort(key=lambda p: -p.priority)

        violations: List[PolicyViolation] = []
        applied: List[str] = []
        current_data = data

        for policy in applicable:
            violation = policy.evaluate(current_data)
            if violation:
                violations.append(violation)
                applied.append(policy.name)
                if violation.effect == PolicyEffect.DENY:
                    return PolicyResult(
                        allowed=False,
                        transformed_data=None,
                        violations=violations,
                        applied_policies=applied
                    )
                elif violation.effect == PolicyEffect.TRANSFORM and policy.transformer:
                    current_data = policy.transformer(current_data)

        return PolicyResult(
            allowed=True,
            transformed_data=current_data,
            violations=violations,
            applied_policies=applied
        )

    def list_by_scope(self, scope: PolicyScope) -> List[Policy]:
        return [p for p in self._policies.values() if p.scope == scope]

    def __len__(self) -> int:
        return len(self._policies)
