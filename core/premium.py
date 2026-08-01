"""Premium unlock store.

Security notes:

* The key itself is **never** written to disk — only the resulting unlock.
* Comparison uses :func:`hmac.compare_digest` to avoid leaking the key length
  or prefix through timing differences.
* Writes are atomic (``os.replace``) so a crash mid-write cannot corrupt the
  store and revoke everybody's access.
"""

from __future__ import annotations

import hmac
import json
import logging
import os
import threading
from collections.abc import Iterable
from pathlib import Path

LOGGER = logging.getLogger("architect.premium")

__all__ = ["PremiumStore"]


class PremiumStore:
    """Tracks which ``(guild_id, user_id)`` pairs unlocked premium."""

    def __init__(
        self,
        path: Path,
        *,
        keys: Iterable[str],
        guild_wide: bool = False,
    ) -> None:
        self.path = Path(path)
        self.guild_wide = guild_wide
        # ``key.strip()``: Ein Key aus reinen Leerzeichen ist keiner. Die
        # Pruefung in :meth:`verify` lehnt ihn ohnehin ab — wuerde er hier
        # stehen bleiben, meldete :attr:`is_configured` faelschlich True und
        # die Startwarnung bliebe aus, obwohl niemand freischalten kann.
        self._keys = tuple(key for key in keys if key and key.strip())
        self._lock = threading.Lock()
        self._users: set[tuple[int, int]] = set()
        self._guilds: set[int] = set()
        self._load()

    # ------------------------------------------------------------ storage ---
    @property
    def storage_is_persistent(self) -> bool:
        """
        Liegt der Store auf etwas, das ein Redeploy ueberlebt?

        Verglichen wird mit dem *Elternordner*, nicht mit "/": ein Mount
        erscheint als anderes Geraet als das Verzeichnis, in dem er
        haengt. Der Vergleich mit dem Wurzeldateisystem geht in einem
        Container daneben, weil / dort selbst ein Overlay ist.

        Ohne Volume ist jede Freischaltung nach dem naechsten Deploy weg
        — und zwar lautlos. Genau deshalb wird beim Start darauf
        hingewiesen.
        """

        directory = self.path.parent
        try:
            if not directory.is_dir():
                return False
            parent = directory.parent
            return directory.stat().st_dev != parent.stat().st_dev
        except OSError:
            return False

    def log_storage_state(self) -> None:
        """Beim Start sagen, ob die Freischaltungen bestehen bleiben.

        Railway zeigt beim Mounten nur den Host-Pfad an, nicht den Pfad
        im Container. Ob das Volume wirklich dort haengt, wo dieser Bot
        schreibt, sieht man sonst erst, wenn nach einem Deploy alle
        Freischaltungen fehlen.
        """

        if self.storage_is_persistent:
            LOGGER.info(
                "Premium-Store liegt auf einem Volume (%s) — "
                "Freischaltungen ueberleben ein Redeploy",
                self.path,
            )
        else:
            LOGGER.warning(
                "Premium-Store liegt NICHT auf einem Volume (%s) — alle "
                "Freischaltungen sind nach dem naechsten Deploy weg. "
                "In Railway unter Settings -> Volumes den Mount path "
                "auf %s setzen.",
                self.path,
                self.path.parent,
            )

    # --------------------------------------------------------------- keys ---
    @property
    def is_configured(self) -> bool:
        """Ist ueberhaupt ein Key hinterlegt?

        Ohne Key kann niemand freischalten. Das ist der sichere Zustand, aber
        er soll beim Start sichtbar sein statt still zu ueberraschen.
        """

        return bool(self._keys)

    def verify(self, candidate: str) -> bool:
        """Constant-time check of a user supplied key.

        Ist kein Key konfiguriert, schlaegt jede Eingabe fehl: ``self._keys``
        ist dann leer und die Schleife laeuft ins Leere. Fail-Closed.
        """

        supplied = candidate.strip()
        if not supplied:
            return False
        # Always compare against every key so the runtime does not reveal which
        # key matched (or how many are configured).
        matched = False
        for key in self._keys:
            if hmac.compare_digest(supplied.casefold(), key.strip().casefold()):
                matched = True
        return matched

    # -------------------------------------------------------------- state ---
    def has_access(self, guild_id: int | None, user_id: int) -> bool:
        with self._lock:
            if guild_id is not None and guild_id in self._guilds:
                return True
            return (guild_id or 0, user_id) in self._users

    def grant(self, guild_id: int | None, user_id: int) -> None:
        with self._lock:
            self._users.add((guild_id or 0, user_id))
            if self.guild_wide and guild_id is not None:
                self._guilds.add(guild_id)
            self._persist()

    def revoke(self, guild_id: int | None, user_id: int) -> None:
        with self._lock:
            self._users.discard((guild_id or 0, user_id))
            self._persist()

    @property
    def unlock_count(self) -> int:
        with self._lock:
            return len(self._users)

    # ---------------------------------------------------------------- i/o ---
    def _load(self) -> None:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return
        except (OSError, json.JSONDecodeError):
            LOGGER.warning(
                "Premium-Store %s ist unlesbar — starte ohne gespeicherte Freischaltungen",
                self.path,
            )
            return

        users = raw.get("users", []) if isinstance(raw, dict) else raw
        for entry in users or []:
            try:
                guild_id, user_id = entry
                self._users.add((int(guild_id), int(user_id)))
            except (TypeError, ValueError):
                continue

        if isinstance(raw, dict):
            for guild_id in raw.get("guilds", []) or []:
                try:
                    self._guilds.add(int(guild_id))
                except (TypeError, ValueError):
                    continue

        LOGGER.info("%d Premium-Freischaltungen geladen", len(self._users))

    def _persist(self) -> None:
        payload = {
            "users": sorted([list(pair) for pair in self._users]),
            "guilds": sorted(self._guilds),
        }
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            os.replace(tmp, self.path)
        except OSError:
            LOGGER.warning("Premium-Store konnte nicht gespeichert werden: %s", self.path)
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
