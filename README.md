# Minecraft Discord Bot

A Discord bot for managing a Minecraft SMP server hosted on [PebbleHost](https://pebblehost.com/minecraft). Built for our friend group's SMP world — handles whitelisting, live server status, coordinate sharing, polls, and team management, all through slash commands.

---

## Features

| Module | Description |
|---|---|
| **Whitelist** | Players can whitelist themselves via a modal (Java & Bedrock supported) |
| **Status** | Live server status with player count via slash command |
| **Admin** | Remove whitelist entries, view the list, run RCON commands from Discord |
| **Coordinates** | Save, list, and delete personal coordinates per dimension |
| **Voting** | Create polls with an optional end time and live results |
| **Teams** | Create, join, leave, modify, and disband Minecraft scoreboard teams |

---

## Requirements

- Python 3.12+
- A Minecraft server with RCON enabled (e.g. hosted on [PebbleHost](https://pebblehost.com/minecraft))
- A Discord bot account ([Discord Developer Portal](https://discord.com/developers/applications))
- Optional: Docker & Docker Compose

---

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/leoapplecool/minecraft-discord-bot.git
cd minecraft-discord-bot
```

### 2. Install dependencies

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configuration

Copy `.env.example` to `.env` and fill in all values:

```bash
cp .env.example .env
```

```env
DISCORD_TOKEN=...           # Your bot token
GUILD_ID=...                # Discord server ID
MEMBER_ROLE_ID=...          # Role assigned after whitelisting
ADMIN_ROLE_ID=...           # Role with bot admin permissions
WHITELIST_CHANNEL_ID=...    # Channel where the whitelist panel is posted
LOG_CHANNEL_ID=...          # Channel for bot action logs

RCON_HOST=...               # Minecraft server IP
RCON_PORT=25575             # RCON port (see PebbleHost RCON tab)
RCON_PASSWORD=...           # RCON password

MC_HOST=...                 # Minecraft server IP
MC_PORT=25565               # Minecraft port
MC_MAX_PLAYERS=20
```

### 4. Run the bot

```bash
python bot.py
```

---

## Configuring RCON (PebbleHost)

RCON lets the bot send Minecraft commands directly to the server (e.g. `whitelist add`, `ban`, `say`).

### Enable RCON on PebbleHost:

1. Open the [PebbleHost Game Panel](https://panel.pebblehost.com)
2. Select your server
3. Go to **Configuration → Startup**
4. Set `ENABLE_RCON` to `true`
5. Note down the **RCON Port** and set a secure **RCON Password**
6. Restart your server

> Alternatively, edit `server.properties` directly:
> ```properties
> enable-rcon=true
> rcon.port=25575
> rcon.password=your_secure_password
> ```

### Add to `.env`:

```env
RCON_HOST=your.server.ip
RCON_PORT=25575           # The RCON port — NOT the player join port
RCON_PASSWORD=your_password
```

---

## Setting up the Discord Bot

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new Application → **Bot** → copy the token → paste into `.env`
3. Under **Privileged Gateway Intents**, enable:
   - `SERVER MEMBERS INTENT`
   - `MESSAGE CONTENT INTENT`
4. Invite the bot to your server via OAuth2 → URL Generator:
   - Scopes: `bot`, `applications.commands`
   - Permissions: `Manage Roles`, `Send Messages`, `Read Message History`, `Embed Links`

---

## Slash Commands

### Whitelist
| Command | Description |
|---|---|
| `/whitelist-panel` | Posts the whitelist button panel (admin only) |
| `/whitelist-remove <user>` | Removes a player from the whitelist |
| `/whitelist-info` | Shows your whitelisted IGN |

Players click the button and fill in a modal with their Minecraft username and platform (Java/Bedrock).

### Status
| Command | Description |
|---|---|
| `/online` | Shows who is currently online with Discord mentions |
| `/serverstatus` | Shows full server status (players, ping, MOTD) |

### Admin *(admin role required)*
| Command | Description |
|---|---|
| `/rcon panel` | Opens a quick-action panel (time, weather, save, list) |
| `/rcon cmd <command>` | Runs any RCON command on the server |
| `/rcon kick <ign> [reason]` | Kicks a player |
| `/rcon ban <ign> [reason]` | Bans a player |
| `/rcon announce <message>` | Broadcasts a message in-game via `say` |

### Coordinates
| Command | Description |
|---|---|
| `/coords add <name> <x> <y> <z> [dimension]` | Save a coordinate |
| `/coords list` | List your saved coordinates |
| `/coords get <name>` | Look up a specific coordinate |
| `/coords delete <name>` | Delete a coordinate |
| `/coords share <name>` | Share a coordinate publicly in the channel |

### Voting
| Command | Description |
|---|---|
| `/vote create <question> [duration_hours]` | Create a new poll |
| `/vote end <id>` | Manually end a poll (admin only) |

### Teams
| Command | Description |
|---|---|
| `/team add <name> [options...]` | Create a Minecraft scoreboard team |
| `/team remove <name>` | Delete your own team |
| `/team join <name>` | Join a team |
| `/team leave` | Leave your current team |
| `/team modify <name> [options...]` | Change your team's settings |
| `/team list` | List all active teams with members |

---

## Docker

```bash
# Start
docker compose up -d

# View logs
docker compose logs -f

# Stop
docker compose down
```

The database is stored in `./data/bot.db` and persists across container restarts.

---

## Project Structure

```
.
├── bot.py              # Entry point
├── config.py           # Config loaded from .env
├── database.py         # SQLite database initialization
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env.example        # Template — never commit the actual .env
├── cogs/
│   ├── whitelist.py    # Whitelist system
│   ├── status.py       # Server status
│   ├── admin.py        # Admin commands
│   ├── coords.py       # Coordinate storage
│   ├── voting.py       # Polls
│   └── team.py         # Minecraft team management
├── utils/
│   ├── rcon.py         # Raw TCP RCON client
│   └── logger.py       # Discord log channel helper
└── data/
    └── bot.db          # SQLite database (auto-generated, not in repo)
```

---

## Notes

This bot was built for a private SMP world shared between friends. Feel free to fork it and adapt it for your own server.

---

