import logging

import discord
from discord import app_commands
from discord.ext import commands

from services.summary import generate_team_status, generate_digest, format_evidence
from services.constitution import format_constitution

logger = logging.getLogger(__name__)


def setup(bot: commands.Bot) -> None:
    identity = bot.identity

    @bot.tree.command(name="about", description="Show identity information")
    async def about(interaction: discord.Interaction):
        desc = identity.describe()
        text = (
            f"**{desc.get('name', '?')}** v{desc.get('version', '?')}\n"
            f"Persona: {desc.get('persona', '?')} | Role: {desc.get('role', '?')}\n"
            f"Status: {desc.get('status', '?')}\n\n"
            f"Goals: {desc.get('active_goals', 0)} active\n"
            f"Intentions: {desc.get('active_intentions', 0)} active\n"
            f"Memories: {desc.get('memories', 0)} stored\n"
            f"Relationships: {desc.get('relationships', 0)}\n"
            f"Timeline Events: {desc.get('timeline_events', 0)}\n\n"
            f"Powered by **IdentityOS**"
        )
        await interaction.response.send_message(text)

    @bot.tree.command(name="status", description="Show team status summary")
    async def status_cmd(interaction: discord.Interaction):
        text = generate_team_status(identity)
        if len(text) > 1900:
            text = text[:1900] + "\n..."
        await interaction.response.send_message(text)

    @bot.tree.command(name="goals", description="List active goals")
    async def goals_cmd(interaction: discord.Interaction):
        goals = identity.goals(status="active")
        if not goals:
            await interaction.response.send_message("No active goals.")
            return
        lines = ["## Active Goals", ""]
        for g in goals:
            lines.append(f"- **{g['title']}** [{g['priority']}] — {g.get('progress', 0):.0%}")
        await interaction.response.send_message("\n".join(lines))

    @bot.tree.command(name="intentions", description="List active intentions")
    async def intentions_cmd(interaction: discord.Interaction):
        intentions = identity.intentions(status="active")
        if not intentions:
            await interaction.response.send_message("No active intentions.")
            return
        lines = ["## Active Intentions", ""]
        for i in intentions:
            author = i.get("metadata", {}).get("author_id", "?")
            expires = i.get("expires_at", "?")[:10]
            lines.append(f"- {i['description']} (by {author}, due {expires})")
        text = "\n".join(lines)
        if len(text) > 1900:
            text = text[:1900] + "\n..."
        await interaction.response.send_message(text)

    @bot.tree.command(name="reminders", description="Show pending reminders")
    async def reminders_cmd(interaction: discord.Interaction):
        reminders = identity.reminders(max_results=20)
        if not reminders:
            await interaction.response.send_message("No pending reminders.")
            return
        lines = ["## Pending Reminders", ""]
        for r in reminders:
            author = r.get("author_id", "unknown")
            label = r["label"].replace("_", " ").title()
            hours = r["hours_left"]
            lines.append(f"- **{author}:** {r['description']} ({label}, {hours:.1f}h)")
        text = "\n".join(lines)
        if len(text) > 1900:
            text = text[:1900] + "\n..."
        await interaction.response.send_message(text)

    @bot.tree.command(name="digest", description="Generate a digest")
    @app_commands.describe(period="daily or weekly")
    @app_commands.choices(period=[
        app_commands.Choice(name="Daily", value="daily"),
        app_commands.Choice(name="Weekly", value="weekly"),
    ])
    async def digest_cmd(interaction: discord.Interaction, period: str = "daily"):
        text = generate_digest(identity, period)
        if len(text) > 1900:
            text = text[:1900] + "\n..."
        await interaction.response.send_message(text)

    @bot.tree.command(name="timeline", description="Show recent timeline events")
    @app_commands.describe(limit="Number of events (max 20)")
    async def timeline_cmd(interaction: discord.Interaction, limit: int = 10):
        limit = min(max(limit, 1), 20)
        events = identity.timeline(limit=limit)
        if not events:
            await interaction.response.send_message("No timeline events.")
            return
        lines = [f"## Recent Events (last {limit})", ""]
        for e in reversed(events):
            lines.append(f"- **{e['title']}** ({e.get('occurred_at', '?')[:16]})")
        text = "\n".join(lines)
        if len(text) > 1900:
            text = text[:1900] + "\n..."
        await interaction.response.send_message(text)

    @bot.tree.command(name="evidence", description="Show evidence for an entity")
    @app_commands.describe(entity_id="Entity ID to look up")
    async def evidence_cmd(interaction: discord.Interaction, entity_id: str):
        text = format_evidence(identity, entity_id)
        if len(text) > 1900:
            text = text[:1900] + "\n..."
        await interaction.response.send_message(text)

    @bot.tree.command(name="confidence", description="Show confidence for an entity")
    @app_commands.describe(entity_id="Entity ID to look up")
    async def confidence_cmd(interaction: discord.Interaction, entity_id: str):
        conf = identity.confidence(entity_id)
        if "error" in conf:
            await interaction.response.send_message(f"Entity `{entity_id}` not found.")
            return
        lines = [f"### Confidence for `{entity_id}`", ""]
        for k, v in conf.items():
            lines.append(f"**{k}:** {v}")
        text = "\n".join(lines)
        if len(text) > 1900:
            text = text[:1900] + "\n..."
        await interaction.response.send_message(text)

    @bot.tree.command(name="constitution", description="Show the IdentityOS Constitution")
    async def constitution_cmd(interaction: discord.Interaction):
        text = format_constitution(identity)
        if len(text) > 1900:
            text = text[:1900] + "\n..."
        await interaction.response.send_message(text)

    @bot.tree.command(name="help", description="Show available commands")
    async def help_cmd(interaction: discord.Interaction):
        commands_list = [
            ("/about", "Identity information"),
            ("/status", "Team status summary"),
            ("/goals", "Active goals"),
            ("/intentions", "Active intentions"),
            ("/reminders", "Pending reminders"),
            ("/digest", "Daily or weekly digest"),
            ("/timeline", "Recent events"),
            ("/evidence", "Evidence for an entity"),
            ("/confidence", "Confidence for an entity"),
            ("/constitution", "IdentityOS Constitution"),
            ("/help", "This message"),
        ]
        lines = ["## Discord Agent Commands", ""]
        for cmd, desc in commands_list:
            lines.append(f"  `{cmd:16s}` — {desc}")
        lines.append("")
        lines.append("The bot also automatically detects commitments, meetings, ")
        lines.append("deadlines, and completions in normal conversation.")
        await interaction.response.send_message("\n".join(lines))

    logger.info("Slash commands registered: about, status, goals, intentions, reminders, digest, timeline, evidence, confidence, constitution, help")
