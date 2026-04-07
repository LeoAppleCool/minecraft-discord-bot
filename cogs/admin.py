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


# ── Schnell-Buttons ───────────────────────────────────────────────────────────

class AdminPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def _run(self, interaction: discord.Interaction, cmd: str, label: str):
        await interaction.response.defer(ephemeral=True)
        try:
            resp = await rcon_command(cmd)
            await interaction.followup.send(
                f"✅ **{label}**\n```{resp or '(kein Output)'}```",
                ephemeral=True,
            )
        except Exception as e:
            await interaction.followup.send(f"❌ RCON-Fehler: `{e}`", ephemeral=True)

    @discord.ui.button(label="☀️ Tag setzen",   style=discord.ButtonStyle.primary,  custom_id="admin:day",   row=0)
    async def set_day(self, i, _):   await self._run(i, "time set day",   "Tag gesetzt")

    @discord.ui.button(label="🌙 Nacht setzen", style=discord.ButtonStyle.secondary, custom_id="admin:night", row=0)
    async def set_night(self, i, _): await self._run(i, "time set night", "Nacht gesetzt")

    @discord.ui.button(label="☀️ Klares Wetter", style=discord.ButtonStyle.primary,  custom_id="admin:clear", row=0)
    async def clear_weather(self, i, _): await self._run(i, "weather clear", "Wetter: klar")

    @discord.ui.button(label="🌧️ Regen",        style=discord.ButtonStyle.secondary, custom_id="admin:rain",  row=0)
    async def rain(self, i, _):      await self._run(i, "weather rain",  "Wetter: Regen")

    @discord.ui.button(label="💾 Save-All",      style=discord.ButtonStyle.success,   custom_id="admin:save",  row=1)
    async def save_all(self, i, _):  await self._run(i, "save-all",      "Welt gespeichert")

    @discord.ui.button(label="📋 Whitelist",     style=discord.ButtonStyle.secondary, custom_id="admin:wl",    row=1)
    async def wl_list(self, i, _):   await self._run(i, "whitelist list", "Whitelist")

    @discord.ui.button(label="👥 Spielerliste",  style=discord.ButtonStyle.secondary, custom_id="admin:list",  row=1)
    async def player_list(self, i, _): await self._run(i, "list",         "Spielerliste")


# ── Cog ───────────────────────────────────────────────────────────────────────

class AdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.add_view(AdminPanelView())

    rcon_group = app_commands.Group(name="rcon", description="Admin RCON Befehle")

    @rcon_group.command(name="panel", description="Öffnet das Admin-Panel")
    @is_admin()
    async def panel(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🛠️  Admin Panel",
            description="Schnell-Aktionen für den Server. Nur für Admins sichtbar.",
            color=0xE67E22,
        )
        embed.add_field(
            name="Zeile 1 — Zeit & Wetter",
            value="Tag/Nacht setzen, Wetter ändern",
            inline=False,
        )
        embed.add_field(
            name="Zeile 2 — Verwaltung",
            value="Welt speichern, Whitelist anzeigen, Spielerliste",
            inline=False,
        )
        await interaction.response.send_message(
            embed=embed, view=AdminPanelView(), ephemeral=True
        )

    @rcon_group.command(name="cmd", description="Führt einen beliebigen RCON-Befehl aus")
    @is_admin()
    @app_commands.describe(command="Der Minecraft-Befehl (ohne /)")
    async def cmd(self, interaction: discord.Interaction, command: str):
        await interaction.response.defer(ephemeral=True)
        try:
            response = await rcon_command(command)
            await interaction.followup.send(
                f"**`/{command}`**\n```{response or '(kein Output)'}```",
                ephemeral=True,
            )
            # Log
            embed = discord.Embed(title="🛠️ RCON Befehl", color=0xE67E22)
            embed.add_field(name="Admin",   value=interaction.user.mention,      inline=True)
            embed.add_field(name="Befehl",  value=f"`/{command}`",               inline=True)
            embed.add_field(name="Antwort", value=f"```{response or '—'}```",    inline=False)
            await log_channel(self.bot, embed)
        except Exception as e:
            await interaction.followup.send(f"❌ RCON-Fehler: `{e}`", ephemeral=True)

    @rcon_group.command(name="kick", description="Kickt einen Spieler vom Server")
    @is_admin()
    @app_commands.describe(ign="Minecraft-Username", reason="Grund (optional)")
    async def kick(self, interaction: discord.Interaction, ign: str, reason: str = "Kein Grund angegeben"):
        await interaction.response.defer(ephemeral=True)
        try:
            resp = await rcon_command(f"kick {ign} {reason}")
            await interaction.followup.send(
                f"👢 `{ign}` wurde gekickt.\n```{resp}```", ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(f"❌ `{e}`", ephemeral=True)

    @rcon_group.command(name="ban", description="Bannt einen Spieler")
    @is_admin()
    @app_commands.describe(ign="Minecraft-Username", reason="Grund (optional)")
    async def ban(self, interaction: discord.Interaction, ign: str, reason: str = "Kein Grund angegeben"):
        await interaction.response.defer(ephemeral=True)
        try:
            resp = await rcon_command(f"ban {ign} {reason}")
            await interaction.followup.send(
                f"🔨 `{ign}` wurde gebannt.\n```{resp}```", ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(f"❌ `{e}`", ephemeral=True)

    @rcon_group.command(name="announce", description="Schickt eine Server-Nachricht")
    @is_admin()
    @app_commands.describe(message="Die Nachricht die im Chat erscheint")
    async def announce(self, interaction: discord.Interaction, message: str):
        await interaction.response.defer(ephemeral=True)
        try:
            await rcon_command(f'say {message}')
            await interaction.followup.send(
                f"📢 Nachricht gesendet: *{message}*", ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(f"❌ `{e}`", ephemeral=True)


async def setup(bot):
    await bot.add_cog(AdminCog(bot))
