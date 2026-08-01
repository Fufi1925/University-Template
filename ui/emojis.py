"""Die Emojis dieser App.

App-Emojis gehoeren genau *einer* Anwendung. Discord ist da eindeutig:

    "An application can own up to 2000 emojis that can only be used by
     that app."
    https://docs.discord.com/developers/resources/emoji

Die Emojis des University Bots lassen sich hier also nicht einsetzen --
sie erschienen als roher Text ``<:zbot:1530...>`` mitten im Satz statt
als Bild. Genau dieser Fehler war dort schon einmal live.

Deshalb legt ``core.emoji_sync`` sie beim Start unter dieser App an und
ruft danach :func:`load` mit dem Ergebnis auf. Bis dahin ist die Tabelle
leer, und alles faellt auf die Unicode-Zeichen zurueck, die jeder
Aufrufer mitgibt.

Bewusst zur Laufzeit gefuellt und nicht als Datei geschrieben: eine
generierte Quelldatei muesste nach dem Schreiben neu geladen werden, und
der University Bot startet sich dafuer selbst neu. Ein Dict im Speicher
spart diesen Neustart.
"""

from __future__ import annotations

# Wird beim Start von core.emoji_sync gefuellt. Leer heisst: noch nicht
# uebertragen, oder EMOJI_SYNC steht auf "false".
EMOJIS: dict[str, str] = {}


def load(mapping: dict[str, str]) -> None:
    """Die Tabelle setzen. Ruft ``core.emoji_sync`` nach dem Abgleich auf."""

    EMOJIS.clear()
    EMOJIS.update(mapping)


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
