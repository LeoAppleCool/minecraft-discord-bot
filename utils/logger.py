import discord
from config import LOG_CHANNEL_ID


async def log(bot: discord.Client, embed: discord.Embed):
    """Sendet ein Embed in den Log-Channel."""
    if not LOG_CHANNEL_ID:
        return
    channel = bot.get_channel(LOG_CHANNEL_ID)
    if channel:
        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            pass
