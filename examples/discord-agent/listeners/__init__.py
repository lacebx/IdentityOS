import logging

import discord
from discord.ext import commands

from pipeline import run_pipeline, generate_team_status
from pipeline import step_detect_evidence_question, step_detect_status_question

logger = logging.getLogger(__name__)


def setup(bot: commands.Bot) -> None:
    identity = bot.identity

    @bot.event
    async def on_message(message: discord.Message):
        if message.author.bot:
            return
        if not message.guild:
            return

        content = message.content.strip()
        author_id = str(message.author.id)
        channel_id = str(message.channel.id)

        # Build a session ID from guild + channel (thread-aware)
        if isinstance(message.channel, discord.Thread):
            session_id = f"discord:{message.guild.id}:thread:{message.channel.id}"
        else:
            session_id = f"discord:{message.guild.id}:channel:{channel_id}"

        # Show typing indicator
        async with message.channel.typing():
            result = run_pipeline(identity, content, author_id, channel_id, session_id)

        reply = result["reply"]
        if not reply:
            return

        if len(reply) > 1900:
            reply = reply[:1900] + "..."

        await message.channel.send(reply)

    @bot.event
    async def on_message_edit(before: discord.Message, after: discord.Message):
        """Treat edited messages as new input."""
        if after.author.bot or not after.guild:
            return
        content = after.content.strip()
        if content == before.content.strip():
            return
        logger.debug("Message edited: %s", after.id)
        # Re-process the edited message
        author_id = str(after.author.id)
        channel_id = str(after.channel.id)
        if isinstance(after.channel, discord.Thread):
            session_id = f"discord:{after.guild.id}:thread:{after.channel.id}"
        else:
            session_id = f"discord:{after.guild.id}:channel:{channel_id}"

        async with after.channel.typing():
            result = run_pipeline(identity, content, author_id, channel_id, session_id)

        reply = result["reply"]
        if reply and len(reply) > 1900:
            reply = reply[:1900] + "..."
        if reply:
            await after.channel.send(reply)

    logger.info("Message listener registered")
