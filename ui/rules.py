"""Regelwerk-Assistent.

Nach dem Bau einer Vorlage bietet der Bot an, den Regelkanal zu fuellen.
Der Ablauf entspricht bewusst dem der Templates, damit nichts neu gelernt
werden muss:

1. **Ergaenzen** — Regelwerk anhaengen, vorhandene Nachrichten bleiben
2. **Neu aufsetzen** — nur dieser eine Kanal wird geleert und neu befuellt
3. **Abbrechen** — nichts passiert, der Nutzer schreibt selbst
4. **Selbst erstellen** — Formular fuer ein eigenes Regelwerk mit zwei Bildern

Bei Option 4 entsteht ein Layout mit Bild oben rechts (``Section`` mit
``Thumbnail``) und einem zweiten Bild unter dem Text (``MediaGallery``).
"""

from __future__ import annotations

import contextlib
import logging
import re
from typing import TYPE_CHECKING

import discord
from discord import ui

from config import COLOR_BRAND, COLOR_SUCCESS
from core.rulesets import RULESETS, RuleLength, RuleSet, get_ruleset
from core.small_caps import strip_decoration

from .components import RULE, SPACE, field_value, footer, notice, quote
from .emojis import button_emoji

if TYPE_CHECKING:
    from bot import ArchitectBot

LOGGER = logging.getLogger("architect.rules")

__all__ = ["RULES_CHANNEL_HINTS", "RulesetPicker", "open_rules_assistant"]

# Namensbestandteile, an denen der Regelkanal erkannt wird.
RULES_CHANNEL_HINTS = ("serverregeln", "regeln", "regelwerk", "rules")

# Discord erlaubt 4000 Zeichen ueber alle TextDisplay-Komponenten hinweg.
_CHAR_BUDGET = 3600

# ... und hoechstens 40 Komponenten pro Nachricht. Jeder Paragraph kostet
# zwei davon (Abstand + Text), der Rahmen etwa sechs. Lange Regelwerke
# reissen dieses Limit, bevor sie das Zeichenlimit erreichen.
_COMPONENT_BUDGET = 34


def _can_manage(user: discord.abc.User | discord.Member) -> bool:
    return isinstance(user, discord.Member) and user.guild_permissions.manage_guild


def find_rules_channel(guild: discord.Guild) -> discord.TextChannel | None:
    """Den Regelkanal finden — auch wenn er in Small Caps benannt ist."""

    best: discord.TextChannel | None = None
    for channel in guild.text_channels:
        plain = strip_decoration(channel.name)
        for hint in RULES_CHANNEL_HINTS:
            if hint in plain:
                # Exakter Treffer schlaegt Teiltreffer.
                if plain.strip() == hint:
                    return channel
                best = best or channel
    return best


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #

def ruleset_views(ruleset: RuleSet, *, guild_name: str = "") -> list[ui.LayoutView]:
    """Ein Regelwerk als eine oder mehrere Nachrichten.

    Jeder Paragraph wird als ``§n • Titel`` mit Fliesstext gerendert. Reicht
    der Platz nicht, wird am Paragraphenrand geteilt — nie mitten in einem
    Paragraphen, damit keine Regel zerrissen wird.

    Die Nummerierung laeuft ueber alle Nachrichten durch: §12 bleibt §12,
    auch wenn es auf der zweiten Nachricht steht.
    """

    views: list[ui.LayoutView] = []

    def new_container(first: bool) -> ui.Container:
        box = ui.Container(accent_colour=discord.Colour(COLOR_BRAND))
        if first:
            heading = f"## {ruleset.emoji}  {ruleset.display_title}"
            subtitle = guild_name or ruleset.name
            box.add_item(ui.TextDisplay(f"{heading}\n-# {subtitle}"))
            if ruleset.intro:
                box.add_item(RULE())
                box.add_item(ui.TextDisplay(quote(ruleset.intro)))
        else:
            box.add_item(
                ui.TextDisplay(
                    f"-# {ruleset.emoji}  {ruleset.display_title} · Fortsetzung"
                )
            )
        box.add_item(RULE())
        return box

    container = new_container(True)
    used = len(ruleset.intro) + len(ruleset.display_title) + 100
    items = 4  # Ueberschrift, Trennlinien, spaeter Fusszeile

    for number, paragraph in enumerate(ruleset.paragraphs, start=1):
        lines = [f"**§{number} • {paragraph.title}**", paragraph.text]
        if paragraph.bullets:
            lines.append("")
            lines.extend(f"• {bullet}" for bullet in paragraph.bullets)
        block = quote(*lines)

        # Rechtzeitig eine neue Nachricht beginnen — der Paragraph bleibt
        # dabei immer zusammen. Beide Limits werden geprueft: lange Texte
        # reissen das Zeichenlimit, viele kurze das Komponentenlimit.
        if used + len(block) > _CHAR_BUDGET or items + 2 > _COMPONENT_BUDGET:
            container.add_item(footer(mark=True))
            view = ui.LayoutView(timeout=None)
            view.add_item(container)
            views.append(view)
            container = new_container(False)
            used = 120
            items = 4

        if number > 1:
            container.add_item(SPACE())
            items += 1
        container.add_item(ui.TextDisplay(block))
        items += 1
        used += len(block)

    if ruleset.closing:
        container.add_item(RULE())
        container.add_item(ui.TextDisplay(f"-# {ruleset.closing}"))

    container.add_item(footer(mark=True))
    view = ui.LayoutView(timeout=None)
    view.add_item(container)
    views.append(view)
    return views


def custom_rules_view(
    heading: str,
    body: str,
    top_image: str | None,
    bottom_image: str | None,
) -> ui.LayoutView:
    """Eigenes Regelwerk: Bild oben rechts, Text, Bild unten."""

    container = ui.Container(accent_colour=discord.Colour(COLOR_BRAND))
    lines = [line for line in body.splitlines() if line.strip()]

    if top_image:
        # Section stellt Text und Bild nebeneinander — das Bild sitzt rechts.
        section = ui.Section(
            ui.TextDisplay(f"## {heading}"),
            accessory=ui.Thumbnail(top_image),
        )
        container.add_item(section)
        container.add_item(RULE())
        if lines:
            container.add_item(ui.TextDisplay(quote(*lines)))
    else:
        container.add_item(ui.TextDisplay(f"## {heading}"))
        if lines:
            container.add_item(RULE())
            container.add_item(ui.TextDisplay(quote(*lines)))

    if bottom_image:
        container.add_item(RULE())
        container.add_item(
            ui.MediaGallery(discord.MediaGalleryItem(bottom_image))
        )

    container.add_item(footer(mark=True))
    view = ui.LayoutView(timeout=None)
    view.add_item(container)
    return view


# --------------------------------------------------------------------------- #
# Schreiben
# --------------------------------------------------------------------------- #

async def _purge_bot_messages(channel: discord.TextChannel, me: discord.Member) -> int:
    """Nur die eigenen Nachrichten entfernen — fremde bleiben unangetastet."""

    removed = 0
    try:
        async for message in channel.history(limit=100):
            if message.author.id != me.id:
                continue
            with contextlib.suppress(discord.HTTPException):
                await message.delete()
                removed += 1
    except (discord.Forbidden, discord.HTTPException):
        pass
    return removed


