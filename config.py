import os
from dotenv import load_dotenv

load_dotenv()

# ── Discord ────────────────────────────────────────────────────────────────────
DISCORD_TOKEN        = os.getenv("DISCORD_TOKEN")
GUILD_ID             = int(os.getenv("GUILD_ID",             "0"))
MEMBER_ROLE_ID       = int(os.getenv("MEMBER_ROLE_ID",       "0"))
WHITELIST_CHANNEL_ID = int(os.getenv("WHITELIST_CHANNEL_ID", "0"))
LOG_CHANNEL_ID       = int(os.getenv("LOG_CHANNEL_ID",       "0"))
ADMIN_ROLE_ID        = int(os.getenv("ADMIN_ROLE_ID",        "0"))

# ── Minecraft RCON ─────────────────────────────────────────────────────────────
RCON_HOST     = os.getenv("RCON_HOST",     "your.server.com")
RCON_PORT     = int(os.getenv("RCON_PORT", "25575"))
RCON_PASSWORD = os.getenv("RCON_PASSWORD", "")

# ── Minecraft Query (for player count) ────────────────────────────────────────
MC_HOST        = os.getenv("MC_HOST",        "your.server.com")
MC_PORT        = int(os.getenv("MC_PORT",    "25565"))
MC_MAX_PLAYERS = int(os.getenv("MC_MAX_PLAYERS", "20"))

# ── Database ───────────────────────────────────────────────────────────────────
DB_PATH = os.getenv("DB_PATH", "data/bot.db")
