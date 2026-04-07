import discord
from discord.ext import commands
from discord import app_commands
import logging
import aiosqlite
import re
from config import MEMBER_ROLE_ID, WHITELIST_CHANNEL_ID, GUILD_ID, DB_PATH
from utils.rcon import rcon_command
from utils.logger import log as log_channel

log = logging.getLogger("whitelist")

IGN_REGEX = re.compile(r"^[a-zA-Z0-9_]{3,16}$")


# ── Modal ──────────────────────────────────────────────────────────────────────

class IGNModal(discord.ui.Modal, title="🎮 Minecraft Whitelist"):
    ign = discord.ui.TextInput(
        label="Dein Minecraft Username (IGN)",
        placeholder="z.B. Notch  |  Bedrock: .Notch (Punkt wird auto-ergänzt)",
        min_length=3,
        max_length=17,
        style=discord.TextStyle.short,
    )

    platform = discord.ui.TextInput(
        label="Platform (java / bedrock)",
        placeholder="java  oder  bedrock",
        min_length=4,
        max_length=7,
        style=discord.TextStyle.short,
    )

    def __init__(self, bot: commands.Bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        raw_name = self.ign.value.strip()
        platform = self.platform.value.strip().lower()

        if platform not in ("java", "bedrock"):
            await interaction.followup.send(
                "❌ Platform muss `java` oder `bedrock` sein.", ephemeral=True
            )
            return

        if platform == "bedrock":
            if not raw_name.startswith("."):
                raw_name = f".{raw_name}"
            name_check = raw_name[1:]
            if not re.match(r"^[a-zA-Z0-9_ ]{3,16}$", name_check):
                await interaction.followup.send(
                    "❌ Ungültiger Bedrock-Username!", ephemeral=True
                )
                return
        else:
            if not IGN_REGEX.match(raw_name):
                await interaction.followup.send(
                    "❌ Ungültiger Java-Username! Nur Buchstaben, Zahlen und `_` erlaubt (3–16 Zeichen).",
                    ephemeral=True,
                )
                return

        name = raw_name

        # Bereits whitelistet?
        async with aiosqlite.connect(DB_PATH) as db:
            row = await (await db.execute(
                "SELECT minecraft_name FROM whitelist WHERE discord_id = ?",
                (interaction.user.id,)
            )).fetchone()

        if row:
            await interaction.followup.send(
                f"⚠️ Du bist bereits als `{row[0]}` whitelistet. "
                "Wende dich an einen Admin, um deinen IGN zu ändern.",
                ephemeral=True,
            )
            return

        # RCON
        try:
            if platform == "bedrock":
                response = await rcon_command(f"fwhitelist add {name}")
            else:
                response = await rcon_command(f"whitelist add {name}")
        except Exception:
            await interaction.followup.send(
                "❌ Verbindung zum Minecraft-Server fehlgeschlagen. Versuche es später nochmal.",
                ephemeral=True,
            )
            return

        if "already" in response.lower():
            await interaction.followup.send(
                f"⚠️ `{name}` ist schon auf der Whitelist. Falls das dein Account ist, "
                "melde dich bei einem Admin.",
                ephemeral=True,
            )
            return

        # In DB speichern
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO whitelist (discord_id, minecraft_name) VALUES (?, ?)",
                (interaction.user.id, name),
            )
            await db.commit()

        # Nickname setzen
        try:
            base = interaction.user.display_name.split(" (")[0]
            await interaction.user.edit(nick=f"{base} ({name})"[:32])
        except discord.Forbidden:
            pass

        # Member-Rolle geben
        guild = interaction.guild
        if guild and MEMBER_ROLE_ID:
            role = guild.get_role(MEMBER_ROLE_ID)
            if role:
                try:
                    await interaction.user.add_roles(role, reason="Whitelist beigetreten")
                except discord.Forbidden:
                    pass

        plattform_emoji = "📱" if platform == "bedrock" else "💻"
        await interaction.followup.send(
            f"✅ {plattform_emoji} **{name}** wurde erfolgreich zur Whitelist hinzugefügt!\n"
            "Du kannst den Server jetzt betreten. Viel Spaß! 🎮",
            ephemeral=True,
        )
        log.info(f"{interaction.user} ({interaction.user.id}) whitelistet als {name} ({platform})")

        # Log-Channel
        embed = discord.Embed(title="✅ Whitelist Beitritt", color=0x2ECC71)
        embed.add_field(name="Discord", value=interaction.user.mention, inline=True)
        embed.add_field(name="IGN",     value=f"`{name}`",              inline=True)
        embed.add_field(name="Platform",value=f"{plattform_emoji} {platform.capitalize()}", inline=True)
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.set_footer(text=f"ID: {interaction.user.id}")
        await log_channel(self.bot, embed)


