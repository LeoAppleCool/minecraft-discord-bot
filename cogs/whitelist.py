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
        label="Your Minecraft Username (IGN)",
        placeholder="e.g. Notch  |  Bedrock: .Notch (dot is added automatically)",
        min_length=3,
        max_length=17,
        style=discord.TextStyle.short,
    )

    platform = discord.ui.TextInput(
        label="Platform (java / bedrock)",
        placeholder="java  or  bedrock",
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
                "❌ Platform must be `java` or `bedrock`.", ephemeral=True
            )
            return

        if platform == "bedrock":
            if not raw_name.startswith("."):
                raw_name = f".{raw_name}"
            name_check = raw_name[1:]
            if not re.match(r"^[a-zA-Z0-9_ ]{3,16}$", name_check):
                await interaction.followup.send(
                    "❌ Invalid Bedrock username!", ephemeral=True
                )
                return
        else:
            if not IGN_REGEX.match(raw_name):
                await interaction.followup.send(
                    "❌ Invalid Java username! Only letters, numbers and `_` allowed (3–16 characters).",
                    ephemeral=True,
                )
                return

        name = raw_name

        # Already whitelisted?
        async with aiosqlite.connect(DB_PATH) as db:
            row = await (await db.execute(
                "SELECT minecraft_name FROM whitelist WHERE discord_id = ?",
                (interaction.user.id,)
            )).fetchone()

        if row:
            await interaction.followup.send(
                f"⚠️ You are already whitelisted as `{row[0]}`. "
                "Contact an admin to change your IGN.",
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
                "❌ Could not connect to the Minecraft server. Please try again later.",
                ephemeral=True,
            )
            return

        if "already" in response.lower():
            await interaction.followup.send(
                f"⚠️ `{name}` is already on the whitelist. If that's your account, "
                "contact an admin.",
                ephemeral=True,
            )
            return

        # Save to DB
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO whitelist (discord_id, minecraft_name) VALUES (?, ?)",
                (interaction.user.id, name),
            )
            await db.commit()

        # Set nickname
        try:
            base = interaction.user.display_name.split(" (")[0]
            await interaction.user.edit(nick=f"{base} ({name})"[:32])
        except discord.Forbidden:
            pass

        # Assign member role
        guild = interaction.guild
        if guild and MEMBER_ROLE_ID:
            role = guild.get_role(MEMBER_ROLE_ID)
            if role:
                try:
                    await interaction.user.add_roles(role, reason="Joined whitelist")
                except discord.Forbidden:
                    pass

        platform_emoji = "📱" if platform == "bedrock" else "💻"
        await interaction.followup.send(
            f"✅ {platform_emoji} **{name}** has been added to the whitelist!\n"
            "You can now join the server. Have fun! 🎮",
            ephemeral=True,
        )
        log.info(f"{interaction.user} ({interaction.user.id}) whitelisted as {name} ({platform})")

        # Log channel
        embed = discord.Embed(title="✅ Whitelist Join", color=0x2ECC71)
        embed.add_field(name="Discord",  value=interaction.user.mention,                        inline=True)
        embed.add_field(name="IGN",      value=f"`{name}`",                                     inline=True)
        embed.add_field(name="Platform", value=f"{platform_emoji} {platform.capitalize()}",     inline=True)
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.set_footer(text=f"ID: {interaction.user.id}")
        await log_channel(self.bot, embed)


# ── Button View ────────────────────────────────────────────────────────────────

class WhitelistView(discord.ui.View):
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(
        label="Join Whitelist",
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

    @app_commands.command(name="whitelist-panel", description="Posts the whitelist panel (admin only)")
    @app_commands.checks.has_permissions(administrator=True)
    async def post_panel(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="⛏️  Join the Server",
            description=(
                "Click the button below to add your **Minecraft account** to the whitelist.\n\n"
                "**How it works:**\n"
                "1. Click **Join Whitelist**\n"
                "2. Enter your Minecraft username\n"
                "3. Select your platform (`java` or `bedrock`)\n"
                "4. You'll automatically receive the Member role\n\n"
                "> ⚠️ Make sure you enter the correct username!\n"
                "> The account must belong to you."
            ),
            color=0x2ECC71,
        )
        embed.set_footer(text="Each Discord account can only register one IGN.")

        target = interaction.channel
        if WHITELIST_CHANNEL_ID:
            ch = interaction.guild.get_channel(WHITELIST_CHANNEL_ID)
            if ch:
                target = ch

        await target.send(embed=embed, view=WhitelistView(self.bot))
        await interaction.response.send_message(
            f"✅ Panel posted in {target.mention}.", ephemeral=True
        )

    @app_commands.command(name="whitelist-remove", description="Removes someone from the whitelist (admin only)")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(member="The Discord user to remove")
    async def remove(self, interaction: discord.Interaction, member: discord.Member):
        async with aiosqlite.connect(DB_PATH) as db:
            row = await (await db.execute(
                "SELECT minecraft_name FROM whitelist WHERE discord_id = ?",
                (member.id,)
            )).fetchone()

        if not row:
            await interaction.response.send_message(
                f"❌ {member.mention} is not in the whitelist database.",
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
                "❌ RCON connection failed.", ephemeral=True
            )
            return

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM whitelist WHERE discord_id = ?", (member.id,))
            await db.commit()

        await interaction.response.send_message(
            f"✅ `{ign}` has been removed from the whitelist.", ephemeral=True
        )

        # Log channel
        embed = discord.Embed(title="🗑️ Whitelist Removal", color=0xE74C3C)
        embed.add_field(name="Discord",     value=member.mention,           inline=True)
        embed.add_field(name="IGN",         value=f"`{ign}`",               inline=True)
        embed.add_field(name="Removed by",  value=interaction.user.mention, inline=True)
        embed.set_footer(text=f"ID: {member.id}")
        await log_channel(self.bot, embed)

    @app_commands.command(name="whitelist-info", description="Shows your whitelisted IGN")
    async def info(self, interaction: discord.Interaction):
        async with aiosqlite.connect(DB_PATH) as db:
            row = await (await db.execute(
                "SELECT minecraft_name, whitelisted_at FROM whitelist WHERE discord_id = ?",
                (interaction.user.id,)
            )).fetchone()

        if not row:
            await interaction.response.send_message(
                "❌ You are not whitelisted yet. Use the whitelist panel!",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            f"✅ You are whitelisted as **`{row[0]}`** (since {row[1][:10]}).",
            ephemeral=True,
        )


async def setup(bot):
    await bot.add_cog(WhitelistCog(bot))
