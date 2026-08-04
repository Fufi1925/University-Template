"""Die Speedrun-Endpunkte, ueber die das Dashboard einen Server baut.

Drei Wege:

``GET  /internal/speedrun/templates``
    Welche Templates es gibt. Das Dashboard baut daraus die Auswahl.

``POST /internal/speedrun/start``
    Bau starten. Antwortet **sofort** -- ein Bau dauert ueber eine
    Minute, und eine HTTP-Anfrage, die so lange offen bleibt, laeuft in
    einen Timeout. Das Dashboard wuesste dann nicht, ob gebaut wird oder
    ob es gescheitert ist.

``GET  /internal/speedrun/{guild_id}``
    Fortschritt. Mit ``since`` holt das Dashboard nur die neuen Zeilen,
    sonst waechst jede Abfrage mit der Log-Laenge.

Geprueft ueber echtes HTTP, nicht durch Aufruf der Funktionen: die
Authentifizierung, die Routen und das JSON gehoeren mit dazu.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import config
from core import speedrun
from core.licence import LicenceClient
from core.premium import PremiumStore

TOKEN = "partner-secret"
GUILD = 1520714989860814992


class _Registry:
    """Registry-Ausschnitt: nur was die Endpunkte anfassen."""

    def __init__(self, templates):
        self._templates = {t.key: t for t in templates}

    @property
    def totals(self):
        return {"templates": len(self._templates), "categories": 1,
                "channels": 1, "voice": 0}

    # Property, kein Aufruf -- genau wie in der echten TemplateRegistry.
    #
    # Vorher stand hier eine Methode. Damit war ``registry.all()`` im
    # Endpunkt gruen, waehrend es gegen die echte Registry mit
    # "TypeError: 'list' object is not callable" abstuerzte -- HTTP 500,
    # und im Dashboard "Template-Bot antwortet nicht". Eine Attrappe,
    # die sich anders verhaelt als das Original, prueft nichts; sie
    # bestaetigt nur die eigene Erfindung.
    @property
    def all(self):
        return list(self._templates.values())

    def get(self, key):
        return self._templates.get(key)


class _Role:
    """Eine Akzent-Rolle, so weit die Endpunkte sie anfassen."""

    def __init__(self, key):
        self.key = key


class _Template:
    def __init__(self, key="community", premium=False):
        self.key = key
        self.name = "Community Discord"
        self.emoji = "🌐"
        self.tagline = "Der Allrounder"
        self.description = "Beschreibung"
        self.premium = premium
        self.accent = "#5865F2"
        self.highlights = ["A", "B"]
        # Rollen tragen einen Key -- `[1, 2, 3]` war eine Abkuerzung,
        # die beim ersten echten Zugriff auffliegt.
        self.roles = [_Role("creator"), _Role("event_team"), _Role("designer")]
        self.category_count = 4
        # Die echte Template-Klasse hat diese Felder; eine Attrappe
        # ohne sie prueft nichts, sondern stuerzt nur anders ab.
        # Genau so ist es passiert: `_role_total` las
        # `extends_base_roles` und bekam einen AttributeError -- HTTP
        # 500, waehrend der Endpunkt gegen die echte Registry lief.
        self.extends_base_roles = True
        # Die echte Template-Klasse hat diese Eigenschaft; ohne sie
        # stuerzt der Endpunkt gegen die Attrappe anders ab als gegen
        # das Original -- und der Test prueft dann nichts.
        self.capabilities = {
            "verify": True, "rules": True, "selfroles": True,
            "tickets": True, "counting": False, "logging": True,
            "j2c": True, "welcome": True,
        }
        self.channel_count = 12
        self.voice_count = 3
        self.text_count = 9
        self.categories = ()


class _Empty:
    def __len__(self):
        return 0


class Bot:
    def __init__(self, tmp_path, guild=None, templates=None):
        self.premium = PremiumStore(tmp_path / "premium.json", keys=("MASTER",))
        self.licence = LicenceClient("https://main.invalid", TOKEN)
        self.registry = _Registry(templates or [_Template()])
        self.pending_handoffs = _Empty()
        self.setup_ledger = _Empty()
        self.active_builds: set[int] = set()
        self.guilds: list = []
        self.user = "Bot#1"
        self.latency = 0.02
        self._guild = guild

    def is_ready(self):
        return True

    def get_guild(self, guild_id):
        if self._guild is not None and guild_id == GUILD:
            return self._guild
        return None


class _Guild:
    """Ein Server, so weit die Endpunkte ihn brauchen."""

    def __init__(self):
        self.id = GUILD
        self.name = "Testserver"
        self.roles = []
        self.channels = []


@pytest.mark.asyncio
class TestSpeedrunEndpoints:
    @staticmethod
    async def _serve(bot_obj, port):
        import web as web_module

        config.PORT = port
        config.PREMIUM_PARTNER_TOKEN = TOKEN
        return await web_module.start_web_server(bot_obj)

    @staticmethod
    async def _get(port, path, token=TOKEN):
        import aiohttp

        headers = {} if token is None else {"X-Partner-Token": token}
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"http://127.0.0.1:{port}{path}", headers=headers
            ) as response:
                return response.status, await response.json()

    @staticmethod
    async def _post(port, path, payload, token=TOKEN):
        import aiohttp

        headers = {} if token is None else {"X-Partner-Token": token}
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"http://127.0.0.1:{port}{path}", json=payload, headers=headers
            ) as response:
                return response.status, await response.json()

    # -- Authentifizierung ------------------------------------------- #

    async def test_templates_need_the_partner_token(self, tmp_path):
        runner = await self._serve(Bot(tmp_path), 8431)
        try:
            status, _ = await self._get(8431, "/internal/speedrun/templates", token=None)
            assert status == 401
            status, _ = await self._get(
                8431, "/internal/speedrun/templates", token="falsch"
            )
            assert status == 401
        finally:
            await runner.cleanup()

    async def test_start_needs_the_partner_token(self, tmp_path):
        runner = await self._serve(Bot(tmp_path), 8432)
        try:
            status, _ = await self._post(
                8432,
                "/internal/speedrun/start",
                {"guild_id": str(GUILD), "template": "community"},
                token=None,
            )
            assert status == 401
        finally:
            await runner.cleanup()

    # -- Templates ---------------------------------------------------- #

    async def test_templates_are_listed(self, tmp_path):
        runner = await self._serve(Bot(tmp_path), 8433)
        try:
            status, body = await self._get(8433, "/internal/speedrun/templates")
            assert status == 200
            assert len(body["templates"]) == 1
            entry = body["templates"][0]
            # Alles, was die Auswahl im Dashboard braucht.
            for field in ("key", "name", "emoji", "tagline", "premium",
                          "accent", "highlights", "role_count", "category_count"):
                assert field in entry, field
            assert entry["key"] == "community"
            assert entry["premium"] is False
        finally:
            await runner.cleanup()

    # -- Start -------------------------------------------------------- #

    async def test_start_refuses_an_unknown_template(self, tmp_path):
        runner = await self._serve(Bot(tmp_path, guild=_Guild()), 8434)
        try:
            status, body = await self._post(
                8434,
                "/internal/speedrun/start",
                {"guild_id": str(GUILD), "template": "gibtesnicht"},
            )
            assert status == 400
            assert "gibtesnicht" in body["error"]
        finally:
            await runner.cleanup()

    async def test_start_refuses_when_the_bot_is_not_on_the_server(self, tmp_path):
        # get_guild gibt None -- der Bot ist nicht eingeladen.
        runner = await self._serve(Bot(tmp_path, guild=None), 8435)
        try:
            status, body = await self._post(
                8435,
                "/internal/speedrun/start",
                {"guild_id": str(GUILD), "template": "community"},
            )
            assert status == 404
            # Ein eigener Code, damit das Dashboard "lade den Bot ein"
            # sagen kann statt einer Fehlermeldung.
            assert body["code"] == "bot_missing"
        finally:
            await runner.cleanup()

    async def test_start_refuses_a_second_build(self, tmp_path):
        bot_obj = Bot(tmp_path, guild=_Guild())
        # Ein Bau laeuft schon -- zwei gleichzeitig am selben Server
        # bauen dieselben Kanaele doppelt.
        bot_obj.active_builds.add(GUILD)
        runner = await self._serve(bot_obj, 8436)
        try:
            status, body = await self._post(
                8436,
                "/internal/speedrun/start",
                {"guild_id": str(GUILD), "template": "community"},
            )
            assert status == 409
            assert body["code"] == "already_running"
        finally:
            await runner.cleanup()

    async def test_start_answers_immediately(self, tmp_path):
        """Die Antwort darf nicht auf den Bau warten."""

        bot_obj = Bot(tmp_path, guild=_Guild())
        runner = await self._serve(bot_obj, 8437)
        try:
            loop = asyncio.get_running_loop()
            before = loop.time()
            status, body = await self._post(
                8437,
                "/internal/speedrun/start",
                {"guild_id": str(GUILD), "template": "community"},
            )
            elapsed = loop.time() - before

            assert status == 200
            assert body["status"] == "started"
            # Grosszuegig: der Punkt ist, dass hier nicht auf einen
            # minutenlangen Bau gewartet wird.
            assert elapsed < 2.0, f"{elapsed:.1f}s -- die Antwort wartet auf den Bau"
        finally:
            await runner.cleanup()
            speedrun.STORE._jobs.pop(GUILD, None)

    # -- Fortschritt --------------------------------------------------- #

    async def test_status_of_an_unknown_server(self, tmp_path):
        runner = await self._serve(Bot(tmp_path), 8438)
        try:
            status, body = await self._get(8438, f"/internal/speedrun/{GUILD}")
            assert status == 200
            assert body["state"] == "none"
            assert body["lines"] == []
        finally:
            await runner.cleanup()

    async def test_status_returns_only_new_lines(self, tmp_path):
        runner = await self._serve(Bot(tmp_path), 8439)
        try:
            job = speedrun.STORE.start(GUILD, "community")
            job.log("erste")
            job.log("zweite")
            job.log("dritte")

            status, body = await self._get(8439, f"/internal/speedrun/{GUILD}")
            assert status == 200
            assert body["line_count"] == 3
            assert len(body["lines"]) == 3

            # Mit since=2 kommen nur die neuen -- sonst waechst jede
            # Abfrage mit der Log-Laenge.
            status, body = await self._get(
                8439, f"/internal/speedrun/{GUILD}?since=2"
            )
            assert len(body["lines"]) == 1
            assert body["lines"][0]["text"] == "dritte"
            # line_count bleibt die Gesamtzahl, damit das Dashboard
            # weiss, wo es beim naechsten Mal weitermacht.
            assert body["line_count"] == 3
        finally:
            await runner.cleanup()
            speedrun.STORE._jobs.pop(GUILD, None)

    async def test_lines_carry_a_source(self, tmp_path):
        """Das Terminal faerbt nach Bot -- dafuer braucht es die Quelle."""

        runner = await self._serve(Bot(tmp_path), 8440)
        try:
            job = speedrun.STORE.start(GUILD, "community")
            job.log("Rollen angelegt", source="template")
            job.log("Verify eingerichtet", source="main")

            _, body = await self._get(8440, f"/internal/speedrun/{GUILD}")
            sources = [line["source"] for line in body["lines"]]
            assert sources == ["template", "main"]
        finally:
            await runner.cleanup()
            speedrun.STORE._jobs.pop(GUILD, None)


class TestJobStore:
    """Der Speicher selbst, ohne HTTP."""

    def test_a_finished_job_stays_readable(self):
        """Nach dem Bau muss das Ergebnis noch abholbar sein.

        Die erste Fassung dieses Tests stand als
        ``assert store.get(1) is not None or store.get(1) is None`` da --
        eine Tautologie, die nichts prueft. Sie war von mir und ist
        durchgerutscht, weil sie gruen war.
        """

        import time

        store = speedrun.JobStore()
        job = store.start(1, "community")
        job.log("fertig")
        job.state = speedrun.JobState.DONE
        job.finished = time.time()

        # Gerade eben fertig: das Dashboard holt jetzt die letzten Zeilen.
        again = store.get(1)
        assert again is not None
        assert again.lines[-1].text == "fertig"

    def test_an_old_job_is_forgotten(self):
        """Sonst waechst der Speicher mit jedem je gebauten Server."""

        import time

        store = speedrun.JobStore()
        job = store.start(9, "community")
        job.state = speedrun.JobState.DONE
        job.finished = time.time() - speedrun.KEEP_FINISHED - 1

        assert store.get(9) is None

    def test_a_running_job_is_never_forgotten(self):
        """Auch nicht, wenn der Bau laenger dauert als die Aufbewahrung."""

        import time

        store = speedrun.JobStore()
        job = store.start(10, "community")
        # Laeuft seit Stunden -- ein sehr grosses Template plus
        # Rate-Limits. Wegzuraeumen hiesse: das Dashboard verliert den
        # laufenden Bau aus den Augen.
        job.started = time.time() - 10 * speedrun.KEEP_FINISHED

        assert store.get(10) is not None
        assert store.running(10) is True

    def test_running_is_only_true_while_running(self):
        store = speedrun.JobStore()
        job = store.start(2, "community")
        assert store.running(2) is True
        job.state = speedrun.JobState.DONE
        assert store.running(2) is False

    def test_the_log_is_capped(self):
        """Eine Endlosschleife darf den Arbeitsspeicher nicht fressen."""

        store = speedrun.JobStore()
        job = store.start(3, "community")
        for index in range(speedrun.MAX_LINES + 50):
            job.log(f"Zeile {index}")
        assert len(job.lines) == speedrun.MAX_LINES


# --------------------------------------------------------------------- #
# Die Zahlen, die das Dashboard vor dem Start anzeigt
# --------------------------------------------------------------------- #


class TestTemplateNumbers:
    """Was die Auswahl im Dashboard ueber ein Template behauptet.

    Hier stand eine Zahl, die nach dem Bau niemand wiederfand: bei
    "community" meldete die Liste drei Rollen, angelegt wurden
    sechzehn. Gezaehlt wurden nur die Akzent-Rollen aus der JSON-Datei
    -- die Basisleiter (Unverified bis Inhaber) kommt im ServerBuilder
    dazu und fehlte in der Rechnung.
    """

    def test_role_count_includes_the_base_ladder(self):
        import web
        from core.permissions import BASE_ROLES
        from core.registry import TemplateRegistry

        registry = TemplateRegistry(BASE_DIR / "templates").load()
        base_keys = {key for key, *_rest in BASE_ROLES}

        for template in registry.all:
            counted = web._role_total(template)
            expected = len(base_keys) + sum(
                1 for spec in template.roles if spec.key not in base_keys
            )
            assert counted == expected, (
                f"{template.key}: gemeldet {counted}, angelegt {expected}"
            )
            # Und die Zahl muss groesser sein als die reine JSON-Liste,
            # sonst wurde die Basisleiter wieder vergessen.
            assert counted > len(template.roles), (
                f"{template.key}: {counted} ist nicht mehr als die "
                f"{len(template.roles)} Akzent-Rollen -- die Basisleiter fehlt"
            )

    def test_a_template_without_the_ladder_counts_only_its_own(self):
        """Ohne ``extends_base_roles`` darf nichts dazugerechnet werden."""

        import web

        class Fake:
            extends_base_roles = False
            roles = (1, 2, 3)

        assert web._role_total(Fake()) == 3

    @pytest.mark.asyncio
    async def test_the_listing_carries_what_the_dashboard_shows(self, tmp_path):
        """Kanalzahlen und Gliederung muessen mitkommen."""

        from aiohttp.test_utils import TestClient, TestServer

        import web as web_module
        from core.registry import TemplateRegistry

        registry = TemplateRegistry(BASE_DIR / "templates").load()
        template = registry.get("community")

        bot = Bot(tmp_path)
        bot.registry = registry

        config.PARTNER_HANDSHAKE_SECRET = TOKEN
        runner = await web_module.start_web_server(bot)
        try:
            async with TestClient(TestServer(runner.app)) as client:
                response = await client.get(
                    "/internal/speedrun/templates",
                    headers={"X-Partner-Token": TOKEN},
                )
                assert response.status == 200
                body = await response.json()

            entry = next(t for t in body["templates"] if t["key"] == "community")

            assert entry["role_count"] == web_module._role_total(template)
            assert entry["channel_count"] == template.channel_count
            assert entry["voice_count"] == template.voice_count
            assert entry["text_count"] == template.text_count
            # Die Gliederung: eine Zeile je Kategorie, mit Kanalzahl.
            assert len(entry["outline"]) == template.category_count
            assert sum(c["channels"] for c in entry["outline"]) == (
                template.channel_count
            )
        finally:
            await runner.cleanup()
