import discord
from discord.ext import commands
from discord import app_commands
import logging
from config import ADMIN_ROLE_ID
from utils.rcon import rcon_command
from utils.logger import log as log_channel

log = logging.getLogger("admin")


def is_admin():
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.user.guild_permissions.administrator:
            return True
        if ADMIN_ROLE_ID:
            role = interaction.guild.get_role(ADMIN_ROLE_ID)
            if role and role in interaction.user.roles:
                return True
        raise app_commands.MissingPermissions(["administrator"])
    return app_commands.check(predicate)


# ── Quick-Action Buttons ──────────────────────────────────────────────────────

class AdminPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def _run(self, interaction: discord.Interaction, cmd: str, label: str):
        await interaction.response.defer(ephemeral=True)
        try:
            resp = await rcon_command(cmd)
            await interaction.followup.send(
                f"✅ **{label}**\n```{resp or '(no output)'}```",
                ephemeral=True,
            )
        except Exception as e:
            await interaction.followup.send(f"❌ RCON error: `{e}`", ephemeral=True)

    @discord.ui.button(label="☀️ Set Day",      style=discord.ButtonStyle.primary,   custom_id="admin:day",   row=0)
    async def set_day(self, i, _):       await self._run(i, "time set day",    "Day set")

    @discord.ui.button(label="🌙 Set Night",    style=discord.ButtonStyle.secondary,  custom_id="admin:night", row=0)
    async def set_night(self, i, _):     await self._run(i, "time set night",  "Night set")

    @discord.ui.button(label="☀️ Clear Weather", style=discord.ButtonStyle.primary,  custom_id="admin:clear", row=0)
    async def clear_weather(self, i, _): await self._run(i, "weather clear",   "Weather: clear")

    @discord.ui.button(label="🌧️ Rain",         style=discord.ButtonStyle.secondary,  custom_id="admin:rain",  row=0)
    async def rain(self, i, _):          await self._run(i, "weather rain",    "Weather: rain")

    @discord.ui.button(label="💾 Save-All",      style=discord.ButtonStyle.success,   custom_id="admin:save",  row=1)
    async def save_all(self, i, _):      await self._run(i, "save-all",        "World saved")

    @discord.ui.button(label="📋 Whitelist",     style=discord.ButtonStyle.secondary, custom_id="admin:wl",    row=1)
    async def wl_list(self, i, _):       await self._run(i, "whitelist list",  "Whitelist")

    @discord.ui.button(label="👥 Player List",   style=discord.ButtonStyle.secondary, custom_id="admin:list",  row=1)
    async def player_list(self, i, _):   await self._run(i, "list",            "Player list")


# ── Cog ───────────────────────────────────────────────────────────────────────

class AdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.add_view(AdminPanelView())

    rcon_group = app_commands.Group(name="rcon", description="Admin RCON commands")

    @rcon_group.command(name="panel", description="Opens the admin quick-action panel")
    @is_admin()
    async def panel(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🛠️  Admin Panel",
            description="Quick actions for the server. Only visible to you.",
            color=0xE67E22,
        )
        embed.add_field(
            name="Row 1 — Time & Weather",
            value="Set day/night, change weather",
            inline=False,
        )
        embed.add_field(
            name="Row 2 — Management",
            value="Save world, show whitelist, list players",
            inline=False,
        )
        await interaction.response.send_message(
            embed=embed, view=AdminPanelView(), ephemeral=True
        )

    @rcon_group.command(name="cmd", description="Runs any RCON command on the server")
    @is_admin()
    @app_commands.describe(command="The Minecraft command (without /)")
    async def cmd(self, interaction: discord.Interaction, command: str):
        await interaction.response.defer(ephemeral=True)
        try:
            response = await rcon_command(command)
            await interaction.followup.send(
                f"**`/{command}`**\n```{response or '(no output)'}```",
                ephemeral=True,
            )
            embed = discord.Embed(title="🛠️ RCON Command", color=0xE67E22)
            embed.add_field(name="Admin",    value=interaction.user.mention,   inline=True)
            embed.add_field(name="Command",  value=f"`/{command}`",            inline=True)
            embed.add_field(name="Response", value=f"```{response or '—'}```", inline=False)
            await log_channel(self.bot, embed)
        except Exception as e:
            await interaction.followup.send(f"❌ RCON error: `{e}`", ephemeral=True)

    @rcon_group.command(name="kick", description="Kicks a player from the server")
    @is_admin()
    @app_commands.describe(ign="Minecraft username", reason="Reason (optional)")
    async def kick(self, interaction: discord.Interaction, ign: str, reason: str = "No reason provided"):
        await interaction.response.defer(ephemeral=True)
        try:
            resp = await rcon_command(f"kick {ign} {reason}")
            await interaction.followup.send(
                f"👢 `{ign}` has been kicked.\n```{resp}```", ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(f"❌ `{e}`", ephemeral=True)

    @rcon_group.command(name="ban", description="Bans a player from the server")
    @is_admin()
    @app_commands.describe(ign="Minecraft username", reason="Reason (optional)")
    async def ban(self, interaction: discord.Interaction, ign: str, reason: str = "No reason provided"):
        await interaction.response.defer(ephemeral=True)
        try:
            resp = await rcon_command(f"ban {ign} {reason}")
            await interaction.followup.send(
                f"🔨 `{ign}` has been banned.\n```{resp}```", ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(f"❌ `{e}`", ephemeral=True)

    @rcon_group.command(name="announce", description="Broadcasts a message in-game via say")
    @is_admin()
    @app_commands.describe(message="The message to broadcast in chat")
    async def announce(self, interaction: discord.Interaction, message: str):
        await interaction.response.defer(ephemeral=True)
        try:
            await rcon_command(f'say {message}')
            await interaction.followup.send(
                f"📢 Message sent: *{message}*", ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(f"❌ `{e}`", ephemeral=True)


async def setup(bot):
    await bot.add_cog(AdminCog(bot))
