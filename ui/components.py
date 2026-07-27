"""Components V2 building blocks.

Every surface in this bot is a :class:`discord.ui.LayoutView` — the legacy
embed object is gone entirely. Components V2 gives us real layout primitives
(containers, sections, separators, thumbnails) instead of the
title/field/footer straitjacket, which is what makes the clean look possible.

Two hard limits to respect:
* 40 components per message
* 4000 characters across all ``TextDisplay`` components
"""

from __future__ import annotations

from typing import Iterable, Sequence

import discord
from discord import ui

from config import (
    BRAND_FOOTER,
    BRAND_NAME,
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
    "footer",
    "header",
    "stat_line",
    "kind_icon",
    "visibility_badge",
    "progress_bar",
    "template_card",
    "notice",
]


# --------------------------------------------------------------------------- #
# Primitives
# --------------------------------------------------------------------------- #

def RULE(*, large: bool = False) -> ui.Separator:
    """A visible divider line."""

    return ui.Separator(
        visible=True,
        spacing=discord.SeparatorSpacing.large if large else discord.SeparatorSpacing.small,
    )


def SPACE(*, large: bool = False) -> ui.Separator:
    """Invisible breathing room."""

    return ui.Separator(
        visible=False,
        spacing=discord.SeparatorSpacing.large if large else discord.SeparatorSpacing.small,
    )


def footer(extra: str | None = None) -> ui.TextDisplay:
    """The subtle grey footer line (``-#`` is Discord's small-text markdown)."""

    text = f"-# {BRAND_FOOTER}"
    if extra:
        text += f"  ·  {extra}"
    return ui.TextDisplay(text)


def header(title: str, subtitle: str | None = None) -> ui.TextDisplay:
    content = f"## {title}"
    if subtitle:
        content += f"\n-# {subtitle}"
    return ui.TextDisplay(content)


def stat_line(pairs: Sequence[tuple[str, object]]) -> str:
    """``**12** Kategorien  ·  **68** Kanäle`` — compact, scannable stats."""

    return "  ·  ".join(f"**{value}** {label}" for label, value in pairs)


_KIND_ICONS: dict[ChannelKind, str] = {
    ChannelKind.TEXT: "💬",
    ChannelKind.VOICE: "🔊",
    ChannelKind.FORUM: "🧵",
    ChannelKind.NEWS: "📢",
    ChannelKind.STAGE: "🎤",
}


def kind_icon(kind: ChannelKind) -> str:
    return _KIND_ICONS.get(kind, "•")


_VISIBILITY_BADGES: dict[Visibility, str] = {
    Visibility.PUBLIC: "",
    Visibility.MEMBER: "",
    Visibility.GATE: "🚪",
    Visibility.READONLY: "🔒",
    Visibility.ARCHIVE: "🗄️",
    Visibility.VIP: "💎",
    Visibility.STAFF: "🛡️",
    Visibility.LEADERSHIP: "👑",
}


def visibility_badge(visibility: Visibility) -> str:
    return _VISIBILITY_BADGES.get(visibility, "")


def progress_bar(current: int, total: int, *, width: int = 12) -> str:
    """A filled/empty block bar used on the live build screen."""

    total = max(total, 1)
    filled = round(width * min(current, total) / total)
    percent = round(100 * min(current, total) / total)
    return f"`{'█' * filled}{'░' * (width - filled)}`  {percent}%"


# --------------------------------------------------------------------------- #
# Composite blocks
# --------------------------------------------------------------------------- #

def template_card(template: Template, *, locked: bool = False) -> list[ui.Item]:
    """One template rendered as a heading + stats + highlight list."""

    badge = "💎 Premium" if template.premium else "🆓 Free"
    if locked:
        badge = "🔒 Gesperrt"

    items: list[ui.Item] = [
        ui.TextDisplay(
            f"### {template.emoji}  {template.name}\n"
            f"-# {badge}  ·  {template.tagline}"
        ),
        ui.TextDisplay(
            stat_line(
                [
                    ("Kategorien", template.category_count),
                    ("Kanäle", template.channel_count),
                    ("Voice", template.voice_count),
                    ("Rollen", len(template.roles)),
                ]
            )
        ),
    ]
    if template.highlights:
        bullets = "\n".join(f"› {line}" for line in template.highlights[:4])
        items.append(ui.TextDisplay(bullets))
    return items


def notice(
    title: str,
    body: str,
    *,
    tone: str = "info",
    extra: Iterable[ui.Item] = (),
) -> ui.LayoutView:
    """A single-container message used for confirmations, errors and hints."""

    accent = {
        "info": COLOR_BRAND,
        "success": COLOR_SUCCESS,
        "error": COLOR_DANGER,
        "premium": COLOR_PREMIUM,
        "neutral": COLOR_NEUTRAL,
    }.get(tone, COLOR_BRAND)

    container = ui.Container(accent_colour=discord.Colour(accent))
    container.add_item(ui.TextDisplay(f"### {title}"))
    container.add_item(ui.TextDisplay(body))
    for item in extra:
        container.add_item(item)

    view = ui.LayoutView(timeout=None)
    view.add_item(container)
    return view
