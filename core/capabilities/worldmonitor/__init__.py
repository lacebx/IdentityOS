from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Optional

from core.capabilities.base import Capability, Skill, object_schema
from core.capabilities.registry import register
from core.capabilities.result import CapabilityResult

USER_AGENT = "worldmonitor-identityos/1.0.0 (+https://worldmonitor.app)"

DEFAULT_BASE_URL = "https://api.worldmonitor.app"
DEFAULT_MCP_URL = "https://worldmonitor.app/mcp"

API_KEY_HEADER = "X-WorldMonitor-Key"

MCP_AUTH_ERROR_CODE = -32001

AUTH_HINT = (
    "Hint: this call needs a key - pass api_key= or set WORLDMONITOR_API_KEY "
    "(get one at https://worldmonitor.app/pro)."
)

DEFAULT_TIMEOUT = 30.0


class WorldMonitorError(Exception):
    pass


class APIError(WorldMonitorError):
    def __init__(self, status, body):
        self.status = status
        self.body = body
        hint = " " + AUTH_HINT if status == 401 else ""
        super().__init__("HTTP %d: %s%s" % (status, _truncate(body), hint))


class MCPError(WorldMonitorError):
    def __init__(self, code, message, data=None):
        self.code = code
        self.data = data
        hint = " " + AUTH_HINT if code == MCP_AUTH_ERROR_CODE else ""
        super().__init__("MCP error %d: %s%s" % (code, message, hint))


def _truncate(value, limit=300):
    text = value if isinstance(value, str) else json.dumps(value)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def parse_body(text, content_type=""):
    payload = text
    if "text/event-stream" in (content_type or "") or _looks_like_sse(text):
        data_lines = [
            line[5:].strip()
            for line in text.splitlines()
            if line.startswith("data:")
        ]
        payload = data_lines[-1] if data_lines else ""
    if not payload:
        return text
    try:
        return json.loads(payload)
    except ValueError:
        return text


def _looks_like_sse(text):
    return any(
        line.startswith("event:") or line.startswith("data:")
        for line in text.splitlines()
    )


