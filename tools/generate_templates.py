#!/usr/bin/env python3
"""Erzeugt die JSON-Dateien in ``templates/``.

Die Templates selbst sind reine Daten — dieses Skript existiert nur, damit die
gemeinsamen Bausteine (Sprachbereich, Logs, Team-Bereiche) in allen Vorlagen
identisch bleiben, statt durch Copy-Paste auseinanderzudriften.

Hauptsprache ist Deutsch: alle Kanal- und Kategorienamen sind deutsch.
Der Sprachbereich enthält bewusst nur Deutsch und English.

Zur Typografie: Kanal- und Kategorienamen sind mit ae/oe/ue geschrieben, weil
Unicode keine Small-Caps-Umlaute kennt und ``ä`` im Namen sonst optisch aus der
Zeile brechen würde. Beschreibungen, Taglines und Topics sind normaler
Fließtext und verwenden echte Umlaute.

Kanalinhalte (``mode``, ``widget``, ``guide``, ``reactions``) werden von
``tools/enrich_content.py`` regelbasiert gesetzt, damit sich ein ``memes``-Kanal
in jeder Vorlage gleich verhält.

Nach Änderungen ausführen:  ``python tools/generate_templates.py``
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
OUT_DIR = BASE_DIR / "templates"

sys.path.insert(0, str(BASE_DIR))


# --------------------------------------------------------------------------- #
# Helfer
# --------------------------------------------------------------------------- #

def ch(
    label: str,
    emoji: str,
    kind: str = "text",
    *,
    topic: str | None = None,
    visibility: str | None = None,
    slowmode: int = 0,
    user_limit: int = 0,
    nsfw: bool = False,
    mode: str = "free",
    widget: str = "none",
    guide: list[str] | None = None,
    reactions: list[str] | None = None,
    seed: str | None = None,
) -> dict[str, Any]:
    entry: dict[str, Any] = {"label": label, "emoji": emoji}
    if kind != "text":
        entry["kind"] = kind
    if topic:
        entry["topic"] = topic
    if visibility:
        entry["visibility"] = visibility
    if slowmode:
        entry["slowmode"] = slowmode
    if user_limit:
        entry["user_limit"] = user_limit
    if nsfw:
        entry["nsfw"] = True
    if mode != "free":
        entry["mode"] = mode
    if widget != "none":
        entry["widget"] = widget
    if guide:
        entry["guide"] = guide
    if reactions:
        entry["reactions"] = reactions
    if seed:
        entry["seed"] = seed
    return entry


def cat(
    label: str,
    emoji: str,
    visibility: str,
    channels: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "label": label,
        "emoji": emoji,
        "visibility": visibility,
        "channels": channels,
    }


# Der Sprachkanal, aus dem "Join to Create" eigene Raeume macht.
#
# Zwei Fehler haengen daran, und beide waren echt:
#
#   1. Die Uebergabe an den University Bot suchte einen Kanal mit dem
#      Slug "allgemeiner-talk". Neun der vierzehn Vorlagen haben keinen
#      -- clan, gaming, rp, social, business, creator, esports, study
#      und support. Bei denen meldete ``capabilities["j2c"]`` trotzdem
#      True (es reichte *irgendein* Sprachkanal), das Dashboard bot den
#      Schalter an, und der Nutzer las hinterher im Bericht
#      "Uebersprungen — channels.j2c fehlt".
#
#   2. Wo es den Kanal gab, war die Wahl trotzdem falsch. Der Hub
#      verschiebt jeden, der ihn betritt, sofort in einen frisch
#      angelegten Raum -- man kann sich darin nicht unterhalten. Ein
#      Kanal namens "allgemeiner talk", in dem nie jemand ankommt, ist
#      genau die Art Ueberraschung, die niemand mit dem Bot in
#      Verbindung bringt.
#
# Deshalb ein eigener Kanal mit sprechendem Namen, in jeder Vorlage,
# immer als erster seiner Kategorie: dort sucht man ihn.
def j2c_channel() -> dict[str, Any]:
    return ch("eigenen-talk-erstellen", "➕", "voice", user_limit=1)


def role(
    key: str,
    label: str,
    emoji: str,
    colour: str,
    tier: str,
    *,
    hoist: bool = True,
    mentionable: bool = False,
) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "emoji": emoji,
        "colour": colour,
        "tier": tier,
        "hoist": hoist,
        "mentionable": mentionable,
    }


# --------------------------------------------------------------------------- #
# Gemeinsame Bausteine fuer die neueren Vorlagen
# --------------------------------------------------------------------------- #
# Die aelteren Fabriken weiter unten tragen dieselben Bloecks noch von Hand;
# neue Vorlagen nutzen diese Helfer, damit die Pflichtteile identisch bleiben.
# Die Testsuite erzwingt: Sprachbereich (deutsch/english), Sprach-Talks,
# Log-Suite, Gate-Kategorie und die deutschen Kanalnamen.

def gate_category(extra: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Eingangsschleuse: Willkommen, Verify, Regeln, häufige Fragen."""

    return cat("willkommen", "🚪", "gate", [
        ch("willkommen", "👋", topic="Willkommen! Verifiziere dich, um den Server zu sehen.", visibility="readonly",
            guide=[
                "Schön, dass du da bist.",
                "Verifiziere dich nebenan, danach siehst du den gesamten Server.",
            ],
        ),
        ch("verifizieren", "✅", topic="Hier verifizieren", widget="verify"),
        ch("regeln", "📜", topic="Serverregeln", visibility="readonly", widget="rules"),
        ch("haeufige-fragen", "❔", topic="Häufig gestellte Fragen", visibility="readonly",
            guide=[
                "Die häufigsten Fragen und ihre Antworten.",
                "Ist deine Frage nicht dabei, melde dich beim Team.",
            ],
        ),
        *(extra or []),
    ])


def info_category(*extra: dict[str, Any]) -> dict[str, Any]:
    """Ankündigungen, Rollenvergabe und ein paar Pflicht-Kanäle."""

    return cat("information", "📌", "readonly", [
        ch("ankuendigungen", "📢", "news", topic="Wichtige Ankündigungen", mode="announce"),
        ch("neuigkeiten", "🆕", topic="Server- und Bot-Updates", mode="announce"),
        ch("rollen-vergabe", "🏷️", topic="Rollen selbst vergeben", widget="roles"),
        ch("partner", "🤝", topic="Unsere Partner",
            guide=[
                "Server und Projekte, mit denen wir zusammenarbeiten.",
            ],
        ),
        ch("team-vorstellung", "👥", topic="Wer gehört zum Team?",
            guide=[
                "Wer zum Team gehört und wofür zuständig ist.",
            ],
        ),
        *extra,
    ])


def hilfe_category(*extra: dict[str, Any]) -> dict[str, Any]:
    """Tickets, Community-Hilfe, Fehler und Vorschläge."""

    return cat("hilfe", "🛟", "public", [
        ch("ticket-eroeffnen", "🎫", topic="Hier ein Support-Ticket öffnen",
           visibility="readonly", widget="ticket"),
        ch("hilfe-und-support", "❓", "forum", topic="Frag die Community"),
        ch("fehler-melden", "🐛", topic="Fehler melden", mode="threads"),
        ch("vorschlaege", "💡", topic="Ideen für den Server", mode="threads", reactions=["👍", "👎"]),
        *(extra or []),
    ])


def sprachen_category() -> dict[str, Any]:
    return cat("sprachen", "🌍", "public", [
        ch("deutsch", "🇩🇪", topic="Deutschsprachiger Chat — die Hauptsprache", slowmode=3),
        ch("english", "🇬🇧", topic="English speaking chat", slowmode=3),
    ])


def sprach_talks_category() -> dict[str, Any]:
    return cat("sprach-talks", "🗣️", "public", [
        ch("deutsch-talk", "🇩🇪", "voice"),
        ch("english-talk", "🇬🇧", "voice"),
        ch("deutsch-talk-2", "🇩🇪", "voice", user_limit=10),
        ch("english-talk-2", "🇬🇧", "voice", user_limit=10),
    ])


def voice_category(label: str, emoji: str, rooms: list[dict[str, Any]]) -> dict[str, Any]:
    """Ein Sprachbereich mit Join-to-Create-Kanal an erster Stelle."""

    return cat(label, emoji, "public", [j2c_channel(), *rooms])


def team_category() -> dict[str, Any]:
    return cat("team", "🛡️", "staff", [
        ch("team-chat", "💼", topic="Interner Teamchat"),
        ch("team-ankuendigungen", "📣", topic="Ankündigungen fürs Team", mode="announce"),
        ch("aufgaben", "📋", topic="Aufgaben und Zuständigkeiten", widget="checklist"),
        ch("bewerbungen", "🧾", topic="Eingehende Bewerbungen", mode="threads"),
        ch("meldungen", "🚨", topic="Gemeldete Vorfälle"),
        ch("schichtplan", "🗓️", topic="Wer hat wann Dienst?"),
        ch("team-talk", "🎙️", "voice", user_limit=15),
        ch("besprechungsraum", "🪑", "voice", user_limit=25),
    ])


def leitung_category() -> dict[str, Any]:
    return cat("leitung", "👑", "leadership", [
        ch("leitungs-chat", "🏛️", topic="Nur für die Serverleitung"),
        ch("planung", "🗺️", topic="Planung und Ausrichtung"),
        ch("personal", "🧑‍💼", topic="Personalthemen"),
        ch("leitungs-talk", "🔐", "voice", user_limit=10),
    ])


def logs_category() -> dict[str, Any]:
    return cat("logs", "📜", "staff", [
        ch("mod-logs", "🔨", topic="Moderationsaktionen", mode="log"),
        ch("mitglieder-logs", "👥", topic="Beitritte und Austritte", mode="log"),
        ch("nachrichten-logs", "✏️", topic="Bearbeitete und gelöschte Nachrichten", mode="log"),
        ch("sprach-logs", "🔊", topic="Voice-Aktivität", mode="log"),
        ch("rollen-logs", "🏷️", topic="Rollenänderungen", mode="log"),
        ch("kanal-logs", "🗂️", topic="Kanaländerungen", mode="log"),
        ch("social-logs", "📱", topic="Social-Media-Feeds und Erwähnungen", mode="log"),
        ch("bot-logs", "🤖", topic="Bot-Ereignisse", mode="log"),
        ch("einladungs-logs", "🔗", topic="Einladungs-Tracking", mode="log"),
        ch("server-logs", "🗃️", topic="Alles Übrige", mode="log"),
    ])


# --------------------------------------------------------------------------- #
# Templates
# --------------------------------------------------------------------------- #

def community() -> dict[str, Any]:
    return {
        "key": "community",
        "name": "Community Discord",
        "emoji": "🌐",
        "tagline": "Der Allrounder für jede wachsende Community",
        "premium": False,
        "accent": "#5865F2",
        "description": (
            "Ein vollständig strukturierter Community-Server auf Deutsch: klare "
            "Eingangsschleuse, lebendige Chatbereiche, Events, Kreativzone und "
            "ein abgeschirmter Team- und Log-Bereich. Ideal, wenn du ohne Umwege "
            "einen professionellen Server willst."
        ),
        "highlights": [
            "Komplett deutsche Kanalnamen in Small Caps",
            "Verify-Schleuse — Neulinge sehen erst nach der Freigabe den ganzen Server",
            "Sprachbereich mit Deutsch und English",
            "Vollständige Log-Suite inklusive Social- und Voice-Logs",
        ],
        "roles": [
            role("creator", "Content Creator", "🎨", "#F97316", "trusted"),
            role("event_team", "Event Team", "🎉", "#EAB308", "helper"),
            role("designer", "Designer", "🖌️", "#EC4899", "trusted", hoist=False),
        ],
        "categories": [
            cat("willkommen", "🚪", "gate", [
                ch("willkommen", "👋", topic="Willkommen! Verifiziere dich, um den Server zu sehen.", visibility="readonly",
                    guide=[
                        "Schön, dass du da bist.",
                        "Verifiziere dich nebenan, danach siehst du den gesamten Server.",
                    ],
                ),
                ch("verifizieren", "✅", topic="Hier verifizieren", widget="verify"),
                ch("regeln", "📜", topic="Serverregeln", visibility="readonly", widget="rules"),
                ch("haeufige-fragen", "❔", topic="Häufig gestellte Fragen", visibility="readonly",
                    guide=[
                        "Die häufigsten Fragen und ihre Antworten.",
                        "Ist deine Frage nicht dabei, melde dich beim Team.",
                    ],
                ),
            ]),
            cat("information", "📌", "readonly", [
                ch("ankuendigungen", "📢", "news", topic="Wichtige Ankündigungen", mode="announce"),
                ch("neuigkeiten", "🆕", topic="Server- und Bot-Updates", mode="announce"),
                ch("rollen-vergabe", "🏷️", topic="Rollen selbst vergeben", widget="roles"),
                ch("partner", "🤝", topic="Unsere Partner",
                    guide=[
                        "Server und Projekte, mit denen wir zusammenarbeiten.",
                    ],
                ),
                ch("gewinnspiele", "🎁", topic="Aktuelle Gewinnspiele", reactions=["🎉"]),
                ch("team-vorstellung", "👥", topic="Wer gehört zum Team?",
                    guide=[
                        "Wer zum Team gehört und wofür zuständig ist.",
                    ],
                ),
            ]),
            cat("community", "💬", "public", [
                ch("allgemein", "💭", topic="Der Hauptchat", slowmode=3,
                    guide=[
                        "Der Hauptchat für alles, was keinen eigenen Kanal hat.",
                    ],
                ),
                ch("plauderecke", "🫧", topic="Kurz und locker"),
                ch("bilder-und-clips", "🖼️", topic="Bilder, Clips, Fundstücke", mode="media"),
                ch("memes", "😂", topic="Nur Memes", mode="media", reactions=["😂"]),
                ch("haustiere", "🐾", topic="Deine Haustiere", mode="media"),
                ch("essen", "🍕", topic="Essen und Rezepte"),
                ch("musik-tipps", "🎧", topic="Was hörst du gerade?"),
                ch("sport", "⚽", topic="Sport und Fitness"),
                ch("technik", "💻", topic="Technik und Gadgets"),
                ch("reisen", "✈️", topic="Reisen und Urlaub"),
                ch("sonstiges", "🌙", topic="Alles, was sonst nirgends passt"),
                ch("bot-befehle", "🤖", topic="Bot-Befehle gehören hierher",
                    guide=[
                        "Bot-Befehle gehören hierher, damit sie den Hauptchat nicht zumüllen.",
                    ],
                ),
                ch("zaehlen", "🔢", topic="Gemeinsam zählen", mode="counting",
                    guide=[
                        "Gemeinsam so weit zählen wie möglich.",
                    ],
                ),
                ch("geburtstage", "🎂", topic="Wer hat heute Geburtstag?", reactions=["🎂"]),
            ]),
            cat("sprachen", "🌍", "public", [
                ch("deutsch", "🇩🇪", topic="Deutschsprachiger Chat — die Hauptsprache", slowmode=3),
                ch("english", "🇬🇧", topic="English speaking chat", slowmode=3),
            ]),
            cat("sprach-talks", "🗣️", "public", [
                ch("deutsch-talk", "🇩🇪", "voice"),
                ch("english-talk", "🇬🇧", "voice"),
                ch("deutsch-talk-2", "🇩🇪", "voice", user_limit=10),
                ch("english-talk-2", "🇬🇧", "voice", user_limit=10),
            ]),
            cat("sprachkanaele", "🔊", "public", [
                j2c_channel(),
                ch("allgemeiner-talk", "🎙️", "voice"),
                ch("chill-ecke", "☕", "voice", user_limit=10),
                ch("musik", "🎶", "voice"),
                ch("zu-zweit", "👥", "voice", user_limit=2),
                ch("zu-dritt", "👨‍👩‍👦", "voice", user_limit=3),
                ch("gruppe", "🛡️", "voice", user_limit=5),
                ch("lernen", "📚", "voice"),
                ch("stream-raum", "📺", "voice", user_limit=20),
                ch("nachtschicht", "🌙", "voice", user_limit=12),
                ch("abwesend", "💤", "voice"),
            ]),
            cat("veranstaltungen", "🎉", "public", [
                ch("event-ankuendigungen", "📅", "news", topic="Kommende Events", visibility="readonly", mode="announce"),
                ch("event-anmeldung", "🎟️", topic="Anmeldungen"),
                ch("event-chat", "🎊", topic="Rund ums Event"),
                ch("event-rueckblick", "📷", topic="Bilder vergangener Events"),
                ch("umfragen", "📊", topic="Abstimmungen", reactions=["👍", "👎"]),
                ch("event-buehne", "🎤", "stage"),
                ch("event-talk", "🎪", "voice", user_limit=50),
            ]),
            cat("kreativ", "🎨", "public", [
                ch("vorzeigen", "🖼️", topic="Zeig deine Arbeit", slowmode=60, mode="media", reactions=["⭐"]),
                ch("rueckmeldungen", "💡", topic="Konstruktive Kritik"),
                ch("fundstuecke", "📚", topic="Werkzeuge und Fundstücke"),
                ch("zusammenarbeit", "🤝", topic="Partner für Projekte finden"),
                ch("auftraege", "💼", topic="Auftragsarbeiten", slowmode=600),
            ]),
            cat("gaming", "🎮", "public", [
                ch("gaming-chat", "🎮", topic="Allgemeiner Gaming-Chat"),
                ch("mitspieler-suche", "🔎", topic="Mitspieler finden", mode="threads"),
                ch("spiele-tipps", "🏆", topic="Empfehlungen und Highlights"),
                ch("gaming-talk", "🕹️", "voice", user_limit=10),
            ]),
            cat("hilfe", "🛟", "public", [
                ch("ticket-eroeffnen", "🎫", topic="Hier ein Support-Ticket öffnen",
                   visibility="readonly", widget="ticket"),
                ch("hilfe-und-support", "❓", "forum", topic="Frag die Community"),
                ch("fehler-melden", "🐛", topic="Fehler melden", mode="threads"),
                ch("vorschlaege", "💡", topic="Ideen für den Server", mode="threads", reactions=["👍", "👎"]),
                ch("beschwerden", "📣", topic="Beschwerden über Mitglieder", mode="threads"),
                ch("entbannungsantrag", "⚖️", topic="Einspruch gegen eine Strafe", mode="threads"),
            ]),
            cat("social media", "📱", "public", [
                ch("instagram", "📸", topic="Instagram-Beiträge", mode="media"),
                ch("tiktok", "🎵", topic="TikTok-Clips", mode="media"),
                ch("youtube", "▶️", topic="YouTube-Uploads", mode="media"),
                ch("twitch", "🟣", topic="Twitch-Streams", mode="media"),
                ch("x-twitter", "🐦", topic="Beiträge von X", mode="media"),
                ch("eigenwerbung", "📣", topic="Eigene Projekte vorstellen", slowmode=300,
                    guide=[
                        "Eigene Projekte vorstellen — ein Beitrag pro Person, kein Spam.",
                    ],
                ),
            ]),
            cat("vip bereich", "💎", "vip", [
                ch("vip-chat", "💬", topic="Exklusiv für VIPs und Booster"),
                ch("vip-vorteile", "🎁", topic="Deine Vorteile", visibility="readonly"),
                ch("vip-wuensche", "🌠", topic="Wünsche und Rückmeldungen"),
                ch("vip-talk", "🥂", "voice", user_limit=15),
            ]),
            cat("team", "🛡️", "staff", [
                ch("team-chat", "💼", topic="Interner Teamchat"),
                ch("team-ankuendigungen", "📣", topic="Ankündigungen fürs Team", mode="announce"),
                ch("aufgaben", "📋", topic="Aufgaben und Zuständigkeiten", widget="checklist"),
                ch("bewerbungen", "🧾", topic="Eingehende Bewerbungen", mode="threads"),
                ch("meldungen", "🚨", topic="Gemeldete Vorfälle"),
                ch("schichtplan", "🗓️", topic="Wer hat wann Dienst?"),
                ch("team-talk", "🎙️", "voice", user_limit=15),
                ch("besprechungsraum", "🪑", "voice", user_limit=25),
            ]),
            cat("leitung", "👑", "leadership", [
                ch("leitungs-chat", "🏛️", topic="Nur für die Serverleitung"),
                ch("planung", "🗺️", topic="Planung und Ausrichtung"),
                ch("personal", "🧑‍💼", topic="Personalthemen"),
                ch("leitungs-talk", "🔐", "voice", user_limit=10),
            ]),
            cat("logs", "📜", "staff", [
                ch("mod-logs", "🔨", topic="Moderationsaktionen", mode="log"),
                ch("mitglieder-logs", "👥", topic="Beitritte und Austritte", mode="log"),
                ch("nachrichten-logs", "✏️", topic="Bearbeitete und gelöschte Nachrichten", mode="log"),
                ch("sprach-logs", "🔊", topic="Voice-Aktivität", mode="log"),
                ch("rollen-logs", "🏷️", topic="Rollenänderungen", mode="log"),
                ch("kanal-logs", "🗂️", topic="Kanaländerungen", mode="log"),
                ch("social-logs", "📱", topic="Social-Media-Feeds und Erwähnungen", mode="log"),
                ch("bot-logs", "🤖", topic="Bot-Ereignisse", mode="log"),
                ch("einladungs-logs", "🔗", topic="Einladungs-Tracking", mode="log"),
                ch("server-logs", "🗃️", topic="Alles Übrige", mode="log"),
            ]),
        ],
    }


