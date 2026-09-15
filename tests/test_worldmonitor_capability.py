"""
test_worldmonitor_capability.py — World Monitor Global Intelligence Capability

Tests for the worldmonitor capability covering:
1. Capability registration and installation
2. Free-tier skills (no API key required)
3. Authenticated skills structure (require API key)
4. Skill input validation
5. Error handling
"""

import pytest
from core.capabilities import CapabilityResult
from core.capabilities.registry import CapabilityRegistry, lookup
from core.capabilities.worldmonitor import WorldMonitorClient


class SimpleStorage:
    def __init__(self):
        self.data = {}
    def load(self, identity_id, namespace):
        return self.data.get(f'{identity_id}:{namespace}')
    def save(self, identity_id, namespace, data):
        self.data[f'{identity_id}:{namespace}'] = data
    def delete(self, identity_id, namespace):
        self.data.pop(f'{identity_id}:{namespace}', None)


class TestWorldMonitorCapability:
    """Test WorldMonitor capability registration and skills."""

    @pytest.fixture
    def storage(self):
        return SimpleStorage()

    @pytest.fixture
    def registry(self, storage):
        return CapabilityRegistry(storage)

    @pytest.fixture
    def cap(self, registry):
        """Install and return the worldmonitor capability."""
        return registry.install('test_id', 'worldmonitor', {})

    def test_capability_registered(self):
        """WorldMonitor capability should be registered in the global registry."""
        cap_cls = lookup('worldmonitor')
        assert cap_cls.id == 'worldmonitor'
        assert cap_cls.name == 'World Monitor'
        assert cap_cls.version == '1.0.0'

    def test_capability_installs(self, cap):
        """Capability should install successfully."""
        assert cap.id == 'worldmonitor'

    def test_skills_count(self, cap):
        """Should have 18 skills total (17 original + health_compact)."""
        skills = cap.skills()
        assert len(skills) == 18

    def test_free_tier_skills_present(self, cap):
        """All free-tier skills should be available."""
        skill_names = {s.name for s in cap.skills()}
        free_skills = {
            'worldmonitor.list_sources',
            'worldmonitor.list_tools',
            'worldmonitor.list_prompts',
            'worldmonitor.list_resources',
            'worldmonitor.health_compact',
            'worldmonitor.call_tool',
        }
        assert free_skills.issubset(skill_names)

    def test_authenticated_skills_present(self, cap):
        """All authenticated skills should be defined."""
        skill_names = {s.name for s in cap.skills()}
        auth_skills = {
            'worldmonitor.world_brief',
            'worldmonitor.country_brief',
            'worldmonitor.country_risk',
            'worldmonitor.market_data',
            'worldmonitor.conflict_events',
            'worldmonitor.cyber_threats',
            'worldmonitor.news_intelligence',
            'worldmonitor.natural_disasters',
            'worldmonitor.sanctions_data',
            'worldmonitor.forecast_predictions',
            'worldmonitor.maritime_activity',
        }
        assert auth_skills.issubset(skill_names)

    def test_skill_permissions(self, cap):
        """All skills should have 'public' permission (auth handled at API level)."""
        for skill in cap.skills():
            assert skill.permission == 'public'

    def test_skill_input_schemas(self, cap):
        """Skills should have proper input schemas."""
        skills_by_name = {s.name: s for s in cap.skills()}

        # list_sources should have view parameter
        list_sources = skills_by_name['worldmonitor.list_sources']
        assert 'view' in list_sources.input_schema['properties']
        assert list_sources.input_schema['properties']['view']['enum'] == ['summary', 'providers', 'outlets']

        # country_risk should require country_code
        country_risk = skills_by_name['worldmonitor.country_risk']
        assert 'country_code' in country_risk.input_schema['required']
        assert country_risk.input_schema['properties']['country_code']['pattern'] == '^[A-Z]{2}$'

        # call_tool should require tool_name
        call_tool = skills_by_name['worldmonitor.call_tool']
        assert 'tool_name' in call_tool.input_schema['required']

    def test_prompts_generated(self, cap):
        """Capability should generate prompts for the identity."""
        prompts = cap.prompts('test_id')
        assert len(prompts) > 0
        assert 'World Monitor Skills' in prompts[0]
        assert 'MANDATORY' in prompts[0]