def _default_transport(request, timeout):
    req = urllib.request.Request(
        request["url"],
        data=request.get("body"),
        headers=request.get("headers") or {},
        method=request.get("method", "GET"),
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            return (
                res.status,
                res.headers.get("content-type", ""),
                res.read().decode("utf-8", "replace"),
            )
    except urllib.error.HTTPError as err:
        return (
            err.code,
            err.headers.get("content-type", "") if err.headers else "",
            err.read().decode("utf-8", "replace"),
        )


@register
class WorldMonitorCapability(Capability):
    id = "worldmonitor"
    name = "World Monitor"
    version = "1.0.0"
    author = "IdentityOS"
    license = "MIT"
    homepage = "https://github.com/lacebx/IdentityOS"
    description = "Real-time global intelligence: world briefs, country risk, markets, conflicts, cyber threats, news, disasters, sanctions, forecasts, maritime activity"
    permissions = ["public"]

    _client: "WorldMonitorClient"

    def __init__(self, config: Optional[dict] = None) -> None:
        super().__init__(config)
        api_key = config.get("api_key") if config else None
        self._client = WorldMonitorClient(api_key=api_key)

    def install(self, identity_id: str, storage: Any) -> None:
        storage.save(identity_id, "capability.worldmonitor", {"installed_at": None, "api_key": self._client.api_key})

    def uninstall(self, identity_id: str, storage: Any) -> None:
        storage.delete(identity_id, "capability.worldmonitor")

    def prompts(self, identity_id: str) -> list[str]:
        return [
            "## World Monitor Skills (MANDATORY — use when asked about global intelligence, geopolitics, markets, conflicts, etc.)",
            "When the user asks about world events, country risk, markets, conflicts, cyber threats, news, disasters, sanctions, forecasts, or maritime activity, you MUST use the skills below.",
            "Do NOT say you cannot access this data. You CAN. Use the skills.",
        ]

    _SKILLS = [
        Skill(name="worldmonitor.world_brief", description="Live global situation brief", permission="public", input_schema=object_schema({}, required=())),
        Skill(name="worldmonitor.country_brief", description="AI strategic brief for a country (ISO 3166-1 alpha-2 code)", permission="public", input_schema=object_schema({"country_code": {"type": "string", "pattern": "^[A-Z]{2}$"}}, required=("country_code",))),
        Skill(name="worldmonitor.country_risk", description="Country risk / resilience scores (ISO 3166-1 alpha-2 code)", permission="public", input_schema=object_schema({"country_code": {"type": "string", "pattern": "^[A-Z]{2}$"}}, required=("country_code",))),
        Skill(name="worldmonitor.market_data", description="Equities, commodities, crypto and FX quotes", permission="public", input_schema=object_schema({"asset_class": {"type": "string", "enum": ["equities", "commodities", "crypto", "fx", "all"]}}, required=())),
        Skill(name="worldmonitor.conflict_events", description="Recent conflict events (country=, min_fatalities=, limit=...)", permission="public", input_schema=object_schema({"country": {"type": "string"}, "min_fatalities": {"type": "integer"}, "limit": {"type": "integer"}}, required=())),
        Skill(name="worldmonitor.cyber_threats", description="Cyber-threat indicators (min_severity=, threat_type=, country=...)", permission="public", input_schema=object_schema({"min_severity": {"type": "string"}, "threat_type": {"type": "string"}, "country": {"type": "string"}}, required=())),
        Skill(name="worldmonitor.news_intelligence", description="Classified news intelligence (topic=, country=, alerts_only=...)", permission="public", input_schema=object_schema({"topic": {"type": "string"}, "country": {"type": "string"}, "alerts_only": {"type": "boolean"}}, required=())),
        Skill(name="worldmonitor.natural_disasters", description="Earthquakes, fires and storms (dataset=, active_only=, min_magnitude=...)", permission="public", input_schema=object_schema({"dataset": {"type": "string"}, "active_only": {"type": "boolean"}, "min_magnitude": {"type": "number"}}, required=())),
        Skill(name="worldmonitor.sanctions_data", description="Sanctions designations (country=, entity_type=, query=...)", permission="public", input_schema=object_schema({"country": {"type": "string"}, "entity_type": {"type": "string"}, "query": {"type": "string"}}, required=())),
        Skill(name="worldmonitor.forecast_predictions", description="Scenario forecasts (domain=, region=...)", permission="public", input_schema=object_schema({"domain": {"type": "string"}, "region": {"type": "string"}}, required=())),
        Skill(name="worldmonitor.maritime_activity", description="Maritime / port activity for a country (ISO 3166-1 alpha-2 code)", permission="public", input_schema=object_schema({"country_code": {"type": "string", "pattern": "^[A-Z]{2}$"}}, required=("country_code",))),
        Skill(name="worldmonitor.list_tools", description="List every available MCP tool (public - no key needed)", permission="public", input_schema=object_schema({}, required=())),
        Skill(name="worldmonitor.list_prompts", description="List MCP prompt templates (public)", permission="public", input_schema=object_schema({}, required=())),
        Skill(name="worldmonitor.list_resources", description="List MCP resources (public)", permission="public", input_schema=object_schema({}, required=())),
        Skill(name="worldmonitor.health", description="API status / health check (requires API key for full, use health_compact for public)", permission="public", input_schema=object_schema({}, required=())),
        Skill(name="worldmonitor.health_compact", description="Public API health check (no key needed)", permission="public", input_schema=object_schema({}, required=())),
        Skill(name="worldmonitor.list_sources", description="List World Monitor data sources (public - no key needed)", permission="public", input_schema=object_schema({"view": {"type": "string", "enum": ["summary", "providers", "outlets"]}}, required=())),
        Skill(name="worldmonitor.call_tool", description="Call any MCP tool directly by name", permission="public", input_schema=object_schema({"tool_name": {"type": "string"}, "arguments": {"type": "object"}}, required=("tool_name",))),
    ]

    def skills(self) -> list[Skill]:
        return list(self._SKILLS)

    def call(self, skill_name: str, **params: Any) -> CapabilityResult:
        import time as _time
        _t0 = _time.monotonic()
        try:
            dispatch = {
                "worldmonitor.world_brief": lambda **p: self._client.world_brief(**p),
                "worldmonitor.country_brief": lambda **p: self._client.country_brief(**p),
                "worldmonitor.country_risk": lambda **p: self._client.country_risk(**p),
                "worldmonitor.market_data": lambda **p: self._client.market_data(**p),
                "worldmonitor.conflict_events": lambda **p: self._client.conflict_events(**p),
                "worldmonitor.cyber_threats": lambda **p: self._client.cyber_threats(**p),
                "worldmonitor.news_intelligence": lambda **p: self._client.news_intelligence(**p),
                "worldmonitor.natural_disasters": lambda **p: self._client.natural_disasters(**p),
                "worldmonitor.sanctions_data": lambda **p: self._client.sanctions_data(**p),
                "worldmonitor.forecast_predictions": lambda **p: self._client.forecast_predictions(**p),
                "worldmonitor.maritime_activity": lambda **p: self._client.maritime_activity(**p),
                "worldmonitor.list_tools": lambda **p: self._client.list_tools(),
                "worldmonitor.list_prompts": lambda **p: self._client.list_prompts(),
                "worldmonitor.list_resources": lambda **p: self._client.list_resources(),
                "worldmonitor.health": lambda **p: self._client.health(),
                "worldmonitor.health_compact": lambda **p: self._client.get("/api/health?compact=1"),
                "worldmonitor.list_sources": lambda view="summary", **p: self._client.call_tool("get_sources", view=view, **p),
                "worldmonitor.call_tool": lambda tool_name=None, arguments=None, **p: self._client.call_tool(name=tool_name, arguments=arguments, **p),
            }
            handler = dispatch.get(skill_name)
            if handler is None:
                return CapabilityResult.fail("worldmonitor", skill_name, "unknown_skill", f"Unknown skill: {skill_name}")
            data = handler(**params)
            return CapabilityResult.from_data("worldmonitor", skill_name, data, source="worldmonitor.app", duration_ms=(_time.monotonic() - _t0) * 1000)
        except Exception as e:
            return CapabilityResult.fail("worldmonitor", skill_name, type(e).__name__, str(e), source="worldmonitor.app", duration_ms=(_time.monotonic() - _t0) * 1000)


class WorldMonitorClient:
    def __init__(
        self,
        api_key=None,
        base_url=None,
        mcp_url=None,
        timeout=DEFAULT_TIMEOUT,
        transport=None,
        env=None,
    ):
        env = os.environ if env is None else env
        self.api_key = api_key or env.get("WORLDMONITOR_API_KEY") or env.get("WM_API_KEY")
        self.base_url = (base_url or env.get("WORLDMONITOR_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.mcp_url = mcp_url or env.get("WORLDMONITOR_MCP_URL") or DEFAULT_MCP_URL
        self.timeout = timeout
        self._transport = transport or _default_transport

    def _headers(self, accept):
        headers = {"user-agent": USER_AGENT, "accept": accept}
        if self.api_key:
            headers[API_KEY_HEADER] = self.api_key
        return headers

    def _rpc(self, method, params=None):
        rpc = {"jsonrpc": "2.0", "id": 1, "method": method}
        if params is not None:
            rpc["params"] = params
        headers = self._headers(accept="application/json, text/event-stream")
        headers["content-type"] = "application/json"
        status, content_type, text = self._transport(
            {
                "url": self.mcp_url,
                "method": "POST",
                "headers": headers,
                "body": json.dumps(rpc).encode("utf-8"),
            },
            self.timeout,
        )
        value = parse_body(text, content_type)
        if isinstance(value, dict) and isinstance(value.get("error"), dict):
            err = value["error"]
            raise MCPError(err.get("code", 0), err.get("message", ""), err.get("data"))
        if status < 200 or status >= 300:
            raise APIError(status, value)
        if isinstance(value, dict) and "result" in value:
            return value["result"]
        return value

    def call_tool(self, name, arguments=None, **kwargs):
        args = dict(arguments or {})
        args.update(kwargs)
        return self._rpc("tools/call", {"name": name, "arguments": args})

    def list_tools(self):
        return self._rpc("tools/list")

    def list_prompts(self):
        return self._rpc("prompts/list")

    def list_resources(self):
        return self._rpc("resources/list")

    def get(self, path, params=None, **kwargs):
        if not path.startswith("/"):
            raise ValueError("get() needs a host-relative API path starting with '/'")
        query = dict(params or {})
        query.update(kwargs)
        url = self.base_url + path
        if query:
            url += "?" + urllib.parse.urlencode({k: _stringify(v) for k, v in query.items()})
        status, content_type, text = self._transport(
            {"url": url, "method": "GET", "headers": self._headers(accept="application/json")},
            self.timeout,
        )
        value = parse_body(text, content_type)
        if status < 200 or status >= 300:
            raise APIError(status, value)
        return value

    def health(self):
        return self.get("/api/health")

    def world_brief(self, **args):
        return self.call_tool("get_world_brief", args)

    def country_brief(self, country_code, **args):
        return self.call_tool("get_country_brief", args, country_code=country_code)

    def country_risk(self, country_code, **args):
        return self.call_tool("get_country_risk", args, country_code=country_code)

    def market_data(self, **args):
        return self.call_tool("get_market_data", args)

    def conflict_events(self, **args):
        return self.call_tool("get_conflict_events", args)

    def cyber_threats(self, **args):
        return self.call_tool("get_cyber_threats", args)

    def news_intelligence(self, **args):
        return self.call_tool("get_news_intelligence", args)

    def natural_disasters(self, **args):
        return self.call_tool("get_natural_disasters", args)

    def sanctions_data(self, **args):
        return self.call_tool("get_sanctions_data", args)

    def forecast_predictions(self, **args):
        return self.call_tool("get_forecast_predictions", args)

    def maritime_activity(self, country_code, **args):
        return self.call_tool("get_maritime_activity", args, country_code=country_code)


def _stringify(value):
    if value is True:
        return "true"
    if value is False:
        return "false"
    return str(value)