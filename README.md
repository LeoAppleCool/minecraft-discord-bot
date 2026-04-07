# Minecraft Discord Bot

Ein Discord-Bot zur Verwaltung eines Minecraft-Servers (gehostet auf [PebbleHost](https://pebblehost.com/minecraft)) mit Whitelist-Management, Server-Status, Koordinatensystem, Abstimmungen und Team-Verwaltung – alles über Slash Commands.

---

## Features

| Modul | Beschreibung |
|---|---|
| **Whitelist** | Spieler können sich selbst per Modal whitelisten (Java & Bedrock) |
| **Status** | Live Server-Status mit Spieleranzahl per Slash Command |
| **Admin** | Whitelist entfernen, Liste anzeigen, RCON-Befehle direkt aus Discord |
| **Koordinaten** | Persönliche Koordinaten speichern, auflisten, löschen |
| **Voting** | Abstimmungen erstellen mit Ablaufzeit und Live-Ergebnis |
| **Teams** | Teams erstellen, beitreten, verlassen, auflösen |

---

## Voraussetzungen

- Python 3.12+
- Einen Minecraft-Server mit aktiviertem RCON (z.B. bei [PebbleHost](https://pebblehost.com/minecraft))
- Einen Discord-Bot-Account ([Discord Developer Portal](https://discord.com/developers/applications))
- Optional: Docker & Docker Compose

---

## Setup

### 1. Repository klonen

```bash
git clone https://github.com/leoapplecool/minecraft-discord-bot.git
cd minecraft-discord-bot
```

### 2. Abhängigkeiten installieren

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Konfiguration

Kopiere `.env.example` zu `.env` und fülle alle Werte aus:

```bash
cp .env.example .env
```

```env
DISCORD_TOKEN=...           # Dein Bot-Token
GUILD_ID=...                # Server-ID
MEMBER_ROLE_ID=...          # Rolle, die nach Whitelist vergeben wird
ADMIN_ROLE_ID=...           # Rolle mit Admin-Rechten für den Bot
WHITELIST_CHANNEL_ID=...    # Channel mit dem Whitelist-Button
LOG_CHANNEL_ID=...          # Channel für Bot-Logs

RCON_HOST=...               # IP des Minecraft-Servers
RCON_PORT=25575             # RCON-Port (PebbleHost: siehe RCON-Tab)
RCON_PASSWORD=...           # RCON-Passwort

MC_HOST=...                 # IP des Minecraft-Servers
MC_PORT=25565               # Minecraft-Port
MC_MAX_PLAYERS=20
```

### 4. Bot starten

```bash
python bot.py
```

---

## RCON konfigurieren (PebbleHost)

RCON erlaubt es, Minecraft-Befehle direkt aus dem Bot zu senden (z.B. `/whitelist add`).

### Auf PebbleHost aktivieren:

1. Öffne das [PebbleHost Game Panel](https://panel.pebblehost.com)
2. Wähle deinen Server aus
3. Gehe zu **Configuration → Startup**
4. Setze `ENABLE_RCON` auf `true`
5. Notiere dir **RCON Port** und setze ein sicheres **RCON Password**
6. Starte den Server neu

> Alternativ direkt in der `server.properties`:
> ```properties
> enable-rcon=true
> rcon.port=25575
> rcon.password=dein_sicheres_passwort
> ```

### In der `.env` eintragen:

```env
RCON_HOST=deine.server.ip
RCON_PORT=25575           # Der RCON-Port aus dem Panel (nicht der Spieler-Port!)
RCON_PASSWORD=dein_passwort
```

---

## Discord-Bot einrichten

1. Gehe zum [Discord Developer Portal](https://discord.com/developers/applications)
2. Erstelle eine neue Application → **Bot** → Token kopieren → in `.env` eintragen
3. Unter **Privileged Gateway Intents** aktiviere:
   - `SERVER MEMBERS INTENT`
   - `MESSAGE CONTENT INTENT`
4. Lade den Bot auf deinen Server ein (OAuth2 → URL Generator):
   - Scopes: `bot`, `applications.commands`
   - Permissions: `Manage Roles`, `Send Messages`, `Read Message History`, `Embed Links`

---

## Slash Commands

### Whitelist
| Command | Beschreibung |
|---|---|
| `/whitelist-setup` | Sendet den Whitelist-Button in den konfigurierten Channel |

Spieler klicken den Button und füllen ein Modal mit ihrem Minecraft-Namen und Platform (Java/Bedrock) aus.

### Status
| Command | Beschreibung |
|---|---|
| `/status` | Zeigt Live-Status des Servers (Online/Offline, Spieler) |

### Admin *(nur Admins)*
| Command | Beschreibung |
|---|---|
| `/whitelist-remove <user>` | Entfernt Spieler von der Whitelist und nimmt Rolle weg |
| `/whitelist-list` | Zeigt alle gewhitelisteten Spieler |
| `/rcon <command>` | Führt beliebigen RCON-Befehl auf dem Server aus |

### Koordinaten
| Command | Beschreibung |
|---|---|
| `/coord-add <name> <x> <y> <z> [dimension]` | Koordinate speichern |
| `/coord-list` | Eigene Koordinaten anzeigen |
| `/coord-delete <name>` | Koordinate löschen |

### Voting
| Command | Beschreibung |
|---|---|
| `/vote-create <frage> [minuten]` | Neue Abstimmung erstellen |
| `/vote-end <id>` | Abstimmung manuell beenden |

### Teams
| Command | Beschreibung |
|---|---|
| `/team-create <name>` | Team erstellen |
| `/team-join <name>` | Team beitreten |
| `/team-leave` | Team verlassen |
| `/team-list` | Alle Teams anzeigen |
| `/team-disband` | Eigenes Team auflösen |

---

## Docker

```bash
# Starten
docker compose up -d

# Logs anzeigen
docker compose logs -f

# Stoppen
docker compose down
```

Die Datenbank wird in `./data/bot.db` gespeichert und übersteht Container-Neustarts.

---

## Projektstruktur

```
.
├── bot.py              # Einstiegspunkt
├── config.py           # Konfiguration aus .env
├── database.py         # Datenbankinitialisierung (SQLite)
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env.example        # Vorlage – .env selbst NIEMALS committen
├── cogs/
│   ├── whitelist.py    # Whitelist-System
│   ├── status.py       # Server-Status
│   ├── admin.py        # Admin-Befehle
│   ├── coords.py       # Koordinaten
│   ├── voting.py       # Abstimmungen
│   └── team.py         # Teams
├── utils/
│   ├── rcon.py         # RCON-Client (raw TCP, kein externes Paket)
│   └── logger.py       # Discord-Log-Channel Helper
└── data/
    └── bot.db          # SQLite-Datenbank (auto-generiert, nicht im Repo)
```

---

## Lizenz

MIT
