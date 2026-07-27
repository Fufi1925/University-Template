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
        "premium": False,
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
                ch("support", "🎫", "forum", topic="Tickets und Hilfe", widget="ticket"),
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
                ch("support", "🎫", "forum", topic="Hilfe vom Team", widget="ticket"),
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
                ch("tickets", "🎫", "forum", topic="Erstelle hier dein Ticket", widget="ticket"),
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
