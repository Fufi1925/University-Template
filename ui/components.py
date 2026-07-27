"""Components V2 — Bausteine der Oberflaeche.

Jede Ansicht ist eine :class:`discord.ui.LayoutView`; das alte Embed-Objekt
kommt nirgends mehr vor. Components V2 liefert echte Layout-Primitive
(Container, Section, Separator, Thumbnail) statt des Korsetts aus
Titel/Feld/Footer — das ist die Grundlage fuer ein ruhiges Layout.

Gestaltungsregeln
-----------------
Das Ziel ist ein Interface, das aussieht, als haette es jemand gebaut, der
weiss was er tut — nicht wie ein generierter Baukasten:

* **Blockzitate statt Fliesstext.** ``>`` setzt Inhalt optisch zurueck und
  erzeugt eine ruhige, eingerueckte Spalte.
* **Emojis sind Navigation, keine Dekoration.** Hoechstens eines pro
  Ueberschrift, und nur dort, wo es beim Scannen hilft.
* **Eine Betonungsebene.** Fett nur fuer Zahlen und Eigennamen. Kein
  Ausrufezeichen-Marketing.
* **Grau fuer Nebensaechliches.** ``-#`` fuer alles, was nicht die
  Hauptaussage ist.

Zwei harte Grenzen von Discord:
* 40 Komponenten pro Nachricht
* 4000 Zeichen ueber alle ``TextDisplay`` hinweg
"""

from __future__ import annotations

from typing import Iterable, Sequence

import discord
from discord import ui

from config import (
    BRAND_FOOTER,
    COLOR_BRAND,
    COLOR_DANGER,
    COLOR_NEUTRAL,
    COLOR_PREMIUM,
    COLOR_SUCCESS,
)
from core.schema import ChannelKind, Template, Visibility

__all__ = [
    "RULE",
    "SPACE",
    "quote",
    "footer",
    "heading",
    "stat_line",
    "kind_icon",
    "visibility_badge",
    "progress_bar",
    "notice",
]


# --------------------------------------------------------------------------- #
# Primitive
# --------------------------------------------------------------------------- #

def RULE(*, large: bool = False) -> ui.Separator:
    """Sichtbare Trennlinie."""

    return ui.Separator(
        visible=True,
        spacing=discord.SeparatorSpacing.large if large else discord.SeparatorSpacing.small,
    )


def SPACE(*, large: bool = False) -> ui.Separator:
    """Unsichtbarer Abstand."""

    return ui.Separator(
        visible=False,
        spacing=discord.SeparatorSpacing.large if large else discord.SeparatorSpacing.small,
    )


def quote(*lines: str) -> str:
    """Setzt Zeilen als Blockzitat.

    Discord bricht ein Blockzitat bei einer Leerzeile ab, deshalb bekommt jede
    Zeile ihr eigenes ``>``. Leere Eintraege werden zu ``>`` allein, was den
    Block optisch zusammenhaelt statt ihn zu zerreissen.
    """

    out: list[str] = []
    for line in lines:
        if not line:
            out.append(">")
            continue
        out.extend(f"> {part}" if part else ">" for part in line.split("\n"))
    return "\n".join(out)


def footer(extra: str | None = None) -> ui.TextDisplay:
    """Zurueckhaltende Fusszeile (``-#`` ist Discords Kleinschrift)."""

    text = f"-# {BRAND_FOOTER}"
    if extra:
        text += f"  ·  {extra}"
    return ui.TextDisplay(text)


def heading(title: str, subtitle: str | None = None, *, level: int = 2) -> ui.TextDisplay:
    """Ueberschrift mit optionaler grauer Unterzeile."""

    content = f"{'#' * level} {title}"
    if subtitle:
        content += f"\n-# {subtitle}"
    return ui.TextDisplay(content)


def stat_line(pairs: Sequence[tuple[str, object]]) -> str:
    """``**12** Kategorien · **68** Kanaele`` — kompakt und scanbar."""

    return "  ·  ".join(f"**{value}** {label}" for label, value in pairs)


_KIND_ICONS: dict[ChannelKind, str] = {
    # Kein nacktes '#': in einem Blockzitat wuerde Discord die Zeile als
    # Markdown-Ueberschrift rendern und riesig darstellen. Das Backtick-'#'
    # sieht aus wie ein Textkanal und bleibt garantiert inline.
    ChannelKind.TEXT: "`#`",
    ChannelKind.VOICE: "🔊",
    ChannelKind.FORUM: "🗂",
    ChannelKind.NEWS: "📣",
    ChannelKind.STAGE: "🎙",
}


def kind_icon(kind: ChannelKind) -> str:
    """Symbol vor einem Kanalnamen in der Strukturvorschau."""

    return _KIND_ICONS.get(kind, "·")


_VISIBILITY_BADGES: dict[Visibility, str] = {
    Visibility.PUBLIC: "",
    Visibility.MEMBER: "",
    Visibility.GATE: "Eingang",
    Visibility.READONLY: "nur lesen",
    Visibility.ARCHIVE: "Archiv",
    Visibility.VIP: "VIP",
    Visibility.STAFF: "Team",
    Visibility.LEADERSHIP: "Leitung",
}


def visibility_badge(visibility: Visibility) -> str:
    """Klartext statt Symbol — ein Wort erklaert sich von selbst."""

    return _VISIBILITY_BADGES.get(visibility, "")


def progress_bar(current: int, total: int, *, width: int = 24) -> str:
    """Schmaler Fortschrittsbalken aus Blockelementen."""

    total = max(total, 1)
    done = min(max(current, 0), total)
    filled = round(width * done / total)
    percent = round(100 * done / total)
    return f"`{'━' * filled}{'─' * (width - filled)}`  {percent}%"


# --------------------------------------------------------------------------- #
# Zusammengesetzte Ansichten
# --------------------------------------------------------------------------- #

_TONES = {
    "info": COLOR_BRAND,
    "success": COLOR_SUCCESS,
    "error": COLOR_DANGER,
    "premium": COLOR_PREMIUM,
    "neutral": COLOR_NEUTRAL,
}


def notice(
    title: str,
    body: str,
    *,
    tone: str = "info",
    hint: str | None = None,
    extra: Iterable[ui.Item] = (),
) -> ui.LayoutView:
    """Einzelner Container fuer Bestaetigungen, Fehler und Hinweise.

    Der Fliesstext steht im Blockzitat, ein optionaler Hinweis darunter in
    Grau — so bleibt die Kernaussage die auffaelligste Zeile.
    """

    container = ui.Container(accent_colour=discord.Colour(_TONES.get(tone, COLOR_BRAND)))
    container.add_item(ui.TextDisplay(f"### {title}"))
    container.add_item(ui.TextDisplay(quote(body)))
    if hint:
        container.add_item(ui.TextDisplay(f"-# {hint}"))
    for item in extra:
        container.add_item(item)

    view = ui.LayoutView(timeout=None)
    view.add_item(container)
    return view
