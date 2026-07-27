#!/usr/bin/env python3
"""Generates the JSON files in ``templates/``.

The templates themselves are plain data — this script only exists so the shared
building blocks (language channels, log categories, staff areas) stay identical
across every template instead of drifting apart through copy-paste.

Run after editing:  ``python tools/generate_templates.py``
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
# Helpers
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
# Language blocks — the "Social Logs" idea, scaled up
# --------------------------------------------------------------------------- #

# (flag, label, native topic)
LANGUAGES: list[tuple[str, str, str]] = [
    ("🇩🇪", "deutsch", "Deutschsprachiger Chat"),
    ("🇬🇧", "english", "English speaking chat"),
    ("🇫🇷", "francais", "Discussion en français"),
    ("🇪🇸", "espanol", "Chat en español"),
    ("🇮🇹", "italiano", "Chat in italiano"),
    ("🇵🇹", "portugues", "Conversa em português"),
    ("🇧🇷", "brasil", "Bate-papo brasileiro"),
    ("🇳🇱", "nederlands", "Nederlandse chat"),
    ("🇵🇱", "polski", "Czat po polsku"),
    ("🇷🇺", "русский", "Русскоязычный чат"),
    ("🇺🇦", "українська", "Українськомовний чат"),
    ("🇹🇷", "turkce", "Türkçe sohbet"),
    ("🇸🇪", "svenska", "Svensk chatt"),
    ("🇳🇴", "norsk", "Norsk chat"),
    ("🇩🇰", "dansk", "Dansk chat"),
    ("🇫🇮", "suomi", "Suomenkielinen chat"),
    ("🇨🇿", "cestina", "Český chat"),
    ("🇸🇰", "slovencina", "Slovenský chat"),
    ("🇭🇺", "magyar", "Magyar csevegés"),
    ("🇷🇴", "romana", "Chat în română"),
    ("🇧🇬", "български", "Български чат"),
    ("🇬🇷", "ελληνικά", "Ελληνικό chat"),
    ("🇷🇸", "srpski", "Srpski čet"),
    ("🇭🇷", "hrvatski", "Hrvatski chat"),
    ("🇱🇹", "lietuviu", "Lietuviškas pokalbis"),
    ("🇯🇵", "日本語", "日本語チャット"),
    ("🇰🇷", "한국어", "한국어 채팅"),
    ("🇨🇳", "中文", "中文聊天"),
    ("🇹🇭", "ไทย", "แชทภาษาไทย"),
    ("🇻🇳", "tieng-viet", "Trò chuyện tiếng Việt"),
    ("🇮🇩", "indonesia", "Obrolan bahasa Indonesia"),
    ("🇵🇭", "filipino", "Filipino chat"),
    ("🇮🇳", "हिन्दी", "हिंदी चैट"),
    ("🇸🇦", "العربية", "دردشة عربية"),
    ("🇮🇱", "עברית", "צ׳אט בעברית"),
    ("🇮🇷", "فارسی", "گفتگوی فارسی"),
]


def language_text(count: int, *, slowmode: int = 3) -> list[dict[str, Any]]:
    """Text channels, one per language."""

    return [
        ch(label, flag, topic=topic, slowmode=slowmode)
        for flag, label, topic in LANGUAGES[:count]
    ] + [ch("other-languages", "🌐", topic="Every other language is welcome here")]


def language_voice(count: int, *, user_limit: int = 12) -> list[dict[str, Any]]:
    """Voice rooms, one per language."""

    return [
        ch(f"{label}-voice", flag, "voice", user_limit=user_limit)
        for flag, label, _ in LANGUAGES[:count]
    ]


def language_category(text_count: int, voice_count: int) -> list[dict[str, Any]]:
    blocks = [
        cat("multi language", "🌍", "public", language_text(text_count)),
    ]
    if voice_count:
        blocks.append(
            cat("language voice", "🗣️", "public", language_voice(voice_count))
        )
    return blocks


# --------------------------------------------------------------------------- #
# Reusable categories
# --------------------------------------------------------------------------- #

def gate_category() -> dict[str, Any]:
    """The only thing an unverified member sees."""

    return cat(
        "willkommen", "🚪", "gate",
        [
            ch("welcome", "👋", topic="Willkommen! Verifiziere dich, um den Server zu sehen.", visibility="readonly"),
            ch("verify", "✅", topic="Hier verifizieren"),
            ch("rules", "📜", topic="Serverregeln", visibility="readonly"),
            ch("faq", "❔", topic="Häufige Fragen", visibility="readonly"),
        ],
    )


def info_category(extra: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return cat(
        "information", "📌", "readonly",
        [
            ch("announcements", "📢", "news", topic="Wichtige Ankündigungen"),
            ch("updates", "🆕", topic="Server- und Bot-Updates"),
            ch("roles", "🏷️", topic="Selbstvergabe von Rollen"),
            ch("partners", "🤝", topic="Unsere Partner"),
            ch("giveaways", "🎁", topic="Aktuelle Gewinnspiele"),
            *(extra or []),
        ],
    )


def staff_category(name: str = "team") -> dict[str, Any]:
    return cat(
        name, "🛡️", "staff",
        [
            ch("team-chat", "💼", topic="Interner Teamchat"),
            ch("team-announcements", "📣", topic="Ankündigungen fürs Team"),
            ch("tasks", "📋", topic="Aufgaben und Zuständigkeiten"),
            ch("applications", "🧾", topic="Eingehende Bewerbungen"),
            ch("reports", "🚨", topic="Gemeldete Vorfälle"),
            ch("team-voice", "🎙️", "voice", user_limit=15),
            ch("meeting-room", "🪑", "voice", user_limit=25),
        ],
    )


def leadership_category() -> dict[str, Any]:
    return cat(
        "leitung", "👑", "leadership",
        [
            ch("leadership-chat", "🏛️", topic="Nur für die Serverleitung"),
            ch("strategy", "🗺️", topic="Planung und Ausrichtung"),
            ch("personnel", "🧑‍💼", topic="Personalthemen"),
            ch("leadership-voice", "🔐", "voice", user_limit=10),
        ],
    )


def logs_category() -> dict[str, Any]:
    """The full log suite — this is the 'Social Logs' pattern expanded."""

    return cat(
        "logs", "📜", "staff",
        [
            ch("mod-logs", "🔨", topic="Moderationsaktionen"),
            ch("member-logs", "👥", topic="Beitritte und Austritte"),
            ch("message-logs", "✏️", topic="Bearbeitete und gelöschte Nachrichten"),
            ch("voice-logs", "🔊", topic="Voice-Aktivität"),
            ch("role-logs", "🏷️", topic="Rollenänderungen"),
            ch("channel-logs", "🗂️", topic="Kanaländerungen"),
            ch("social-logs", "📱", topic="Social-Media-Feeds und Erwähnungen"),
            ch("bot-logs", "🤖", topic="Bot-Ereignisse"),
            ch("invite-logs", "🔗", topic="Einladungs-Tracking"),
            ch("server-logs", "🗃️", topic="Alles Übrige"),
        ],
    )


def voice_lounge(count: int = 8, *, prefix: str = "lounge") -> dict[str, Any]:
    rooms = [
        ch("general-voice", "🎙️", "voice", user_limit=0),
        ch("chill", "☕", "voice", user_limit=10),
        ch("music", "🎶", "voice", user_limit=0),
        ch("duo", "👥", "voice", user_limit=2),
        ch("trio", "👨‍👩‍👦", "voice", user_limit=3),
        ch("squad", "🛡️", "voice", user_limit=5),
        ch("study", "📚", "voice", user_limit=0),
        ch("stream-room", "📺", "voice", user_limit=20),
        ch("late-night", "🌙", "voice", user_limit=12),
        ch("afk", "💤", "voice", user_limit=0),
    ]
    return cat(prefix, "🔊", "public", rooms[:count] + [rooms[-1]])


def vip_category() -> dict[str, Any]:
    return cat(
        "vip lounge", "💎", "vip",
        [
            ch("vip-chat", "💬", topic="Exklusiv für VIPs und Booster"),
            ch("vip-perks", "🎁", topic="Deine Vorteile", visibility="readonly"),
            ch("vip-wishes", "🌠", topic="Wünsche und Feedback"),
            ch("vip-voice", "🥂", "voice", user_limit=15),
        ],
    )


def social_category() -> dict[str, Any]:
    return cat(
        "social", "📱", "public",
        [
            ch("instagram", "📸", topic="Instagram-Posts"),
            ch("tiktok", "🎵", topic="TikTok-Clips"),
            ch("youtube", "▶️", topic="YouTube-Uploads"),
            ch("twitch", "🟣", topic="Twitch-Streams"),
            ch("x-twitter", "🐦", topic="Posts von X"),
            ch("self-promo", "📣", topic="Eigene Projekte vorstellen", slowmode=300),
        ],
    )


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
            "Ein vollständig strukturierter Community-Server: klare Eingangsschleuse, "
            "lebendige Chatbereiche, 37 Sprachkanäle, großzügige Voice-Zone und ein "
            "abgeschirmter Team- und Log-Bereich. Ideal, wenn du ohne Umwege einen "
            "professionellen Server willst."
        ),
        "highlights": [
            "Verify-Schleuse — Neulinge sehen erst nach der Freigabe den ganzen Server",
            "37 Sprachkanäle plus 12 Sprach-Voice-Räume",
            "Vollständige Log-Suite inklusive Social- und Voice-Logs",
            "Abgestufte Team-, Leitungs- und VIP-Bereiche",
        ],
        "roles": [
            role("creator", "Content Creator", "🎨", "#F97316", "trusted"),
            role("event_team", "Event Team", "🎉", "#EAB308", "helper"),
            role("designer", "Designer", "🖌️", "#EC4899", "trusted", hoist=False),
        ],
        "categories": [
            gate_category(),
            info_category(),
            cat("community", "💬", "public", [
                ch("general", "💭", topic="Der Hauptchat", slowmode=3),
                ch("small-talk", "🫧", topic="Kurz und locker"),
                ch("media", "🖼️", topic="Bilder, Clips, Fundstücke"),
                ch("memes", "😂", topic="Nur Memes"),
                ch("pets", "🐾", topic="Deine Haustiere"),
                ch("food", "🍕", topic="Essen und Rezepte"),
                ch("music-share", "🎧", topic="Was hörst du gerade?"),
                ch("off-topic", "🌙", topic="Alles, was sonst nirgends passt"),
                ch("bot-commands", "🤖", topic="Bot-Befehle gehören hierher"),
                ch("counting", "🔢", topic="Gemeinsam zählen"),
            ]),
            *language_category(36, 12),
            voice_lounge(9),
            cat("events", "🎉", "public", [
                ch("event-announcements", "📅", "news", topic="Kommende Events", visibility="readonly"),
                ch("event-signup", "🎟️", topic="Anmeldungen"),
                ch("event-chat", "🎊", topic="Rund ums Event"),
                ch("event-photos", "📷", topic="Rückblicke"),
                ch("event-stage", "🎤", "stage"),
                ch("event-voice", "🎪", "voice", user_limit=50),
            ]),
            cat("creative", "🎨", "public", [
                ch("showcase", "🖼️", topic="Zeig deine Arbeit", slowmode=60),
                ch("feedback", "💡", topic="Konstruktive Kritik"),
                ch("resources", "📚", topic="Tools und Fundstücke"),
                ch("collabs", "🤝", topic="Partner für Projekte finden"),
            ]),
            cat("hilfe", "🛟", "public", [
                ch("support", "❓", "forum", topic="Frag die Community"),
                ch("bug-reports", "🐛", topic="Fehler melden"),
                ch("suggestions", "💭", topic="Ideen für den Server"),
                ch("appeals", "⚖️", topic="Einspruch gegen eine Strafe"),
            ]),
            social_category(),
            vip_category(),
            staff_category(),
            leadership_category(),
            logs_category(),
        ],
    }


def rp() -> dict[str, Any]:
    return {
        "key": "rp",
        "name": "RP Server",
        "emoji": "🎭",
        "tagline": "Roleplay mit Fraktionen, Ämtern und Immersion",
        "premium": False,
        "accent": "#9333EA",
        "description": (
            "Ein durchgeplanter Roleplay-Server. Die Reihenfolge ist bewusst gewählt: "
            "Flughafen und Verify zuerst, dann Regelwerke, RP-Start, Fraktionen, "
            "Behörden und Wirtschaft. Dazu abgeschirmte Team-, Büro- und Log-Bereiche."
        ),
        "highlights": [
            "Bewusste Kategorie-Reihenfolge: Flughafen → Verify → Regelwerk → RP",
            "Eigene Bereiche für Fraktionen, Behörden und Wirtschaft",
            "18 RP-Voice-Räume inklusive Funk- und Gerichtssaal",
            "Getrennte Büro- und Aktenbereiche für das High-Team",
        ],
        "roles": [
            role("roleplayer", "Roleplayer", "🎭", "#7C3AED", "member", hoist=False),
            role("whitelist", "Whitelist", "📝", "#8B5CF6", "trusted", hoist=False),
            role("faction_lead", "Fraktionsleitung", "🏴", "#A21CAF", "helper"),
            role("gov", "Behörde", "🏛️", "#0EA5E9", "helper"),
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
            cat("verify", "✅", "gate", [
                ch("verifizieren", "🔓", topic="Verifizierung starten"),
                ch("verify-info", "📖", topic="So läuft die Verifizierung", visibility="readonly"),
                ch("verify-fragen", "❔", topic="Fragen zur Verifizierung"),
                ch("whitelist-antrag", "📝", topic="Whitelist beantragen"),
            ]),
            cat("regelwerk", "📜", "readonly", [
                ch("serverregeln", "⚖️", topic="Die verbindlichen Serverregeln"),
                ch("rp-regeln", "🎭", topic="Roleplay-spezifische Regeln"),
                ch("fraktionsregeln", "🏴", topic="Regeln für Fraktionen"),
                ch("strafenkatalog", "📕", topic="Welche Strafe folgt worauf"),
                ch("changelog", "🔄", topic="Änderungen am Regelwerk"),
            ]),
            cat("rp start", "🚀", "public", [
                ch("ankuendigungen", "📢", "news", topic="Server-News", visibility="readonly"),
                ch("rp-news", "📰", topic="Was passiert in der Stadt?"),
                ch("charaktere", "🧑‍🎤", topic="Stelle deinen Charakter vor", slowmode=120),
                ch("steckbriefe", "📇", topic="Charakter-Steckbriefe"),
                ch("suche-rp", "🔍", topic="Mitspieler für Szenen finden"),
                ch("ooc-chat", "💬", topic="Out of character"),
            ]),
            cat("fraktionen", "🏴", "public", [
                ch("fraktions-news", "📣", topic="Neues aus den Fraktionen", visibility="readonly"),
                ch("fraktionssuche", "🔎", topic="Fraktion gesucht?"),
                ch("bewerbungen", "📨", topic="Fraktionsbewerbungen"),
                ch("allianzen", "🤝", topic="Bündnisse und Konflikte"),
                ch("fraktions-chat", "💼", topic="Übergreifender Austausch"),
                ch("fraktions-voice", "🎙️", "voice", user_limit=20),
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
                ch("jobs", "💼", topic="Stellenangebote"),
                ch("werbung", "📺", topic="Werbung für dein Unternehmen", slowmode=600),
            ]),
            cat("rp talks", "🎙️", "public", [
                ch("stadt-1", "🏙️", "voice", user_limit=0),
                ch("stadt-2", "🌆", "voice", user_limit=0),
                ch("stadt-3", "🌃", "voice", user_limit=0),
                ch("funk-polizei", "📻", "voice", user_limit=15),
                ch("funk-rettung", "🚨", "voice", user_limit=15),
                ch("fraktion-a", "🅰️", "voice", user_limit=12),
                ch("fraktion-b", "🅱️", "voice", user_limit=12),
                ch("privat-1", "🔒", "voice", user_limit=4),
                ch("privat-2", "🔒", "voice", user_limit=4),
                ch("warteraum", "⏳", "voice", user_limit=0),
                ch("afk", "💤", "voice", user_limit=0),
            ]),
            *language_category(20, 8),
            cat("freizeit", "🎲", "public", [
                ch("offtopic", "🌙", topic="Alles außerhalb des RP"),
                ch("memes", "😂", topic="Memes aus der Stadt"),
                ch("clips", "🎬", topic="Deine besten Szenen"),
                ch("screenshots", "📸", topic="Bilder aus dem RP"),
                ch("bot-commands", "🤖", topic="Bot-Befehle"),
                ch("lounge-voice", "☕", "voice", user_limit=0),
            ]),
            cat("support", "🛟", "public", [
                ch("support", "🎫", "forum", topic="Tickets und Hilfe"),
                ch("bug-reports", "🐛", topic="Fehler melden"),
                ch("beschwerden", "📣", topic="Beschwerden über Spieler"),
                ch("entbannung", "⚖️", topic="Entbannungsanträge"),
                ch("vorschlaege", "💡", topic="Ideen für die Stadt"),
                ch("warteschlange", "⏱️", "voice", user_limit=0),
                ch("support-1", "🧑‍💻", "voice", user_limit=3),
                ch("support-2", "🧑‍💻", "voice", user_limit=3),
            ]),
            vip_category(),
            staff_category(),
            cat("bueros", "💼", "leadership", [
                ch("buero-leitung", "🗝️", topic="Büro der Serverleitung"),
                ch("buero-entwicklung", "🛠️", topic="Entwicklung und Skripte"),
                ch("buero-personal", "🧑‍💼", topic="Personalakten"),
                ch("akten", "🗄️", topic="Archiv", visibility="archive"),
                ch("besprechung", "🪑", "voice", user_limit=12),
            ]),
            leadership_category(),
            logs_category(),
        ],
    }


def social() -> dict[str, Any]:
    return {
        "key": "social",
        "name": "Social Lounge",
        "emoji": "☕",
        "tagline": "Chillen, quatschen, Leute treffen — in 37 Sprachen",
        "premium": False,
        "accent": "#14B8A6",
        "description": (
            "Der geselligste Server der Sammlung. Der Fokus liegt auf Gesprächen: "
            "37 Sprachkanäle, 24 Sprach-Voice-Räume, ein großer Voice-Bereich, "
            "Medien, Aktivitäten und eine vollständige Social-Log-Struktur."
        ),
        "highlights": [
            "Größter Sprachbereich: 37 Textkanäle und 24 Voice-Räume",
            "Aktivitäten, Watch-Partys und Musikräume",
            "Vorbereitete Vorstellungs- und Kennenlern-Kanäle",
            "Komplette Social-Log-Suite für Moderation",
        ],
        "roles": [
            role("host", "Lounge Host", "🌟", "#F97316", "helper"),
            role("nightowl", "Night Owl", "🌙", "#6366F1", "trusted", hoist=False),
            role("dj", "DJ", "🎧", "#EC4899", "trusted", hoist=False),
            role("welcomer", "Welcomer", "🫶", "#22D3EE", "helper"),
        ],
        "categories": [
            gate_category(),
            info_category([ch("introductions", "🙋", topic="Stell dich kurz vor")]),
            cat("lounge", "☕", "public", [
                ch("general", "💬", topic="Der Hauptchat", slowmode=3),
                ch("vent", "🫂", topic="Wenn du reden musst", slowmode=30),
                ch("good-news", "🎉", topic="Teile deine guten Nachrichten"),
                ch("daily-question", "❓", topic="Frage des Tages"),
                ch("confessions", "🤫", topic="Anonyme Geständnisse"),
                ch("compliments", "💐", topic="Sag jemandem etwas Nettes"),
                ch("advice", "🧭", topic="Rat von der Community"),
                ch("bot-commands", "🤖", topic="Bot-Befehle"),
            ]),
            *language_category(36, 24),
            cat("voice lounge", "🔊", "public", [
                ch("hangout-1", "🎙️", "voice", user_limit=0),
                ch("hangout-2", "🎙️", "voice", user_limit=0),
                ch("hangout-3", "🎙️", "voice", user_limit=0),
                ch("chill", "☕", "voice", user_limit=10),
                ch("deep-talk", "🌌", "voice", user_limit=6),
                ch("music", "🎶", "voice", user_limit=0),
                ch("karaoke", "🎤", "voice", user_limit=12),
                ch("duo", "👥", "voice", user_limit=2),
                ch("trio", "👨‍👩‍👦", "voice", user_limit=3),
                ch("study-together", "📚", "voice", user_limit=0),
                ch("late-night", "🌙", "voice", user_limit=12),
                ch("stage", "🎭", "stage"),
                ch("afk", "💤", "voice", user_limit=0),
            ]),
            cat("medien", "🖼️", "public", [
                ch("photos", "📸", topic="Deine Fotos"),
                ch("art", "🎨", topic="Kunst und Zeichnungen"),
                ch("memes", "😂", topic="Memes"),
                ch("music-share", "🎧", topic="Songempfehlungen"),
                ch("movies-series", "🎬", topic="Filme und Serien"),
                ch("books", "📖", topic="Was liest du gerade?"),
                ch("pets", "🐾", topic="Haustiere"),
                ch("outfits", "👗", topic="Outfit des Tages"),
            ]),
            cat("aktivitaeten", "🎲", "public", [
                ch("game-night", "🕹️", topic="Spieleabende"),
                ch("watch-party", "🍿", topic="Gemeinsam schauen"),
                ch("challenges", "🏅", topic="Community-Challenges"),
                ch("birthdays", "🎂", topic="Geburtstage"),
                ch("polls", "📊", topic="Abstimmungen"),
                ch("activity-voice", "🎪", "voice", user_limit=25),
            ]),
            social_category(),
            vip_category(),
            cat("hilfe", "🛟", "public", [
                ch("support", "❓", "forum", topic="Fragen an das Team"),
                ch("suggestions", "💡", topic="Vorschläge"),
                ch("reports", "🚩", topic="Etwas melden"),
                ch("appeals", "⚖️", topic="Einspruch"),
            ]),
            staff_category(),
            leadership_category(),
            logs_category(),
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
            "Für Gaming-Communities, die mehr als einen Voice-Channel brauchen: "
            "eigene Hubs pro Spiel, LFG-System, Turnierverwaltung, Coaching und "
            "20 Squad-Räume in unterschiedlichen Größen."
        ),
        "highlights": [
            "Eigene Text-Hubs für 10 Spiele plus LFG-Kanäle",
            "20 Voice-Räume: Duo, Trio, Squad, Full-Stack und Turnierräume",
            "Turnier- und Scrim-Verwaltung mit eigener Rollengruppe",
            "Clip-, Highlight- und Coaching-Bereiche",
        ],
        "roles": [
            role("gamer", "Gamer", "🎮", "#22D3EE", "member", hoist=False),
            role("competitive", "Competitive", "🏆", "#F59E0B", "trusted"),
            role("coach", "Coach", "🧠", "#8B5CF6", "helper"),
            role("tournament", "Tournament Team", "🎯", "#E11D48", "helper"),
            role("caster", "Caster", "🎙️", "#0EA5E9", "helper"),
            role("clipper", "Clip Creator", "🎬", "#F97316", "trusted", hoist=False),
        ],
        "categories": [
            gate_category(),
            info_category([ch("patch-notes", "🩹", topic="Patchnotes der Spiele")]),
            cat("gaming hub", "🎮", "public", [
                ch("gaming-general", "💬", topic="Allgemeiner Gaming-Chat"),
                ch("valorant", "🔫", topic="Valorant"),
                ch("league-of-legends", "⚔️", topic="League of Legends"),
                ch("counter-strike", "💣", topic="Counter-Strike"),
                ch("fortnite", "🏗️", topic="Fortnite"),
                ch("minecraft", "⛏️", topic="Minecraft"),
                ch("gta-rp", "🚗", topic="GTA und RP"),
                ch("rocket-league", "🚀", topic="Rocket League"),
                ch("apex-legends", "🎯", topic="Apex Legends"),
                ch("call-of-duty", "🪖", topic="Call of Duty"),
                ch("indie-games", "🕹️", topic="Indie und Geheimtipps"),
                ch("retro", "👾", topic="Klassiker"),
            ]),
            cat("mitspieler", "🔎", "public", [
                ch("lfg-general", "📣", topic="Looking for group"),
                ch("lfg-ranked", "🏅", topic="Ranked-Mitspieler"),
                ch("lfg-casual", "🎲", topic="Entspannt zocken"),
                ch("scrims", "⚔️", topic="Scrims und Übungsspiele"),
                ch("team-suche", "🧩", topic="Feste Teams finden"),
            ]),
            cat("competitive", "🏆", "public", [
                ch("tournament-news", "📢", "news", topic="Turnier-Ankündigungen", visibility="readonly"),
                ch("tournament-signup", "📝", topic="Anmeldung"),
                ch("brackets", "🗂️", topic="Turnierbäume"),
                ch("results", "📊", topic="Ergebnisse", visibility="readonly"),
                ch("coaching", "🧠", "forum", topic="Coaching-Anfragen"),
                ch("vod-review", "🎞️", topic="VOD-Analysen"),
            ]),
            cat("clips", "🎬", "public", [
                ch("highlights", "⭐", topic="Deine besten Momente", slowmode=60),
                ch("fails", "💀", topic="Weniger gute Momente"),
                ch("setups", "🖥️", topic="Zeig dein Setup"),
                ch("screenshots", "📸", topic="Screenshots"),
                ch("streams", "🟣", topic="Wer streamt gerade?"),
            ]),
            cat("squad voice", "🔊", "public", [
                ch("lobby", "🎙️", "voice", user_limit=0),
                ch("duo-1", "👥", "voice", user_limit=2),
                ch("duo-2", "👥", "voice", user_limit=2),
                ch("trio-1", "👨‍👩‍👦", "voice", user_limit=3),
                ch("trio-2", "👨‍👩‍👦", "voice", user_limit=3),
                ch("squad-1", "🛡️", "voice", user_limit=5),
                ch("squad-2", "🛡️", "voice", user_limit=5),
                ch("squad-3", "🛡️", "voice", user_limit=5),
                ch("full-stack-1", "⚔️", "voice", user_limit=10),
                ch("full-stack-2", "⚔️", "voice", user_limit=10),
                ch("scrim-a", "🅰️", "voice", user_limit=6),
                ch("scrim-b", "🅱️", "voice", user_limit=6),
                ch("tournament-1", "🏆", "voice", user_limit=12),
                ch("tournament-2", "🏆", "voice", user_limit=12),
                ch("casting", "🎙️", "stage"),
                ch("chill", "☕", "voice", user_limit=10),
                ch("music", "🎶", "voice", user_limit=0),
                ch("afk", "💤", "voice", user_limit=0),
            ]),
            *language_category(20, 10),
            social_category(),
            vip_category(),
            cat("support", "🛟", "public", [
                ch("support", "🎫", "forum", topic="Hilfe vom Team"),
                ch("tech-help", "🛠️", topic="Technische Probleme"),
                ch("bug-reports", "🐛", topic="Fehler melden"),
                ch("suggestions", "💡", topic="Vorschläge"),
            ]),
            staff_category(),
            leadership_category(),
            logs_category(),
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
            "und Watch-Party-Räume mit Stage-Support."
        ),
        "highlights": [
            "Getrennte Spoiler-Kanäle pro Bereich",
            "Seasonal-, Manga-, Fanart- und Cosplay-Zonen",
            "Watch-Party-Voice mit Stage für Events",
            "Japanisch-, Koreanisch- und Chinesisch-Lernkanäle",
        ],
        "roles": [
            role("otaku", "Otaku", "🌸", "#F472B6", "member", hoist=False),
            role("manga_reader", "Manga Reader", "📚", "#A78BFA", "trusted", hoist=False),
            role("fanartist", "Fan Artist", "🖌️", "#FB7185", "trusted"),
            role("cosplayer", "Cosplayer", "🎀", "#F0ABFC", "trusted"),
            role("watch_host", "Watch Party Host", "🍿", "#F59E0B", "helper"),
        ],
        "categories": [
            gate_category(),
            info_category([ch("seasonal-chart", "📅", topic="Die aktuelle Season")]),
            cat("anime", "📺", "public", [
                ch("anime-general", "💬", topic="Allgemeiner Anime-Chat"),
                ch("currently-watching", "👀", topic="Was schaust du gerade?"),
                ch("seasonals", "🌱", topic="Die laufende Season"),
                ch("recommendations", "⭐", topic="Empfehlungen"),
                ch("spoilers", "🚨", topic="Achtung: Spoiler erlaubt"),
                ch("reviews", "📝", topic="Deine Bewertungen"),
                ch("news", "📰", "news", topic="Anime-News", visibility="readonly"),
            ]),
            cat("manga", "📚", "public", [
                ch("manga-general", "💬", topic="Manga-Chat"),
                ch("new-chapters", "🆕", topic="Neue Kapitel"),
                ch("manga-spoilers", "🚨", topic="Spoiler erlaubt"),
                ch("light-novels", "📖", topic="Light Novels"),
                ch("webtoons", "📱", topic="Webtoons und Manhwa"),
            ]),
            cat("kreativ", "🎨", "public", [
                ch("fanart", "🖌️", topic="Eigene Fanart", slowmode=120),
                ch("art-help", "💡", topic="Feedback und Tipps"),
                ch("cosplay", "🎀", topic="Cosplay zeigen"),
                ch("edits", "✂️", topic="Edits und AMVs"),
                ch("writing", "✍️", topic="Fanfiction"),
                ch("commissions", "💰", topic="Auftragsarbeiten", slowmode=600),
            ]),
            cat("watch party", "🍿", "public", [
                ch("watch-planning", "📅", topic="Nächste Watch-Party planen"),
                ch("watch-chat", "💬", topic="Live-Chat zur Party"),
                ch("watch-room-1", "🎬", "voice", user_limit=25),
                ch("watch-room-2", "🎬", "voice", user_limit=25),
                ch("watch-stage", "🎤", "stage"),
            ]),
            cat("japan", "🗾", "public", [
                ch("nihongo", "🇯🇵", topic="Japanisch lernen"),
                ch("korean", "🇰🇷", topic="Koreanisch lernen"),
                ch("chinese", "🇨🇳", topic="Chinesisch lernen"),
                ch("culture", "⛩️", topic="Kultur und Reisen"),
                ch("food", "🍜", topic="Japanische Küche"),
            ]),
            cat("games", "🎮", "public", [
                ch("gacha", "🎰", topic="Gacha-Spiele"),
                ch("jrpg", "🗡️", topic="JRPGs"),
                ch("rhythm-games", "🎵", topic="Rhythmusspiele"),
                ch("visual-novels", "📗", topic="Visual Novels"),
                ch("gaming-voice", "🕹️", "voice", user_limit=10),
            ]),
            voice_lounge(8, prefix="voice lounge"),
            *language_category(20, 8),
            social_category(),
            vip_category(),
            staff_category(),
            leadership_category(),
            logs_category(),
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
            "ein abgeschirmter Kundenbereich und Meeting-Räume. Berechtigungen sind "
            "so gesetzt, dass interne Themen intern bleiben."
        ),
        "highlights": [
            "Abteilungen für Entwicklung, Design, Marketing, Sales und HR",
            "Kundenbereich getrennt vom internen Bereich",
            "Meeting-Räume, Stand-up-Voice und Fokus-Räume",
            "Vollständige Audit-Logs für Nachvollziehbarkeit",
        ],
        "roles": [
            role("employee", "Mitarbeiter", "💼", "#0F766E", "member"),
            role("client", "Kunde", "🤝", "#059669", "guest"),
            role("freelancer", "Freelancer", "🧑‍💻", "#14B8A6", "member", hoist=False),
            role("project_lead", "Projektleitung", "📊", "#0369A1", "helper"),
            role("dept_lead", "Abteilungsleitung", "👔", "#1D4ED8", "moderator"),
            role("hr", "HR", "🧑‍💼", "#7C3AED", "moderator"),
            role("management", "Management", "🏛️", "#DC2626", "admin"),
        ],
        "categories": [
            gate_category(),
            info_category([ch("company-news", "🏢", topic="Unternehmensnews")]),
            cat("allgemein", "💬", "public", [
                ch("general", "💭", topic="Allgemeiner Austausch"),
                ch("random", "🎲", topic="Kaffeeküche"),
                ch("wins", "🎉", topic="Erfolge feiern"),
                ch("questions", "❓", topic="Kurze Fragen"),
                ch("bot-commands", "🤖", topic="Bot-Befehle"),
            ]),
            cat("abteilungen", "🏗️", "member", [
                ch("development", "💻", topic="Entwicklung"),
                ch("design", "🎨", topic="Design und UX"),
                ch("marketing", "📣", topic="Marketing"),
                ch("sales", "💰", topic="Vertrieb"),
                ch("support-team", "🛟", topic="Kundensupport intern"),
                ch("finance", "📈", topic="Finanzen"),
                ch("hr", "🧑‍💼", topic="Personal"),
                ch("legal", "⚖️", topic="Recht und Compliance"),
            ]),
            cat("projekte", "📊", "member", [
                ch("project-board", "🗂️", topic="Übersicht aller Projekte", visibility="readonly"),
                ch("project-alpha", "🅰️", topic="Projekt Alpha"),
                ch("project-beta", "🅱️", topic="Projekt Beta"),
                ch("project-gamma", "🇬", topic="Projekt Gamma"),
                ch("backlog", "📋", "forum", topic="Aufgaben und Ideen"),
                ch("releases", "🚀", topic="Release-Ankündigungen", visibility="readonly"),
            ]),
            cat("kunden", "🤝", "public", [
                ch("client-welcome", "👋", topic="Willkommen, Kunden", visibility="readonly"),
                ch("client-requests", "📥", "forum", topic="Anfragen einreichen"),
                ch("client-updates", "📢", topic="Statusmeldungen", visibility="readonly"),
                ch("client-feedback", "💬", topic="Feedback"),
                ch("client-call", "📞", "voice", user_limit=10),
            ]),
            cat("meetings", "🗓️", "member", [
                ch("meeting-notes", "📝", topic="Protokolle"),
                ch("agenda", "📌", topic="Tagesordnung"),
                ch("standup", "☀️", "voice", user_limit=20),
                ch("meeting-room-1", "🪑", "voice", user_limit=15),
                ch("meeting-room-2", "🪑", "voice", user_limit=15),
                ch("focus-1", "🎧", "voice", user_limit=1),
                ch("focus-2", "🎧", "voice", user_limit=1),
                ch("all-hands", "🏛️", "stage"),
                ch("break-room", "☕", "voice", user_limit=0),
            ]),
            cat("wissen", "📚", "member", [
                ch("handbook", "📖", topic="Das Unternehmenshandbuch", visibility="readonly"),
                ch("onboarding", "🚀", topic="Einstieg für Neue"),
                ch("templates", "🗂️", topic="Vorlagen und Assets"),
                ch("tools", "🛠️", topic="Werkzeuge und Zugänge"),
                ch("archive", "🗄️", topic="Abgeschlossenes", visibility="archive"),
            ]),
            *language_category(12, 4),
            staff_category("leitung intern"),
            leadership_category(),
            logs_category(),
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
            "Für Lerngruppen, Fachschaften und Uni-Communities: ein Kanal pro Fach, "
            "Lerngruppen, Prüfungsvorbereitung, ein Ressourcen-Archiv und stille "
            "Pomodoro-Räume, in denen wirklich gearbeitet wird."
        ),
        "highlights": [
            "Eigene Kanäle für 10 Fachbereiche",
            "Stille Study-Rooms mit Pomodoro-Timer-Kanälen",
            "Prüfungs-, Hausarbeits- und Abgabe-Bereiche",
            "Tutor-Rollen mit eigenem Sprechstunden-Voice",
        ],
        "roles": [
            role("student", "Student", "🎓", "#0284C7", "member", hoist=False),
            role("freshman", "Ersti", "🐣", "#38BDF8", "member", hoist=False),
            role("tutor", "Tutor", "🧑‍🏫", "#16A34A", "helper"),
            role("lecturer", "Lehrkraft", "🏫", "#2563EB", "moderator"),
            role("study_lead", "Study Leitung", "📚", "#7C3AED", "admin"),
            role("alumni", "Alumni", "🎖️", "#A16207", "trusted", hoist=False),
        ],
        "categories": [
            gate_category(),
            info_category([ch("semester-plan", "📅", topic="Termine und Fristen")]),
            cat("campus", "🏫", "public", [
                ch("general", "💬", topic="Allgemeiner Campus-Chat"),
                ch("introductions", "🙋", topic="Stell dich vor"),
                ch("questions", "❓", topic="Kurze Fragen"),
                ch("motivation", "🔥", topic="Motivation und Erfolge"),
                ch("memes", "😂", topic="Uni-Memes"),
                ch("bot-commands", "🤖", topic="Bot-Befehle"),
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
                ch("geistes", "🏛️", topic="Geisteswissenschaften"),
            ]),
            cat("lerngruppen", "👥", "public", [
                ch("gruppensuche", "🔎", topic="Lerngruppe finden"),
                ch("gruppe-1", "1️⃣", topic="Lerngruppe 1"),
                ch("gruppe-2", "2️⃣", topic="Lerngruppe 2"),
                ch("gruppe-3", "3️⃣", topic="Lerngruppe 3"),
                ch("gruppe-4", "4️⃣", topic="Lerngruppe 4"),
                ch("projektarbeit", "🧩", "forum", topic="Gruppenprojekte"),
            ]),
            cat("pruefungen", "📝", "public", [
                ch("pruefungstermine", "📅", topic="Termine", visibility="readonly"),
                ch("altklausuren", "🗂️", topic="Altklausuren und Übungen"),
                ch("lernplaene", "🗺️", topic="Lernpläne teilen"),
                ch("hausarbeiten", "📄", topic="Hausarbeiten und Abgaben"),
                ch("panik-raum", "😰", topic="Für den Tag vor der Prüfung"),
            ]),
            cat("study rooms", "🔇", "public", [
                ch("silent-1", "🤫", "voice", user_limit=0),
                ch("silent-2", "🤫", "voice", user_limit=0),
                ch("pomodoro-25", "🍅", "voice", user_limit=0),
                ch("pomodoro-50", "🍅", "voice", user_limit=0),
                ch("group-study-1", "👥", "voice", user_limit=6),
                ch("group-study-2", "👥", "voice", user_limit=6),
                ch("sprechstunde", "🧑‍🏫", "voice", user_limit=8),
                ch("praesentation", "📊", "stage"),
                ch("pause", "☕", "voice", user_limit=0),
                ch("afk", "💤", "voice", user_limit=0),
            ]),
            cat("ressourcen", "📚", "public", [
                ch("skripte", "📑", topic="Skripte und Folien"),
                ch("buecher", "📖", topic="Literaturempfehlungen"),
                ch("tools", "🛠️", topic="Nützliche Werkzeuge"),
                ch("stipendien", "💰", topic="Förderung und Stipendien"),
                ch("jobs", "💼", topic="Werkstudentenstellen"),
                ch("archiv", "🗄️", topic="Vergangene Semester", visibility="archive"),
            ]),
            cat("campusleben", "🎉", "public", [
                ch("events", "📅", topic="Partys und Veranstaltungen"),
                ch("sport", "⚽", topic="Hochschulsport"),
                ch("wohnen", "🏠", topic="WG- und Zimmersuche"),
                ch("mensa", "🍽️", topic="Essen auf dem Campus"),
                ch("freizeit-voice", "🎪", "voice", user_limit=20),
            ]),
            *language_category(16, 6),
            vip_category(),
            staff_category(),
            leadership_category(),
            logs_category(),
        ],
    }


def creator() -> dict[str, Any]:
    return {
        "key": "creator",
        "name": "Creator Studio",
        "emoji": "🎬",
        "tagline": "Content planen, produzieren und vermarkten",
        "premium": True,
        "accent": "#F97316",
        "description": (
            "Für Content Creator und ihre Communities: getrennte Bereiche für "
            "Planung, Produktion, Feedback und Kooperationen, dazu ein "
            "abgeschirmter Business-Bereich für Deals und Rechnungen."
        ),
        "highlights": [
            "Produktions-Pipeline von Idee bis Upload",
            "Feedback-Kanäle mit Slowmode für Qualität",
            "Kooperations- und Sponsoring-Bereich, nur für Creator sichtbar",
            "Aufnahme-Voice mit getrennten Räumen pro Format",
        ],
        "roles": [
            role("creator_pro", "Creator", "🎬", "#F97316", "trusted"),
            role("editor", "Editor", "✂️", "#EA580C", "trusted"),
            role("thumbnail", "Thumbnail Artist", "🖼️", "#FB923C", "trusted", hoist=False),
            role("collab", "Collab Team", "🤝", "#DB2777", "helper"),
            role("sponsor", "Sponsor", "💰", "#CA8A04", "guest", hoist=False),
            role("moderator_chat", "Chat Mod", "💬", "#3B82F6", "moderator"),
        ],
        "categories": [
            gate_category(),
            info_category([ch("upload-plan", "📅", topic="Wann kommt was?")]),
            cat("community", "💬", "public", [
                ch("general", "💭", topic="Allgemeiner Chat"),
                ch("suggestions", "💡", topic="Themenwünsche"),
                ch("questions", "❓", topic="Fragen an den Creator"),
                ch("clips", "🎞️", topic="Clips aus Videos und Streams"),
                ch("memes", "😂", topic="Memes"),
                ch("bot-commands", "🤖", topic="Bot-Befehle"),
            ]),
            cat("produktion", "🎬", "staff", [
                ch("ideas", "💡", "forum", topic="Ideensammlung"),
                ch("scripts", "📝", topic="Skripte und Konzepte"),
                ch("recording", "🎥", topic="Aufnahmeplanung"),
                ch("editing", "✂️", topic="Schnitt und Postproduktion"),
                ch("thumbnails", "🖼️", topic="Thumbnail-Entwürfe"),
                ch("review", "🔍", topic="Letzter Check vor Upload"),
                ch("published", "✅", topic="Veröffentlicht", visibility="archive"),
            ]),
            cat("feedback", "🔍", "public", [
                ch("video-feedback", "🎬", topic="Feedback zu Videos", slowmode=60),
                ch("stream-feedback", "🟣", topic="Feedback zu Streams", slowmode=60),
                ch("design-feedback", "🎨", topic="Feedback zu Grafiken", slowmode=60),
                ch("analytics", "📊", topic="Zahlen und Reichweite", visibility="staff"),
            ]),
            cat("business", "💼", "leadership", [
                ch("deals", "🤝", topic="Kooperationsanfragen"),
                ch("sponsoring", "💰", topic="Sponsoring"),
                ch("contracts", "📄", topic="Verträge"),
                ch("invoices", "🧾", topic="Rechnungen"),
                ch("business-voice", "🔐", "voice", user_limit=8),
            ]),
            cat("collabs", "🤝", "member", [
                ch("collab-board", "📌", topic="Offene Kooperationen"),
                ch("creator-lounge", "☕", topic="Austausch unter Creators"),
                ch("cross-promo", "🔁", topic="Gegenseitige Promo"),
                ch("collab-voice", "🎙️", "voice", user_limit=10),
            ]),
            cat("studio voice", "🔊", "public", [
                ch("recording-1", "🔴", "voice", user_limit=4),
                ch("recording-2", "🔴", "voice", user_limit=4),
                ch("podcast", "🎙️", "voice", user_limit=6),
                ch("watch-together", "📺", "voice", user_limit=20),
                ch("community-hangout", "☕", "voice", user_limit=0),
                ch("q-and-a", "❔", "stage"),
                ch("afk", "💤", "voice", user_limit=0),
            ]),
            social_category(),
            *language_category(16, 6),
            vip_category(),
            staff_category(),
            logs_category(),
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
            "Wissensdatenbank, klare Eskalationsstufen und ein Auswertungsbereich, "
            "in dem Qualität und Reaktionszeiten sichtbar werden."
        ),
        "highlights": [
            "Ticket-Forum mit getrennten Eskalationsstufen",
            "Öffentliche Wissensdatenbank und FAQ",
            "Interner Qualitäts- und Auswertungsbereich",
            "Sprechstunden-Voice mit Warteschlange",
        ],
        "roles": [
            role("ticket_team", "Ticket Team", "🎫", "#0EA5E9", "helper"),
            role("specialist", "Fachberater", "🧠", "#0891B2", "helper"),
            role("escalation", "Eskalation", "🚨", "#DC2626", "moderator"),
            role("quality", "Quality Team", "📈", "#7C3AED", "moderator"),
            role("knowledge", "Wissensredaktion", "📚", "#16A34A", "helper"),
        ],
        "categories": [
            gate_category(),
            info_category([ch("status", "🟢", topic="Systemstatus und Störungen")]),
            cat("hilfe", "🛟", "public", [
                ch("start-here", "👋", topic="So bekommst du Hilfe", visibility="readonly"),
                ch("tickets", "🎫", "forum", topic="Erstelle hier dein Ticket"),
                ch("quick-questions", "⚡", topic="Kurze Fragen ohne Ticket"),
                ch("community-help", "🤝", topic="Nutzer helfen Nutzern"),
                ch("bug-reports", "🐛", "forum", topic="Fehler melden"),
                ch("feature-requests", "💡", "forum", topic="Wünsche einreichen"),
            ]),
            cat("wissen", "📚", "readonly", [
                ch("faq", "❔", topic="Häufige Fragen"),
                ch("guides", "📖", topic="Schritt-für-Schritt-Anleitungen"),
                ch("troubleshooting", "🔧", topic="Problemlösungen"),
                ch("changelog", "🔄", topic="Was hat sich geändert?"),
                ch("known-issues", "⚠️", topic="Bekannte Probleme"),
            ]),
            cat("sprechstunde", "🎙️", "public", [
                ch("warteschlange", "⏳", "voice", user_limit=0),
                ch("support-raum-1", "🧑‍💻", "voice", user_limit=3),
                ch("support-raum-2", "🧑‍💻", "voice", user_limit=3),
                ch("support-raum-3", "🧑‍💻", "voice", user_limit=3),
                ch("screenshare", "🖥️", "voice", user_limit=5),
            ]),
            cat("support intern", "🔧", "staff", [
                ch("team-briefing", "📋", topic="Tagesbriefing"),
                ch("eskalation", "🚨", topic="Eskalierte Fälle"),
                ch("wissensredaktion", "✍️", topic="Artikel schreiben und pflegen"),
                ch("schichtplan", "🗓️", topic="Wer hat wann Dienst?"),
                ch("interne-voice", "🎧", "voice", user_limit=10),
            ]),
            cat("auswertung", "📈", "leadership", [
                ch("statistiken", "📊", topic="Zahlen und Trends"),
                ch("qualitaet", "🏅", topic="Qualitätssicherung"),
                ch("feedback-auswertung", "💬", topic="Was sagen die Nutzer?"),
                ch("verbesserungen", "🚀", topic="Maßnahmen"),
            ]),
            *language_category(24, 8),
            cat("community", "💬", "public", [
                ch("general", "💭", topic="Allgemeiner Chat"),
                ch("offtopic", "🌙", topic="Abseits vom Support"),
                ch("lounge-voice", "☕", "voice", user_limit=0),
            ]),
            staff_category(),
            leadership_category(),
            logs_category(),
        ],
    }


def esports() -> dict[str, Any]:
    return {
        "key": "esports",
        "name": "Esports Organisation",
        "emoji": "🏆",
        "tagline": "Roster, Scrims und Matchday-Betrieb",
        "premium": True,
        "accent": "#E11D48",
        "description": (
            "Für Esports-Organisationen mit mehreren Teams: getrennte Roster-Bereiche, "
            "Matchday-Betrieb, Analyse und ein Bereich für Sponsoren und Presse — "
            "sauber abgeschirmt von der öffentlichen Fan-Community."
        ),
        "highlights": [
            "Eigene, private Bereiche für vier Roster",
            "Matchday-Kanäle mit Vorbereitung, Live und Nachbesprechung",
            "Analyse- und VOD-Review-Struktur",
            "Getrennte Zonen für Fans, Presse und Sponsoren",
        ],
        "roles": [
            role("player", "Player", "🎮", "#E11D48", "trusted"),
            role("captain", "Captain", "🎖️", "#BE123C", "helper"),
            role("coach_es", "Coach", "🧠", "#8B5CF6", "helper"),
            role("analyst", "Analyst", "📊", "#0EA5E9", "helper"),
            role("manager", "Team Manager", "📋", "#F59E0B", "moderator"),
            role("press", "Presse", "📰", "#64748B", "guest", hoist=False),
            role("fan", "Fan", "💛", "#FACC15", "member", hoist=False),
        ],
        "categories": [
            gate_category(),
            info_category([ch("match-schedule", "📅", topic="Kommende Spiele")]),
            cat("fanzone", "💛", "public", [
                ch("general", "💬", topic="Fan-Chat"),
                ch("match-talk", "🔥", topic="Live mitfiebern"),
                ch("predictions", "🔮", topic="Tippspiel"),
                ch("fanart", "🎨", topic="Fanart und Support"),
                ch("merch", "👕", topic="Merchandise"),
                ch("watchparty", "📺", "voice", user_limit=50),
                ch("fan-stage", "📣", "stage"),
            ]),
            cat("roster", "🎯", "staff", [
                ch("roster-main", "🥇", topic="Hauptteam"),
                ch("roster-academy", "🥈", topic="Academy"),
                ch("roster-female", "🥉", topic="Female Roster"),
                ch("roster-content", "🎬", topic="Content-Team"),
                ch("tryouts", "📝", topic="Sichtungen"),
                ch("roster-voice-1", "🎙️", "voice", user_limit=8),
                ch("roster-voice-2", "🎙️", "voice", user_limit=8),
            ]),
            cat("matchday", "⚔️", "staff", [
                ch("preparation", "📋", topic="Vorbereitung"),
                ch("lineups", "🧩", topic="Aufstellungen"),
                ch("live", "🔴", topic="Während des Matches"),
                ch("debrief", "🗣️", topic="Nachbesprechung"),
                ch("results", "📊", topic="Ergebnisse"),
                ch("matchroom-1", "🅰️", "voice", user_limit=6),
                ch("matchroom-2", "🅱️", "voice", user_limit=6),
            ]),
            cat("analyse", "📊", "staff", [
                ch("vod-review", "🎞️", topic="VOD-Analysen"),
                ch("scouting", "🔭", topic="Gegner beobachten"),
                ch("stats", "📈", topic="Statistiken"),
                ch("strategy", "🗺️", topic="Strategien"),
                ch("review-voice", "🖥️", "voice", user_limit=10),
            ]),
            cat("organisation", "🏢", "leadership", [
                ch("management", "🏛️", topic="Orga-Leitung"),
                ch("sponsoren", "💰", topic="Sponsoring"),
                ch("presse", "📰", topic="Presseanfragen"),
                ch("vertraege", "📄", topic="Verträge"),
                ch("budget", "🧾", topic="Budget"),
                ch("orga-voice", "🔐", "voice", user_limit=10),
            ]),
            social_category(),
            *language_category(16, 6),
            vip_category(),
            staff_category(),
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