async def _post(
    interaction: discord.Interaction,
    channel: discord.TextChannel,
    views: list[ui.LayoutView],
    *,
    reset: bool,
) -> None:
    guild = interaction.guild
    me = guild.me if guild else None
    removed = 0

    if reset and me is not None:
        removed = await _purge_bot_messages(channel, me)

    posted = 0
    first: discord.Message | None = None
    for view in views:
        try:
            # Kein content= — Components V2 verbietet das Feld.
            message = await channel.send(view=view)
            posted += 1
            first = first or message
        except discord.Forbidden:
            await interaction.edit_original_response(
                view=notice(
                    "Keine Schreibrechte",
                    f"Der Bot darf in {channel.mention} nicht schreiben.",
                    tone="error",
                    hint="Prüfe die Kanalberechtigungen der Bot-Rolle.",
                )
            )
            return
        except discord.HTTPException as exc:
            LOGGER.warning("Regelwerk konnte nicht gesendet werden: %s", exc)
            await interaction.edit_original_response(
                view=notice("Fehlgeschlagen", f"```{exc.text or exc}```", tone="error")
            )
            return

    if first is not None:
        with contextlib.suppress(discord.HTTPException):
            await first.pin(reason="Regelwerk")

    lines = [f"Das Regelwerk steht in {channel.mention}."]
    if posted > 1:
        lines.append(f"Es wurde auf **{posted}** Nachrichten verteilt.")
    if removed:
        lines.append(f"**{removed}** frühere Bot-Nachrichten wurden entfernt.")

    await interaction.edit_original_response(
        view=notice(
            "Regelwerk eingerichtet",
            "\n".join(lines),
            tone="success",
            hint="Die Nachricht lässt sich jederzeit bearbeiten oder löschen.",
        )
    )


# --------------------------------------------------------------------------- #
# Eigenes Regelwerk
# --------------------------------------------------------------------------- #

_URL_RE = re.compile(r"^https?://\S+\.(?:png|jpe?g|gif|webp)(?:\?\S*)?$", re.IGNORECASE)


class CustomRulesModal(ui.Modal, title="Eigenes Regelwerk"):
    """Formular fuer ein selbst geschriebenes Regelwerk mit zwei Bildern."""

    heading = ui.Label(
        text="Überschrift",
        description="Steht groß über dem Regelwerk.",
        component=ui.TextInput(
            placeholder="Serverregeln",
            required=True,
            max_length=100,
        ),
    )

    body = ui.Label(
        text="Regeln",
        description="Eine Regel pro Zeile. Wird als Blockzitat dargestellt.",
        component=ui.TextInput(
            style=discord.TextStyle.paragraph,
            placeholder="1. Sei freundlich\n2. Kein Spam\n3. Kein NSFW",
            required=True,
            max_length=3000,
        ),
    )

    top_image = ui.Label(
        text="Bild oben rechts",
        description="Direktlink auf ein Bild (png, jpg, gif, webp). Optional.",
        component=ui.TextInput(
            placeholder="https://…/logo.png",
            required=False,
            max_length=400,
        ),
    )

    bottom_image = ui.Label(
        text="Bild unten",
        description="Breites Banner unter dem Text. Optional.",
        component=ui.TextInput(
            placeholder="https://…/banner.png",
            required=False,
            max_length=400,
        ),
    )

    def __init__(self, bot: ArchitectBot, channel: discord.TextChannel) -> None:
        super().__init__(timeout=900)
        self.bot = bot
        self.channel = channel

    async def on_submit(self, interaction: discord.Interaction) -> None:
        top = field_value(self.top_image).strip() or None
        bottom = field_value(self.bottom_image).strip() or None

        for url, where in ((top, "oben rechts"), (bottom, "unten")):
            if url and not _URL_RE.match(url):
                await interaction.response.send_message(
                    view=notice(
                        "Bildlink ungültig",
                        f"Der Link für das Bild **{where}** funktioniert so nicht.",
                        tone="error",
                        hint="Es muss ein direkter Link auf eine Bilddatei sein "
                        "und auf png, jpg, gif oder webp enden.",
                    ),
                    ephemeral=True,
                )
                return

        view = custom_rules_view(
            field_value(self.heading),
            field_value(self.body),
            top,
            bottom,
        )
        await interaction.response.send_message(
            view=_PreviewWrapper(self.bot, self.channel, [view]), ephemeral=True
        )


