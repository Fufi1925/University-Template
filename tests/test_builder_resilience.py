"""Was der Builder tut, wenn Discord nicht mitspielt.

``test_build_simulation.py`` prueft den Erfolgsfall: alle Kanaele entstehen,
ein zweiter Lauf aendert nichts, private Kategorien bleiben privat. Diese
Datei nimmt die Gegenrichtung — die Pfade, die nur bei Fehlern laufen und die
deshalb im Betrieb selten, aber dann folgenreich sind.

Der Leitgedanke dahinter: **ein Teilausfall darf nie einen halb gebauten
Server hinterlassen, ohne dass es jemand erfaehrt.** Was nicht geklappt hat,
gehoert in den Bericht, und der Rest muss trotzdem entstehen.

Die Attrappen aus der Bau-Simulation werden wiederverwendet statt kopiert;
sie bilden Discords Verhalten bereits genau genug ab.
"""

from __future__ import annotations

import sys
from pathlib import Path

import discord
import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# Ohne "tests."-Praefix importieren: die Suite legt das Projektwurzel- und das
# tests-Verzeichnis in sys.path, sodass dieselbe Datei sonst unter zwei
# Modulnamen gefunden wird — mypy bricht darauf ab.
from test_build_simulation import (
    FakeChannel,
    FakeGuild,
    FakeRole,
    _FakeResponse,
)

import config
from core.builder import BuildError, BuildMode, ServerBuilder
from core.registry import TemplateRegistry


@pytest.fixture(scope="module")
def registry() -> TemplateRegistry:
    return TemplateRegistry(config.TEMPLATE_DIR).load()


@pytest.fixture(scope="module")
def template(registry):
    """Die kleinste Vorlage — die Fehlerpfade sind ueberall dieselben."""

    return min(registry.all, key=lambda t: t.channel_count)


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    """Der Throttle interessiert hier nicht."""

    import core.builder as builder

    async def instant(_seconds: float) -> None:
        return None

    monkeypatch.setattr(builder.asyncio, "sleep", instant)


def http(status: int = 500) -> discord.HTTPException:
    return discord.HTTPException(_FakeResponse(), f"Fehler {status}")


def forbidden() -> discord.Forbidden:
    return discord.Forbidden(_FakeResponse(), "verboten")


# --------------------------------------------------------------------------- #
# Preflight
# --------------------------------------------------------------------------- #

class TestPreflight:
    """Lieber vorher ablehnen als mitten im Umbau scheitern."""

    def test_missing_manage_roles_is_named(self, template):
        guild = FakeGuild()
        guild.me.guild_permissions.manage_roles = False

        with pytest.raises(BuildError) as excinfo:
            ServerBuilder(guild, template).preflight()

        assert "Rollen verwalten" in str(excinfo.value)

    def test_missing_manage_channels_is_named(self, template):
        guild = FakeGuild()
        guild.me.guild_permissions.manage_channels = False

        with pytest.raises(BuildError) as excinfo:
            ServerBuilder(guild, template).preflight()

        assert "Kanäle verwalten" in str(excinfo.value)

    def test_channel_limit_is_checked_before_building(self, registry):
        """Discord erlaubt 500 Kanaele. Danach bricht es mittendrin ab."""

        biggest = max(registry.all, key=lambda t: t.channel_count)
        guild = FakeGuild()
        for index in range(480):
            channel = FakeChannel(guild, f"alt-{index}", "text")
            guild._channels[channel.id] = channel

        with pytest.raises(BuildError) as excinfo:
            ServerBuilder(guild, biggest).preflight()

        assert "500" in str(excinfo.value)

    def test_role_limit_is_checked(self, template):
        guild = FakeGuild()
        for index in range(245):
            guild.roles.append(FakeRole(guild, f"rolle-{index}", index + 1))

        with pytest.raises(BuildError) as excinfo:
            ServerBuilder(guild, template).preflight()

        assert "250" in str(excinfo.value)

    def test_healthy_guild_passes(self, template):
        ServerBuilder(FakeGuild(), template).preflight()


# --------------------------------------------------------------------------- #
# Rollen
# --------------------------------------------------------------------------- #

