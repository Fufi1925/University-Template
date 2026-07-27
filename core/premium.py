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
from pathlib import Path
from typing import Iterable

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
        self._keys = tuple(key for key in keys if key)
        self._lock = threading.Lock()
        self._users: set[tuple[int, int]] = set()
        self._guilds: set[int] = set()
        self._load()

    # --------------------------------------------------------------- keys ---
    def verify(self, candidate: str) -> bool:
        """Constant-time check of a user supplied key."""

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