class _PreviewWrapper(ui.LayoutView):
    """Vorschau des eigenen Regelwerks mit Bestaetigung."""

    def __init__(
        self,
        bot: ArchitectBot,
        channel: discord.TextChannel,
        views: list[ui.LayoutView],
    ) -> None:
        super().__init__(timeout=600)
        self.bot = bot
        self.channel = channel
        self.views = views

        container = ui.Container(accent_colour=discord.Colour(COLOR_SUCCESS))
        container.add_item(
            ui.TextDisplay(
                "### Vorschau erstellt\n"
                f"-# So wird dein Regelwerk in {channel.name} aussehen"
            )
        )
        container.add_item(RULE())
        container.add_item(
            ui.TextDisplay(
                quote(
                    "Die Vorschau siehst du in der nächsten Nachricht.",
                    "Wenn sie passt, veröffentliche sie mit dem Button.",
                )
            )
        )
        row = ui.ActionRow()
        row.add_item(_PublishCustom(self))
        container.add_item(row)
        container.add_item(footer())
        self.add_item(container)


class _PublishCustom(ui.Button["_PreviewWrapper"]):
    def __init__(self, parent: _PreviewWrapper) -> None:
        super().__init__(label="Veröffentlichen", style=discord.ButtonStyle.success)
        self.screen = parent

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        await _post(interaction, self.screen.channel, self.screen.views, reset=False)


# --------------------------------------------------------------------------- #
# Auswahl und Optionen
# --------------------------------------------------------------------------- #

class _RulesetSelect(ui.Select["RulesetPicker"]):
    def __init__(self, screen: RulesetPicker) -> None:
        options = [
            discord.SelectOption(
                label=rs.name,
                value=rs.key,
                emoji=rs.emoji,
                description=f"{rs.scope.label} · {rs.rule_count} § · {rs.tagline}"[:100],
                default=rs.key == screen.selected,
            )
            for rs in RULESETS
        ]
        super().__init__(
            placeholder="Regelwerk auswählen",
            min_values=1,
            max_values=1,
            options=options,
        )
        self.screen = screen

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.edit_message(
            view=RulesetPicker(
                self.screen.bot, self.screen.channel, selected=self.values[0]
            )
        )


class RulesetPicker(ui.LayoutView):
    """Hauptansicht: Regelwerk waehlen und anwenden."""

    def __init__(
        self,
        bot: ArchitectBot,
        channel: discord.TextChannel,
        *,
        selected: str | None = None,
    ) -> None:
        super().__init__(timeout=900)
        self.bot = bot
        self.channel = channel
        self.selected = selected

        ruleset = get_ruleset(selected) if selected else None
        container = ui.Container(accent_colour=discord.Colour(COLOR_BRAND))

        container.add_item(
            ui.TextDisplay(
                "## Regelwerk einrichten\n"
                f"-# Ziel: {channel.mention}  ·  {len(RULESETS)} Vorlagen"
            )
        )
        container.add_item(RULE())

        if ruleset is None:
            grouped = []
            for length in RuleLength:
                names = [rs.name for rs in RULESETS if rs.length is length]
                grouped.append(f"**{length.label}** — {', '.join(names)}")
            container.add_item(ui.TextDisplay(quote(*grouped)))
            container.add_item(SPACE())
            container.add_item(
                ui.TextDisplay(
                    "-# Wähle unten eine Vorlage aus, um sie im Detail zu sehen."
                )
            )
        else:
            container.add_item(
                ui.TextDisplay(
                    f"### {ruleset.emoji}  {ruleset.name}\n"
                    f"-# {ruleset.scope.label}  ·  {ruleset.rule_count} Paragraphen  ·  "
                    f"{ruleset.length.label}"
                )
            )
            preview: list[str] = []
            if ruleset.intro:
                preview.append(f"*{ruleset.intro}*")
            # Erste drei Paragraphen anreissen, Text gekuerzt.
            for number, paragraph in enumerate(ruleset.paragraphs[:3], start=1):
                text = paragraph.text
                if len(text) > 110:
                    text = text[:107].rsplit(" ", 1)[0] + " …"
                preview.append(f"**§{number} • {paragraph.title}**")
                preview.append(text)
            remaining = len(ruleset.paragraphs) - 3
            if remaining > 0:
                preview.append(f"-# … und {remaining} weitere Paragraphen")
            container.add_item(ui.TextDisplay(quote(*preview)))

        container.add_item(RULE())
        select_row = ui.ActionRow()
        select_row.add_item(_RulesetSelect(self))
        container.add_item(select_row)

        action_row = ui.ActionRow()
        action_row.add_item(_ApplyRules(self, reset=False))
        action_row.add_item(_ApplyRules(self, reset=True))
        action_row.add_item(_CancelRules())
        container.add_item(action_row)

        custom_row = ui.ActionRow()
        custom_row.add_item(_CustomRules(self))
        container.add_item(custom_row)

        container.add_item(
            ui.TextDisplay(
                "-# **Ergänzen** hängt an  ·  **Neu aufsetzen** leert nur diesen "
                "Kanal  ·  **Selbst erstellen** öffnet ein Formular"
            )
        )
        container.add_item(footer())
        self.add_item(container)


