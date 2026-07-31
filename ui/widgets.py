"""Interaktive Nachrichten, die dauerhaft in den Kanaelen stehen.

Diese Views muessen einen Bot-Neustart ueberleben: niemand pinnt einen
Verify-Button an, der nach dem naechsten Deploy tot ist. Deshalb haben alle
Komponenten eine feste ``custom_id`` und ``timeout=None``, und der Bot
registriert sie beim Start erneut (``bot.add_view``).

Weil eine persistente View ihren Zustand nicht kennt, steht alles Noetige in
der ``custom_id`` selbst — bei den Selbstrollen zum Beispiel die Rollennamen.
"""

from __future__ import annotations

import contextlib
import logging

import discord
from discord import ui

from config import COLOR_BRAND, COLOR_SUCCESS
from core.content import CHECKLIST_ITEMS
from core.permissions import MEMBER, VERIFIED
from core.small_caps import strip_decoration
from ui.components import RULE, footer, notice, quote

LOGGER = logging.getLogger("architect.widgets")

__all__ = [
    "PERSISTENT_VIEWS",
    "ChecklistView",
    "RulesView",
    "SelfRoleView",
    "TicketView",
    "VerifyView",
    "build_widget_view",
]


# --------------------------------------------------------------------------- #
# Hilfsfunktionen
# --------------------------------------------------------------------------- #

def _find_role(guild: discord.Guild, *needles: str) -> discord.Role | None:
    """Rolle ueber einen Namensbestandteil finden (Small Caps toleriert)."""

    for needle in needles:
        target = needle.casefold()
        for role in guild.roles:
            if role.is_default():
                continue
            if target in strip_decoration(role.name).casefold():
                return role
    return None


async def _grant(
    interaction: discord.Interaction,
    *needles: str,
    success: str,
) -> None:
    """Rolle vergeben und dem Nutzer eine private Rueckmeldung geben."""

    guild, member = interaction.guild, interaction.user
    if guild is None or not isinstance(member, discord.Member):
        return

    role = _find_role(guild, *needles)
    if role is None:
        await interaction.response.send_message(
            view=notice(
                "Rolle fehlt",
                "Die passende Rolle existiert auf diesem Server nicht.",
                tone="error",
                hint="Ein Teammitglied sollte die Vorlage erneut anwenden.",
            ),
            ephemeral=True,
        )
        return

    if role in member.roles:
        await interaction.response.send_message(
            view=notice("Schon erledigt", "Du hast diese Rolle bereits.", tone="neutral"),
            ephemeral=True,
        )
        return

    if not role.is_assignable():
        await interaction.response.send_message(
            view=notice(
                "Nicht möglich",
                f"Der Bot darf **{role.name}** nicht vergeben.",
                tone="error",
                hint="Die Bot-Rolle muss über dieser Rolle stehen.",
            ),
            ephemeral=True,
        )
        return

    try:
        await member.add_roles(role, reason="Selbstverifizierung")
    except discord.HTTPException:
        LOGGER.exception("Rolle konnte nicht vergeben werden")
        await interaction.response.send_message(
            view=notice("Fehlgeschlagen", "Bitte versuche es später erneut.", tone="error"),
            ephemeral=True,
        )
        return

    # Die Unverified-Rolle wird entfernt, sonst bleibt die Schleuse zu.
    unverified = _find_role(guild, "unverified")
    if unverified is not None and unverified in member.roles and unverified.is_assignable():
        with contextlib.suppress(discord.HTTPException):
            await member.remove_roles(unverified, reason="Verifiziert")

    await interaction.response.send_message(
        view=notice("Willkommen", success, tone="success"), ephemeral=True
    )


# --------------------------------------------------------------------------- #
# Verify
# --------------------------------------------------------------------------- #

class VerifyView(ui.LayoutView):
    """Button, der die Verified-Rolle vergibt."""

    def __init__(self, title: str = "", lines: list[str] | None = None) -> None:
        super().__init__(timeout=None)
        container = ui.Container(accent_colour=discord.Colour(COLOR_SUCCESS))
        container.add_item(ui.TextDisplay(f"### {title or 'Verifizierung'}"))
        container.add_item(RULE())
        container.add_item(ui.TextDisplay(quote(*(lines or ["Klicke unten, um freigeschaltet zu werden."]))))
        row = ui.ActionRow()
        row.add_item(_VerifyButton())
        container.add_item(row)
        container.add_item(footer(mark=True))
        self.add_item(container)


