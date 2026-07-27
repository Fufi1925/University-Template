"""Die angeheftete Startnachricht eines Kanals.

Zwei Faelle:

* Der Kanal hat ein **Widget** (Verify, Regeln, Rollen, Ticket, Checkliste) —
  dann kommt eine interaktive View mit Button oder Dropdown.
* Sonst ein reiner **Header**: Titel, Zweck und die geltende Regel.

Beide sehen gleich aus, damit der Server einheitlich wirkt.
"""

from __future__ import annotations

import discord
from discord import ui

from config import COLOR_BRAND, COLOR_NEUTRAL
from core.schema import ChannelMode, ChannelSpec, Visibility, Widget
from .components import RULE, footer, quote
from .widgets import build_widget_view

__all__ = ["intro_view", "header_view"]


# Ruhige Farbe fuer Log- und Archivkanaele, damit die Startnachricht dort
# nicht wie eine Ankuendigung wirkt.
_QUIET = {ChannelMode.LOG}
_QUIET_VISIBILITY = {Visibility.ARCHIVE, Visibility.READONLY}


def header_view(spec: ChannelSpec, title: str, lines: list[str]) -> ui.LayoutView:
    """Nicht-interaktiver Kanal-Header."""

    quiet = spec.mode in _QUIET or spec.visibility in _QUIET_VISIBILITY
    accent = COLOR_NEUTRAL if quiet else COLOR_BRAND

    container = ui.Container(accent_colour=discord.Colour(accent))
    container.add_item(ui.TextDisplay(f"### {title}"))
    if lines:
        container.add_item(RULE())
        container.add_item(ui.TextDisplay(quote(*lines)))
    # Dauerhafte Nachricht im Kanal — Signatur fuer den Wiedererkennung.
    container.add_item(footer(mark=True))

    view = ui.LayoutView(timeout=None)
    view.add_item(container)
    return view


def intro_view(spec: ChannelSpec, title: str, lines: list[str]) -> ui.LayoutView:
    """Passende View fuer diesen Kanal — mit Widget, falls vorgesehen."""

    if spec.widget is not Widget.NONE:
        view = build_widget_view(spec.widget.value, title, lines)
        if view is not None:
            return view
    return header_view(spec, title, lines)
