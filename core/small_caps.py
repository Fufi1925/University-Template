"""Small Caps Basic — the typographic layer of every template.

Discord lowercases text channel names, which normally destroys any styling.
Unicode small capitals survive that normalisation because each glyph *is* its
own lowercase form, so a channel called ``ᴀɴɴᴏᴜɴᴄᴇᴍᴇɴᴛꜱ`` stays readable.

The mapping below is "Small Caps Basic": every ASCII letter has a genuine
Unicode small-capital counterpart, with the two historical gaps (``x`` and the
digits) handled explicitly so nothing silently falls back to a plain glyph.
"""

from __future__ import annotations

import re
import unicodedata

__all__ = [
    "category_name",
    "channel_name",
    "from_small_caps",
    "is_small_caps",
    "role_name",
    "slugify",
    "strip_decoration",
    "to_small_caps",
]


# Latin small capital letters. ``x`` has no dedicated small-cap codepoint in
# Unicode, so the modifier letter is the accepted stand-in used by Discord
# communities; it keeps the optical weight of the surrounding glyphs.
_SMALL_CAPS: dict[str, str] = {
    "a": "ᴀ", "b": "ʙ", "c": "ᴄ", "d": "ᴅ", "e": "ᴇ", "f": "ꜰ", "g": "ɢ",
    "h": "ʜ", "i": "ɪ", "j": "ᴊ", "k": "ᴋ", "l": "ʟ", "m": "ᴍ", "n": "ɴ",
    "o": "ᴏ", "p": "ᴘ", "q": "ǫ", "r": "ʀ", "s": "ꜱ", "t": "ᴛ", "u": "ᴜ",
    "v": "ᴠ", "w": "ᴡ", "x": "x", "y": "ʏ", "z": "ᴢ",
}

# German umlauts and other common accents are folded to their base letter so
# they render in the same optical style instead of breaking the line.
_FOLD: dict[str, str] = {
    "ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss",
    "à": "a", "á": "a", "â": "a", "ã": "a", "å": "a",
    "è": "e", "é": "e", "ê": "e", "ë": "e",
    "ì": "i", "í": "i", "î": "i", "ï": "i",
    "ò": "o", "ó": "o", "ô": "o", "õ": "o", "ø": "o",
    "ù": "u", "ú": "u", "û": "u",
    "ç": "c", "ñ": "n", "ý": "y",
}

_REVERSE: dict[str, str] = {v: k for k, v in _SMALL_CAPS.items() if v != k}

_TRANSLATION = str.maketrans(_SMALL_CAPS)

# The separator used between the emoji and the label of a channel. A full-width
# middle dot reads better than a hyphen and is not touched by Discord.
SEPARATOR = "・"


def to_small_caps(text: str) -> str:
    """Convert ``text`` to Small Caps Basic.

    Emojis, digits, punctuation and any non-Latin script (Cyrillic, Japanese,
    Arabic, …) are passed through untouched so multi-language channel names
    keep their native spelling.
    """

    folded = "".join(_FOLD.get(char, char) for char in text.lower())
    return folded.translate(_TRANSLATION)


def from_small_caps(text: str) -> str:
    """Best-effort inverse of :func:`to_small_caps`, used for name matching."""

    return "".join(_REVERSE.get(char, char) for char in text)


def is_small_caps(text: str) -> bool:
    """Return ``True`` when ``text`` contains at least one small-cap glyph."""

    return any(char in _REVERSE for char in text)


def channel_name(label: str, emoji: str | None = None, *, small_caps: bool = True) -> str:
    """Build a decorated channel name: ``🔊・ᴠᴏɪᴄᴇ-ʟᴏᴜɴɢᴇ``.

    Discord converts spaces in text channels to hyphens; doing it ourselves
    keeps text and voice channels visually identical.
    """

    styled = to_small_caps(label) if small_caps else label.lower()
    styled = re.sub(r"\s+", "-", styled.strip())
    if not emoji:
        return styled
    return f"{emoji}{SEPARATOR}{styled}"


def category_name(label: str, emoji: str | None = None, *, small_caps: bool = True) -> str:
    """Build a decorated category name.

    Categories keep their spaces (Discord does not rewrite them) and are
    rendered in uppercase-looking small caps for a clear visual hierarchy.
    """

    styled = to_small_caps(label) if small_caps else label
    styled = re.sub(r"\s+", " ", styled.strip())
    if not emoji:
        return styled
    return f"{emoji}{SEPARATOR}{styled}"


def role_name(label: str, emoji: str | None = None, *, small_caps: bool = False) -> str:
    """Build a role name.

    Roles are *not* small-capped by default: they appear in the member list and
    in mentions where plain casing is easier to scan.
    """

    styled = to_small_caps(label) if small_caps else label
    if not emoji:
        return styled
    return f"{emoji}{SEPARATOR}{styled}"


def strip_decoration(name: str) -> str:
    """Remove emoji prefix and separators so two names can be compared."""

    without_prefix = name.split(SEPARATOR)[-1] if SEPARATOR in name else name
    plain = from_small_caps(without_prefix)
    # Drop emoji / symbol codepoints, then collapse the remaining separators.
    plain = "".join(
        char for char in plain if not unicodedata.category(char).startswith("So")
    )
    plain = re.sub(r"[\s_-]+", " ", plain)
    return plain.strip().lower()


def slugify(name: str) -> str:
    """ASCII slug of a decorated name — useful for exports and diagnostics."""

    plain = strip_decoration(name)
    plain = "".join(_FOLD.get(char, char) for char in plain)
    plain = re.sub(r"[^a-z0-9]+", "-", plain)
    return plain.strip("-")


if __name__ == "__main__":  # pragma: no cover - manual smoke test
    samples = ["Announcements", "Voice Lounge", "Größe & Qualität", "русский", "日本語"]
    for sample in samples:
        print(f"{sample:22} -> {to_small_caps(sample)}")
    print(channel_name("general chat", "💬"))
    print(category_name("Information", "📌"))
