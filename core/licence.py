"""Lizenz-Abfrage beim University Bot.

Bisher gab es genau einen Master-Key: derselbe Text schaltet jeden frei,
der ihn kennt. Wird er einmal weitergegeben, laesst er sich nur noch
zuruecknehmen, indem man ihn fuer *alle* aendert.

Stattdessen kauft man jetzt beim University Bot einen persoenlichen Key,
loest ihn dort ein, und dieser Bot fragt nur noch nach:

    GET <MAIN_BOT_URL>/api/v1/premium/check/<user_id>
    X-Partner-Token: <PREMIUM_PARTNER_TOKEN>

Zwei Grundsaetze:

**Fail-closed.** Ist der University Bot nicht erreichbar, das Token
falsch oder die Antwort unlesbar, gilt: kein Premium. Ein Ausfall darf
niemals versehentlich freischalten.

**Zwischenspeichern.** Die Abfrage haengt an Interaktionen, die Discord
nach drei Sekunden als tot betrachtet. Eine Antwort wird deshalb kurz
gemerkt, damit nicht jeder Klick einen HTTP-Aufruf ausloest.

Der alte Master-Key bleibt bestehen. Ist ``MAIN_BOT_URL`` nicht gesetzt,
verhaelt sich der Bot exakt wie vorher — bestehende Installationen
brechen also nicht.
"""

from __future__ import annotations

import logging
import time

import aiohttp

LOGGER = logging.getLogger("architect.licence")

__all__ = ["LicenceClient"]

#: Wie lange eine Antwort gilt. Kurz genug, dass ein frisch eingeloester
#: Key schnell wirkt, lang genug, dass Klicken keine Anfrageflut wird.
CACHE_TTL = 300.0

#: Discord verwirft eine Interaktion nach drei Sekunden. Bleibt der
#: University Bot laenger stumm, ist die Antwort ohnehin wertlos.
TIMEOUT = 4.0


class LicenceClient:
    """Fragt den University Bot, ob ein Discord-Konto Premium hat."""

    def __init__(self, base_url: str, token: str) -> None:
        # Ein abschliessender Schraegstrich wuerde die URL verdoppeln.
        self.base_url = (base_url or "").strip().rstrip("/")
        self.token = (token or "").strip()
        self._cache: dict[int, tuple[float, bool]] = {}

    @property
    def is_configured(self) -> bool:
        """Beides noetig — eine URL ohne Token wird nur 401 liefern."""

        return bool(self.base_url and self.token)

    def forget(self, user_id: int) -> None:
        """Zwischenspeicher fuer ein Konto leeren."""

        self._cache.pop(int(user_id), None)

    async def has_premium(self, user_id: int) -> bool:
        """
        Hat dieses Konto Premium?

        Wirft nie. Jeder Fehler wird zu ``False``, damit ein Ausfall des
        University Bots hier keine Interaktion zerreisst.
        """

        if not self.is_configured:
            return False

        user_id = int(user_id)
        now = time.monotonic()

        cached = self._cache.get(user_id)
        if cached and cached[0] > now:
            return cached[1]

        url = f"{self.base_url}/api/v1/premium/check/{user_id}"
        granted = False
        try:
            timeout = aiohttp.ClientTimeout(total=TIMEOUT)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(
                    url, headers={"X-Partner-Token": self.token}
                ) as response:
                    if response.status == 200:
                        payload = await response.json()
                        granted = bool(payload.get("premium"))
                    elif response.status in (401, 403):
                        LOGGER.warning(
                            "Lizenzabfrage abgelehnt (HTTP %s) — stimmt "
                            "PREMIUM_PARTNER_TOKEN auf beiden Seiten?",
                            response.status,
                        )
                    elif response.status == 503:
                        LOGGER.warning(
                            "Der University Bot hat kein PREMIUM_PARTNER_TOKEN "
                            "gesetzt — die Lizenzabfrage ist dort deaktiviert."
                        )
                    else:
                        LOGGER.warning(
                            "Lizenzabfrage: unerwarteter Status %s", response.status
                        )
        except aiohttp.ClientError as exc:
            LOGGER.warning("Lizenzabfrage fehlgeschlagen: %s", exc)
        except Exception as exc:
            LOGGER.warning("Lizenzabfrage unerwartet fehlgeschlagen: %s", exc)

        # Auch ein "nein" wird gemerkt, sonst fragt jeder Klick eines
        # Nutzers ohne Premium erneut an.
        self._cache[user_id] = (now + CACHE_TTL, granted)
        return granted
