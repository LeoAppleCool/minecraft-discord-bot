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
        name="coords", description="Save and retrieve coordinates"
    )

    @coords_group.command(name="add", description="Save a coordinate")
    @app_commands.describe(
        name="Location name (e.g. 'Base', 'Mine')",
        x="X coordinate",
        y="Y coordinate",
        z="Z coordinate",
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
                "❌ Name too long (max 32 characters).", ephemeral=True
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
                await interaction.response.send_message(f"❌ Database error: `{e}`", ephemeral=True)
                return

        emoji = DIM_EMOJI.get(dimension, "📍")
        await interaction.response.send_message(
            f"{emoji} **{name}** saved: `{x}, {y}, {z}` ({dimension})",
            ephemeral=True,
        )

    @coords_group.command(name="list", description="List all your saved coordinates")
    async def list_coords(self, interaction: discord.Interaction):
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT name, x, y, z, dimension FROM coords WHERE guild_id=? AND user_id=? ORDER BY name",
                (interaction.guild_id, interaction.user.id),
            )
            rows = await cursor.fetchall()

        if not rows:
            await interaction.response.send_message(
                "📭 You have no saved coordinates yet. Use `/coords add`!",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title=f"📍 Your Coordinates ({len(rows)})",
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

    @coords_group.command(name="get", description="Look up a specific coordinate")
    @app_commands.describe(name="Name of the location to look up")
    async def get(self, interaction: discord.Interaction, name: str):
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT x, y, z, dimension, created_at FROM coords WHERE guild_id=? AND user_id=? AND name=?",
                (interaction.guild_id, interaction.user.id, name),
            )
            row = await cursor.fetchone()

        if not row:
            await interaction.response.send_message(
                f"❌ No coordinate named **{name}** found.", ephemeral=True
            )
            return

        x, y, z, dim, created_at = row
        emoji = DIM_EMOJI.get(dim, "📍")
        await interaction.response.send_message(
            f"{emoji} **{name}** — `{x}, {y}, {z}` ({dim})\n_Saved on {created_at[:10]}_",
            ephemeral=True,
        )

    @coords_group.command(name="delete", description="Delete a saved coordinate")
    @app_commands.describe(name="Name of the coordinate to delete")
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
                f"❌ No coordinate named **{name}** found.", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"🗑️ **{name}** has been deleted.", ephemeral=True
            )

    @coords_group.command(name="share", description="Share a coordinate publicly in the current channel")
    @app_commands.describe(name="Name of the coordinate to share")
    async def share(self, interaction: discord.Interaction, name: str):
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT x, y, z, dimension FROM coords WHERE guild_id=? AND user_id=? AND name=?",
                (interaction.guild_id, interaction.user.id, name),
            )
            row = await cursor.fetchone()

        if not row:
            await interaction.response.send_message(
                f"❌ No coordinate named **{name}** found.", ephemeral=True
            )
            return

        x, y, z, dim = row
        emoji = DIM_EMOJI.get(dim, "📍")
        embed = discord.Embed(
            title=f"{emoji}  {name}",
            description=f"**Coordinates:** `{x}, {y}, {z}`\n**Dimension:** {dim.capitalize()}",
            color=0x27AE60,
        )
        embed.set_footer(text=f"Shared by {interaction.user.display_name}")
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(CoordsCog(bot))
