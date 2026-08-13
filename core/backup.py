"""Backup der Serverstruktur als JSON-Datei.

``/template backup erstellen`` schreibt den aktuellen Stand des Servers —
Rollen, Kategorien, Kanaele, Berechtigungen — in eine lesbare JSON-Datei.
Sie ist ein Schnappschuss zum Aufheben und Wiederherstellen von Hand, kein
Ein-Klick-Restore: Zurueckspielen ist bewusst ein eigener, bedachter
Vorgang und nicht Teil dieses Bots.

Zwei Grundsaetze wie beim Premium-Store:

* **Atomar schreiben.** Erst eine ``.tmp``-Datei, dann ``os.replace`` — ein
  Absturz mitten im Schreiben hinterlaesst nie eine halbe Datei.
* **IDs als Strings.** Snowflakes sind 64-Bit-Zahlen; eine JSON-Zahl
  verliert die letzten Stellen.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .small_caps import slugify

__all__ = ["BACKUP_VERSION", "backup_filename", "capture_backup", "save_backup"]

#: Formatversion des Backups — wer spaeter einen Restore baut, erkennt daran,
#: mit welcher Struktur er es zu tun hat.
BACKUP_VERSION = 1


def _overwrites(channel: Any) -> dict[str, dict[str, int]]:
    """Overwrite-Map auf Rollen-/Benutzernamen umschluesseln."""

    result: dict[str, dict[str, int]] = {}
    for target, overwrite in getattr(channel, "overwrites", {}).items():
        name = getattr(target, "name", None)
        if name is None:
            name = f"id:{getattr(target, 'id', '?')}"
        allow, deny = overwrite.pair()
        result[name] = {
            "allow": int(allow.value),
            "deny": int(deny.value),
        }
    return result


def capture_backup(guild: Any) -> dict[str, Any]:
    """Den aktuellen Stand des Servers als Dictionary abbilden.

    Gelesen wird ausschliesslich ueber Attribute, die auch die Fakes in den
    Tests mitbringen — nichts davon geht an die API.
    """

    roles: list[dict[str, Any]] = []
    for role in sorted(guild.roles, key=lambda r: r.position, reverse=True):
        roles.append(
            {
                "id": str(role.id),
                "name": role.name,
                "position": role.position,
                "colour": int(getattr(role, "colour", 0)),
                "permissions": int(role.permissions.value),
                "hoist": bool(getattr(role, "hoist", False)),
                "mentionable": bool(getattr(role, "mentionable", False)),
                "managed": bool(getattr(role, "managed", False)),
                "default": bool(role.is_default()),
            }
        )

    channels: list[dict[str, Any]] = []
    for channel in sorted(guild.channels, key=lambda c: c.position):
        category = getattr(channel, "category", None)
        channels.append(
            {
                "id": str(channel.id),
                "name": channel.name,
                "type": getattr(channel.type, "name", str(getattr(channel, "type", ""))),
                "position": channel.position,
                "category": getattr(category, "name", None),
                "topic": getattr(channel, "topic", None),
                "slowmode": getattr(channel, "slowmode_delay", 0),
                "nsfw": bool(getattr(channel, "nsfw", False)),
                "user_limit": getattr(channel, "user_limit", 0),
                "overwrites": _overwrites(channel),
            }
        )

    now = datetime.now(UTC)
    return {
        "meta": {
            "version": BACKUP_VERSION,
            "captured_at": now.isoformat(timespec="seconds"),
            "guild": {
                "id": str(guild.id),
                "name": guild.name,
                "member_count": getattr(guild, "member_count", None),
            },
        },
        "roles": roles,
        "channels": channels,
    }


def backup_filename(guild: Any, when: datetime | None = None) -> str:
    """Dateiname mit Server-Slug und Zeitstempel."""

    moment = when or datetime.now(UTC)
    server = slugify(guild.name) or "server"
    return f"backup-{server}-{moment:%Y%m%d-%H%M%S}.json"


async def save_backup(guild: Any, directory: Path) -> Path:
    """Backup atomar in ``directory`` schreiben und den Pfad zurueckgeben."""

    directory.mkdir(parents=True, exist_ok=True)
    path = directory / backup_filename(guild)
    temporary = path.with_suffix(path.suffix + ".tmp")

    payload = json.dumps(capture_backup(guild), ensure_ascii=False, indent=2)
    temporary.write_text(payload + "\n", encoding="utf-8")
    os.replace(temporary, path)
    return path