class TestWorldMonitorFreeTierSkills:
    """Test free-tier skills that work without API key."""

    @pytest.fixture
    def cap(self):
        storage = SimpleStorage()
        registry = CapabilityRegistry(storage)
        return registry.install('test_id', 'worldmonitor', {})

    @pytest.mark.network
    def test_list_sources_summary(self, cap):
        """list_sources with summary view should work."""
        result = cap.call('worldmonitor.list_sources', view='summary')
        assert isinstance(result, CapabilityResult)
        assert result.success
        assert result.data is not None
        assert 'content' in result.data
        import json
        data = json.loads(result.data['content'][0]['text'])
        assert data['view'] == 'summary'
        assert 'summary' in data
        assert 'providerCount' in data['summary']
        assert 'outletCount' in data['summary']

    @pytest.mark.network
    def test_list_sources_providers(self, cap):
        """list_sources with providers view should work."""
        result = cap.call('worldmonitor.list_sources', view='providers', limit=5)
        assert isinstance(result, CapabilityResult)
        assert result.success
        import json
        data = json.loads(result.data['content'][0]['text'])
        assert data['view'] == 'providers'
        assert 'providers' in data
        assert isinstance(data['providers'], list)

    @pytest.mark.network
    def test_list_sources_outlets(self, cap):
        """list_sources with outlets view should work."""
        result = cap.call('worldmonitor.list_sources', view='outlets', limit=5)
        assert isinstance(result, CapabilityResult)
        assert result.success
        import json
        data = json.loads(result.data['content'][0]['text'])
        assert data['view'] == 'outlets'
        assert 'outlets' in data
        assert isinstance(data['outlets'], list)

    @pytest.mark.network
    def test_list_tools(self, cap):
        """list_tools should return all MCP tools."""
        result = cap.call('worldmonitor.list_tools')
        assert isinstance(result, CapabilityResult)
        assert result.success
        assert 'tools' in result.data
        tools = result.data['tools']
        assert isinstance(tools, list)
        assert len(tools) > 50  # Should have many tools
        # Check tool structure
        for tool in tools[:3]:
            assert 'name' in tool
            assert 'description' in tool
            assert 'inputSchema' in tool

    @pytest.mark.network
    def test_list_prompts(self, cap):
        """list_prompts should return MCP prompt templates."""
        result = cap.call('worldmonitor.list_prompts')
        assert isinstance(result, CapabilityResult)
        assert result.success
        assert 'prompts' in result.data
        prompts = result.data['prompts']
        assert isinstance(prompts, list)
        assert len(prompts) >= 6
        for prompt in prompts:
            assert 'name' in prompt
            assert 'description' in prompt

    @pytest.mark.network
    def test_list_resources(self, cap):
        """list_resources should return MCP resources."""
        result = cap.call('worldmonitor.list_resources')
        assert isinstance(result, CapabilityResult)
        assert result.success
        assert 'resources' in result.data
        resources = result.data['resources']
        assert isinstance(resources, list)
        assert len(resources) >= 10
        for resource in resources:
            assert 'uri' in resource
            assert 'name' in resource

    @pytest.mark.network
    def test_health_compact(self, cap):
        """health_compact should return public health status."""
        result = cap.call('worldmonitor.health_compact')
        assert isinstance(result, CapabilityResult)
        assert result.success
        assert 'status' in result.data
        assert result.data['status'] == 'HEALTHY'
        assert 'summary' in result.data

    @pytest.mark.network
    def test_call_tool_get_sources(self, cap):
        """call_tool with get_sources should work."""
        result = cap.call('worldmonitor.call_tool', tool_name='get_sources', arguments={'view': 'summary'})
        assert isinstance(result, CapabilityResult)
        assert result.success
        import json
        data = json.loads(result.data['content'][0]['text'])
        assert data['view'] == 'summary'


class TestWorldMonitorClient:
    """Test the WorldMonitorClient directly."""

    def test_client_initialization(self):
        """Client should initialize with default URLs."""
        client = WorldMonitorClient()
        assert client.base_url == 'https://api.worldmonitor.app'
        assert client.mcp_url == 'https://worldmonitor.app/mcp'
        assert client.api_key is None

    def test_client_with_api_key(self):
        """Client should accept API key."""
        client = WorldMonitorClient(api_key='wm_test_key')
        assert client.api_key == 'wm_test_key'

    def test_client_with_env_api_key(self, monkeypatch):
        """Client should read API key from environment."""
        monkeypatch.setenv('WORLDMONITOR_API_KEY', 'wm_env_key')
        client = WorldMonitorClient()
        assert client.api_key == 'wm_env_key'

    @pytest.mark.network
    def test_rest_health_compact(self):
        """Direct REST call to health compact endpoint."""
        client = WorldMonitorClient()
        result = client.get('/api/health?compact=1')
        assert result['status'] == 'HEALTHY'
        assert 'summary' in result
        assert 'checkedAt' in result


class TestWorldMonitorErrorHandling:
    """Test error handling in the capability."""

    @pytest.fixture
    def cap(self):
        storage = SimpleStorage()
        registry = CapabilityRegistry(storage)
        return registry.install('test_id', 'worldmonitor', {})

    def test_unknown_skill(self, cap):
        """Calling unknown skill should return failure result."""
        result = cap.call('worldmonitor.unknown_skill')
        assert isinstance(result, CapabilityResult)
        assert not result.success
        assert result.error['type'] == 'unknown_skill'

    def test_call_tool_missing_name(self, cap):
        """call_tool without tool_name should fail."""
        result = cap.call('worldmonitor.call_tool', arguments={})
        assert isinstance(result, CapabilityResult)
        assert not result.success

    @pytest.mark.network
    def test_authenticated_skill_without_key(self, cap):
        """Authenticated skills should fail gracefully without API key."""
        result = cap.call('worldmonitor.world_brief')
        assert isinstance(result, CapabilityResult)
        assert not result.success
        # Should get auth error
        assert 'auth' in str(result.error).lower() or 'key' in str(result.error).lower() or '401' in str(result.error)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])