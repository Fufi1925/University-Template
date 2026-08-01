"""Emojis beim Start uebernehmen — wie beim University Bot.

App-Emojis gehoeren genau einer Anwendung. Discord sagt es deutlich:

    "An application can own up to 2000 emojis that can only be used by
     that app."
    https://docs.discord.com/developers/resources/emoji

Ein ``<:zbot:1530375453142159521>`` aus dem University Bot erscheint bei
uns also nicht als Bild, sondern als roher Text mitten im Satz. Genau
dieser Fehler war dort schon einmal live, als vier Emojis auf geloeschte
IDs zeigten.

Die Bilder selbst liegen offen auf ``cdn.discordapp.com`` und brauchen
keinen Token. Beim Start laedt dieser Sync also alles herunter, was noch
fehlt, und legt es unter *unserer* App an. Namen bleiben gleich, die IDs
sind zwangslaeufig neue.

Gesteuert ueber ``EMOJI_SYNC``:

    EMOJI_SYNC="true"   laeuft bei jedem Start (Standard)
    EMOJI_SYNC="false"  wird uebersprungen

Nach dem ersten Lauf ist nichts mehr zu tun: bereits vorhandene Namen
werden erkannt und nur noch eingelesen. Der Bot startet dabei *nicht*
neu — anders als der University Bot, der eine Quelldatei umschreibt und
sie neu laden muss. Hier landen die IDs im Speicher, das reicht.

Faellt der Sync aus, laeuft der Bot normal weiter und benutzt die
Unicode-Rueckfaelle. Ein Emoji ist Zierde; daran darf kein Start
scheitern.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
from pathlib import Path

import aiohttp

LOGGER = logging.getLogger("architect.emojis")

__all__ = ["sync_emojis"]

BASE_DIR = Path(__file__).resolve().parent.parent
SOURCE_FILE = BASE_DIR / "tools" / "emoji_source.json"

API = "https://discord.com/api/v10"
CDN = "https://cdn.discordapp.com/emojis"

# Discord erlaubt 2000 pro App. Der Deckel hier faengt eine kaputte
# Quelldatei ab, bevor sie tausende Uploads ausloest.
MAX_UPLOADS = 300

# Discord bremst Uploads. Ohne Pause endet ein Lauf in 429ern.
UPLOAD_PAUSE = 0.4

# Discord akzeptiert nur diese Zeichen im Namen. Ein ungueltiger Name
# laesst den Upload mit 400 scheitern.
VALID_NAME = re.compile(r"[A-Za-z0-9_]{2,32}")


def _load_source() -> list[dict]:
    """Die Liste der zu uebernehmenden Emojis."""

    try:
        data = json.loads(SOURCE_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        LOGGER.warning("%s fehlt — keine Emojis zu uebernehmen", SOURCE_FILE)
        return []
    except (OSError, json.JSONDecodeError) as exc:
        LOGGER.warning("%s ist unlesbar (%s)", SOURCE_FILE, exc)
        return []

    out = []
    for entry in data if isinstance(data, list) else []:
        name = str(entry.get("name", "")).strip()
        emoji_id = str(entry.get("id", "")).strip()
        if not VALID_NAME.fullmatch(name) or not emoji_id.isdigit():
            LOGGER.warning("Emoji uebersprungen (ungueltig): %r", entry)
            continue
        out.append({
            "name": name,
            "id": emoji_id,
            "animated": bool(entry.get("animated")),
        })
    return out


async def _fetch_image(session: aiohttp.ClientSession, emoji_id: str,
                       animated: bool) -> tuple[bytes | None, str]:
    """Das Bild holen.

    Die Endung ist nur eine Vermutung: ein als animiert eingetragenes
    Emoji ist es nicht zwangslaeufig, und ein ``.gif`` auf ein statisches
    Bild liefert 415. Also der Reihe nach durchprobieren.
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


async def sync_emojis(token: str, *, enabled: bool = True) -> dict[str, str]:
    """
    Emojis der App abgleichen und die fertige Zuordnung zurueckgeben.

    Wirft nie. Jeder Fehlerfall endet mit dem, was bis dahin bekannt ist
    — im schlimmsten Fall ein leeres Dict, und dann greifen ueberall die
    Unicode-Rueckfaelle.
    """

    if not enabled:
        LOGGER.info("EMOJI_SYNC ist aus — es werden Unicode-Zeichen benutzt.")
        return {}

    if not token:
        LOGGER.warning("Kein Token — Emoji-Sync uebersprungen.")
        return {}

    wanted = _load_source()
    if not wanted:
        return {}

    if len(wanted) > MAX_UPLOADS:
        LOGGER.warning(
            "%d Emojis in der Quelle, mehr als das Limit von %d — abgebrochen.",
            len(wanted), MAX_UPLOADS,
        )
        return {}

    mapping: dict[str, str] = {}

    try:
        headers = {"Authorization": f"Bot {token}"}
        timeout = aiohttp.ClientTimeout(total=120)
        async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
            async with session.get(f"{API}/users/@me") as response:
                if response.status != 200:
                    LOGGER.warning(
                        "Emoji-Sync: Login fehlgeschlagen (HTTP %s)", response.status
                    )
                    return {}
                app_id = (await response.json())["id"]

            async with session.get(f"{API}/applications/{app_id}/emojis") as response:
                if response.status != 200:
                    LOGGER.warning(
                        "Emoji-Sync: Liste nicht lesbar (HTTP %s)", response.status
                    )
                    return {}
                payload = await response.json()

            items = payload.get("items", payload) if isinstance(payload, dict) else payload
            have = {item["name"]: item for item in items}

            uploaded = failed = 0

            for entry in wanted:
                name = entry["name"]

                # Schon da: nur uebernehmen. Discord lehnt doppelte
                # Namen ohnehin ab.
                if name in have:
                    item = have[name]
                    prefix = "a" if item.get("animated") else ""
                    mapping[name] = f"<{prefix}:{item['name']}:{item['id']}>"
                    continue

                image, mime = await _fetch_image(
                    session, entry["id"], entry["animated"]
                )
                if image is None:
                    LOGGER.warning(
                        "Emoji %s: Bild nicht ladbar (Quelle %s ist weg)",
                        name, entry["id"],
                    )
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
                        mapping[name] = f"<{prefix}:{item['name']}:{item['id']}>"
                        uploaded += 1
                    else:
                        text = (await response.text())[:120]
                        LOGGER.warning(
                            "Emoji %s abgelehnt (HTTP %s): %s",
                            name, response.status, text,
                        )
                        failed += 1

                await asyncio.sleep(UPLOAD_PAUSE)

    except asyncio.CancelledError:
        raise
    except Exception as exc:
        LOGGER.warning("Emoji-Sync fehlgeschlagen (%s) — Unicode wird benutzt.", exc)
        return mapping

    if uploaded or failed:
        LOGGER.info(
            "Emoji-Sync: %d neu, %d vorhanden, %d fehlgeschlagen",
            uploaded, len(mapping) - uploaded, failed,
        )
    else:
        LOGGER.info("Emoji-Sync: %d Emojis, alles vorhanden", len(mapping))

    return mapping