def rp() -> dict[str, Any]:
    return {
        "key": "rp",
        "name": "RP Server",
        "emoji": "🎭",
        "tagline": "Roleplay mit Fraktionen, Behörden und Wirtschaft",
        "premium": True,
        "accent": "#9333EA",
        "description": (
            "Ein durchgeplanter Roleplay-Server auf Deutsch. Die Reihenfolge ist "
            "bewusst gewählt: Flughafen und Verify zuerst, dann Regelwerke, "
            "RP-Start, Fraktionen, Behörden und Wirtschaft. Dazu abgeschirmte "
            "Team-, Büro- und Log-Bereiche."
        ),
        "highlights": [
            "Bewusste Reihenfolge: Flughafen → Verify → Regelwerk → RP",
            "Eigene Bereiche für Fraktionen, Behörden und Wirtschaft",
            "Viele RP-Talks inklusive Funk- und Gerichtssaal",
            "Getrennte Büro- und Aktenbereiche für das High-Team",
        ],
        "roles": [
            role("roleplayer", "Roleplayer", "🎭", "#7C3AED", "member", hoist=False),
            role("whitelist", "Whitelist", "📝", "#8B5CF6", "trusted", hoist=False),
            role("faction_lead", "Fraktionsleitung", "🏴", "#A21CAF", "helper"),
            role("gov", "Behoerde", "🏛️", "#0EA5E9", "helper"),
            role("emergency", "Rettungsdienst", "🚑", "#EF4444", "helper"),
            role("police", "Polizei", "🚓", "#2563EB", "helper"),
            role("rp_event", "RP Event Team", "🎬", "#C026D3", "helper"),
            role("supporter_rp", "RP Support", "🧭", "#14B8A6", "helper"),
        ],
        "categories": [
            cat("flughafen", "✈️", "gate", [
                ch("ankunft", "🛬", topic="Hier landest du. Willkommen!", visibility="readonly"),
                ch("einreise", "🛂", topic="Einreiseformalitäten"),
                ch("abflug", "🛫", topic="Abmeldung vom Server"),
                ch("flughafen-info", "📋", topic="Alles zum Einstieg", visibility="readonly"),
                ch("fundbuero", "🧳", topic="Verlorenes und Gefundenes"),
            ]),
            cat("verifizierung", "✅", "gate", [
                ch("verifizieren", "🔓", topic="Verifizierung starten", widget="verify"),
                ch("verify-info", "📖", topic="So läuft die Verifizierung", visibility="readonly"),
                ch("verify-fragen", "❔", topic="Fragen zur Verifizierung"),
                ch("whitelist-antrag", "📝", topic="Whitelist beantragen"),
            ]),
            cat("regelwerk", "📜", "readonly", [
                ch("serverregeln", "⚖️", topic="Die verbindlichen Serverregeln", widget="rules"),
                ch("rp-regeln", "🎭", topic="Roleplay-spezifische Regeln"),
                ch("fraktionsregeln", "🏴", topic="Regeln für Fraktionen"),
                ch("strafenkatalog", "📕", topic="Welche Strafe folgt worauf"),
                ch("regel-aenderungen", "🔄", topic="Änderungen am Regelwerk", mode="announce"),
            ]),
            cat("rp start", "🚀", "public", [
                ch("ankuendigungen", "📢", "news", topic="Server-News", visibility="readonly", mode="announce"),
                ch("stadt-nachrichten", "📰", topic="Was passiert in der Stadt?", mode="announce"),
                ch("charaktere", "🧑‍🎤", topic="Stelle deinen Charakter vor", slowmode=120),
                ch("steckbriefe", "📇", topic="Charakter-Steckbriefe"),
                ch("rp-suche", "🔍", topic="Mitspieler für Szenen finden"),
                ch("ooc-chat", "💬", topic="Ausserhalb des Rollenspiels"),
            ]),
            cat("fraktionen", "🏴", "public", [
                ch("fraktions-news", "📣", topic="Neues aus den Fraktionen", visibility="readonly", mode="announce"),
                ch("fraktionssuche", "🔎", topic="Fraktion gesucht?"),
                ch("fraktions-bewerbung", "📨", topic="Fraktionsbewerbungen"),
                ch("buendnisse", "🤝", topic="Bündnisse und Konflikte"),
                ch("fraktions-chat", "💼", topic="Übergreifender Austausch"),
                ch("fraktions-talk", "🎙️", "voice", user_limit=20),
            ]),
            cat("behoerden", "🏛️", "public", [
                ch("polizei", "🚓", topic="Polizeidienststelle"),
                ch("rettungsdienst", "🚑", topic="Rettungsdienst und Krankenhaus"),
                ch("justiz", "⚖️", topic="Gericht und Anwälte"),
                ch("stadtverwaltung", "🏢", topic="Verwaltung und Bürgeramt"),
                ch("fahndung", "🚨", topic="Aktuelle Fahndungen"),
                ch("notruf", "📞", "voice", user_limit=10),
                ch("gerichtssaal", "👨‍⚖️", "voice", user_limit=25),
            ]),
            cat("wirtschaft", "💰", "public", [
                ch("marktplatz", "🛒", topic="Kaufen und verkaufen", slowmode=60),
                ch("fahrzeuge", "🚗", topic="Fahrzeughandel"),
                ch("immobilien", "🏠", topic="Häuser und Grundstücke"),
                ch("stellenangebote", "💼", topic="Jobs in der Stadt"),
                ch("werbung", "📺", topic="Werbung für dein Unternehmen", slowmode=600),
            ]),
            cat("rp talks", "🎙️", "public", [
                j2c_channel(),
                ch("stadt-1", "🏙️", "voice"),
                ch("stadt-2", "🌆", "voice"),
                ch("stadt-3", "🌃", "voice"),
                ch("funk-polizei", "📻", "voice", user_limit=15),
                ch("funk-rettung", "🚨", "voice", user_limit=15),
                ch("fraktion-a", "🅰️", "voice", user_limit=12),
                ch("fraktion-b", "🅱️", "voice", user_limit=12),
                ch("privat-1", "🔒", "voice", user_limit=4),
                ch("privat-2", "🔒", "voice", user_limit=4),
                ch("warteraum", "⏳", "voice"),
                ch("abwesend", "💤", "voice"),
            ]),
            cat("sprachen", "🌍", "public", [
                ch("deutsch", "🇩🇪", topic="Deutschsprachiger Chat — die Hauptsprache", slowmode=3),
                ch("english", "🇬🇧", topic="English speaking chat", slowmode=3),
            ]),
            cat("sprach-talks", "🗣️", "public", [
                ch("deutsch-talk", "🇩🇪", "voice"),
                ch("english-talk", "🇬🇧", "voice"),
                ch("deutsch-talk-2", "🇩🇪", "voice", user_limit=10),
                ch("english-talk-2", "🇬🇧", "voice", user_limit=10),
            ]),
            cat("freizeit", "🎲", "public", [
                ch("sonstiges", "🌙", topic="Alles ausserhalb des RP"),
                ch("memes", "😂", topic="Memes aus der Stadt", mode="media", reactions=["😂"]),
                ch("clips", "🎬", topic="Deine besten Szenen", mode="media", reactions=["🔥"]),
                ch("bildschirmfotos", "📸", topic="Bilder aus dem RP", mode="media"),
                ch("bot-befehle", "🤖", topic="Bot-Befehle",
                    guide=[
                        "Bot-Befehle gehören hierher, damit sie den Hauptchat nicht zumüllen.",
                    ],
                ),
                ch("freizeit-talk", "☕", "voice"),
            ]),
            cat("hilfe", "🛟", "public", [
                ch("ticket-eroeffnen", "🎫", topic="Hier ein Support-Ticket öffnen",
                   visibility="readonly", widget="ticket"),
                ch("support", "❓", "forum", topic="Tickets und Hilfe"),
                ch("fehler-melden", "🐛", topic="Fehler melden", mode="threads"),
                ch("beschwerden", "📣", topic="Beschwerden über Spieler", mode="threads"),
                ch("entbannungsantrag", "⚖️", topic="Entbannungsanträge", mode="threads"),
                ch("vorschlaege", "💡", topic="Ideen für die Stadt", mode="threads", reactions=["👍", "👎"]),
                ch("warteschlange", "⏱️", "voice"),
                ch("support-1", "🧑‍💻", "voice", user_limit=3),
                ch("support-2", "🧑‍💻", "voice", user_limit=3),
            ]),
            cat("vip bereich", "💎", "vip", [
                ch("vip-chat", "💬", topic="Exklusiv für VIPs und Booster"),
                ch("vip-vorteile", "🎁", topic="Deine Vorteile", visibility="readonly"),
                ch("vip-wuensche", "🌠", topic="Wünsche und Rückmeldungen"),
                ch("vip-talk", "🥂", "voice", user_limit=15),
            ]),
            cat("team", "🛡️", "staff", [
                ch("team-chat", "💼", topic="Interner Teamchat"),
                ch("team-ankuendigungen", "📣", topic="Ankündigungen fürs Team", mode="announce"),
                ch("aufgaben", "📋", topic="Aufgaben und Zuständigkeiten", widget="checklist"),
                ch("bewerbungen", "🧾", topic="Eingehende Bewerbungen", mode="threads"),
                ch("meldungen", "🚨", topic="Gemeldete Vorfälle"),
                ch("schichtplan", "🗓️", topic="Wer hat wann Dienst?"),
                ch("team-talk", "🎙️", "voice", user_limit=15),
                ch("besprechungsraum", "🪑", "voice", user_limit=25),
            ]),
            cat("bueros", "💼", "leadership", [
                ch("buero-leitung", "🗝️", topic="Büro der Serverleitung"),
                ch("buero-entwicklung", "🛠️", topic="Entwicklung und Skripte"),
                ch("buero-personal", "🧑‍💼", topic="Personalakten"),
                ch("akten", "🗄️", topic="Archiv", visibility="archive"),
                ch("besprechung", "🪑", "voice", user_limit=12),
            ]),
            cat("leitung", "👑", "leadership", [
                ch("leitungs-chat", "🏛️", topic="Nur für die Serverleitung"),
                ch("planung", "🗺️", topic="Planung und Ausrichtung"),
                ch("personal", "🧑‍💼", topic="Personalthemen"),
                ch("leitungs-talk", "🔐", "voice", user_limit=10),
            ]),
            cat("logs", "📜", "staff", [
                ch("mod-logs", "🔨", topic="Moderationsaktionen", mode="log"),
                ch("mitglieder-logs", "👥", topic="Beitritte und Austritte", mode="log"),
                ch("nachrichten-logs", "✏️", topic="Bearbeitete und gelöschte Nachrichten", mode="log"),
                ch("sprach-logs", "🔊", topic="Voice-Aktivität", mode="log"),
                ch("rollen-logs", "🏷️", topic="Rollenänderungen", mode="log"),
                ch("kanal-logs", "🗂️", topic="Kanaländerungen", mode="log"),
                ch("social-logs", "📱", topic="Social-Media-Feeds und Erwähnungen", mode="log"),
                ch("bot-logs", "🤖", topic="Bot-Ereignisse", mode="log"),
                ch("einladungs-logs", "🔗", topic="Einladungs-Tracking", mode="log"),
                ch("server-logs", "🗃️", topic="Alles Übrige", mode="log"),
            ]),
        ],
    }


def social() -> dict[str, Any]:
    return {
        "key": "social",
        "name": "Social Lounge",
        "emoji": "☕",
        "tagline": "Chillen, quatschen, Leute treffen",
        "premium": False,
        "accent": "#14B8A6",
        "description": (
            "Der geselligste Server der Sammlung. Der Fokus liegt auf Gesprächen: "
            "viele Themenkanäle, ein großzügiger Voice-Bereich, Medien, "
            "Aktivitäten und eine vollständige Social-Log-Struktur."
        ),
        "highlights": [
            "Größter Voice-Bereich aller Vorlagen",
            "Viele Themenkanäle für echte Gespräche",
            "Aktivitäten, Watch-Partys und Musikräume",
            "Vorbereitete Vorstellungs- und Kennenlern-Kanäle",
        ],
        "roles": [
            role("host", "Lounge Host", "🌟", "#F97316", "helper"),
            role("nightowl", "Nachteule", "🌙", "#6366F1", "trusted", hoist=False),
            role("dj", "DJ", "🎧", "#EC4899", "trusted", hoist=False),
            role("welcomer", "Begruesser", "🫶", "#22D3EE", "helper"),
        ],
        "categories": [
            cat("willkommen", "🚪", "gate", [
                ch("willkommen", "👋", topic="Willkommen! Verifiziere dich, um den Server zu sehen.", visibility="readonly",
                    guide=[
                        "Schön, dass du da bist.",
                        "Verifiziere dich nebenan, danach siehst du den gesamten Server.",
                    ],
                ),
                ch("verifizieren", "✅", topic="Hier verifizieren", widget="verify"),
                ch("regeln", "📜", topic="Serverregeln", visibility="readonly", widget="rules"),
                ch("haeufige-fragen", "❔", topic="Häufig gestellte Fragen", visibility="readonly",
                    guide=[
                        "Die häufigsten Fragen und ihre Antworten.",
                        "Ist deine Frage nicht dabei, melde dich beim Team.",
                    ],
                ),
            ]),
            cat("information", "📌", "readonly", [
                ch("ankuendigungen", "📢", "news", topic="Wichtige Ankündigungen", mode="announce"),
                ch("neuigkeiten", "🆕", topic="Server- und Bot-Updates", mode="announce"),
                ch("rollen-vergabe", "🏷️", topic="Rollen selbst vergeben", widget="roles"),
                ch("partner", "🤝", topic="Unsere Partner",
                    guide=[
                        "Server und Projekte, mit denen wir zusammenarbeiten.",
                    ],
                ),
                ch("gewinnspiele", "🎁", topic="Aktuelle Gewinnspiele", reactions=["🎉"]),
                ch("team-vorstellung", "👥", topic="Wer gehört zum Team?",
                    guide=[
                        "Wer zum Team gehört und wofür zuständig ist.",
                    ],
                ),
                ch("vorstellungen", "🙋", topic="Stell dich kurz vor"),
            ]),
            cat("lounge", "☕", "public", [
                ch("allgemein", "💬", topic="Der Hauptchat", slowmode=3,
                    guide=[
                        "Der Hauptchat für alles, was keinen eigenen Kanal hat.",
                    ],
                ),
                ch("sorgen-ecke", "🫂", topic="Wenn du reden musst", slowmode=30,
                    guide=[
                        "Ein Ort zum Reden, wenn es gerade schwer ist.",
                        "Behandelt einander mit Respekt. Kein Ratschlag ohne Nachfrage.",
                    ],
                ),
                ch("gute-nachrichten", "🎉", topic="Teile deine guten Nachrichten", reactions=["🎉"]),
                ch("frage-des-tages", "❓", topic="Frage des Tages"),
                ch("gestaendnisse", "🤫", topic="Anonyme Geständnisse",
                    guide=[
                        "Anonyme Geständnisse. Bleibt fair.",
                    ],
                ),
                ch("komplimente", "💐", topic="Sag jemandem etwas Nettes"),
                ch("ratschlaege", "🧭", topic="Rat von der Community"),
                ch("smalltalk", "🫧", topic="Kurz und locker"),
                ch("bot-befehle", "🤖", topic="Bot-Befehle",
                    guide=[
                        "Bot-Befehle gehören hierher, damit sie den Hauptchat nicht zumüllen.",
                    ],
                ),
            ]),
            cat("sprachen", "🌍", "public", [
                ch("deutsch", "🇩🇪", topic="Deutschsprachiger Chat — die Hauptsprache", slowmode=3),
                ch("english", "🇬🇧", topic="English speaking chat", slowmode=3),
            ]),
            cat("sprach-talks", "🗣️", "public", [
                ch("deutsch-talk", "🇩🇪", "voice"),
                ch("english-talk", "🇬🇧", "voice"),
                ch("deutsch-talk-2", "🇩🇪", "voice", user_limit=10),
                ch("english-talk-2", "🇬🇧", "voice", user_limit=10),
            ]),
            cat("sprachkanaele", "🔊", "public", [
                j2c_channel(),
                ch("treffpunkt-1", "🎙️", "voice"),
                ch("treffpunkt-2", "🎙️", "voice"),
                ch("treffpunkt-3", "🎙️", "voice"),
                ch("chill-ecke", "☕", "voice", user_limit=10),
                ch("tiefgruendig", "🌌", "voice", user_limit=6),
                ch("musik", "🎶", "voice"),
                ch("karaoke", "🎤", "voice", user_limit=12),
                ch("zu-zweit", "👥", "voice", user_limit=2),
                ch("zu-dritt", "👨‍👩‍👦", "voice", user_limit=3),
                ch("gemeinsam-lernen", "📚", "voice"),
                ch("nachtschicht", "🌙", "voice", user_limit=12),
                ch("buehne", "🎭", "stage"),
                ch("abwesend", "💤", "voice"),
            ]),
            cat("medien", "🖼️", "public", [
                ch("fotos", "📸", topic="Deine Fotos", mode="media"),
                ch("kunst", "🎨", topic="Kunst und Zeichnungen", mode="media", reactions=["⭐"]),
                ch("memes", "😂", topic="Memes", mode="media", reactions=["😂"]),
                ch("musik-tipps", "🎧", topic="Songempfehlungen"),
                ch("filme-und-serien", "🎬", topic="Filme und Serien"),
                ch("buecher", "📖", topic="Was liest du gerade?"),
                ch("haustiere", "🐾", topic="Haustiere", mode="media"),
                ch("outfits", "👗", topic="Outfit des Tages", mode="media"),
            ]),
            cat("aktivitaeten", "🎲", "public", [
                ch("spieleabend", "🕹️", topic="Spieleabende"),
                ch("watch-party", "🍿", topic="Gemeinsam schauen", mode="media"),
                ch("wettbewerbe", "🏅", topic="Community-Challenges"),
                ch("geburtstage", "🎂", topic="Geburtstage", reactions=["🎂"]),
                ch("umfragen", "📊", topic="Abstimmungen", reactions=["👍", "👎"]),
                ch("aktivitaets-talk", "🎪", "voice", user_limit=25),
            ]),
            cat("alltag", "🌤️", "public", [
                ch("essen-und-trinken", "🍕", topic="Rezepte und Restaurants"),
                ch("sport-und-fitness", "⚽", topic="Sport und Bewegung"),
                ch("reisen", "✈️", topic="Reiseziele und Tipps"),
                ch("technik", "💻", topic="Technik und Gadgets"),
                ch("schule-und-arbeit", "🎓", topic="Alltag, Studium, Job"),
            ]),
            cat("social media", "📱", "public", [
                ch("instagram", "📸", topic="Instagram-Beiträge", mode="media"),
                ch("tiktok", "🎵", topic="TikTok-Clips", mode="media"),
                ch("youtube", "▶️", topic="YouTube-Uploads", mode="media"),
                ch("twitch", "🟣", topic="Twitch-Streams", mode="media"),
                ch("x-twitter", "🐦", topic="Beiträge von X", mode="media"),
                ch("eigenwerbung", "📣", topic="Eigene Projekte vorstellen", slowmode=300,
                    guide=[
                        "Eigene Projekte vorstellen — ein Beitrag pro Person, kein Spam.",
                    ],
                ),
            ]),
            cat("vip bereich", "💎", "vip", [
                ch("vip-chat", "💬", topic="Exklusiv für VIPs und Booster"),
                ch("vip-vorteile", "🎁", topic="Deine Vorteile", visibility="readonly"),
                ch("vip-wuensche", "🌠", topic="Wünsche und Rückmeldungen"),
                ch("vip-talk", "🥂", "voice", user_limit=15),
            ]),
            cat("hilfe", "🛟", "public", [
                ch("ticket-eroeffnen", "🎫", topic="Hier ein Support-Ticket öffnen",
                   visibility="readonly", widget="ticket"),
                ch("hilfe-und-support", "❓", "forum", topic="Frag die Community"),
                ch("fehler-melden", "🐛", topic="Fehler melden", mode="threads"),
                ch("vorschlaege", "💡", topic="Ideen für den Server", mode="threads", reactions=["👍", "👎"]),
                ch("beschwerden", "📣", topic="Beschwerden über Mitglieder", mode="threads"),
                ch("entbannungsantrag", "⚖️", topic="Einspruch gegen eine Strafe", mode="threads"),
            ]),
            cat("team", "🛡️", "staff", [
                ch("team-chat", "💼", topic="Interner Teamchat"),
                ch("team-ankuendigungen", "📣", topic="Ankündigungen fürs Team", mode="announce"),
                ch("aufgaben", "📋", topic="Aufgaben und Zuständigkeiten", widget="checklist"),
                ch("bewerbungen", "🧾", topic="Eingehende Bewerbungen", mode="threads"),
                ch("meldungen", "🚨", topic="Gemeldete Vorfälle"),
                ch("schichtplan", "🗓️", topic="Wer hat wann Dienst?"),
                ch("team-talk", "🎙️", "voice", user_limit=15),
                ch("besprechungsraum", "🪑", "voice", user_limit=25),
            ]),
            cat("leitung", "👑", "leadership", [
                ch("leitungs-chat", "🏛️", topic="Nur für die Serverleitung"),
                ch("planung", "🗺️", topic="Planung und Ausrichtung"),
                ch("personal", "🧑‍💼", topic="Personalthemen"),
                ch("leitungs-talk", "🔐", "voice", user_limit=10),
            ]),
            cat("logs", "📜", "staff", [
                ch("mod-logs", "🔨", topic="Moderationsaktionen", mode="log"),
                ch("mitglieder-logs", "👥", topic="Beitritte und Austritte", mode="log"),
                ch("nachrichten-logs", "✏️", topic="Bearbeitete und gelöschte Nachrichten", mode="log"),
                ch("sprach-logs", "🔊", topic="Voice-Aktivität", mode="log"),
                ch("rollen-logs", "🏷️", topic="Rollenänderungen", mode="log"),
                ch("kanal-logs", "🗂️", topic="Kanaländerungen", mode="log"),
                ch("social-logs", "📱", topic="Social-Media-Feeds und Erwähnungen", mode="log"),
                ch("bot-logs", "🤖", topic="Bot-Ereignisse", mode="log"),
                ch("einladungs-logs", "🔗", topic="Einladungs-Tracking", mode="log"),
                ch("server-logs", "🗃️", topic="Alles Übrige", mode="log"),
            ]),
        ],
    }


