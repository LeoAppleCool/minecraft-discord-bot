import discord
from discord.ext import commands
import asyncio
import logging
import os
from dotenv import load_dotenv
from database import init_db

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
log = logging.getLogger("MinecraftBot")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True


class MinecraftBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await init_db()
        await self.load_extension("cogs.whitelist")
        await self.load_extension("cogs.status")
        await self.load_extension("cogs.admin")
        await self.load_extension("cogs.coords")
        await self.load_extension("cogs.voting")
        await self.load_extension("cogs.team")
        await self.tree.sync()
        log.info("Alle Cogs geladen & Slash Commands gesynct.")

    async def on_ready(self):
        log.info(f"Eingeloggt als {self.user} (ID: {self.user.id})")


bot = MinecraftBot()

if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise ValueError("DISCORD_TOKEN fehlt in der .env Datei!")
    bot.run(token)
