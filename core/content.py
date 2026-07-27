"""Inhalte, die der Bot in die Kanaele schreibt.

Ein frisch gebauter Server hat 90+ leere Kanaele. Ohne Hinweis weiss niemand,
was in ``🏷️・ʀᴏʟʟᴇɴ-ᴠᴇʀɢᴀʙᴇ`` gehoert oder was ``einladungs-logs`` ueberhaupt
tut. Dieses Modul erzeugt pro Kanal eine angeheftete Startnachricht.

Der Text entsteht aus drei Quellen, in dieser Reihenfolge:

1. ``guide`` — von Hand geschriebene Zeilen im Template
2. der Kanal-``mode`` — erklaert die Regel, die tatsaechlich durchgesetzt wird
3. das ``topic`` — als Rueckfalltext, damit kein Kanal ohne Hinweis bleibt

Damit muss niemand 886 Nachrichten von Hand pflegen: die Templates tragen
ihre Beschreibung bereits, und die Sonderfaelle bekommen zwei, drei Zeilen.
"""

from __future__ import annotations

from .schema import ChannelMode, ChannelSpec, Visibility, Widget

__all__ = [
    "MARKER",
    "has_marker",
    "channel_guide",
    "mode_rule",
    "seed_message",
    "CHECKLIST_ITEMS",
]

# Unsichtbare Signatur in jeder Bot-Nachricht. Damit findet der Bot seine
# eigenen Nachrichten beim zweiten Durchlauf wieder und bearbeitet sie, statt
# sie zu verdoppeln.
#
# Wichtig: Die Marke steht **im View**, nicht im ``content``-Feld. Discord
# lehnt Nachrichten mit Components V2 ab, sobald ``content`` gesetzt ist:
#
#     Invalid Form Body — In content: The 'content' field cannot be used
#     when using IS_COMPONENTS_V2
#
# Deshalb haengt sie unsichtbar an der Fusszeile.
MARKER = "\u200b\u2063"


# Kanalnamen tragen ae/oe/ue, weil Small Caps keine Umlaute kennen. Im
# Fliesstext der Startnachricht sollen sie aber wieder korrekt stehen.
_UNFOLD = (
    ("zaehlen", "zählen"),
    ("vorschlaege", "vorschläge"),
    ("ankuendigungen", "ankündigungen"),
    ("haeufige", "häufige"),
    ("sprachkanaele", "sprachkanäle"),
    ("gespraeche", "gespräche"),
    ("aktivitaeten", "aktivitäten"),
    ("faecher", "fächer"),
    ("pruefungen", "prüfungen"),
    ("lernraeume", "lernräume"),
    ("bueros", "büros"),
    ("buero", "büro"),
    ("behoerden", "behörden"),
    ("wuensche", "wünsche"),
    ("beitraege", "beiträge"),
    ("entbannungsantrag", "entbannungsantrag"),
    ("loeschen", "löschen"),
    ("veroeffentlicht", "veröffentlicht"),
    ("rueckmeldungen", "rückmeldungen"),
    ("qualitaet", "qualität"),
    ("plaene", "pläne"),
    ("raeume", "räume"),
    ("kanaele", "kanäle"),
)


def _unfold(label: str) -> str:
    for folded, proper in _UNFOLD:
        label = label.replace(folded, proper)
    return label


def has_marker(message: object) -> bool:
    """Stammt diese Nachricht aus einer Vorlage des Bots?

    Durchsucht die Components-V2-Baeume nach der unsichtbaren Signatur. Das
    ``content``-Feld wird zusaetzlich geprueft, damit Nachrichten aus
    aelteren Versionen weiterhin erkannt werden.
    """

    if MARKER in (getattr(message, "content", "") or ""):
        return True

    def walk(items) -> bool:
        for item in items or ():
            if MARKER in (getattr(item, "content", "") or ""):
                return True
            if walk(getattr(item, "children", None)):
                return True
            accessory = getattr(item, "accessory", None)
            if accessory is not None and walk([accessory]):
                return True
        return False

    return walk(getattr(message, "components", None))


# --------------------------------------------------------------------------- #
# Regeltexte je Modus
# --------------------------------------------------------------------------- #

