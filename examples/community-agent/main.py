#!/usr/bin/env python3
"""
IdentityOS Community Agent — Discord Bot

A reference application demonstrating how to build on the IdentityOS SDK.
The entire bot uses ONLY `from identityos import Identity` — no internal modules.
"""

import logging
import os
import sys

# Ensure the community-agent package is importable
_AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
if _AGENT_DIR not in sys.path:
    sys.path.insert(0, _AGENT_DIR)

import discord
from discord.ext import commands

from config import config
from services.identity import load_or_create_identity


class CommunityAgent(commands.Bot):
    """Discord bot that wraps an IdentityOS identity."""

    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True

        super().__init__(command_prefix="!", intents=intents)

        self.bot_config = config
        self.identity = load_or_create_identity(
            config.identity_id,
            storage_path=config.identity_storage_path,
        )

    async def setup_hook(self) -> None:
        """Load all extensions (commands, listeners, scheduler)."""
        # Commands
        import commands
        commands.setup(self)

        # Listeners
        import listeners.conversation as conversation_listener
        conversation_listener.setup(self)

        # Scheduler
        import scheduler
        scheduler.setup(self)

        # Sync slash commands
        if config.guild_id:
            guild = discord.Object(id=config.guild_id)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            logging.info("Slash commands synced to guild %s", config.guild_id)
        else:
            await self.tree.sync()
            logging.info("Slash commands synced globally")

        logging.info(
            "Community Agent setup complete: %s v%s",
            self.identity.name, self.identity.version,
        )

    async def on_ready(self) -> None:
        logging.info(
            "Bot logged in as %s (ID: %s) | Connected to %d guild(s)",
            self.user, self.user.id, len(self.guilds),
        )


def main() -> None:
    logging.basicConfig(
        level=getattr(logging, config.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if not config.discord_token:
        logging.error("DISCORD_TOKEN not set. Create a .env file from .env.example")
        sys.exit(1)

    bot = CommunityAgent()
    bot.run(config.discord_token, log_handler=None)


if __name__ == "__main__":
    main()
