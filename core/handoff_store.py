"""Zwei Speicher fuer den Partner-Handshake.

:class:`PendingHandoffs`
    Kurzlebig, nur im Arbeitsspeicher. Haelt Server, deren OAuth-Callback
    eingetroffen ist, bis ``on_guild_join`` sie abholt. Nach einer Stunde ist
    ein Eintrag ohnehin wertlos — ihn beim Neustart zu verlieren ist sicherer,
    als einen veralteten zu verwenden.

:class:`SetupLedger`
    Dauerhaft auf der Platte. Merkt sich, auf welchen Servern das Template
    schon lief. Wird der Bot entfernt und wieder hinzugefuegt, richtet er
    nicht ein zweites Mal alles ein.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from pathlib import Path

from .handshake import MAX_AGE, Handoff

LOGGER = logging.getLogger("architect.handoff")

__all__ = ["PendingHandoffs", "SetupLedger"]


class PendingHandoffs:
    """Vorgemerkte Server zwischen Callback und Guild-Join."""

    def __init__(self, ttl: int = MAX_AGE) -> None:
        self.ttl = ttl
        self._lock = threading.Lock()
        self._entries: dict[int, tuple[Handoff, float]] = {}

    def add(self, handoff: Handoff) -> None:
        with self._lock:
            self._prune()
            self._entries[handoff.guild_id] = (handoff, time.monotonic())
        LOGGER.info("Handoff vorgemerkt für Guild %s", handoff.guild_id)

    def pop(self, guild_id: int) -> Handoff | None:
        """Eintrag entnehmen. Jeder Handoff wird hoechstens einmal genutzt."""

        with self._lock:
            self._prune()
            entry = self._entries.pop(guild_id, None)
        return entry[0] if entry else None

    def peek(self, guild_id: int) -> Handoff | None:
        with self._lock:
            self._prune()
            entry = self._entries.get(guild_id)
        return entry[0] if entry else None

    def discard(self, guild_id: int) -> None:
        with self._lock:
            self._entries.pop(guild_id, None)

    def _prune(self) -> None:
        """Abgelaufene Eintraege entfernen. Aufrufer haelt den Lock."""

        now = time.monotonic()
        stale = [
            guild_id
            for guild_id, (_, added) in self._entries.items()
            if now - added > self.ttl
        ]
        for guild_id in stale:
            del self._entries[guild_id]

    def __len__(self) -> int:
        with self._lock:
            self._prune()
            return len(self._entries)

    def __contains__(self, guild_id: object) -> bool:
        # ``in`` darf mit allem aufgerufen werden, nicht nur mit int-artigem.
        # Alles, was sich nicht als Guild-ID lesen laesst, ist schlicht nicht
        # enthalten — eine Exception waere hier das falsche Signal.
        if not isinstance(guild_id, (int, str)):
            return False
        try:
            return self.peek(int(guild_id)) is not None
        except ValueError:
            return False


class SetupLedger:
    """Dauerhafte Liste der Server, auf denen das Template schon lief.

    Schreibt atomar (``os.replace``), damit ein Absturz mitten im Schreiben
    die Datei nicht zerstoert und dadurch alle Server erneut eingerichtet
    wuerden.
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()
        self._entries: dict[int, dict] = {}
        self._load()

    # ---------------------------------------------------------------- API --
    def was_set_up(self, guild_id: int) -> bool:
        with self._lock:
            return guild_id in self._entries

    def record(self, guild_id: int, *, template: str, source: str) -> None:
        with self._lock:
            self._entries[guild_id] = {
                "template": template,
                "source": source,
                "at": int(time.time()),
            }
            self._persist()
        LOGGER.info("Setup vermerkt: Guild %s, Vorlage %s", guild_id, template)

    def details(self, guild_id: int) -> dict | None:
        with self._lock:
            entry = self._entries.get(guild_id)
            return dict(entry) if entry else None

    def forget(self, guild_id: int) -> bool:
        """Vermerk loeschen, damit bewusst erneut eingerichtet werden kann."""

        with self._lock:
            existed = self._entries.pop(guild_id, None) is not None
            if existed:
                self._persist()
        return existed

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)

    # ---------------------------------------------------------------- I/O --
    def _load(self) -> None:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return
        except (OSError, json.JSONDecodeError):
            LOGGER.warning(
                "Setup-Register %s ist unlesbar — starte ohne Vermerke. "
                "Bereits eingerichtete Server könnten erneut aufgebaut werden.",
                self.path,
            )
            return

        for key, value in (raw or {}).items():
            try:
                self._entries[int(key)] = value if isinstance(value, dict) else {}
            except (TypeError, ValueError):
                continue

        if self._entries:
            LOGGER.info("%d bereits eingerichtete Server geladen", len(self._entries))

    def _persist(self) -> None:
        """Aufrufer haelt den Lock."""

        payload = {str(key): value for key, value in self._entries.items()}
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            os.replace(tmp, self.path)
        except OSError:
            LOGGER.warning("Setup-Register konnte nicht gespeichert werden: %s", self.path)
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
