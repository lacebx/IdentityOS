"""
capabilities.py - Identity Capabilities Registry

Capabilities are physical or environmental affordances that an identity
can access at runtime. Unlike Skills (which are declared), Capabilities
are **discovered**.

Examples:
  A robot identity discovers:
    - vision (if cameras are connected)
    - walking (if deployed on a mobile chassis)
    - manipulation (if equipped with arms/hands)

  A cloud identity discovers:
    - internet (always available)
    - file_system (if sandbox permits)
    - voice (if TTS service configured)

  A distributed identity discovers capabilities across nodes:
    - device:robot-01 -> walking, vision
    - device:server-02 -> internet, compute

Capabilities decouple identity from physical embodiment.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Capability:
    """
    A single capability available to the identity.

    Attributes:
        name     : Capability type (e.g., "vision", "walking", "internet")
        enabled  : Whether the capability is currently active
        provider : Source of the capability (e.g., "device:camera-01")
        metadata : Arbitrary capability-specific data
    """
    name: str
    enabled: bool = True
    provider: str = "unknown"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "enabled": self.enabled,
            "provider": self.provider,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Capability":
        return cls(
            name=data["name"],
            enabled=data.get("enabled", True),
            provider=data.get("provider", "unknown"),
            metadata=data.get("metadata", {}),
        )


class CapabilityRegistry:
    """
    Manages capability discovery and registration for an identity.

    Usage:
        registry = CapabilityRegistry()
        registry.discover()  # auto-detect available capabilities
        registry.register("internet", enabled=True, provider="cloud")
        if registry.has("vision"):
            frame = registry.use("vision", action="capture")
    """

    def __init__(self) -> None:
        self._capabilities: dict[str, Capability] = {}

    def register(
        self,
        name: str,
        enabled: bool = True,
        provider: str = "unknown",
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        Manually register a capability.
        """
        self._capabilities[name] = Capability(
            name=name,
            enabled=enabled,
            provider=provider,
            metadata=metadata or {},
        )

    def discover(self) -> list[Capability]:
        """
        Auto-discover capabilities from the runtime environment.

        This is a placeholder. Real implementations would:
          - Check connected devices (cameras, sensors)
          - Query API availability (TTS, vision services)
          - Inspect system permissions
          - Poll network/hardware state
        """
        # Default: assume cloud/internet environment
        if "internet" not in self._capabilities:
            self.register("internet", enabled=True, provider="cloud")

        # Future: hardware detection, API probing, etc.
        return list(self._capabilities.values())

    def has(self, name: str) -> bool:
        """Return True if the capability exists and is enabled."""
        cap = self._capabilities.get(name)
        return cap is not None and cap.enabled

    def get(self, name: str) -> Optional[Capability]:
        """Return the Capability object, or None if not found."""
        return self._capabilities.get(name)

    def enable(self, name: str) -> None:
        """Enable a registered capability."""
        if name in self._capabilities:
            self._capabilities[name].enabled = True

    def disable(self, name: str) -> None:
        """Disable a registered capability."""
        if name in self._capabilities:
            self._capabilities[name].enabled = False

    def list_available(self) -> list[str]:
        """Return a list of all enabled capability names."""
        return [
            name
            for name, cap in self._capabilities.items()
            if cap.enabled
        ]

    def use(self, name: str, action: str = "invoke", **kwargs: Any) -> Any:
        """
        Invoke a capability.

        This is a stub. Real runtimes would route `action` to the
        appropriate provider (e.g., send camera capture command).

        Raises:
            RuntimeError if the capability is not available.
        """
        if not self.has(name):
            raise RuntimeError(
                f"Capability '{name}' not available or disabled."
            )
        cap = self._capabilities[name]
        # Stub: return metadata for now
        return {
            "capability": name,
            "action": action,
            "provider": cap.provider,
            "result": "simulated",  # would be real execution
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialize the registry to OIS format."""
        return {
            "available": [cap.to_dict() for cap in self._capabilities.values()]
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CapabilityRegistry":
        """Deserialize from OIS format."""
        registry = cls()
        for cap_data in data.get("available", []):
            cap = Capability.from_dict(cap_data)
            registry._capabilities[cap.name] = cap
        return registry