class _ApplyRules(ui.Button["RulesetPicker"]):
    def __init__(self, screen: RulesetPicker, *, reset: bool) -> None:
        super().__init__(
            label="Neu aufsetzen" if reset else "Ergänzen",
            style=discord.ButtonStyle.danger if reset else discord.ButtonStyle.primary,
            disabled=screen.selected is None,
        )
        self.screen = screen
        self.reset = reset

    async def callback(self, interaction: discord.Interaction) -> None:
        if not _can_manage(interaction.user):
            await interaction.response.send_message(
                view=notice(
                    "Keine Berechtigung",
                    "Dafür brauchst du **Server verwalten**.",
                    tone="error",
                ),
                ephemeral=True,
            )
            return

        ruleset = get_ruleset(self.screen.selected or "")
        if ruleset is None:
            await interaction.response.send_message(
                view=notice("Nichts ausgewählt", "Wähle zuerst ein Regelwerk.", tone="error"),
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        guild_name = interaction.guild.name if interaction.guild else ""
        views = ruleset_views(ruleset, guild_name=guild_name)
        await _post(interaction, self.screen.channel, views, reset=self.reset)


class _CancelRules(ui.Button["RulesetPicker"]):
    def __init__(self) -> None:
        super().__init__(label="Abbrechen", style=discord.ButtonStyle.secondary)

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.edit_message(
            view=notice(
                "Abgebrochen",
                "Der Regelkanal bleibt unverändert.",
                tone="neutral",
                hint="Du kannst dein Regelwerk selbst schreiben.",
            )
        )


class _CustomRules(ui.Button["RulesetPicker"]):
    def __init__(self, screen: RulesetPicker) -> None:
        super().__init__(
            label="Eigenes Regelwerk erstellen",
            style=discord.ButtonStyle.secondary,
            emoji=button_emoji("zwrench", "✏️"),
        )
        self.screen = screen

    async def callback(self, interaction: discord.Interaction) -> None:
        if not _can_manage(interaction.user):
            await interaction.response.send_message(
                view=notice(
                    "Keine Berechtigung",
                    "Dafür brauchst du **Server verwalten**.",
                    tone="error",
                ),
                ephemeral=True,
            )
            return
        await interaction.response.send_modal(
            CustomRulesModal(self.screen.bot, self.screen.channel)
        )


# --------------------------------------------------------------------------- #
# Einstieg
# --------------------------------------------------------------------------- #

async def open_rules_assistant(
    interaction: discord.Interaction, bot: ArchitectBot
) -> None:
    """Assistenten oeffnen — sucht den Regelkanal selbst."""

    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message(
            view=notice("Nur auf Servern", "Das funktioniert nur in einem Server.", tone="error"),
            ephemeral=True,
        )
        return

    channel = find_rules_channel(guild)
    if channel is None:
        await interaction.response.send_message(
            view=notice(
                "Kein Regelkanal gefunden",
                "Auf diesem Server gibt es keinen Kanal für Regeln.",
                tone="error",
                hint="Wende zuerst eine Vorlage an — sie legt den Kanal an.",
            ),
            ephemeral=True,
        )
        return

    await interaction.response.send_message(
        view=RulesetPicker(bot, channel), ephemeral=True
    )
