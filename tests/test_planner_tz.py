"""
test_planner_tz.py — R8 regression: invalid timezones are rejected with a
structured failure; valid IANA zones resolve to real offsets.

The old planner extracted ANY short token after ``in`` as a timezone
("OKC", "NEW", "TOKYO") and silently fell back to UTC for longer IANA
names — fabricating results for zones it never resolved.

New contract asserts:
  * fake zone names (OKC, Tokyo-without-region) produce a structured
    ValueError surfaced as failed routing evidence, never a success.
  * valid IANA zones (America/Chicago, Asia/Tokyo) resolve to real,
    non-zero UTC offsets.
  * no-zone requests still default to UTC.
"""

import pytest

from core.planner import SkillRouter
from core.capabilities.registry import lookup
from core.capabilities.datetime import DateTimeCapability, _offset_for


@pytest.fixture()
def router():
    return SkillRouter(None, "test")


class _S:
    def __init__(self, name):
        self.name = name


def test_invalid_zone_rejected_with_valueerror(router):
    for q in ("what time is it in OKC", "time in New York", "time in Tokyo"):
        with pytest.raises(ValueError, match="Unknown timezone"):
            router._extract_params(q, _S("datetime.now"))


def test_route_fails_honestly_for_invalid_zone():
    from core.capabilities.registry import CapabilityRegistry
    from runtime.persistence import JSONFileBackend
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        reg = CapabilityRegistry(JSONFileBackend(root_dir=d))
        inst = lookup("datetime")()
        inst.install("test", reg._storage)
        r = SkillRouter(reg, "test")
        ev = r.route("what time is it in OKC")
        for r in ev._results:
            assert r.success is False, r
            assert "Unknown timezone" in r.error["message"]


def test_valid_iana_zone_resolves_real_offset(router):
    params = router._extract_params("time in America/Chicago", _S("datetime.now"))
    assert params == {"tz_name": "America/Chicago"}
    assert _offset_for("America/Chicago") != 0.0

    res = DateTimeCapability().call("datetime.now", tz_name="America/Chicago")
    assert res.success
    assert res.data["utc_offset_hours"] == -5.0 or res.data["utc_offset_hours"] == -6.0


def test_valid_iana_zone_asia_tokyo(router):
    params = router._extract_params("time in Asia/Tokyo", _S("datetime.now"))
    assert params == {"tz_name": "Asia/Tokyo"}
    res = DateTimeCapability().call("datetime.now", tz_name="Asia/Tokyo")
    assert res.success
    assert res.data["utc_offset_hours"] == 9.0


def test_no_zone_defaults_to_utc(router):
    params = router._extract_params("what time is it", _S("datetime.now"))
    assert params == {"tz_name": "UTC"}


def test_known_codes_still_work(router):
    params = router._extract_params("time in IST", _S("datetime.now"))
    assert params == {"tz_name": "IST"}
    res = DateTimeCapability().call("datetime.now", tz_name="IST")
    assert res.success
    assert res.data["utc_offset_hours"] == 5.5