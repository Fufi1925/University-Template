"""Discord Architect — server templates via Components V2.

Entry point. Run with ``python bot.py`` after setting ``DISCORD_TOKEN``.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
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
                "Privileged Intents sind aus — '%sstart' funktioniert nicht. "
                "Nutze /start oder setze ENABLE_PRIVILEGED_INTENTS=true.",
                config.COMMAND_PREFIX,
            )

        if not self.premium.is_configured:
            LOGGER.warning(
                "Kein PREMIUM_KEY gesetzt — die Premium-Vorlagen lassen sich "
                "nicht freischalten. Variable setzen, um sie zu aktivieren."
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
                    name=f"{config.COMMAND_PREFIX}start · {templates} Templates",
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

    @property
    def command_prefix_display(self) -> str:
        """Der Prefix, wie er in Meldungen erscheinen soll."""

        return config.COMMAND_PREFIX

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
    def has_premium(self, interaction_or_ctx) -> bool:
        guild = getattr(interaction_or_ctx, "guild", None)
        user = getattr(interaction_or_ctx, "user", None) or getattr(
            interaction_or_ctx, "author", None
        )
        if user is None:
            return False
        return self.premium.has_access(guild.id if guild else None, user.id)


bot = ArchitectBot()


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #

async def _require_guild(ctx: commands.Context) -> discord.Guild | None:
    """Den Server aus dem Kontext holen, oder freundlich abbrechen.

    ``@commands.guild_only()`` schuetzt das zur Laufzeit bereits, aber der
    Typ bleibt ``Guild | None``. Statt die Pruefung in jedem Befehl zu
    wiederholen — oder sie wegzucasten und beim naechsten Umbau zu verlieren —
    steht sie hier einmal.
    """

    if ctx.guild is not None:
        return ctx.guild
    await ctx.send(
        view=notice(
            "Nur auf Servern verfügbar",
            "Dieser Befehl funktioniert nur innerhalb eines Servers.",
            tone="error",
        )
    )
    return None

@bot.command(name="start", aliases=["templates", "setup", "menu"])
@commands.guild_only()
async def start_prefix(ctx: commands.Context) -> None:
    """Open the template menu."""

    await ctx.send(view=build_start_view(bot, premium=bot.has_premium(ctx)))


@bot.tree.command(name="start", description="Öffnet das Server-Template-Menü")
@discord.app_commands.guild_only()
async def start_slash(interaction: discord.Interaction) -> None:
    await interaction.response.send_message(
        view=build_start_view(bot, premium=bot.has_premium(interaction))
    )


@bot.command(name="regeln", aliases=["rules", "regelwerk"])
@commands.guild_only()
async def rules_prefix(ctx: commands.Context) -> None:
    """Öffnet den Regelwerk-Assistenten."""

    from ui.rules import RulesetPicker, find_rules_channel

    guild = await _require_guild(ctx)
    if guild is None:
        return

    channel = find_rules_channel(guild)
    if channel is None:
        await ctx.send(
            view=notice(
                "Kein Regelkanal gefunden",
                "Auf diesem Server gibt es keinen Kanal für Regeln.",
                tone="error",
                hint=f"Wende zuerst eine Vorlage mit {config.COMMAND_PREFIX}start an.",
            )
        )
        return
    await ctx.send(view=RulesetPicker(bot, channel))


@bot.tree.command(name="regeln", description="Regelwerk für den Regelkanal einrichten")
@discord.app_commands.guild_only()
async def rules_slash(interaction: discord.Interaction) -> None:
    from ui.rules import open_rules_assistant

    await open_rules_assistant(interaction, bot)


@bot.command(name="partner-setup", aliases=["autosetup"])
@commands.guild_only()
@commands.has_guild_permissions(manage_guild=True)
async def partner_setup(ctx: commands.Context) -> None:
    """Die Partner-Vorlage bewusst erneut anwenden."""

    guild = await _require_guild(ctx)
    if guild is None:
        return

    previous = bot.setup_ledger.details(guild.id)

    if previous is not None:
        await ctx.send(
            view=notice(
                "Wird erneut aufgebaut",
                f"Die Vorlage lief hier bereits (**{previous.get('template', '?')}**). "
                "Bestehende Kanäle und Rollen bleiben erhalten, es wird nur ergänzt.",
                tone="neutral",
            )
        )

    handoff = Handoff(
        guild_id=guild.id,
        user_id=ctx.author.id,
        issued_at=int(time.time()),
        source="manual",
        guild_name=guild.name,
    )
    await bot.autosetup.run(guild, handoff, force=True)


@partner_setup.error
async def partner_setup_error(ctx: commands.Context, error: commands.CommandError) -> None:
    if isinstance(error, commands.MissingPermissions):
        await ctx.send(
            view=notice(
                "Keine Berechtigung",
                "Dafür brauchst du **Server verwalten**.",
                tone="error",
            )
        )
        return
    raise error


@bot.command(name="ping")
async def ping(ctx: commands.Context) -> None:
    await ctx.send(
        view=notice(
            "Pong",
            f"Latenz **{round(bot.latency * 1000)} ms**",
            tone="neutral",
            hint=f"{len(bot.registry)} Vorlagen geladen",
        )
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
            "     oder ENABLE_PRIVILEGED_INTENTS=false setzen (dann nur /start).\n",
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
