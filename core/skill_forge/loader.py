"""Load a verified forged capability without relying on process-global state."""

from __future__ import annotations

import hashlib
import sys
import types
from typing import Any, Optional

from core.capabilities.base import Capability

from .artifacts import verify_package_record


PACKAGE_NAMESPACE = "skill_forge.packages"


def capability_class_from_source(source: str, capability_id: str, digest: str) -> type[Capability]:
    module_name = f"identityos_forged_{capability_id}_{digest[:12]}"
    module = types.ModuleType(module_name)
    module.__file__ = f"<{module_name}>"
    sys.modules[module_name] = module
    try:
        exec(compile(source, module.__file__, "exec"), module.__dict__)
    finally:
        sys.modules.pop(module_name, None)
    matches = [
        value
        for value in module.__dict__.values()
        if isinstance(value, type)
        and issubclass(value, Capability)
        and value is not Capability
        and getattr(value, "id", None) == capability_id
    ]
    if len(matches) != 1:
        raise ValueError(
            f"forged source must define exactly one Capability class with id '{capability_id}'"
        )
    return matches[0]


def persisted_capability_class(storage: Any, identity_id: str, capability_id: str) -> Optional[type[Capability]]:
    raw = storage.load(identity_id, PACKAGE_NAMESPACE) or {}
    record = (raw.get("packages") or {}).get(capability_id)
    if not isinstance(record, dict):
        return None
    digest = verify_package_record(record)
    manifest = record.get("manifest", {})
    if manifest.get("id") != capability_id:
        raise ValueError("persisted forged package manifest id mismatch")
    return capability_class_from_source(str(record["source"]), capability_id, digest)
