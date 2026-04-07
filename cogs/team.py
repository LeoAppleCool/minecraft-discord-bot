import asyncio
import re
import logging
import aiosqlite
import discord
from discord.ext import commands
from discord import app_commands
from config import DB_PATH
from utils.rcon import rcon_command
from utils.logger import log as log_channel

log = logging.getLogger("team")

TEAM_NAME_RE    = re.compile(r"^[a-zA-Z0-9_\-]{1,16}$")
MC_COLOR_CODE   = re.compile(r"§[0-9a-fk-orA-FK-OR]")  # strips §4, §a, §r etc.

MC_COLORS = [
    "aqua", "black", "blue", "dark_aqua", "dark_blue", "dark_gray",
    "dark_green", "dark_purple", "dark_red", "gold", "gray", "green",
    "light_purple", "red", "white", "yellow", "reset",
]

VISIBILITY_OPTIONS = ["always", "hideForOtherTeams", "hideForOwnTeam", "never"]
COLLISION_OPTIONS  = ["always", "pushOtherTeams", "pushOwnTeam", "never"]

COLOR_HEX = {
    "aqua": 0x55FFFF, "black": 0x1C1C1C, "blue": 0x5555FF,
    "dark_aqua": 0x00AAAA, "dark_blue": 0x0000AA, "dark_gray": 0x555555,
    "dark_green": 0x00AA00, "dark_purple": 0xAA00AA, "dark_red": 0xAA0000,
    "gold": 0xFFAA00, "gray": 0xAAAAAA, "green": 0x55FF55,
    "light_purple": 0xFF55FF, "red": 0xFF5555, "white": 0xFFFFFF,
    "yellow": 0xFFFF55, "reset": 0x95A5A6,
}


# ── Helpers ───────────────────────────────────────────────────────────────────

async def get_own_ign(discord_id: int) -> str | None:
    """Returns the whitelisted Minecraft IGN for a Discord user, or None."""
    async with aiosqlite.connect(DB_PATH) as db:
        row = await (await db.execute(
            "SELECT minecraft_name FROM whitelist WHERE discord_id = ?",
            (discord_id,),
        )).fetchone()
    return row[0] if row else None


def _strip_colors(text: str) -> str:
    """Removes Minecraft §-color codes from a string."""
    return MC_COLOR_CODE.sub("", text)


async def get_all_db_teams() -> list[tuple[str, int]]:
    """Returns all (team_name, creator_id) rows from the DB."""
    async with aiosqlite.connect(DB_PATH) as db:
        rows = await (await db.execute(
            "SELECT team_name, creator_id FROM teams"
        )).fetchall()
    return rows


async def get_creator_teams(discord_id: int) -> list[str]:
    """Returns team names from the DB that were created by this Discord user."""
    async with aiosqlite.connect(DB_PATH) as db:
        rows = await (await db.execute(
            "SELECT team_name FROM teams WHERE creator_id = ?", (discord_id,)
        )).fetchall()
    return [r[0] for r in rows]


async def fetch_team_members(team_name: str) -> list[str]:
    """Returns member list of a MC team using the internal team name."""
    try:
        resp = _strip_colors(await rcon_command(f"team list {team_name}"))
        # Output: "Team [displayName] has N members: player1, player2"
        if ":" in resp:
            raw = resp.split(":", 1)[1]
            return [m.strip() for m in raw.split(",") if m.strip()]
    except Exception:
        pass
    return []


def _escape_text(text: str) -> str:
    """Escapes double-quotes and backslashes for use inside MC JSON text."""
    return text.replace("\\", "\\\\").replace('"', '\\"')


def _json_text(text: str) -> str:
    return f'{{"text":"{_escape_text(text)}"}}'


# ── Cog ───────────────────────────────────────────────────────────────────────

class TeamCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    team_group = app_commands.Group(
        name="team",
        description="🏷️ Minecraft Teams verwalten",
    )

    # ─────────────────────────────────────────────────────────────────────────
    # /team add
    # ─────────────────────────────────────────────────────────────────────────

    @team_group.command(name="add", description="Erstellt ein neues Minecraft-Team")
    @app_commands.describe(
        name            = "Teamname (1–16 Zeichen, keine Leerzeichen)",
        display_name    = "Anzeigename im Spiel (optional)",
        color           = "Teamfarbe",
        friendly_fire   = "Dürfen Teammitglieder sich gegenseitig Schaden zufügen?",
        see_friendly_invisibles = "Können unsichtbare Teammitglieder gesehen werden?",
        nametag_visibility      = "Wer sieht den Namens-Tag von Teammitgliedern?",
        death_message_visibility= "Wer sieht Todesnachrichten von Teammitgliedern?",
        collision_rule          = "Kollisionsregel mit anderen Spielern",
        prefix = "Text vor dem Spielernamen (max. 16 Zeichen)",
        suffix = "Text nach dem Spielernamen (max. 16 Zeichen)",
    )
    @app_commands.choices(
        color=[app_commands.Choice(name=c, value=c) for c in MC_COLORS],
        friendly_fire=[
            app_commands.Choice(name="✅ Ja — Teammates können sich schaden", value="true"),
            app_commands.Choice(name="❌ Nein — Kein Schaden an Teammates",  value="false"),
        ],
        see_friendly_invisibles=[
            app_commands.Choice(name="✅ Ja — Unsichtbare Teammates sichtbar", value="true"),
            app_commands.Choice(name="❌ Nein — Bleiben unsichtbar",           value="false"),
        ],
        nametag_visibility=[
            app_commands.Choice(name="always — Immer sichtbar",                  value="always"),
            app_commands.Choice(name="hideForOtherTeams — Nur für eigenes Team", value="hideForOtherTeams"),
            app_commands.Choice(name="hideForOwnTeam — Nur für andere Teams",    value="hideForOwnTeam"),
            app_commands.Choice(name="never — Niemals sichtbar",                 value="never"),
        ],
        death_message_visibility=[
            app_commands.Choice(name="always — Alle sehen Todesnachrichten",             value="always"),
            app_commands.Choice(name="hideForOtherTeams — Nur eigenes Team sieht es",    value="hideForOtherTeams"),
            app_commands.Choice(name="hideForOwnTeam — Nur andere Teams sehen es",       value="hideForOwnTeam"),
            app_commands.Choice(name="never — Niemand sieht Todesnachrichten",           value="never"),
        ],
        collision_rule=[
            app_commands.Choice(name="always — Kollision mit allen",               value="always"),
            app_commands.Choice(name="pushOtherTeams — Schiebt andere Teams",      value="pushOtherTeams"),
            app_commands.Choice(name="pushOwnTeam — Schiebt eigene Teammates",     value="pushOwnTeam"),
            app_commands.Choice(name="never — Keine Kollision",                    value="never"),
        ],
    )
    async def team_add(
        self,
        interaction: discord.Interaction,
        name: str,
        display_name: str | None = None,
        color: str | None = None,
        friendly_fire: str | None = None,
        see_friendly_invisibles: str | None = None,
        nametag_visibility: str | None = None,
        death_message_visibility: str | None = None,
        collision_rule: str | None = None,
        prefix: str | None = None,
        suffix: str | None = None,
    ):
        await interaction.response.defer(ephemeral=True)

        # Must be whitelisted
        ign = await get_own_ign(interaction.user.id)
        if not ign:
            await interaction.followup.send(
                "❌ Du musst auf der Whitelist stehen, um ein Team zu erstellen.", ephemeral=True
            )
            return

        # Name validation
        if not TEAM_NAME_RE.match(name):
            await interaction.followup.send(
                "❌ Ungültiger Teamname!\n"
                "Erlaubt: Buchstaben, Zahlen, `_` und `-` · Max. **16 Zeichen** · Keine Leerzeichen.",
                ephemeral=True,
            )
            return

        # Prefix/Suffix length
        if prefix and len(prefix) > 16:
            await interaction.followup.send("❌ Prefix darf maximal **16 Zeichen** lang sein.", ephemeral=True)
            return
        if suffix and len(suffix) > 16:
            await interaction.followup.send("❌ Suffix darf maximal **16 Zeichen** lang sein.", ephemeral=True)
            return

        # One team per player
        existing = await get_creator_teams(interaction.user.id)
        if existing:
            await interaction.followup.send(
                f"❌ Du besitzt bereits Team **`{existing[0]}`**.\n"
                "Du kannst nur ein Team gleichzeitig besitzen. Lösche es zuerst mit `/team remove`.",
                ephemeral=True,
            )
            return

        # Create team via RCON — MC itself tells us if the name is already taken
        try:
            resp = await rcon_command(f"team add {name}")
        except Exception:
            await interaction.followup.send("❌ RCON-Verbindung fehlgeschlagen.", ephemeral=True)
            return

        if "already" in resp.lower():
            await interaction.followup.send(
                f"❌ Ein Team namens `{name}` existiert bereits auf dem Server.", ephemeral=True
            )
            return

        if "created" not in resp.lower():
            await interaction.followup.send(
                f"❌ Team konnte nicht erstellt werden:\n```{resp}```", ephemeral=True
            )
            return

        # Apply optional settings
        modify_tasks = []
        if display_name:
            modify_tasks.append(("displayName", _json_text(display_name)))
        if color:
            modify_tasks.append(("color", color))
        if friendly_fire:
            modify_tasks.append(("friendlyFire", friendly_fire))
        if see_friendly_invisibles:
            modify_tasks.append(("seeFriendlyInvisibles", see_friendly_invisibles))
        if nametag_visibility:
            modify_tasks.append(("nametagVisibility", nametag_visibility))
        if death_message_visibility:
            modify_tasks.append(("deathMessageVisibility", death_message_visibility))
        if collision_rule:
            modify_tasks.append(("collisionRule", collision_rule))
        if prefix:
            modify_tasks.append(("prefix", prefix))
        if suffix:
            modify_tasks.append(("suffix", suffix))

        errors = []
        for option, value in modify_tasks:
            try:
                r = await rcon_command(f"team modify {name} {option} {value}")
                if "error" in r.lower():
                    errors.append(f"`{option}`: {r}")
            except Exception as e:
                errors.append(f"`{option}`: {e}")

        # Persist in DB
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "INSERT OR REPLACE INTO teams (team_name, creator_id) VALUES (?, ?)",
                    (name, interaction.user.id),
                )
                await db.commit()
        except Exception as e:
            log.error(f"DB-Fehler beim Speichern von Team '{name}': {e}")
            await interaction.followup.send(
                f"⚠️ Team wurde in Minecraft erstellt, aber **nicht in der Datenbank gespeichert**!\n"
                f"```{e}```\nBitte starte den Bot neu und versuche es erneut.",
                ephemeral=True,
            )
            return

        # Response embed
        embed = discord.Embed(
            title=f"✅ Team `{name}` erstellt!",
            color=COLOR_HEX.get(color or "", 0x2ECC71),
        )
        embed.add_field(name="👑 Besitzer",  value=interaction.user.mention, inline=True)
        if display_name:
            embed.add_field(name="📛 Anzeigename", value=display_name, inline=True)
        if color:
            embed.add_field(name="🎨 Farbe", value=f"`{color}`", inline=True)

        settings = []
        if friendly_fire:
            settings.append(f"⚔️ Friendly Fire: **{'an' if friendly_fire == 'true' else 'aus'}**")
        if see_friendly_invisibles:
            settings.append(f"👁️ Unsichtbar sehen: **{'an' if see_friendly_invisibles == 'true' else 'aus'}**")
        if nametag_visibility:
            settings.append(f"🏷️ Namens-Tag: **{nametag_visibility}**")
        if death_message_visibility:
            settings.append(f"💀 Todesnachricht: **{death_message_visibility}**")
        if collision_rule:
            settings.append(f"💥 Kollision: **{collision_rule}**")
        if prefix:
            settings.append(f"◀️ Prefix: `{prefix}`")
        if suffix:
            settings.append(f"▶️ Suffix: `{suffix}`")
        if settings:
            embed.add_field(name="⚙️ Einstellungen", value="\n".join(settings), inline=False)
        if errors:
            embed.add_field(name="⚠️ Warnungen", value="\n".join(errors), inline=False)
        embed.set_footer(text="Mit /team join können Spieler deinem Team beitreten.")

        await interaction.followup.send(embed=embed, ephemeral=True)
        log.info(f"{interaction.user} ({interaction.user.id}) erstellte Team '{name}'")

        log_embed = discord.Embed(title="🏷️ Team erstellt", color=0x2ECC71)
        log_embed.add_field(name="Team",        value=f"`{name}`",              inline=True)
        log_embed.add_field(name="Erstellt von", value=interaction.user.mention, inline=True)
        await log_channel(self.bot, log_embed)

    # ─────────────────────────────────────────────────────────────────────────
    # /team remove
    # ─────────────────────────────────────────────────────────────────────────

    @team_group.command(name="remove", description="Löscht dein eigenes Team (inkl. aller Mitglieder)")
    @app_commands.describe(name="Dein Team — nur dein eigenes kann gelöscht werden")
    async def team_remove(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer(ephemeral=True)

        ign = await get_own_ign(interaction.user.id)
        if not ign:
            await interaction.followup.send("❌ Du musst whitelistet sein.", ephemeral=True)
            return

        own_teams = await get_creator_teams(interaction.user.id)
        if name not in own_teams:
            await interaction.followup.send(
                "❌ Du kannst nur dein **eigenes** Team löschen.\n"
                "Nutze `/team list`, um alle Teams anzuzeigen.",
                ephemeral=True,
            )
            return

        try:
            resp = await rcon_command(f"team remove {name}")
        except Exception:
            await interaction.followup.send("❌ RCON-Verbindung fehlgeschlagen.", ephemeral=True)
            return

        # Remove from DB even if MC already removed it
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM teams WHERE team_name = ?", (name,))
            await db.commit()

        await interaction.followup.send(
            f"🗑️ Team **`{name}`** wurde gelöscht.\n"
            f"```{resp or 'Team removed.'}```",
            ephemeral=True,
        )
        log.info(f"{interaction.user} ({interaction.user.id}) löschte Team '{name}'")

        log_embed = discord.Embed(title="🗑️ Team gelöscht", color=0xE74C3C)
        log_embed.add_field(name="Team",        value=f"`{name}`",              inline=True)
        log_embed.add_field(name="Gelöscht von", value=interaction.user.mention, inline=True)
        await log_channel(self.bot, log_embed)

    @team_remove.autocomplete("name")
    async def _autocomplete_own_teams_remove(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        own = await get_creator_teams(interaction.user.id)
        return [
            app_commands.Choice(name=t, value=t)
            for t in sorted(own) if current.lower() in t.lower()
        ][:25]

    # ─────────────────────────────────────────────────────────────────────────
    # /team join
    # ─────────────────────────────────────────────────────────────────────────

    @team_group.command(name="join", description="Tritt einem Team bei (nur du selbst)")
    @app_commands.describe(name="Team dem du beitreten möchtest")
    async def team_join(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer(ephemeral=True)

        ign = await get_own_ign(interaction.user.id)
        if not ign:
            await interaction.followup.send(
                "❌ Du musst auf der Whitelist stehen, um einem Team beizutreten.", ephemeral=True
            )
            return

        ign = ign.strip()

        # Try plain score-holder name first (works online & offline in MC 1.20+)
        try:
            resp = await rcon_command(f"team join {name} {ign}")
        except Exception:
            await interaction.followup.send("❌ RCON-Verbindung fehlgeschlagen.", ephemeral=True)
            return

        resp_clean = _strip_colors(resp).strip()
        resp_lower = resp_clean.lower()

        # Debug: zeige die rohe MC-Antwort falls leer oder fehlerhaft
        if not resp_clean:
            await interaction.followup.send(
                f"❌ Minecraft hat keine Antwort zurückgegeben.\n"
                f"Gesendeter Befehl: `team join {name} {ign}`\n"
                f"Bitte stelle sicher dass du **online** auf dem Server bist!",
                ephemeral=True,
            )
            return

        if "error" in resp_lower or "unknown" in resp_lower or "0" in resp_lower:
            await interaction.followup.send(
                f"❌ Beitreten fehlgeschlagen:\n```{resp_clean}```\n"
                f"IGN: `{ign}` · Team: `{name}`",
                ephemeral=True,
            )
            return

        await interaction.followup.send(
            f"✅ Du (`{ign}`) bist jetzt in Team **`{name}`**!", ephemeral=True
        )
        log.info(f"{interaction.user} ({ign}) ist Team '{name}' beigetreten")

        log_embed = discord.Embed(title="➕ Team beigetreten", color=0x3498DB)
        log_embed.add_field(name="Team",    value=f"`{name}`",                        inline=True)
        log_embed.add_field(name="Spieler", value=f"`{ign}` · {interaction.user.mention}", inline=True)
        await log_channel(self.bot, log_embed)

    @team_join.autocomplete("name")
    async def _autocomplete_all_teams_join(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        # Use DB — these are the real internal team names, not display names
        all_teams = await get_all_db_teams()
        return [
            app_commands.Choice(name=t, value=t)
            for t, _ in sorted(all_teams) if current.lower() in t.lower()
        ][:25]

    # ─────────────────────────────────────────────────────────────────────────
    # /team leave
    # ─────────────────────────────────────────────────────────────────────────

    @team_group.command(name="leave", description="Verlässt dein aktuelles Team (nur du selbst)")
    async def team_leave(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        ign = await get_own_ign(interaction.user.id)
        if not ign:
            await interaction.followup.send("❌ Du musst whitelistet sein.", ephemeral=True)
            return

        try:
            resp = await rcon_command(f"team leave @a[name={ign.strip()}]")
        except Exception:
            await interaction.followup.send("❌ RCON-Verbindung fehlgeschlagen.", ephemeral=True)
            return

        # MC returns an error message if the player wasn't in a team
        if "error" in resp.lower() or "no entity" in resp.lower():
            await interaction.followup.send(
                f"⚠️ Konnte Team nicht verlassen — bist du in einem Team?\n```{resp}```",
                ephemeral=True,
            )
            return

        await interaction.followup.send(
            f"✅ Du (`{ign}`) hast dein Team verlassen.", ephemeral=True
        )
        log.info(f"{interaction.user} ({ign}) hat sein Team verlassen")

        log_embed = discord.Embed(title="➖ Team verlassen", color=0xE67E22)
        log_embed.add_field(name="Spieler", value=f"`{ign}` · {interaction.user.mention}", inline=True)
        await log_channel(self.bot, log_embed)

    # ─────────────────────────────────────────────────────────────────────────
    # /team modify
    # ─────────────────────────────────────────────────────────────────────────

    @team_group.command(name="modify", description="Ändert Einstellungen deines eigenen Teams")
    @app_commands.describe(
        name            = "Dein Team",
        display_name    = "Neuer Anzeigename im Spiel",
        color           = "Neue Teamfarbe",
        friendly_fire   = "Friendly Fire an/aus",
        see_friendly_invisibles = "Unsichtbare Teammates sehen an/aus",
        nametag_visibility      = "Namens-Tag Sichtbarkeit",
        death_message_visibility= "Todesnachricht Sichtbarkeit",
        collision_rule          = "Kollisionsregel",
        prefix = "Text vor dem Spielernamen (max. 16 Zeichen)",
        suffix = "Text nach dem Spielernamen (max. 16 Zeichen)",
    )
    @app_commands.choices(
        color=[app_commands.Choice(name=c, value=c) for c in MC_COLORS],
        friendly_fire=[
            app_commands.Choice(name="✅ An — Teammates können sich schaden",  value="true"),
            app_commands.Choice(name="❌ Aus — Kein Schaden an Teammates",     value="false"),
        ],
        see_friendly_invisibles=[
            app_commands.Choice(name="✅ An — Unsichtbare Teammates sichtbar", value="true"),
            app_commands.Choice(name="❌ Aus — Bleiben unsichtbar",            value="false"),
        ],
        nametag_visibility=[
            app_commands.Choice(name="always — Immer sichtbar",                  value="always"),
            app_commands.Choice(name="hideForOtherTeams — Nur für eigenes Team", value="hideForOtherTeams"),
            app_commands.Choice(name="hideForOwnTeam — Nur für andere Teams",    value="hideForOwnTeam"),
            app_commands.Choice(name="never — Niemals sichtbar",                 value="never"),
        ],
        death_message_visibility=[
            app_commands.Choice(name="always — Alle sehen Todesnachrichten",          value="always"),
            app_commands.Choice(name="hideForOtherTeams — Nur eigenes Team sieht es", value="hideForOtherTeams"),
            app_commands.Choice(name="hideForOwnTeam — Nur andere Teams sehen es",    value="hideForOwnTeam"),
            app_commands.Choice(name="never — Niemand sieht Todesnachrichten",        value="never"),
        ],
        collision_rule=[
            app_commands.Choice(name="always — Kollision mit allen",            value="always"),
            app_commands.Choice(name="pushOtherTeams — Schiebt andere Teams",   value="pushOtherTeams"),
            app_commands.Choice(name="pushOwnTeam — Schiebt eigene Teammates",  value="pushOwnTeam"),
            app_commands.Choice(name="never — Keine Kollision",                 value="never"),
        ],
    )
    async def team_modify(
        self,
        interaction: discord.Interaction,
        name: str,
        display_name: str | None = None,
        color: str | None = None,
        friendly_fire: str | None = None,
        see_friendly_invisibles: str | None = None,
        nametag_visibility: str | None = None,
        death_message_visibility: str | None = None,
        collision_rule: str | None = None,
        prefix: str | None = None,
        suffix: str | None = None,
    ):
        await interaction.response.defer(ephemeral=True)

        ign = await get_own_ign(interaction.user.id)
        if not ign:
            await interaction.followup.send("❌ Du musst whitelistet sein.", ephemeral=True)
            return

        # Ownership check
        own_teams = await get_creator_teams(interaction.user.id)
        if name not in own_teams:
            await interaction.followup.send(
                "❌ Du kannst nur **dein eigenes** Team modifizieren.", ephemeral=True
            )
            return

        if not any([display_name, color, friendly_fire, see_friendly_invisibles,
                    nametag_visibility, death_message_visibility, collision_rule, prefix, suffix]):
            await interaction.followup.send(
                "⚠️ Gib mindestens eine Option an, die du ändern möchtest.", ephemeral=True
            )
            return

        # Prefix/Suffix length
        if prefix and len(prefix) > 16:
            await interaction.followup.send("❌ Prefix darf maximal **16 Zeichen** lang sein.", ephemeral=True)
            return
        if suffix and len(suffix) > 16:
            await interaction.followup.send("❌ Suffix darf maximal **16 Zeichen** lang sein.", ephemeral=True)
            return

        # Build modify tasks: (mc_option, value, human_label)
        tasks: list[tuple[str, str, str]] = []
        if display_name:
            tasks.append(("displayName",           _json_text(display_name),    f"📛 Anzeigename → `{display_name}`"))
        if color:
            tasks.append(("color",                 color,                       f"🎨 Farbe → `{color}`"))
        if friendly_fire:
            label = "an" if friendly_fire == "true" else "aus"
            tasks.append(("friendlyFire",           friendly_fire,               f"⚔️ Friendly Fire → **{label}**"))
        if see_friendly_invisibles:
            label = "an" if see_friendly_invisibles == "true" else "aus"
            tasks.append(("seeFriendlyInvisibles",  see_friendly_invisibles,     f"👁️ Unsichtbar sehen → **{label}**"))
        if nametag_visibility:
            tasks.append(("nametagVisibility",      nametag_visibility,          f"🏷️ Namens-Tag → `{nametag_visibility}`"))
        if death_message_visibility:
            tasks.append(("deathMessageVisibility", death_message_visibility,    f"💀 Todesnachricht → `{death_message_visibility}`"))
        if collision_rule:
            tasks.append(("collisionRule",          collision_rule,              f"💥 Kollision → `{collision_rule}`"))
        if prefix:
            tasks.append(("prefix",  prefix,  f"◀️ Prefix → `{prefix}`"))
        if suffix:
            tasks.append(("suffix",  suffix,  f"▶️ Suffix → `{suffix}`"))

        changes: list[str] = []
        errors:  list[str] = []

        for option, value, human in tasks:
            try:
                r = await rcon_command(f"team modify {name} {option} {value}")
                if "error" in r.lower():
                    errors.append(f"`{option}`: {r}")
                else:
                    changes.append(human)
            except Exception as e:
                errors.append(f"`{option}`: {e}")

        embed = discord.Embed(
            title=f"✏️ Team `{name}` bearbeitet",
            color=COLOR_HEX.get(color or "", 0x9B59B6),
        )
        if changes:
            embed.add_field(name="✅ Geändert", value="\n".join(changes), inline=False)
        if errors:
            embed.add_field(name="❌ Fehler",   value="\n".join(errors),  inline=False)
        if not changes and not errors:
            embed.description = "Keine Änderungen vorgenommen."

        await interaction.followup.send(embed=embed, ephemeral=True)

        if changes:
            log.info(f"{interaction.user} modifizierte Team '{name}': {changes}")
            log_embed = discord.Embed(title="✏️ Team modifiziert", color=0x9B59B6)
            log_embed.add_field(name="Team",       value=f"`{name}`",              inline=True)
            log_embed.add_field(name="Von",        value=interaction.user.mention, inline=True)
            log_embed.add_field(name="Änderungen", value="\n".join(changes),       inline=False)
            await log_channel(self.bot, log_embed)

    @team_modify.autocomplete("name")
    async def _autocomplete_own_teams_modify(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        own = await get_creator_teams(interaction.user.id)
        return [
            app_commands.Choice(name=t, value=t)
            for t in sorted(own) if current.lower() in t.lower()
        ][:25]

    # ─────────────────────────────────────────────────────────────────────────
    # /team list
    # ─────────────────────────────────────────────────────────────────────────

    @team_group.command(name="list", description="Zeigt alle vorhandenen Teams mit Mitgliedern")
    async def team_list(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)

        # Use DB as source of truth — stores the real internal team names
        db_teams = await get_all_db_teams()
        if not db_teams:
            await interaction.followup.send("📋 Es gibt aktuell keine Teams.")
            return

        shown = db_teams[:20]
        # Fetch member lists using internal names (not display names)
        member_lists = await asyncio.gather(*[fetch_team_members(t) for t, _ in shown])

        embed = discord.Embed(
            title=f"🏷️ Minecraft Teams ({len(db_teams)})",
            color=0x1ABC9C,
        )

        for (team_name, creator_id), members in zip(shown, member_lists):
            owner_str  = f"<@{creator_id}>"
            member_str = " · ".join(f"`{m}`" for m in members) if members else "*Keine Mitglieder*"

            embed.add_field(
                name  = f"🏷️ {team_name}",
                value = f"**👑 Besitzer:** {owner_str}\n**👥 Mitglieder:** {member_str}",
                inline= False,
            )

        if len(db_teams) > 20:
            embed.set_footer(text=f"Zeige 20 von {len(db_teams)} Teams.")

        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(TeamCog(bot))
