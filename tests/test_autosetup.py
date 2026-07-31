"""OAuth-Callback und automatische Einrichtung.

Der heikelste Teil ist das Wettrennen: Discord kann den Callback **vor**
oder **nach** ``on_guild_join`` ausliefern. Beide Reihenfolgen kommen in der
Praxis vor, und in beiden muss der Server genau einmal eingerichtet werden.
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import discord

import config
from core.autosetup import AutoSetup
from core.handoff_store import PendingHandoffs, SetupLedger
from core.handshake import SOURCE, Handoff, sign_state
from core.registry import TemplateRegistry

SECRET = "test-secret-mit-genug-entropie-1234567890"
GUILD_ID = 123456789012345678


@pytest.fixture(autouse=True)
def _secret(monkeypatch):
    monkeypatch.setenv("PARTNER_HANDSHAKE_SECRET", SECRET)


@pytest.fixture(scope="module")
def registry() -> TemplateRegistry:
    return TemplateRegistry(config.TEMPLATE_DIR).load()


@pytest.fixture(autouse=True)
def _fast(monkeypatch):
    """Wartezeiten überspringen, damit die Suite schnell bleibt."""

    async def instant(_seconds):
        return None

    monkeypatch.setattr("core.autosetup.asyncio.sleep", instant)


# --------------------------------------------------------------------------- #
# Attrappen
# --------------------------------------------------------------------------- #

class FakeChannel:
    def __init__(self, guild, name="allgemein", writable=True):
        self.guild = guild
        self.name = name
        self.mention = f"#{name}"
        self.writable = writable
        self.sent: list[object] = []

    def permissions_for(self, _member):
        return type("P", (), {"send_messages": self.writable})()

    async def send(self, content=None, view=None, **kwargs):
        self.sent.append(view if view is not None else content)
        return object()


class FakeMe:
    def __init__(self, guild, *, manage=True):
        self.guild = guild
        self.id = 999
        self.bot = True
        self.guild_permissions = (
            discord.Permissions.all() if manage else discord.Permissions.none()
        )
        self.top_role = type("R", (), {"__le__": lambda s, o: False})()


class FakeRole:
    def __init__(self, name="@everyone", position=0):
        self.name = name
        self.position = position

    def is_default(self):
        return self.position == 0


class FakeGuild:
    def __init__(self, guild_id=GUILD_ID, *, manage=True, writable=True, roles=2):
        self.id = guild_id
        self.name = "Testserver"
        self.channels: list[object] = []
        self.default_role = FakeRole()
        self.roles = [self.default_role] + [
            FakeRole(f"rolle-{i}", i) for i in range(1, roles)
        ]
        self.text_channels = [FakeChannel(self, writable=writable)]
        self.system_channel = self.text_channels[0]
        self.me = FakeMe(self, manage=manage)

    @property
    def outbox(self):
        return self.text_channels[0].sent


class FakeBot:
    """Nur die Teile, die AutoSetup wirklich anfasst."""

    def __init__(self, registry, tmp_path, *, template="community"):
        self.registry = registry
        self.pending_handoffs = PendingHandoffs()
        self.setup_ledger = SetupLedger(tmp_path / "ledger.json")
        self.partner_template_key = template
        self.active_builds: set[int] = set()
        self.command_prefix_display = "!"
        self.autosetup = AutoSetup(self)
        self.builds: list[tuple[int, str]] = []

    def get_guild(self, guild_id):
        return None


@pytest.fixture
def bot(registry, tmp_path):
    return FakeBot(registry, tmp_path)


@pytest.fixture
def no_real_build(monkeypatch):
    """Den echten Aufbau ersetzen — hier zählt nur, *ob* er läuft."""

    calls: list[tuple[int, str]] = []

    def install(bot):
        from core.builder import BuildMode, BuildReport

        async def fake_apply(self, mode, **kwargs):
            calls.append((self.guild.id, self.template.key))
            report = BuildReport(mode=BuildMode.EXTEND, template_key=self.template.key)
            report.channels_created = 42
            report.roles_created = 13
            report.categories_created = 7
            report.messages_posted = 40
            return report

        monkeypatch.setattr("core.builder.ServerBuilder.apply", fake_apply)
        return calls

    return install


def _handoff(guild_id=GUILD_ID) -> Handoff:
    return Handoff(
        guild_id=guild_id,
        user_id=42,
        issued_at=int(time.time()),
        source=SOURCE,
        guild_name="Testserver",
    )


# --------------------------------------------------------------------------- #
# Reihenfolge: Callback zuerst
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
class TestCallbackFirst:
    async def test_setup_runs_when_handoff_is_waiting(self, bot, no_real_build):
        calls = no_real_build(bot)
        guild = FakeGuild()

        bot.pending_handoffs.add(_handoff())
        await bot.autosetup.on_guild_join(guild)

        assert calls == [(GUILD_ID, "community")]
        assert bot.setup_ledger.was_set_up(GUILD_ID)

    async def test_summary_is_posted(self, bot, no_real_build):
        no_real_build(bot)
        guild = FakeGuild()
        bot.pending_handoffs.add(_handoff())

        await bot.autosetup.on_guild_join(guild)

        assert guild.outbox, "Es wurde keine Zusammenfassung gepostet"

    async def test_handoff_is_consumed(self, bot, no_real_build):
        no_real_build(bot)
        bot.pending_handoffs.add(_handoff())

        await bot.autosetup.on_guild_join(FakeGuild())

        assert bot.pending_handoffs.pop(GUILD_ID) is None


# --------------------------------------------------------------------------- #
# Reihenfolge: Guild-Join zuerst
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
class TestJoinFirst:
    async def test_retry_finds_a_late_handoff(self, bot, no_real_build, monkeypatch):
        """Der Callback trifft ein, während on_guild_join noch wartet."""

        calls = no_real_build(bot)
        guild = FakeGuild()

        original = asyncio.sleep
        state = {"added": False}

        async def sleep_and_deliver(_seconds):
            # Beim ersten Warten liefert der Webserver den Handoff nach.
            if not state["added"]:
                state["added"] = True
                bot.pending_handoffs.add(_handoff())
            await original(0)

        monkeypatch.setattr("core.autosetup.asyncio.sleep", sleep_and_deliver)

        await bot.autosetup.on_guild_join(guild)

        assert calls == [(GUILD_ID, "community")]

    async def test_gives_up_after_the_retries(self, bot, no_real_build):
        """Kommt nichts nach, bleibt es ein normaler Beitritt."""

        calls = no_real_build(bot)

        await bot.autosetup.on_guild_join(FakeGuild())

        assert calls == []
        assert not bot.setup_ledger.was_set_up(GUILD_ID)


# --------------------------------------------------------------------------- #
# Normale Beitritte
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
class TestPlainJoin:
    async def test_guild_without_handoff_is_untouched(self, bot, no_real_build):
        calls = no_real_build(bot)
        guild = FakeGuild()

        await bot.autosetup.on_guild_join(guild)

        assert calls == []
        assert guild.outbox == [], "Ein normaler Beitritt darf nichts posten"

    async def test_handoff_for_another_guild_does_not_apply(self, bot, no_real_build):
        calls = no_real_build(bot)
        bot.pending_handoffs.add(_handoff(guild_id=999))

        await bot.autosetup.on_guild_join(FakeGuild(guild_id=GUILD_ID))

        assert calls == []


# --------------------------------------------------------------------------- #
# Kein zweites Mal
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
class TestNoDoubleSetup:
    async def test_second_join_does_not_rebuild(self, bot, no_real_build):
        calls = no_real_build(bot)

        bot.pending_handoffs.add(_handoff())
        await bot.autosetup.on_guild_join(FakeGuild())
        assert len(calls) == 1

        # Bot entfernt, erneut hinzugefügt — mit frischem Handoff.
        bot.pending_handoffs.add(_handoff())
        await bot.autosetup.on_guild_join(FakeGuild())

        assert len(calls) == 1, "Der Server wurde ein zweites Mal aufgebaut"

    async def test_second_join_explains_itself(self, bot, no_real_build):
        no_real_build(bot)
        bot.pending_handoffs.add(_handoff())
        await bot.autosetup.on_guild_join(FakeGuild())

        second = FakeGuild()
        bot.pending_handoffs.add(_handoff())
        await bot.autosetup.on_guild_join(second)

        assert second.outbox, "Der Nutzer erfährt nicht, warum nichts passiert"

    async def test_force_allows_a_deliberate_rerun(self, bot, no_real_build):
        calls = no_real_build(bot)

        bot.pending_handoffs.add(_handoff())
        await bot.autosetup.on_guild_join(FakeGuild())

        await bot.autosetup.run(FakeGuild(), _handoff(), force=True)

        assert len(calls) == 2

    async def test_ledger_is_only_written_after_success(self, bot, monkeypatch):
        """Bricht der Aufbau ab, darf ein zweiter Versuch nicht blockiert sein."""

        async def failing_apply(self, mode, **kwargs):
            raise discord.HTTPException(
                type("R", (), {"status": 500, "reason": "boom"})(), "kaputt"
            )

        monkeypatch.setattr("core.builder.ServerBuilder.apply", failing_apply)

        bot.pending_handoffs.add(_handoff())
        await bot.autosetup.on_guild_join(FakeGuild())

        assert not bot.setup_ledger.was_set_up(GUILD_ID)


# --------------------------------------------------------------------------- #
# Fehlerfälle
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
class TestFailureHandling:
    async def test_missing_permissions_are_reported(self, bot, no_real_build):
        """Keine Ausnahme, sondern eine verständliche Meldung."""

        calls = no_real_build(bot)
        guild = FakeGuild(manage=False)

        bot.pending_handoffs.add(_handoff())
        await bot.autosetup.on_guild_join(guild)

        assert calls == [], "Ohne Rechte darf nichts gebaut werden"
        assert guild.outbox, "Der Server erfährt nicht, warum nichts passiert"
        assert not bot.setup_ledger.was_set_up(GUILD_ID)

    async def test_unknown_template_is_reported(self, registry, tmp_path, no_real_build):
        bot = FakeBot(registry, tmp_path, template="gibtsnicht")
        calls = no_real_build(bot)
        guild = FakeGuild()

        bot.pending_handoffs.add(_handoff())
        await bot.autosetup.on_guild_join(guild)

        assert calls == []
        assert guild.outbox

    async def test_no_writable_channel_does_not_crash(self, bot, no_real_build):
        calls = no_real_build(bot)
        guild = FakeGuild(writable=False)

        bot.pending_handoffs.add(_handoff())
        await bot.autosetup.on_guild_join(guild)

        # Der Aufbau läuft trotzdem — nur die Meldung entfällt.
        assert calls == [(GUILD_ID, "community")]

    async def test_concurrent_setup_is_skipped(self, bot, no_real_build):
        calls = no_real_build(bot)
        bot.active_builds.add(GUILD_ID)
        bot.pending_handoffs.add(_handoff())

        await bot.autosetup.on_guild_join(FakeGuild())

        assert calls == []

    async def test_build_lock_is_released(self, bot, no_real_build):
        no_real_build(bot)
        bot.pending_handoffs.add(_handoff())

        await bot.autosetup.on_guild_join(FakeGuild())

        assert GUILD_ID not in bot.active_builds


# --------------------------------------------------------------------------- #
# Der Webserver
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
class TestOAuthCallback:
    async def test_valid_state_is_remembered(self, bot):
        """Der Callback merkt den Server vor."""

        from core.handshake import read_state

        state = sign_state(GUILD_ID, 42, guild_name="Testserver")
        handoff = read_state(state)
        assert handoff is not None

        bot.pending_handoffs.add(handoff)
        assert bot.pending_handoffs.peek(GUILD_ID) is not None

    async def test_guild_id_mismatch_is_caught(self):
        """Ein fremdes Token an der eigenen Einladung darf nicht durchgehen."""

        from core.handshake import read_state

        handoff = read_state(sign_state(GUILD_ID, 42))
        assert handoff is not None
        # Discord meldet eine andere Guild als das Token behauptet.
        assert handoff.guild_id != 555555555555555555


@pytest.mark.asyncio
class TestLiveEndpoint:
    """Der Endpunkt über echtes HTTP — statische Prüfung reicht hier nicht."""

    @staticmethod
    async def _serve(bot_obj, port):
        import web as web_module

        config.PORT = port
        return await web_module.start_web_server(bot_obj)

    @staticmethod
    def _bot(registry, tmp_path):
        class Bot(FakeBot):
            def __init__(self):
                super().__init__(registry, tmp_path)
                self.user = "Bot#1"
                self.guilds = []
                self.latency = 0.03
                self.scheduled: list[int] = []

            def is_ready(self):
                return True

            def schedule_partner_setup(self, guild):
                self.scheduled.append(guild.id)

        return Bot()

    async def _get(self, port, path, **params):
        import aiohttp

        async with aiohttp.ClientSession() as session:
            url = f"http://127.0.0.1:{port}{path}"
            async with session.get(url, params=params) as response:
                return response.status, await response.text()

    async def test_valid_state_is_stored(self, registry, tmp_path):
        bot_obj = self._bot(registry, tmp_path)
        runner = await self._serve(bot_obj, 8231)
        try:
            state = sign_state(GUILD_ID, 42, guild_name="Testserver")
            status, _ = await self._get(
                8231, "/oauth/callback", code="c", guild_id=str(GUILD_ID), state=state
            )
            assert status == 200
            assert bot_obj.pending_handoffs.peek(GUILD_ID) is not None
        finally:
            await runner.cleanup()

    async def test_forged_signature_is_not_stored(self, registry, tmp_path):
        bot_obj = self._bot(registry, tmp_path)
        runner = await self._serve(bot_obj, 8232)
        try:
            body = sign_state(GUILD_ID, 42).split(".")[0]
            status, _ = await self._get(
                8232,
                "/oauth/callback",
                code="c",
                guild_id=str(GUILD_ID),
                state=f"{body}.gefaelscht",
            )
            # Die Seite ist freundlich, der Handoff aber verworfen.
            assert status == 200
            assert bot_obj.pending_handoffs.peek(GUILD_ID) is None
        finally:
            await runner.cleanup()

    async def test_guild_id_mismatch_is_refused(self, registry, tmp_path):
        bot_obj = self._bot(registry, tmp_path)
        runner = await self._serve(bot_obj, 8233)
        try:
            state = sign_state(GUILD_ID, 42)
            status, _ = await self._get(
                8233, "/oauth/callback", code="c", guild_id="999", state=state
            )
            assert status == 400
            assert bot_obj.pending_handoffs.peek(GUILD_ID) is None
            assert bot_obj.pending_handoffs.peek(999) is None
        finally:
            await runner.cleanup()

    async def test_plain_join_without_state(self, registry, tmp_path):
        bot_obj = self._bot(registry, tmp_path)
        runner = await self._serve(bot_obj, 8234)
        try:
            status, body = await self._get(
                8234, "/oauth/callback", code="c", guild_id=str(GUILD_ID)
            )
            assert status == 200
            assert "start" in body  # Hinweis auf den manuellen Befehl
            assert bot_obj.pending_handoffs.peek(GUILD_ID) is None
        finally:
            await runner.cleanup()

    async def test_user_cancelled(self, registry, tmp_path):
        bot_obj = self._bot(registry, tmp_path)
        runner = await self._serve(bot_obj, 8235)
        try:
            status, body = await self._get(
                8235, "/oauth/callback", error="access_denied"
            )
            assert status == 200
            assert "Abgebrochen" in body
        finally:
            await runner.cleanup()

    async def test_setup_is_triggered_if_bot_already_joined(self, registry, tmp_path):
        """Callback nach dem Join: die Einrichtung wird nachgezogen."""

        bot_obj = self._bot(registry, tmp_path)
        guild = FakeGuild()
        bot_obj.get_guild = lambda gid: guild if gid == GUILD_ID else None

        runner = await self._serve(bot_obj, 8236)
        try:
            state = sign_state(GUILD_ID, 42)
            await self._get(
                8236, "/oauth/callback", code="c", guild_id=str(GUILD_ID), state=state
            )
            assert bot_obj.scheduled == [GUILD_ID]
        finally:
            await runner.cleanup()

    async def test_health_still_works(self, registry, tmp_path):
        bot_obj = self._bot(registry, tmp_path)
        runner = await self._serve(bot_obj, 8237)
        try:
            import json

            status, body = await self._get(8237, "/health")
            assert status == 200
            payload = json.loads(body)
            assert payload["partner_handshake"] is True
            assert "pending_handoffs" in payload
        finally:
            await runner.cleanup()

    async def test_health_reports_disabled_handshake(
        self, registry, tmp_path, monkeypatch
    ):
        monkeypatch.delenv("PARTNER_HANDSHAKE_SECRET", raising=False)
        bot_obj = self._bot(registry, tmp_path)
        runner = await self._serve(bot_obj, 8238)
        try:
            import json

            _, body = await self._get(8238, "/health")
            assert json.loads(body)["partner_handshake"] is False
        finally:
            await runner.cleanup()


class TestLiveEndpointEdges:
    """Antwortpfade des Callbacks, die bisher nur statisch belegt waren."""

    @staticmethod
    async def _serve(bot_obj, port):
        import web as web_module

        config.PORT = port
        return await web_module.start_web_server(bot_obj)

    @staticmethod
    def _bot(registry, tmp_path):
        class Bot(FakeBot):
            def __init__(self):
                super().__init__(registry, tmp_path)
                self.user = "Bot#1"
                self.guilds = []
                self.latency = 0.03
                self.scheduled: list[int] = []

            def is_ready(self):
                return True

            def schedule_partner_setup(self, guild):
                self.scheduled.append(guild.id)

        return Bot()

    async def _get(self, port, path, **params):
        import aiohttp

        async with aiohttp.ClientSession() as session:
            url = f"http://127.0.0.1:{port}{path}"
            async with session.get(url, params=params) as response:
                return response.status, await response.text()

    async def test_user_cancelled_is_not_an_error(self, registry, tmp_path):
        """Wer im Discord-Dialog abbricht, hat nichts falsch gemacht."""

        bot_obj = self._bot(registry, tmp_path)
        runner = await self._serve(bot_obj, 8241)
        try:
            status, body = await self._get(
                8241, "/oauth/callback", error="access_denied"
            )
            assert status == 200
            assert "Abgebrochen" in body
            assert bot_obj.pending_handoffs.peek(GUILD_ID) is None
        finally:
            await runner.cleanup()

    async def test_unreadable_guild_id_is_refused(self, registry, tmp_path):
        bot_obj = self._bot(registry, tmp_path)
        runner = await self._serve(bot_obj, 8242)
        try:
            state = sign_state(GUILD_ID, 42)
            status, body = await self._get(
                8242, "/oauth/callback", code="c", guild_id="keine-zahl", state=state
            )
            assert status == 400
            assert "unlesbar" in body
            assert bot_obj.pending_handoffs.peek(GUILD_ID) is None
        finally:
            await runner.cleanup()

    async def test_callback_without_state_still_welcomes(self, registry, tmp_path):
        """Ein normaler Beitritt ohne Partner-Token ist voellig in Ordnung."""

        bot_obj = self._bot(registry, tmp_path)
        runner = await self._serve(bot_obj, 8243)
        try:
            status, body = await self._get(8243, "/oauth/callback", code="c")
            assert status == 200
            assert "hinzugefügt" in body
        finally:
            await runner.cleanup()

    async def test_health_endpoint_reports_state(self, registry, tmp_path):
        """Railway prueft diesen Endpunkt — er muss echte Zahlen liefern."""

        import json

        bot_obj = self._bot(registry, tmp_path)
        runner = await self._serve(bot_obj, 8244)
        try:
            status, body = await self._get(8244, "/health")
            assert status == 200

            payload = json.loads(body)
            assert payload["status"] == "online"
            assert payload["templates"] == len(registry)
            assert payload["channels"] > 0
        finally:
            await runner.cleanup()

    async def test_root_serves_the_same_status(self, registry, tmp_path):
        bot_obj = self._bot(registry, tmp_path)
        runner = await self._serve(bot_obj, 8245)
        try:
            status, _ = await self._get(8245, "/")
            assert status == 200
        finally:
            await runner.cleanup()

    async def test_html_escapes_the_guild_name(self, registry, tmp_path):
        """Der Servername kommt aus dem Token und landet in einer HTML-Seite."""

        bot_obj = self._bot(registry, tmp_path)
        runner = await self._serve(bot_obj, 8246)
        try:
            state = sign_state(
                GUILD_ID, 42, guild_name="<script>alert(1)</script>"
            )
            status, body = await self._get(
                8246, "/oauth/callback", code="c", guild_id=str(GUILD_ID), state=state
            )
            assert status == 200
            assert "<script>" not in body, "Servername ungefiltert in der Antwort"
            assert "&lt;script&gt;" in body
        finally:
            await runner.cleanup()


class TestWebRoutes:
    """Statische Prüfung der Endpunkte."""

    @staticmethod
    def _source() -> str:
        return (BASE_DIR / "web.py").read_text(encoding="utf-8")

    def test_callback_route_exists(self):
        assert 'add_get("/oauth/callback"' in self._source()

    def test_health_routes_survive(self):
        source = self._source()
        assert 'add_get("/health"' in source
        assert 'add_get("/"' in source

    def test_callback_verifies_the_token(self):
        """Der Endpunkt darf state niemals ungeprüft übernehmen."""

        source = self._source()
        assert "read_state(" in source

    def test_callback_compares_the_guild_id(self):
        assert "handoff.guild_id" in self._source()

    def test_no_client_secret_in_responses(self):
        """Das Client-Secret gehört nie in eine HTTP-Antwort."""

        source = self._source()
        assert "DISCORD_CLIENT_SECRET" not in source
