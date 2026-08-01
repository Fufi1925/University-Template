#!/usr/bin/env python3
"""Kopiert die Emojis des University Bots in diese App.

Warum kopieren und nicht einfach benutzen
-----------------------------------------
App-Emojis sind an *eine* Anwendung gebunden. Discord sagt es deutlich:

    "An application can own up to 2000 emojis that can only be used by
     that app."
    https://docs.discord.com/developers/resources/emoji

Ein ``<:zbot:1530375453142159521>`` aus dem University Bot erscheint bei
uns also nicht als Bild, sondern als roher Text mitten im Satz. Genau
dieser Fehler war im University Bot schon einmal live -- vier Emojis
zeigten auf gelöschte IDs und standen als ``<:error:139...>`` in den
Antworten.

Die Bilder selbst sind dagegen frei abrufbar: ``cdn.discordapp.com``
liefert sie ohne Token. Dieses Skript lädt sie also herunter und legt
sie unter *unserer* App neu an. Die Namen bleiben gleich, die IDs sind
zwangsläufig neue.

Ausführen
---------
    DISCORD_TOKEN=... python tools/sync_emojis.py

Schreibt ``ui/emojis.py``. Ohne ``--write`` wird nichts hochgeladen,
sondern nur gezeigt, was passieren würde -- 142 Uploads sind nichts,
das man aus Versehen anstößt.

Optionen
--------
    --write     wirklich hochladen und ``ui/emojis.py`` schreiben
    --source    Datei mit den Vorlagen (Standard: die mitgelieferte)
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import re
import sys
from pathlib import Path

import aiohttp

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

OUT_FILE = BASE_DIR / "ui" / "emojis.py"
SOURCE_FILE = BASE_DIR / "tools" / "emoji_source.json"

API = "https://discord.com/api/v10"
CDN = "https://cdn.discordapp.com/emojis"

# Discord nimmt maximal 2000 App-Emojis; wir liegen weit darunter, aber
# ein Deckel verhindert, dass ein kaputtes Quelldokument tausende
# Uploads auslöst.
MAX_UPLOADS = 300


def parse_source(path: Path) -> list[dict]:
    """Liest die Emoji-Liste. Erwartet [{name, id, animated}, ...]."""

    data = json.loads(path.read_text(encoding="utf-8"))
    out = []
    for entry in data:
        name = str(entry.get("name", "")).strip()
        emoji_id = str(entry.get("id", "")).strip()
        # Discord erlaubt nur diese Zeichen; ein ungültiger Name lässt
        # den ganzen Upload mit 400 scheitern.
        if not re.fullmatch(r"[A-Za-z0-9_]{2,32}", name) or not emoji_id.isdigit():
            print(f"  übersprungen (ungültig): {entry!r}")
            continue
        out.append({"name": name, "id": emoji_id,
                    "animated": bool(entry.get("animated"))})
    return out


async def fetch_image(session: aiohttp.ClientSession, emoji_id: str,
                      animated: bool) -> tuple[bytes | None, str]:
    """Lädt das Bild. Die Endung im Quelldokument ist nur eine Vermutung.

    Ein als animiert markiertes Emoji ist es nicht zwangsläufig, und ein
    ``.gif`` auf ein statisches Bild liefert 415. Also der Reihe nach.
    """

    order = ["gif", "png", "webp"] if animated else ["png", "webp", "gif"]
    mimes = {"gif": "image/gif", "png": "image/png", "webp": "image/webp"}

    for ext in order:
        try:
            async with session.get(f"{CDN}/{emoji_id}.{ext}") as response:
                if response.status == 200:
                    return await response.read(), mimes[ext]
        except aiohttp.ClientError:
            continue
    return None, ""


async def existing_emojis(session: aiohttp.ClientSession, app_id: str) -> dict:
    async with session.get(f"{API}/applications/{app_id}/emojis") as response:
        if response.status != 200:
            raise SystemExit(
                f"Emojis der App nicht lesbar (HTTP {response.status}). "
                "Stimmt DISCORD_TOKEN?"
            )
        payload = await response.json()
    items = payload.get("items", payload) if isinstance(payload, dict) else payload
    return {item["name"]: item for item in items}


async def run(write: bool, source: Path) -> int:
    import config

    token = config.DISCORD_TOKEN
    if not token:
        raise SystemExit("DISCORD_TOKEN ist nicht gesetzt.")

    wanted = parse_source(source)
    if not wanted:
        raise SystemExit(f"Keine gültigen Einträge in {source}")
    if len(wanted) > MAX_UPLOADS:
        raise SystemExit(f"{len(wanted)} Einträge — mehr als {MAX_UPLOADS}, abgebrochen.")

    headers = {"Authorization": f"Bot {token}"}
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(f"{API}/users/@me") as response:
            if response.status != 200:
                raise SystemExit(f"Login fehlgeschlagen (HTTP {response.status}).")
            app_id = (await response.json())["id"]

        have = await existing_emojis(session, app_id)
        print(f"App {app_id}: {len(have)} Emojis vorhanden, {len(wanted)} gewünscht")

        result: dict[str, str] = {}
        uploaded = skipped = failed = 0

        for entry in wanted:
            name = entry["name"]

            # Schon da: übernehmen, nicht doppelt hochladen. Discord
            # lehnt doppelte Namen ohnehin ab.
            if name in have:
                item = have[name]
                prefix = "a" if item.get("animated") else ""
                result[name] = f"<{prefix}:{item['name']}:{item['id']}>"
                skipped += 1
                continue

            if not write:
                print(f"  würde hochladen: {name}")
                uploaded += 1
                continue

            image, mime = await fetch_image(session, entry["id"], entry["animated"])
            if image is None:
                print(f"  FEHLER Bild nicht ladbar: {name} ({entry['id']})")
                failed += 1
                continue

            body = {
                "name": name,
                "image": f"data:{mime};base64,{base64.b64encode(image).decode()}",
            }
            async with session.post(
                f"{API}/applications/{app_id}/emojis", json=body
            ) as response:
                if response.status in (200, 201):
                    item = await response.json()
                    prefix = "a" if item.get("animated") else ""
                    result[name] = f"<{prefix}:{item['name']}:{item['id']}>"
                    uploaded += 1
                    print(f"  hochgeladen: {name} -> {item['id']}")
                else:
                    print(f"  FEHLER {name}: HTTP {response.status} "
                          f"{(await response.text())[:120]}")
                    failed += 1

            # Discord bremst Uploads; ohne Pause endet der Lauf in 429ern.
            await asyncio.sleep(0.4)

    print(f"\n{uploaded} neu, {skipped} vorhanden, {failed} fehlgeschlagen")

    if not write:
        print("\nProbelauf — nichts hochgeladen. Mit --write ausführen.")
        return 0

    if failed and not result:
        raise SystemExit("Nichts übertragen, ui/emojis.py bleibt unverändert.")

    write_module(result)
    print(f"{OUT_FILE} geschrieben ({len(result)} Emojis)")
    return 1 if failed else 0


def write_module(mapping: dict[str, str]) -> None:
    lines = [
        '"""Die Emojis dieser App — erzeugt von ``tools/sync_emojis.py``.',
        "",
        "Nicht von Hand bearbeiten. App-Emojis gehören genau einer",
        "Anwendung, deshalb sind das Kopien der Emojis des University",
        "Bots unter eigenen IDs, nicht dieselben.",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "EMOJIS: dict[str, str] = {",
    ]
    for name in sorted(mapping):
        lines.append(f'    "{name}": "{mapping[name]}",')
    lines += [
        "}",
        "",
        "",
        'def emoji(name: str, fallback: str = "") -> str:',
        '    """Ein Emoji, oder ``fallback`` wenn es das nicht gibt.',
        "",
        "    Nie eine Ausnahme: ein fehlendes Emoji darf eine Antwort nicht",
        "    verhindern. Ohne Rückfalltext bleibt schlicht nichts stehen —",
        "    besser als ein roher ``<:name:123>``-Platzhalter im Satz.",
        '    """',
        "",
        "    return EMOJIS.get(name, fallback)",
        "",
    ]
    OUT_FILE.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true",
                        help="wirklich hochladen und ui/emojis.py schreiben")
    parser.add_argument("--source", type=Path, default=SOURCE_FILE)
    args = parser.parse_args()
    return asyncio.run(run(args.write, args.source))


if __name__ == "__main__":
    sys.exit(main())
