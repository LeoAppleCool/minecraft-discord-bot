import discord
from discord.ext import commands
from discord import app_commands
import logging
import aiosqlite
from datetime import datetime, timedelta
from config import DB_PATH
from utils.logger import log as log_channel

log = logging.getLogger("voting")


# ── Persistent Vote View ───────────────────────────────────────────────────────

class VoteView(discord.ui.View):
    def __init__(self, vote_id: int, bot: commands.Bot):
        super().__init__(timeout=None)
        self.vote_id = vote_id
        self.bot = bot
        self.yes_button.custom_id = f"vote:yes:{vote_id}"
        self.no_button.custom_id  = f"vote:no:{vote_id}"

    @discord.ui.button(label="✅  Yes", style=discord.ButtonStyle.success, custom_id="vote:yes:0", row=0)
    async def yes_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_vote(interaction, "yes")

    @discord.ui.button(label="❌  No",  style=discord.ButtonStyle.danger,  custom_id="vote:no:0",  row=0)
    async def no_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_vote(interaction, "no")

    async def _handle_vote(self, interaction: discord.Interaction, choice: str):
        await interaction.response.defer(ephemeral=True)

        async with aiosqlite.connect(DB_PATH) as db:
            row = await (await db.execute(
                "SELECT active, yes_count, no_count, question FROM votes WHERE id=?",
                (self.vote_id,)
            )).fetchone()

        if not row or not row[0]:
            await interaction.followup.send("⏰ This poll has already ended.", ephemeral=True)
            return

        async with aiosqlite.connect(DB_PATH) as db:
            col = "yes_count" if choice == "yes" else "no_count"
            await db.execute(f"UPDATE votes SET {col} = {col} + 1 WHERE id=?", (self.vote_id,))
            await db.commit()
            updated = await (await db.execute(
                "SELECT yes_count, no_count FROM votes WHERE id=?", (self.vote_id,)
            )).fetchone()

        yes, no = updated
        total = yes + no
        yes_pct = round(yes / total * 100) if total else 0

        await interaction.followup.send(
            f"{'✅' if choice == 'yes' else '❌'} Vote counted!\n"
            f"**Current:** ✅ {yes} ({yes_pct}%) · ❌ {no} ({100 - yes_pct}%)",
            ephemeral=True,
        )


# ── Cog ───────────────────────────────────────────────────────────────────────

class VotingCog(commands.Cog):
    vote_group = app_commands.Group(name="vote", description="Create and manage polls")

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @vote_group.command(name="create", description="Start a new poll")
    @app_commands.describe(
        question="The poll question",
        duration_hours="How long the poll runs (in hours, 0 = unlimited)",
    )
    async def create(
        self,
        interaction: discord.Interaction,
        question: str,
        duration_hours: int = 24,
    ):
        ends_at = None
        ends_str = "unlimited"
        if duration_hours > 0:
            end_dt = datetime.utcnow() + timedelta(hours=duration_hours)
            ends_at = end_dt.isoformat()
            ends_str = f"ends <t:{int(end_dt.timestamp())}:R>"

        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                """INSERT INTO votes (guild_id, channel_id, message_id, question, created_by, yes_count, no_count, ends_at)
                   VALUES (?, ?, ?, ?, ?, 0, 0, ?)""",
                (interaction.guild_id, interaction.channel_id, 0, question, interaction.user.id, ends_at),
            )
            vote_id = cursor.lastrowid
            await db.commit()

        embed = discord.Embed(
            title="🗳️  Poll",
            description=f"**{question}**",
            color=0x9B59B6,
        )
        embed.add_field(name="✅ Yes",      value="`0 votes`", inline=True)
        embed.add_field(name="❌ No",       value="`0 votes`", inline=True)
        embed.add_field(name="⏰ Duration", value=ends_str,    inline=False)
        embed.set_footer(text=f"Poll #{vote_id} · created by {interaction.user.display_name}")

        view = VoteView(vote_id, self.bot)
        await interaction.response.send_message(embed=embed, view=view)
        msg = await interaction.original_response()

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE votes SET message_id=? WHERE id=?", (msg.id, vote_id))
            await db.commit()

        log_embed = discord.Embed(title="🗳️ Poll Created", color=0x9B59B6)
        log_embed.add_field(name="Question",   value=question,                  inline=False)
        log_embed.add_field(name="Created by", value=interaction.user.mention,  inline=True)
        log_embed.add_field(name="Duration",   value=ends_str,                  inline=True)
        log_embed.set_footer(text=f"Poll #{vote_id}")
        await log_channel(self.bot, log_embed)

    @vote_group.command(name="end", description="End a poll and show the result (admin only)")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(vote_id="The poll ID")
    async def end(self, interaction: discord.Interaction, vote_id: int):
        async with aiosqlite.connect(DB_PATH) as db:
            row = await (await db.execute(
                "SELECT question, yes_count, no_count, active FROM votes WHERE id=? AND guild_id=?",
                (vote_id, interaction.guild_id),
            )).fetchone()

        if not row:
            await interaction.response.send_message("❌ Poll not found.", ephemeral=True)
            return

        question, yes, no, active = row
        if not active:
            await interaction.response.send_message("⏰ This poll has already ended.", ephemeral=True)
            return

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE votes SET active=0 WHERE id=?", (vote_id,))
            await db.commit()

        total = yes + no
        yes_pct = round(yes / total * 100) if total else 0
        winner = "✅ Yes wins!" if yes > no else ("❌ No wins!" if no > yes else "🤝 Tie!")

        embed = discord.Embed(
            title="🗳️  Poll Ended",
            description=f"**{question}**\n\n{winner}",
            color=0x2ECC71 if yes >= no else 0xE74C3C,
        )
        embed.add_field(name="✅ Yes", value=f"`{yes} votes ({yes_pct}%)`",       inline=True)
        embed.add_field(name="❌ No",  value=f"`{no} votes ({100 - yes_pct}%)`",  inline=True)
        embed.set_footer(text=f"Total: {total} votes · Poll #{vote_id}")
        await interaction.response.send_message(embed=embed)

        log_embed = discord.Embed(title="🗳️ Poll Ended", color=0x95A5A6)
        log_embed.add_field(name="Question", value=question,                  inline=False)
        log_embed.add_field(name="Result",   value=winner,                    inline=True)
        log_embed.add_field(name="Ended by", value=interaction.user.mention,  inline=True)
        log_embed.set_footer(text=f"Poll #{vote_id} · {total} votes")
        await log_channel(self.bot, log_embed)


async def setup(bot):
    await bot.add_cog(VotingCog(bot))
