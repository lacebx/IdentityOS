"""Runtime validation for capability skill contracts.

The project intentionally supports a small, dependency-free JSON Schema
subset.  Tool definitions and invocation validation therefore share the
same contract instead of letting model calls reach handlers unchecked.
"""

from __future__ import annotations

from typing import Any


class CapabilityContractError(ValueError):
    """Raised when capability parameters violate a skill contract."""


_PYTHON_TYPES: dict[str, tuple[type, ...]] = {
    "string": (str,),
    "integer": (int,),
    "number": (int, float),
    "boolean": (bool,),
    "object": (dict,),
    "array": (list,),
}


def validate_parameters(schema: dict[str, Any], params: dict[str, Any]) -> None:
    """Validate *params* against the supported object-schema subset."""
    if not isinstance(params, dict):
        raise CapabilityContractError("parameters must be an object")
    if not schema:
        return
    if schema.get("type", "object") != "object":
        raise CapabilityContractError("top-level skill schema must be an object")

    properties = schema.get("properties", {})
    required = schema.get("required", [])
    missing = [name for name in required if name not in params]
    if missing:
        raise CapabilityContractError(
            "missing required parameter(s): " + ", ".join(sorted(missing))
        )

    if schema.get("additionalProperties", True) is False:
        extras = sorted(set(params) - set(properties))
        if extras:
            raise CapabilityContractError(
                "unexpected parameter(s): " + ", ".join(extras)
            )

    for name, value in params.items():
        prop = properties.get(name)
        if prop is None:
            continue
        _validate_value(name, value, prop)


def _validate_value(name: str, value: Any, schema: dict[str, Any]) -> None:
    expected = schema.get("type")
    if expected in _PYTHON_TYPES:
        valid_types = _PYTHON_TYPES[expected]
        valid = isinstance(value, valid_types)
        if expected in ("integer", "number") and isinstance(value, bool):
            valid = False
        if not valid:
            raise CapabilityContractError(
                f"parameter '{name}' must be {expected}, got {type(value).__name__}"
            )

    if "enum" in schema and value not in schema["enum"]:
        allowed = ", ".join(repr(item) for item in schema["enum"])
        raise CapabilityContractError(f"parameter '{name}' must be one of: {allowed}")

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            raise CapabilityContractError(
                f"parameter '{name}' must be >= {schema['minimum']}"
            )
        if "maximum" in schema and value > schema["maximum"]:
            raise CapabilityContractError(
                f"parameter '{name}' must be <= {schema['maximum']}"
            )

    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            raise CapabilityContractError(
                f"parameter '{name}' must contain at least {schema['minLength']} character(s)"
            )
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            raise CapabilityContractError(
                f"parameter '{name}' must contain at most {schema['maxLength']} character(s)"
            )
