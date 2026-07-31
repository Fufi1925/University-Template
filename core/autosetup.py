"""Automatische Einrichtung nach einem Partner-Handoff.

Ablauf, sobald der Bot einem Server beitritt:

1. Steht ein geprueftes Token bereit? Wenn nein, passiert nichts — ein
   normaler Beitritt bleibt ein normaler Beitritt.
2. Das Wettrennen abfangen: Der OAuth-Callback kann **vor** oder **nach**
   ``on_guild_join`` eintreffen. Trifft der Join zuerst ein, wird kurz
   gewartet und erneut nachgesehen.
3. Lief das Template hier schon einmal? Dann nicht erneut aufbauen.
4. Rechte pruefen, Vorlage anwenden, Zusammenfassung posten.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

import discord

from .builder import BuildError, BuildMode, BuildReport, ServerBuilder
from .handshake import Handoff
from .schema import Template

if TYPE_CHECKING:
    from bot import ArchitectBot

LOGGER = logging.getLogger("architect.autosetup")

__all__ = ["RETRY_ATTEMPTS", "RETRY_DELAY", "AutoSetup"]

#: Wartezeit zwischen den Versuchen, den Handoff doch noch zu finden.
RETRY_DELAY = 2.0

#: So oft wird nachgesehen, bevor der Beitritt als normal gilt.
RETRY_ATTEMPTS = 2


class AutoSetup:
    """Bindet Handoff, Ledger und Builder zusammen."""

    def __init__(self, bot: ArchitectBot) -> None:
        self.bot = bot

    # ----------------------------------------------------------- guild join --
    async def on_guild_join(self, guild: discord.Guild) -> None:
        """Einstiegspunkt aus dem Event."""

        handoff = self.bot.pending_handoffs.pop(guild.id)

        if handoff is None:
            # Wettrennen: Der Callback ist vielleicht noch unterwegs.
            handoff = await self._wait_for_handoff(guild.id)

        if handoff is None:
            LOGGER.info(
                "Guild %s (%s) beigetreten — kein Handoff, keine Automatik",
                guild.id,
                guild.name,
            )
            return

        await self.run(guild, handoff)

    async def _wait_for_handoff(self, guild_id: int) -> Handoff | None:
        """Kurz warten, falls der Callback noch nicht angekommen ist."""

        for attempt in range(1, RETRY_ATTEMPTS + 1):
            await asyncio.sleep(RETRY_DELAY)
            handoff = self.bot.pending_handoffs.pop(guild_id)
            if handoff is not None:
                LOGGER.info(
                    "Handoff für Guild %s nach %d. Versuch gefunden", guild_id, attempt
                )
                return handoff
        return None

    # -------------------------------------------------------------- ausfuehren
    async def run(
        self,
        guild: discord.Guild,
        handoff: Handoff,
        *,
        force: bool = False,
    ) -> None:
        """Vorlage anwenden und das Ergebnis melden."""

        ledger = self.bot.setup_ledger

        if not force and ledger.was_set_up(guild.id):
            LOGGER.info(
                "Guild %s wurde bereits eingerichtet — übersprungen", guild.id
            )
            await self._notify(
                guild,
                "Bereits eingerichtet",
                "Auf diesem Server lief die Vorlage schon einmal. "
                "Es wurde nichts verändert.",
                hint=f"Erneut aufbauen: {self.bot.command_prefix_display}partner-setup",
                tone="neutral",
            )
            return

        if guild.id in self.bot.active_builds:
            LOGGER.info("Guild %s: Einrichtung läuft bereits", guild.id)
            return

        template = self._resolve_template()
        if template is None:
            LOGGER.error("Vorlage '%s' existiert nicht", self.bot.partner_template_key)
            await self._notify(
                guild,
                "Vorlage nicht gefunden",
                "Die für Partner-Server hinterlegte Vorlage existiert nicht.",
                hint="PARTNER_TEMPLATE prüfen.",
                tone="error",
            )
            return

        # Discord braucht einen Moment, bis Rechte und Rollen des Bots
        # vollstaendig im Cache stehen.
        await asyncio.sleep(1.5)

        self.bot.active_builds.add(guild.id)
        try:
            builder = ServerBuilder(guild, template)

            # Rechte und Limits zuerst — lieber eine klare Meldung als eine
            # Ausnahme mitten im Aufbau.
            try:
                builder.preflight()
            except BuildError as exc:
                LOGGER.warning("Guild %s: Preflight fehlgeschlagen: %s", guild.id, exc)
                await self._notify(
                    guild,
                    "Automatische Einrichtung nicht möglich",
                    str(exc),
                    hint="Nach dem Beheben: "
                    f"{self.bot.command_prefix_display}partner-setup",
                    tone="error",
                )
                return

            LOGGER.info(
                "Automatische Einrichtung startet: Guild %s, Vorlage %s",
                guild.id,
                template.key,
            )
            report = await builder.apply(BuildMode.EXTEND)

            # Erst nach dem Erfolg vermerken. Bricht der Aufbau ab, darf ein
            # zweiter Versuch nicht blockiert sein.
            ledger.record(guild.id, template=template.key, source=handoff.source)

            await self._post_summary(guild, template, report)
            LOGGER.info(
                "Guild %s eingerichtet: %d Kanäle, %d Rollen",
                guild.id,
                report.channels_created,
                report.roles_created,
            )

        except discord.Forbidden:
            LOGGER.exception("Guild %s: Discord hat abgelehnt", guild.id)
            await self._notify(
                guild,
                "Discord hat die Einrichtung abgelehnt",
                "Dem Bot fehlen Berechtigungen.",
                hint="Die Bot-Rolle muss über den zu verwaltenden Rollen stehen.",
                tone="error",
            )
        except (BuildError, discord.HTTPException) as exc:
            LOGGER.exception("Guild %s: Einrichtung fehlgeschlagen", guild.id)
            await self._notify(
                guild,
                "Einrichtung abgebrochen",
                str(exc)[:500],
                tone="error",
            )
        finally:
            self.bot.active_builds.discard(guild.id)

    def _resolve_template(self) -> Template | None:
        return self.bot.registry.get(self.bot.partner_template_key)

    # ---------------------------------------------------------------- melden --
    @staticmethod
    def _target_channel(guild: discord.Guild) -> discord.TextChannel | None:
        """Ein Kanal, in dem der Bot tatsaechlich schreiben darf."""

        me = guild.me
        if me is None:
            return None

        candidates: list[discord.TextChannel] = []
        if guild.system_channel is not None:
            candidates.append(guild.system_channel)
        candidates.extend(guild.text_channels)

        for channel in candidates:
            if channel.permissions_for(me).send_messages:
                return channel
        return None

    async def _notify(
        self,
        guild: discord.Guild,
        title: str,
        body: str,
        *,
        hint: str | None = None,
        tone: str = "info",
    ) -> None:
        channel = self._target_channel(guild)
        if channel is None:
            LOGGER.warning("Guild %s: kein beschreibbarer Kanal für die Meldung", guild.id)
            return

        from ui.components import notice

        try:
            await channel.send(view=notice(title, body, tone=tone, hint=hint))
        except discord.HTTPException:
            LOGGER.debug("Meldung konnte nicht gesendet werden", exc_info=True)

    async def _post_summary(
        self,
        guild: discord.Guild,
        template: Template,
        report: BuildReport,
    ) -> None:
        channel = self._target_channel(guild)
        if channel is None:
            return

        from ui.views import partner_summary_view

        try:
            await channel.send(view=partner_summary_view(template, report))
        except discord.HTTPException:
            LOGGER.debug("Zusammenfassung konnte nicht gesendet werden", exc_info=True)