def gaming() -> dict[str, Any]:
    return {
        "key": "gaming",
        "name": "Gaming Pro Hub",
        "emoji": "🎮",
        "tagline": "Squads, Turniere und ein Kanal pro Spiel",
        "premium": True,
        "accent": "#22D3EE",
        "description": (
            "Für Gaming-Communities, die mehr als einen Sprachkanal brauchen: "
            "eigene Bereiche pro Spiel, Mitspielersuche, Turnierverwaltung, "
            "Coaching und viele Squad-Räume in unterschiedlichen Größen."
        ),
        "highlights": [
            "Eigene Kanäle für 12 Spiele plus Mitspielersuche",
            "18 Sprachkanäle: zu zweit, zu dritt, Squad und Turnierräume",
            "Turnier- und Scrim-Verwaltung mit eigener Rollengruppe",
            "Clip-, Highlight- und Coaching-Bereiche",
        ],
        "roles": [
            role("gamer", "Gamer", "🎮", "#22D3EE", "member", hoist=False),
            role("competitive", "Turnierspieler", "🏆", "#F59E0B", "trusted"),
            role("coach", "Coach", "🧠", "#8B5CF6", "helper"),
            role("tournament", "Turnier Team", "🎯", "#E11D48", "helper"),
            role("caster", "Kommentator", "🎙️", "#0EA5E9", "helper"),
            role("clipper", "Clip Creator", "🎬", "#F97316", "trusted", hoist=False),
        ],
        "categories": [
            cat("willkommen", "🚪", "gate", [
                ch("willkommen", "👋", topic="Willkommen! Verifiziere dich, um den Server zu sehen.", visibility="readonly",
                    guide=[
                        "Schön, dass du da bist.",
                        "Verifiziere dich nebenan, danach siehst du den gesamten Server.",
                    ],
                ),
                ch("verifizieren", "✅", topic="Hier verifizieren", widget="verify"),
                ch("regeln", "📜", topic="Serverregeln", visibility="readonly", widget="rules"),
                ch("haeufige-fragen", "❔", topic="Häufig gestellte Fragen", visibility="readonly",
                    guide=[
                        "Die häufigsten Fragen und ihre Antworten.",
                        "Ist deine Frage nicht dabei, melde dich beim Team.",
                    ],
                ),
            ]),
            cat("information", "📌", "readonly", [
                ch("ankuendigungen", "📢", "news", topic="Wichtige Ankündigungen", mode="announce"),
                ch("neuigkeiten", "🆕", topic="Server- und Bot-Updates", mode="announce"),
                ch("rollen-vergabe", "🏷️", topic="Rollen selbst vergeben", widget="roles"),
                ch("partner", "🤝", topic="Unsere Partner",
                    guide=[
                        "Server und Projekte, mit denen wir zusammenarbeiten.",
                    ],
                ),
                ch("gewinnspiele", "🎁", topic="Aktuelle Gewinnspiele", reactions=["🎉"]),
                ch("team-vorstellung", "👥", topic="Wer gehört zum Team?",
                    guide=[
                        "Wer zum Team gehört und wofür zuständig ist.",
                    ],
                ),
                ch("patchnotes", "🩹", topic="Patchnotes der Spiele", mode="announce"),
            ]),
            cat("spiele", "🎮", "public", [
                ch("gaming-allgemein", "💬", topic="Allgemeiner Gaming-Chat"),
                ch("valorant", "🔫", topic="Valorant"),
                ch("league-of-legends", "⚔️", topic="League of Legends"),
                ch("counter-strike", "💣", topic="Counter-Strike"),
                ch("fortnite", "🏗️", topic="Fortnite"),
                ch("minecraft", "⛏️", topic="Minecraft"),
                ch("gta-rp", "🚗", topic="GTA und Rollenspiel"),
                ch("rocket-league", "🚀", topic="Rocket League"),
                ch("apex-legends", "🎯", topic="Apex Legends"),
                ch("call-of-duty", "🪖", topic="Call of Duty"),
                ch("indie-spiele", "🕹️", topic="Indie und Geheimtipps"),
                ch("klassiker", "👾", topic="Retro und Klassiker"),
            ]),
            cat("mitspieler", "🔎", "public", [
                ch("mitspieler-suche", "📣", topic="Mitspieler finden", mode="threads"),
                ch("ranked-suche", "🏅", topic="Ranked-Mitspieler"),
                ch("entspannt-zocken", "🎲", topic="Ohne Druck spielen"),
                ch("scrims", "⚔️", topic="Scrims und Übungsspiele"),
                ch("team-suche", "🧩", topic="Feste Teams finden", mode="threads"),
            ]),
            cat("turniere", "🏆", "public", [
                ch("turnier-news", "📢", "news", topic="Turnier-Ankündigungen", visibility="readonly", mode="announce"),
                ch("turnier-anmeldung", "📝", topic="Anmeldung"),
                ch("turnierbaum", "🗂️", topic="Turnierbäume"),
                ch("ergebnisse", "📊", topic="Ergebnisse", visibility="readonly", mode="announce"),
                ch("coaching", "🧠", "forum", topic="Coaching-Anfragen"),
                ch("spielanalyse", "🎞️", topic="Aufzeichnungen analysieren"),
            ]),
            cat("clips", "🎬", "public", [
                ch("highlights", "⭐", topic="Deine besten Momente", slowmode=60, mode="media", reactions=["🔥"]),
                ch("fails", "💀", topic="Weniger gute Momente", mode="media"),
                ch("setups", "🖥️", topic="Zeig dein Setup", mode="media"),
                ch("bildschirmfotos", "📸", topic="Bildschirmfotos", mode="media"),
                ch("streams", "🟣", topic="Wer streamt gerade?"),
            ]),
            cat("squad talks", "🔊", "public", [
                j2c_channel(),
                ch("lobby", "🎙️", "voice"),
                ch("zu-zweit-1", "👥", "voice", user_limit=2),
                ch("zu-zweit-2", "👥", "voice", user_limit=2),
                ch("zu-dritt-1", "👨‍👩‍👦", "voice", user_limit=3),
                ch("zu-dritt-2", "👨‍👩‍👦", "voice", user_limit=3),
                ch("squad-1", "🛡️", "voice", user_limit=5),
                ch("squad-2", "🛡️", "voice", user_limit=5),
                ch("squad-3", "🛡️", "voice", user_limit=5),
                ch("grossgruppe-1", "⚔️", "voice", user_limit=10),
                ch("grossgruppe-2", "⚔️", "voice", user_limit=10),
                ch("scrim-a", "🅰️", "voice", user_limit=6),
                ch("scrim-b", "🅱️", "voice", user_limit=6),
                ch("turnier-1", "🏆", "voice", user_limit=12),
                ch("turnier-2", "🏆", "voice", user_limit=12),
                ch("kommentar-buehne", "🎙️", "stage"),
                ch("chill-ecke", "☕", "voice", user_limit=10),
                ch("musik", "🎶", "voice"),
                ch("abwesend", "💤", "voice"),
            ]),
            cat("sprachen", "🌍", "public", [
                ch("deutsch", "🇩🇪", topic="Deutschsprachiger Chat — die Hauptsprache", slowmode=3),
                ch("english", "🇬🇧", topic="English speaking chat", slowmode=3),
            ]),
            cat("sprach-talks", "🗣️", "public", [
                ch("deutsch-talk", "🇩🇪", "voice"),
                ch("english-talk", "🇬🇧", "voice"),
                ch("deutsch-talk-2", "🇩🇪", "voice", user_limit=10),
                ch("english-talk-2", "🇬🇧", "voice", user_limit=10),
            ]),
            cat("social media", "📱", "public", [
                ch("instagram", "📸", topic="Instagram-Beiträge", mode="media"),
                ch("tiktok", "🎵", topic="TikTok-Clips", mode="media"),
                ch("youtube", "▶️", topic="YouTube-Uploads", mode="media"),
                ch("twitch", "🟣", topic="Twitch-Streams", mode="media"),
                ch("x-twitter", "🐦", topic="Beiträge von X", mode="media"),
                ch("eigenwerbung", "📣", topic="Eigene Projekte vorstellen", slowmode=300,
                    guide=[
                        "Eigene Projekte vorstellen — ein Beitrag pro Person, kein Spam.",
                    ],
                ),
            ]),
            cat("vip bereich", "💎", "vip", [
                ch("vip-chat", "💬", topic="Exklusiv für VIPs und Booster"),
                ch("vip-vorteile", "🎁", topic="Deine Vorteile", visibility="readonly"),
                ch("vip-wuensche", "🌠", topic="Wünsche und Rückmeldungen"),
                ch("vip-talk", "🥂", "voice", user_limit=15),
            ]),
            cat("hilfe", "🛟", "public", [
                ch("ticket-eroeffnen", "🎫", topic="Hier ein Support-Ticket öffnen",
                   visibility="readonly", widget="ticket"),
                ch("support", "❓", "forum", topic="Hilfe vom Team"),
                ch("technik-hilfe", "🛠️", topic="Technische Probleme"),
                ch("fehler-melden", "🐛", topic="Fehler melden", mode="threads"),
                ch("vorschlaege", "💡", topic="Vorschläge", mode="threads", reactions=["👍", "👎"]),
            ]),
            cat("team", "🛡️", "staff", [
                ch("team-chat", "💼", topic="Interner Teamchat"),
                ch("team-ankuendigungen", "📣", topic="Ankündigungen fürs Team", mode="announce"),
                ch("aufgaben", "📋", topic="Aufgaben und Zuständigkeiten", widget="checklist"),
                ch("bewerbungen", "🧾", topic="Eingehende Bewerbungen", mode="threads"),
                ch("meldungen", "🚨", topic="Gemeldete Vorfälle"),
                ch("schichtplan", "🗓️", topic="Wer hat wann Dienst?"),
                ch("team-talk", "🎙️", "voice", user_limit=15),
                ch("besprechungsraum", "🪑", "voice", user_limit=25),
            ]),
            cat("leitung", "👑", "leadership", [
                ch("leitungs-chat", "🏛️", topic="Nur für die Serverleitung"),
                ch("planung", "🗺️", topic="Planung und Ausrichtung"),
                ch("personal", "🧑‍💼", topic="Personalthemen"),
                ch("leitungs-talk", "🔐", "voice", user_limit=10),
            ]),
            cat("logs", "📜", "staff", [
                ch("mod-logs", "🔨", topic="Moderationsaktionen", mode="log"),
                ch("mitglieder-logs", "👥", topic="Beitritte und Austritte", mode="log"),
                ch("nachrichten-logs", "✏️", topic="Bearbeitete und gelöschte Nachrichten", mode="log"),
                ch("sprach-logs", "🔊", topic="Voice-Aktivität", mode="log"),
                ch("rollen-logs", "🏷️", topic="Rollenänderungen", mode="log"),
                ch("kanal-logs", "🗂️", topic="Kanaländerungen", mode="log"),
                ch("social-logs", "📱", topic="Social-Media-Feeds und Erwähnungen", mode="log"),
                ch("bot-logs", "🤖", topic="Bot-Ereignisse", mode="log"),
                ch("einladungs-logs", "🔗", topic="Einladungs-Tracking", mode="log"),
                ch("server-logs", "🗃️", topic="Alles Übrige", mode="log"),
            ]),
        ],
    }


def anime() -> dict[str, Any]:
    return {
        "key": "anime",
        "name": "Anime & Manga Hub",
        "emoji": "🌸",
        "tagline": "Seasonals, Manga, Fanart und Watch-Partys",
        "premium": True,
        "accent": "#F472B6",
        "description": (
            "Ein Zuhause für Anime-Communities: getrennte Bereiche für laufende "
            "Seasonals, Manga, Fanart und Cosplay, klar markierte Spoiler-Kanäle "
            "und Watch-Party-Räume mit Bühne."
        ),
        "highlights": [
            "Getrennte Spoiler-Kanäle pro Bereich",
            "Seasonal-, Manga-, Fanart- und Cosplay-Zonen",
            "Watch-Party-Räume mit Bühne für Events",
            "Bereich für japanische Sprache und Kultur",
        ],
        "roles": [
            role("otaku", "Otaku", "🌸", "#F472B6", "member", hoist=False),
            role("manga_reader", "Manga Leser", "📚", "#A78BFA", "trusted", hoist=False),
            role("fanartist", "Fan Kuenstler", "🖌️", "#FB7185", "trusted"),
            role("cosplayer", "Cosplayer", "🎀", "#F0ABFC", "trusted"),
            role("watch_host", "Watch Party Host", "🍿", "#F59E0B", "helper"),
        ],
        "categories": [
            cat("willkommen", "🚪", "gate", [
                ch("willkommen", "👋", topic="Willkommen! Verifiziere dich, um den Server zu sehen.", visibility="readonly",
                    guide=[
                        "Schön, dass du da bist.",
                        "Verifiziere dich nebenan, danach siehst du den gesamten Server.",
                    ],
                ),
                ch("verifizieren", "✅", topic="Hier verifizieren", widget="verify"),
                ch("regeln", "📜", topic="Serverregeln", visibility="readonly", widget="rules"),
                ch("haeufige-fragen", "❔", topic="Häufig gestellte Fragen", visibility="readonly",
                    guide=[
                        "Die häufigsten Fragen und ihre Antworten.",
                        "Ist deine Frage nicht dabei, melde dich beim Team.",
                    ],
                ),
            ]),
            cat("information", "📌", "readonly", [
                ch("ankuendigungen", "📢", "news", topic="Wichtige Ankündigungen", mode="announce"),
                ch("neuigkeiten", "🆕", topic="Server- und Bot-Updates", mode="announce"),
                ch("rollen-vergabe", "🏷️", topic="Rollen selbst vergeben", widget="roles"),
                ch("partner", "🤝", topic="Unsere Partner",
                    guide=[
                        "Server und Projekte, mit denen wir zusammenarbeiten.",
                    ],
                ),
                ch("gewinnspiele", "🎁", topic="Aktuelle Gewinnspiele", reactions=["🎉"]),
                ch("team-vorstellung", "👥", topic="Wer gehört zum Team?",
                    guide=[
                        "Wer zum Team gehört und wofür zuständig ist.",
                    ],
                ),
                ch("season-uebersicht", "📅", topic="Die aktuelle Season"),
            ]),
            cat("anime", "📺", "public", [
                ch("anime-allgemein", "💬", topic="Allgemeiner Anime-Chat"),
                ch("aktuell-geschaut", "👀", topic="Was schaust du gerade?"),
                ch("season-anime", "🌱", topic="Die laufende Season"),
                ch("empfehlungen", "⭐", topic="Empfehlungen"),
                ch("spoiler", "🚨", topic="Achtung: Spoiler erlaubt"),
                ch("bewertungen", "📝", topic="Deine Bewertungen"),
                ch("anime-news", "📰", "news", topic="Anime-Neuigkeiten", visibility="readonly", mode="announce"),
            ]),
            cat("manga", "📚", "public", [
                ch("manga-allgemein", "💬", topic="Manga-Chat"),
                ch("neue-kapitel", "🆕", topic="Neue Kapitel"),
                ch("manga-spoiler", "🚨", topic="Spoiler erlaubt"),
                ch("light-novels", "📖", topic="Light Novels"),
                ch("webtoons", "📱", topic="Webtoons und Manhwa"),
            ]),
            cat("kreativ", "🎨", "public", [
                ch("fanart", "🖌️", topic="Eigene Fanart", slowmode=120, mode="media", reactions=["⭐"]),
                ch("kunst-hilfe", "💡", topic="Rückmeldungen und Tipps"),
                ch("cosplay", "🎀", topic="Cosplay zeigen", mode="media"),
                ch("edits", "✂️", topic="Edits und Musikvideos", mode="media"),
                ch("fanfiction", "✍️", topic="Eigene Geschichten"),
                ch("auftraege", "💰", topic="Auftragsarbeiten", slowmode=600),
            ]),
            cat("watch party", "🍿", "public", [
                ch("watch-planung", "📅", topic="Nächste Watch-Party planen"),
                ch("watch-chat", "💬", topic="Live-Chat zur Party"),
                ch("watch-raum-1", "🎬", "voice", user_limit=25),
                ch("watch-raum-2", "🎬", "voice", user_limit=25),
                ch("watch-buehne", "🎤", "stage"),
            ]),
            cat("japan", "🗾", "public", [
                ch("japanisch-lernen", "🇯🇵", topic="Japanisch lernen"),
                ch("kultur", "⛩️", topic="Kultur und Reisen"),
                ch("kueche", "🍜", topic="Japanische Küche"),
                ch("musik", "🎵", topic="J-Pop, Openings und Soundtracks"),
            ]),
            cat("spiele", "🎮", "public", [
                ch("gacha", "🎰", topic="Gacha-Spiele"),
                ch("rollenspiele", "🗡️", topic="JRPGs"),
                ch("rhythmus-spiele", "🎵", topic="Rhythmusspiele"),
                ch("visual-novels", "📗", topic="Visual Novels"),
                ch("gaming-talk", "🕹️", "voice", user_limit=10),
            ]),
            cat("sprachkanaele", "🔊", "public", [
                j2c_channel(),
                ch("allgemeiner-talk", "🎙️", "voice"),
                ch("chill-ecke", "☕", "voice", user_limit=10),
                ch("musik", "🎶", "voice"),
                ch("zu-zweit", "👥", "voice", user_limit=2),
                ch("zu-dritt", "👨‍👩‍👦", "voice", user_limit=3),
                ch("gruppe", "🛡️", "voice", user_limit=5),
                ch("lernen", "📚", "voice"),
                ch("stream-raum", "📺", "voice", user_limit=20),
                ch("nachtschicht", "🌙", "voice", user_limit=12),
                ch("abwesend", "💤", "voice"),
            ]),
            cat("sprachen", "🌍", "public", [
                ch("deutsch", "🇩🇪", topic="Deutschsprachiger Chat — die Hauptsprache", slowmode=3),
                ch("english", "🇬🇧", topic="English speaking chat", slowmode=3),
            ]),
            cat("sprach-talks", "🗣️", "public", [
                ch("deutsch-talk", "🇩🇪", "voice"),
                ch("english-talk", "🇬🇧", "voice"),
                ch("deutsch-talk-2", "🇩🇪", "voice", user_limit=10),
                ch("english-talk-2", "🇬🇧", "voice", user_limit=10),
            ]),
            cat("social media", "📱", "public", [
                ch("instagram", "📸", topic="Instagram-Beiträge", mode="media"),
                ch("tiktok", "🎵", topic="TikTok-Clips", mode="media"),
                ch("youtube", "▶️", topic="YouTube-Uploads", mode="media"),
                ch("twitch", "🟣", topic="Twitch-Streams", mode="media"),
                ch("x-twitter", "🐦", topic="Beiträge von X", mode="media"),
                ch("eigenwerbung", "📣", topic="Eigene Projekte vorstellen", slowmode=300,
                    guide=[
                        "Eigene Projekte vorstellen — ein Beitrag pro Person, kein Spam.",
                    ],
                ),
            ]),
            cat("vip bereich", "💎", "vip", [
                ch("vip-chat", "💬", topic="Exklusiv für VIPs und Booster"),
                ch("vip-vorteile", "🎁", topic="Deine Vorteile", visibility="readonly"),
                ch("vip-wuensche", "🌠", topic="Wünsche und Rückmeldungen"),
                ch("vip-talk", "🥂", "voice", user_limit=15),
            ]),
            cat("hilfe", "🛟", "public", [
                ch("ticket-eroeffnen", "🎫", topic="Hier ein Support-Ticket öffnen",
                   visibility="readonly", widget="ticket"),
                ch("hilfe-und-support", "❓", "forum", topic="Frag die Community"),
                ch("fehler-melden", "🐛", topic="Fehler melden", mode="threads"),
                ch("vorschlaege", "💡", topic="Ideen für den Server", mode="threads", reactions=["👍", "👎"]),
                ch("beschwerden", "📣", topic="Beschwerden über Mitglieder", mode="threads"),
                ch("entbannungsantrag", "⚖️", topic="Einspruch gegen eine Strafe", mode="threads"),
            ]),
            cat("team", "🛡️", "staff", [
                ch("team-chat", "💼", topic="Interner Teamchat"),
                ch("team-ankuendigungen", "📣", topic="Ankündigungen fürs Team", mode="announce"),
                ch("aufgaben", "📋", topic="Aufgaben und Zuständigkeiten", widget="checklist"),
                ch("bewerbungen", "🧾", topic="Eingehende Bewerbungen", mode="threads"),
                ch("meldungen", "🚨", topic="Gemeldete Vorfälle"),
                ch("schichtplan", "🗓️", topic="Wer hat wann Dienst?"),
                ch("team-talk", "🎙️", "voice", user_limit=15),
                ch("besprechungsraum", "🪑", "voice", user_limit=25),
            ]),
            cat("leitung", "👑", "leadership", [
                ch("leitungs-chat", "🏛️", topic="Nur für die Serverleitung"),
                ch("planung", "🗺️", topic="Planung und Ausrichtung"),
                ch("personal", "🧑‍💼", topic="Personalthemen"),
                ch("leitungs-talk", "🔐", "voice", user_limit=10),
            ]),
            cat("logs", "📜", "staff", [
                ch("mod-logs", "🔨", topic="Moderationsaktionen", mode="log"),
                ch("mitglieder-logs", "👥", topic="Beitritte und Austritte", mode="log"),
                ch("nachrichten-logs", "✏️", topic="Bearbeitete und gelöschte Nachrichten", mode="log"),
                ch("sprach-logs", "🔊", topic="Voice-Aktivität", mode="log"),
                ch("rollen-logs", "🏷️", topic="Rollenänderungen", mode="log"),
                ch("kanal-logs", "🗂️", topic="Kanaländerungen", mode="log"),
                ch("social-logs", "📱", topic="Social-Media-Feeds und Erwähnungen", mode="log"),
                ch("bot-logs", "🤖", topic="Bot-Ereignisse", mode="log"),
                ch("einladungs-logs", "🔗", topic="Einladungs-Tracking", mode="log"),
                ch("server-logs", "🗃️", topic="Alles Übrige", mode="log"),
            ]),
        ],
    }