# ── Button View ────────────────────────────────────────────────────────────────

class WhitelistView(discord.ui.View):
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(
        label="Whitelist beitreten",
        style=discord.ButtonStyle.success,
        emoji="⛏️",
        custom_id="whitelist:join",
    )
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(IGNModal(self.bot))


# ── Cog ───────────────────────────────────────────────────────────────────────

class WhitelistCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        bot.add_view(WhitelistView(bot))

    @app_commands.command(name="whitelist-panel", description="Postet das Whitelist-Panel (Admin)")
    @app_commands.checks.has_permissions(administrator=True)
    async def post_panel(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="⛏️  Dem Server beitreten",
            description=(
                "Klicke auf den Button unten, um deinen **Minecraft-Account** "
                "zur Whitelist hinzuzufügen.\n\n"
                "**So funktioniert's:**\n"
                "1. Klicke auf **Whitelist beitreten**\n"
                "2. Gib deinen Minecraft-Username ein\n"
                "3. Wähle deine Platform (`java` oder `bedrock`)\n"
                "4. Du bekommst automatisch die Member-Rolle\n\n"
                "> ⚠️ Stelle sicher, dass du den richtigen Username eingibst!\n"
                "> Der Account muss dir gehören."
            ),
            color=0x2ECC71,
        )
        embed.set_footer(text="Jeder Discord-Account kann nur einen IGN registrieren.")

        target = interaction.channel
        if WHITELIST_CHANNEL_ID:
            ch = interaction.guild.get_channel(WHITELIST_CHANNEL_ID)
            if ch:
                target = ch

        await target.send(embed=embed, view=WhitelistView(self.bot))
        await interaction.response.send_message(
            f"✅ Panel in {target.mention} gepostet.", ephemeral=True
        )

    @app_commands.command(name="whitelist-remove", description="Entfernt jemanden von der Whitelist (Admin)")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(member="Der Discord-User der entfernt werden soll")
    async def remove(self, interaction: discord.Interaction, member: discord.Member):
        async with aiosqlite.connect(DB_PATH) as db:
            row = await (await db.execute(
                "SELECT minecraft_name FROM whitelist WHERE discord_id = ?",
                (member.id,)
            )).fetchone()

        if not row:
            await interaction.response.send_message(
                f"❌ {member.mention} ist nicht in der Whitelist-Datenbank.",
                ephemeral=True,
            )
            return

        ign = row[0]
        try:
            if ign.startswith("."):
                await rcon_command(f"fwhitelist remove {ign}")
            else:
                await rcon_command(f"whitelist remove {ign}")
        except Exception:
            await interaction.response.send_message(
                "❌ RCON-Verbindung fehlgeschlagen.", ephemeral=True
            )
            return

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM whitelist WHERE discord_id = ?", (member.id,))
            await db.commit()

        await interaction.response.send_message(
            f"✅ `{ign}` wurde von der Whitelist entfernt.", ephemeral=True
        )

        # Log-Channel
        embed = discord.Embed(title="🗑️ Whitelist Entfernung", color=0xE74C3C)
        embed.add_field(name="Discord",     value=member.mention,          inline=True)
        embed.add_field(name="IGN",         value=f"`{ign}`",              inline=True)
        embed.add_field(name="Entfernt von",value=interaction.user.mention, inline=True)
        embed.set_footer(text=f"ID: {member.id}")
        await log_channel(self.bot, embed)

    @app_commands.command(name="whitelist-info", description="Zeigt deinen whitelisteten IGN")
    async def info(self, interaction: discord.Interaction):
        async with aiosqlite.connect(DB_PATH) as db:
            row = await (await db.execute(
                "SELECT minecraft_name, whitelisted_at FROM whitelist WHERE discord_id = ?",
                (interaction.user.id,)
            )).fetchone()

        if not row:
            await interaction.response.send_message(
                "❌ Du bist noch nicht whitelistet. Nutze das Whitelist-Panel!",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            f"✅ Du bist als **`{row[0]}`** whitelistet (seit {row[1][:10]}).",
            ephemeral=True,
        )


async def setup(bot):
    await bot.add_cog(WhitelistCog(bot))
