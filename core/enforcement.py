"""Durchsetzung der Kanal-Modi zur Laufzeit.

„Bitte hier nur Bilder" ist eine Bitte. Dieses Modul macht daraus eine Regel:
wer im Bilder-Kanal reinen Text schreibt, dessen Nachricht wird entfernt und
durch einen kurzen, selbstloeschenden Hinweis ersetzt.

Damit das ohne Datenbank funktioniert, liest der Bot den Modus aus dem
**Kanal-Topic**. Beim Bauen schreibt die Engine dort eine unsichtbare Marke
hinein (``[mode:media]``), die im Discord-Client nicht auffaellt, aber nach
einem Neustart sofort wieder verfuegbar ist.
"""

from __future__ import annotations

import contextlib
import logging
import re

import discord

from .schema import ChannelMode

LOGGER = logging.getLogger("architect.enforcement")

__all__ = [
    "is_exempt",
    "mode_tag",
    "read_mode",
    "reaction_tag",
    "read_reactions",
    "strip_tags",
    "check_message",
    "next_count",
]

# Die Marken stehen am Ende des Topics. Eckige Klammern sind in Topics
# erlaubt und werden von Discord nicht angetastet.
_MODE_RE = re.compile(r"\[mode:([a-z]+)\]")
_REACT_RE = re.compile(r"\[react:([^\]]+)\]")

#: Wie lange ein Hinweis stehen bleibt, bevor er sich selbst entfernt.
HINT_SECONDS = 12


def is_exempt(author: object) -> bool:
    """Darf diese Person die Kanalregel ignorieren?

    Wer Nachrichten verwalten darf, gehoert zum Team. Fehlt die Information
    (unvollstaendiger Member-Cache), wird im Zweifel **nicht** geloescht.
    """

    permissions = getattr(author, "guild_permissions", None)
    if permissions is None:
        return True
    return bool(
        getattr(permissions, "manage_messages", False)
        or getattr(permissions, "administrator", False)
    )


def mode_tag(mode: ChannelMode) -> str:
    return "" if mode is ChannelMode.FREE else f"[mode:{mode.value}]"


def reaction_tag(reactions: tuple[str, ...]) -> str:
    return f"[react:{''.join(reactions)}]" if reactions else ""


def read_mode(channel: discord.abc.GuildChannel) -> ChannelMode:
    """Modus eines Kanals aus dessen Topic lesen."""

    topic = getattr(channel, "topic", None) or ""
    match = _MODE_RE.search(topic)
    if not match:
        return ChannelMode.FREE
    try:
        return ChannelMode(match.group(1))
    except ValueError:
        return ChannelMode.FREE


def read_reactions(channel: discord.abc.GuildChannel) -> tuple[str, ...]:
    """Auto-Reaktionen eines Kanals aus dessen Topic lesen."""

    topic = getattr(channel, "topic", None) or ""
    match = _REACT_RE.search(topic)
    if not match:
        return ()
    # Emojis koennen mehrere Codepoints haben; die Marke trennt per Leerzeichen,
    # faellt aber auf zeichenweises Lesen zurueck.
    raw = match.group(1)
    return tuple(part for part in raw.split(" ") if part) if " " in raw else tuple(raw)


def strip_tags(topic: str | None) -> str:
    """Topic ohne Steuermarken — fuer die Anzeige."""

    if not topic:
        return ""
    cleaned = _MODE_RE.sub("", _REACT_RE.sub("", topic))
    return " ".join(cleaned.split())


def _has_media(message: discord.Message) -> bool:
    """Enthaelt die Nachricht Bild, Video, Link oder ein Sticker?"""

    if message.attachments or message.stickers:
        return True
    if message.embeds:
        return True
    # Discord erzeugt die Embeds fuer Links erst verzoegert, daher zusaetzlich
    # der direkte Blick in den Text.
    return bool(re.search(r"https?://\S+", message.content))


_NUMBER_RE = re.compile(r"^\s*(\d{1,9})")


def next_count(history_content: str | None) -> int:
    """Die Zahl, die als naechstes erwartet wird."""

    if not history_content:
        return 1
    match = _NUMBER_RE.match(history_content)
    return int(match.group(1)) + 1 if match else 1


async def check_message(message: discord.Message) -> bool:
    """Prueft eine Nachricht gegen den Kanal-Modus.

    Gibt ``True`` zurueck, wenn die Nachricht entfernt wurde.
    """

    channel = message.channel
    mode = read_mode(channel)
    if mode is ChannelMode.FREE or not mode.is_enforced:
        return False

    # Das Team darf immer schreiben — sonst kann niemand moderieren.
    #
    # Bewusst per getattr statt isinstance: ist der Member-Cache unvollstaendig,
    # liefert Discord ein User-Objekt ohne guild_permissions. Dann lieber die
    # Nachricht stehen lassen, als einem Moderator ins Wort zu faehren.
    author = message.author
    if is_exempt(author):
        return False

    hint: str | None = None

    if mode is ChannelMode.MEDIA and not _has_media(message):
        hint = (
            f"{author.mention} in diesem Kanal sind nur Beiträge mit "
            "**Bild, Video oder Link** erlaubt."
        )

    elif mode is ChannelMode.COUNTING:
        expected: int | None = None
        with contextlib.suppress(discord.HTTPException, AttributeError):
            async for previous in channel.history(limit=5, before=message):
                if previous.author.bot and not _NUMBER_RE.match(previous.content or ""):
                    continue
                expected = next_count(previous.content)
                break
        if expected is None:
            expected = 1

        match = _NUMBER_RE.match(message.content or "")
        if match is None or int(match.group(1)) != expected:
            hint = f"{author.mention} als Nächstes kommt **{expected}**."

    if hint is None:
        return False

    try:
        await message.delete()
    except (discord.Forbidden, discord.NotFound):
        return False
    except discord.HTTPException:
        LOGGER.debug("Nachricht konnte nicht entfernt werden", exc_info=True)
        return False

    with contextlib.suppress(discord.HTTPException):
        await channel.send(hint, delete_after=HINT_SECONDS)
    return True


async def apply_reactions(message: discord.Message) -> None:
    """Auto-Reaktionen unter einen Beitrag setzen."""

    for emoji in read_reactions(message.channel):
        try:
            await message.add_reaction(emoji)
        except (discord.Forbidden, discord.NotFound):
            return
        except discord.HTTPException:
            continue
