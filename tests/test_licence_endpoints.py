"""Die internen Endpunkte, ueber die der University Bot Lizenzen meldet.

Zwei Wege, und der zweite fehlte:

``/internal/licence-revoked``
    Eine Lizenz ist erloschen. Jede lokale Freischaltung des Kontos
    faellt weg, der Zwischenspeicher wird geleert.

``/internal/licence-refresh``
    Eine Lizenz hat sich geaendert — in der Praxis: sie wurde wieder
    freigegeben. Ohne diesen Weg blieb der Zwischenspeicher auf "kein
    Premium" stehen, bis zu fuenf Minuten lang. Im Dashboard stand
    "aktiv", im Bot galt "nein". Das ist die unangenehmste Sorte
    Fehler, weil sie aussieht, als sei sie behoben.

Geprueft wird ueber echtes HTTP, nicht durch Aufruf der Funktion: die
Authentifizierung, die Routen und das JSON gehoeren mit dazu.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import config
from core.licence import LicenceClient
from core.premium import PremiumStore

TOKEN = "partner-secret"
USER = 1303627964734246944


class Bot:
    """Nur das, was die Endpunkte anfassen."""

    def __init__(self, tmp_path):
        self.premium = PremiumStore(tmp_path / "premium.json", keys=("MASTER",))
        self.licence = LicenceClient("https://main.invalid", TOKEN)
        self.registry = _Registry()
        self.pending_handoffs = _Empty()
        self.setup_ledger = _Empty()
        self.active_builds: set[int] = set()
        self.guilds: list = []
        self.user = "Bot#1"
        self.latency = 0.02

    def is_ready(self):
        return True

    def get_guild(self, _guild_id):
        return None


class _Registry:
    @property
    def totals(self):
        return {"templates": 1, "categories": 1, "channels": 1, "voice": 0}


class _Empty:
    def __len__(self):
        return 0


@pytest.mark.asyncio
class TestLicenceEndpoints:
    @staticmethod
    async def _serve(bot_obj, port):
        import web as web_module

        config.PORT = port
        config.PREMIUM_PARTNER_TOKEN = TOKEN
        return await web_module.start_web_server(bot_obj)

    @staticmethod
    async def _post(port, path, payload, token=TOKEN):
        import aiohttp

        headers = {} if token is None else {"X-Partner-Token": token}
        async with aiohttp.ClientSession() as session:
            url = f"http://127.0.0.1:{port}{path}"
            async with session.post(url, json=payload, headers=headers) as response:
                return response.status, await response.json()

    async def test_revoke_removes_local_unlocks(self, tmp_path):
        bot_obj = Bot(tmp_path)
        bot_obj.premium.grant(111, USER)
        bot_obj.premium.grant(222, USER)

        runner = await self._serve(bot_obj, 8321)
        try:
            status, body = await self._post(
                8321, "/internal/licence-revoked", {"user_id": str(USER)}
            )
            assert status == 200
            assert body["removed"] == 2
            assert bot_obj.premium.has_access(111, USER) is False
            assert bot_obj.premium.has_access(222, USER) is False
        finally:
            await runner.cleanup()

    async def test_refresh_clears_the_cache(self, tmp_path):
        """
        Der eigentliche Fehler: nach dem Wieder-Freigeben hielt der
        Zwischenspeicher das alte Nein fest.
        """

        bot_obj = Bot(tmp_path)
        # So sieht es aus, nachdem der University Bot "kein Premium"
        # gemeldet hat.
        bot_obj.licence._cache[USER] = (float("inf"), False)

        runner = await self._serve(bot_obj, 8322)
        try:
            status, _ = await self._post(
                8322, "/internal/licence-refresh", {"user_id": str(USER)}
            )
            assert status == 200
            assert USER not in bot_obj.licence._cache, (
                "der Zwischenspeicher haelt weiter 'kein Premium' fest"
            )
        finally:
            await runner.cleanup()

    async def test_revoke_clears_the_cache_too(self, tmp_path):
        bot_obj = Bot(tmp_path)
        bot_obj.licence._cache[USER] = (float("inf"), True)

        runner = await self._serve(bot_obj, 8323)
        try:
            await self._post(
                8323, "/internal/licence-revoked", {"user_id": str(USER)}
            )
            assert USER not in bot_obj.licence._cache
        finally:
            await runner.cleanup()

    @pytest.mark.parametrize(
        "path", ["/internal/licence-revoked", "/internal/licence-refresh"]
    )
    async def test_a_wrong_token_is_refused(self, tmp_path, path):
        bot_obj = Bot(tmp_path)
        bot_obj.premium.grant(111, USER)

        runner = await self._serve(bot_obj, 8324)
        try:
            status, _ = await self._post(
                8324, path, {"user_id": str(USER)}, token="falsch"
            )
            assert status == 401
            # Und nichts wurde angefasst.
            assert bot_obj.premium.has_access(111, USER) is True
        finally:
            await runner.cleanup()

    @pytest.mark.parametrize(
        "path", ["/internal/licence-revoked", "/internal/licence-refresh"]
    )
    async def test_a_missing_token_is_refused(self, tmp_path, path):
        bot_obj = Bot(tmp_path)
        runner = await self._serve(bot_obj, 8325)
        try:
            status, _ = await self._post(
                8325, path, {"user_id": str(USER)}, token=None
            )
            assert status == 401
        finally:
            await runner.cleanup()

    async def test_without_a_configured_token_the_endpoint_is_off(self, tmp_path):
        """Fail-closed: kein Token konfiguriert heisst abgeschaltet."""

        bot_obj = Bot(tmp_path)
        runner = await self._serve(bot_obj, 8326)
        config.PREMIUM_PARTNER_TOKEN = ""
        try:
            status, _ = await self._post(
                8326, "/internal/licence-revoked", {"user_id": str(USER)},
                token="irgendwas",
            )
            assert status == 503
        finally:
            config.PREMIUM_PARTNER_TOKEN = TOKEN
            await runner.cleanup()

    async def test_a_missing_user_id_is_refused(self, tmp_path):
        bot_obj = Bot(tmp_path)
        runner = await self._serve(bot_obj, 8327)
        try:
            status, _ = await self._post(8327, "/internal/licence-revoked", {})
            assert status == 400
        finally:
            await runner.cleanup()

    async def test_an_unknown_account_is_not_an_error(self, tmp_path):
        """Nichts zu tun ist kein Fehler — sonst meldet das Dashboard rot."""

        bot_obj = Bot(tmp_path)
        runner = await self._serve(bot_obj, 8328)
        try:
            status, body = await self._post(
                8328, "/internal/licence-revoked", {"user_id": "999"}
            )
            assert status == 200
            assert body["removed"] == 0
        finally:
            await runner.cleanup()
