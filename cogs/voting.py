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

    @discord.ui.button(label="✅  Ja",   style=discord.ButtonStyle.success, custom_id="vote:yes:0", row=0)
    async def yes_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_vote(interaction, "yes")

    @discord.ui.button(label="❌  Nein", style=discord.ButtonStyle.danger,  custom_id="vote:no:0",  row=0)
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
            await interaction.followup.send("⏰ Diese Abstimmung ist bereits beendet.", ephemeral=True)
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
            f"{'✅' if choice == 'yes' else '❌'} Stimme gezählt!\n"
            f"**Aktuell:** ✅ {yes} ({yes_pct}%) · ❌ {no} ({100 - yes_pct}%)",
            ephemeral=True,
        )


# ── Cog ───────────────────────────────────────────────────────────────────────

class VotingCog(commands.Cog):
    vote_group = app_commands.Group(name="vote", description="Abstimmungen erstellen und verwalten")

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @vote_group.command(name="create", description="Startet eine neue Abstimmung")
    @app_commands.describe(
        question="Die Frage der Abstimmung",
        duration_hours="Wie lange läuft die Abstimmung (in Stunden, 0 = unbegrenzt)",
    )
    async def create(
        self,
        interaction: discord.Interaction,
        question: str,
        duration_hours: int = 24,
    ):
        ends_at = None
        ends_str = "unbegrenzt"
        if duration_hours > 0:
            end_dt = datetime.utcnow() + timedelta(hours=duration_hours)
            ends_at = end_dt.isoformat()
            ends_str = f"endet <t:{int(end_dt.timestamp())}:R>"

        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                """INSERT INTO votes (guild_id, channel_id, message_id, question, created_by, yes_count, no_count, ends_at)
                   VALUES (?, ?, ?, ?, ?, 0, 0, ?)""",
                (interaction.guild_id, interaction.channel_id, 0, question, interaction.user.id, ends_at),
            )
            vote_id = cursor.lastrowid
            await db.commit()

        embed = discord.Embed(
            title="🗳️  Abstimmung",
            description=f"**{question}**",
            color=0x9B59B6,
        )
        embed.add_field(name="✅ Ja",   value="`0 Stimmen`", inline=True)
        embed.add_field(name="❌ Nein", value="`0 Stimmen`", inline=True)
        embed.add_field(name="⏰ Dauer", value=ends_str,     inline=False)
        embed.set_footer(text=f"Abstimmung #{vote_id} · erstellt von {interaction.user.display_name}")

        view = VoteView(vote_id, self.bot)
        await interaction.response.send_message(embed=embed, view=view)
        msg = await interaction.original_response()

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE votes SET message_id=? WHERE id=?", (msg.id, vote_id))
            await db.commit()

        # Log
        log_embed = discord.Embed(title="🗳️ Abstimmung erstellt", color=0x9B59B6)
        log_embed.add_field(name="Frage",     value=question,                  inline=False)
        log_embed.add_field(name="Erstellt von", value=interaction.user.mention, inline=True)
        log_embed.add_field(name="Dauer",     value=ends_str,                  inline=True)
        log_embed.set_footer(text=f"Abstimmung #{vote_id}")
        await log_channel(self.bot, log_embed)

    @vote_group.command(name="end", description="Beendet eine Abstimmung und zeigt das Ergebnis (Admin)")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(vote_id="Die ID der Abstimmung")
    async def end(self, interaction: discord.Interaction, vote_id: int):
        async with aiosqlite.connect(DB_PATH) as db:
            row = await (await db.execute(
                "SELECT question, yes_count, no_count, active FROM votes WHERE id=? AND guild_id=?",
                (vote_id, interaction.guild_id),
            )).fetchone()

        if not row:
            await interaction.response.send_message("❌ Abstimmung nicht gefunden.", ephemeral=True)
            return

        question, yes, no, active = row
        if not active:
            await interaction.response.send_message("⏰ Diese Abstimmung ist bereits beendet.", ephemeral=True)
            return

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE votes SET active=0 WHERE id=?", (vote_id,))
            await db.commit()

        total = yes + no
        yes_pct = round(yes / total * 100) if total else 0
        winner = "✅ Ja gewinnt!" if yes > no else ("❌ Nein gewinnt!" if no > yes else "🤝 Unentschieden!")

        embed = discord.Embed(
            title="🗳️  Abstimmung beendet",
            description=f"**{question}**\n\n{winner}",
            color=0x2ECC71 if yes >= no else 0xE74C3C,
        )
        embed.add_field(name="✅ Ja",   value=f"`{yes} Stimmen ({yes_pct}%)`",       inline=True)
        embed.add_field(name="❌ Nein", value=f"`{no} Stimmen ({100 - yes_pct}%)`",  inline=True)
        embed.set_footer(text=f"Gesamt: {total} Stimmen · Abstimmung #{vote_id}")
        await interaction.response.send_message(embed=embed)

        # Log
        log_embed = discord.Embed(title="🗳️ Abstimmung beendet", color=0x95A5A6)
        log_embed.add_field(name="Frage",       value=question,                  inline=False)
        log_embed.add_field(name="Ergebnis",    value=winner,                    inline=True)
        log_embed.add_field(name="Beendet von", value=interaction.user.mention,  inline=True)
        log_embed.set_footer(text=f"Abstimmung #{vote_id} · {total} Stimmen")
        await log_channel(self.bot, log_embed)


async def setup(bot):
    await bot.add_cog(VotingCog(bot))