_MODE_RULES: dict[ChannelMode, str] = {
    ChannelMode.MEDIA: (
        "Nur Beiträge mit **Bild, Video oder Link**. "
        "Reine Textnachrichten werden automatisch entfernt."
    ),
    ChannelMode.THREADS: "Jeder Beitrag bekommt automatisch einen **eigenen Thread**.",
    ChannelMode.COUNTING: (
        "Immer nur die **nächste Zahl**. Wer sich verzählt, fängt wieder bei 1 an."
    ),
    ChannelMode.ANNOUNCE: "Nur das Team schreibt hier.",
    ChannelMode.LOG: "Automatische Einträge. Bitte **nicht** hineinschreiben.",
}


def mode_rule(spec: ChannelSpec) -> str | None:
    """Die Regel, die fuer diesen Kanal gilt — oder ``None``."""

    rule = _MODE_RULES.get(spec.mode)
    if rule:
        return rule
    # Kanaele ohne eigenen Modus, die trotzdem nur gelesen werden.
    if spec.visibility in {Visibility.READONLY, Visibility.ARCHIVE}:
        return "Nur zum Lesen."
    return None


# --------------------------------------------------------------------------- #
# Widgets
# --------------------------------------------------------------------------- #

_WIDGET_INTRO: dict[Widget, tuple[str, str]] = {
    Widget.VERIFY: (
        "Verifizierung",
        "Klicke auf den Button, um Zugriff auf den Server zu erhalten.",
    ),
    Widget.RULES: (
        "Regeln akzeptieren",
        "Lies die Regeln und bestätige sie mit dem Button. "
        "Erst danach ist der Server vollständig sichtbar.",
    ),
    Widget.ROLES: (
        "Rollen auswählen",
        "Wähle im Menü aus, was auf dich zutrifft. "
        "Eine erneute Auswahl entfernt die Rolle wieder.",
    ),
    Widget.TICKET: (
        "Support-Ticket",
        "Öffne ein Ticket, wenn du Hilfe brauchst. "
        "Es entsteht ein privater Thread, den nur du und das Team sehen.",
    ),
    Widget.CHECKLIST: (
        "Einrichtung abschließen",
        "Diese Punkte kann der Bot nicht automatisch erledigen.",
    ),
}


CHECKLIST_ITEMS: tuple[str, ...] = (
    "Regeltext an den eigenen Server anpassen",
    "Team-Rollen an die richtigen Personen vergeben",
    "Log-Bot verbinden und auf die Log-Kanäle richten",
    "Willkommensnachricht persönlicher formulieren",
    "Premium-Key ändern, falls der Bot öffentlich läuft",
)


# --------------------------------------------------------------------------- #
# Startnachricht
# --------------------------------------------------------------------------- #

def channel_guide(spec: ChannelSpec) -> tuple[str, list[str]] | None:
    """Titel und Textzeilen der angehefteten Startnachricht.

    Gibt ``None`` zurueck, wenn der Kanal keine Nachricht braucht.
    """

    if not spec.wants_message:
        return None

    # Sprechender Titel: Emoji plus lesbarer Name statt Small Caps, denn
    # in der Nachricht selbst ist normale Schrift besser lesbar. Die im
    # Kanalnamen gefalteten Umlaute werden dabei zurueckgeholt.
    title = _unfold(spec.label).replace("-", " ").strip().title()
    if spec.emoji:
        title = f"{spec.emoji}  {title}"

    lines: list[str] = []

    if spec.widget is not Widget.NONE:
        _, intro = _WIDGET_INTRO[spec.widget]
        lines.append(intro)
    elif spec.guide:
        lines.extend(spec.guide)
    elif spec.topic:
        lines.append(spec.topic)

    # Bei Widgets erklaert der Button selbst, was zu tun ist — eine zusaetzliche
    # Regelzeile wie "Nur zum Lesen" waere dort irrefuehrend.
    if spec.widget is Widget.NONE:
        rule = mode_rule(spec)
        if rule and rule not in lines:
            lines.append(rule)

    if spec.widget is Widget.CHECKLIST:
        lines.append("")
        lines.extend(f"☐ {item}" for item in CHECKLIST_ITEMS)

    return title, lines


def seed_message(spec: ChannelSpec) -> str | None:
    """Erste inhaltliche Nachricht, damit der Kanal nicht leer wirkt."""

    if spec.seed:
        return spec.seed
    if spec.mode is ChannelMode.COUNTING:
        return "1"
    return None
