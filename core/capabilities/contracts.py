"""Runtime validation for capability skill contracts.

The project intentionally supports a small, dependency-free JSON Schema
subset.  Tool definitions and invocation validation therefore share the
same contract instead of letting model calls reach handlers unchecked.
"""

from __future__ import annotations

from copy import deepcopy
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
    "null": (type(None),),
}


def model_tool_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Return a provider-facing copy where optional values accept ``null``.

    Some tool-calling models represent an omitted optional argument as an
    explicit JSON ``null``.  Strict providers validate that generation before
    the runtime can apply a handler default, so optional properties must admit
    null at the provider boundary.  The runtime contract remains unchanged.
    """
    result = deepcopy(schema)
    _make_optional_properties_nullable(result)
    return result


def normalize_parameters(
    schema: dict[str, Any], params: dict[str, Any]
) -> dict[str, Any]:
    """Drop model-emitted nulls for optional arguments before validation.

    A null explicitly allowed by the runtime schema is preserved.  Required
    arguments are also preserved so normal contract validation rejects them.
    """
    if not isinstance(params, dict) or not schema:
        return dict(params)
    return _normalize_object(schema, params)


def _make_optional_properties_nullable(schema: Any) -> None:
    if not isinstance(schema, dict):
        return

    if schema.get("type") == "object" or "properties" in schema:
        required = set(schema.get("required", []))
        for name, prop in schema.get("properties", {}).items():
            if name not in required and isinstance(prop, dict):
                prop_type = prop.get("type")
                if isinstance(prop_type, str) and prop_type != "null":
                    prop["type"] = [prop_type, "null"]
                elif isinstance(prop_type, list) and "null" not in prop_type:
                    prop["type"] = [*prop_type, "null"]
            _make_optional_properties_nullable(prop)

    _make_optional_properties_nullable(schema.get("items"))


def _normalize_object(schema: dict[str, Any], value: dict[str, Any]) -> dict[str, Any]:
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))
    normalized: dict[str, Any] = {}
    for name, item in value.items():
        prop = properties.get(name)
        if (
            item is None
            and name not in required
            and isinstance(prop, dict)
            and not _allows_null(prop)
        ):
            continue
        if isinstance(item, dict) and isinstance(prop, dict):
            normalized[name] = _normalize_object(prop, item)
        else:
            normalized[name] = item
    return normalized


def _allows_null(schema: dict[str, Any]) -> bool:
    expected = schema.get("type")
    return expected == "null" or (
        isinstance(expected, list) and "null" in expected
    )


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
    expected_types = [expected] if isinstance(expected, str) else expected
    if isinstance(expected_types, list) and all(
        item in _PYTHON_TYPES for item in expected_types
    ):
        valid = any(isinstance(value, _PYTHON_TYPES[item]) for item in expected_types)
        if any(item in ("integer", "number") for item in expected_types) and isinstance(value, bool):
            valid = False
        if not valid:
            expected_label = " or ".join(str(item) for item in expected_types)
            raise CapabilityContractError(
                f"parameter '{name}' must be {expected_label}, got {type(value).__name__}"
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
