from __future__ import annotations

from typing import Any, Optional

import httpx

from core.capabilities.base import Capability, Skill
from core.capabilities.registry import register
from core.capabilities.result import CapabilityResult

WTTR_URL = "https://wttr.in"


@register
class WeatherCapability(Capability):
    id = "weather"
    name = "Weather"
    version = "1.0.0"
    author = "IdentityOS"
    license = "MIT"
    homepage = "https://github.com/lacebx/IdentityOS"
    description = "Get current weather and forecasts for any location"
    permissions = ["public"]

    _client: httpx.Client

    def __init__(self, config: Optional[dict] = None) -> None:
        super().__init__(config)
        self._client = httpx.Client(timeout=10)

    def install(self, identity_id: str, storage: Any) -> None:
        storage.save(identity_id, "capability.weather", {"installed_at": None})

    def uninstall(self, identity_id: str, storage: Any) -> None:
        storage.delete(identity_id, "capability.weather")

    def prompts(self, identity_id: str) -> list[str]:
        return [
            "## Weather Skills (MANDATORY — use when asked about weather)",
            "When the user asks about weather, temperature, or forecast, you MUST use the skills below.",
            "Do NOT say you cannot access weather data. You CAN. Use the skills.",
        ]

    _SKILLS = [
        Skill(name="weather.current", description="Get current weather conditions for a location", permission="public"),
        Skill(name="weather.forecast", description="Get a multi-day weather forecast for a location", permission="public"),
    ]

    def skills(self) -> list[Skill]:
        return list(self._SKILLS)

    def call(self, skill_name: str, **params: Any) -> CapabilityResult:
        import time as _time
        _t0 = _time.monotonic()
        try:
            dispatch = {
                "weather.current": self._current,
                "weather.forecast": self._forecast,
            }
            handler = dispatch.get(skill_name)
            if handler is None:
                return CapabilityResult.fail("weather", skill_name, "unknown_skill", f"Unknown skill: {skill_name}")
            data = handler(**params)
            return CapabilityResult.from_data("weather", skill_name, data, source="wttr.in", duration_ms=(_time.monotonic() - _t0) * 1000)
        except Exception as e:
            return CapabilityResult.fail("weather", skill_name, type(e).__name__, str(e), source="wttr.in", duration_ms=(_time.monotonic() - _t0) * 1000)

    def _current(self, location: str = "London", **kwargs: Any) -> dict[str, Any]:
        resp = self._client.get(f"{WTTR_URL}/{location}", params={"format": "j1"})
        resp.raise_for_status()
        data = resp.json()
        cc = data.get("current_condition", [{}])[0]
        return {
            "location": location,
            "temperature_c": cc.get("temp_C", ""),
            "temperature_f": cc.get("temp_F", ""),
            "humidity": cc.get("humidity", ""),
            "description": cc.get("weatherDesc", [{}])[0].get("value", ""),
            "wind_speed_kmh": cc.get("windspeedKmph", ""),
            "visibility_km": cc.get("visibility", ""),
        }

    def _forecast(self, location: str = "London", days: int = 3, **kwargs: Any) -> list[dict[str, Any]]:
        resp = self._client.get(f"{WTTR_URL}/{location}", params={"format": "j1"})
        resp.raise_for_status()
        data = resp.json()
        forecasts = data.get("weather", [])[:days]
        result = []
        for day in forecasts:
            result.append({
                "date": day.get("date", ""),
                "max_temp_c": day.get("maxtempC", ""),
                "min_temp_c": day.get("mintempC", ""),
                "description": day.get("hourly", [{}])[0].get("weatherDesc", [{}])[0].get("value", ""),
            })
        return result