def business() -> dict[str, Any]:
    return {
        "key": "business",
        "name": "Business & Company",
        "emoji": "🏢",
        "tagline": "Abteilungen, Projekte und Kunden sauber getrennt",
        "premium": True,
        "accent": "#0F766E",
        "description": (
            "Ein Discord als Arbeitsplatz: getrennte Abteilungen, Projekträume, "
            "ein abgeschirmter Kundenbereich und Besprechungsräume. Die Rechte "
            "sind so gesetzt, dass interne Themen intern bleiben."
        ),
        "highlights": [
            "Abteilungen für Entwicklung, Design, Marketing, Vertrieb und Personal",
            "Kundenbereich getrennt vom internen Bereich",
            "Besprechungsräume, tägliche Abstimmung und Fokus-Räume",
            "Vollständige Logs für Nachvollziehbarkeit",
        ],
        "roles": [
            role("employee", "Mitarbeiter", "💼", "#0F766E", "member"),
            role("client", "Kunde", "🤝", "#059669", "guest"),
            role("freelancer", "Freiberufler", "🧑‍💻", "#14B8A6", "member", hoist=False),
            role("project_lead", "Projektleitung", "📊", "#0369A1", "helper"),
            role("dept_lead", "Abteilungsleitung", "👔", "#1D4ED8", "moderator"),
            role("hr", "Personalwesen", "🧑‍💼", "#7C3AED", "moderator"),
            role("management", "Geschaeftsleitung", "🏛️", "#DC2626", "admin"),
        ],
        "categories": [
            cat("willkommen", "🚪", "gate", [
                ch("willkommen", "👋", topic="Willkommen! Verifiziere dich, um den Server zu sehen.", visibility="readonly",
                    guide=[
                        "Schön, dass du da bist.",
                        "Verifiziere dich nebenan, danach siehst du den gesamten Server.",
                    ],
                ),
                ch("verifizieren", "✅", topic="Hier verifizieren", widget="verify"),
                ch("regeln", "📜", topic="Serverregeln", visibility="readonly", widget="rules"),
                ch("haeufige-fragen", "❔", topic="Häufig gestellte Fragen", visibility="readonly",
                    guide=[
                        "Die häufigsten Fragen und ihre Antworten.",
                        "Ist deine Frage nicht dabei, melde dich beim Team.",
                    ],
                ),
            ]),
            cat("information", "📌", "readonly", [
                ch("ankuendigungen", "📢", "news", topic="Wichtige Ankündigungen", mode="announce"),
                ch("neuigkeiten", "🆕", topic="Server- und Bot-Updates", mode="announce"),
                ch("rollen-vergabe", "🏷️", topic="Rollen selbst vergeben", widget="roles"),
                ch("partner", "🤝", topic="Unsere Partner",
                    guide=[
                        "Server und Projekte, mit denen wir zusammenarbeiten.",
                    ],
                ),
                ch("gewinnspiele", "🎁", topic="Aktuelle Gewinnspiele", reactions=["🎉"]),
                ch("team-vorstellung", "👥", topic="Wer gehört zum Team?",
                    guide=[
                        "Wer zum Team gehört und wofür zuständig ist.",
                    ],
                ),
                ch("unternehmens-news", "🏢", topic="Unternehmensnachrichten", mode="announce"),
            ]),
            cat("allgemein", "💬", "public", [
                ch("allgemein", "💭", topic="Allgemeiner Austausch",
                    guide=[
                        "Der Hauptchat für alles, was keinen eigenen Kanal hat.",
                    ],
                ),
                ch("kaffeekueche", "🎲", topic="Lockerer Austausch"),
                ch("erfolge", "🎉", topic="Erfolge feiern", reactions=["🎉"]),
                ch("kurze-fragen", "❓", topic="Kurze Fragen"),
                ch("bot-befehle", "🤖", topic="Bot-Befehle",
                    guide=[
                        "Bot-Befehle gehören hierher, damit sie den Hauptchat nicht zumüllen.",
                    ],
                ),
            ]),
            cat("abteilungen", "🏗️", "member", [
                ch("entwicklung", "💻", topic="Entwicklung"),
                ch("gestaltung", "🎨", topic="Design und Nutzererlebnis"),
                ch("marketing", "📣", topic="Marketing"),
                ch("vertrieb", "💰", topic="Vertrieb"),
                ch("kundenbetreuung", "🛟", topic="Kundensupport intern"),
                ch("finanzen", "📈", topic="Finanzen"),
                ch("personal", "🧑‍💼", topic="Personalwesen"),
                ch("recht", "⚖️", topic="Recht und Richtlinien"),
            ]),
            cat("projekte", "📊", "member", [
                ch("projekt-uebersicht", "🗂️", topic="Übersicht aller Projekte", visibility="readonly"),
                ch("projekt-alpha", "🅰️", topic="Projekt Alpha"),
                ch("projekt-beta", "🅱️", topic="Projekt Beta"),
                ch("projekt-gamma", "🇬", topic="Projekt Gamma"),
                ch("aufgabenspeicher", "📋", "forum", topic="Aufgaben und Ideen"),
                ch("veroeffentlichungen", "🚀", topic="Release-Ankündigungen", visibility="readonly", mode="announce"),
            ]),
            cat("kunden", "🤝", "public", [
                ch("kunden-willkommen", "👋", topic="Willkommen, Kunden", visibility="readonly"),
                ch("kunden-anfragen", "📥", "forum", topic="Anfragen einreichen"),
                ch("kunden-updates", "📢", topic="Statusmeldungen", visibility="readonly", mode="announce"),
                ch("kunden-rueckmeldung", "💬", topic="Rückmeldungen"),
                ch("kunden-gespraech", "📞", "voice", user_limit=10),
            ]),
            cat("besprechungen", "🗓️", "member", [
                j2c_channel(),
                ch("protokolle", "📝", topic="Besprechungsprotokolle"),
                ch("tagesordnung", "📌", topic="Tagesordnung"),
                ch("tages-abstimmung", "☀️", "voice", user_limit=20),
                ch("besprechung-1", "🪑", "voice", user_limit=15),
                ch("besprechung-2", "🪑", "voice", user_limit=15),
                ch("fokus-1", "🎧", "voice", user_limit=1),
                ch("fokus-2", "🎧", "voice", user_limit=1),
                ch("vollversammlung", "🏛️", "stage"),
                ch("pausenraum", "☕", "voice"),
            ]),
            cat("wissen", "📚", "member", [
                ch("handbuch", "📖", topic="Das Unternehmenshandbuch", visibility="readonly"),
                ch("einarbeitung", "🚀", topic="Einstieg für Neue"),
                ch("vorlagen", "🗂️", topic="Vorlagen und Materialien"),
                ch("werkzeuge", "🛠️", topic="Werkzeuge und Zugänge"),
                ch("archiv", "🗄️", topic="Abgeschlossenes", visibility="archive"),
            ]),
            cat("sprachen", "🌍", "public", [
                ch("deutsch", "🇩🇪", topic="Deutschsprachiger Chat — die Hauptsprache", slowmode=3),
                ch("english", "🇬🇧", topic="English speaking chat", slowmode=3),
            ]),
            cat("sprach-talks", "🗣️", "public", [
                ch("deutsch-talk", "🇩🇪", "voice"),
                ch("english-talk", "🇬🇧", "voice"),
            ]),
            cat("interne leitung", "🛡️", "staff", [
                ch("team-chat", "💼", topic="Interner Teamchat"),
                ch("team-ankuendigungen", "📣", topic="Ankündigungen fürs Team", mode="announce"),
                ch("aufgaben", "📋", topic="Aufgaben und Zuständigkeiten", widget="checklist"),
                ch("bewerbungen", "🧾", topic="Eingehende Bewerbungen", mode="threads"),
                ch("meldungen", "🚨", topic="Gemeldete Vorfälle"),
                ch("schichtplan", "🗓️", topic="Wer hat wann Dienst?"),
                ch("team-talk", "🎙️", "voice", user_limit=15),
                ch("besprechungsraum", "🪑", "voice", user_limit=25),
            ]),
            cat("leitung", "👑", "leadership", [
                ch("leitungs-chat", "🏛️", topic="Nur für die Serverleitung"),
                ch("planung", "🗺️", topic="Planung und Ausrichtung"),
                ch("personal", "🧑‍💼", topic="Personalthemen"),
                ch("leitungs-talk", "🔐", "voice", user_limit=10),
            ]),
            cat("logs", "📜", "staff", [
                ch("mod-logs", "🔨", topic="Moderationsaktionen", mode="log"),
                ch("mitglieder-logs", "👥", topic="Beitritte und Austritte", mode="log"),
                ch("nachrichten-logs", "✏️", topic="Bearbeitete und gelöschte Nachrichten", mode="log"),
                ch("sprach-logs", "🔊", topic="Voice-Aktivität", mode="log"),
                ch("rollen-logs", "🏷️", topic="Rollenänderungen", mode="log"),
                ch("kanal-logs", "🗂️", topic="Kanaländerungen", mode="log"),
                ch("social-logs", "📱", topic="Social-Media-Feeds und Erwähnungen", mode="log"),
                ch("bot-logs", "🤖", topic="Bot-Ereignisse", mode="log"),
                ch("einladungs-logs", "🔗", topic="Einladungs-Tracking", mode="log"),
                ch("server-logs", "🗃️", topic="Alles Übrige", mode="log"),
            ]),
        ],
    }


def study() -> dict[str, Any]:
    return {
        "key": "study",
        "name": "Study & University",
        "emoji": "🎓",
        "tagline": "Fächer, Lerngruppen und stille Arbeitsräume",
        "premium": True,
        "accent": "#0284C7",
        "description": (
            "Für Lerngruppen, Fachschaften und Uni-Communities: ein Kanal pro "
            "Fach, Lerngruppen, Prüfungsvorbereitung, ein Materialarchiv und "
            "stille Arbeitsräume, in denen wirklich gearbeitet wird."
        ),
        "highlights": [
            "Eigene Kanäle für 10 Fachbereiche",
            "Stille Lernräume mit Pomodoro-Kanälen",
            "Prüfungs-, Hausarbeits- und Abgabe-Bereiche",
            "Tutor-Rollen mit eigenem Sprechstundenraum",
        ],
        "roles": [
            role("student", "Student", "🎓", "#0284C7", "member", hoist=False),
            role("freshman", "Ersti", "🐣", "#38BDF8", "member", hoist=False),
            role("tutor", "Tutor", "🧑‍🏫", "#16A34A", "helper"),
            role("lecturer", "Lehrkraft", "🏫", "#2563EB", "moderator"),
            role("study_lead", "Studienleitung", "📚", "#7C3AED", "admin"),
            role("alumni", "Ehemalige", "🎖️", "#A16207", "trusted", hoist=False),
        ],
        "categories": [
            cat("willkommen", "🚪", "gate", [
                ch("willkommen", "👋", topic="Willkommen! Verifiziere dich, um den Server zu sehen.", visibility="readonly",
                    guide=[
                        "Schön, dass du da bist.",
                        "Verifiziere dich nebenan, danach siehst du den gesamten Server.",
                    ],
                ),
                ch("verifizieren", "✅", topic="Hier verifizieren", widget="verify"),
                ch("regeln", "📜", topic="Serverregeln", visibility="readonly", widget="rules"),
                ch("haeufige-fragen", "❔", topic="Häufig gestellte Fragen", visibility="readonly",
                    guide=[
                        "Die häufigsten Fragen und ihre Antworten.",
                        "Ist deine Frage nicht dabei, melde dich beim Team.",
                    ],
                ),
            ]),
            cat("information", "📌", "readonly", [
                ch("ankuendigungen", "📢", "news", topic="Wichtige Ankündigungen", mode="announce"),
                ch("neuigkeiten", "🆕", topic="Server- und Bot-Updates", mode="announce"),
                ch("rollen-vergabe", "🏷️", topic="Rollen selbst vergeben", widget="roles"),
                ch("partner", "🤝", topic="Unsere Partner",
                    guide=[
                        "Server und Projekte, mit denen wir zusammenarbeiten.",
                    ],
                ),
                ch("gewinnspiele", "🎁", topic="Aktuelle Gewinnspiele", reactions=["🎉"]),
                ch("team-vorstellung", "👥", topic="Wer gehört zum Team?",
                    guide=[
                        "Wer zum Team gehört und wofür zuständig ist.",
                    ],
                ),
                ch("semesterplan", "📅", topic="Termine und Fristen"),
            ]),
            cat("campus", "🏫", "public", [
                ch("allgemein", "💬", topic="Allgemeiner Campus-Chat",
                    guide=[
                        "Der Hauptchat für alles, was keinen eigenen Kanal hat.",
                    ],
                ),
                ch("vorstellungen", "🙋", topic="Stell dich vor"),
                ch("kurze-fragen", "❓", topic="Kurze Fragen"),
                ch("motivation", "🔥", topic="Motivation und Erfolge"),
                ch("memes", "😂", topic="Uni-Memes", mode="media", reactions=["😂"]),
                ch("bot-befehle", "🤖", topic="Bot-Befehle",
                    guide=[
                        "Bot-Befehle gehören hierher, damit sie den Hauptchat nicht zumüllen.",
                    ],
                ),
            ]),
            cat("faecher", "📗", "public", [
                ch("mathematik", "➗", topic="Mathematik"),
                ch("informatik", "💻", topic="Informatik"),
                ch("physik", "⚛️", topic="Physik"),
                ch("chemie", "🧪", topic="Chemie"),
                ch("biologie", "🧬", topic="Biologie"),
                ch("wirtschaft", "📈", topic="Wirtschaftswissenschaften"),
                ch("jura", "⚖️", topic="Rechtswissenschaften"),
                ch("medizin", "🩺", topic="Medizin"),
                ch("sprachen", "🗣️", topic="Sprachwissenschaften"),
                ch("geisteswissenschaften", "🏛️", topic="Geisteswissenschaften"),
            ]),
            cat("lerngruppen", "👥", "public", [
                ch("gruppensuche", "🔎", topic="Lerngruppe finden", mode="threads"),
                ch("gruppe-1", "1️⃣", topic="Lerngruppe 1"),
                ch("gruppe-2", "2️⃣", topic="Lerngruppe 2"),
                ch("gruppe-3", "3️⃣", topic="Lerngruppe 3"),
                ch("gruppe-4", "4️⃣", topic="Lerngruppe 4"),
                ch("projektarbeit", "🧩", "forum", topic="Gruppenprojekte"),
            ]),
            cat("pruefungen", "📝", "public", [
                ch("pruefungstermine", "📅", topic="Termine", visibility="readonly"),
                ch("altklausuren", "🗂️", topic="Altklausuren und Übungen",
                    guide=[
                        "Altklausuren und Übungsblätter.",
                        "Bitte nur teilen, was weitergegeben werden darf.",
                    ],
                ),
                ch("lernplaene", "🗺️", topic="Lernpläne teilen"),
                ch("hausarbeiten", "📄", topic="Hausarbeiten und Abgaben"),
                ch("panikraum", "😰", topic="Für den Tag vor der Prüfung",
                    guide=[
                        "Für den Tag vor der Prüfung. Ihr schafft das.",
                    ],
                ),
            ]),
            cat("lernraeume", "🔇", "public", [
                j2c_channel(),
                ch("stillarbeit-1", "🤫", "voice"),
                ch("stillarbeit-2", "🤫", "voice"),
                ch("pomodoro-25", "🍅", "voice"),
                ch("pomodoro-50", "🍅", "voice"),
                ch("lerngruppe-1", "👥", "voice", user_limit=6),
                ch("lerngruppe-2", "👥", "voice", user_limit=6),
                ch("sprechstunde", "🧑‍🏫", "voice", user_limit=8),
                ch("praesentation", "📊", "stage"),
                ch("pause", "☕", "voice"),
                ch("abwesend", "💤", "voice"),
            ]),
            cat("materialien", "📚", "public", [
                ch("skripte", "📑", topic="Skripte und Folien"),
                ch("buecher", "📖", topic="Literaturempfehlungen"),
                ch("werkzeuge", "🛠️", topic="Nützliche Werkzeuge"),
                ch("stipendien", "💰", topic="Förderung und Stipendien"),
                ch("stellenangebote", "💼", topic="Werkstudentenstellen"),
                ch("archiv", "🗄️", topic="Vergangene Semester", visibility="archive"),
            ]),
            cat("campusleben", "🎉", "public", [
                ch("veranstaltungen", "📅", topic="Partys und Veranstaltungen"),
                ch("hochschulsport", "⚽", topic="Hochschulsport"),
                ch("wohnen", "🏠", topic="WG- und Zimmersuche"),
                ch("mensa", "🍽️", topic="Essen auf dem Campus"),
                ch("freizeit-talk", "🎪", "voice", user_limit=20),
            ]),
            cat("sprachen", "🌍", "public", [
                ch("deutsch", "🇩🇪", topic="Deutschsprachiger Chat — die Hauptsprache", slowmode=3),
                ch("english", "🇬🇧", topic="English speaking chat", slowmode=3),
            ]),
            cat("sprach-talks", "🗣️", "public", [
                ch("deutsch-talk", "🇩🇪", "voice"),
                ch("english-talk", "🇬🇧", "voice"),
                ch("deutsch-talk-2", "🇩🇪", "voice", user_limit=10),
                ch("english-talk-2", "🇬🇧", "voice", user_limit=10),
            ]),
            cat("vip bereich", "💎", "vip", [
                ch("vip-chat", "💬", topic="Exklusiv für VIPs und Booster"),
                ch("vip-vorteile", "🎁", topic="Deine Vorteile", visibility="readonly"),
                ch("vip-wuensche", "🌠", topic="Wünsche und Rückmeldungen"),
                ch("vip-talk", "🥂", "voice", user_limit=15),
            ]),
            cat("hilfe", "🛟", "public", [
                ch("ticket-eroeffnen", "🎫", topic="Hier ein Support-Ticket öffnen",
                   visibility="readonly", widget="ticket"),
                ch("hilfe-und-support", "❓", "forum", topic="Frag die Community"),
                ch("fehler-melden", "🐛", topic="Fehler melden", mode="threads"),
                ch("vorschlaege", "💡", topic="Ideen für den Server", mode="threads", reactions=["👍", "👎"]),
                ch("beschwerden", "📣", topic="Beschwerden über Mitglieder", mode="threads"),
                ch("entbannungsantrag", "⚖️", topic="Einspruch gegen eine Strafe", mode="threads"),
            ]),
            cat("team", "🛡️", "staff", [
                ch("team-chat", "💼", topic="Interner Teamchat"),
                ch("team-ankuendigungen", "📣", topic="Ankündigungen fürs Team", mode="announce"),
                ch("aufgaben", "📋", topic="Aufgaben und Zuständigkeiten", widget="checklist"),
                ch("bewerbungen", "🧾", topic="Eingehende Bewerbungen", mode="threads"),
                ch("meldungen", "🚨", topic="Gemeldete Vorfälle"),
                ch("schichtplan", "🗓️", topic="Wer hat wann Dienst?"),
                ch("team-talk", "🎙️", "voice", user_limit=15),
                ch("besprechungsraum", "🪑", "voice", user_limit=25),
            ]),
            cat("leitung", "👑", "leadership", [
                ch("leitungs-chat", "🏛️", topic="Nur für die Serverleitung"),
                ch("planung", "🗺️", topic="Planung und Ausrichtung"),
                ch("personal", "🧑‍💼", topic="Personalthemen"),
                ch("leitungs-talk", "🔐", "voice", user_limit=10),
            ]),
            cat("logs", "📜", "staff", [
                ch("mod-logs", "🔨", topic="Moderationsaktionen", mode="log"),
                ch("mitglieder-logs", "👥", topic="Beitritte und Austritte", mode="log"),
                ch("nachrichten-logs", "✏️", topic="Bearbeitete und gelöschte Nachrichten", mode="log"),
                ch("sprach-logs", "🔊", topic="Voice-Aktivität", mode="log"),
                ch("rollen-logs", "🏷️", topic="Rollenänderungen", mode="log"),
                ch("kanal-logs", "🗂️", topic="Kanaländerungen", mode="log"),
                ch("social-logs", "📱", topic="Social-Media-Feeds und Erwähnungen", mode="log"),
                ch("bot-logs", "🤖", topic="Bot-Ereignisse", mode="log"),
                ch("einladungs-logs", "🔗", topic="Einladungs-Tracking", mode="log"),
                ch("server-logs", "🗃️", topic="Alles Übrige", mode="log"),
            ]),
        ],
    }


def creator() -> dict[str, Any]:
    return {
        "key": "creator",
        "name": "Creator Studio",
        "emoji": "🎬",
        "tagline": "Inhalte planen, produzieren und vermarkten",
        "premium": True,
        "accent": "#F97316",
        "description": (
            "Für Content Creator und ihre Communities: getrennte Bereiche für "
            "Planung, Produktion, Rückmeldungen und Kooperationen, dazu ein "
            "abgeschirmter Geschäftsbereich für Verträge und Rechnungen."
        ),
        "highlights": [
            "Produktionsablauf von der Idee bis zum Upload",
            "Rückmelde-Kanäle mit Slowmode für Qualität",
            "Kooperationsbereich, nur für Creator sichtbar",
            "Aufnahmeräume getrennt nach Format",
        ],
        "roles": [
            role("creator_pro", "Creator", "🎬", "#F97316", "trusted"),
            role("editor", "Cutter", "✂️", "#EA580C", "trusted"),
            role("thumbnail", "Thumbnail Designer", "🖼️", "#FB923C", "trusted", hoist=False),
            role("collab", "Kooperations Team", "🤝", "#DB2777", "helper"),
            role("sponsor", "Sponsor", "💰", "#CA8A04", "guest", hoist=False),
            role("moderator_chat", "Chat Moderator", "💬", "#3B82F6", "moderator"),
        ],
        "categories": [
            cat("willkommen", "🚪", "gate", [
                ch("willkommen", "👋", topic="Willkommen! Verifiziere dich, um den Server zu sehen.", visibility="readonly",
                    guide=[
                        "Schön, dass du da bist.",
                        "Verifiziere dich nebenan, danach siehst du den gesamten Server.",
                    ],
                ),
                ch("verifizieren", "✅", topic="Hier verifizieren", widget="verify"),
                ch("regeln", "📜", topic="Serverregeln", visibility="readonly", widget="rules"),
                ch("haeufige-fragen", "❔", topic="Häufig gestellte Fragen", visibility="readonly",
                    guide=[
                        "Die häufigsten Fragen und ihre Antworten.",
                        "Ist deine Frage nicht dabei, melde dich beim Team.",
                    ],
                ),
            ]),
            cat("information", "📌", "readonly", [
                ch("ankuendigungen", "📢", "news", topic="Wichtige Ankündigungen", mode="announce"),
                ch("neuigkeiten", "🆕", topic="Server- und Bot-Updates", mode="announce"),
                ch("rollen-vergabe", "🏷️", topic="Rollen selbst vergeben", widget="roles"),
                ch("partner", "🤝", topic="Unsere Partner",
                    guide=[
                        "Server und Projekte, mit denen wir zusammenarbeiten.",
                    ],
                ),
                ch("gewinnspiele", "🎁", topic="Aktuelle Gewinnspiele", reactions=["🎉"]),
                ch("team-vorstellung", "👥", topic="Wer gehört zum Team?",
                    guide=[
                        "Wer zum Team gehört und wofür zuständig ist.",
                    ],
                ),
                ch("upload-plan", "📅", topic="Wann kommt was?"),
            ]),
            cat("community", "💬", "public", [
                ch("allgemein", "💭", topic="Allgemeiner Chat",
                    guide=[
                        "Der Hauptchat für alles, was keinen eigenen Kanal hat.",
                    ],
                ),
                ch("themenwuensche", "💡", topic="Themenwünsche", mode="threads", reactions=["👍", "👎"]),
                ch("fragen", "❓", topic="Fragen an den Creator"),
                ch("clips", "🎞️", topic="Clips aus Videos und Streams", mode="media", reactions=["🔥"]),
                ch("memes", "😂", topic="Memes", mode="media", reactions=["😂"]),
                ch("bot-befehle", "🤖", topic="Bot-Befehle",
                    guide=[
                        "Bot-Befehle gehören hierher, damit sie den Hauptchat nicht zumüllen.",
                    ],
                ),
            ]),
            cat("produktion", "🎬", "staff", [
                ch("ideen", "💡", "forum", topic="Ideensammlung", reactions=["👍", "👎"]),
                ch("skripte", "📝", topic="Skripte und Konzepte"),
                ch("aufnahme", "🎥", topic="Aufnahmeplanung"),
                ch("schnitt", "✂️", topic="Schnitt und Nachbearbeitung"),
                ch("thumbnails", "🖼️", topic="Thumbnail-Entwürfe", mode="media"),
                ch("endkontrolle", "🔍", topic="Letzter Check vor Upload"),
                ch("veroeffentlicht", "✅", topic="Veröffentlicht", visibility="archive"),
            ]),
            cat("rueckmeldungen", "🔍", "public", [
                ch("video-feedback", "🎬", topic="Rückmeldung zu Videos", slowmode=60),
                ch("stream-feedback", "🟣", topic="Rückmeldung zu Streams", slowmode=60),
                ch("design-feedback", "🎨", topic="Rückmeldung zu Grafiken", slowmode=60),
                ch("statistiken", "📊", topic="Zahlen und Reichweite", visibility="staff"),
            ]),
            cat("geschaeftlich", "💼", "leadership", [
                ch("kooperationen", "🤝", topic="Kooperationsanfragen"),
                ch("sponsoring", "💰", topic="Sponsoring"),
                ch("vertraege", "📄", topic="Verträge"),
                ch("rechnungen", "🧾", topic="Rechnungen"),
                ch("geschaefts-talk", "🔐", "voice", user_limit=8),
            ]),
            cat("zusammenarbeit", "🤝", "member", [
                ch("kooperations-boerse", "📌", topic="Offene Kooperationen"),
                ch("creator-lounge", "☕", topic="Austausch unter Creators"),
                ch("gegenseitige-werbung", "🔁", topic="Gegenseitige Promo"),
                ch("kooperations-talk", "🎙️", "voice", user_limit=10),
            ]),
            cat("studio", "🔊", "public", [
                j2c_channel(),
                ch("aufnahme-1", "🔴", "voice", user_limit=4),
                ch("aufnahme-2", "🔴", "voice", user_limit=4),
                ch("podcast", "🎙️", "voice", user_limit=6),
                ch("gemeinsam-schauen", "📺", "voice", user_limit=20),
                ch("community-treff", "☕", "voice"),
                ch("fragerunde", "❔", "stage"),
                ch("abwesend", "💤", "voice"),
            ]),
            cat("social media", "📱", "public", [
                ch("instagram", "📸", topic="Instagram-Beiträge", mode="media"),
                ch("tiktok", "🎵", topic="TikTok-Clips", mode="media"),
                ch("youtube", "▶️", topic="YouTube-Uploads", mode="media"),
                ch("twitch", "🟣", topic="Twitch-Streams", mode="media"),
                ch("x-twitter", "🐦", topic="Beiträge von X", mode="media"),
                ch("eigenwerbung", "📣", topic="Eigene Projekte vorstellen", slowmode=300,
                    guide=[
                        "Eigene Projekte vorstellen — ein Beitrag pro Person, kein Spam.",
                    ],
                ),
            ]),
            cat("sprachen", "🌍", "public", [
                ch("deutsch", "🇩🇪", topic="Deutschsprachiger Chat — die Hauptsprache", slowmode=3),
                ch("english", "🇬🇧", topic="English speaking chat", slowmode=3),
            ]),
            cat("sprach-talks", "🗣️", "public", [
                ch("deutsch-talk", "🇩🇪", "voice"),
                ch("english-talk", "🇬🇧", "voice"),
                ch("deutsch-talk-2", "🇩🇪", "voice", user_limit=10),
                ch("english-talk-2", "🇬🇧", "voice", user_limit=10),
            ]),
            cat("vip bereich", "💎", "vip", [
                ch("vip-chat", "💬", topic="Exklusiv für VIPs und Booster"),
                ch("vip-vorteile", "🎁", topic="Deine Vorteile", visibility="readonly"),
                ch("vip-wuensche", "🌠", topic="Wünsche und Rückmeldungen"),
                ch("vip-talk", "🥂", "voice", user_limit=15),
            ]),
            cat("hilfe", "🛟", "public", [
                ch("ticket-eroeffnen", "🎫", topic="Hier ein Support-Ticket öffnen",
                   visibility="readonly", widget="ticket"),
                ch("hilfe-und-support", "❓", "forum", topic="Frag die Community"),
                ch("fehler-melden", "🐛", topic="Fehler melden", mode="threads"),
                ch("vorschlaege", "💡", topic="Ideen für den Server", mode="threads", reactions=["👍", "👎"]),
                ch("beschwerden", "📣", topic="Beschwerden über Mitglieder", mode="threads"),
                ch("entbannungsantrag", "⚖️", topic="Einspruch gegen eine Strafe", mode="threads"),
            ]),
            cat("team", "🛡️", "staff", [
                ch("team-chat", "💼", topic="Interner Teamchat"),
                ch("team-ankuendigungen", "📣", topic="Ankündigungen fürs Team", mode="announce"),
                ch("aufgaben", "📋", topic="Aufgaben und Zuständigkeiten", widget="checklist"),
                ch("bewerbungen", "🧾", topic="Eingehende Bewerbungen", mode="threads"),
                ch("meldungen", "🚨", topic="Gemeldete Vorfälle"),
                ch("schichtplan", "🗓️", topic="Wer hat wann Dienst?"),
                ch("team-talk", "🎙️", "voice", user_limit=15),
                ch("besprechungsraum", "🪑", "voice", user_limit=25),
            ]),
            cat("logs", "📜", "staff", [
                ch("mod-logs", "🔨", topic="Moderationsaktionen", mode="log"),
                ch("mitglieder-logs", "👥", topic="Beitritte und Austritte", mode="log"),
                ch("nachrichten-logs", "✏️", topic="Bearbeitete und gelöschte Nachrichten", mode="log"),
                ch("sprach-logs", "🔊", topic="Voice-Aktivität", mode="log"),
                ch("rollen-logs", "🏷️", topic="Rollenänderungen", mode="log"),
                ch("kanal-logs", "🗂️", topic="Kanaländerungen", mode="log"),
                ch("social-logs", "📱", topic="Social-Media-Feeds und Erwähnungen", mode="log"),
                ch("bot-logs", "🤖", topic="Bot-Ereignisse", mode="log"),
                ch("einladungs-logs", "🔗", topic="Einladungs-Tracking", mode="log"),
                ch("server-logs", "🗃️", topic="Alles Übrige", mode="log"),
            ]),
        ],
    }


