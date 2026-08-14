"""Premium unlock store.

Security notes:

* The key itself is **never** written to disk — only the resulting unlock.
* Comparison uses :func:`hmac.compare_digest` to avoid leaking the key length
  or prefix through timing differences.
* Writes are atomic (``os.replace``) so a crash mid-write cannot corrupt the
  store and revoke everybody's access.

Zusaetzlich vergibt der Bot **persoenliche Einmal-Keys**: Im Startmenue
schickt „Jetzt mehr Templates mit Premium freischalten" dem Nutzer per DM
einen Key, den er im Key-Fenster einloest. Auch diese Keys landen nie im
Klartext auf der Platte — gespeichert wird nur ihr SHA-256-Hash, gebunden
an das Konto, mit Ablaufdatum und einmaliger Verwendung.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import secrets
import threading
import time
from collections.abc import Iterable
from pathlib import Path

LOGGER = logging.getLogger("architect.premium")

__all__ = ["PERSONAL_KEY_TTL", "PremiumStore"]

#: Wie lange ein per DM ausgegebener Key gueltig bleibt. Lang genug, dass
#: niemand in Zeitnot geraet, kurz genug, dass herumliegende Keys wertlos
#: werden.
PERSONAL_KEY_TTL = 7 * 24 * 3600


def _normalise_key(candidate: str) -> str:
    """Einen Key auf eine Vergleichsform bringen.

    Bindestriche und Leerzeichen sind nur Formatierung — wer den Key aus
    der DM kopiert, bekommt die Gruppen mit, wer ihn abtippt, laesst sie
    vielleicht weg. Beides meint denselben Key.
    """

    return candidate.strip().casefold().replace("-", "").replace(" ", "")


def _digest(normalised: str) -> str:
    """SHA-256 eines normalisierten Keys — nur das wird gespeichert."""

    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()


def _format_key(raw: str) -> str:
    """Einen rohen Key in lesbare Vierergruppen bringen: ``ABCD-EFGH-…``."""

    return "-".join(raw[i : i + 4] for i in range(0, len(raw), 4))


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
        #: (guild, user) -> Ablaufzeitpunkt. Persoenliche Keys sind nach
        #: sieben Tagen vorbei; Master-Keys bleiben dauerhaft und stehen
        #: deshalb in ``_users``, nicht hier.
        self._expiring: dict[tuple[int, int], float] = {}
        #: Digest -> {user, issued, expires}. Nur Hashes, nie Klartext.
        self._pending: dict[str, dict] = {}
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

    # ------------------------------------------------------- personal keys --
    def issue_key(self, user_id: int) -> str:
        """Einen persoenlichen Einmal-Key fuer ``user_id`` ausgeben.

        Der Key kommt per DM beim Nutzer an und wird im Key-Fenster
        eingeloest. Gespeichert wird nur sein Hash — der Klartext existiert
        ausschliesslich in der Direktnachricht.

        Ein neuer Key ersetzt die offenen Keys desselben Kontos: niemand
        soll sich durch wiederholtes Klicken einen Vorrat anlegen koennen.
        """

        # 24 Hex-Zeichen = 96 Bit Zufall, vier Vierergruppen. Bewusst Hex
        # statt urlsafe Base64: deren Alphabet enthaelt Bindestriche, und
        # die sind hier der Trenner — ein Key mit Trennern im Alphabet
        # waere unlesbar.
        raw = secrets.token_hex(12)
        normalised = _normalise_key(raw)
        now = time.time()
        with self._lock:
            self._pending = {
                digest: entry
                for digest, entry in self._pending.items()
                if entry["user"] != user_id and entry["expires"] > now
            }
            self._pending[_digest(normalised)] = {
                "user": int(user_id),
                "issued": int(now),
                "expires": int(now + PERSONAL_KEY_TTL),
            }
            self._persist()
        return _format_key(raw)

    def redeem_key(self, candidate: str, *, user_id: int) -> str | None:
        """Einen eingegebenen Key einloesen.

        Zwei Wege, in dieser Reihenfolge:

        1. Der konfigurierte Master-Key — der klassische Weg, bei dem die
           Serverleitung einen Key ausgibt. Gilt dauerhaft.
        2. Ein persoenlicher Einmal-Key: er muss existieren, zu **diesem**
           Konto gehoeren, noch nicht abgelaufen sein — und wird beim
           Einloesen verbraucht. Ein weitergegebener Key hilft dem
           Empfaenger also nichts.

        Gibt ``\"master\"``, ``\"personal\"`` oder ``None`` zurueck — der
        Aufrufer entscheidet daran, ob die Freischaltung ein Ablaufdatum
        bekommt und an den University Bot gemeldet wird.
        """

        if self.verify(candidate):
            return "master"

        digest = _digest(_normalise_key(candidate))
        with self._lock:
            entry = self._pending.get(digest)
            if entry is None or entry["user"] != int(user_id):
                return None
            if time.time() > entry["expires"]:
                return None
            del self._pending[digest]
            self._persist()
        return "personal"

    def restore_key(self, candidate: str, *, user_id: int) -> bool:
        """Einen gerade eingeloesten Key wieder gueltig machen.

        ``redeem_key`` verbraucht den Key sofort -- richtig so, sonst
        koennte man ihn zweimal einreichen. Wird die Freischaltung
        danach aber doch abgelehnt (der University Bot meldet, dass die
        Probewoche schon verbraucht ist), waere der Key ersatzlos weg:
        der Nutzer haette nichts bekommen und trotzdem seinen Key
        verloren. Deshalb wird er hier zurueckgelegt.

        Die urspruengliche Gueltigkeit wird nicht verlaengert: der Key
        laeuft ab, wann er ohnehin abgelaufen waere.
        """

        digest = _digest(_normalise_key(candidate))
        with self._lock:
            if digest in self._pending:
                return False
            self._pending[digest] = {
                "user": int(user_id),
                "issued": int(time.time()),
                "expires": int(time.time() + PERSONAL_KEY_TTL),
            }
            self._persist()
        return True

    @property
    def pending_key_count(self) -> int:
        """Wie viele Einmal-Keys derzeit offen sind — fuer Tests und Status."""

        with self._lock:
            return len(self._pending)

    # -------------------------------------------------------------- state ---
    def has_access(self, guild_id: int | None, user_id: int) -> bool:
        with self._lock:
            if guild_id is not None and guild_id in self._guilds:
                return True
            key = (guild_id or 0, user_id)
            if key in self._users:
                return True

            expires = self._expiring.get(key)
            if expires is None:
                return False
            if time.time() >= expires:
                # Abgelaufene Freischaltungen fallen beim ersten Anfassen
                # weg — ohne eigenen Aufraeumlauf.
                del self._expiring[key]
                self._persist()
                return False
            return True

    def access_expires(self, guild_id: int | None, user_id: int) -> float | None:
        """Wann laeuft die Freischaltung ab — ``None`` heisst dauerhaft.

        Das Dashboard des University Bots zeigt auf dieser Grundlage
        „7 Tage Premium" statt eines unbefristeten Freischalters.
        """

        with self._lock:
            return self._expiring.get((guild_id or 0, user_id))

    def grant(
        self,
        guild_id: int | None,
        user_id: int,
        *,
        expires_at: float | None = None,
    ) -> None:
        """Freischalten — dauerhaft, oder mit Ablaufdatum.

        ``expires_at`` ist ein Unix-Zeitstempel. Persoenliche Keys laufen
        nach sieben Tagen ab; Master-Keys bleiben dauerhaft. Eine
        befristete Freischaltung schaltet bewusst **nicht** den ganzen
        Server frei — sie gehoert einem Konto, nicht einer Community.
        """

        with self._lock:
            key = (guild_id or 0, user_id)
            if expires_at is None:
                self._users.add(key)
                self._expiring.pop(key, None)
                if self.guild_wide and guild_id is not None:
                    self._guilds.add(guild_id)
            else:
                self._users.discard(key)
                self._expiring[key] = expires_at
            self._persist()

    def revoke(self, guild_id: int | None, user_id: int) -> None:
        with self._lock:
            key = (guild_id or 0, user_id)
            self._users.discard(key)
            self._expiring.pop(key, None)
            self._persist()

    def revoke_user(self, user_id: int) -> int:
        """
        Jede Freischaltung dieses Kontos entfernen, serveruebergreifend.

        :meth:`revoke` braucht die Server-ID, die beim Widerruf ueber das
        Dashboard niemand kennt: dort wird eine *Lizenz* gesperrt, und
        die gehoert einem Konto, nicht einem Server. Ohne diese Methode
        blieben alle lokalen Freischaltungen bestehen und der Nutzer
        haette weiter Premium, obwohl die Lizenz weg ist.

        Gibt zurueck, wie viele Eintraege entfernt wurden.
        """

        user_id = int(user_id)
        with self._lock:
            gone = {pair for pair in self._users if pair[1] == user_id}
            gone |= {pair for pair in self._expiring if pair[1] == user_id}
            if not gone:
                return 0
            self._users -= gone
            for pair in gone:
                self._expiring.pop(pair, None)

            # guild_wide: eine Freischaltung galt fuer den ganzen Server.
            # Sie muss mit, sonst behaelt der Server Premium, obwohl
            # niemand mehr eine gueltige Lizenz hat.
            for guild_id, _ in gone:
                if guild_id and guild_id in self._guilds:
                    self._guilds.discard(guild_id)

            self._persist()
            return len(gone)

    @property
    def unlock_count(self) -> int:
        with self._lock:
            return len(self._users) + len(self._expiring)

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

            for digest, entry in (raw.get("pending", {}) or {}).items():
                try:
                    user = int(entry["user"])
                    expires = float(entry["expires"])
                except (KeyError, TypeError, ValueError):
                    continue
                self._pending[str(digest)] = {
                    "user": user,
                    "issued": float(entry.get("issued", 0)),
                    "expires": expires,
                }

            for entry in raw.get("expires", []) or []:
                try:
                    guild_id, user_id, expires = entry
                    self._expiring[(int(guild_id), int(user_id))] = float(expires)
                except (TypeError, ValueError):
                    continue

        LOGGER.info("%d Premium-Freischaltungen geladen", self.unlock_count)

    def _persist(self) -> None:
        payload = {
            "users": sorted([list(pair) for pair in self._users]),
            "guilds": sorted(self._guilds),
            "pending": dict(sorted(self._pending.items())),
            "expires": sorted(
                [[guild_id, user_id, expires] for (guild_id, user_id), expires in self._expiring.items()]
            ),
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
