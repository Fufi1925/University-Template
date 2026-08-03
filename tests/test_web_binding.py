"""Der Webserver muss über IPv4 *und* IPv6 erreichbar sein.

Railways privates Netz (``<dienst>.railway.internal``) ist IPv6-only.
Ein Server, der auf ``0.0.0.0`` lauscht, horcht nur auf IPv4 — jeder
Aufruf des University Bots endet dann in *connection refused*, im
Dashboard sichtbar als 502.

Genau das ist im Betrieb passiert: ``/precheck`` ging (das beantwortet
der Hauptbot selbst), ``/templates`` nicht (dafür muss er hierher).

Der Umkehrschluss ``"::"`` wäre genauso falsch: asyncio setzt auf einem
``"::"``-Socket ``IPV6_V6ONLY``, dann ist IPv4 tot — und damit Railways
Health-Check und die öffentliche Domain.

Deshalb wird hier beides geprüft, gegen einen echten Server auf einem
echten Port. Ein Test, der nur den Quelltext nach ``0.0.0.0`` absucht,
würde die V6ONLY-Falle nicht bemerken.
"""

from __future__ import annotations

import asyncio
import socket
import sys
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from aiohttp import web


def _free_port() -> int:
    with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as probe:
        probe.bind(("::", 0))
        return probe.getsockname()[1]


async def _reachable(host: str, port: int, family: int) -> bool:
    """Wie ein anderer Dienst es versuchen würde."""

    try:
        _reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port, family=family), timeout=3
        )
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        return True
    except Exception:
        return False


def _has_ipv6() -> bool:
    try:
        with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as probe:
            probe.bind(("::1", 0))
        return True
    except OSError:
        return False


@pytest.mark.asyncio
class TestBinding:
    async def test_the_real_server_answers_on_both_families(self, monkeypatch):
        """Der echte start_web_server, nicht eine Nachbildung."""

        if not _has_ipv6():
            pytest.skip("kein IPv6 in dieser Umgebung")

        import config
        import web as web_module

        port = _free_port()
        monkeypatch.setattr(config, "PORT", port)

        class _Empty:
            def __len__(self):
                return 0

        class _Registry:
            @property
            def totals(self):
                return {"templates": 0, "categories": 0, "channels": 0, "voice": 0}

            # Property, kein Aufruf -- wie in der echten Registry.
            # test_fakes_match_reality.py hält das fest.
            @property
            def all(self):
                return []

            def get(self, key):
                return None

        class _Bot:
            user = "Bot#1"
            latency = 0.01

            def __init__(self):
                self.registry = _Registry()
                self.pending_handoffs = _Empty()
                self.setup_ledger = _Empty()
                self.active_builds: set[int] = set()
                self.guilds: list = []

            def is_ready(self):
                return True

            def get_guild(self, guild_id):
                return None

        runner = await web_module.start_web_server(_Bot())
        try:
            over_v4 = await _reachable("127.0.0.1", port, socket.AF_INET)
            over_v6 = await _reachable("::1", port, socket.AF_INET6)
        finally:
            await runner.cleanup()

        # IPv4: Railways Health-Check und die öffentliche Domain.
        assert over_v4, (
            "über IPv4 nicht erreichbar — der Health-Check schlägt fehl "
            "und Railway startet den Dienst immer wieder neu"
        )
        # IPv6: das private Netz, über das der University Bot kommt.
        assert over_v6, (
            "über IPv6 nicht erreichbar — Railways privates Netz läuft nur "
            "darüber, der University Bot bekommt connection refused"
        )

    async def test_zero_zero_would_not_be_enough(self):
        """Die Gegenprobe: mit 0.0.0.0 ist IPv6 tot.

        Ohne diesen Test wäre nicht belegt, dass der Test oben überhaupt
        etwas prüft — er könnte in einer Umgebung grün sein, in der
        jeder Bind auf allen Familien landet.
        """

        if not _has_ipv6():
            pytest.skip("kein IPv6 in dieser Umgebung")

        port = _free_port()
        async def hello(_request):
            return web.json_response({"ok": True})

        app = web.Application()
        app.router.add_get("/", hello)
        runner = web.AppRunner(app)
        await runner.setup()
        await web.TCPSite(runner, "0.0.0.0", port).start()
        try:
            over_v4 = await _reachable("127.0.0.1", port, socket.AF_INET)
            over_v6 = await _reachable("::1", port, socket.AF_INET6)
        finally:
            await runner.cleanup()

        assert over_v4
        assert not over_v6, (
            "0.0.0.0 war hier auch über IPv6 erreichbar — dann sagt der "
            "Test oben nichts aus"
        )

    async def test_ipv6_only_would_not_be_enough_either(self):
        """Und die andere Richtung: mit "::" ist IPv4 tot.

        Das ist der naheliegende „Fix“, den man nach dem ersten Bug
        einbauen würde. Er tauscht bloß aus, welche Hälfte kaputt ist.
        """

        if not _has_ipv6():
            pytest.skip("kein IPv6 in dieser Umgebung")

        port = _free_port()
        async def hello(_request):
            return web.json_response({"ok": True})

        app = web.Application()
        app.router.add_get("/", hello)
        runner = web.AppRunner(app)
        await runner.setup()
        await web.TCPSite(runner, "::", port).start()
        try:
            over_v4 = await _reachable("127.0.0.1", port, socket.AF_INET)
            over_v6 = await _reachable("::1", port, socket.AF_INET6)
        finally:
            await runner.cleanup()

        assert over_v6
        assert not over_v4, (
            "\"::\" war hier auch über IPv4 erreichbar — dann ist die "
            "V6ONLY-Falle in dieser Umgebung nicht nachweisbar"
        )