def support() -> dict[str, Any]:
    return {
        "key": "support",
        "name": "Support Center",
        "emoji": "🛟",
        "tagline": "Tickets, Wissensdatenbank und Eskalationsstufen",
        "premium": True,
        "accent": "#0EA5E9",
        "description": (
            "Ein Server, der auf Hilfe ausgelegt ist: Ticket-Forum, gepflegte "
            "Wissensdatenbank, klare Eskalationsstufen und ein "
            "Auswertungsbereich, in dem Qualität und Reaktionszeiten sichtbar "
            "werden."
        ),
        "highlights": [
            "Ticket-Forum mit getrennten Eskalationsstufen",
            "Oeffentliche Wissensdatenbank und häufige Fragen",
            "Interner Qualitäts- und Auswertungsbereich",
            "Sprechstundenräume mit Warteschlange",
        ],
        "roles": [
            role("ticket_team", "Ticket Team", "🎫", "#0EA5E9", "helper"),
            role("specialist", "Fachberater", "🧠", "#0891B2", "helper"),
            role("escalation", "Eskalation", "🚨", "#DC2626", "moderator"),
            role("quality", "Qualitaetsteam", "📈", "#7C3AED", "moderator"),
            role("knowledge", "Wissensredaktion", "📚", "#16A34A", "helper"),
        ],
        "categories": [
            cat("willkommen", "🚪", "gate", [
                ch("willkommen", "👋", topic="Willkommen! Verifiziere dich, um den Server zu sehen.", visibility="readonly",
                    guide=[
                        "Schön, dass du da bist.",
                        "Verifiziere dich nebenan, danach siehst du den gesamten Server.",
                    ],
                ),
                ch("verifizieren", "✅", topic="Hier verifizieren", widget="verify"),
                ch("regeln", "📜", topic="Serverregeln", visibility="readonly", widget="rules"),
                ch("haeufige-fragen", "❔", topic="Häufig gestellte Fragen", visibility="readonly",
                    guide=[
                        "Die häufigsten Fragen und ihre Antworten.",
                        "Ist deine Frage nicht dabei, melde dich beim Team.",
                    ],
                ),
            ]),
            cat("information", "📌", "readonly", [
                ch("ankuendigungen", "📢", "news", topic="Wichtige Ankündigungen", mode="announce"),
                ch("neuigkeiten", "🆕", topic="Server- und Bot-Updates", mode="announce"),
                ch("rollen-vergabe", "🏷️", topic="Rollen selbst vergeben", widget="roles"),
                ch("partner", "🤝", topic="Unsere Partner",
                    guide=[
                        "Server und Projekte, mit denen wir zusammenarbeiten.",
                    ],
                ),
                ch("gewinnspiele", "🎁", topic="Aktuelle Gewinnspiele", reactions=["🎉"]),
                ch("team-vorstellung", "👥", topic="Wer gehört zum Team?",
                    guide=[
                        "Wer zum Team gehört und wofür zuständig ist.",
                    ],
                ),
                ch("systemstatus", "🟢", topic="Systemstatus und Störungen", mode="announce"),
            ]),
            cat("hilfe", "🛟", "public", [
                ch("so-gehts", "👋", topic="So bekommst du Hilfe", visibility="readonly",
                    guide=[
                        "Kurze Fragen direkt nebenan.",
                        "Alles, was länger dauert, gehört in ein Ticket.",
                    ],
                ),
                ch("ticket-eroeffnen", "🎫", topic="Hier ein Support-Ticket öffnen",
                   visibility="readonly", widget="ticket"),
                ch("tickets", "❓", "forum", topic="Erstelle hier dein Ticket"),
                ch("kurze-fragen", "⚡", topic="Kurze Fragen ohne Ticket"),
                ch("community-hilfe", "🤝", topic="Nutzer helfen Nutzern"),
                ch("fehler-melden", "🐛", "forum", topic="Fehler melden"),
                ch("funktionswuensche", "💡", "forum", topic="Wünsche einreichen", reactions=["👍", "👎"]),
            ]),
            cat("wissen", "📚", "readonly", [
                ch("haeufige-fragen", "❔", topic="Häufig gestellte Fragen",
                    guide=[
                        "Die häufigsten Fragen und ihre Antworten.",
                        "Ist deine Frage nicht dabei, melde dich beim Team.",
                    ],
                ),
                ch("anleitungen", "📖", topic="Schritt-für-Schritt-Anleitungen"),
                ch("problemloesungen", "🔧", topic="Problemlösungen"),
                ch("aenderungen", "🔄", topic="Was hat sich geändert?"),
                ch("bekannte-probleme", "⚠️", topic="Bekannte Probleme"),
            ]),
            cat("sprechstunde", "🎙️", "public", [
                j2c_channel(),
                ch("warteschlange", "⏳", "voice"),
                ch("support-raum-1", "🧑‍💻", "voice", user_limit=3),
                ch("support-raum-2", "🧑‍💻", "voice", user_limit=3),
                ch("support-raum-3", "🧑‍💻", "voice", user_limit=3),
                ch("bildschirm-teilen", "🖥️", "voice", user_limit=5),
            ]),
            cat("support intern", "🔧", "staff", [
                ch("tagesbriefing", "📋", topic="Tagesbriefing"),
                ch("eskalation", "🚨", topic="Eskalierte Fälle"),
                ch("wissensredaktion", "✍️", topic="Artikel schreiben und pflegen"),
                ch("schichtplan", "🗓️", topic="Wer hat wann Dienst?"),
                ch("interner-talk", "🎧", "voice", user_limit=10),
            ]),
            cat("auswertung", "📈", "leadership", [
                ch("statistiken", "📊", topic="Zahlen und Trends"),
                ch("qualitaet", "🏅", topic="Qualitätssicherung"),
                ch("rueckmeldungen", "💬", topic="Was sagen die Nutzer?"),
                ch("verbesserungen", "🚀", topic="Maßnahmen"),
            ]),
            cat("sprachen", "🌍", "public", [
                ch("deutsch", "🇩🇪", topic="Deutschsprachiger Chat — die Hauptsprache", slowmode=3),
                ch("english", "🇬🇧", topic="English speaking chat", slowmode=3),
            ]),
            cat("sprach-talks", "🗣️", "public", [
                ch("deutsch-talk", "🇩🇪", "voice"),
                ch("english-talk", "🇬🇧", "voice"),
                ch("deutsch-talk-2", "🇩🇪", "voice", user_limit=10),
                ch("english-talk-2", "🇬🇧", "voice", user_limit=10),
            ]),
            cat("community", "💬", "public", [
                ch("allgemein", "💭", topic="Allgemeiner Chat",
                    guide=[
                        "Der Hauptchat für alles, was keinen eigenen Kanal hat.",
                    ],
                ),
                ch("sonstiges", "🌙", topic="Abseits vom Support"),
                ch("plauder-talk", "☕", "voice"),
            ]),
            cat("team", "🛡️", "staff", [
                ch("team-chat", "💼", topic="Interner Teamchat"),
                ch("team-ankuendigungen", "📣", topic="Ankündigungen fürs Team", mode="announce"),
                ch("aufgaben", "📋", topic="Aufgaben und Zuständigkeiten", widget="checklist"),
                ch("bewerbungen", "🧾", topic="Eingehende Bewerbungen", mode="threads"),
                ch("meldungen", "🚨", topic="Gemeldete Vorfälle"),
                ch("schichtplan", "🗓️", topic="Wer hat wann Dienst?"),
                ch("team-talk", "🎙️", "voice", user_limit=15),
                ch("besprechungsraum", "🪑", "voice", user_limit=25),
            ]),
            cat("leitung", "👑", "leadership", [
                ch("leitungs-chat", "🏛️", topic="Nur für die Serverleitung"),
                ch("planung", "🗺️", topic="Planung und Ausrichtung"),
                ch("personal", "🧑‍💼", topic="Personalthemen"),
                ch("leitungs-talk", "🔐", "voice", user_limit=10),
            ]),
            cat("logs", "📜", "staff", [
                ch("mod-logs", "🔨", topic="Moderationsaktionen", mode="log"),
                ch("mitglieder-logs", "👥", topic="Beitritte und Austritte", mode="log"),
                ch("nachrichten-logs", "✏️", topic="Bearbeitete und gelöschte Nachrichten", mode="log"),
                ch("sprach-logs", "🔊", topic="Voice-Aktivität", mode="log"),
                ch("rollen-logs", "🏷️", topic="Rollenänderungen", mode="log"),
                ch("kanal-logs", "🗂️", topic="Kanaländerungen", mode="log"),
                ch("social-logs", "📱", topic="Social-Media-Feeds und Erwähnungen", mode="log"),
                ch("bot-logs", "🤖", topic="Bot-Ereignisse", mode="log"),
                ch("einladungs-logs", "🔗", topic="Einladungs-Tracking", mode="log"),
                ch("server-logs", "🗃️", topic="Alles Übrige", mode="log"),
            ]),
        ],
    }


def esports() -> dict[str, Any]:
    return {
        "key": "esports",
        "name": "Esports Organisation",
        "emoji": "🏆",
        "tagline": "Kader, Scrims und Spieltagsbetrieb",
        "premium": True,
        "accent": "#E11D48",
        "description": (
            "Für Esports-Organisationen mit mehreren Teams: getrennte "
            "Kaderbereiche, Spieltagsbetrieb, Analyse und ein Bereich für "
            "Sponsoren und Presse — sauber abgeschirmt von der öffentlichen "
            "Fan-Community."
        ),
        "highlights": [
            "Eigene, private Bereiche für vier Kader",
            "Spieltags-Kanäle mit Vorbereitung, Live und Nachbesprechung",
            "Analyse- und Aufzeichnungsstruktur",
            "Getrennte Zonen für Fans, Presse und Sponsoren",
        ],
        "roles": [
            role("player", "Spieler", "🎮", "#E11D48", "trusted"),
            role("captain", "Kapitaen", "🎖️", "#BE123C", "helper"),
            role("coach_es", "Coach", "🧠", "#8B5CF6", "helper"),
            role("analyst", "Analyst", "📊", "#0EA5E9", "helper"),
            role("manager", "Teammanager", "📋", "#F59E0B", "moderator"),
            role("press", "Presse", "📰", "#64748B", "guest", hoist=False),
            role("fan", "Fan", "💛", "#FACC15", "member", hoist=False),
        ],
        "categories": [
            cat("willkommen", "🚪", "gate", [
                ch("willkommen", "👋", topic="Willkommen! Verifiziere dich, um den Server zu sehen.", visibility="readonly",
                    guide=[
                        "Schön, dass du da bist.",
                        "Verifiziere dich nebenan, danach siehst du den gesamten Server.",
                    ],
                ),
                ch("verifizieren", "✅", topic="Hier verifizieren", widget="verify"),
                ch("regeln", "📜", topic="Serverregeln", visibility="readonly", widget="rules"),
                ch("haeufige-fragen", "❔", topic="Häufig gestellte Fragen", visibility="readonly",
                    guide=[
                        "Die häufigsten Fragen und ihre Antworten.",
                        "Ist deine Frage nicht dabei, melde dich beim Team.",
                    ],
                ),
            ]),
            cat("information", "📌", "readonly", [
                ch("ankuendigungen", "📢", "news", topic="Wichtige Ankündigungen", mode="announce"),
                ch("neuigkeiten", "🆕", topic="Server- und Bot-Updates", mode="announce"),
                ch("rollen-vergabe", "🏷️", topic="Rollen selbst vergeben", widget="roles"),
                ch("partner", "🤝", topic="Unsere Partner",
                    guide=[
                        "Server und Projekte, mit denen wir zusammenarbeiten.",
                    ],
                ),
                ch("gewinnspiele", "🎁", topic="Aktuelle Gewinnspiele", reactions=["🎉"]),
                ch("team-vorstellung", "👥", topic="Wer gehört zum Team?",
                    guide=[
                        "Wer zum Team gehört und wofür zuständig ist.",
                    ],
                ),
                ch("spielplan", "📅", topic="Kommende Spiele", mode="announce"),
            ]),
            cat("fanbereich", "💛", "public", [
                j2c_channel(),
                ch("allgemein", "💬", topic="Fan-Chat",
                    guide=[
                        "Der Hauptchat für alles, was keinen eigenen Kanal hat.",
                    ],
                ),
                ch("spieltag-chat", "🔥", topic="Live mitfiebern"),
                ch("tippspiel", "🔮", topic="Tippspiel"),
                ch("fanart", "🎨", topic="Fanart und Unterstützung", mode="media", reactions=["⭐"]),
                ch("fanartikel", "👕", topic="Merchandise", mode="media"),
                ch("gemeinsam-schauen", "📺", "voice", user_limit=50),
                ch("fan-buehne", "📣", "stage"),
            ]),
            cat("kader", "🎯", "staff", [
                ch("hauptteam", "🥇", topic="Hauptteam"),
                ch("nachwuchs", "🥈", topic="Academy"),
                ch("frauen-team", "🥉", topic="Female Roster"),
                ch("content-team", "🎬", topic="Content-Team"),
                ch("sichtungen", "📝", topic="Probetrainings"),
                ch("kader-talk-1", "🎙️", "voice", user_limit=8),
                ch("kader-talk-2", "🎙️", "voice", user_limit=8),
            ]),
            cat("spieltag", "⚔️", "staff", [
                ch("vorbereitung", "📋", topic="Vorbereitung"),
                ch("aufstellungen", "🧩", topic="Aufstellungen"),
                ch("live", "🔴", topic="Während des Spiels"),
                ch("nachbesprechung", "🗣️", topic="Nachbesprechung"),
                ch("ergebnisse", "📊", topic="Ergebnisse", mode="announce"),
                ch("spielraum-1", "🅰️", "voice", user_limit=6),
                ch("spielraum-2", "🅱️", "voice", user_limit=6),
            ]),
            cat("analyse", "📊", "staff", [
                ch("spielanalyse", "🎞️", topic="Aufzeichnungen analysieren"),
                ch("gegner-beobachtung", "🔭", topic="Gegner beobachten"),
                ch("statistiken", "📈", topic="Statistiken"),
                ch("strategie", "🗺️", topic="Strategien"),
                ch("analyse-talk", "🖥️", "voice", user_limit=10),
            ]),
            cat("organisation", "🏢", "leadership", [
                ch("geschaeftsleitung", "🏛️", topic="Orga-Leitung"),
                ch("sponsoren", "💰", topic="Sponsoring"),
                ch("presse", "📰", topic="Presseanfragen"),
                ch("vertraege", "📄", topic="Verträge"),
                ch("budget", "🧾", topic="Budget"),
                ch("orga-talk", "🔐", "voice", user_limit=10),
            ]),
            cat("social media", "📱", "public", [
                ch("instagram", "📸", topic="Instagram-Beiträge", mode="media"),
                ch("tiktok", "🎵", topic="TikTok-Clips", mode="media"),
                ch("youtube", "▶️", topic="YouTube-Uploads", mode="media"),
                ch("twitch", "🟣", topic="Twitch-Streams", mode="media"),
                ch("x-twitter", "🐦", topic="Beiträge von X", mode="media"),
                ch("eigenwerbung", "📣", topic="Eigene Projekte vorstellen", slowmode=300,
                    guide=[
                        "Eigene Projekte vorstellen — ein Beitrag pro Person, kein Spam.",
                    ],
                ),
            ]),
            cat("sprachen", "🌍", "public", [
                ch("deutsch", "🇩🇪", topic="Deutschsprachiger Chat — die Hauptsprache", slowmode=3),
                ch("english", "🇬🇧", topic="English speaking chat", slowmode=3),
            ]),
            cat("sprach-talks", "🗣️", "public", [
                ch("deutsch-talk", "🇩🇪", "voice"),
                ch("english-talk", "🇬🇧", "voice"),
                ch("deutsch-talk-2", "🇩🇪", "voice", user_limit=10),
                ch("english-talk-2", "🇬🇧", "voice", user_limit=10),
            ]),
            cat("vip bereich", "💎", "vip", [
                ch("vip-chat", "💬", topic="Exklusiv für VIPs und Booster"),
                ch("vip-vorteile", "🎁", topic="Deine Vorteile", visibility="readonly"),
                ch("vip-wuensche", "🌠", topic="Wünsche und Rückmeldungen"),
                ch("vip-talk", "🥂", "voice", user_limit=15),
            ]),
            cat("hilfe", "🛟", "public", [
                ch("ticket-eroeffnen", "🎫", topic="Hier ein Support-Ticket öffnen",
                   visibility="readonly", widget="ticket"),
                ch("hilfe-und-support", "❓", "forum", topic="Frag die Community"),
                ch("fehler-melden", "🐛", topic="Fehler melden", mode="threads"),
                ch("vorschlaege", "💡", topic="Ideen für den Server", mode="threads", reactions=["👍", "👎"]),
                ch("beschwerden", "📣", topic="Beschwerden über Mitglieder", mode="threads"),
                ch("entbannungsantrag", "⚖️", topic="Einspruch gegen eine Strafe", mode="threads"),
            ]),
            cat("team", "🛡️", "staff", [
                ch("team-chat", "💼", topic="Interner Teamchat"),
                ch("team-ankuendigungen", "📣", topic="Ankündigungen fürs Team", mode="announce"),
                ch("aufgaben", "📋", topic="Aufgaben und Zuständigkeiten", widget="checklist"),
                ch("bewerbungen", "🧾", topic="Eingehende Bewerbungen", mode="threads"),
                ch("meldungen", "🚨", topic="Gemeldete Vorfälle"),
                ch("schichtplan", "🗓️", topic="Wer hat wann Dienst?"),
                ch("team-talk", "🎙️", "voice", user_limit=15),
                ch("besprechungsraum", "🪑", "voice", user_limit=25),
            ]),
            cat("logs", "📜", "staff", [
                ch("mod-logs", "🔨", topic="Moderationsaktionen", mode="log"),
                ch("mitglieder-logs", "👥", topic="Beitritte und Austritte", mode="log"),
                ch("nachrichten-logs", "✏️", topic="Bearbeitete und gelöschte Nachrichten", mode="log"),
                ch("sprach-logs", "🔊", topic="Voice-Aktivität", mode="log"),
                ch("rollen-logs", "🏷️", topic="Rollenänderungen", mode="log"),
                ch("kanal-logs", "🗂️", topic="Kanaländerungen", mode="log"),
                ch("social-logs", "📱", topic="Social-Media-Feeds und Erwähnungen", mode="log"),
                ch("bot-logs", "🤖", topic="Bot-Ereignisse", mode="log"),
                ch("einladungs-logs", "🔗", topic="Einladungs-Tracking", mode="log"),
                ch("server-logs", "🗃️", topic="Alles Übrige", mode="log"),
            ]),
        ],
    }


