import logging
from datetime import datetime, timezone
from typing import Optional

import discord
from discord.ext import commands, tasks

logger = logging.getLogger(__name__)


def setup(bot: commands.Bot) -> None:
    identity = bot.identity
    cfg = bot.config

    @tasks.loop(minutes=cfg.reminder_interval_minutes)
    async def check_reminders():
        if not bot.is_ready():
            return
        reminders = identity.reminders(max_results=10)
        overdue = [r for r in reminders if r["label"] == "overdue"]
        if not overdue:
            return

        channel = _find_default_channel(bot)
        if not channel:
            logger.warning("No channel found for reminders")
            return

        for r in overdue[:3]:
            author_id = r.get("author_id", "")
            mention = f"<@{author_id}>" if author_id else "someone"
            hours = abs(r["hours_left"])
            msg = (
                f"⏰ Hey {mention}, you said you'd finish **{r['description']}** "
                f"— it's now {hours:.0f}h overdue. Any update?"
            )
            try:
                await channel.send(msg)
                logger.info("Reminder sent: %s — %s", author_id, r["description"][:40])
            except Exception as e:
                logger.error("Reminder send failed: %s", e)

    @tasks.loop(hours=24)
    async def daily_digest():
        if not bot.is_ready():
            return
        now = datetime.now(timezone.utc)
        try:
            h, m = map(int, cfg.digest_time_daily.split(":"))
        except (ValueError, AttributeError):
            return
        if now.hour != h or now.minute < m or now.minute > m + 5:
            return

        channel = _find_default_channel(bot)
        if not channel:
            return

        from services.summary import generate_digest
        text = generate_digest(identity, period="daily")
        if len(text) > 1900:
            text = text[:1900] + "\n..."
        try:
            await channel.send(text)
            logger.info("Daily digest sent")
        except Exception as e:
            logger.error("Daily digest failed: %s", e)

    @tasks.loop(hours=24)
    async def weekly_digest():
        if not bot.is_ready():
            return
        now = datetime.now(timezone.utc)
        if now.strftime("%A").lower() != cfg.digest_day_weekly.lower():
            return
        try:
            h, m = map(int, cfg.digest_time_weekly.split(":"))
        except (ValueError, AttributeError):
            return
        if now.hour != h or now.minute < m or now.minute > m + 5:
            return

        channel = _find_default_channel(bot)
        if not channel:
            return

        from services.summary import generate_digest
        text = generate_digest(identity, period="weekly")
        if len(text) > 1900:
            text = text[:1900] + "\n..."
        try:
            await channel.send(text)
            logger.info("Weekly digest sent")
        except Exception as e:
            logger.error("Weekly digest failed: %s", e)

    for loop in (check_reminders, daily_digest, weekly_digest):
        loop.before_loop(bot.wait_until_ready)
        loop.start()

    logger.info(
        "Scheduler: reminders %dmin, daily at %s, weekly %s at %s",
        cfg.reminder_interval_minutes,
        cfg.digest_time_daily,
        cfg.digest_day_weekly,
        cfg.digest_time_weekly,
    )


def _find_default_channel(bot: commands.Bot) -> Optional[discord.TextChannel]:
    for guild in bot.guilds:
        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).send_messages:
                return channel
    return None
