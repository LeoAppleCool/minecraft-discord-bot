import aiosqlite
import os
from config import DB_PATH


async def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS whitelist (
                discord_id   INTEGER PRIMARY KEY,
                minecraft_name TEXT NOT NULL,
                whitelisted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS coords (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id  INTEGER NOT NULL,
                user_id   INTEGER NOT NULL,
                name      TEXT    NOT NULL,
                x         INTEGER NOT NULL,
                y         INTEGER NOT NULL,
                z         INTEGER NOT NULL,
                dimension TEXT    NOT NULL DEFAULT 'overworld',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(guild_id, user_id, name)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS votes (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id    INTEGER NOT NULL,
                channel_id  INTEGER NOT NULL,
                message_id  INTEGER NOT NULL,
                question    TEXT    NOT NULL,
                created_by  INTEGER NOT NULL,
                yes_count   INTEGER NOT NULL DEFAULT 0,
                no_count    INTEGER NOT NULL DEFAULT 0,
                ends_at     TIMESTAMP,
                active      INTEGER NOT NULL DEFAULT 1,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS teams (
                team_name   TEXT    PRIMARY KEY,
                creator_id  INTEGER NOT NULL,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()
