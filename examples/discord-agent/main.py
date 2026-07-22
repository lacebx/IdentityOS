#!/usr/bin/env python3
"""
IdentityOS Discord Agent — production-ready Discord bot powered by IdentityOS.

Uses ONLY from identityos import Identity — no internal runtime imports.
"""

import asyncio
import logging
import os
import signal
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from typing import Optional

import discord
from discord.ext import commands

from config import config
from services.identity import load_or_create_identity

logger = logging.getLogger(__name__)


class HealthHandler(BaseHTTPRequestHandler):
    """Minimal HTTP healthcheck endpoint."""

    def do_GET(self) -> None:
        if self.path == "/healthz":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            status = "healthy" if getattr(self.server, "bot_ready", False) else "starting"
            self.wfile.write(f'{{"status":"{status}"}}\n'.encode())
        else:
            self.send_response(404)
            self.end_headers()


class DiscordAgent(commands.Bot):
    """Production Discord bot wrapping an IdentityOS identity."""

    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.members = True

        super().__init__(
            command_prefix="!",
            intents=intents,
            heartbeat_timeout=60.0,
            guild_ready_timeout=5.0,
        )

        self.config = config
        self.identity = load_or_create_identity(
            identity_id=config.identity_id,
            identity_name=config.identity_name,
            identity_class=config.identity_class,
            storage_path=config.identity_storage_path,
        )
        self._health_server: Optional[HTTPServer] = None
        self._running = True

    async def setup_hook(self) -> None:
        """Register all components."""
        import commands
        commands.setup(self)

        import listeners
        listeners.setup(self)

        import scheduler
        scheduler.setup(self)

        if config.command_sync_on_start and config.guild_id:
            guild = discord.Object(id=config.guild_id)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            logger.info("Synced %d slash commands to guild %s", len(synced), config.guild_id)
        elif config.command_sync_on_start:
            synced = await self.tree.sync()
            logger.info("Synced %d slash commands globally", len(synced))

        logger.info(
            "Setup complete: %s v%s | persona=%s role=%s",
            self.identity.name, self.identity.version,
            self.identity.persona, self.identity.role,
        )

    async def on_ready(self) -> None:
        logger.info(
            "Bot online: %s (ID: %s) | %d guild(s) | %d member(s)",
            self.user, self.user.id,
            len(self.guilds),
            sum(g.member_count or 0 for g in self.guilds),
        )
        # Signal healthcheck that we're ready
        if self._health_server:
            self._health_server.bot_ready = True

    async def on_resumed(self) -> None:
        logger.info("Session resumed after disconnect")

    async def close(self) -> None:
        self._running = False
        if self._health_server:
            self._health_server.shutdown()
        logger.info("Shutting down...")
        await super().close()

    def run_healthcheck(self) -> None:
        """Run healthcheck HTTP server in a background thread."""
        server = HTTPServer(("0.0.0.0", config.healthcheck_port), HealthHandler)
        server.bot_ready = False
        self._health_server = server
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        logger.info("Healthcheck listening on port %d", config.healthcheck_port)


def main() -> None:
    logging.basicConfig(
        level=getattr(logging, config.log_level.upper(), logging.INFO),
        format=config.log_format,
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    errors = config.validate()
    if errors:
        for err in errors:
            logger.error("Config error: %s", err)
        sys.exit(1)

    bot = DiscordAgent()
    bot.run_healthcheck()

    # Handle graceful shutdown
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, lambda s, f: asyncio.create_task(bot.close()))
        except (ValueError, AttributeError):
            pass

    try:
        bot.run(config.discord_token, log_handler=None)
    except discord.LoginFailure:
        logger.error("Invalid Discord token. Check your .env file.")
        sys.exit(1)
    except discord.PrivilegedIntentsRequired:
        logger.error(
            "Missing privileged intents. "
            "Enable MESSAGE CONTENT INTENT and SERVER MEMBERS INTENT in the Discord Developer Portal."
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
