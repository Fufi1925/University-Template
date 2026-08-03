"""Das Terminal im Dashboard muss mitlaufen, nicht ruckeln.

Der Fortschritt meldete sich nur einmal je Kategorie: 31 Zeilen für 94
Kanäle. Zwischen zwei Zeilen vergingen bis zu fünf Sekunden, in denen
im Dashboard nichts passierte — es sah aus, als hinge der Bau.

Der Detail-Hook schließt die Lücke: eine Zeile pro Rolle und pro Kanal,
also in dem Takt, in dem tatsächlich etwas entsteht.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import config
from core.builder import BuildMode, ServerBuilder
from core.registry import TemplateRegistry
from tests.test_build_simulation import FakeGuild


@pytest.fixture(scope="module")
def registry():
    return TemplateRegistry(config.TEMPLATE_DIR).load()


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    async def instant(_seconds):
        return None

    monkeypatch.setattr("core.builder.asyncio.sleep", instant)


@pytest.mark.asyncio
class TestLiveProgress:
    async def test_there_is_a_line_for_every_object(self, registry):
        """Nicht nur je Kategorie -- je Rolle und je Kanal."""

        template = registry.get("community")
        guild = FakeGuild()
        lines: list[str] = []

        async def detail(line: str) -> None:
            lines.append(line)

        report = await ServerBuilder(guild, template).apply(
            BuildMode.EXTEND, write_intros=False, detail=detail
        )

        created = (
            report.roles_created + report.categories_created + report.channels_created
        )
        assert len(lines) == created, (
            f"{len(lines)} Meldungen für {created} angelegte Objekte"
        )

        # Und deutlich mehr als die Kategorie-Meldungen allein.
        assert len(lines) > template.category_count * 3, (
            f"nur {len(lines)} Zeilen bei {template.channel_count} Kanälen — "
            "das Terminal steht wieder still"
        )

    async def test_the_lines_say_what_happened(self, registry):
        """»Kanal angelegt: X« statt einer nackten Zahl."""

        template = registry.get("community")
        guild = FakeGuild()
        lines: list[str] = []

        async def detail(line: str) -> None:
            lines.append(line)

        await ServerBuilder(guild, template).apply(
            BuildMode.EXTEND, write_intros=False, detail=detail
        )

        kinds = {line.split(":")[0] for line in lines}
        assert "Rolle angelegt" in kinds, kinds
        assert "Kategorie angelegt" in kinds, kinds
        assert "Kanal angelegt" in kinds, kinds

        # Jede Zeile nennt auch, *was* angelegt wurde.
        for line in lines:
            assert ": " in line and len(line.split(": ", 1)[1]) > 1, line

    async def test_a_second_run_stays_quiet(self, registry):
        """Was schon da ist, wird nicht noch einmal gemeldet.

        Sonst behauptet das Terminal beim zweiten Lauf, es sei alles neu
        angelegt worden — und man sucht danach nach Kanälen, die es
        doppelt gar nicht gibt.
        """

        template = registry.get("community")
        guild = FakeGuild()
        builder = ServerBuilder(guild, template)
        await builder.apply(BuildMode.EXTEND, write_intros=False)

        lines: list[str] = []

        async def detail(line: str) -> None:
            lines.append(line)

        await ServerBuilder(guild, template).apply(
            BuildMode.EXTEND, write_intros=False, detail=detail
        )

        assert not lines, f"zweiter Lauf meldet {len(lines)} Neuanlagen: {lines[:3]}"

    async def test_a_broken_hook_does_not_break_the_build(self, registry):
        """Das Log ist Beiwerk. Der Server ist es nicht."""

        template = registry.get("community")
        guild = FakeGuild()

        async def explode(_line: str) -> None:
            raise RuntimeError("Log weg")

        report = await ServerBuilder(guild, template).apply(
            BuildMode.EXTEND, write_intros=False, detail=explode
        )

        assert report.channels_created == template.channel_count
        assert report.roles_created > 0

    async def test_without_a_hook_nothing_changes(self, registry):
        """Die Chat-Befehle geben keinen Hook mit -- das muss weiter gehen."""

        template = registry.get("community")
        guild = FakeGuild()

        report = await ServerBuilder(guild, template).apply(
            BuildMode.EXTEND, write_intros=False
        )
        assert report.channels_created == template.channel_count

    async def test_the_log_cap_is_not_reached(self, registry):
        """Auch das größte Template muss unter die 500-Zeilen-Grenze passen.

        Bei mehr Zeilen als dem Deckel bricht das Log genau dann ab,
        wenn es interessant wird: am Ende, wo die Warnungen stehen.
        """

        from core.speedrun import MAX_LINES

        for template in registry.all:
            guild = FakeGuild()
            lines: list[str] = []

            async def detail(line: str, _sink=lines) -> None:
                _sink.append(line)

            report = await ServerBuilder(guild, template).apply(
                BuildMode.EXTEND, write_intros=False, detail=detail
            )
            # Plus Fortschritt (1 + Kategorien), Kopf- und Fusszeilen.
            estimate = len(lines) + template.category_count + 6 + len(report.warnings)
            assert estimate < MAX_LINES, (
                f"{template.key}: ~{estimate} Zeilen, Deckel ist {MAX_LINES}"
            )
