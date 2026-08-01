"""Die Emojis dieser App.

App-Emojis gehoeren genau *einer* Anwendung. Discord ist da eindeutig:

    "An application can own up to 2000 emojis that can only be used by
     that app."
    https://docs.discord.com/developers/resources/emoji

Die Emojis des University Bots lassen sich hier also nicht einfach
einsetzen -- sie erschienen als roher Text ``<:zbot:1530...>`` mitten im
Satz statt als Bild. Genau dieser Fehler war dort schon einmal live.

Deshalb werden sie kopiert: ``tools/sync_emojis.py`` laedt die Bilder
vom CDN (die sind frei abrufbar) und legt sie unter dieser App neu an.
Dieses Modul wird dabei ueberschrieben.

Bis das Skript gelaufen ist, ist ``EMOJIS`` leer. Das ist Absicht und
kein Fehler: ``emoji()`` liefert dann den Unicode-Rueckfall, den jeder
Aufrufer mitgibt, und alles sieht aus wie vorher. Ein fest eingetragener
Platzhalter waere schlimmer -- er wuerde als Text erscheinen.
"""

from __future__ import annotations

# Wird von tools/sync_emojis.py gefuellt. Leer = es wurde noch nicht
# uebertragen.
EMOJIS: dict[str, str] = {}


def emoji(name: str, fallback: str = "") -> str:
    """Ein App-Emoji, oder ``fallback``.

    Wirft nie. Ein fehlendes Emoji darf keine Antwort verhindern, und
    ohne Rueckfalltext bleibt einfach nichts stehen -- immer noch besser
    als ein roher ``<:name:123>``-Platzhalter im laufenden Text.
    """

    return EMOJIS.get(name, fallback)


def button_emoji(name: str, fallback: str) -> str:
    """Wie :func:`emoji`, aber garantiert nicht leer.

    Fuer Knoepfe und Auswahlmenues. Discord baut aus einem leeren String
    ein PartialEmoji mit leerem Namen -- kein Fehler beim Erzeugen, aber
    die Komponente wird beim Senden abgelehnt. Ein Aufrufer, der aus
    Versehen ``""`` als Rueckfall uebergibt, wuerde das erst live
    merken.
    """

    value = EMOJIS.get(name) or fallback
    if not value:
        raise ValueError(
            f"button_emoji({name!r}) braucht einen Rueckfall -- ein leeres "
            "Emoji laesst Discord die ganze Komponente ablehnen."
        )
    return value


def has_emojis() -> bool:
    """Ob schon uebertragen wurde. Fuer die Startmeldung."""

    return bool(EMOJIS)
