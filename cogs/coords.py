import discord
from discord.ext import commands
from discord import app_commands
import logging
import aiosqlite
from config import DB_PATH

log = logging.getLogger("coords")

DIMENSIONS = ["overworld", "nether", "end"]
DIM_EMOJI = {"overworld": "🌍", "nether": "🔥", "end": "🌌"}


class CoordsCog(commands.Cog):
    coords_group = app_commands.Group(
        name="coords", description="Koordinaten speichern und abrufen"
    )

    @coords_group.command(name="add", description="Speichert eine Koordinate")
    @app_commands.describe(
        name="Name des Ortes (z.B. 'Base', 'Mine')",
        x="X-Koordinate",
        y="Y-Koordinate",
        z="Z-Koordinate",
        dimension="Dimension",
    )
    @app_commands.choices(dimension=[
        app_commands.Choice(name="🌍 Overworld", value="overworld"),
        app_commands.Choice(name="🔥 Nether",    value="nether"),
        app_commands.Choice(name="🌌 End",       value="end"),
    ])
    async def add(
        self,
        interaction: discord.Interaction,
        name: str,
        x: int,
        y: int,
        z: int,
        dimension: str = "overworld",
    ):
        if len(name) > 32:
            await interaction.response.send_message(
                "❌ Name zu lang (max 32 Zeichen).", ephemeral=True
            )
            return

        async with aiosqlite.connect(DB_PATH) as db:
            try:
                await db.execute(
                    """
                    INSERT INTO coords (guild_id, user_id, name, x, y, z, dimension)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(guild_id, user_id, name)
                    DO UPDATE SET x=excluded.x, y=excluded.y, z=excluded.z,
                                  dimension=excluded.dimension
                    """,
                    (interaction.guild_id, interaction.user.id, name, x, y, z, dimension),
                )
                await db.commit()
            except Exception as e:
                await interaction.response.send_message(f"❌ Datenbankfehler: `{e}`", ephemeral=True)
                return

        emoji = DIM_EMOJI.get(dimension, "📍")
        await interaction.response.send_message(
            f"{emoji} **{name}** gespeichert: `{x}, {y}, {z}` ({dimension})",
            ephemeral=True,
        )

    @coords_group.command(name="list", description="Zeigt alle deine gespeicherten Koordinaten")
    async def list_coords(self, interaction: discord.Interaction):
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT name, x, y, z, dimension FROM coords WHERE guild_id=? AND user_id=? ORDER BY name",
                (interaction.guild_id, interaction.user.id),
            )
            rows = await cursor.fetchall()

        if not rows:
            await interaction.response.send_message(
                "📭 Du hast noch keine Koordinaten gespeichert. Nutze `/coords add`!",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title=f"📍 Deine Koordinaten ({len(rows)})",
            color=0x3498DB,
        )
        for name, x, y, z, dim in rows:
            emoji = DIM_EMOJI.get(dim, "📍")
            embed.add_field(
                name=f"{emoji} {name}",
                value=f"`{x}, {y}, {z}`\n_{dim}_",
                inline=True,
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @coords_group.command(name="get", description="Sucht eine bestimmte Koordinate")
    @app_commands.describe(name="Name des gesuchten Ortes")
    async def get(self, interaction: discord.Interaction, name: str):
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT x, y, z, dimension, created_at FROM coords WHERE guild_id=? AND user_id=? AND name=?",
                (interaction.guild_id, interaction.user.id, name),
            )
            row = await cursor.fetchone()

        if not row:
            await interaction.response.send_message(
                f"❌ Keine Koordinate namens **{name}** gefunden.", ephemeral=True
            )
            return

        x, y, z, dim, created_at = row
        emoji = DIM_EMOJI.get(dim, "📍")
        await interaction.response.send_message(
            f"{emoji} **{name}** — `{x}, {y}, {z}` ({dim})\n_Gespeichert am {created_at[:10]}_",
            ephemeral=True,
        )

    @coords_group.command(name="delete", description="Löscht eine gespeicherte Koordinate")
    @app_commands.describe(name="Name der Koordinate die gelöscht werden soll")
    async def delete(self, interaction: discord.Interaction, name: str):
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "DELETE FROM coords WHERE guild_id=? AND user_id=? AND name=?",
                (interaction.guild_id, interaction.user.id, name),
            )
            await db.commit()
            deleted = cursor.rowcount

        if deleted == 0:
            await interaction.response.send_message(
                f"❌ Keine Koordinate namens **{name}** gefunden.", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"🗑️ **{name}** wurde gelöscht.", ephemeral=True
            )

    @coords_group.command(name="share", description="Teilt eine Koordinate im aktuellen Kanal")
    @app_commands.describe(name="Name der Koordinate die geteilt werden soll")
    async def share(self, interaction: discord.Interaction, name: str):
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT x, y, z, dimension FROM coords WHERE guild_id=? AND user_id=? AND name=?",
                (interaction.guild_id, interaction.user.id, name),
            )
            row = await cursor.fetchone()

        if not row:
            await interaction.response.send_message(
                f"❌ Keine Koordinate namens **{name}** gefunden.", ephemeral=True
            )
            return

        x, y, z, dim = row
        emoji = DIM_EMOJI.get(dim, "📍")
        embed = discord.Embed(
            title=f"{emoji}  {name}",
            description=f"**Koordinaten:** `{x}, {y}, {z}`\n**Dimension:** {dim.capitalize()}",
            color=0x27AE60,
        )
        embed.set_footer(text=f"Geteilt von {interaction.user.display_name}")
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(CoordsCog(bot))