class _VerifyButton(ui.Button["VerifyView"]):
    def __init__(self) -> None:
        super().__init__(
            label="Verifizieren",
            style=discord.ButtonStyle.success,
            custom_id="architect:verify",
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        await _grant(
            interaction,
            VERIFIED,
            MEMBER,
            success="Du bist jetzt verifiziert und siehst den gesamten Server.",
        )


# --------------------------------------------------------------------------- #
# Regeln akzeptieren
# --------------------------------------------------------------------------- #

class RulesView(ui.LayoutView):
    def __init__(self, title: str = "", lines: list[str] | None = None) -> None:
        super().__init__(timeout=None)
        container = ui.Container(accent_colour=discord.Colour(COLOR_BRAND))
        container.add_item(ui.TextDisplay(f"### {title or 'Regeln'}"))
        container.add_item(RULE())
        container.add_item(
            ui.TextDisplay(quote(*(lines or ["Bitte lies die Regeln und bestätige sie."])))
        )
        container.add_item(
            ui.TextDisplay("-# Mit dem Klick bestätigst du, die Regeln gelesen zu haben.")
        )
        row = ui.ActionRow()
        row.add_item(_AcceptButton())
        container.add_item(row)
        container.add_item(footer(mark=True))
        self.add_item(container)


class _AcceptButton(ui.Button["RulesView"]):
    def __init__(self) -> None:
        super().__init__(
            label="Regeln akzeptieren",
            style=discord.ButtonStyle.success,
            custom_id="architect:rules",
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        await _grant(
            interaction,
            VERIFIED,
            MEMBER,
            success="Danke — die Regeln gelten damit als akzeptiert.",
        )


# --------------------------------------------------------------------------- #
# Selbstrollen
# --------------------------------------------------------------------------- #

# (Label, Beschreibung, Emoji) — die Rollen werden beim Klick angelegt,
# falls sie noch fehlen, damit das Widget auf jedem Server funktioniert.
SELF_ROLES: tuple[tuple[str, str, str], ...] = (
    ("Ankündigungen", "Ping bei wichtigen Neuigkeiten", "📢"),
    ("Events", "Ping bei Events und Aktionen", "🎉"),
    ("Umfragen", "Ping bei Abstimmungen", "📊"),
    ("Gaming", "Interesse an Gaming-Runden", "🎮"),
    ("Musik", "Interesse an Musik und Voice", "🎧"),
    ("Kreativ", "Interesse an Kunst und Projekten", "🎨"),
)


class SelfRoleView(ui.LayoutView):
    def __init__(self, title: str = "", lines: list[str] | None = None) -> None:
        super().__init__(timeout=None)
        container = ui.Container(accent_colour=discord.Colour(COLOR_BRAND))
        container.add_item(ui.TextDisplay(f"### {title or 'Rollen'}"))
        container.add_item(RULE())
        container.add_item(
            ui.TextDisplay(quote(*(lines or ["Wähle aus, was auf dich zutrifft."])))
        )
        row = ui.ActionRow()
        row.add_item(_SelfRoleSelect())
        container.add_item(row)
        container.add_item(footer(mark=True))
        self.add_item(container)


class _SelfRoleSelect(ui.Select["SelfRoleView"]):
    def __init__(self) -> None:
        super().__init__(
            placeholder="Rollen auswählen",
            min_values=0,
            max_values=len(SELF_ROLES),
            custom_id="architect:selfroles",
            options=[
                discord.SelectOption(label=label, description=description, emoji=emoji)
                for label, description, emoji in SELF_ROLES
            ],
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        guild, member = interaction.guild, interaction.user
        if guild is None or not isinstance(member, discord.Member):
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        wanted = set(self.values)
        added: list[str] = []
        removed: list[str] = []
        failed = False

        for label, _, emoji in SELF_ROLES:
            role = _find_role(guild, label)

            if label in wanted:
                if role is None:
                    try:
                        role = await guild.create_role(
                            name=f"{emoji}・{label}",
                            reason="Selbstvergebene Rolle",
                            mentionable=True,
                        )
                    except discord.HTTPException:
                        failed = True
                        continue
                if role not in member.roles and role.is_assignable():
                    try:
                        await member.add_roles(role, reason="Selbstvergabe")
                        added.append(label)
                    except discord.HTTPException:
                        failed = True
            elif role is not None and role in member.roles and role.is_assignable():
                try:
                    await member.remove_roles(role, reason="Selbstvergabe")
                    removed.append(label)
                except discord.HTTPException:
                    failed = True

        parts: list[str] = []
        if added:
            parts.append("**Hinzugefügt:** " + ", ".join(added))
        if removed:
            parts.append("**Entfernt:** " + ", ".join(removed))
        if not parts:
            parts.append("Es hat sich nichts geändert.")

        await interaction.followup.send(
            view=notice(
                "Rollen aktualisiert",
                "\n".join(parts),
                tone="success" if not failed else "error",
                hint="Einige Rollen konnten nicht gesetzt werden." if failed else None,
            ),
            ephemeral=True,
        )


# --------------------------------------------------------------------------- #
# Ticket
# --------------------------------------------------------------------------- #

class TicketView(ui.LayoutView):
    def __init__(self, title: str = "", lines: list[str] | None = None) -> None:
        super().__init__(timeout=None)
        container = ui.Container(accent_colour=discord.Colour(COLOR_BRAND))
        container.add_item(ui.TextDisplay(f"### {title or 'Support'}"))
        container.add_item(RULE())
        container.add_item(
            ui.TextDisplay(quote(*(lines or ["Öffne ein Ticket, wenn du Hilfe brauchst."])))
        )
        row = ui.ActionRow()
        row.add_item(_TicketButton())
        container.add_item(row)
        container.add_item(footer(mark=True))
        self.add_item(container)


class _TicketButton(ui.Button["TicketView"]):
    def __init__(self) -> None:
        super().__init__(
            label="Ticket erstellen",
            style=discord.ButtonStyle.primary,
            custom_id="architect:ticket",
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(
                view=notice(
                    "Nicht möglich",
                    "Tickets funktionieren nur in Textkanälen.",
                    tone="error",
                ),
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        name = f"ticket-{interaction.user.name}"[:100]

        try:
            thread = await channel.create_thread(
                name=name,
                type=discord.ChannelType.private_thread,
                invitable=False,
                reason="Support-Ticket",
            )
            await thread.add_user(interaction.user)
        except discord.Forbidden:
            await interaction.followup.send(
                view=notice(
                    "Keine Berechtigung",
                    "Dem Bot fehlt das Recht, Threads zu erstellen.",
                    tone="error",
                ),
                ephemeral=True,
            )
            return
        except discord.HTTPException:
            # Private Threads brauchen ein Server-Boost-Level; oeffentlich als Rueckfall.
            try:
                thread = await channel.create_thread(name=name, reason="Support-Ticket")
            except discord.HTTPException:
                await interaction.followup.send(
                    view=notice("Fehlgeschlagen", "Ticket konnte nicht angelegt werden.", tone="error"),
                    ephemeral=True,
                )
                return

        with contextlib.suppress(discord.HTTPException):
            await thread.send(
                view=notice(
                    "Ticket eröffnet",
                    f"{interaction.user.mention} — beschreibe bitte dein Anliegen.",
                    tone="success",
                    hint="Das Team meldet sich, sobald jemand verfügbar ist.",
                )
            )

        await interaction.followup.send(
            view=notice("Ticket erstellt", f"Dein Ticket: {thread.mention}", tone="success"),
            ephemeral=True,
        )


# --------------------------------------------------------------------------- #
# Checkliste
# --------------------------------------------------------------------------- #

class ChecklistView(ui.LayoutView):
    """Aufgabenliste fuers Team — abhakbar, Zustand steckt im Text."""

    def __init__(self, title: str = "", lines: list[str] | None = None) -> None:
        super().__init__(timeout=None)
        container = ui.Container(accent_colour=discord.Colour(COLOR_BRAND))
        container.add_item(ui.TextDisplay(f"### {title or 'Einrichtung abschließen'}"))
        container.add_item(RULE())
        container.add_item(
            ui.TextDisplay(
                quote(
                    "Diese Punkte kann der Bot nicht automatisch erledigen.",
                    "",
                    *(f"☐ {item}" for item in CHECKLIST_ITEMS),
                )
            )
        )
        container.add_item(footer(mark=True))
        self.add_item(container)


# --------------------------------------------------------------------------- #
# Zuordnung
# --------------------------------------------------------------------------- #

_BUILDERS = {
    "verify": VerifyView,
    "rules": RulesView,
    "roles": SelfRoleView,
    "ticket": TicketView,
    "checklist": ChecklistView,
}


def build_widget_view(widget_value: str, title: str, lines: list[str]) -> ui.LayoutView | None:
    """View zu einem ``Widget``-Wert erzeugen."""

    builder = _BUILDERS.get(widget_value)
    if builder is None:
        return None
    return builder(title, lines)


#: Views, die der Bot beim Start erneut registrieren muss, damit die
#: angehefteten Nachrichten nach einem Neustart weiter funktionieren.
PERSISTENT_VIEWS: tuple[type[ui.LayoutView], ...] = (
    VerifyView,
    RulesView,
    SelfRoleView,
    TicketView,
)
