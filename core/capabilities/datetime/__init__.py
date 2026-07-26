from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from core.capabilities.base import Capability, Skill
from core.capabilities.registry import register

_KNOWN_ZONES = {
    "UTC": 0,
    "GMT": 0,
    "EST": -5,
    "CST": -6,
    "MST": -7,
    "PST": -8,
    "CET": 1,
    "EET": 2,
    "IST": 5.5,
    "JST": 9,
    "AEST": 10,
    "NZST": 12,
}


@register
class DateTimeCapability(Capability):
    id = "datetime"
    name = "DateTime"
    version = "1.0.0"
    author = "IdentityOS"
    license = "MIT"
    homepage = "https://github.com/lacebx/IdentityOS"
    description = "Get current time in any timezone, convert between zones, calculate date differences"
    permissions = ["public"]

    def __init__(self, config: Optional[dict] = None) -> None:
        super().__init__(config)

    def install(self, identity_id: str, storage: Any) -> None:
        storage.save(identity_id, "capability.datetime", {"installed_at": None})

    def uninstall(self, identity_id: str, storage: Any) -> None:
        storage.delete(identity_id, "capability.datetime")

    def prompts(self, identity_id: str) -> list[str]:
        return [
            "## Available DateTime Skills",
            "You can get the current time in any timezone, convert between timezones, and calculate date differences.",
        ]

    _SKILLS = [
        Skill(name="datetime.now", description="Get current date and time in a timezone", permission="public"),
        Skill(name="datetime.convert", description="Convert a time between timezones", permission="public"),
        Skill(name="datetime.diff", description="Calculate days between two dates", permission="public"),
        Skill(name="datetime.zones", description="List all supported timezone codes", permission="public"),
    ]

    def skills(self) -> list[Skill]:
        return list(self._SKILLS)

    def call(self, skill_name: str, **params: Any) -> Any:
        dispatch = {
            "datetime.now": self._now,
            "datetime.convert": self._convert,
            "datetime.diff": self._diff,
            "datetime.zones": self._zones,
        }
        handler = dispatch.get(skill_name)
        if handler is None:
            raise ValueError(f"Unknown skill: {skill_name}")
        return handler(**params)

    @staticmethod
    def _utc_offset(tz_name: str) -> float:
        upper = tz_name.upper().strip()
        if upper in _KNOWN_ZONES:
            return _KNOWN_ZONES[upper]
        raise ValueError(f"Unknown timezone: {tz_name}. Supported: {', '.join(_KNOWN_ZONES.keys())}")

    def _now(self, timezone: str = "UTC", **kwargs: Any) -> dict[str, Any]:
        offset = self._utc_offset(timezone)
        tz = timezone(timedelta(hours=offset))
        now = datetime.now(tz)
        return {
            "timezone": timezone.upper(),
            "datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
            "utc_offset_hours": offset,
            "weekday": now.strftime("%A"),
        }

    def _convert(self, dt_str: str = "", from_tz: str = "UTC", to_tz: str = "UTC", **kwargs: Any) -> dict[str, Any]:
        from_offset = self._utc_offset(from_tz)
        to_offset = self._utc_offset(to_tz)
        dt = datetime.fromisoformat(dt_str) if dt_str else datetime.now()
        delta = to_offset - from_offset
        converted = dt + timedelta(hours=delta)
        return {
            "input": {"datetime": dt_str, "timezone": from_tz.upper()},
            "output": {
                "datetime": converted.strftime("%Y-%m-%d %H:%M:%S"),
                "timezone": to_tz.upper(),
            },
            "difference_hours": delta,
        }

    @staticmethod
    def _diff(date1: str = "", date2: str = "", **kwargs: Any) -> dict[str, Any]:
        d1 = datetime.strptime(date1, "%Y-%m-%d") if date1 else datetime.now()
        d2 = datetime.strptime(date2, "%Y-%m-%d") if date2 else datetime.now()
        diff = abs((d2 - d1).days)
        return {
            "date1": d1.strftime("%Y-%m-%d"),
            "date2": d2.strftime("%Y-%m-%d"),
            "days_between": diff,
            "weeks_between": round(diff / 7, 1),
        }

    @staticmethod
    def _zones(**kwargs: Any) -> dict[str, Any]:
        return {"timezones": _KNOWN_ZONES}
