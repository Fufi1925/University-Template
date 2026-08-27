"""Discord Architect — server templates via Components V2.

Entry point. Run with ``python bot.py`` after setting ``DISCORD_TOKEN``.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import math
import sys
import time
from typing import TYPE_CHECKING

import aiohttp
import discord
from discord.ext import commands

import config
from core.autosetup import AutoSetup
from core.handoff_store import PendingHandoffs, SetupLedger
from core.handshake import Handoff
from core.licence import LicenceClient
from core.premium import PremiumStore
from core.registry import TemplateRegistry
from core.schema import TemplateError
from ui.components import notice
from ui.views import build_start_view

if TYPE_CHECKING:
    from aiohttp.web import AppRunner

logging.basicConfig(
    level=config.LOG_LEVEL,
    format="%(asctime)s │ %(levelname)-7s │ %(name)-20s │ %(message)s",
    datefmt="%H:%M:%S",
)
LOGGER = logging.getLogger("architect")

#: Wie lange jede Präsenz-Variante angezeigt wird (Discord drosselt darunter).
STATUS_INTERVAL = 15

__all__ = ["ArchitectBot"]


class ArchitectBot(commands.Bot):
    """The bot. Owns the template registry, the premium store and build locks."""

    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.guilds = True
        intents.message_content = config.ENABLE_PRIVILEGED_INTENTS
        intents.members = config.ENABLE_PRIVILEGED_INTENTS

        super().__init__(
            command_prefix=commands.when_mentioned_or(config.COMMAND_PREFIX),
            intents=intents,
            help_command=None,
            allowed_mentions=discord.AllowedMentions.none(),
            description=f"{config.BRAND_NAME} — {config.BRAND_TAGLINE}",
        )

        self.registry = TemplateRegistry(config.TEMPLATE_DIR).load()
        self.premium = PremiumStore(
            config.PREMIUM_STORE,
            keys=(config.PREMIUM_KEY, *config.PREMIUM_EXTRA_KEYS),
            guild_wide=config.PREMIUM_UNLOCKS_GUILD,
        )
        self.licence = LicenceClient(
            config.MAIN_BOT_URL, config.PREMIUM_PARTNER_TOKEN
        )
        self.active_builds: set[int] = set()
        self._health_runner: AppRunner | None = None
        self._status_task: asyncio.Task | None = None

        # Partner-Handshake: kurzlebige Vormerkungen und dauerhafter Vermerk,
        # wo das Template schon lief.
        self.pending_handoffs = PendingHandoffs()
        self.setup_ledger = SetupLedger(config.SETUP_LEDGER)
        self.partner_template_key = config.PARTNER_TEMPLATE
        self.autosetup = AutoSetup(self)

    # ------------------------------------------------------------ lifecycle --
    async def setup_hook(self) -> None:
        # Emojis zuerst: die persistenten Views bauen ihre Buttons beim
        # Erzeugen, und button_emoji() liest die Tabelle in diesem
        # Moment. Andersherum haetten die angehefteten Nachrichten fuer
        # immer die Unicode-Rueckfaelle -- sie werden nie neu gebaut.
        from core.emoji_sync import sync_emojis
        from ui.emojis import load as load_emojis

        load_emojis(
            await sync_emojis(config.DISCORD_TOKEN or "", enabled=config.EMOJI_SYNC)
        )

        # Angeheftete Verify-/Rollen-/Ticket-Nachrichten muessen einen
        # Neustart ueberleben, sonst sind die Buttons danach tot.
        from ui.widgets import PERSISTENT_VIEWS

        for view_cls in PERSISTENT_VIEWS:
            self.add_view(view_cls())

        if config.HEALTH_SERVER:
            from web import start_web_server

            self._health_runner = await start_web_server(self)

        try:
            if config.DISCORD_GUILD_ID:
                guild = discord.Object(id=int(config.DISCORD_GUILD_ID))
                self.tree.copy_global_to(guild=guild)
                await self.tree.sync(guild=guild)
                LOGGER.info("Slash-Commands mit Guild %s synchronisiert", config.DISCORD_GUILD_ID)
            else:
                await self.tree.sync()
                LOGGER.info("Slash-Commands global synchronisiert")
        except (ValueError, discord.HTTPException) as exc:
            LOGGER.warning("Slash-Sync fehlgeschlagen: %s", exc)

        if not config.ENABLE_PRIVILEGED_INTENTS:
            LOGGER.warning(
                "Privileged Intents sind aus — Kanal-Modi und die "
                "Eingangsschleuse arbeiten nur mit aktivierten Intents. "
                "Setze ENABLE_PRIVILEGED_INTENTS=true."
            )

        # Sagt, ob Freischaltungen einen Deploy ueberleben. Railway loggt
        # beim Mounten nur den Host-Pfad, nicht den Pfad im Container.
        self.premium.log_storage_state()

        # Der Backup-Ordner wird beim Start angelegt — wer das Volume in
        # Railway vergessen hat, merkt es sofort statt beim ersten Backup.
        from config import BACKUP_DIR

        try:
            BACKUP_DIR.mkdir(parents=True, exist_ok=True)
            LOGGER.info("Backups landen in %s", BACKUP_DIR)
        except OSError:
            LOGGER.warning(
                "Backup-Ordner %s ist nicht beschreibbar — "
                "/template backup erstellen wird fehlschlagen.",
                BACKUP_DIR,
            )

        if not self.premium.is_configured and not self.licence.is_configured:
            # Nur warnen, wenn *beide* Wege fehlen. Wer Lizenzen ueber den
            # University Bot bezieht, braucht keinen Master-Key — die alte
            # Warnung erschien dort trotzdem und sah aus wie ein Fehler.
            LOGGER.warning(
                "Weder PREMIUM_KEY noch MAIN_BOT_URL gesetzt — Premium "
                "laesst sich nicht freischalten."
            )

        if self.licence.is_configured:
            LOGGER.info(
                "Lizenzabfrage aktiv: Premium wird beim University Bot "
                "erfragt (%s)", self.licence.base_url,
            )

        # Ohne uebertragene Emojis faellt alles auf Unicode zurueck. Das
        # sieht man den Antworten nicht sofort an, deshalb steht es im Log.
        from ui.emojis import EMOJIS, has_emojis

        if has_emojis():
            LOGGER.info("%d eigene Emojis aktiv", len(EMOJIS))
        else:
            LOGGER.info(
                "Keine eigenen Emojis — es werden Unicode-Zeichen benutzt. "
                "EMOJI_SYNC=true setzen, um sie zu uebernehmen."
            )

    async def close(self) -> None:
        if self._status_task is not None:
            self._status_task.cancel()
            self._status_task = None
        if self._health_runner is not None:
            with contextlib.suppress(Exception):
                await self._health_runner.cleanup()
            self._health_runner = None
        await super().close()

    async def on_ready(self) -> None:
        totals = self.registry.totals

        LOGGER.info("Online als %s (%d Server)", self.user, len(self.guilds))
        LOGGER.info(
            "%d Templates · %d Kategorien · %d Kanäle",
            totals["templates"],
            totals["categories"],
            totals["channels"],
        )

        # on_ready feuert auch nach jedem Reconnect. Ohne diese Sperre liefe
        # nach ein paar Stunden ein Dutzend Rotationen parallel.
        if self._status_task is None or self._status_task.done():
            self._status_task = self.loop.create_task(self._rotate_status())

    async def _rotate_status(self) -> None:
        """Wechselt die Präsenz alle 15 Sekunden."""

        await self.wait_until_ready()
        templates = self.registry.totals["templates"]

        while not self.is_closed():
            # Zahlen bei jedem Durchlauf neu ermitteln — sonst zeigt der Bot
            # nach dem ersten Serverbeitritt dauerhaft veraltete Werte.
            servers = len(self.guilds)
            members = sum(guild.member_count or 0 for guild in self.guilds)

            activities = (
                discord.Activity(
                    type=discord.ActivityType.watching,
                    name=f"/template start · {templates} Templates",
                ),
                discord.Activity(
                    type=discord.ActivityType.playing,
                    name=f"Auf {servers} Servern",
                ),
                discord.Activity(
                    type=discord.ActivityType.listening,
                    name=f"{members} User weltweit",
                ),
            )

            for activity in activities:
                with contextlib.suppress(discord.HTTPException):
                    await self.change_presence(
                        status=discord.Status.online, activity=activity
                    )
                await asyncio.sleep(STATUS_INTERVAL)

    async def on_member_join(self, member: discord.Member) -> None:
        """Give newcomers the Unverified role so the gate actually gates."""

        if member.bot:
            return
        role = discord.utils.find(
            lambda r: "unverified" in r.name.lower(), member.guild.roles
        )
        if role is None or not role.is_assignable():
            return
        with contextlib.suppress(discord.HTTPException):
            await member.add_roles(role, reason="Neues Mitglied")

    async def on_guild_join(self, guild: discord.Guild) -> None:
        """Automatische Einrichtung, wenn der Server von einem Partner kam."""

        LOGGER.info("Server beigetreten: %s (%s)", guild.name, guild.id)
        try:
            await self.autosetup.on_guild_join(guild)
        except Exception:  # pragma: no cover - darf den Bot nie mitreissen
            LOGGER.exception("Automatische Einrichtung fehlgeschlagen")

    def schedule_partner_setup(self, guild: discord.Guild) -> None:
        """Einrichtung anstossen, wenn der Callback nach dem Join kam.

        Wird aus dem Webserver aufgerufen, der nicht warten kann — deshalb
        eine Hintergrundaufgabe statt eines await.
        """

        handoff = self.pending_handoffs.pop(guild.id)
        if handoff is None:
            return

        async def runner() -> None:
            try:
                await self.autosetup.run(guild, handoff)
            except Exception:  # pragma: no cover
                LOGGER.exception("Nachgezogene Einrichtung fehlgeschlagen")

        self.loop.create_task(runner())

    async def on_message(self, message: discord.Message) -> None:
        """Setzt Kanal-Modi durch und vergibt Auto-Reaktionen."""

        if message.author.bot or message.guild is None:
            await self.process_commands(message)
            return

        from core.enforcement import apply_reactions, check_message

        removed = False
        with contextlib.suppress(discord.HTTPException):
            removed = await check_message(message)

        if removed:
            return

        with contextlib.suppress(discord.HTTPException):
            await apply_reactions(message)

        await self.process_commands(message)

    # -------------------------------------------------------------- helpers --
    async def has_premium(self, interaction_or_ctx) -> bool:
        """
        Hat dieser Nutzer Premium?

        Zwei Wege, in dieser Reihenfolge:

        1. Der lokale Store — jemand hat hier den Master-Key eingegeben.
           Das ist ein Speicherzugriff und kostet nichts.
        2. Der University Bot, falls eingerichtet. Dort kauft und loest
           man einen persoenlichen Key ein.

        Erst lokal, damit eine bestehende Freischaltung auch dann noch
        gilt, wenn der University Bot gerade nicht erreichbar ist.
        """

        guild = getattr(interaction_or_ctx, "guild", None)
        user = getattr(interaction_or_ctx, "user", None) or getattr(
            interaction_or_ctx, "author", None
        )
        if user is None:
            return False

        if self.premium.has_access(guild.id if guild else None, user.id):
            return True

        return await self.licence.has_premium(user.id)


bot = ArchitectBot()


# --------------------------------------------------------------------------- #
# Commands: /template ... plus /ping
# --------------------------------------------------------------------------- #

template_group = discord.app_commands.Group(
    name="template",
    description="Server-Vorlagen ansehen, anwenden und verwalten",
    guild_only=True,
)


@template_group.command(name="start", description="Öffnet das Vorlagen-Menü")
async def template_start(interaction: discord.Interaction) -> None:
    """Das Vorlagen-Menü — Auswählen, Ansehen, Anwenden."""

    await interaction.response.send_message(
        view=build_start_view(bot, premium=await bot.has_premium(interaction))
    )


@template_group.command(name="list", description="Zeigt alle Vorlagen mit Details")
async def template_list(interaction: discord.Interaction) -> None:
    """Alle Vorlagen auf einen Blick — mit Vorschau je Vorlage."""

    from ui.management import TemplateListView

    await interaction.response.send_message(view=TemplateListView(bot))


@template_group.command(
    name="löschen",
    description="Macht eine Vorlage rückgängig oder leert den Server",
)
@discord.app_commands.default_permissions(manage_guild=True)
@discord.app_commands.describe(
    vorlage="Welche Vorlage rückgängig gemacht werden soll (leer lassen für eine Auswahl)"
)
async def template_delete(
    interaction: discord.Interaction, vorlage: str | None = None
) -> None:
    """Struktur einer Vorlage entfernen — oder alles Löschbare."""

    from ui.management import DeleteConfirmView, DeletePickerView

    if vorlage:
        template = bot.registry.get(vorlage)
        if template is None:
            await interaction.response.send_message(
                view=notice(
                    "Vorlage nicht gefunden",
                    f"`{vorlage}` ist keine bekannte Vorlage.",
                    tone="error",
                    hint="Ohne Argument öffnet sich die Auswahl aller Vorlagen.",
                ),
                ephemeral=True,
            )
            return
        await interaction.response.send_message(
            view=DeleteConfirmView(bot, template), ephemeral=True
        )
        return

    await interaction.response.send_message(view=DeletePickerView(bot), ephemeral=True)


@template_delete.autocomplete("vorlage")
async def template_delete_autocomplete(
    interaction: discord.Interaction, current: str
) -> list[discord.app_commands.Choice[str]]:
    """Vorlagen passend zur Eingabe vorschlagen."""

    needle = current.lower()
    return [
        discord.app_commands.Choice(name=f"{tpl.emoji} {tpl.name}", value=tpl.key)
        for tpl in bot.registry.all
        if needle in tpl.name.lower() or needle in tpl.key
    ][:25]


@template_group.command(
    name="ai", description="Stellt eine Vorlage aus deiner Beschreibung zusammen"
)
async def template_ai(interaction: discord.Interaction) -> None:
    """Regelbasierter Assistent: Beschreibung → fertige Vorlage."""

    from ui.management import AiTemplateModal

    await interaction.response.send_modal(AiTemplateModal(bot))


@template_group.command(
    name="premium", description="Zeigt deinen Premium-Status"
)
async def template_premium(interaction: discord.Interaction) -> None:
    """Wie es um Premium steht — und wie man es bekommt.

    Hiess frueher `/template key` und oeffnete ein Eingabefeld fuer
    einen Lizenz-Key. Diese Keys gibt es nicht mehr: es gibt genau ein
    Premium, der University Bot verwaltet es, und man bekommt es dort
    ueber einen Beta-Antrag. Ein Eingabefeld fuer Keys, die niemand
    mehr ausstellt, waere eine Sackgasse mit Cursor.
    """

    if await bot.has_premium(interaction):
        await interaction.response.send_message(
            view=notice(
                "Premium ist aktiv",
                "Dein Premium gilt für beide Bots.",
                tone="premium",
                hint="Öffne /template start, um alle Vorlagen zu sehen.",
            ),
            ephemeral=True,
        )
        return

    # Der Weg zum Dashboard. Ohne konfigurierte Adresse steht hier
    # kein toter Link, sondern nur der Hinweis.
    ziel = f"{config.DASHBOARD_URL}/dashboard/premium/beta" if config.DASHBOARD_URL else ""
    await interaction.response.send_message(
        view=notice(
            "Kein Premium",
            "Premium gilt für beide Bots und hängt an deinem "
            "Discord-Konto.",
            tone="premium",
            hint=(
                f"Stell einen Beta-Antrag im Dashboard: {ziel}"
                if ziel
                else "Stell einen Beta-Antrag im Dashboard des "
                "University Bots."
            ),
        ),
        ephemeral=True,
    )


@template_group.command(
    name="regeln", description="Regelwerk für den Regelkanal einrichten"
)
async def template_regeln(interaction: discord.Interaction) -> None:
    from ui.rules import open_rules_assistant

    await open_rules_assistant(interaction, bot)


@template_group.command(
    name="partner-setup", description="Die Partner-Vorlage erneut anwenden"
)
@discord.app_commands.default_permissions(manage_guild=True)
async def template_partner_setup(interaction: discord.Interaction) -> None:
    """Die Partner-Vorlage bewusst erneut anwenden."""

    guild = interaction.guild
    if guild is None:  # pragma: no cover - die Gruppe ist guild_only
        return

    previous = bot.setup_ledger.details(guild.id)
    if previous is not None:
        await interaction.response.send_message(
            view=notice(
                "Wird erneut aufgebaut",
                f"Die Vorlage lief hier bereits (**{previous.get('template', '?')}**). "
                "Bestehende Kanäle und Rollen bleiben erhalten, es wird nur ergänzt.",
                tone="neutral",
            ),
            ephemeral=True,
        )

    handoff = Handoff(
        guild_id=guild.id,
        user_id=interaction.user.id,
        issued_at=int(time.time()),
        source="manual",
        guild_name=guild.name,
    )
    await bot.autosetup.run(guild, handoff, force=True)


backup_group = discord.app_commands.Group(
    name="backup",
    description="Backups der Serverstruktur",
    parent=template_group,
)


@backup_group.command(
    name="erstellen",
    description="Sichert Rollen, Kanäle und Berechtigungen als JSON",
)
@discord.app_commands.default_permissions(manage_guild=True)
async def backup_erstellen(interaction: discord.Interaction) -> None:
    """Serverstruktur als JSON-Datei sichern."""

    from config import BACKUP_DIR
    from core.backup import capture_backup, save_backup

    guild = interaction.guild
    if guild is None:  # pragma: no cover - die Gruppe ist guild_only
        return

    await interaction.response.defer(thinking=True, ephemeral=True)

    try:
        # Erst der Schnappschuss (liefert die Zahlen fuer die Antwort),
        # dann die Datei — beides aus derselben Datenquelle.
        payload = capture_backup(guild)
        path = await save_backup(guild, BACKUP_DIR)
    except OSError as exc:
        await interaction.followup.send(
            view=notice(
                "Backup fehlgeschlagen",
                f"Die Datei konnte nicht geschrieben werden: {exc}",
                tone="error",
                hint="Prüfe, ob BACKUP_DIR beschreibbar ist — auf Railway "
                "gehört der Pfad auf ein Volume.",
            ),
            ephemeral=True,
        )
        return

    view = notice(
        "Backup erstellt",
        f"**{path.name}**\n"
        f"Rollen: {len(payload['roles'])}  ·  Kanäle: {len(payload['channels'])}",
        tone="success",
        hint=f"Serverseitig liegt eine Kopie unter `{BACKUP_DIR}`.",
    )
    try:
        await interaction.followup.send(
            view=view,
            file=discord.File(path, filename=path.name),
            ephemeral=True,
        )
    except (discord.NotFound, discord.HTTPException):  # pragma: no cover
        # Interaktion abgelaufen — das Backup selbst ist fertig und liegt
        # auf der Platte. Nur die Zustellung ist gescheitert.
        LOGGER.warning(
            "Backup %s geschrieben, aber die Antwort kam nicht mehr an", path.name
        )


bot.tree.add_command(template_group)


@bot.tree.command(name="ping", description="Antwortet mit der Latenz")
async def ping_slash(interaction: discord.Interaction) -> None:
    # Vor dem ersten Heartbeat liefert discord.py NaN — round() wirft darauf
    # einen ValueError. Das Zeitfenster ist klein, aber ausgerechnet direkt
    # nach dem Start greift man am ehesten zu /ping.
    latency = bot.latency
    measured = "—" if math.isnan(latency) else f"{round(latency * 1000)} ms"

    await interaction.response.send_message(
        view=notice(
            "Pong",
            f"Latenz **{measured}**",
            tone="neutral",
            hint=f"{len(bot.registry)} Vorlagen geladen",
        ),
        ephemeral=True,
    )


@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError) -> None:
    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(error, commands.NoPrivateMessage):
        await ctx.send(
            view=notice(
                "Nur auf Servern verfügbar",
                "Dieser Befehl funktioniert nur innerhalb eines Servers.",
                tone="error",
            )
        )
        return
    if isinstance(error, (commands.MissingPermissions, commands.BotMissingPermissions)):
        await ctx.send(view=notice("Keine Berechtigung", str(error), tone="error"))
        return
    LOGGER.exception("Command-Fehler in '%s'", ctx.command, exc_info=error)


def main() -> None:
    if not config.DISCORD_TOKEN:
        print(
            "\n  ❌  DISCORD_TOKEN fehlt.\n\n"
            "     Lokal:   cp .env.example .env  und den Token eintragen\n"
            "     Railway: unter Variables als Secret setzen\n",
            file=sys.stderr,
        )
        raise SystemExit(1)

    try:
        bot.run(config.DISCORD_TOKEN, log_handler=None)
    except discord.LoginFailure:
        print("\n  ❌  Token ungültig — bitte im Developer Portal neu generieren.\n", file=sys.stderr)
        raise SystemExit(1) from None
    except discord.PrivilegedIntentsRequired:
        print(
            "\n  ❌  Privileged Intents nicht aktiviert.\n\n"
            "     Developer Portal → Bot → Server Members + Message Content einschalten,\n"
            "     oder ENABLE_PRIVILEGED_INTENTS=false setzen (dann ohne\n"
            "     Kanal-Modi und Eingangsschleuse).\n",
            file=sys.stderr,
        )
        raise SystemExit(1) from None
    except (OSError, aiohttp.ClientError) as exc:
        # No traceback for a plain connectivity problem — it is never a bug here.
        print(
            f"\n  ❌  Keine Verbindung zu Discord: {exc}\n"
            "     Prüfe Internetverbindung, Proxy oder Firewall.\n",
            file=sys.stderr,
        )
        raise SystemExit(1) from None


if __name__ == "__main__":
    try:
        main()
    except TemplateError as exc:
        print(f"\n  ❌  Template-Fehler: {exc}\n", file=sys.stderr)
        raise SystemExit(1) from None
    except KeyboardInterrupt:
        pass