def music() -> dict[str, Any]:
    return {
        "key": "music",
        "name": "Musik & DJ",
        "emoji": "🎵",
        "tagline": "Hörsessions, eigene Tracks und Bühnenabende",
        "premium": False,
        "accent": "#A855F7",
        "description": (
            "Für Musikserver: gemeinsame Hörsessions, ein Bereich für eigene "
            "Produktionen mit Rückmeldungen, Bühnenabende für Live-Sets und "
            "getrennte Räume nach Genre. Der Zählkanal fehlt hier bewusst — "
            "auf einem Musikserver zählt niemand."
        ),
        "highlights": [
            "Bühne für Live-Sets und Hörabende",
            "Eigene Produktionen mit strukturierter Rückmeldung",
            "Sprachräume nach Genre getrennt",
            "Vollständige Log-Suite inklusive Voice-Logs",
        ],
        "roles": [
            role("dj", "DJ", "🎧", "#A855F7", "trusted"),
            role("producer", "Producer", "🎹", "#7C3AED", "trusted"),
            role("vocalist", "Vocalist", "🎤", "#EC4899", "trusted", hoist=False),
            role("kurator", "Kurator", "📻", "#F59E0B", "helper"),
        ],
        "categories": [
            cat("willkommen", "🚪", "gate", [
                ch("willkommen", "👋", topic="Willkommen! Verifiziere dich, um den Server zu sehen.", visibility="readonly",
                    guide=[
                        "Schön, dass du da bist.",
                        "Verifiziere dich nebenan, danach siehst du den gesamten Server.",
                    ],
                ),
                ch("verifizieren", "✅", topic="Hier verifizieren", widget="verify"),
                ch("regeln", "📜", topic="Serverregeln", visibility="readonly", widget="rules"),
                ch("haeufige-fragen", "❔", topic="Häufig gestellte Fragen", visibility="readonly",
                    guide=[
                        "Die häufigsten Fragen und ihre Antworten.",
                        "Ist deine Frage nicht dabei, melde dich beim Team.",
                    ],
                ),
            ]),
            cat("information", "📌", "readonly", [
                ch("ankuendigungen", "📢", "news", topic="Wichtige Ankündigungen", mode="announce"),
                ch("neuigkeiten", "🆕", topic="Server- und Bot-Updates", mode="announce"),
                ch("rollen-vergabe", "🏷️", topic="Rollen selbst vergeben", widget="roles"),
                ch("partner", "🤝", topic="Unsere Partner",
                    guide=[
                        "Server und Projekte, mit denen wir zusammenarbeiten.",
                    ],
                ),
                ch("team-vorstellung", "👥", topic="Wer gehört zum Team?",
                    guide=[
                        "Wer zum Team gehört und wofür zuständig ist.",
                    ],
                ),
            ]),
            cat("musik", "🎵", "public", [
                ch("was-laeuft-gerade", "🎶", topic="Was hörst du gerade?"),
                ch("empfehlungen", "⭐", topic="Empfehlungen und Entdeckungen", reactions=["⭐"]),
                ch("playlisten", "📻", topic="Geteilte Playlisten", mode="media"),
                ch("neuerscheinungen", "🆕", topic="Neue Alben und Singles"),
                ch("konzerte", "🎫", topic="Konzerte und Festivals"),
                ch("liedtexte", "📝", topic="Texte und ihre Bedeutung"),
                ch("musik-quiz", "❓", topic="Rate den Song", reactions=["🎵"]),
            ]),
            cat("eigene-musik", "🎹", "public", [
                ch("eigene-tracks", "🎼", topic="Zeig deine Produktionen", slowmode=120, mode="media", reactions=["🔥"]),
                ch("rueckmeldungen", "💡", topic="Konstruktive Kritik zu Tracks", mode="threads"),
                ch("zusammenarbeit", "🤝", topic="Wer sucht wen für ein Projekt?"),
                ch("technik-hilfe", "🔧", topic="DAWs, Plugins, Aufnahmetechnik"),
                ch("stimmen-gesucht", "🎤", topic="Vocalisten und Features"),
            ]),
            cat("buehne", "🎤", "public", [
                ch("buehnen-plan", "📅", "news", topic="Wann spielt wer?", visibility="readonly", mode="announce"),
                ch("buehnen-chat", "💬", topic="Chat während der Sets"),
                ch("hauptbuehne", "🎪", "stage"),
                ch("offene-buehne", "🎙️", "stage"),
                ch("hoersession", "🎧", "voice", user_limit=25),
            ]),
            cat("sprachen", "🌍", "public", [
                ch("deutsch", "🇩🇪", topic="Deutschsprachiger Chat — die Hauptsprache", slowmode=3),
                ch("english", "🇬🇧", topic="English speaking chat", slowmode=3),
            ]),
            cat("sprach-talks", "🗣️", "public", [
                ch("deutsch-talk", "🇩🇪", "voice"),
                ch("english-talk", "🇬🇧", "voice"),
                ch("deutsch-talk-2", "🇩🇪", "voice", user_limit=10),
                ch("english-talk-2", "🇬🇧", "voice", user_limit=10),
            ]),
            cat("sprachkanaele", "🔊", "public", [
                j2c_channel(),
                ch("allgemeiner-talk", "🎙️", "voice"),
                ch("elektro", "🎛️", "voice", user_limit=15),
                ch("rock-und-metal", "🎸", "voice", user_limit=15),
                ch("hip-hop", "🎤", "voice", user_limit=15),
                ch("klassik-und-jazz", "🎻", "voice", user_limit=10),
                ch("chill-ecke", "☕", "voice", user_limit=10),
                ch("uebungsraum", "🥁", "voice", user_limit=5),
                ch("abwesend", "💤", "voice"),
            ]),
            cat("community", "💬", "public", [
                ch("allgemein", "💭", topic="Der Hauptchat", slowmode=3,
                    guide=[
                        "Der Hauptchat für alles, was keinen eigenen Kanal hat.",
                    ],
                ),
                ch("bilder-und-clips", "🖼️", topic="Bilder, Clips, Fundstücke", mode="media"),
                ch("memes", "😂", topic="Nur Memes", mode="media", reactions=["😂"]),
                ch("sonstiges", "🌙", topic="Alles, was sonst nirgends passt"),
                ch("bot-befehle", "🤖", topic="Bot-Befehle gehören hierher",
                    guide=[
                        "Bot-Befehle gehören hierher, damit sie den Hauptchat nicht zumüllen.",
                    ],
                ),
            ]),
            cat("hilfe", "🛟", "public", [
                ch("ticket-eroeffnen", "🎫", topic="Hier ein Ticket öffnen",
                   visibility="readonly", widget="ticket"),
                ch("kurze-fragen", "⚡", topic="Kurze Fragen ohne Ticket"),
            ]),
            cat("team", "🛡️", "staff", [
                ch("team-chat", "💼", topic="Interner Teamchat"),
                ch("team-ankuendigungen", "📣", topic="Ankündigungen fürs Team", mode="announce"),
                ch("aufgaben", "📋", topic="Aufgaben und Zuständigkeiten", widget="checklist"),
                ch("bewerbungen", "🧾", topic="Eingehende Bewerbungen", mode="threads"),
                ch("meldungen", "🚨", topic="Gemeldete Vorfälle"),
                ch("team-talk", "🎙️", "voice", user_limit=15),
            ]),
            cat("leitung", "👑", "leadership", [
                ch("leitungs-chat", "🏛️", topic="Nur für die Serverleitung"),
                ch("planung", "🗺️", topic="Planung und Ausrichtung"),
                ch("leitungs-talk", "🔐", "voice", user_limit=10),
            ]),
            cat("logs", "📜", "staff", [
                ch("mod-logs", "🔨", topic="Moderationsaktionen", mode="log"),
                ch("mitglieder-logs", "👥", topic="Beitritte und Austritte", mode="log"),
                ch("nachrichten-logs", "✏️", topic="Bearbeitete und gelöschte Nachrichten", mode="log"),
                ch("sprach-logs", "🔊", topic="Voice-Aktivität", mode="log"),
                ch("rollen-logs", "🏷️", topic="Rollenänderungen", mode="log"),
                ch("kanal-logs", "🗂️", topic="Kanaländerungen", mode="log"),
                ch("social-logs", "📱", topic="Social-Media-Feeds und Erwähnungen", mode="log"),
                ch("bot-logs", "🤖", topic="Bot-Ereignisse", mode="log"),
                ch("einladungs-logs", "🔗", topic="Einladungs-Tracking", mode="log"),
                ch("server-logs", "🗃️", topic="Alles Übrige", mode="log"),
            ]),
        ],
    }


def dev() -> dict[str, Any]:
    return {
        "key": "dev",
        "name": "Entwickler & Open Source",
        "emoji": "💻",
        "tagline": "Code-Hilfe, Projekte und Code-Reviews",
        "premium": False,
        "accent": "#22C55E",
        "description": (
            "Für Entwickler-Communities: nach Sprachen getrennte Hilfe-Foren, "
            "ein Bereich für eigene Projekte, Code-Reviews und Pair-Programming "
            "mit Bildschirmfreigabe. Ohne Zählkanal und ohne Event-Bereich — "
            "hier wird gearbeitet, nicht gefeiert."
        ),
        "highlights": [
            "Hilfe-Foren getrennt nach Sprache und Stack",
            "Code-Review-Bereich mit Threads pro Anfrage",
            "Pair-Programming-Räume mit Bildschirmfreigabe",
            "Ticket-Panel für längere Anliegen",
        ],
        "roles": [
            role("maintainer", "Maintainer", "🔑", "#22C55E", "helper"),
            role("contributor", "Contributor", "🛠️", "#16A34A", "trusted"),
            role("reviewer", "Reviewer", "🔍", "#0EA5E9", "helper"),
            role("frontend", "Frontend", "🎨", "#EC4899", "member", hoist=False),
            role("backend", "Backend", "⚙️", "#64748B", "member", hoist=False),
            role("devops", "DevOps", "☁️", "#F59E0B", "member", hoist=False),
        ],
        "categories": [
            cat("willkommen", "🚪", "gate", [
                ch("willkommen", "👋", topic="Willkommen! Verifiziere dich, um den Server zu sehen.", visibility="readonly",
                    guide=[
                        "Schön, dass du da bist.",
                        "Verifiziere dich nebenan, danach siehst du den gesamten Server.",
                    ],
                ),
                ch("verifizieren", "✅", topic="Hier verifizieren", widget="verify"),
                ch("regeln", "📜", topic="Serverregeln", visibility="readonly", widget="rules"),
                ch("haeufige-fragen", "❔", topic="Häufig gestellte Fragen", visibility="readonly",
                    guide=[
                        "Die häufigsten Fragen und ihre Antworten.",
                        "Ist deine Frage nicht dabei, melde dich beim Team.",
                    ],
                ),
            ]),
            cat("information", "📌", "readonly", [
                ch("ankuendigungen", "📢", "news", topic="Wichtige Ankündigungen", mode="announce"),
                ch("neuigkeiten", "🆕", topic="Server- und Bot-Updates", mode="announce"),
                ch("rollen-vergabe", "🏷️", topic="Rollen selbst vergeben", widget="roles"),
                ch("projekt-vorstellung", "📦", topic="Womit beschäftigen wir uns?",
                    guide=[
                        "Die Projekte, um die es auf diesem Server geht.",
                    ],
                ),
                ch("team-vorstellung", "👥", topic="Wer gehört zum Team?",
                    guide=[
                        "Wer zum Team gehört und wofür zuständig ist.",
                    ],
                ),
            ]),
            cat("hilfe", "🛟", "public", [
                ch("so-fragst-du-richtig", "📖", topic="So bekommst du schnell Hilfe", visibility="readonly",
                    guide=[
                        "Zeig deinen Code, die Fehlermeldung und was du schon versucht hast.",
                        "Alles, was länger dauert, gehört in ein Ticket.",
                    ],
                ),
                ch("ticket-eroeffnen", "🎫", topic="Hier ein Ticket öffnen",
                   visibility="readonly", widget="ticket"),
                ch("hilfe-allgemein", "❓", "forum", topic="Allgemeine Fragen"),
                ch("hilfe-web", "🌐", "forum", topic="HTML, CSS, JavaScript, Frameworks"),
                ch("hilfe-python", "🐍", "forum", topic="Python und sein Umfeld"),
                ch("hilfe-datenbanken", "🗄️", "forum", topic="SQL, Schema-Fragen, Abfragen"),
                ch("hilfe-devops", "☁️", "forum", topic="Deployment, Docker, CI"),
                ch("kurze-fragen", "⚡", topic="Einzeiler ohne Forum-Beitrag"),
            ]),
            cat("projekte", "📦", "public", [
                ch("projekt-vorstellen", "🚀", topic="Stell dein Projekt vor", slowmode=300, mode="media", reactions=["🚀"]),
                ch("code-review", "🔍", topic="Bitte um Durchsicht", mode="threads"),
                ch("mitstreiter-gesucht", "🤝", topic="Wer sucht wen für ein Projekt?"),
                ch("bibliotheken", "📚", topic="Nützliche Bibliotheken und Werkzeuge"),
                ch("fehler-melden", "🐛", "forum", topic="Fehler in unseren Projekten"),
                ch("funktionswuensche", "💡", "forum", topic="Wünsche einreichen", reactions=["👍", "👎"]),
            ]),
            cat("austausch", "💬", "public", [
                ch("allgemein", "💭", topic="Der Hauptchat", slowmode=3,
                    guide=[
                        "Der Hauptchat für alles, was keinen eigenen Kanal hat.",
                    ],
                ),
                ch("arbeitsplatz", "🖥️", topic="Zeig deinen Aufbau", mode="media"),
                ch("stellenangebote", "💼", topic="Jobs und Aufträge", slowmode=600),
                ch("lesestoff", "📰", topic="Artikel und Vorträge"),
                ch("memes", "😂", topic="Nur Memes", mode="media", reactions=["😂"]),
                ch("bot-befehle", "🤖", topic="Bot-Befehle gehören hierher",
                    guide=[
                        "Bot-Befehle gehören hierher, damit sie den Hauptchat nicht zumüllen.",
                    ],
                ),
            ]),
            cat("sprachen", "🌍", "public", [
                ch("deutsch", "🇩🇪", topic="Deutschsprachiger Chat — die Hauptsprache", slowmode=3),
                ch("english", "🇬🇧", topic="English speaking chat", slowmode=3),
            ]),
            cat("sprach-talks", "🗣️", "public", [
                ch("deutsch-talk", "🇩🇪", "voice"),
                ch("english-talk", "🇬🇧", "voice"),
                ch("deutsch-talk-2", "🇩🇪", "voice", user_limit=10),
                ch("english-talk-2", "🇬🇧", "voice", user_limit=10),
            ]),
            cat("arbeitsraeume", "🔊", "public", [
                j2c_channel(),
                ch("allgemeiner-talk", "🎙️", "voice"),
                ch("pair-programming-1", "👥", "voice", user_limit=2),
                ch("pair-programming-2", "👥", "voice", user_limit=2),
                ch("bildschirm-teilen", "🖥️", "voice", user_limit=8),
                ch("stilles-arbeiten", "🤫", "voice", user_limit=20),
                ch("chill-ecke", "☕", "voice", user_limit=10),
                ch("abwesend", "💤", "voice"),
            ]),
            cat("team", "🛡️", "staff", [
                ch("team-chat", "💼", topic="Interner Teamchat"),
                ch("team-ankuendigungen", "📣", topic="Ankündigungen fürs Team", mode="announce"),
                ch("aufgaben", "📋", topic="Aufgaben und Zuständigkeiten", widget="checklist"),
                ch("bewerbungen", "🧾", topic="Eingehende Bewerbungen", mode="threads"),
                ch("meldungen", "🚨", topic="Gemeldete Vorfälle"),
                ch("team-talk", "🎙️", "voice", user_limit=15),
            ]),
            cat("leitung", "👑", "leadership", [
                ch("leitungs-chat", "🏛️", topic="Nur für die Serverleitung"),
                ch("planung", "🗺️", topic="Planung und Ausrichtung"),
                ch("leitungs-talk", "🔐", "voice", user_limit=10),
            ]),
            cat("logs", "📜", "staff", [
                ch("mod-logs", "🔨", topic="Moderationsaktionen", mode="log"),
                ch("mitglieder-logs", "👥", topic="Beitritte und Austritte", mode="log"),
                ch("nachrichten-logs", "✏️", topic="Bearbeitete und gelöschte Nachrichten", mode="log"),
                ch("sprach-logs", "🔊", topic="Voice-Aktivität", mode="log"),
                ch("rollen-logs", "🏷️", topic="Rollenänderungen", mode="log"),
                ch("kanal-logs", "🗂️", topic="Kanaländerungen", mode="log"),
                ch("social-logs", "📱", topic="Social-Media-Feeds und Erwähnungen", mode="log"),
                ch("bot-logs", "🤖", topic="Bot-Ereignisse", mode="log"),
                ch("einladungs-logs", "🔗", topic="Einladungs-Tracking", mode="log"),
                ch("server-logs", "🗃️", topic="Alles Übrige", mode="log"),
            ]),
        ],
    }


def minimal() -> dict[str, Any]:
    return {
        "key": "minimal",
        "name": "Kleiner Server",
        "emoji": "🌱",
        "tagline": "Nur das Nötigste — für Freundeskreise und den Anfang",
        "premium": False,
        "accent": "#14B8A6",
        "description": (
            "Bewusst klein: keine Verify-Schleuse, kein Ticket-System, keine "
            "Rollen-Vergabe. Ein Regelkanal, ein paar Chats, ein paar "
            "Sprachräume und ein knapper Log-Bereich. Für Freundeskreise und "
            "alle, die mit fünfzehn Kanälen auskommen statt mit neunzig."
        ),
        "highlights": [
            "Keine Verify-Schleuse — jeder ist sofort dabei",
            "Nur vier Log-Kanäle statt zehn",
            "Wenige, klar benannte Kanäle statt einer langen Liste",
            "Lässt sich später jederzeit erweitern",
        ],
        "roles": [
            role("stammgast", "Stammgast", "🌿", "#14B8A6", "trusted", hoist=False),
        ],
        "categories": [
            # Kein Verify-Widget: dieser Server soll ohne Schleuse
            # laufen. Die Gate-Kategorie bleibt trotzdem, weil der
            # Willkommenskanal dort steht -- der Hauptbot findet die
            # Begruessung ueber genau diese Kategorie.
            cat("start", "🚪", "gate", [
                ch("willkommen", "👋", topic="Willkommen auf dem Server", visibility="readonly",
                    guide=[
                        "Schön, dass du da bist.",
                        "Lies kurz die Regeln, dann leg einfach los.",
                    ],
                ),
                ch("regeln", "📜", topic="Serverregeln", visibility="readonly", widget="rules"),
            ]),
            cat("information", "📌", "readonly", [
                ch("ankuendigungen", "📢", topic="Wichtige Ankündigungen", mode="announce"),
            ]),
            cat("chat", "💬", "public", [
                ch("allgemein", "💭", topic="Der Hauptchat",
                    guide=[
                        "Der Hauptchat für alles, was keinen eigenen Kanal hat.",
                    ],
                ),
                ch("bilder-und-clips", "🖼️", topic="Bilder, Clips, Fundstücke", mode="media"),
                ch("memes", "😂", topic="Nur Memes", mode="media", reactions=["😂"]),
                ch("bot-befehle", "🤖", topic="Bot-Befehle gehören hierher",
                    guide=[
                        "Bot-Befehle gehören hierher, damit sie den Hauptchat nicht zumüllen.",
                    ],
                ),
            ]),
            cat("sprachkanaele", "🔊", "public", [
                j2c_channel(),
                ch("allgemeiner-talk", "🎙️", "voice"),
                ch("zu-zweit", "👥", "voice", user_limit=2),
                ch("chill-ecke", "☕", "voice", user_limit=10),
                ch("abwesend", "💤", "voice"),
            ]),
            cat("team", "🛡️", "staff", [
                ch("team-chat", "💼", topic="Interner Teamchat"),
                ch("team-talk", "🎙️", "voice", user_limit=10),
            ]),
            # Nur die vier Logs, die man auf einem kleinen Server
            # wirklich liest. Zehn Log-Kanaele fuer fuenfzehn Leute
            # waeren mehr Logs als Chats.
            cat("logs", "📜", "staff", [
                ch("mod-logs", "🔨", topic="Moderationsaktionen", mode="log"),
                ch("mitglieder-logs", "👥", topic="Beitritte und Austritte", mode="log"),
                ch("nachrichten-logs", "✏️", topic="Bearbeitete und gelöschte Nachrichten", mode="log"),
                ch("server-logs", "🗃️", topic="Alles Übrige", mode="log"),
            ]),
        ],
    }


