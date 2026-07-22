import os
from dataclasses import dataclass, field
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


@dataclass
class Config:
    discord_token: str = field(default_factory=lambda: os.getenv("DISCORD_TOKEN", ""))
    guild_id: int = field(default_factory=lambda: int(os.getenv("GUILD_ID", "0")))

    identity_id: str = field(default_factory=lambda: os.getenv("IDENTITY_ID", "discord-agent"))
    identity_name: str = field(default_factory=lambda: os.getenv("IDENTITY_NAME", "Discord Agent"))
    identity_class: str = field(default_factory=lambda: os.getenv("IDENTITY_CLASS", "assistant"))
    identity_storage_path: str = field(default_factory=lambda: os.getenv("IDENTITY_STORAGE_PATH", "/data/identities"))

    reminder_interval_minutes: int = field(
        default_factory=lambda: int(os.getenv("REMINDER_INTERVAL_MINUTES", "30"))
    )
    digest_time_daily: str = field(default_factory=lambda: os.getenv("DIGEST_TIME_DAILY", "09:00"))
    digest_time_weekly: str = field(default_factory=lambda: os.getenv("DIGEST_TIME_WEEKLY", "09:00"))
    digest_day_weekly: str = field(default_factory=lambda: os.getenv("DIGEST_DAY_WEEKLY", "monday"))

    timezone: str = field(default_factory=lambda: os.getenv("TIMEZONE", "UTC"))
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    log_format: str = field(
        default_factory=lambda: os.getenv(
            "LOG_FORMAT", "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        )
    )

    healthcheck_port: int = field(default_factory=lambda: int(os.getenv("HEALTHCHECK_PORT", "8080")))
    command_sync_on_start: bool = field(
        default_factory=lambda: os.getenv("COMMAND_SYNC_ON_START", "true").lower() == "true"
    )

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.discord_token:
            errors.append("DISCORD_TOKEN is required")
        if self.guild_id <= 0:
            errors.append("GUILD_ID must be a positive integer")
        if self.reminder_interval_minutes < 1:
            errors.append("REMINDER_INTERVAL_MINUTES must be >= 1")
        try:
            hour, minute = self.digest_time_daily.split(":")
            int(hour)
            int(minute)
        except (ValueError, AttributeError):
            errors.append("DIGEST_TIME_DAILY must be HH:MM format")
        valid_days = {"monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"}
        if self.digest_day_weekly.lower() not in valid_days:
            errors.append(f"DIGEST_DAY_WEEKLY must be one of {valid_days}")
        return errors


config = Config()
