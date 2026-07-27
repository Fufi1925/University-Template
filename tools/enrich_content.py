#!/usr/bin/env python3
"""Weist den Kanaelen ihre Modi, Widgets, Reaktionen und Hinweistexte zu.

Die Zuordnung passiert regelbasiert ueber den Kanalnamen, damit sie in allen
zehn Vorlagen identisch ausfaellt: ein ``memes``-Kanal verhaelt sich im
Community-Server genauso wie im Anime-Hub.

Ausfuehren:  ``python tools/enrich_content.py``
Danach:      ``python tools/generate_templates.py`` (schreibt den Generator neu)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = BASE_DIR / "templates"
sys.path.insert(0, str(BASE_DIR))


# --------------------------------------------------------------------------- #
# Widgets — exakte Kanalnamen
# --------------------------------------------------------------------------- #

WIDGETS: dict[str, str] = {
    "verifizieren": "verify",
    "regeln": "rules",
    "serverregeln": "rules",
    "rollen-vergabe": "roles",
    "tickets": "ticket",
    "support": "ticket",
    "aufgaben": "checklist",
}


# --------------------------------------------------------------------------- #
# Modi
# --------------------------------------------------------------------------- #

# Kanaele, in denen nur Beitraege mit Bild, Video oder Link erlaubt sind.
MEDIA = {
    "bilder-und-clips", "memes", "fotos", "kunst", "fanart", "clips",
    "bildschirmfotos", "highlights", "fails", "setups", "outfits",
    "haustiere", "cosplay", "edits", "vorzeigen", "screenshots",
    "instagram", "tiktok", "youtube", "twitch", "x-twitter",
    "thumbnails", "watch-party", "merchandise", "fanartikel",
}

# Jeder Beitrag wird zu einem eigenen Thread.
THREADS = {
    "vorschlaege", "themenwuensche", "ideen", "fehler-melden",
    "funktionswuensche", "beschwerden", "entbannungsantrag",
    "entbannungsantraege", "bewerbungen", "gruppensuche",
    "mitspieler-suche", "team-suche",
}

COUNTING = {"zaehlen"}

# Nur das Team schreibt.
ANNOUNCE = {
    "ankuendigungen", "neuigkeiten", "team-ankuendigungen", "event-ankuendigungen",
    "turnier-news", "anime-news", "unternehmens-news", "stadt-nachrichten",
    "fraktions-news", "patchnotes", "systemstatus", "spielplan",
    "veroeffentlichungen", "ergebnisse", "kunden-updates", "regel-aenderungen",
}


def is_log(label: str) -> bool:
    return label.endswith("-logs") or label == "logs"


# --------------------------------------------------------------------------- #
# Auto-Reaktionen
# --------------------------------------------------------------------------- #

REACTIONS: dict[str, list[str]] = {
    "vorschlaege": ["👍", "👎"],
    "themenwuensche": ["👍", "👎"],
    "ideen": ["👍", "👎"],
    "funktionswuensche": ["👍", "👎"],
    "umfragen": ["👍", "👎"],
    "vorzeigen": ["⭐"],
    "fanart": ["⭐"],
    "kunst": ["⭐"],
    "highlights": ["🔥"],
    "clips": ["🔥"],
    "memes": ["😂"],
    "gute-nachrichten": ["🎉"],
    "erfolge": ["🎉"],
    "geburtstage": ["🎂"],
    "gewinnspiele": ["🎉"],
}


# --------------------------------------------------------------------------- #
# Ausformulierte Hinweistexte
# --------------------------------------------------------------------------- #

GUIDES: dict[str, list[str]] = {
    "willkommen": [
        "Schön, dass du da bist.",
        "Verifiziere dich nebenan, danach siehst du den gesamten Server.",
    ],
    "haeufige-fragen": [
        "Die häufigsten Fragen und ihre Antworten.",
        "Ist deine Frage nicht dabei, melde dich beim Team.",
    ],
    "allgemein": ["Der Hauptchat für alles, was keinen eigenen Kanal hat."],
    "bot-befehle": [
        "Bot-Befehle gehören hierher, damit sie den Hauptchat nicht zumüllen.",
    ],
    "zaehlen": ["Gemeinsam so weit zählen wie möglich."],
    "team-vorstellung": ["Wer zum Team gehört und wofür zuständig ist."],
    "partner": ["Server und Projekte, mit denen wir zusammenarbeiten."],
    "eigenwerbung": [
        "Eigene Projekte vorstellen — ein Beitrag pro Person, kein Spam.",
    ],
    "sorgen-ecke": [
        "Ein Ort zum Reden, wenn es gerade schwer ist.",
        "Behandelt einander mit Respekt. Kein Ratschlag ohne Nachfrage.",
    ],
    "gestaendnisse": ["Anonyme Geständnisse. Bleibt fair."],
    "panikraum": ["Für den Tag vor der Prüfung. Ihr schafft das."],
    "altklausuren": [
        "Altklausuren und Übungsblätter.",
        "Bitte nur teilen, was weitergegeben werden darf.",
    ],
    "warteschlange": ["Betritt diesen Sprachkanal, das Team holt dich ab."],
    "so-gehts": [
        "Kurze Fragen direkt nebenan.",
        "Alles, was länger dauert, gehört in ein Ticket.",
    ],
}


# --------------------------------------------------------------------------- #
# Anreicherung
# --------------------------------------------------------------------------- #

def enrich_channel(channel: dict[str, Any], visibility: str) -> None:
    label = channel["label"]
    kind = channel.get("kind", "text")

    # Sprachkanaele bekommen keine Nachricht.
    if kind in {"voice", "stage"}:
        return

    if label in WIDGETS:
        channel["widget"] = WIDGETS[label]

    # Modus bestimmen — die spezifischste Regel gewinnt.
    if is_log(label):
        channel["mode"] = "log"
    elif label in COUNTING:
        channel["mode"] = "counting"
    elif label in MEDIA:
        channel["mode"] = "media"
    elif label in THREADS and kind != "forum":
        channel["mode"] = "threads"
    elif label in ANNOUNCE or (visibility == "readonly" and kind == "news"):
        channel["mode"] = "announce"

    if label in REACTIONS:
        channel["reactions"] = REACTIONS[label]

    if label in GUIDES:
        channel["guide"] = GUIDES[label]


def enrich_template(data: dict[str, Any]) -> int:
    touched = 0
    for category in data["categories"]:
        visibility = category.get("visibility", "public")
        for channel in category["channels"]:
            before = json.dumps(channel, sort_keys=True)
            enrich_channel(channel, visibility)
            if json.dumps(channel, sort_keys=True) != before:
                touched += 1

    # Genau ein Checklisten-Kanal pro Vorlage: der erste Team-Aufgabenkanal.
    return touched


def main() -> int:
    from core.schema import Template, TemplateError

    print(f"{'Vorlage':<22}{'Kanäle':>8}{'Widgets':>9}{'Modi':>7}{'Reakt.':>8}")
    print("─" * 54)

    total = 0
    for path in sorted(TEMPLATE_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        touched = enrich_template(data)
        path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

        try:
            template = Template.parse(data, source=path.name)
        except TemplateError as exc:
            print(f"\n  ❌  {exc}\n", file=sys.stderr)
            return 1

        widgets = sum(
            1 for _, c in template.iter_channels() if c.widget.value != "none"
        )
        modes = sum(1 for _, c in template.iter_channels() if c.mode.value != "free")
        reactions = sum(1 for _, c in template.iter_channels() if c.reactions)
        total += touched

        print(
            f"{template.name:<22}{touched:>8}{widgets:>9}{modes:>7}{reactions:>8}"
        )

    print("─" * 54)
    print(f"{total} Kanäle angereichert")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