def clan() -> dict[str, Any]:
    return {
        "key": "clan",
        "name": "Clan Server",
        "emoji": "⚔️",
        "tagline": "Clan Talk, Fight Calls und ein Bereich nur für Mitglieder",
        "premium": True,
        "accent": "#DC2626",
        "description": (
            "Für Clans und Gilden, die zusammen spielen statt nur zusammen "
            "zu chatten: fester Kader mit Rängen, Fight Calls vor dem Match, "
            "Kriegsplanung, Trainingsräume und ein abgeschirmter Bereich, "
            "den nur Clan-Mitglieder sehen. Aufgebaut wie der Gaming Hub — "
            "aber alles dreht sich um den Clan, nicht um einzelne Spiele."
        ),
        "highlights": [
            "Clan Talk, Fight Call und War Room als eigene Sprachräume",
            "Geschlossener Mitglieder-Bereich — nur für den Kader",
            "Kriegsplanung mit Gegner-Aufklärung und Aufstellung",
            "Ränge vom Rekruten bis zur Clanleitung",
        ],
        "roles": [
            role("clan_leader", "Clanleiter", "👑", "#DC2626", "leadership"),
            role("officer", "Offizier", "🎖️", "#EA580C", "moderator"),
            role("veteran", "Veteran", "🛡️", "#F59E0B", "trusted"),
            role("clan_member", "Clan Mitglied", "⚔️", "#DC2626", "vip"),
            role("recruit", "Rekrut", "🌱", "#64748B", "member", hoist=False),
            role("war_caller", "Fight Caller", "📣", "#8B5CF6", "helper"),
            role("scout", "Scout", "🔭", "#0EA5E9", "trusted", hoist=False),
        ],
        "categories": [
            cat("willkommen", "🚪", "gate", [
                ch("willkommen", "👋", topic="Willkommen! Verifiziere dich, um den Server zu sehen.", visibility="readonly",
                    guide=[
                        "Schön, dass du da bist.",
                        "Verifiziere dich nebenan, danach siehst du den gesamten Server.",
                    ],
                ),
                ch("verifizieren", "✅", topic="Hier verifizieren", widget="verify"),
                ch("regeln", "📜", topic="Serverregeln", visibility="readonly", widget="rules"),
                ch("haeufige-fragen", "❔", topic="Häufig gestellte Fragen", visibility="readonly",
                    guide=[
                        "Die häufigsten Fragen und ihre Antworten.",
                        "Ist deine Frage nicht dabei, melde dich beim Team.",
                    ],
                ),
            ]),
            cat("information", "📌", "readonly", [
                ch("ankuendigungen", "📢", "news", topic="Wichtige Ankündigungen", mode="announce"),
                ch("clan-news", "🆕", topic="Neuigkeiten aus dem Clan", mode="announce"),
                ch("rollen-vergabe", "🏷️", topic="Rollen selbst vergeben", widget="roles"),
                ch("kader", "📋", topic="Wer gehört zum Clan?",
                    guide=[
                        "Der aktuelle Kader mit Rängen und Zuständigkeiten.",
                    ],
                ),
                ch("erfolge", "🏆", topic="Gewonnene Matches und Turniere", reactions=["🏆"]),
                ch("partner", "🤝", topic="Befreundete Clans",
                    guide=[
                        "Clans und Projekte, mit denen wir zusammenarbeiten.",
                    ],
                ),
            ]),
            # Der Bewerbungsweg. Ein Clan lebt vom Nachwuchs, und ohne
            # eigenen Bereich landen Bewerbungen im Hauptchat, wo sie
            # nach zehn Nachrichten niemand mehr findet.
            cat("beitreten", "📝", "public", [
                ch("so-bewirbst-du-dich", "📖", topic="So kommst du in den Clan", visibility="readonly",
                    guide=[
                        "Lies die Anforderungen, dann stell dich nebenan vor.",
                        "Das Team meldet sich bei dir.",
                    ],
                ),
                ch("bewerbungen", "🧾", "forum", topic="Bewirb dich hier"),
                ch("probezeit", "🌱", topic="Chat für Rekruten in der Probezeit"),
                ch("vorstellung", "👋", topic="Stell dich kurz vor"),
            ]),
            cat("clan chat", "💬", "public", [
                ch("allgemein", "💭", topic="Der Hauptchat", slowmode=3,
                    guide=[
                        "Der Hauptchat für alles, was keinen eigenen Kanal hat.",
                    ],
                ),
                ch("clips-und-bilder", "🎬", topic="Deine besten Momente", mode="media", reactions=["🔥"]),
                ch("memes", "😂", topic="Nur Memes", mode="media", reactions=["😂"]),
                ch("builds-und-setups", "🛠️", topic="Ausrüstung, Builds, Einstellungen"),
                ch("patchnotes", "📄", topic="Was hat sich im Spiel geändert?"),
                ch("bot-befehle", "🤖", topic="Bot-Befehle gehören hierher",
                    guide=[
                        "Bot-Befehle gehören hierher, damit sie den Hauptchat nicht zumüllen.",
                    ],
                ),
            ]),
            # Das Herzstück: alles rund um den nächsten Kampf.
            cat("kriegsplanung", "⚔️", "public", [
                ch("fight-plan", "🗺️", topic="Wie gehen wir das Match an?", mode="threads"),
                ch("aufstellung", "📋", topic="Wer spielt welche Rolle?"),
                ch("gegner-aufklaerung", "🔭", topic="Was wissen wir über den Gegner?"),
                ch("match-termine", "📅", "news", topic="Wann spielen wir?", visibility="readonly", mode="announce"),
                ch("anwesenheit", "✋", topic="Wer kann wann?", reactions=["✅", "❌"]),
                ch("nachbesprechung", "📊", topic="Was lief gut, was nicht?", mode="threads"),
            ]),
            # Die Sprachkanäle, die dem Clan seinen Namen geben.
            cat("clan talks", "🔊", "public", [
                j2c_channel(),
                ch("clan-talk", "⚔️", "voice"),
                ch("clan-talk-2", "⚔️", "voice", user_limit=15),
                ch("fight-call", "📣", "voice", user_limit=10),
                ch("fight-call-2", "📣", "voice", user_limit=10),
                ch("war-room", "🗺️", "voice", user_limit=20),
                ch("zu-zweit", "👥", "voice", user_limit=2),
                ch("zu-dritt", "👨‍👩‍👦", "voice", user_limit=3),
                ch("squad-1", "🛡️", "voice", user_limit=5),
                ch("squad-2", "🛡️", "voice", user_limit=5),
                ch("scrim-raum", "🎯", "voice", user_limit=12),
                ch("kommentar-buehne", "🎙️", "stage"),
                ch("chill-ecke", "☕", "voice", user_limit=10),
                ch("musik", "🎶", "voice"),
                ch("abwesend", "💤", "voice"),
            ]),
            cat("training", "🎯", "public", [
                ch("trainingsplan", "📅", topic="Wann wird trainiert?", mode="announce"),
                ch("uebungen", "🔁", topic="Drills und Übungen"),
                ch("coaching", "🧠", topic="Frag nach Rückmeldung", mode="threads"),
                ch("aufnahmen", "📼", topic="Mitschnitte zum Auswerten", mode="media"),
                ch("trainingsraum-1", "🎯", "voice", user_limit=8),
                ch("trainingsraum-2", "🎯", "voice", user_limit=8),
            ]),
            # Nur für den Kader. `member`-Sichtbarkeit heißt: wer die
            # Verify-Schleuse passiert hat, ist drin -- aber kein Gast
            # von außen.
            cat("mitglieder", "🔐", "member", [
                ch("mitglieder-chat", "🗣️", topic="Nur für den Kader"),
                ch("interne-absprachen", "📌", topic="Was nicht nach außen gehört"),
                ch("kasse", "💰", topic="Clan-Kasse und Beiträge"),
                ch("mitglieder-talk", "🔒", "voice", user_limit=25),
            ]),
            # Der Premium-Bereich. `vip`-Sichtbarkeit: unsichtbar für
            # alle außer VIP, Booster, Partner und das Team. Genau
            # dafür gibt es diese Stufe schon -- eine eigene zu bauen
            # hieße, die Rechteregeln ein zweites Mal zu schreiben.
            cat("premium", "💎", "vip", [
                ch("premium-chat", "💎", topic="Nur für Premium-Mitglieder"),
                ch("premium-vorteile", "🎁", topic="Was Premium dir bringt", visibility="readonly",
                    guide=[
                        "Deine Vorteile als Premium-Mitglied.",
                    ],
                ),
                ch("premium-wuensche", "💡", topic="Wünsche und Vorschläge", mode="threads"),
                ch("frueher-zugang", "🚀", topic="Neues zuerst für Premium", mode="announce"),
                ch("premium-talk", "💎", "voice", user_limit=15),
                ch("premium-lounge", "🛋️", "voice", user_limit=10),
            ]),
            cat("sprachen", "🌍", "public", [
                ch("deutsch", "🇩🇪", topic="Deutschsprachiger Chat — die Hauptsprache", slowmode=3),
                ch("english", "🇬🇧", topic="English speaking chat", slowmode=3),
            ]),
            cat("sprach-talks", "🗣️", "public", [
                ch("deutsch-talk", "🇩🇪", "voice"),
                ch("english-talk", "🇬🇧", "voice"),
                ch("deutsch-talk-2", "🇩🇪", "voice", user_limit=10),
                ch("english-talk-2", "🇬🇧", "voice", user_limit=10),
            ]),
            cat("hilfe", "🛟", "public", [
                ch("ticket-eroeffnen", "🎫", topic="Hier ein Ticket öffnen",
                   visibility="readonly", widget="ticket"),
                ch("kurze-fragen", "⚡", topic="Kurze Fragen ohne Ticket"),
                ch("fehler-melden", "🐛", topic="Probleme auf dem Server melden"),
            ]),
            cat("team", "🛡️", "staff", [
                ch("team-chat", "💼", topic="Interner Teamchat"),
                ch("team-ankuendigungen", "📣", topic="Ankündigungen fürs Team", mode="announce"),
                ch("aufgaben", "📋", topic="Aufgaben und Zuständigkeiten", widget="checklist"),
                ch("bewerbungs-sichtung", "🧾", topic="Eingehende Bewerbungen", mode="threads"),
                ch("meldungen", "🚨", topic="Gemeldete Vorfälle"),
                ch("team-talk", "🎙️", "voice", user_limit=15),
            ]),
            cat("leitung", "👑", "leadership", [
                ch("leitungs-chat", "🏛️", topic="Nur für die Clanleitung"),
                ch("kader-planung", "🗺️", topic="Wer kommt, wer geht"),
                ch("clan-kriege", "⚔️", topic="Absprachen mit anderen Clans"),
                ch("leitungs-talk", "🔐", "voice", user_limit=10),
            ]),
            cat("logs", "📜", "staff", [
                ch("mod-logs", "🔨", topic="Moderationsaktionen", mode="log"),
                ch("mitglieder-logs", "👥", topic="Beitritte und Austritte", mode="log"),
                ch("nachrichten-logs", "✏️", topic="Bearbeitete und gelöschte Nachrichten", mode="log"),
                ch("sprach-logs", "🔊", topic="Voice-Aktivität", mode="log"),
                ch("rollen-logs", "🏷️", topic="Rollenänderungen", mode="log"),
                ch("kanal-logs", "🗂️", topic="Kanaländerungen", mode="log"),
                ch("social-logs", "📱", topic="Social-Media-Feeds und Erwähnungen", mode="log"),
                ch("bot-logs", "🤖", topic="Bot-Ereignisse", mode="log"),
                ch("einladungs-logs", "🔗", topic="Einladungs-Tracking", mode="log"),
                ch("server-logs", "🗃️", topic="Alles Übrige", mode="log"),
            ]),
        ],
    }

def fitness() -> dict[str, Any]:
    return {
        "key": "fitness",
        "name": "Fitness & Sport",
        "emoji": "🏋️",
        "tagline": "Trainingspläne, Challenges und gemeinsame Ziele",
        "premium": True,
        "accent": "#16A34A",
        "description": (
            "Für alle, die trainieren statt nur darüber zu reden: ein Kanal "
            "pro Trainingsart, Formchecks per Video, eine Challenge-"
            "Verwaltung mit Anmeldung und Ergebnissen, Ernährung und ein "
            "Sprachbereich für gemeinsame Workouts — vom Solo-Lauf bis zum "
            "Gruppen-Training."
        ),
        "highlights": [
            "Formcheck-Kanal: Technik per Video bewerten lassen",
            "Monats-Challenges mit Anmeldung und Ergebnissen",
            "Eigene Bereiche für Kraft, Ausdauer und Mobility",
            "Workout- und Coaching-Sprachräume",
        ],
        "roles": [
            role("sportler", "Sportler", "🏅", "#16A34A", "trusted"),
            role("trainer", "Trainer", "🧑‍🏫", "#15803D", "helper"),
            role("ernaehrungscoach", "Ernaehrungscoach", "🥗", "#65A30D", "trusted", hoist=False),
            role("challenge_team", "Challenge Team", "🏆", "#CA8A04", "helper"),
        ],
        "categories": [
            gate_category(),
            info_category(ch("wochenplan", "📅", topic="Die Trainingswoche")),
            cat("training", "🏋️", "public", [
                ch("trainingsplaene", "🗒️", "forum", topic="Pläne und Routinen"),
                ch("krafttraining", "🏋️", topic="Kraft und Muskeln"),
                ch("ausdauer", "🏃", topic="Laufen, Rad, Schwimmen"),
                ch("mobilitaet", "🧘", topic="Beweglichkeit und Yoga"),
                ch("formcheck", "📹", topic="Video zur Technikbewertung", mode="media"),
                ch("fortschritt", "📈", topic="Vorher-Nachher und Messwerte", mode="media", reactions=["⭐"]),
                ch("erfolge", "🎉", topic="Persönliche Bestleistungen", reactions=["🎉"]),
            ]),
            cat("ernaehrung", "🥗", "public", [
                ch("rezepte", "🍽️", topic="Rezepte für Training und Alltag"),
                ch("mahlzeiten-planung", "📋", topic="Wochenpläne und Mealprep"),
                ch("supplemente", "💊", topic="Sinn und Unsinn von Supplementen"),
                ch("trinkprotokoll", "💧", topic="Wasser und Elektrolyte"),
            ]),
            cat("challenges", "🏆", "public", [
                ch("monats-challenge", "🎯", "news", topic="Die aktuelle Challenge", visibility="readonly", mode="announce"),
                ch("anmeldung", "📝", topic="Zur Challenge anmelden"),
                ch("team-challenges", "👥", topic="Gemeinsam an den Start"),
                ch("ergebnisse", "📊", topic="Wochenergebnisse", visibility="readonly", mode="announce"),
            ]),
            cat("sportarten", "⚽", "public", [
                ch("laufen", "🏃", topic="Laufrunden und Marathons"),
                ch("radfahren", "🚴", topic="Rennrad und Mountainbike"),
                ch("schwimmen", "🏊", topic="Bahn ziehen"),
                ch("mannschaftssport", "⚽", topic="Fußball, Volleyball und mehr"),
                ch("kampfsport", "🥋", topic="Boxen, Judo, BJJ"),
                ch("klettern", "🧗", topic="Halle und Fels"),
            ]),
            voice_category("trainings-raeume", "🔊", [
                ch("trainings-talk", "🎧", "voice"),
                ch("workout-raum", "💪", "voice", user_limit=6),
                ch("gruppen-workout", "🏋️", "voice", user_limit=12),
                ch("coaching-raum", "🧑‍🏫", "voice", user_limit=4),
                ch("pausen-talk", "☕", "voice", user_limit=10),
            ]),
            hilfe_category(),
            sprachen_category(),
            sprach_talks_category(),
            team_category(),
            leitung_category(),
            logs_category(),
        ],
    }


def pets() -> dict[str, Any]:
    return {
        "key": "pets",
        "name": "Haustiere & Tierwelt",
        "emoji": "🐾",
        "tagline": "Hunde, Katzen, Aquaristik und ein Herz für Tiere",
        "premium": True,
        "accent": "#F97316",
        "description": (
            "Ein Zuhause für Tierfreunde: eigene Kanäle für Hunde, Katzen, "
            "Kleintiere, Vögel, Aquaristik und Pferde, dazu Gesundheit, "
            "Ernährung und Erziehung. Fotowettbewerbe, Gassi-Treffen, "
            "Vermittlung und ein Bereich für den Tierschutz machen den "
            "Server rund."
        ),
        "highlights": [
            "Eigene Kanäle für acht Tiergruppen",
            "Fotowettbewerbe mit Community-Abstimmung",
            "Vermittlung und Tierschutz mit eigenen Kanälen",
            "Beratungs- und Züchter-Sprachräume",
        ],
        "roles": [
            role("hundefreund", "Hundefreund", "🐶", "#F97316", "member", hoist=False),
            role("katzenfreund", "Katzenfreund", "🐱", "#EA580C", "member", hoist=False),
            role("aquarist", "Aquarist", "🐠", "#0EA5E9", "trusted", hoist=False),
            role("tierberater", "Tierberater", "🩺", "#16A34A", "helper"),
        ],
        "categories": [
            gate_category(),
            info_category(ch("tier-news", "🆕", topic="Neuigkeiten aus der Tierwelt", mode="announce")),
            cat("tiere", "🐾", "public", [
                ch("haustiere", "🐾", topic="Zeig dein Tier", mode="media", reactions=["❤️"]),
                ch("hunde", "🐶", topic="Alles rund um den Hund"),
                ch("katzen", "🐱", topic="Alles rund um die Katze"),
                ch("kleintiere", "🐹", topic="Kaninchen, Hamster und Co"),
                ch("voegel", "🦜", topic="Papageien und Ziervögel"),
                ch("aquaristik", "🐠", topic="Aquarium und Teich"),
                ch("reptilien", "🦎", topic="Terraristik"),
                ch("pferde", "🐴", topic="Pferd und Reiten"),
            ]),
            cat("gesundheit", "🩺", "public", [
                ch("gesundheit", "💉", topic="Gesundheit und Vorsorge"),
                ch("ernaehrung", "🍖", topic="Futter und Leckerli"),
                ch("erziehung", "🎓", topic="Erziehung und Training"),
                ch("tierarzt-fragen", "🩺", topic="Fragen an Erfahrene"),
                ch("versicherung", "🛡️", topic="Tierkrankenversicherung"),
            ]),
            cat("foto-studio", "📸", "public", [
                ch("tierfotos", "📸", topic="Deine schönsten Tierfotos", mode="media", reactions=["⭐"]),
                ch("video-des-tages", "🎬", topic="Lustige und süße Clips", mode="media"),
                ch("abstimmung", "📊", topic="Wer hat das schönste Foto?", reactions=["👍", "👎"]),
            ]),
            cat("treffen", "🎪", "public", [
                ch("gassi-treffen", "🐕", topic="Gemeinsame Runden drehen"),
                ch("tier-events", "🎪", topic="Messen und Veranstaltungen"),
                ch("vermittlung", "🏠", topic="Tiere suchen ein Zuhause"),
                ch("tierschutz", "🫶", topic="Helfen und Spenden"),
                ch("vermisst-gefunden", "🔎", topic="Vermisste Tiere melden"),
            ]),
            voice_category("tier-talks", "🔊", [
                ch("haustier-talk", "🎙️", "voice"),
                ch("beratungs-raum", "🩺", "voice", user_limit=4),
                ch("zuechter-talk", "🐾", "voice", user_limit=8),
                ch("event-talk", "🎪", "voice", user_limit=20),
                ch("quatsch-raum", "☕", "voice", user_limit=10),
            ]),
            hilfe_category(),
            sprachen_category(),
            sprach_talks_category(),
            team_category(),
            leitung_category(),
            logs_category(),
        ],
    }


def food() -> dict[str, Any]:
    return {
        "key": "food",
        "name": "Kochen & Genuss",
        "emoji": "🍳",
        "tagline": "Rezepte, Backabende und Koch-Duelle",
        "premium": True,
        "accent": "#EF4444",
        "description": (
            "Für alle, die gerne kochen, backen und genießen: Rezepte als "
            "Threads, getrennte Kanäle für Backen, Grillen, Desserts und "
            "Getränke, Koch-Duelle mit Abstimmung, eine Foto-Galerie für "
            "gelungene Gerichte — und gemeinsame Koch- und Backabende in "
            "den Sprachräumen."
        ),
        "highlights": [
            "Koch-Duelle mit Abstimmung und Siegerehrung",
            "Foto-Galerie für gelungene Gerichte",
            "Eigene Bereiche für Backen, Grillen und Getränke",
            "Gemeinsame Koch- und Backabende per Voice",
        ],
        "roles": [
            role("hobbykoch", "Hobbykoch", "👨‍🍳", "#EF4444", "trusted"),
            role("backfee", "Backfee", "🧁", "#EC4899", "trusted", hoist=False),
            role("grillmeister", "Grillmeister", "🥩", "#EA580C", "trusted", hoist=False),
            role("kuechenchef", "Kuechenchef", "👩‍🍳", "#B91C1C", "helper"),
        ],
        "categories": [
            gate_category(),
            info_category(ch("rezept-der-woche", "⭐", topic="Das Rezept der Woche", mode="announce")),
            cat("kueche", "🍳", "public", [
                ch("rezepte", "📖", topic="Rezepte teilen", mode="threads"),
                ch("backen", "🧁", topic="Kuchen, Brot und Co"),
                ch("grillen", "🔥", topic="Feuer und Rauch"),
                ch("desserts", "🍰", topic="Süßes zum Schluss"),
                ch("getraenke", "🍹", topic="Cocktails und Co"),
                ch("fruehstueck", "🍳", topic="Der beste Start in den Tag"),
            ]),
            cat("koch-duelle", "🏆", "public", [
                ch("themen-wochen", "🎯", "news", topic="Das aktuelle Thema", visibility="readonly", mode="announce"),
                ch("abstimmung", "📊", topic="Wer kocht am besten?", reactions=["👍", "👎"]),
                ch("ergebnisse", "🎉", topic="Gewinner und Rezepte", visibility="readonly", mode="announce"),
            ]),
            cat("genuss-fotos", "📸", "public", [
                ch("gerichte", "🍽️", topic="Zeig dein Ergebnis", mode="media", reactions=["⭐"]),
                ch("fail-des-tages", "😅", topic="Wenn es nicht klappt", mode="media"),
                ch("restaurant-tipps", "🍴", topic="Wo schmeckt es?"),
                ch("einkaufstipps", "🛒", topic="Zutaten und Märkte"),
            ]),
            cat("ernaehrung", "🥗", "public", [
                ch("gesund-kochen", "🥗", topic="Leicht und ausgewogen"),
                ch("vegetarisch", "🌱", topic="Ohne Fleisch"),
                ch("vegan", "🥦", topic="Pflanzlich unterwegs"),
                ch("allergien", "⚠️", topic="Unverträglichkeiten und Austausch"),
            ]),
            voice_category("koch-talks", "🔊", [
                ch("koch-talk", "🎙️", "voice"),
                ch("gemeinsam-kochen", "🍲", "voice", user_limit=8),
                ch("back-abend", "🧁", "voice", user_limit=8),
                ch("grill-abend", "🔥", "voice", user_limit=12),
                ch("kaffeeklatsch", "☕", "voice", user_limit=10),
            ]),
            hilfe_category(),
            sprachen_category(),
            sprach_talks_category(),
            team_category(),
            leitung_category(),
            logs_category(),
        ],
    }


def travel() -> dict[str, Any]:
    return {
        "key": "travel",
        "name": "Reisen & Abenteuer",
        "emoji": "🧳",
        "tagline": "Reiseberichte, Planung und Mitreisende",
        "premium": True,
        "accent": "#0EA5E9",
        "description": (
            "Für alle mit Fernweh: ein Kanal pro Kontinent, Reiseberichte "
            "mit Fotos und Videos, eine komplette Planungsabteilung von der "
            "Packliste bis zum Visum, Mitreisendensuche und Stammtische. "
            "Dazu eine Bühne für Reiseberichte und Räume für gemeinsame "
            "Planung."
        ),
        "highlights": [
            "Reiseberichte mit Fotos, Videos und Bewertungen",
            "Planung von der Packliste bis zum Visum",
            "Mitreisendensuche und Gruppenreisen",
            "Bühne für Reiseberichte und Planungsräume",
        ],
        "roles": [
            role("weltenbummler", "Weltenbummler", "🌍", "#0EA5E9", "trusted"),
            role("reiseleiter", "Reiseleiter", "🧭", "#0284C7", "helper"),
            role("fotograf", "Fotograf", "📷", "#7C3AED", "trusted", hoist=False),
        ],
        "categories": [
            gate_category(),
            info_category(ch("reise-planer", "📅", topic="Wohin geht es als Nächstes?")),
            cat("laender", "🗺️", "public", [
                ch("deutschland", "🇩🇪", topic="Reisen in Deutschland"),
                ch("europa", "🇪🇺", topic="Kurzurlaub in Europa"),
                ch("asien", "🌏", topic="Fernost und Südostasien"),
                ch("amerika", "🌎", topic="Nord- und Südamerika"),
                ch("afrika", "🌍", topic="Safari und Wüste"),
                ch("ozeanien", "🏝️", topic="Australien und die Südsee"),
            ]),
            cat("reiseberichte", "📖", "public", [
                ch("berichte", "📖", topic="Deine Reisegeschichten", mode="threads"),
                ch("fotos", "📸", topic="Unterwegs geknipst", mode="media", reactions=["⭐"]),
                ch("videos", "🎬", topic="Reisevideos", mode="media"),
                ch("bewertungen", "⭐", topic="Hotels und Touren bewerten"),
            ]),
            cat("planung", "🎒", "public", [
                ch("packlisten", "🎒", topic="Was kommt mit?"),
                ch("budget", "💰", topic="Kosten und Sparen"),
                ch("unterkuenfte", "🏨", topic="Hotels, Hostels, Camping"),
                ch("transport", "🚆", topic="Bahn, Flug, Auto"),
                ch("versicherungen", "🛡️", topic="Was zahlt wer?"),
                ch("visa-und-papiere", "🛂", topic="Einreise und Formalitäten"),
            ]),
            cat("reise-partner", "🤝", "public", [
                ch("mitreisende-gesucht", "🔎", topic="Wer kommt mit?", mode="threads"),
                ch("gruppenreisen", "👥", topic="Gemeinsam unterwegs"),
                ch("treffen", "🎪", topic="Stammtische und Events"),
                ch("souvenirs", "🎁", topic="Mitbringsel zeigen", mode="media"),
            ]),
            voice_category("reise-talks", "🔊", [
                ch("reise-talk", "🎙️", "voice"),
                ch("planungs-raum", "🗺️", "voice", user_limit=6),
                ch("foto-talk", "📷", "voice", user_limit=6),
                ch("reisebericht-buehne", "🎤", "stage"),
                ch("abend-talk", "🌙", "voice", user_limit=10),
            ]),
            hilfe_category(),
            sprachen_category(),
            sprach_talks_category(),
            team_category(),
            leitung_category(),
            logs_category(),
        ],
    }


