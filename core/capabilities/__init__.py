from __future__ import annotations

from .base import Capability, Skill
from .registry import CapabilityRegistry

# Import built-in capabilities so their @register decorators fire
from . import github  # noqa: F401

__all__ = [
    "Capability",
    "Skill",
    "CapabilityRegistry",
]
