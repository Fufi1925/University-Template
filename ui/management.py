"""Verwaltungsoberflaeche der ``/template``-Gruppe.

Hier wohnen die Ansichten, die nichts bauen, sondern informieren und
aufraeumen: die Liste aller Vorlagen, der Loesch-Dialog (einzelne Vorlage
oder kompletter Wipe) und das Formular des regelbasierten Assistenten.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord import ui

from config import COLOR_BRAND, COLOR_DANGER, COLOR_SUCCESS
from core.builder import BuildError, RemovalReport, ServerBuilder, wipe_guild
from core.permissions import BASE_ROLES
from core.schema import Template, TemplateError

from .components import RULE, SPACE, field_value, footer, notice, quote, stat_line
from .views import DetailView, _fallback_notify, _safe_edit

if TYPE_CHECKING:
    from bot import ArchitectBot

LOGGER = logging.getLogger("architect.ui.management")

BASE_ROLE_COUNT = len(BASE_ROLES)

__all__ = ["AiTemplateModal", "DeleteConfirmView", "DeletePickerView", "TemplateListView"]

_MANAGE_HINT = "Dafür brauchst du die Berechtigung **Server verwalten**."


def _can_manage(user: discord.abc.User | discord.Member) -> bool:
    return isinstance(user, discord.Member) and user.guild_permissions.manage_guild


# --------------------------------------------------------------------------- #
# /template list
# --------------------------------------------------------------------------- #

class _ListSelect(ui.Select["TemplateListView"]):
    """Waehlt eine Vorlage und oeffnet die Detailansicht mit Vorschau."""

    def __init__(self, bot: ArchitectBot, templates: list[Template]) -> None:
        options = [
            discord.SelectOption(
                label=template.name,
                value=template.key,
                description=template.tagline[:100],
                emoji=template.emoji,
            )
            for template in templates
        ]
        super().__init__(
            placeholder="Vorlage für die Vorschau wählen",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="architect:list-select",
        )
        self.bot = bot

    async def callback(self, interaction: discord.Interaction) -> None:
        template = self.bot.registry.get(self.values[0])
        if template is None:
            await interaction.response.send_message(
                view=notice(
                    "Vorlage nicht gefunden",
                    "Diese Vorlage steht nicht mehr zur Verfügung.",
                    tone="error",
                ),
                ephemeral=True,
            )
            return

        # Premium-Vorlagen sind gelistet, aber erst nach dem Unlock nutzbar.
        if template.premium and not await self.bot.has_premium(interaction):
            await interaction.response.send_message(
                view=notice(
                    "Premium erforderlich",
                    f"**{template.name}** ist eine Premium-Vorlage.",
                    tone="premium",
                    hint="Wende dich an die Serverleitung oder schalte Premium "
                    "im Startmenü frei.",
                ),
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            view=DetailView(self.bot, template), ephemeral=True
        )


class TemplateListView(ui.LayoutView):
    """Alle Vorlagen auf einen Blick — mit Vorschau je Vorlage."""

    def __init__(self, bot: ArchitectBot) -> None:
        super().__init__(timeout=None)
        self.bot = bot

        registry = bot.registry
        totals = registry.totals

        container = ui.Container(accent_colour=discord.Colour(COLOR_BRAND))
        container.add_item(
            ui.TextDisplay(
                f"## Alle Vorlagen\n"
                f"-# {totals['templates']} Templates  ·  "
                f"{totals['categories']} Kategorien  ·  {totals['channels']} Kanäle"
            )
        )
        container.add_item(RULE())

        for section, templates in (
            ("**Kostenlos**", registry.free),
            ("**Premium**", registry.premium),
        ):
            container.add_item(ui.TextDisplay(section))
            container.add_item(
                ui.TextDisplay(
                    quote(
                        *(
                            f"{t.emoji}  **{t.name}** — {t.tagline}\n"
                            f"-# {t.category_count} Kategorien  ·  "
                            f"{t.channel_count} Kanäle  ·  "
                            f"{t.voice_count} Sprachkanäle  ·  "
                            f"{BASE_ROLE_COUNT + len(t.roles)} Rollen"
                            for t in templates
                        )
                    )
                )
            )
            container.add_item(SPACE())

        row = ui.ActionRow()
        row.add_item(_ListSelect(bot, registry.all))
        container.add_item(row)
        container.add_item(
            footer("Vorlage wählen, um Details und Vorschau zu sehen")
        )
        self.add_item(container)


# --------------------------------------------------------------------------- #
# /template löschen
# --------------------------------------------------------------------------- #

class _DeleteSelect(ui.Select["DeletePickerView"]):
    """Waehlt die Vorlage, deren Struktur rueckgaengig gemacht wird."""

    def __init__(self, bot: ArchitectBot) -> None:
        options = [
            discord.SelectOption(
                label=template.name,
                value=template.key,
                description=template.tagline[:100],
                emoji=template.emoji,
            )
            for template in bot.registry.all
        ]
        super().__init__(
            placeholder="Vorlage wählen, die entfernt werden soll",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="architect:delete-select",
        )
        self.bot = bot

    async def callback(self, interaction: discord.Interaction) -> None:
        template = self.bot.registry.get(self.values[0])
        if template is None:
            await interaction.response.send_message(
                view=notice(
                    "Vorlage nicht gefunden",
                    "Diese Vorlage steht nicht mehr zur Verfügung.",
                    tone="error",
                ),
                ephemeral=True,
            )
            return
        await interaction.response.edit_message(
            view=DeleteConfirmView(self.bot, template)
        )


class _WipeButton(ui.Button["DeletePickerView"]):
    """Der Weg zum kompletten Wipe — ohne eine einzelne Vorlage zu nennen."""

    def __init__(self) -> None:
        super().__init__(
            label="Alles löschen (Wipe)",
            style=discord.ButtonStyle.danger,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        if self.view is None:
            return
        await interaction.response.edit_message(
            view=DeleteConfirmView(self.view.bot, None)
        )


class DeletePickerView(ui.LayoutView):
    """Einstieg des Loesch-Befehls: Vorlage waehlen oder alles loeschen."""

    def __init__(self, bot: ArchitectBot) -> None:
        super().__init__(timeout=600)
        self.bot = bot

        container = ui.Container(accent_colour=discord.Colour(COLOR_DANGER))
        container.add_item(
            ui.TextDisplay(
                "## Vorlage entfernen\n"
                "-# Was soll gelöscht werden?"
            )
        )
        container.add_item(RULE())
        container.add_item(
            ui.TextDisplay(
                quote(
                    "**Eine Vorlage rückgängig machen**",
                    "Löscht nur Kategorien, Kanäle und Rollen, die zu dieser "
                    "Vorlage passen. Fremde Kanäle bleiben unangetastet.",
                )
            )
        )
        container.add_item(SPACE())
        container.add_item(
            ui.TextDisplay(
                quote(
                    "**Alles löschen (Wipe)**",
                    "Löscht alle Kanäle und Rollen, die der Bot entfernen darf.",
                    "Das lässt sich nicht rückgängig machen.",
                )
            )
        )
        container.add_item(RULE())

        row = ui.ActionRow()
        row.add_item(_DeleteSelect(bot))
        container.add_item(row)
        row = ui.ActionRow()
        row.add_item(_WipeButton())
        row.add_item(_CancelButton())
        container.add_item(row)

        container.add_item(footer("In beiden Fällen folgt eine Bestätigung."))
        self.add_item(container)


class _CancelButton(ui.Button["ui.LayoutView"]):
    def __init__(self) -> None:
        super().__init__(label="Abbrechen", style=discord.ButtonStyle.secondary)

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.edit_message(
            view=notice("Abgebrochen", "Es wurde nichts gelöscht.", tone="neutral")
        )


class _ConfirmDeleteButton(ui.Button["DeleteConfirmView"]):
    def __init__(self, template: Template | None) -> None:
        super().__init__(
            label="Löschen" if template is not None else "Alles löschen",
            style=discord.ButtonStyle.danger,
        )
        self.template = template

    async def callback(self, interaction: discord.Interaction) -> None:
        if self.view is None:
            return
        await _run_deletion(interaction, self.view.bot, self.template)


class DeleteConfirmView(ui.LayoutView):
    """Die letzte Warnung, bevor wirklich geloescht wird."""

    def __init__(self, bot: ArchitectBot, template: Template | None) -> None:
        super().__init__(timeout=600)
        self.bot = bot
        self.template = template

        if template is not None:
            heading = f"## {template.emoji}  {template.name} entfernen"
            body = (
                f"**{template.name}** wird rückgängig gemacht: "
                f"{template.category_count} Kategorien und "
                f"{template.channel_count} Kanäle der Vorlage sowie ihre "
                f"{len(template.roles)} eigenen Rollen werden gelöscht."
            )
            caveats = (
                "Die geteilten Basis-Rollen (Verified, Moderation, …) bleiben "
                "erhalten. Fremde Kanäle in passenden Kategorien ebenfalls — "
                "die Kategorie bleibt dann stehen."
            )
        else:
            heading = "## Alles löschen (Wipe)"
            body = (
                "**Alle** Kanäle und Rollen, die der Bot entfernen darf, "
                "werden gelöscht — ohne Neuaufbau."
            )
            caveats = "Das lässt sich nicht rückgängig machen."

        container = ui.Container(accent_colour=discord.Colour(COLOR_DANGER))
        container.add_item(ui.TextDisplay(f"{heading}\n-# {body}"))
        container.add_item(RULE())
        container.add_item(ui.TextDisplay(quote(caveats)))
        container.add_item(RULE())

        row = ui.ActionRow()
        row.add_item(_ConfirmDeleteButton(template))
        row.add_item(_CancelButton())
        container.add_item(row)
        container.add_item(footer())
        self.add_item(container)


def _deletion_view(report: RemovalReport, template: Template | None) -> ui.LayoutView:
    """Ergebnis einer Loeschung — Zahlen plus alles, was stehen blieb."""

    label = "Alles gelöscht" if template is None else f"{template.name} entfernt"
    container = ui.Container(accent_colour=discord.Colour(COLOR_SUCCESS))
    container.add_item(ui.TextDisplay(f"### {label}\n-# Der Server wurde aufgeräumt."))
    container.add_item(RULE())
    container.add_item(
        ui.TextDisplay(
            quote(
                "**Gelöscht**",
                stat_line(
                    [
                        ("Kategorien", report.deleted_categories),
                        ("Kanäle", report.deleted_channels),
                        ("Rollen", report.deleted_roles),
                    ]
                ),
            )
        )
    )
    if report.warnings:
        container.add_item(RULE())
        container.add_item(ui.TextDisplay("**Hinweise**"))
        container.add_item(ui.TextDisplay(quote(*report.warnings[:4])))
    container.add_item(RULE())
    container.add_item(
        ui.TextDisplay("-# Es wurde nichts neu angelegt — nur entfernt.")
    )
    container.add_item(footer())
    view = ui.LayoutView(timeout=None)
    view.add_item(container)
    return view


async def _run_deletion(
    interaction: discord.Interaction,
    bot: ArchitectBot,
    template: Template | None,
) -> None:
    """Die eigentliche Loeschung — mit denselben Waechtern wie ein Build."""

    guild = interaction.guild
    if guild is None:
        return

    if not _can_manage(interaction.user):
        await interaction.response.send_message(
            view=notice("Keine Berechtigung", _MANAGE_HINT, tone="error"),
            ephemeral=True,
        )
        return

    me = guild.me
    perms = me.guild_permissions if me is not None else None
    if perms is None or not (perms.manage_channels and perms.manage_roles):
        await interaction.response.send_message(
            view=notice(
                "Einrichtung nicht möglich",
                "Dem Bot fehlen Berechtigungen: **Kanäle verwalten** und "
                "**Rollen verwalten**.",
                tone="error",
            ),
            ephemeral=True,
        )
        return

    if guild.id in bot.active_builds:
        await interaction.response.send_message(
            view=notice(
                "Einrichtung läuft bereits",
                "Für diesen Server läuft gerade eine Einrichtung.",
                tone="error",
                hint="Warte, bis der Vorgang abgeschlossen ist.",
            ),
            ephemeral=True,
        )
        return

    bot.active_builds.add(guild.id)
    try:
        report = (
            await ServerBuilder(guild, template).unapply()
            if template is not None
            else await wipe_guild(guild)
        )
        LOGGER.info(
            "Löschung fertig guild=%s template=%s deleted=%d",
            guild.id,
            template.key if template else "wipe",
            report.total_deleted,
        )
        if not await _safe_edit(interaction, _deletion_view(report, template)):
            await _fallback_notify(interaction, _deletion_view(report, template))
    except BuildError as exc:
        await _safe_edit(
            interaction,
            notice("Löschen abgebrochen", str(exc), tone="error"),
        )
    except discord.Forbidden:
        LOGGER.exception("Forbidden während Löschung guild=%s", guild.id)
        await _safe_edit(
            interaction,
            notice(
                "Discord hat die Aktion abgelehnt",
                "Dem Bot fehlen Berechtigungen.",
                tone="error",
                hint="Die Bot-Rolle muss über den zu verwaltenden Rollen stehen.",
            ),
        )
    except discord.HTTPException as exc:
        LOGGER.exception("HTTP-Fehler während Löschung guild=%s", guild.id)
        await _safe_edit(
            interaction,
            notice("Discord meldet einen Fehler", f"```{exc.text or exc}```", tone="error"),
        )
    finally:
        bot.active_builds.discard(guild.id)


# --------------------------------------------------------------------------- #
# /template ai
# --------------------------------------------------------------------------- #

class AiTemplateModal(ui.Modal, title="Vorlage per KI erstellen"):
    """Beschreibung abfragen — den Rest macht der regelbasierte Assistent.

    Kein Sprachmodell im Hintergrund: die Antwort steht sofort fest und
    kostet keine API. Das Ergebnis ist eine normale Vorlage mit Vorschau
    und denselben Anwenden-Optionen wie jede andere.
    """

    name = ui.Label(
        text="Server-Name",
        description="Wie soll die Vorlage heißen?",
        component=ui.TextInput(
            placeholder="Mein Community-Server",
            required=True,
            min_length=2,
            max_length=60,
        ),
    )

    description = ui.Label(
        text="Beschreibung",
        description="Worum geht es? Themen wie Gaming, Musik, Studium, RP …",
        component=ui.TextInput(
            placeholder="Ein Server zum Zocken und für Musik, mit Tickets für Hilfe",
            required=True,
            min_length=8,
            max_length=1500,
            style=discord.TextStyle.paragraph,
        ),
    )

    def __init__(self, bot: ArchitectBot) -> None:
        super().__init__(timeout=600)
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction) -> None:
        from core.ai_templates import compose_template

        server_name = field_value(self.name)
        description = field_value(self.description)

        try:
            template = compose_template(
                self.bot.registry, name=server_name, description=description
            )
        except TemplateError as exc:
            await interaction.response.send_message(
                view=notice(
                    "Daraus wird keine Vorlage",
                    str(exc),
                    tone="error",
                    hint="Probiere eine kürzere oder allgemeinere Beschreibung.",
                ),
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            view=DetailView(self.bot, template), ephemeral=True
        )

    async def on_error(  # type: ignore[override]
        self, interaction: discord.Interaction, error: Exception, /
    ) -> None:  # pragma: no cover
        LOGGER.exception("AI-Vorlage fehlgeschlagen", exc_info=error)
        if not interaction.response.is_done():
            await interaction.response.send_message(
                view=notice(
                    "Etwas ist schiefgelaufen",
                    "Bitte versuche es noch einmal.",
                    tone="error",
                ),
                ephemeral=True,
            )