def art() -> dict[str, Any]:
    return {
        "key": "art",
        "name": "Kunst & Kreativ",
        "emoji": "🎨",
        "tagline": "Werke zeigen, Feedback holen, gemeinsam zeichnen",
        "premium": True,
        "accent": "#EC4899",
        "description": (
            "Ein Atelier für alle: Kunstwerke, Skizzen, digitale Kunst, "
            "Fotografie und Handwerk in getrennten Kanälen, strukturiertes "
            "Feedback per Thread, Themen-Wettbewerbe mit Abstimmung, eine "
            "virtuelle Galerie und gemeinsame Zeichenabende in den "
            "Sprachräumen."
        ),
        "highlights": [
            "Getrennte Kanäle für jede Kunstform",
            "Feedback-Threads und Tutorials",
            "Themen-Wettbewerbe mit Community-Abstimmung",
            "Virtuelle Galerie und gemeinsame Zeichenabende",
        ],
        "roles": [
            role("kuenstler", "Kuenstler", "🎨", "#EC4899", "trusted"),
            role("illustrator", "Illustrator", "🖌️", "#DB2777", "trusted", hoist=False),
            role("fotograf_k", "Fotograf", "📷", "#8B5CF6", "trusted", hoist=False),
            role("kurator", "Kurator", "🏛️", "#F59E0B", "helper"),
        ],
        "categories": [
            gate_category(),
            info_category(ch("ausstellungen", "🖼️", topic="Aktuelle Ausstellungen", mode="announce")),
            cat("werkstatt", "🎨", "public", [
                ch("kunstwerke", "🖼️", topic="Zeig deine Werke", slowmode=120, mode="media", reactions=["⭐"]),
                ch("skizzen", "✏️", topic="Schnelle Skizzen", mode="media"),
                ch("digitale-kunst", "💻", topic="Zeichnen am Rechner", mode="media"),
                ch("fotografie", "📷", topic="Bilder mit der Kamera", mode="media"),
                ch("handwerk", "🧵", topic="Nähen, Töpfern, Holz"),
                ch("basteln", "✂️", topic="Bastelideen und Anleitungen"),
            ]),
            cat("rueckmeldung", "💬", "public", [
                ch("kritik", "💡", topic="Konstruktive Rückmeldung", mode="threads"),
                ch("techniken", "🛠️", topic="Material und Methoden"),
                ch("tutorials", "🎓", topic="Schritt für Schritt"),
                ch("auftraege", "💼", topic="Auftragsarbeiten", slowmode=600),
            ]),
            cat("wettbewerbe", "🏆", "public", [
                ch("themen-wettbewerb", "🎯", "news", topic="Das aktuelle Thema", visibility="readonly", mode="announce"),
                ch("abstimmung", "📊", topic="Stimme ab", reactions=["👍", "👎"]),
                ch("gewinner", "🎉", topic="Die Gewinner", visibility="readonly", mode="announce"),
            ]),
            cat("gemeinsam", "👥", "public", [
                ch("gemeinsam-zeichnen", "👥", topic="Zeichenabende planen"),
                ch("kunst-tausch", "🔁", topic="Werke tauschen"),
                ch("galerie", "🖼️", topic="Virtuelle Galerie", visibility="readonly", mode="announce"),
            ]),
            voice_category("atelier-talks", "🔊", [
                ch("atelier-talk", "🎙️", "voice"),
                ch("zeichnen-gemeinsam", "✏️", "voice", user_limit=8),
                ch("kritik-runde", "💬", "voice", user_limit=6),
                ch("podcast-hoeren", "🎧", "voice", user_limit=10),
                ch("chill-ecke", "☕", "voice", user_limit=10),
            ]),
            hilfe_category(),
            sprachen_category(),
            sprach_talks_category(),
            team_category(),
            leitung_category(),
            logs_category(),
        ],
    }


def books() -> dict[str, Any]:
    return {
        "key": "books",
        "name": "Bücher & Geschichten",
        "emoji": "📚",
        "tagline": "Lesekreise, Schreibwerkstatt und ein Zählkanal",
        "premium": True,
        "accent": "#8B5CF6",
        "description": (
            "Ein Wohnzimmer für Leseratten: Kanäle für jedes Genre, "
            "Lesekreise mit festen Gruppen, eine Schreibwerkstatt für "
            "eigene Texte mit strukturierter Rückmeldung, eine "
            "Tauschbörse für Bücher — und ein Zählkanal, der die gelesenen "
            "Seiten hochzählt."
        ),
        "highlights": [
            "Kanäle für jedes Genre — vom Klassiker bis zum Krimi",
            "Lesekreise und Buddy-Reads",
            "Schreibwerkstatt mit Feedback-Threads",
            "Zählkanal für die gelesenen Seiten",
        ],
        "roles": [
            role("leseratte", "Leseratte", "📖", "#8B5CF6", "member", hoist=False),
            role("autor", "Autor", "✍️", "#7C3AED", "trusted"),
            role("lektor", "Lektor", "🔍", "#A78BFA", "trusted", hoist=False),
            role("lesekreis_leitung", "Lesekreis-Leitung", "🧭", "#F59E0B", "helper"),
        ],
        "categories": [
            gate_category(),
            info_category(ch("neuerscheinungen", "🆕", topic="Neu auf dem Markt", mode="announce")),
            cat("buecher", "📚", "public", [
                ch("aktuell-gelesen", "📖", topic="Was liest du gerade?"),
                ch("empfehlungen", "⭐", topic="Empfehlungen", reactions=["⭐"]),
                ch("klassiker", "🏛️", topic="Die großen Werke"),
                ch("sachbuecher", "🧠", topic="Wissen zum Nachlesen"),
                ch("fantasy", "🐉", topic="Fantasy und Sci-Fi"),
                ch("krimis", "🕵️", topic="Krimis und Thriller"),
                ch("romane", "💌", topic="Romane und Liebesgeschichten"),
                ch("seiten-zaehlen", "🔢", topic="Gemeinsam zählen", mode="counting",
                    guide=[
                        "Gemeinsam so weit zählen wie möglich.",
                    ],
                ),
            ]),
            cat("lesekreise", "👥", "public", [
                ch("lesekreis-1", "1️⃣", topic="Lesekreis 1"),
                ch("lesekreis-2", "2️⃣", topic="Lesekreis 2"),
                ch("buddy-read", "👥", topic="Zu zweit lesen"),
                ch("zitate", "💬", topic="Lieblingsstellen teilen"),
                ch("buchverfilmungen", "🎬", topic="Buch trifft Film"),
            ]),
            cat("schreibwerkstatt", "✍️", "public", [
                ch("eigene-texte", "✍️", topic="Zeig deine Texte", slowmode=120),
                ch("rueckmeldungen", "💡", topic="Konstruktive Kritik", mode="threads"),
                ch("schreibtipps", "🎓", topic="Handwerk und Stil"),
                ch("veroeffentlichung", "📣", topic="Der Weg ins Regal"),
            ]),
            cat("buchmarkt", "🏷️", "public", [
                ch("tauschboerse", "🔁", topic="Bücher tauschen"),
                ch("angebote", "💰", topic="Schnäppchen und Rabatte"),
                ch("sammlerausgaben", "🎁", topic="Besondere Ausgaben"),
            ]),
            voice_category("lese-talks", "🔊", [
                ch("lese-talk", "🎙️", "voice"),
                ch("lesekreis-talk", "👥", "voice", user_limit=10),
                ch("schreibstube", "✍️", "voice", user_limit=6),
                ch("vorlese-buehne", "🎤", "stage"),
                ch("stille-lounge", "🤫", "voice", user_limit=10),
            ]),
            hilfe_category(),
            sprachen_category(),
            sprach_talks_category(),
            team_category(),
            leitung_category(),
            logs_category(),
        ],
    }


def movies() -> dict[str, Any]:
    return {
        "key": "movies",
        "name": "Film & Serien",
        "emoji": "🎞️",
        "tagline": "Bewertungen, Theorien und gemeinsame Watch-Partys",
        "premium": True,
        "accent": "#E11D48",
        "description": (
            "Für Cineasten und Serienjunkies: Filme, Serien und Genres in "
            "getrennten Kanälen, eine klar markierte Spoiler-Zone für "
            "Theorien, Watch-Partys mit Planung und Kino-Treffen, dazu "
            "Sprachräume zum gemeinsamen Schauen mit Bühne für Filmabende."
        ),
        "highlights": [
            "Getrennte Kanäle für Filme, Serien und Genres",
            "Spoiler-Zone für Theorien und Fan-Edits",
            "Watch-Partys mit Planung und Kino-Treffen",
            "Filmräume und Bühne für gemeinsame Abende",
        ],
        "roles": [
            role("cineast", "Cineast", "🎬", "#E11D48", "trusted"),
            role("serienjunkie", "Serienjunkie", "📺", "#BE123C", "trusted", hoist=False),
            role("filmteam", "Filmteam", "🎥", "#F59E0B", "helper"),
        ],
        "categories": [
            gate_category(),
            info_category(ch("kinostarts", "🎟️", topic="Was kommt ins Kino?", mode="announce")),
            cat("filme", "🎬", "public", [
                ch("film-news", "📰", "news", topic="Neuigkeiten aus Hollywood", visibility="readonly", mode="announce"),
                ch("trailer", "🎬", topic="Neue Trailer", mode="media"),
                ch("bewertungen", "⭐", topic="Deine Wertung", mode="threads", reactions=["⭐"]),
                ch("klassiker", "🎞️", topic="Filmgeschichte"),
                ch("dokumentationen", "🎥", topic="Dokus und Reportagen"),
            ]),
            cat("serien", "📺", "public", [
                ch("aktuell", "📺", topic="Was schaust du gerade?"),
                ch("bingewatching", "🍿", topic="Staffeln am Stück"),
                ch("serien-news", "🆕", topic="Verlängerungen und Absetzungen", mode="announce"),
                ch("staffel-talk", "🎬", topic="Die aktuelle Staffel"),
            ]),
            cat("genres", "🎭", "public", [
                ch("horror", "👻", topic="Gänsehaut gefällig?"),
                ch("komoedien", "😂", topic="Zum Lachen"),
                ch("science-fiction", "🚀", topic="Zukunft und Weltraum"),
                ch("fantasy-filme", "🐉", topic="Magie und Drachen"),
                ch("thriller", "🔪", topic="Spannung bis zum Schluss"),
            ]),
            cat("spoiler-zone", "⚠️", "public", [
                ch("spoiler-chat", "⚠️", topic="Achtung: Spoiler erlaubt"),
                ch("theorien", "🧠", topic="Wer steckt wirklich dahinter?"),
                ch("fan-edits", "✂️", topic="Eigene Schnitte", mode="media"),
            ]),
            cat("watchpartys", "🍿", "public", [
                ch("watch-party", "🍿", topic="Gemeinsam schauen", mode="media"),
                ch("planung", "📅", topic="Wann schauen wir was?"),
                ch("kinotreffen", "🎟️", topic="Gemeinsam ins Kino"),
            ]),
            voice_category("film-talks", "🔊", [
                ch("film-talk", "🎙️", "voice"),
                ch("watch-raum-1", "🎬", "voice", user_limit=25),
                ch("watch-raum-2", "🎬", "voice", user_limit=25),
                ch("film-buehne", "🎤", "stage"),
                ch("serien-talk", "📺", "voice", user_limit=10),
            ]),
            hilfe_category(),
            sprachen_category(),
            sprach_talks_category(),
            team_category(),
            leitung_category(),
            logs_category(),
        ],
    }


def science() -> dict[str, Any]:
    return {
        "key": "science",
        "name": "Wissenschaft & Technik",
        "emoji": "🔬",
        "tagline": "Diskutieren, experimentieren, verstehen",
        "premium": True,
        "accent": "#06B6D4",
        "description": (
            "Für Neugierige: ein Kanal pro Fachrichtung, eine "
            "Diskussionsrunde mit eingeordneten Studien, Neuigkeiten aus "
            "Forschung und Technik, eine Werkbank für Experimente, "
            "Eigenbauten und 3D-Druck — und Fachvorträge auf der Bühne. "
            "Experimente nur mit Sicherheitshinweis."
        ),
        "highlights": [
            "Kanäle für sechs Fachrichtungen",
            "Studien einordnen statt Schlagzeilen teilen",
            "Werkbank für Experimente, Eigenbau und 3D-Druck",
            "Fachvorträge auf der Bühne",
        ],
        "roles": [
            role("forscher", "Forscher", "🔬", "#06B6D4", "trusted"),
            role("ingenieur", "Ingenieur", "⚙️", "#0891B2", "trusted", hoist=False),
            role("mentor", "Mentor", "🧑‍🏫", "#16A34A", "helper"),
        ],
        "categories": [
            gate_category(),
            info_category(ch("forschungs-news", "📰", topic="Neues aus der Forschung", mode="announce")),
            cat("diskussion", "💬", "public", [
                ch("wissenschafts-talk", "💬", topic="Diskutieren und staunen"),
                ch("studien", "📑", topic="Studien einordnen"),
                ch("kontroversen", "⚖️", topic="Streitfragen mit Anstand", slowmode=30, mode="threads"),
                ch("fragen", "❓", topic="Fragen ohne Scheu"),
            ]),
            cat("faecher", "🔬", "public", [
                ch("physik", "⚛️", topic="Physik"),
                ch("chemie", "🧪", topic="Chemie"),
                ch("biologie", "🧬", topic="Biologie"),
                ch("astronomie", "🔭", topic="Astronomie"),
                ch("mathematik", "➗", topic="Mathematik"),
                ch("informatik", "💻", topic="Informatik"),
            ]),
            cat("technik", "⚙️", "public", [
                ch("gadgets", "📱", topic="Neue Geräte"),
                ch("ki", "🤖", topic="Künstliche Intelligenz"),
                ch("robotik", "🦾", topic="Maschinen, die sich bewegen"),
                ch("raumfahrt", "🚀", topic="Raketen und Missionen"),
                ch("energie", "⚡", topic="Strom, Wärme, Zukunft"),
                ch("umwelt", "🌱", topic="Klima und Ökosysteme"),
            ]),
            cat("werkbank", "🛠️", "public", [
                ch("experimente", "🧫", topic="Selbst ausprobieren",
                    guide=[
                        "Nur mit Sicherheitshinweis und gesundem Menschenverstand.",
                    ],
                ),
                ch("eigenbau", "🛠️", topic="Selbst gebaut", mode="media", reactions=["⭐"]),
                ch("werkzeuge", "🔧", topic="Geräte und Hilfsmittel"),
                ch("3d-druck", "🖨️", topic="Drucken und Konstruieren"),
                ch("projekte", "📦", topic="Gemeinsame Projekte"),
            ]),
            voice_category("labor-talks", "🔊", [
                ch("labor-talk", "🎙️", "voice"),
                ch("experiment-raum", "🧪", "voice", user_limit=8),
                ch("beobachtungs-raum", "🔭", "voice", user_limit=8),
                ch("lerngruppe", "👥", "voice", user_limit=8),
                ch("fachvortrag", "🎤", "stage"),
            ]),
            hilfe_category(),
            sprachen_category(),
            sprach_talks_category(),
            team_category(),
            leitung_category(),
            logs_category(),
        ],
    }


def finance() -> dict[str, Any]:
    return {
        "key": "finance",
        "name": "Finanzen & Krypto",
        "emoji": "📈",
        "tagline": "Märkte verstehen — ohne Anlageberatung",
        "premium": True,
        "accent": "#10B981",
        "description": (
            "Ein Ort zum Lernen und Diskutieren: Kanäle für Aktien, ETFs, "
            "Krypto, Anleihen, Immobilien und Altersvorsorge, Analysen und "
            "Strategien im Austausch, ein Bildungsbereich vom Glossar bis "
            "zum Podcast — und ein klarer Grundsatz: hier wird diskutiert, "
            "nicht empfohlen. Keine Anlageberatung."
        ),
        "highlights": [
            "Kanäle für sechs Anlageklassen",
            "Bildungsbereich vom Glossar bis zum Podcast",
            "Analysen und Strategien im Austausch",
            "Grundsatz: diskutieren statt empfehlen",
        ],
        "roles": [
            role("investor", "Investor", "📊", "#10B981", "trusted"),
            role("trader", "Trader", "💹", "#059669", "trusted", hoist=False),
            role("analyst", "Analyst", "🔍", "#0EA5E9", "trusted", hoist=False),
            role("berater", "Berater", "🧑‍💼", "#7C3AED", "helper"),
        ],
        "categories": [
            gate_category(),
            info_category(ch("markt-news", "📰", topic="Was bewegt die Märkte?", mode="announce")),
            cat("finanzen", "📈", "public", [
                ch("aktien", "📈", topic="Aktien und Unternehmen"),
                ch("etfs", "🧺", topic="ETFs und Fonds"),
                ch("krypto", "🪙", topic="Bitcoin und Co"),
                ch("anleihen", "📜", topic="Anleihen und Zinsen"),
                ch("immobilien", "🏠", topic="Stein auf Stein"),
                ch("altersvorsorge", "🏦", topic="Rente und Vorsorge"),
            ]),
            cat("austausch", "💬", "public", [
                ch("analysen", "🔍", topic="Charts und Auswertungen",
                    guide=[
                        "Keine Anlageberatung — hier wird diskutiert, nicht empfohlen.",
                    ],
                ),
                ch("strategien", "🧠", topic="Ansätze vergleichen", mode="threads"),
                ch("risiko", "⚠️", topic="Verluste und Fehler"),
                ch("steuern", "🧾", topic="Was der Staat will"),
                ch("anfaengerfragen", "❓", topic="Keine Frage ist dumm"),
            ]),
            cat("bildung", "🎓", "public", [
                ch("grundlagen", "🎓", topic="Von null auf verstehen"),
                ch("glossar", "📖", topic="Begriffe kurz erklärt"),
                ch("buchempfehlungen", "📚", topic="Lesen lohnt sich"),
                ch("podcasts", "🎧", topic="Hören statt lesen"),
                ch("kurse", "🏫", topic="Seminare und Kurse"),
            ]),
            cat("news", "📰", "public", [
                ch("nachrichten", "📰", "news", topic="Wirtschaftsnachrichten", visibility="readonly", mode="announce"),
                ch("kalender", "📅", topic="Termine und Zahlen", visibility="readonly", mode="announce"),
                ch("krypto-news", "🪙", topic="Neues aus der Kryptowelt", visibility="readonly", mode="announce"),
            ]),
            voice_category("markt-talks", "🔊", [
                ch("markt-talk", "🎙️", "voice"),
                ch("analyse-raum", "📊", "voice", user_limit=10),
                ch("lern-raum", "🎓", "voice", user_limit=10),
                ch("investoren-talk", "💼", "voice", user_limit=10),
                ch("vortrag", "🎤", "stage"),
            ]),
            hilfe_category(),
            sprachen_category(),
            sprach_talks_category(),
            team_category(),
            leitung_category(),
            logs_category(),
        ],
    }


def collect() -> dict[str, Any]:
    return {
        "key": "collect",
        "name": "Sammeln & Tauschen",
        "emoji": "🃏",
        "tagline": "Karten, Münzen, Modelle — sammeln mit System",
        "premium": True,
        "accent": "#F59E0B",
        "description": (
            "Für Sammlerinnen und Sammler: eigene Kanäle für "
            "Trading-Cards, Münzen, Briefmarken, Modellbau, Figuren, "
            "Comics und Schallplatten, eine Tauschbörse mit Bewertungen, "
            "Echtheitsprüfung per Foto, laufende Auktionen und ein "
            "Sprachbereich für Tauschabende und Vorstellungsrunden."
        ),
        "highlights": [
            "Kanäle für sieben Sammelgebiete",
            "Tauschbörse mit Händler-Bewertungen",
            "Echtheitsprüfung und Zustandsbewertung",
            "Auktionen mit Geboten und Ergebnissen",
        ],
        "roles": [
            role("sammler", "Sammler", "🃏", "#F59E0B", "trusted"),
            role("haendler", "Haendler", "🏷️", "#D97706", "trusted", hoist=False),
            role("pruefer", "Pruefer", "🔍", "#0EA5E9", "helper"),
            role("auktions_team", "Auktions-Team", "🔨", "#DC2626", "helper"),
        ],
        "categories": [
            gate_category(),
            info_category(ch("messetermine", "📅", topic="Börsen und Messen", mode="announce")),
            cat("sammelgebiete", "🃏", "public", [
                ch("trading-cards", "🃏", topic="Karten aller Art"),
                ch("muenzen", "🪙", topic="Münzen und Medaillen"),
                ch("briefmarken", "✉️", topic="Philatelie"),
                ch("modellbau", "🚂", topic="Modelle und Dioramen"),
                ch("figuren", "🧸", topic="Figuren und Spielzeug"),
                ch("comics", "💥", topic="Comics und Magazine"),
                ch("schallplatten", "💿", topic="Vinyl und CDs"),
            ]),
            cat("tausch", "🔁", "public", [
                ch("tauschboerse", "🔁", topic="Tauschen und handeln", mode="threads"),
                ch("suche", "🔎", topic="Ich suche …"),
                ch("biete", "🎁", topic="Ich biete …"),
                ch("bewertungen", "⭐", topic="Erfahrungen mit Händlern"),
                ch("haendler-verzeichnis", "📇", topic="Vertrauenswürdige Quellen"),
            ]),
            cat("pruefung", "🔍", "public", [
                ch("echtheits-pruefung", "🔍", topic="Echt oder nicht?", mode="threads",
                    guide=[
                        (
                            "Zeig gute Fotos von vorne und hinten — je mehr "
                            "Details, desto besser die Einschätzung."
                        ),
                    ],
                ),
                ch("zustands-bewertung", "📏", topic="Wie gut ist der Zustand?"),
                ch("reparatur", "🛠️", topic="Kleben, restaurieren, retten"),
                ch("lagerung", "📦", topic="Richtig aufbewahren"),
            ]),
            cat("auktionen", "🔨", "public", [
                ch("auktionen", "🔨", "news", topic="Laufende Auktionen", visibility="readonly", mode="announce"),
                ch("gebote", "💰", topic="Gebote abgeben"),
                ch("ergebnisse", "🎉", topic="Zuschläge und Preise", visibility="readonly", mode="announce"),
            ]),
            voice_category("sammler-talks", "🔊", [
                ch("sammlertalk", "🎙️", "voice"),
                ch("tausch-talk", "🔁", "voice", user_limit=8),
                ch("bewertungs-raum", "🔍", "voice", user_limit=4),
                ch("vorstell-runde", "🎁", "voice", user_limit=10),
                ch("spielrunde", "🎲", "voice", user_limit=8),
            ]),
            hilfe_category(),
            sprachen_category(),
            sprach_talks_category(),
            team_category(),
            leitung_category(),
            logs_category(),
        ],
    }


TEMPLATES = [
    community,
    rp,
    social,
    gaming,
    anime,
    business,
    study,
    creator,
    support,
    esports,
    music,
    dev,
    minimal,
    clan,
    fitness,
    pets,
    food,
    travel,
    art,
    books,
    movies,
    science,
    finance,
    collect,
]


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    from core.schema import Template, TemplateError

    total_channels = 0
    print(f"{'Template':<22} {'Typ':<9} {'Kat.':>5} {'Kanäle':>7} {'Voice':>6} {'Rollen':>7}")
    print("─" * 62)

    for factory in TEMPLATES:
        data = factory()
        path = OUT_DIR / f"{data['key']}.json"
        path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

        try:
            template = Template.parse(data, source=path.name)
        except TemplateError as exc:
            print(f"\n  ❌  {exc}\n", file=sys.stderr)
            return 1

        total_channels += template.channel_count
        print(
            f"{template.name:<22} "
            f"{'premium' if template.premium else 'free':<9} "
            f"{template.category_count:>5} "
            f"{template.channel_count:>7} "
            f"{template.voice_count:>6} "
            f"{len(template.roles):>7}"
        )

    print("─" * 62)
    print(f"{len(TEMPLATES)} Templates · {total_channels} Kanäle insgesamt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
