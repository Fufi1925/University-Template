"""Die Lizenzabfrage beim University Bot.

Bisher entschied ein einziger Master-Key ueber Premium: wer ihn kennt,
ist drin, und zuruecknehmen laesst er sich nur, indem man ihn fuer alle
aendert. Jetzt kann stattdessen ein persoenlicher Key beim University
Bot gekauft werden, und dieser Bot fragt dort nach.

Zwei Eigenschaften entscheiden darueber, ob das sicher ist, und beide
werden hier geprueft:

**Fail-closed.** Netzwerkfehler, falsches Token, kaputte Antwort, kein
Token konfiguriert — nichts davon darf Premium gewaehren. Der bequeme
Fehler waere hier der gefaehrliche.

**Kein Aufruf pro Klick.** Die Abfrage haengt an Discord-Interaktionen,
die nach drei Sekunden verfallen. Antworten werden deshalb kurz
gemerkt.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.licence import LicenceClient

USER = 1303627964734246944


class FakeResponse:
    def __init__(self, status: int, payload: dict | None = None,
                 broken: bool = False) -> None:
        self.status = status
        self._payload = payload or {}
        self._broken = broken

    async def json(self):
        if self._broken:
            raise ValueError("keine gueltige JSON-Antwort")
        return self._payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class FakeSession:
    """Zaehlt die Aufrufe, damit der Zwischenspeicher pruefbar wird."""

    def __init__(self, response=None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.calls: list[tuple[str, dict]] = []

    def get(self, url, headers=None, **kwargs):
        self.calls.append((url, headers or {}))
        if self.error is not None:
            raise self.error
        return self.response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


@pytest.fixture
def patched(monkeypatch):
    """Ersetzt aiohttp.ClientSession und gibt die Sitzung zurueck."""

    def apply(session: FakeSession):
        import core.licence as licence

        monkeypatch.setattr(
            licence.aiohttp, "ClientSession", lambda *a, **k: session
        )
        return session

    return apply


class TestConfiguration:
    def test_needs_both_url_and_token(self):
        assert not LicenceClient("", "").is_configured
        assert not LicenceClient("https://bot.example", "").is_configured
        # Eine URL ohne Token liefert nur 401 — das ist nicht konfiguriert.
        assert not LicenceClient("", "token").is_configured
        assert LicenceClient("https://bot.example", "token").is_configured

    def test_trailing_slash_does_not_double_up(self):
        client = LicenceClient("https://bot.example/", "token")
        assert client.base_url == "https://bot.example"

    async def test_unconfigured_never_grants(self, patched):
        session = patched(FakeSession(FakeResponse(200, {"premium": True})))
        client = LicenceClient("", "")

        assert await client.has_premium(USER) is False
        assert session.calls == [], "ohne Konfiguration darf nichts abgefragt werden"


class TestAnswers:
    async def test_premium_true_is_granted(self, patched):
        patched(FakeSession(FakeResponse(200, {"premium": True})))
        client = LicenceClient("https://bot.example", "token")

        assert await client.has_premium(USER) is True

    async def test_premium_false_is_refused(self, patched):
        patched(FakeSession(FakeResponse(200, {"premium": False})))
        client = LicenceClient("https://bot.example", "token")

        assert await client.has_premium(USER) is False

    async def test_the_token_is_sent(self, patched):
        session = patched(FakeSession(FakeResponse(200, {"premium": True})))
        client = LicenceClient("https://bot.example", "geheim")

        await client.has_premium(USER)

        url, headers = session.calls[0]
        assert url == f"https://bot.example/api/v1/premium/check/{USER}"
        assert headers.get("X-Partner-Token") == "geheim"


class TestFailClosed:
    """Jeder Fehlerfall muss "kein Premium" bedeuten."""

    @pytest.mark.parametrize("status", [401, 403, 404, 500, 502, 503])
    async def test_error_status_grants_nothing(self, patched, status):
        patched(FakeSession(FakeResponse(status, {"premium": True})))
        client = LicenceClient("https://bot.example", "token")

        assert await client.has_premium(USER) is False, (
            f"HTTP {status} hat Premium gewaehrt"
        )

    async def test_network_error_grants_nothing(self, patched):
        import aiohttp

        patched(FakeSession(error=aiohttp.ClientError("keine Verbindung")))
        client = LicenceClient("https://bot.example", "token")

        assert await client.has_premium(USER) is False

    async def test_unexpected_error_grants_nothing(self, patched):
        patched(FakeSession(error=RuntimeError("kaputt")))
        client = LicenceClient("https://bot.example", "token")

        # Wirft nicht: eine Interaktion darf daran nicht zerbrechen.
        assert await client.has_premium(USER) is False

    async def test_unreadable_answer_grants_nothing(self, patched):
        patched(FakeSession(FakeResponse(200, broken=True)))
        client = LicenceClient("https://bot.example", "token")

        assert await client.has_premium(USER) is False

    async def test_missing_field_grants_nothing(self, patched):
        patched(FakeSession(FakeResponse(200, {})))
        client = LicenceClient("https://bot.example", "token")

        assert await client.has_premium(USER) is False


class TestAccountBound:
    """
    Die Lizenz haengt am Konto, nicht am Server.

    Wer den Key auf der Website eingeloest hat, soll Premium haben,
    bevor der Bot ueberhaupt irgendwo eingeladen wurde — und auf jedem
    weiteren Server sofort, ohne erneut etwas einzugeben.
    """

    async def test_no_guild_is_part_of_the_request(self, patched):
        session = patched(FakeSession(FakeResponse(200, {"premium": True})))
        client = LicenceClient("https://bot.example", "token")

        await client.has_premium(USER)

        url, _ = session.calls[0]
        assert str(USER) in url
        # Taucht hier je eine Server-ID auf, waere die Lizenz an den
        # Server gebunden statt an das Konto.
        assert "guild" not in url.lower()

    async def test_same_answer_regardless_of_server(self, patched):
        session = patched(FakeSession(FakeResponse(200, {"premium": True})))
        client = LicenceClient("https://bot.example", "token")

        first = await client.has_premium(USER)
        client.forget(USER)
        second = await client.has_premium(USER)

        assert first is second is True
        assert session.calls[0][0] == session.calls[1][0]


class TestExpiry:
    """Laeuft eine Lizenz ab, muss der Zugang wieder verschwinden."""

    async def test_premium_drops_when_the_licence_ends(self, patched, monkeypatch):
        import core.licence as licence

        session = FakeSession(FakeResponse(200, {"premium": True}))
        patched(session)
        client = LicenceClient("https://bot.example", "token")

        clock = {"now": 1000.0}
        monkeypatch.setattr(licence.time, "monotonic", lambda: clock["now"])

        assert await client.has_premium(USER) is True

        # Der University Bot meldet die Lizenz jetzt als abgelaufen.
        session.response = FakeResponse(200, {"premium": False})
        clock["now"] += licence.CACHE_TTL + 1

        assert await client.has_premium(USER) is False, (
            "eine abgelaufene Lizenz gilt weiter"
        )


class TestCache:
    async def test_repeated_checks_hit_the_network_once(self, patched):
        session = patched(FakeSession(FakeResponse(200, {"premium": True})))
        client = LicenceClient("https://bot.example", "token")

        for _ in range(5):
            assert await client.has_premium(USER) is True

        assert len(session.calls) == 1, (
            f"{len(session.calls)} Anfragen fuer fuenf Klicks — der "
            "Zwischenspeicher greift nicht"
        )

    async def test_a_no_is_cached_too(self, patched):
        session = patched(FakeSession(FakeResponse(200, {"premium": False})))
        client = LicenceClient("https://bot.example", "token")

        await client.has_premium(USER)
        await client.has_premium(USER)

        assert len(session.calls) == 1

    async def test_different_users_are_separate(self, patched):
        session = patched(FakeSession(FakeResponse(200, {"premium": True})))
        client = LicenceClient("https://bot.example", "token")

        await client.has_premium(USER)
        await client.has_premium(USER + 1)

        assert len(session.calls) == 2

    async def test_forget_forces_a_fresh_look(self, patched):
        session = patched(FakeSession(FakeResponse(200, {"premium": True})))
        client = LicenceClient("https://bot.example", "token")

        await client.has_premium(USER)
        client.forget(USER)
        await client.has_premium(USER)

        assert len(session.calls) == 2

    async def test_the_cache_expires(self, patched, monkeypatch):
        import core.licence as licence

        session = patched(FakeSession(FakeResponse(200, {"premium": True})))
        client = LicenceClient("https://bot.example", "token")

        clock = {"now": 1000.0}
        monkeypatch.setattr(licence.time, "monotonic", lambda: clock["now"])

        await client.has_premium(USER)
        clock["now"] += licence.CACHE_TTL + 1
        await client.has_premium(USER)

        assert len(session.calls) == 2, "der Zwischenspeicher laeuft nie ab"
