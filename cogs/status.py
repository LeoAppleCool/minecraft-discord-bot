import discord
from discord.ext import commands, tasks
import logging
import re
import aiosqlite
from mcstatus import JavaServer
from config import MC_HOST, MC_PORT, MC_MAX_PLAYERS, DB_PATH
from utils.rcon import rcon_command

log = logging.getLogger("status")


class StatusCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.server = JavaServer.lookup(f"{MC_HOST}:{MC_PORT}")
        self._last_online = True
        self.update_status.start()

    def cog_unload(self):
        self.update_status.cancel()

    @tasks.loop(seconds=45)
    async def update_status(self):
        try:
            status = await self.server.async_status()
            online = status.players.online
            maximum = status.players.max or MC_MAX_PLAYERS

            activity = discord.Activity(
                type=discord.ActivityType.watching,
                name=f"{online}/{maximum} Spieler",
            )
            await self.bot.change_presence(status=discord.Status.online, activity=activity)

            if not self._last_online:
                log.info("Server wieder online.")
            self._last_online = True

        except Exception:
            if self._last_online:
                log.warning("Server nicht erreichbar – Status auf offline gesetzt.")
            self._last_online = False
            activity = discord.Activity(
                type=discord.ActivityType.watching,
                name="Server offline ❌",
            )
            await self.bot.change_presence(
                status=discord.Status.do_not_disturb, activity=activity
            )

    @update_status.before_loop
    async def before_update(self):
        await self.bot.wait_until_ready()

    @discord.app_commands.command(name="online", description="Zeigt alle Spieler die gerade online sind")
    async def online(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        # Spieleranzahl via mcstatus, echte Namen via RCON list
        try:
            status = await self.server.async_status()
            online_count = status.players.online
            max_count = status.players.max or MC_MAX_PLAYERS
        except Exception:
            embed = discord.Embed(
                title="🔴  Server nicht erreichbar",
                description="Der Minecraft-Server ist aktuell offline.",
                color=0xE74C3C,
            )
            embed.set_footer(text=f"{MC_HOST}:{MC_PORT}")
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Echte Namen via RCON (kein "Anonymous Player" Problem)
        player_names: list[str] = []
        try:
            rcon_resp = await rcon_command("list")
            # Antwort z.B.: "There are 3 of a max of 20 players online: Foo, Bar, Baz"
            match = re.search(r"online:\s*(.+)", rcon_resp, re.IGNORECASE)
            if match:
                raw_names = match.group(1).strip()
                if raw_names:
                    player_names = [n.strip() for n in raw_names.split(",") if n.strip()]
        except Exception:
            pass  # RCON nicht verfügbar → leere Liste

        # IGN → discord_id mapping aus der DB laden
        ign_to_discord: dict[str, int] = {}
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT discord_id, minecraft_name FROM whitelist") as cursor:
                async for discord_id, minecraft_name in cursor:
                    ign_to_discord[minecraft_name.lower()] = discord_id

        if not player_names:
            if online_count == 0:
                description = "Aktuell ist niemand online. 😴"
            else:
                description = f"**{online_count}** Spieler online — keine Namensliste verfügbar."
        else:
            lines = []
            for name in player_names:
                # Prefix wie "[Syndicate] " entfernen für den DB-Lookup
                clean_name = re.sub(r"^\[.*?\]\s*", "", name).strip()
                discord_id = ign_to_discord.get(clean_name.lower())
                if discord_id:
                    lines.append(f"⛏️  **{name}** (<@{discord_id}>)")
                else:
                    lines.append(f"⛏️  **{name}**")
            description = "\n".join(lines)

        bar_filled = round((online_count / max_count) * 10) if max_count else 0
        bar = "█" * bar_filled + "░" * (10 - bar_filled)

        embed = discord.Embed(
            title="🌍  Wer ist gerade online?",
            description=description,
            color=0x57F287,
        )
        embed.add_field(
            name="Spieler",
            value=f"`{bar}` **{online_count}/{max_count}**",
            inline=False,
        )
        embed.set_footer(text=f"{MC_HOST}:{MC_PORT}  •  Nur für dich sichtbar")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.app_commands.command(name="serverstatus", description="Zeigt den aktuellen Server-Status")
    async def serverstatus(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            status = await self.server.async_status()
            players = status.players.online
            maximum = status.players.max or MC_MAX_PLAYERS
            motd = status.description or "—"
            latency = round(status.latency, 1)

            # Player list
            names = []
            if status.players.sample:
                names = [p.name for p in status.players.sample]

            embed = discord.Embed(
                title="🟢  Server Online",
                color=0x2ECC71,
            )
            embed.add_field(name="Spieler", value=f"`{players}/{maximum}`", inline=True)
            embed.add_field(name="Ping",    value=f"`{latency} ms`",        inline=True)
            embed.add_field(name="MOTD",    value=f"`{str(motd)[:100]}`",   inline=False)
            if names:
                embed.add_field(
                    name="Online",
                    value=", ".join(f"`{n}`" for n in names) or "—",
                    inline=False,
                )
            embed.set_footer(text=f"{MC_HOST}:{MC_PORT}")
            await interaction.followup.send(embed=embed)

        except Exception as e:
            embed = discord.Embed(
                title="🔴  Server Offline",
                description="Der Server ist aktuell nicht erreichbar.",
                color=0xE74C3C,
            )
            embed.set_footer(text=f"{MC_HOST}:{MC_PORT}")
            await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(StatusCog(bot))
