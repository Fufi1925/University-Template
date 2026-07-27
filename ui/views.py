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
    COLOR_BRAND,
    COLOR_DANGER,
    COLOR_NEUTRAL,
    COLOR_PREMIUM,
    COLOR_SUCCESS,
)
from core.builder import BuildError, BuildMode, BuildReport, ServerBuilder
from core.schema import Template
from .components import (
    RULE,
    SPACE,
    footer,
    kind_icon,
    notice,
    progress_bar,
    stat_line,
    template_card,
    visibility_badge,
)

if TYPE_CHECKING:
    from bot import ArchitectBot

LOGGER = logging.getLogger("architect.ui")

__all__ = ["StartView", "build_start_view"]

_MANAGE_HINT = (
    "Dafür brauchst du die Berechtigung **Server verwalten**. "
    "So kann niemand den Server ungefragt umbauen."
)


def _can_manage(user: discord.abc.User | discord.Member) -> bool:
    return isinstance(user, discord.Member) and user.guild_permissions.manage_guild


# --------------------------------------------------------------------------- #
# Premium unlock
# --------------------------------------------------------------------------- #

class PremiumModal(ui.Modal, title="Premium freischalten"):
    """Key prompt. The key is verified in constant time and never stored."""

    key = ui.TextInput(
        label="Premium-Key",
        placeholder="z. B. Vexo x Fufi KEY 2354",
        required=True,
        min_length=4,
        max_length=100,
    )

    def __init__(self, bot: "ArchitectBot") -> None:
        super().__init__(timeout=300)
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction) -> None:
        supplied = str(self.key.value)

        if not self.bot.premium.verify(supplied):
            await interaction.response.send_message(
                view=notice(
                    "❌  Key ungültig",
                    "Dieser Key wurde nicht erkannt. Achte auf Leerzeichen und "
                    "Groß-/Kleinschreibung und versuche es erneut.",
                    tone="error",
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
        listing = "\n".join(
            f"{tpl.emoji}  **{tpl.name}** — {tpl.tagline}" for tpl in unlocked
        )
        container = ui.Container(accent_colour=discord.Colour(COLOR_PREMIUM))
        container.add_item(
            ui.TextDisplay(
                "## 💎  Premium aktiv\n"
                f"-# Freigeschaltet für {interaction.user.mention}"
            )
        )
        container.add_item(RULE())
        container.add_item(
            ui.TextDisplay(f"**{len(unlocked)} zusätzliche Templates** stehen dir jetzt offen:")
        )
        container.add_item(ui.TextDisplay(listing))
        container.add_item(RULE())
        container.add_item(
            ui.TextDisplay(
                "Öffne das Menü mit `!start` erneut — die Premium-Vorlagen "
                "erscheinen dort ab sofort direkt im Dropdown."
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
                view=notice("❌  Fehler", "Bitte versuche es erneut.", tone="error"),
                ephemeral=True,
            )


class PremiumButton(ui.Button["ui.LayoutView"]):
    def __init__(self, bot: "ArchitectBot") -> None:
        super().__init__(
            label="Sichere dir jetzt Premium um mehr Templates zu bekommen",
            style=discord.ButtonStyle.success,
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
                    "💎  Bereits freigeschaltet",
                    "Du hast Premium schon aktiviert. Öffne `!start` erneut, "
                    "um alle Vorlagen im Dropdown zu sehen.",
                    tone="premium",
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

    def __init__(self, bot: "ArchitectBot", template: Template) -> None:
        super().__init__(timeout=600)
        self.bot = bot
        self.template = template

        container = ui.Container(accent_colour=discord.Colour(template.accent))
        container.add_item(
            ui.TextDisplay(
                f"## {template.emoji}  {template.name}\n"
                f"-# Wie soll die Vorlage angewendet werden?"
            )
        )
        container.add_item(RULE())
        container.add_item(
            ui.TextDisplay(
                "**➕  Ergänzen** — *empfohlen*\n"
                "Fügt nur hinzu, was fehlt. Bestehende Kanäle, Rollen und "
                "Berechtigungen bleiben unangetastet."
            )
        )
        container.add_item(SPACE())
        container.add_item(
            ui.TextDisplay(
                "**🧨  Neu aufsetzen**\n"
                "Löscht **alle** Kanäle und Rollen, die der Bot löschen darf, "
                "und baut die Vorlage frisch auf. Das lässt sich **nicht** "
                "rückgängig machen."
            )
        )
        container.add_item(RULE())
        container.add_item(
            ui.TextDisplay(
                stat_line(
                    [
                        ("Kategorien", template.category_count),
                        ("Kanäle", template.channel_count),
                        ("Rollen", "13 + " + str(len(template.roles))),
                    ]
                )
            )
        )

        row = ui.ActionRow()
        row.add_item(_ModeButton(self, BuildMode.EXTEND))
        row.add_item(_ModeButton(self, BuildMode.REBUILD))
        row.add_item(_CancelButton())
        container.add_item(row)
        container.add_item(footer())
        self.add_item(container)


class _ModeButton(ui.Button["ConfirmView"]):
    def __init__(self, parent: ConfirmView, mode: BuildMode) -> None:
        extend = mode is BuildMode.EXTEND
        super().__init__(
            label="Ergänzen" if extend else "Neu aufsetzen",
            style=discord.ButtonStyle.success if extend else discord.ButtonStyle.danger,
            emoji="➕" if extend else "🧨",
        )
        self.screen = parent
        self.mode = mode

    async def callback(self, interaction: discord.Interaction) -> None:
        await _run_build(interaction, self.screen.bot, self.screen.template, self.mode)


class _CancelButton(ui.Button["ConfirmView"]):
    def __init__(self) -> None:
        super().__init__(label="Abbrechen", style=discord.ButtonStyle.secondary, emoji="✖️")

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.edit_message(
            view=notice("✖️  Abgebrochen", "Es wurde nichts verändert.", tone="neutral")
        )


# --------------------------------------------------------------------------- #
# Build execution
# --------------------------------------------------------------------------- #

def _progress_view(template: Template, label: str, step: int, total: int) -> ui.LayoutView:
    container = ui.Container(accent_colour=discord.Colour(COLOR_BRAND))
    container.add_item(ui.TextDisplay(f"## ⚙️  {template.name} wird gebaut"))
    container.add_item(RULE())
    container.add_item(ui.TextDisplay(progress_bar(step, total)))
    container.add_item(ui.TextDisplay(f"-# Schritt {step}/{total} · {label}"))
    view = ui.LayoutView(timeout=None)
    view.add_item(container)
    return view


def _report_view(template: Template, report: BuildReport) -> ui.LayoutView:
    rebuilt = report.mode is BuildMode.REBUILD
    container = ui.Container(accent_colour=discord.Colour(COLOR_SUCCESS))
    container.add_item(
        ui.TextDisplay(
            f"## ✅  {template.name} steht\n"
            f"-# {'Server neu aufgesetzt' if rebuilt else 'Vorlage ergänzt'}"
        )
    )
    container.add_item(RULE())
    container.add_item(
        ui.TextDisplay(
            "**Erstellt**\n"
            + stat_line(
                [
                    ("Rollen", report.roles_created),
                    ("Kategorien", report.categories_created),
                    ("Kanäle", report.channels_created),
                ]
            )
        )
    )

    if rebuilt and (report.deleted_channels or report.deleted_roles):
        container.add_item(SPACE())
        container.add_item(
            ui.TextDisplay(
                "**Entfernt**\n"
                + stat_line(
                    [
                        ("Kanäle", report.deleted_channels),
                        ("Rollen", report.deleted_roles),
                    ]
                )
            )
        )

    if report.roles_updated or report.channels_updated:
        container.add_item(SPACE())
        container.add_item(
            ui.TextDisplay(
                "**Aktualisiert**\n"
                + stat_line(
                    [
                        ("Rollen", report.roles_updated),
                        ("Kanäle", report.channels_updated),
                    ]
                )
            )
        )

    if report.warnings:
        container.add_item(RULE())
        container.add_item(
            ui.TextDisplay("**⚠️  Hinweise**\n" + "\n".join(f"› {w}" for w in report.warnings[:4]))
        )

    container.add_item(RULE())
    container.add_item(
        ui.TextDisplay(
            "-# Der Bot legt ausschließlich die Struktur an und schreibt "
            "keine Nachrichten in deine Kanäle."
        )
    )
    container.add_item(footer())

    view = ui.LayoutView(timeout=None)
    view.add_item(container)
    return view


async def _run_build(
    interaction: discord.Interaction,
    bot: "ArchitectBot",
    template: Template,
    mode: BuildMode,
) -> None:
    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message(
            view=notice("❌  Nur auf Servern", "Das funktioniert nur in einem Server.", tone="error"),
            ephemeral=True,
        )
        return

    if not _can_manage(interaction.user):
        await interaction.response.send_message(
            view=notice("🔐  Keine Berechtigung", _MANAGE_HINT, tone="error"), ephemeral=True
        )
        return

    if guild.id in bot.active_builds:
        await interaction.response.send_message(
            view=notice(
                "⏳  Läuft bereits",
                "Für diesen Server läuft gerade ein Setup. Warte, bis es fertig ist.",
                tone="error",
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
            view=notice("🚫  Setup nicht möglich", str(exc), tone="error")
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
        report = await builder.apply(mode, progress=on_progress)
        await interaction.edit_original_response(view=_report_view(template, report))
        LOGGER.info(
            "Build fertig guild=%s template=%s mode=%s created=%d",
            guild.id,
            template.key,
            mode.value,
            report.total_created,
        )
    except BuildError as exc:
        await interaction.edit_original_response(
            view=notice("🚫  Setup abgebrochen", str(exc), tone="error")
        )
    except discord.Forbidden:
        LOGGER.exception("Forbidden während Build guild=%s", guild.id)
        await interaction.edit_original_response(
            view=notice(
                "🚫  Discord hat abgelehnt",
                "Dem Bot fehlen Rechte. Prüfe, ob die Bot-Rolle **über** den zu "
                "verwaltenden Rollen steht und ob **Rollen verwalten** sowie "
                "**Kanäle verwalten** aktiv sind.",
                tone="error",
            )
        )
    except discord.HTTPException as exc:
        LOGGER.exception("HTTP-Fehler während Build guild=%s", guild.id)
        await interaction.edit_original_response(
            view=notice("🚫  Discord-Fehler", f"```{exc.text or exc}```", tone="error")
        )
    finally:
        bot.active_builds.discard(guild.id)


# --------------------------------------------------------------------------- #
# Template preview
# --------------------------------------------------------------------------- #

def _preview_views(template: Template) -> list[ui.LayoutView]:
    """Full channel listing, split across messages to respect the 4000-char cap."""

    views: list[ui.LayoutView] = []
    container = ui.Container(accent_colour=discord.Colour(template.accent))
    container.add_item(
        ui.TextDisplay(
            f"## {template.emoji}  {template.name}\n-# Komplette Struktur im Überblick"
        )
    )
    container.add_item(RULE())
    budget = 200

    for category in template.categories:
        badge = visibility_badge(category.visibility)
        lines = [f"**{category.display_name}** {badge}".rstrip()]
        for channel in category.channels:
            suffix = ""
            if channel.kind.is_voice_like and channel.user_limit:
                suffix = f" `{channel.user_limit}`"
            lines.append(f"{kind_icon(channel.kind)} {channel.display_name}{suffix}")
        block = "\n".join(lines)

        # 4000 chars per message across all TextDisplays — start a new message
        # before we hit it.
        if budget + len(block) > 3600:
            container.add_item(footer())
            view = ui.LayoutView(timeout=None)
            view.add_item(container)
            views.append(view)

            container = ui.Container(accent_colour=discord.Colour(template.accent))
            container.add_item(ui.TextDisplay(f"### {template.emoji}  {template.name} — Fortsetzung"))
            container.add_item(RULE())
            budget = 100

        container.add_item(ui.TextDisplay(block))
        budget += len(block)

    container.add_item(footer())
    view = ui.LayoutView(timeout=None)
    view.add_item(container)
    views.append(view)
    return views


class DetailView(ui.LayoutView):
    """Template detail screen with Preview / Apply actions."""

    def __init__(self, bot: "ArchitectBot", template: Template) -> None:
        super().__init__(timeout=600)
        self.bot = bot
        self.template = template

        container = ui.Container(accent_colour=discord.Colour(template.accent))
        container.add_item(
            ui.TextDisplay(
                f"## {template.emoji}  {template.name}\n"
                f"-# {'💎 Premium' if template.premium else '🆓 Free'}  ·  {template.tagline}"
            )
        )
        container.add_item(RULE())
        container.add_item(ui.TextDisplay(template.description))
        container.add_item(SPACE())
        container.add_item(
            ui.TextDisplay(
                stat_line(
                    [
                        ("Kategorien", template.category_count),
                        ("Textkanäle", template.text_count),
                        ("Voice", template.voice_count),
                        ("Extra-Rollen", len(template.roles)),
                    ]
                )
            )
        )

        if template.highlights:
            container.add_item(RULE())
            container.add_item(
                ui.TextDisplay("\n".join(f"› {line}" for line in template.highlights))
            )

        container.add_item(RULE())
        row = ui.ActionRow()
        row.add_item(_PreviewButton(self))
        row.add_item(_ApplyButton(self))
        container.add_item(row)
        container.add_item(footer())
        self.add_item(container)


class _PreviewButton(ui.Button["DetailView"]):
    def __init__(self, parent: DetailView) -> None:
        super().__init__(label="Alle Kanäle ansehen", style=discord.ButtonStyle.secondary, emoji="🔍")
        self.screen = parent

    async def callback(self, interaction: discord.Interaction) -> None:
        views = _preview_views(self.screen.template)
        await interaction.response.send_message(view=views[0], ephemeral=True)
        for extra in views[1:]:
            await interaction.followup.send(view=extra, ephemeral=True)


class _ApplyButton(ui.Button["DetailView"]):
    def __init__(self, parent: DetailView) -> None:
        super().__init__(
            label="Auf diesem Server anwenden", style=discord.ButtonStyle.primary, emoji="🚀"
        )
        self.screen = parent

    async def callback(self, interaction: discord.Interaction) -> None:
        if not _can_manage(interaction.user):
            await interaction.response.send_message(
                view=notice("🔐  Keine Berechtigung", _MANAGE_HINT, tone="error"), ephemeral=True
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
            placeholder=(
                "💎  Wähle aus allen Templates …" if premium else "✨  Wähle dein Template …"
            ),
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
                view=notice("❌  Unbekannt", "Dieses Template gibt es nicht mehr.", tone="error"),
                ephemeral=True,
            )
            return

        if template.premium and not self.bot.premium.has_access(
            interaction.guild.id if interaction.guild else None, interaction.user.id
        ):
            await interaction.response.send_message(
                view=notice(
                    "💎  Premium erforderlich",
                    f"**{template.name}** gehört zu den Premium-Vorlagen. "
                    "Klicke im Hauptmenü auf den grünen Premium-Button und gib "
                    "deinen Key ein, um sie freizuschalten.",
                    tone="premium",
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
            ui.TextDisplay(
                f"# {BRAND_NAME}\n"
                f"-# {BRAND_TAGLINE}  ·  Small Caps  ·  Multi-Language  ·  Components V2"
            )
        )
        container.add_item(RULE(large=True))

        container.add_item(
            ui.TextDisplay(
                "Wähle unten eine Vorlage. Du siehst zuerst eine **Vorschau** — "
                "gebaut wird erst, wenn du es ausdrücklich bestätigst."
            )
        )
        container.add_item(SPACE())

        # --- free tier -----------------------------------------------------
        container.add_item(ui.TextDisplay("### 🆓  Kostenlos"))
        container.add_item(
            ui.TextDisplay(
                "\n".join(
                    f"{t.emoji}  **{t.name}** — {t.tagline}\n"
                    f"-# {t.category_count} Kategorien · {t.channel_count} Kanäle · {t.voice_count} Voice"
                    for t in free
                )
            )
        )

        # --- premium tier --------------------------------------------------
        if locked:
            container.add_item(RULE())
            container.add_item(
                ui.TextDisplay(
                    f"### 💎  Premium  {'· freigeschaltet' if premium else f'· {len(locked)} weitere'}"
                )
            )
            container.add_item(
                ui.TextDisplay(
                    "\n".join(
                        f"{'' if premium else '🔒 '}{t.emoji}  **{t.name}** — {t.tagline}"
                        for t in locked
                    )
                )
            )

        container.add_item(RULE(large=True))

        # --- selector ------------------------------------------------------
        select_row = ui.ActionRow()
        select_row.add_item(TemplateSelect(bot, available, premium=premium))
        container.add_item(select_row)

        if not premium:
            button_row = ui.ActionRow()
            button_row.add_item(PremiumButton(bot))
            container.add_item(button_row)

        container.add_item(
            footer(
                f"{totals['templates']} Templates · {totals['channels']} Kanäle insgesamt"
            )
        )
        self.add_item(container)


def build_start_view(bot: "ArchitectBot", *, premium: bool) -> StartView:
    return StartView(bot, premium=premium)