class TestRoleFailures:
    async def test_forbidden_role_is_reported_and_build_continues(
        self, template, monkeypatch
    ):
        """Eine abgelehnte Rolle darf den restlichen Aufbau nicht kippen."""

        guild = FakeGuild()
        original = guild.create_role
        calls = {"n": 0}

        async def flaky(**kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                raise forbidden()
            return await original(**kwargs)

        monkeypatch.setattr(guild, "create_role", flaky)

        report = await ServerBuilder(guild, template).apply(BuildMode.EXTEND)

        assert report.roles_skipped >= 1
        assert report.roles_created >= 1, "Nach dem Fehler wurde nichts mehr angelegt"
        assert any("konnte nicht erstellt werden" in w for w in report.warnings)

    async def test_http_error_on_role_is_counted_but_silent(
        self, template, monkeypatch
    ):
        """Ein 500er ist kein Berechtigungsproblem — er gehoert ins Log, nicht
        als Handlungsanweisung in den Bericht."""

        guild = FakeGuild()
        original = guild.create_role
        calls = {"n": 0}

        async def flaky(**kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                raise http()
            return await original(**kwargs)

        monkeypatch.setattr(guild, "create_role", flaky)

        report = await ServerBuilder(guild, template).apply(BuildMode.EXTEND)

        assert report.roles_skipped >= 1
        assert not any("konnte nicht erstellt werden" in w for w in report.warnings)

    async def test_role_order_failure_is_explained(self, template, monkeypatch):
        """Der haeufigste Einrichtungsfehler: Bot-Rolle steht zu weit unten."""

        guild = FakeGuild()

        async def refuse(positions=None, reason=None):
            raise forbidden()

        monkeypatch.setattr(guild, "edit_role_positions", refuse)

        report = await ServerBuilder(guild, template).apply(BuildMode.REBUILD)

        assert any("Reihenfolge" in w for w in report.warnings)
        assert any("zu weit unten" in w for w in report.warnings)


# --------------------------------------------------------------------------- #
# Kanaele
# --------------------------------------------------------------------------- #

class TestChannelFailures:
    async def test_category_creation_failure_aborts_with_a_clear_message(
        self, template, monkeypatch
    ):
        """Ohne Kategorie haetten ihre Kanaele kein Zuhause."""

        guild = FakeGuild()

        async def refuse(name, **kwargs):
            raise forbidden()

        monkeypatch.setattr(guild, "create_category", refuse)

        with pytest.raises(BuildError) as excinfo:
            await ServerBuilder(guild, template).apply(BuildMode.EXTEND)

        assert "Kategorie" in str(excinfo.value)

    async def test_stage_channel_falls_back_to_voice(self, template, monkeypatch):
        """Stage braucht die Community-Funktion; ohne sie nimmt der Bot Voice."""

        guild = FakeGuild()

        async def refuse(name, **kwargs):
            raise http()

        monkeypatch.setattr(guild, "create_stage_channel", refuse)

        report = await ServerBuilder(guild, template).apply(BuildMode.EXTEND)

        assert report.channels_created > 0
        assert not any("stage" in w.lower() for w in report.warnings)

    async def test_forum_channel_falls_back_to_text(self, template, monkeypatch):
        guild = FakeGuild()

        async def refuse(name, **kwargs):
            raise http()

        monkeypatch.setattr(guild, "create_forum", refuse)

        report = await ServerBuilder(guild, template).apply(BuildMode.EXTEND)

        assert report.channels_created > 0


# --------------------------------------------------------------------------- #
# Wipe
# --------------------------------------------------------------------------- #

class TestWipe:
    """``REBUILD`` loescht. Was es nicht loeschen darf, ist wichtiger."""

    async def test_everyone_role_is_never_deleted(self, template):
        guild = FakeGuild()
        everyone = guild.default_role

        await ServerBuilder(guild, template).apply(BuildMode.REBUILD)

        assert not everyone.deleted, "@everyone wurde geloescht"
        assert everyone in guild.roles

    async def test_managed_roles_are_left_alone(self, template):
        """Integrations-Rollen gehoeren anderen Bots — Discord verbietet das
        ohnehin, aber der Builder soll es gar nicht erst versuchen."""

        guild = FakeGuild()
        bot_role = FakeRole(guild, "AnderesBot", 5, managed=True)
        guild.roles.append(bot_role)

        await ServerBuilder(guild, template).apply(BuildMode.REBUILD)

        assert not bot_role.deleted

    async def test_roles_above_the_bot_are_counted_as_undeletable(self, template):
        guild = FakeGuild(bot_top=10)
        higher = FakeRole(guild, "Owner", 50)
        guild.roles.append(higher)

        report = await ServerBuilder(guild, template).apply(BuildMode.REBUILD)

        assert not higher.deleted
        assert report.undeletable >= 1
        assert any("über der Bot-Rolle" in w for w in report.warnings)

    async def test_existing_channels_are_removed(self, template):
        guild = FakeGuild()
        old = FakeChannel(guild, "alter-kanal", "text")
        guild._channels[old.id] = old

        report = await ServerBuilder(guild, template).apply(BuildMode.REBUILD)

        assert old.deleted
        assert report.deleted_channels >= 1

    async def test_undeletable_channel_does_not_stop_the_wipe(
        self, template, monkeypatch
    ):
        guild = FakeGuild()
        stubborn = FakeChannel(guild, "bleibt", "text")
        deletable = FakeChannel(guild, "geht-weg", "text")
        guild._channels[stubborn.id] = stubborn
        guild._channels[deletable.id] = deletable

        async def refuse(reason=None):
            raise forbidden()

        monkeypatch.setattr(stubborn, "delete", refuse)

        report = await ServerBuilder(guild, template).apply(BuildMode.REBUILD)

        assert deletable.deleted, "Der loeschbare Kanal blieb stehen"
        assert report.undeletable >= 1

    async def test_already_deleted_channel_is_not_an_error(
        self, template, monkeypatch
    ):
        """Race mit dem Gateway: der Kanal ist weg, bevor wir ihn loeschen."""

        guild = FakeGuild()
        ghost = FakeChannel(guild, "geist", "text")
        guild._channels[ghost.id] = ghost

        async def gone(reason=None):
            raise discord.NotFound(_FakeResponse(), "schon weg")

        monkeypatch.setattr(ghost, "delete", gone)

        report = await ServerBuilder(guild, template).apply(BuildMode.REBUILD)

        assert report.undeletable == 0, "Ein bereits geloeschter Kanal zaehlt nicht"


# --------------------------------------------------------------------------- #
# Fortschritt
# --------------------------------------------------------------------------- #

class TestProgress:
    async def test_progress_reaches_the_end(self, template):
        """Ein Balken, der bei 80% stehen bleibt, sieht aus wie ein Absturz."""

        steps: list[tuple[int, int]] = []

        async def on_progress(label: str, step: int, total: int) -> None:
            steps.append((step, total))

        await ServerBuilder(FakeGuild(), template).apply(
            BuildMode.EXTEND, progress=on_progress
        )

        assert steps, "Es kam kein einziger Fortschritt an"
        last_step, total = steps[-1]
        assert last_step == total, f"Balken endet bei {last_step}/{total}"

    async def test_progress_never_goes_backwards(self, template):
        steps: list[int] = []

        async def on_progress(label: str, step: int, total: int) -> None:
            steps.append(step)

        await ServerBuilder(FakeGuild(), template).apply(
            BuildMode.EXTEND, progress=on_progress
        )

        assert steps == sorted(steps), f"Fortschritt springt zurueck: {steps}"

    async def test_a_broken_progress_hook_does_not_kill_the_build(self, template):
        """Der Balken ist Beiwerk. Er darf den Serverumbau nicht mitreissen."""

        async def explode(label: str, step: int, total: int) -> None:
            raise RuntimeError("Anzeige kaputt")

        builder = ServerBuilder(FakeGuild(), template)
        try:
            report = await builder.apply(BuildMode.EXTEND, progress=explode)
        except RuntimeError:
            pytest.fail(
                "Ein Fehler in der Fortschrittsanzeige hat den Bau abgebrochen"
            )
        assert report.channels_created > 0


# --------------------------------------------------------------------------- #
# Bericht
# --------------------------------------------------------------------------- #

class TestReport:
    async def test_warnings_are_deduplicated(self, template):
        """Zwanzig Mal dieselbe Warnung ist keine Information."""

        from core.builder import BuildReport

        report = BuildReport(mode=BuildMode.EXTEND, template_key="x")
        for _ in range(5):
            report.warn("Dasselbe Problem")

        assert report.warnings == ["Dasselbe Problem"]

    async def test_totals_add_up(self, template):
        guild = FakeGuild()
        report = await ServerBuilder(guild, template).apply(BuildMode.EXTEND)

        assert report.total_created == (
            report.roles_created + report.categories_created + report.channels_created
        )
        assert report.channels_created == guild.created_channels
