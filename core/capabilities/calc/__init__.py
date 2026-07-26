from __future__ import annotations

import ast
import math
import operator
from typing import Any, Optional

from core.capabilities.base import Capability, Skill
from core.capabilities.registry import register

_ALLOWED_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

_ALLOWED_NAMES = {
    "pi": math.pi,
    "e": math.e,
    "inf": math.inf,
    "nan": math.nan,
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "sum": sum,
    "int": int,
    "float": float,
    "sqrt": math.sqrt,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "log": math.log,
    "log10": math.log10,
    "floor": math.floor,
    "ceil": math.ceil,
}

_UNIT_CONVERSIONS = {
    "km_to_miles": lambda x: x * 0.621371,
    "miles_to_km": lambda x: x / 0.621371,
    "c_to_f": lambda x: x * 9 / 5 + 32,
    "f_to_c": lambda x: (x - 32) * 5 / 9,
    "kg_to_lbs": lambda x: x * 2.20462,
    "lbs_to_kg": lambda x: x / 2.20462,
    "m_to_ft": lambda x: x * 3.28084,
    "ft_to_m": lambda x: x / 3.28084,
    "l_to_gal": lambda x: x * 0.264172,
    "gal_to_l": lambda x: x / 0.264172,
}


@register
class CalcCapability(Capability):
    id = "calc"
    name = "Calculator"
    version = "1.0.0"
    author = "IdentityOS"
    license = "MIT"
    homepage = "https://github.com/lacebx/IdentityOS"
    description = "Evaluate mathematical expressions and convert between units"
    permissions = ["public"]

    def __init__(self, config: Optional[dict] = None) -> None:
        super().__init__(config)

    def install(self, identity_id: str, storage: Any) -> None:
        storage.save(identity_id, "capability.calc", {"installed_at": None})

    def uninstall(self, identity_id: str, storage: Any) -> None:
        storage.delete(identity_id, "capability.calc")

    def prompts(self, identity_id: str) -> list[str]:
        return [
            "## Available Calculator Skills",
            "You can evaluate math expressions and convert between units (km/miles, C/F, kg/lbs, m/ft, L/gal).",
        ]

    _SKILLS = [
        Skill(name="calc.evaluate", description="Evaluate a mathematical expression safely", permission="public"),
        Skill(name="calc.convert", description="Convert between supported units", permission="public"),
        Skill(name="calc.conversions", description="List all available unit conversions", permission="public"),
    ]

    def skills(self) -> list[Skill]:
        return list(self._SKILLS)

    def call(self, skill_name: str, **params: Any) -> Any:
        dispatch = {
            "calc.evaluate": self._evaluate,
            "calc.convert": self._convert,
            "calc.conversions": self._list_conversions,
        }
        handler = dispatch.get(skill_name)
        if handler is None:
            raise ValueError(f"Unknown skill: {skill_name}")
        return handler(**params)

    @staticmethod
    def _safe_eval(expr: str) -> float:
        tree = ast.parse(expr.strip(), mode="eval")
        if not isinstance(tree, ast.Expression):
            raise ValueError("Not a valid expression")

        def _eval(node: ast.AST) -> float:
            if isinstance(node, ast.Constant):
                if isinstance(node.value, (int, float)):
                    return float(node.value)
                raise ValueError(f"Unsupported constant: {type(node.value)}")
            if isinstance(node, ast.Name):
                if node.id in _ALLOWED_NAMES:
                    return _ALLOWED_NAMES[node.id]
                raise ValueError(f"Unknown name: {node.id}")
            if isinstance(node, ast.UnaryOp):
                op = _ALLOWED_OPERATORS.get(type(node.op))
                if op is None:
                    raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
                return op(_eval(node.operand))
            if isinstance(node, ast.BinOp):
                op = _ALLOWED_OPERATORS.get(type(node.op))
                if op is None:
                    raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
                return op(_eval(node.left), _eval(node.right))
            if isinstance(node, ast.Call):
                func = _ALLOWED_NAMES.get(node.func.id) if isinstance(node.func, ast.Name) else None
                if func is None:
                    raise ValueError(f"Unknown function: {getattr(node.func, 'id', '?')}")
                args = [_eval(a) for a in node.args]
                return func(*args)
            raise ValueError(f"Unsupported syntax: {type(node).__name__}")

        return _eval(tree.body)

    def _evaluate(self, expression: str = "", **kwargs: Any) -> dict[str, Any]:
        return {
            "expression": expression,
            "result": self._safe_eval(expression),
        }

    def _convert(self, value: float = 0, from_unit: str = "", to_unit: str = "", **kwargs: Any) -> dict[str, Any]:
        key = f"{from_unit}_to_{to_unit}"
        if key not in _UNIT_CONVERSIONS:
            return {"error": f"Unknown conversion: {from_unit} -> {to_unit}", "available": list(_UNIT_CONVERSIONS.keys())}
        result = _UNIT_CONVERSIONS[key](value)
        return {
            "value": value,
            "from": from_unit,
            "to": to_unit,
            "result": round(result, 6),
        }

    @staticmethod
    def _list_conversions(**kwargs: Any) -> dict[str, Any]:
        return {"conversions": list(_UNIT_CONVERSIONS.keys())}
