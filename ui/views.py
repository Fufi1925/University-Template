"""The interactive surfaces: start menu, premium unlock, preview and build."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

import discord
from discord import ui

from config import (
    BRAND_NAME,
    BRAND_TAGLINE,
    COMMAND_PREFIX,
    COLOR_BRAND,
    COLOR_DANGER,
    COLOR_NEUTRAL,
    COLOR_PREMIUM,
    COLOR_SUCCESS,
)
from core.builder import BuildError, BuildMode, BuildReport, ServerBuilder
from core.permissions import BASE_ROLES
from core.rulesets import RULESETS
from core.schema import Template
from .components import (
    RULE,
    SPACE,
    footer,
    kind_icon,
    notice,
    progress_bar,
    quote,
    stat_line,
    visibility_badge,
)

if TYPE_CHECKING:
    from bot import ArchitectBot

LOGGER = logging.getLogger("architect.ui")

# Jede Vorlage erbt diese Rollenleiter; die Zahl darf nicht hartcodiert werden.
BASE_ROLE_COUNT = len(BASE_ROLES)
RULESET_COUNT = len(RULESETS)

__all__ = ["StartView", "build_start_view", "partner_summary_view"]

_MANAGE_HINT = "Dafür brauchst du die Berechtigung **Server verwalten**."
_MANAGE_REASON = "So kann niemand den Server ungefragt umbauen."


def _can_manage(user: discord.abc.User | discord.Member) -> bool:
    return isinstance(user, discord.Member) and user.guild_permissions.manage_guild


# --------------------------------------------------------------------------- #
# Premium unlock
# --------------------------------------------------------------------------- #

class PremiumModal(ui.Modal, title="Premium freischalten"):
    """Key-Abfrage.

    Der Platzhalter zeigt bewusst **kein** Beispiel des echten Keys — sonst
    koennte ihn jeder ablesen, der den Button anklickt, und Premium waere
    wertlos. Geprueft wird in konstanter Zeit, gespeichert wird der Key nie.
    """

    # ui.Label statt des veralteten label=-Arguments (discord.py 2.6+).
    # Die description fuehrt den Nutzer, ohne den Key zu verraten.
    key = ui.Label(
        text="Premium-Key",
        description="Den Key erhältst du von der Serverleitung.",
        component=ui.TextInput(
            placeholder="Key hier eingeben",
            required=True,
            min_length=4,
            max_length=100,
        ),
    )

    def __init__(self, bot: "ArchitectBot") -> None:
        super().__init__(timeout=300)
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction) -> None:
        # self.key ist das Label; der eingegebene Text liegt in dessen component.
        supplied = str(self.key.component.value)

        if not self.bot.premium.verify(supplied):
            LOGGER.info(
                "Ungültiger Premium-Key von user=%s guild=%s",
                interaction.user.id,
                interaction.guild.id if interaction.guild else None,
            )
            await interaction.response.send_message(
                view=notice(
                    "Key nicht erkannt",
                    "Der eingegebene Key ist nicht gültig.",
                    tone="error",
                    hint="Achte auf Leerzeichen am Anfang und Ende. "
                    "Groß- und Kleinschreibung spielt keine Rolle.",
                ),
                ephemeral=True,
            )
            return

        guild_id = interaction.guild.id if interaction.guild else None
        self.bot.premium.grant(guild_id, interaction.user.id)
        LOGGER.info(
            "Premium freigeschaltet für user=%s guild=%s", interaction.user.id, guild_id
        )

        unlocked = self.bot.registry.premium
        container = ui.Container(accent_colour=discord.Colour(COLOR_PREMIUM))
        container.add_item(
            ui.TextDisplay(
                "### Premium freigeschaltet\n"
                f"-# {len(unlocked)} zusätzliche Vorlagen für "
                f"{interaction.user.display_name}"
            )
        )
        container.add_item(RULE())
        container.add_item(
            ui.TextDisplay(
                quote(
                    *(
                        f"{tpl.emoji}  **{tpl.name}** — {tpl.tagline}"
                        for tpl in unlocked
                    )
                )
            )
        )
        container.add_item(RULE())
        container.add_item(
            ui.TextDisplay(
                f"-# Öffne das Menü mit `{COMMAND_PREFIX}start` erneut — "
                "die Vorlagen stehen jetzt im Auswahlmenü."
            )
        )
        container.add_item(footer())

        view = ui.LayoutView(timeout=None)
        view.add_item(container)
        await interaction.response.send_message(view=view, ephemeral=True)

    async def on_error(
        self, interaction: discord.Interaction, error: Exception
    ) -> None:  # pragma: no cover
        LOGGER.exception("Premium-Modal fehlgeschlagen", exc_info=error)
        if not interaction.response.is_done():
            await interaction.response.send_message(
                view=notice(
                    "Etwas ist schiefgelaufen",
                    "Bitte versuche es noch einmal.",
                    tone="error",
                ),
                ephemeral=True,
            )


class PremiumButton(ui.Button["ui.LayoutView"]):
    def __init__(self, bot: "ArchitectBot") -> None:
        super().__init__(
            label="Premium freischalten",
            style=discord.ButtonStyle.secondary,
            emoji="💎",
            custom_id="architect:premium",
        )
        self.bot = bot

    async def callback(self, interaction: discord.Interaction) -> None:
        if self.bot.premium.has_access(
            interaction.guild.id if interaction.guild else None, interaction.user.id
        ):
            await interaction.response.send_message(
                view=notice(
                    "Bereits freigeschaltet",
                    "Premium ist für dich aktiv.",
                    tone="premium",
                    hint=f"Öffne {COMMAND_PREFIX}start erneut, "
                    "um alle Vorlagen zu sehen.",
                ),
                ephemeral=True,
            )
            return
        await interaction.response.send_modal(PremiumModal(self.bot))


# --------------------------------------------------------------------------- #
# Build confirmation
# --------------------------------------------------------------------------- #

class ConfirmView(ui.LayoutView):
    """Mode picker shown after a template was selected."""

    def __init__(
        self,
        bot: "ArchitectBot",
        template: Template,
        *,
        write_intros: bool = True,
    ) -> None:
        super().__init__(timeout=600)
        self.bot = bot
        self.template = template
        # Startnachrichten sind standardmaessig an, aber abschaltbar.
        self.write_intros = write_intros
        self._compose()

    def _compose(self) -> None:
        """Baut den Inhalt auf. Wird beim Umschalten erneut aufgerufen."""

        template = self.template
        self.clear_items()

        container = ui.Container(accent_colour=discord.Colour(template.accent))
        container.add_item(
            ui.TextDisplay(
                f"### {template.emoji}  {template.name}\n"
                "-# Wie soll die Vorlage angewendet werden?"
            )
        )
        container.add_item(RULE())
        container.add_item(
            ui.TextDisplay(
                quote(
                    "**Ergänzen**  ·  empfohlen",
                    "Fügt nur hinzu, was fehlt. Bestehende Kanäle, Rollen und "
                    "Berechtigungen bleiben unangetastet.",
                )
            )
        )
        container.add_item(SPACE())
        container.add_item(
            ui.TextDisplay(
                quote(
                    "**Neu aufsetzen**",
                    "Löscht alle Kanäle und Rollen, die der Bot entfernen darf, "
                    "und baut die Vorlage frisch auf.",
                    "Das lässt sich nicht rückgängig machen.",
                )
            )
        )
        container.add_item(RULE())
        container.add_item(
            ui.TextDisplay(
                "-# "
                + stat_line(
                    [
                        ("Kategorien", template.category_count),
                        ("Kanäle", template.channel_count),
                        ("Rollen", f"{BASE_ROLE_COUNT} + {len(template.roles)}"),
                    ]
                )
            )
        )

        container.add_item(SPACE())
        container.add_item(ui.TextDisplay(self._intro_line()))

        row = ui.ActionRow()
        row.add_item(_ModeButton(self, BuildMode.EXTEND))
        row.add_item(_ModeButton(self, BuildMode.REBUILD))
        row.add_item(_CancelButton())
        container.add_item(row)

        toggle_row = ui.ActionRow()
        toggle_row.add_item(_IntroToggle(self))
        container.add_item(toggle_row)

        container.add_item(footer())
        self.add_item(container)

    def _intro_line(self) -> str:
        if self.write_intros:
            return (
                "-# In jeden Textkanal kommt eine angeheftete Startnachricht, "
                "die den Zweck des Kanals erklärt."
            )
        return "-# Die Kanäle bleiben leer — es wird nichts hineingeschrieben."


class _IntroToggle(ui.Button["ConfirmView"]):
    """Schaltet die Startnachrichten an und aus."""

    def __init__(self, parent: ConfirmView) -> None:
        on = parent.write_intros
        super().__init__(
            label="Startnachrichten: an" if on else "Startnachrichten: aus",
            style=discord.ButtonStyle.secondary,
        )
        self.screen = parent

    async def callback(self, interaction: discord.Interaction) -> None:
        screen = self.screen
        await interaction.response.edit_message(
            view=ConfirmView(
                screen.bot, screen.template, write_intros=not screen.write_intros
            )
        )


class _ModeButton(ui.Button["ConfirmView"]):
    def __init__(self, parent: ConfirmView, mode: BuildMode) -> None:
        extend = mode is BuildMode.EXTEND
        super().__init__(
            label="Ergänzen" if extend else "Neu aufsetzen",
            # Nur die zerstoerende Aktion ist rot. Die empfohlene bleibt
            # zurueckhaltend, damit die Farbe eine Warnung bleibt.
            style=discord.ButtonStyle.primary if extend else discord.ButtonStyle.danger,
        )
        self.screen = parent
        self.mode = mode

    async def callback(self, interaction: discord.Interaction) -> None:
        await _run_build(
            interaction,
            self.screen.bot,
            self.screen.template,
            self.mode,
            write_intros=self.screen.write_intros,
        )


class _CancelButton(ui.Button["ConfirmView"]):
    def __init__(self) -> None:
        super().__init__(label="Abbrechen", style=discord.ButtonStyle.secondary)

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.edit_message(
            view=notice("Abgebrochen", "Es wurde nichts verändert.", tone="neutral")
        )


# --------------------------------------------------------------------------- #
# Build execution
# --------------------------------------------------------------------------- #

def _progress_view(template: Template, label: str, step: int, total: int) -> ui.LayoutView:
    container = ui.Container(accent_colour=discord.Colour(COLOR_BRAND))
    container.add_item(
        ui.TextDisplay(
            f"### {template.name} wird eingerichtet\n"
            f"-# Schritt {step} von {total}"
        )
    )
    container.add_item(RULE())
    container.add_item(ui.TextDisplay(quote(progress_bar(step, total), label)))
    view = ui.LayoutView(timeout=None)
    view.add_item(container)
    return view


def _report_view(
    template: Template,
    report: BuildReport,
    bot: "ArchitectBot | None" = None,
    guild: discord.Guild | None = None,
) -> ui.LayoutView:
    rebuilt = report.mode is BuildMode.REBUILD
    container = ui.Container(accent_colour=discord.Colour(COLOR_SUCCESS))
    container.add_item(
        ui.TextDisplay(
            f"### {template.name} steht\n"
            f"-# {'Server neu aufgesetzt' if rebuilt else 'Vorlage ergänzt'}"
        )
    )
    container.add_item(RULE())

    lines = [
        "**Erstellt**",
        stat_line(
            [
                ("Rollen", report.roles_created),
                ("Kategorien", report.categories_created),
                ("Kanäle", report.channels_created),
            ]
        ),
    ]

    if rebuilt and (report.deleted_channels or report.deleted_roles):
        lines += [
            "",
            "**Entfernt**",
            stat_line(
                [
                    ("Kanäle", report.deleted_channels),
                    ("Rollen", report.deleted_roles),
                ]
            ),
        ]

    if report.roles_updated or report.channels_updated:
        lines += [
            "",
            "**Aktualisiert**",
            stat_line(
                [
                    ("Rollen", report.roles_updated),
                    ("Kanäle", report.channels_updated),
                ]
            ),
        ]

    if report.messages_posted or report.messages_updated:
        written = [("Startnachrichten", report.messages_posted)]
        if report.messages_pinned:
            written.append(("angeheftet", report.messages_pinned))
        if report.messages_updated:
            written.append(("aktualisiert", report.messages_updated))
        lines += ["", "**Geschrieben**", stat_line(written)]

    container.add_item(ui.TextDisplay(quote(*lines)))

    if report.warnings:
        container.add_item(RULE())
        container.add_item(ui.TextDisplay("**Hinweise**"))
        container.add_item(ui.TextDisplay(quote(*report.warnings[:4])))

    container.add_item(RULE())
    if report.messages_posted or report.messages_updated:
        closing = (
            "-# Jeder Textkanal hat eine angeheftete Startnachricht. "
            "Sie lässt sich jederzeit bearbeiten oder löschen."
        )
    else:
        closing = (
            "-# Es wurde ausschließlich die Struktur angelegt. "
            "In die Kanäle wurden keine Nachrichten geschrieben."
        )
    container.add_item(ui.TextDisplay(closing))

    # Direkt weiter zum Regelwerk — der Kanal steht jetzt, ist aber leer.
    if bot is not None and guild is not None:
        from .rules import find_rules_channel

        rules_channel = find_rules_channel(guild)
        if rules_channel is not None:
            container.add_item(RULE())
            container.add_item(
                ui.TextDisplay(
                    quote(
                        "**Nächster Schritt**",
                        f"{rules_channel.mention} wartet noch auf ein Regelwerk. "
                        f"Es stehen {RULESET_COUNT} Vorlagen bereit — "
                        "oder du schreibst dein eigenes.",
                    )
                )
            )
            row = ui.ActionRow()
            row.add_item(_OpenRulesButton(bot, rules_channel))
            container.add_item(row)

    container.add_item(footer())

    view = ui.LayoutView(timeout=None)
    view.add_item(container)
    return view


class _OpenRulesButton(ui.Button["ui.LayoutView"]):
    """Fuehrt vom fertigen Server direkt zum Regelwerk-Assistenten."""

    def __init__(self, bot: "ArchitectBot", channel: discord.TextChannel) -> None:
        super().__init__(
            label="Regelwerk einrichten",
            style=discord.ButtonStyle.primary,
            emoji="📜",
        )
        self.bot = bot
        self.channel = channel

    async def callback(self, interaction: discord.Interaction) -> None:
        from .rules import RulesetPicker

        await interaction.response.send_message(
            view=RulesetPicker(self.bot, self.channel), ephemeral=True
        )


async def _run_build(
    interaction: discord.Interaction,
    bot: "ArchitectBot",
    template: Template,
    mode: BuildMode,
    *,
    write_intros: bool = True,
) -> None:
    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message(
            view=notice(
                "Nur auf Servern verfügbar",
                "Diese Aktion funktioniert nur innerhalb eines Servers.",
                tone="error",
            ),
            ephemeral=True,
        )
        return

    if not _can_manage(interaction.user):
        await interaction.response.send_message(
            view=notice(
                "Keine Berechtigung", _MANAGE_HINT, tone="error", hint=_MANAGE_REASON
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
    builder = ServerBuilder(guild, template)

    try:
        builder.preflight()
    except BuildError as exc:
        bot.active_builds.discard(guild.id)
        await interaction.response.edit_message(
            view=notice("Einrichtung nicht möglich", str(exc), tone="error")
        )
        return

    await interaction.response.edit_message(
        view=_progress_view(template, "Start", 0, template.category_count + 1)
    )

    # Throttle progress edits: Discord rate limits message edits per channel.
    last_edit = 0.0
    loop = asyncio.get_running_loop()

    async def on_progress(label: str, step: int, total: int) -> None:
        nonlocal last_edit
        now = loop.time()
        if now - last_edit < 1.6 and step < total:
            return
        last_edit = now
        try:
            await interaction.edit_original_response(
                view=_progress_view(template, label, step, total)
            )
        except discord.HTTPException:
            pass

    try:
        report = await builder.apply(
            mode, progress=on_progress, write_intros=write_intros
        )
        await interaction.edit_original_response(
            view=_report_view(template, report, bot, guild)
        )
        LOGGER.info(
            "Build fertig guild=%s template=%s mode=%s created=%d",
            guild.id,
            template.key,
            mode.value,
            report.total_created,
        )
    except BuildError as exc:
        await interaction.edit_original_response(
            view=notice("Einrichtung abgebrochen", str(exc), tone="error")
        )
    except discord.Forbidden:
        LOGGER.exception("Forbidden während Build guild=%s", guild.id)
        await interaction.edit_original_response(
            view=notice(
                "Discord hat die Aktion abgelehnt",
                "Dem Bot fehlen Berechtigungen.",
                tone="error",
                hint="Die Bot-Rolle muss über den zu verwaltenden Rollen stehen. "
                "Benötigt werden Rollen verwalten und Kanäle verwalten.",
            )
        )
    except discord.HTTPException as exc:
        LOGGER.exception("HTTP-Fehler während Build guild=%s", guild.id)
        await interaction.edit_original_response(
            view=notice(
                "Discord meldet einen Fehler",
                f"```{exc.text or exc}```",
                tone="error",
            )
        )
    finally:
        bot.active_builds.discard(guild.id)


# --------------------------------------------------------------------------- #
# Template preview
# --------------------------------------------------------------------------- #

def _preview_views(template: Template) -> list[ui.LayoutView]:
    """Vollstaendige Kanalliste, aufgeteilt auf mehrere Nachrichten.

    Jede Kategorie wird zu einem Blockzitat: die Ueberschrift bleibt links,
    die Kanaele stehen eingerueckt darunter. Das ergibt eine ruhige Spalte
    statt einer flachen Aufzaehlung.
    """

    views: list[ui.LayoutView] = []

    def new_container(continued: bool = False) -> ui.Container:
        box = ui.Container(accent_colour=discord.Colour(template.accent))
        suffix = "  ·  Fortsetzung" if continued else ""
        box.add_item(
            ui.TextDisplay(
                f"### {template.emoji}  {template.name}\n"
                f"-# Alle Kategorien und Kanäle{suffix}"
            )
        )
        box.add_item(RULE())
        return box

    container = new_container()
    budget = 200

    for category in template.categories:
        badge = visibility_badge(category.visibility)
        head = f"**{category.display_name}**"
        if badge:
            head += f"  ·  {badge}"

        rows = [head]
        for channel in category.channels:
            suffix = ""
            if channel.kind.is_voice_like and channel.user_limit:
                suffix = f"  `{channel.user_limit}`"
            rows.append(f"{kind_icon(channel.kind)} {channel.display_name}{suffix}")
        block = quote(*rows)

        # 4000 Zeichen pro Nachricht ueber alle TextDisplays — rechtzeitig
        # eine neue Nachricht beginnen.
        if budget + len(block) > 3600:
            container.add_item(footer())
            view = ui.LayoutView(timeout=None)
            view.add_item(container)
            views.append(view)

            container = new_container(continued=True)
            budget = 150

        container.add_item(ui.TextDisplay(block))
        budget += len(block)

    container.add_item(footer())
    view = ui.LayoutView(timeout=None)
    view.add_item(container)
    views.append(view)
    return views


class DetailView(ui.LayoutView):
    """Template detail screen with Preview / Apply actions."""

    def __init__(
        self,
        bot: "ArchitectBot",
        template: Template,
        *,
        write_intros: bool = True,
    ) -> None:
        super().__init__(timeout=600)
        self.bot = bot
        self.template = template
        # Startnachrichten sind standardmaessig an, aber abschaltbar.
        self.write_intros = write_intros
        self._compose()

    def _compose(self) -> None:
        """Baut den Inhalt auf. Wird beim Umschalten erneut aufgerufen."""

        template = self.template
        self.clear_items()

        container = ui.Container(accent_colour=discord.Colour(template.accent))
        container.add_item(
            ui.TextDisplay(
                f"### {template.emoji}  {template.name}\n"
                f"-# {'Premium' if template.premium else 'Kostenlos'}"
                f"  ·  {template.tagline}"
            )
        )
        container.add_item(RULE())
        container.add_item(ui.TextDisplay(quote(template.description)))

        if template.highlights:
            container.add_item(SPACE())
            container.add_item(ui.TextDisplay(quote(*template.highlights)))

        container.add_item(RULE())
        container.add_item(
            ui.TextDisplay(
                "-# "
                + stat_line(
                    [
                        ("Kategorien", template.category_count),
                        ("Textkanäle", template.text_count),
                        ("Sprachkanäle", template.voice_count),
                        ("Rollen", f"{BASE_ROLE_COUNT} + {len(template.roles)}"),
                    ]
                )
            )
        )

        row = ui.ActionRow()
        row.add_item(_PreviewButton(self))
        row.add_item(_ApplyButton(self))
        container.add_item(row)
        container.add_item(footer())
        self.add_item(container)


class _PreviewButton(ui.Button["DetailView"]):
    def __init__(self, parent: DetailView) -> None:
        super().__init__(label="Struktur ansehen", style=discord.ButtonStyle.secondary)
        self.screen = parent

    async def callback(self, interaction: discord.Interaction) -> None:
        views = _preview_views(self.screen.template)
        await interaction.response.send_message(view=views[0], ephemeral=True)
        for extra in views[1:]:
            await interaction.followup.send(view=extra, ephemeral=True)


class _ApplyButton(ui.Button["DetailView"]):
    def __init__(self, parent: DetailView) -> None:
        super().__init__(label="Anwenden", style=discord.ButtonStyle.primary)
        self.screen = parent

    async def callback(self, interaction: discord.Interaction) -> None:
        if not _can_manage(interaction.user):
            await interaction.response.send_message(
                view=notice(
                    "Keine Berechtigung",
                    _MANAGE_HINT,
                    tone="error",
                    hint=_MANAGE_REASON,
                ),
                ephemeral=True,
            )
            return
        await interaction.response.edit_message(
            view=ConfirmView(self.screen.bot, self.screen.template)
        )


# --------------------------------------------------------------------------- #
# Start menu
# --------------------------------------------------------------------------- #

class TemplateSelect(ui.Select["StartView"]):
    def __init__(self, bot: "ArchitectBot", templates: list[Template], *, premium: bool) -> None:
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
            placeholder="Vorlage auswählen",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="architect:select",
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

        if template.premium and not self.bot.premium.has_access(
            interaction.guild.id if interaction.guild else None, interaction.user.id
        ):
            await interaction.response.send_message(
                view=notice(
                    "Premium erforderlich",
                    f"**{template.name}** ist eine Premium-Vorlage.",
                    tone="premium",
                    hint="Im Hauptmenü auf Premium freischalten klicken "
                    "und den Key eingeben.",
                ),
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            view=DetailView(self.bot, template), ephemeral=True
        )


class StartView(ui.LayoutView):
    """The screen behind ``!start`` / ``/start``."""

    def __init__(self, bot: "ArchitectBot", *, premium: bool) -> None:
        super().__init__(timeout=None)
        self.bot = bot

        registry = bot.registry
        free = registry.free
        locked = registry.premium
        available = registry.available_to(premium=premium)
        totals = registry.totals

        container = ui.Container(
            accent_colour=discord.Colour(COLOR_PREMIUM if premium else COLOR_BRAND)
        )

        container.add_item(
            ui.TextDisplay(f"## {BRAND_NAME}\n-# {BRAND_TAGLINE}")
        )
        container.add_item(RULE())

        # --- kostenlos -----------------------------------------------------
        container.add_item(ui.TextDisplay("**Kostenlos**"))
        container.add_item(
            ui.TextDisplay(
                quote(
                    *(
                        f"{t.emoji}  **{t.name}** — {t.tagline}\n"
                        f"-# {t.category_count} Kategorien  ·  "
                        f"{t.channel_count} Kanäle  ·  {t.voice_count} Sprachkanäle"
                        for t in free
                    )
                )
            )
        )

        # --- premium -------------------------------------------------------
        if locked:
            container.add_item(SPACE())
            container.add_item(
                ui.TextDisplay(
                    "**Premium**"
                    + ("  ·  freigeschaltet" if premium else f"  ·  {len(locked)} weitere")
                )
            )
            container.add_item(
                ui.TextDisplay(
                    quote(
                        *(
                            f"{t.emoji}  **{t.name}** — {t.tagline}"
                            if premium
                            else f"{t.emoji}  {t.name} — {t.tagline}"
                            for t in locked
                        )
                    )
                )
            )

        container.add_item(RULE())

        # --- selector ------------------------------------------------------
        select_row = ui.ActionRow()
        select_row.add_item(TemplateSelect(bot, available, premium=premium))
        container.add_item(select_row)

        if not premium:
            button_row = ui.ActionRow()
            button_row.add_item(PremiumButton(bot))
            container.add_item(button_row)

        container.add_item(
            footer(f"{totals['templates']} Vorlagen  ·  Vorschau vor dem Anwenden")
        )
        self.add_item(container)


def build_start_view(bot: "ArchitectBot", *, premium: bool) -> StartView:
    return StartView(bot, premium=premium)


# --------------------------------------------------------------------------- #
# Automatische Einrichtung ueber einen Partner-Bot
# --------------------------------------------------------------------------- #

def partner_summary_view(template: Template, report: BuildReport) -> ui.LayoutView:
    """Zusammenfassung nach der automatischen Einrichtung.

    Sie muss ohne Vorgeschichte verstaendlich sein: die Leser haben den Bot
    nicht selbst gestartet und sehen ihn hier zum ersten Mal.
    """

    container = ui.Container(accent_colour=discord.Colour(COLOR_SUCCESS))
    container.add_item(
        ui.TextDisplay(
            f"### Server eingerichtet\n-# Vorlage: {template.emoji}  {template.name}"
        )
    )
    container.add_item(RULE())

    lines = [
        "**Angelegt**",
        stat_line(
            [
                ("Kategorien", report.categories_created),
                ("Kanäle", report.channels_created),
                ("Rollen", report.roles_created),
            ]
        ),
    ]
    if report.messages_posted:
        lines += [
            "",
            f"In {report.messages_posted} Kanälen steht eine angeheftete "
            "Nachricht, die den Zweck des Kanals erklärt.",
        ]
    container.add_item(ui.TextDisplay(quote(*lines)))

    # Was nicht geklappt hat, gehoert genauso in den Bericht wie der Erfolg.
    if report.warnings:
        container.add_item(RULE())
        container.add_item(ui.TextDisplay("**Nicht vollständig übernommen**"))
        container.add_item(ui.TextDisplay(quote(*report.warnings[:4])))

    container.add_item(RULE())
    container.add_item(
        ui.TextDisplay(
            quote(
                "**Nächste Schritte**",
                f"Weitere Vorlagen ansehen: `{COMMAND_PREFIX}start`",
                f"Regelwerk einrichten: `{COMMAND_PREFIX}regeln`",
            )
        )
    )
    container.add_item(
        ui.TextDisplay(
            "-# Bestehende Kanäle und Rollen wurden nicht verändert — "
            "es wurde nur ergänzt."
        )
    )
    container.add_item(footer())

    view = ui.LayoutView(timeout=None)
    view.add_item(container)
    return view
