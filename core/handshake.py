"""Partner-Handshake: signierte OAuth-``state``-Token pruefen.

Ein Partner-Bot (*University Bot*) schickt Server zu uns. Damit unser Bot
weiss, dass ein Beitritt von dort stammt, haengt der Partner an den
Einladungslink einen signierten ``state``-Wert. Discord reicht ihn
unveraendert an unsere Redirect-URI weiter.

Warum die Signatur nicht verhandelbar ist
-----------------------------------------
Ohne sie koennte jeder ``?state=university-bot`` an seinen eigenen
Einladungslink haengen und uns dazu bringen, einen fremden Server als
Partner-Server zu behandeln — inklusive automatischem Umbau. Die Signatur
ist das Einzige, was einen echten Handoff von einer Faelschung trennt.

Aufbau des Tokens::

    <body>.<signature>

    body       URL-sicheres Base64 ohne Padding eines JSON-Objekts
    signature  URL-sicheres Base64 ohne Padding von
               HMAC-SHA256(secret, body als ASCII)

Ist ``PARTNER_HANDSHAKE_SECRET`` nicht gesetzt, gilt **kein** Token als
gueltig. Lieber gar keine Automatik als eine manipulierbare.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import time
from dataclasses import dataclass

LOGGER = logging.getLogger("architect.handshake")

__all__ = [
    "SOURCE",
    "MAX_AGE",
    "Handoff",
    "read_state",
    "sign_state",
    "is_enabled",
]

#: Kennung des Partners im Token. Aendert der Partner seinen Wert, muss er
#: hier mitgeaendert werden — sonst wird jeder Link abgelehnt.
SOURCE = "university-bot"

#: Ein Token ist eine Stunde lang gueltig. Danach ist der Handoff wertlos:
#: der Nutzer hat die Einladung offensichtlich nicht abgeschlossen.
MAX_AGE = 3600


def _secret() -> bytes:
    """Das Secret bei jedem Aufruf frisch lesen.

    Nicht auf Modulebene cachen: Tests setzen die Variable zur Laufzeit, und
    ein einmal eingefrorenes leeres Secret waere schwer zu erkennen.
    """

    return os.getenv("PARTNER_HANDSHAKE_SECRET", "").encode()


def is_enabled() -> bool:
    """Ist die Automatik ueberhaupt scharf geschaltet?"""

    return bool(_secret())


def _unb64(text: str) -> bytes:
    """URL-sicheres Base64 ohne Padding dekodieren."""

    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _b64(raw: bytes) -> str:
    """Bytes als URL-sicheres Base64 ohne Padding."""

    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


@dataclass(frozen=True, slots=True)
class Handoff:
    """Ein geprueftes Token — nur so kommt es aus :func:`read_state` heraus."""

    guild_id: int
    user_id: int
    issued_at: int
    source: str
    guild_name: str | None = None

    @property
    def age(self) -> float:
        return time.time() - self.issued_at


def read_state(state: str | None) -> Handoff | None:
    """Token pruefen. Gibt ``None`` zurueck, sobald irgendetwas nicht stimmt.

    Die Reihenfolge ist bewusst gewaehlt: erst die Form, dann die Signatur,
    dann erst der Inhalt. So wird nie JSON aus einer Quelle geparst, deren
    Echtheit nicht feststeht.
    """

    secret = _secret()
    if not secret:
        # Ohne Secret ist die Automatik aus. Kein Token gilt.
        return None
    if not state or "." not in state:
        return None

    body, _, signature = state.partition(".")
    if not body or not signature:
        return None

    try:
        expected = _b64(
            hmac.new(secret, body.encode("ascii"), hashlib.sha256).digest()
        )
        # compare_digest statt ==: konstante Laufzeit. Ein normaler Vergleich
        # bricht beim ersten falschen Zeichen ab und verraet damit ueber die
        # Antwortzeit, wie weit man richtig geraten hat.
        if not hmac.compare_digest(signature, expected):
            LOGGER.debug("Handshake: Signatur stimmt nicht")
            return None

        payload = json.loads(_unb64(body).decode("utf-8"))
    except Exception:
        # Kaputtes Base64, kaputtes JSON, Nicht-ASCII im Body — alles fuehrt
        # zum selben Ergebnis: nicht vertrauen.
        LOGGER.debug("Handshake: Token nicht lesbar", exc_info=True)
        return None

    if not isinstance(payload, dict):
        return None

    # Auch bei gueltiger Signatur: Der Partner muss der erwartete sein.
    # Teilen sich spaeter mehrere Partner ein Secret, ist src das Einzige,
    # was sie auseinanderhaelt.
    if payload.get("src") != SOURCE:
        LOGGER.debug("Handshake: unerwartete Quelle %r", payload.get("src"))
        return None

    try:
        issued = int(payload.get("t", 0))
        guild_id = int(payload.get("g", 0))
        user_id = int(payload.get("u", 0))
    except (TypeError, ValueError):
        return None

    if issued <= 0 or time.time() - issued > MAX_AGE:
        LOGGER.debug("Handshake: Token abgelaufen oder ohne Zeitstempel")
        return None

    if guild_id <= 0:
        return None

    guild_name = payload.get("guild_name")
    if guild_name is not None and not isinstance(guild_name, str):
        guild_name = None

    return Handoff(
        guild_id=guild_id,
        user_id=user_id,
        issued_at=issued,
        source=SOURCE,
        guild_name=guild_name,
    )


def sign_state(
    guild_id: int | str,
    user_id: int | str,
    *,
    issued_at: int | None = None,
    guild_name: str | None = None,
    secret: bytes | None = None,
) -> str:
    """Ein Token erzeugen.

    Der Bot braucht das im Betrieb nicht — der Partner signiert. Die Funktion
    existiert fuer Tests und damit das Format an genau einer Stelle definiert
    ist, statt in zwei Projekten auseinanderzulaufen.
    """

    key = secret if secret is not None else _secret()
    if not key:
        raise RuntimeError("PARTNER_HANDSHAKE_SECRET ist nicht gesetzt")

    payload: dict[str, object] = {
        "g": str(guild_id),
        "u": str(user_id),
        "t": int(issued_at if issued_at is not None else time.time()),
        "src": SOURCE,
    }
    if guild_name:
        payload["guild_name"] = guild_name

    body = _b64(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = _b64(hmac.new(key, body.encode("ascii"), hashlib.sha256).digest())
    return f"{body}.{signature}"
