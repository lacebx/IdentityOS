"""
Test configuration validation.
"""

import os
import sys

_AGENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _AGENT_DIR not in sys.path:
    sys.path.insert(0, _AGENT_DIR)

from config import Config


class TestConfig:
    def test_default_config(self):
        cfg = Config()
        errors = cfg.validate()
        # Should fail because DISCORD_TOKEN is empty and GUILD_ID is 0
        assert any("DISCORD_TOKEN" in e for e in errors)
        assert any("GUILD_ID" in e for e in errors)

    def test_valid_config(self):
        cfg = Config()
        cfg.discord_token = "fake-token"
        cfg.guild_id = 123456789
        assert len(cfg.validate()) == 0

    def test_invalid_digest_time(self):
        cfg = Config()
        cfg.digest_time_daily = "not-a-time"
        errors = cfg.validate()
        assert any("DIGEST_TIME_DAILY" in e for e in errors)

    def test_invalid_digest_day(self):
        cfg = Config()
        cfg.discord_token = "t"
        cfg.guild_id = 1
        cfg.digest_day_weekly = "funday"
        errors = cfg.validate()
        assert any("DIGEST_DAY_WEEKLY" in e for e in errors)

    def test_reminder_interval_valid(self):
        cfg = Config()
        cfg.discord_token = "t"
        cfg.guild_id = 1
        cfg.reminder_interval_minutes = 0
        errors = cfg.validate()
        assert any("REMINDER_INTERVAL_MINUTES" in e for e in errors)
