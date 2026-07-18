"""
permissions.py - Identity Authorization & Permissions

Permissions define **what an identity is allowed to do**, separate from
behavioral policies. This module implements a flexible RBAC-style system
that can be enforced by compliant runtimes.

Key Concepts:
  - Permissions: scope-based authorization (e.g., "read:records", "write:logs")
  - Roles: named permission bundles (e.g., "officer" = [read:records, write:logs])
  - Allowed vs Denied: explicit allow/deny lists for fine-grained control

Example:
  Officer Maya:
    Allowed:
      - read:records
      - write:logs
      - use:vehicle
    Denied:
      - delete:evidence
      - approve:warrants

Permissions describe **authority**, not behavior.
Policies describe behavior; permissions describe authorization.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class PermissionPolicy:
    """
    Authorization scopes for an identity.

    Attributes:
        allowed  : List of granted permission scopes
        denied   : List of explicitly denied scopes (overrides allowed)
        roles    : Named role assignments
        metadata : Arbitrary policy-specific data
    """
    allowed: list[str] = field(default_factory=list)
    denied: list[str] = field(default_factory=list)
    roles: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "denied": self.denied,
            "roles": self.roles,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PermissionPolicy":
        return cls(
            allowed=data.get("allowed", []),
            denied=data.get("denied", []),
            roles=data.get("roles", []),
            metadata=data.get("metadata", {}),
        )


class PermissionManager:
    """
    Manages permission enforcement and role assignment for an identity.

    Usage:
        pm = PermissionManager()
        pm.grant("read:records")
        pm.deny("delete:evidence")
        pm.assign_role("officer")

        if pm.check("read:records"):
            # allowed
            ...

        if pm.check("delete:evidence"):
            # denied
            raise PermissionError()
    """

    # Role definitions (can be extended or loaded from config)
    ROLE_DEFINITIONS = {
        "admin": ["read:*", "write:*", "delete:*", "approve:*"],
        "officer": ["read:records", "write:logs", "use:vehicle"],
        "analyst": ["read:records", "execute:analysis"],
        "viewer": ["read:*"],
    }

    def __init__(self, policy: Optional[PermissionPolicy] = None) -> None:
        self._policy = policy or PermissionPolicy()

    def grant(self, scope: str) -> None:
        """Grant a permission scope."""
        if scope not in self._policy.allowed:
            self._policy.allowed.append(scope)

    def deny(self, scope: str) -> None:
        """Explicitly deny a permission scope."""
        if scope not in self._policy.denied:
            self._policy.denied.append(scope)

    def revoke(self, scope: str) -> None:
        """Remove a granted permission."""
        if scope in self._policy.allowed:
            self._policy.allowed.remove(scope)

    def assign_role(self, role: str) -> None:
        """Assign a named role."""
        if role not in self._policy.roles:
            self._policy.roles.append(role)

    def unassign_role(self, role: str) -> None:
        """Remove a role assignment."""
        if role in self._policy.roles:
            self._policy.roles.remove(role)

    def check(self, scope: str) -> bool:
        """
        Check if a permission scope is allowed.

        Returns:
            True if allowed, False if denied or not granted.

        Logic:
          1. If explicitly denied -> False
          2. If explicitly allowed -> True
          3. If granted via role -> True
          4. Otherwise -> False (deny by default)
        """
        # Explicit deny takes precedence
        if self._match_any(scope, self._policy.denied):
            return False

        # Explicit allow
        if self._match_any(scope, self._policy.allowed):
            return True

        # Role-based permissions
        for role in self._policy.roles:
            role_perms = self.ROLE_DEFINITIONS.get(role, [])
            if self._match_any(scope, role_perms):
                return True

        # Default: deny
        return False

    def _match_any(self, scope: str, patterns: list[str]) -> bool:
        """
        Check if scope matches any pattern in the list.

        Supports:
          - Exact match: "read:records"
          - Wildcard: "read:*" matches "read:records", "read:logs", etc.
        """
        for pattern in patterns:
            if self._match(scope, pattern):
                return True
        return False

    def _match(self, scope: str, pattern: str) -> bool:
        """Match a single scope against a pattern (supports wildcards)."""
        if pattern == "*" or pattern == scope:
            return True
        if pattern.endswith(":*"):
            prefix = pattern[:-1]  # remove trailing '*'
            return scope.startswith(prefix)
        return False

    def list_permissions(self) -> dict[str, list[str]]:
        """
        Return a summary of all active permissions.

        Returns:
            {
                "allowed": [...],
                "denied": [...],
                "from_roles": [...]
            }
        """
        role_perms = []
        for role in self._policy.roles:
            role_perms.extend(self.ROLE_DEFINITIONS.get(role, []))

        return {
            "allowed": self._policy.allowed,
            "denied": self._policy.denied,
            "from_roles": list(set(role_perms)),
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialize to OIS format."""
        return self._policy.to_dict()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PermissionManager":
        """Deserialize from OIS format."""
        policy = PermissionPolicy.from_dict(data)
        return cls(policy)


def enforce(manager: PermissionManager, scope: str) -> None:
    """
    Enforce a permission check, raising PermissionError if denied.

    Usage:
        enforce(pm, "delete:evidence")
        # raises PermissionError if not allowed
    """
    if not manager.check(scope):
        raise PermissionError(
            f"Permission denied: '{scope}' is not allowed for this identity."
        )
