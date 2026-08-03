"""Die Attrappen der Testsuite müssen sich wie das Original verhalten.

Der Anlass ist ein echter Ausfall: der Speedrun-Endpunkt rief
``bot.registry.all()`` auf. ``all`` ist aber eine *Property*, kein
Aufruf — die Klammern rufen die zurückgegebene Liste auf, und das endet
in ``TypeError: 'list' object is not callable``. HTTP 500, im Dashboard
sichtbar als „Template-Bot antwortet nicht".

Der zugehörige Test war grün. In seiner Attrappe war ``all`` als
*Methode* definiert, also passte der falsche Aufruf. Eine Attrappe, die
sich anders verhält als das Original, prüft nichts — sie bestätigt die
eigene Erfindung.

Dieser Test vergleicht deshalb die Attrappen mit der echten Klasse:
Was drüben eine Property ist, muss hier eine Property sein.
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.registry import TemplateRegistry


def _kind(owner: type, name: str) -> str:
    """„property“, „method“ oder „fehlt“ — für einen lesbaren Vergleich."""

    attribute = inspect.getattr_static(owner, name, None)
    if attribute is None:
        return "fehlt"
    if isinstance(attribute, property):
        return "property"
    if callable(attribute):
        return "method"
    return type(attribute).__name__


# Die Mitglieder, auf die es ankommt.
_MEMBERS = ("all", "free", "premium", "totals", "get", "available_to")


def _fake_registries() -> list[tuple[str, dict[str, str]]]:
    """Jede Registry-Attrappe der Suite, rein über den Syntaxbaum.

    Zwei Gründe, warum hier nichts importiert wird:

      * Attrappen stehen oft *innerhalb* einer Testfunktion. Ein
        ``getattr`` auf das Modul findet die nicht — mein erster
        Versuch hat genau deshalb die Abweichung übersehen, die dieser
        Test finden sollte.
      * Ein Import zieht die halbe Suite mit; der Baum reicht völlig,
        um „Property oder Methode“ zu beantworten.

    Bewusst nicht von Hand aufgezählt: die zweite Abweichung steckte in
    einer Datei, an die ich beim Suchen nicht gedacht hatte. Eine Liste,
    die jemand pflegen muss, veraltet genau dann, wenn sie gebraucht wird.
    """

    import ast

    found: list[tuple[str, dict[str, str]]] = []
    for path in sorted((BASE_DIR / "tests").glob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            # Nur Attrappen, keine Testklassen: die heißen Test*.
            if node.name.startswith("Test"):
                continue
            if "registry" not in node.name.lower():
                continue

            members: dict[str, str] = {}
            for item in node.body:
                if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if item.name not in _MEMBERS:
                    continue
                is_property = any(
                    getattr(decorator, "id", "") == "property"
                    for decorator in item.decorator_list
                )
                members[item.name] = "property" if is_property else "method"

            if members:
                found.append((f"{path.name}:{node.name}", members))
    return found


class TestRegistryFake:
    def test_every_fake_registry_matches_the_real_one(self):
        """Jedes nachgebildete Mitglied muss dieselbe Art haben.

        Eine Attrappe muss nicht die ganze Registry nachbauen -- aber
        was sie nachbaut, muss sich verhalten wie das Original.
        """

        fakes = _fake_registries()
        assert fakes, "keine Registry-Attrappe gefunden — sucht der Test richtig?"

        wrong: dict[str, dict] = {}
        for label, members in fakes:
            mismatches = {
                name: {"attrappe": kind, "original": _kind(TemplateRegistry, name)}
                for name, kind in members.items()
                if kind != _kind(TemplateRegistry, name)
            }
            if mismatches:
                wrong[label] = mismatches

        assert not wrong, f"Attrappe weicht vom Original ab: {wrong}"

    def test_the_search_actually_finds_the_fakes(self):
        """Sonst wäre die Prüfung oben leer und trotzdem grün.

        Der erste Versuch importierte die Module und las die Klassen per
        getattr — damit blieben alle Attrappen unsichtbar, die in einer
        Testfunktion stehen. Genau dort steckte eine der Abweichungen.
        """

        fakes = _fake_registries()
        labels = [label for label, _members in fakes]

        # Die drei Dateien, die heute eine Registry nachbauen. Kommt
        # eine dazu, findet der Test sie von selbst; verschwindet eine
        # aus dieser Liste, ist die Suche kaputt.
        for expected in (
            "test_speedrun_endpoints.py",
            "test_licence_endpoints.py",
            "test_web_binding.py",
        ):
            assert any(label.startswith(expected) for label in labels), (
                f"{expected} wurde nicht gefunden — gefunden: {labels}"
            )

        covered = {name for _label, members in fakes for name in members}
        assert "all" in covered, "keine Attrappe bildet `all` nach"

    def test_the_real_registry_still_has_all_as_a_property(self):
        """Damit der Vergleich oben nicht beide Seiten gleichzeitig verliert.

        Würde ``all`` im Original zur Methode, wäre der Test darüber
        weiter grün — und der Endpunkt wieder kaputt, nur andersherum.
        """

        assert _kind(TemplateRegistry, "all") == "property"
        assert _kind(TemplateRegistry, "free") == "property"
        assert _kind(TemplateRegistry, "premium") == "property"
        assert _kind(TemplateRegistry, "totals") == "property"


class TestAgainstTheRealRegistry:
    """Der Endpunkt einmal über echtes HTTP, mit der echten Registry.

    Die Attrappen-Prüfungen oben sind Schadensbegrenzung. Das hier ist
    der Test, der den Ausfall verhindert hätte: keine Nachbildung,
    sondern die Registry, die im Betrieb läuft — samt der zehn echten
    Template-Dateien.
    """

    @staticmethod
    def _free_port() -> int:
        import socket

        with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as probe:
            probe.bind(("::", 0))
            return probe.getsockname()[1]

    def test_templates_endpoint_against_the_real_registry(self, monkeypatch):
        import asyncio

        import aiohttp

        import config
        import web as web_module

        token = "partner-secret"
        port = self._free_port()
        monkeypatch.setattr(config, "PORT", port)
        monkeypatch.setattr(config, "PREMIUM_PARTNER_TOKEN", token)

        real_registry = TemplateRegistry(config.TEMPLATE_DIR).load()

        class _Empty:
            def __len__(self):
                return 0

        class _Bot:
            user = "Bot#1"
            latency = 0.01

            def __init__(self):
                # Kein Nachbau: genau das Objekt aus dem Betrieb.
                self.registry = real_registry
                self.pending_handoffs = _Empty()
                self.setup_ledger = _Empty()
                self.active_builds: set[int] = set()
                self.guilds: list = []

            def is_ready(self):
                return True

            def get_guild(self, guild_id):
                return None

        async def go():
            runner = await web_module.start_web_server(_Bot())
            try:
                async with aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as session:
                    async with session.get(
                        f"http://127.0.0.1:{port}/internal/speedrun/templates",
                        headers={"X-Partner-Token": token},
                    ) as response:
                        return response.status, await response.json()
            finally:
                await runner.cleanup()

        status, body = asyncio.run(go())

        assert status == 200, f"HTTP {status}: {body}"

        items = body["templates"]
        assert len(items) == len(real_registry.all), (
            f"{len(items)} von {len(real_registry.all)} Templates geliefert"
        )

        # Und der Inhalt stimmt, nicht nur die Anzahl.
        keys = {item["key"] for item in items}
        assert keys == {template.key for template in real_registry.all}
        assert "community" in keys, "das einzige Beta-Template fehlt"

        for item in items:
            assert item["name"], f"{item['key']} hat keinen Namen"
            assert isinstance(item["premium"], bool)
            assert item["category_count"] > 0


class TestEndpointsUseTheRegistryCorrectly:
    def test_no_endpoint_calls_a_property(self):
        """``registry.all()`` und Geschwister im Quelltext aufspüren.

        Der Vergleich oben fängt den Fall nur, wenn ein Test den
        Endpunkt auch anfasst. Diese Prüfung greift überall in web.py,
        auch in Zweigen, durch die keine Anfrage läuft.
        """

        source = (BASE_DIR / "web.py").read_text(encoding="utf-8")

        offenders = [
            f"registry.{name}()"
            for name in ("all", "free", "premium", "totals")
            if f"registry.{name}()" in source
        ]
        assert not offenders, (
            f"Property mit Klammern aufgerufen: {offenders} — "
            "das ergibt TypeError und HTTP 500"
        )
