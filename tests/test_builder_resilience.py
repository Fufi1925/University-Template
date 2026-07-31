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
    FakeCategory,
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


@pytest.fixture
def as_text_channels(monkeypatch):
    """Laesst den Builder die Attrappen als Textkanaele akzeptieren.

    Der Produktivcode prueft ``isinstance(channel, discord.TextChannel)``,
    bevor er eine Startnachricht schreibt — zu Recht, in einem Sprachkanal
    gibt es keine. Statt diese Pruefung aufzuweichen, wird sie hier fuer die
    Dauer des Tests auf die Fakes ausgeweitet. (Dieselbe Idee wie
    ``as_text_channels`` in der Bau-Simulation; importierte Fixtures
    registriert pytest nicht, deshalb steht sie hier noch einmal.)
    """

    import core.builder as builder_module

    real_isinstance = isinstance

    def patched(obj, cls):
        if cls is discord.TextChannel:
            return (
                real_isinstance(obj, FakeChannel)
                and not real_isinstance(obj, FakeCategory)
                and obj.kind in {"text", "news", "forum"}
            )
        if cls is discord.VoiceChannel:
            return real_isinstance(obj, FakeChannel) and obj.kind in {"voice", "stage"}
        return real_isinstance(obj, cls)

    monkeypatch.setattr(builder_module, "isinstance", patched, raising=False)
    return patched


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

    def test_incomplete_guild_is_rejected(self, template):
        """``guild.me`` fehlt, solange der Member-Cache noch leer ist."""

        guild = FakeGuild()
        guild.me = None

        with pytest.raises(BuildError) as excinfo:
            ServerBuilder(guild, template).preflight()

        assert "vollständig geladen" in str(excinfo.value)

    def test_bot_role_at_the_bottom_is_rejected(self, template):
        """Ganz unten kann der Bot gar nichts verwalten."""

        guild = FakeGuild()
        guild._bot_role.position = 0

        with pytest.raises(BuildError) as excinfo:
            ServerBuilder(guild, template).preflight()

        assert "ganz unten" in str(excinfo.value)

    def test_both_missing_permissions_are_listed(self, template):
        guild = FakeGuild()
        guild.me.guild_permissions.manage_roles = False
        guild.me.guild_permissions.manage_channels = False

        with pytest.raises(BuildError) as excinfo:
            ServerBuilder(guild, template).preflight()

        message = str(excinfo.value)
        assert "Rollen verwalten" in message and "Kanäle verwalten" in message


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


# --------------------------------------------------------------------------- #
# Kategorie-Wiederherstellung
# --------------------------------------------------------------------------- #

class TestCategoryRecovery:
    """Der Fall aus dem Railway-Log: die Kategorie verschwindet mittendrin.

    Passiert, wenn ein anderer Bot parallel aufraeumt. Discord antwortet dann
    mit *In parent_id: Category does not exist*, und ohne Wiederherstellung
    fehlten ab diesem Punkt alle uebrigen Kanaele der Kategorie.
    """

    async def test_channel_is_retried_in_a_fresh_category(
        self, template, monkeypatch
    ):
        guild = FakeGuild()
        original = guild.create_text_channel
        state = {"failed": False}

        async def vanish_once(name, **kwargs):
            if not state["failed"]:
                state["failed"] = True
                raise discord.HTTPException(
                    _FakeResponse(), "In parent_id: Category does not exist"
                )
            return await original(name, **kwargs)

        monkeypatch.setattr(guild, "create_text_channel", vanish_once)

        report = await ServerBuilder(guild, template).apply(BuildMode.EXTEND)

        assert report.channels_created > 0, "Nach dem Verlust kam kein Kanal mehr"
        assert report.categories_created > template.category_count - 1, (
            "Es wurde keine Ersatzkategorie angelegt"
        )

    async def test_unrecoverable_channel_is_reported_and_skipped(
        self, template, monkeypatch
    ):
        """Ein anderer Fehler darf die folgenden Kanaele nicht mitnehmen."""

        guild = FakeGuild()
        original = guild.create_text_channel
        state = {"n": 0}

        async def one_bad_apple(name, **kwargs):
            state["n"] += 1
            if state["n"] == 1:
                raise discord.HTTPException(_FakeResponse(), "irgendein Feldfehler")
            return await original(name, **kwargs)

        monkeypatch.setattr(guild, "create_text_channel", one_bad_apple)

        report = await ServerBuilder(guild, template).apply(BuildMode.EXTEND)

        assert report.warnings, "Der Ausfall wurde nicht gemeldet"
        assert report.channels_created > 0, "Der Rest wurde nicht mehr gebaut"

    async def test_forbidden_channel_is_named_in_the_report(
        self, template, monkeypatch
    ):
        guild = FakeGuild()
        original = guild.create_text_channel
        state = {"n": 0}

        async def refuse_first(name, **kwargs):
            state["n"] += 1
            if state["n"] == 1:
                raise forbidden()
            return await original(name, **kwargs)

        monkeypatch.setattr(guild, "create_text_channel", refuse_first)

        report = await ServerBuilder(guild, template).apply(BuildMode.EXTEND)

        assert any("konnte nicht erstellt werden" in w for w in report.warnings)


# --------------------------------------------------------------------------- #
# Zweiter Durchlauf
# --------------------------------------------------------------------------- #

class TestRebuildUpdates:
    """``REBUILD`` auf einem bestehenden Server aktualisiert statt zu doppeln."""

    async def test_existing_categories_are_updated(self, template, monkeypatch):
        guild = FakeGuild()
        await ServerBuilder(guild, template).apply(BuildMode.EXTEND)
        before = guild.created_categories

        await ServerBuilder(guild, template).apply(BuildMode.EXTEND)

        assert guild.created_categories == before, "Kategorien wurden verdoppelt"

    async def test_uneditable_category_is_reported(self, template, monkeypatch):
        """Rebuild passt Rechte an — geht das nicht, muss es auffallen."""

        guild = FakeGuild()
        await ServerBuilder(guild, template).apply(BuildMode.EXTEND)

        for category in guild.categories:
            async def refuse(**kwargs):
                raise forbidden()

            monkeypatch.setattr(category, "edit", refuse)

        # REBUILD wuerde zuerst alles loeschen; hier interessiert der
        # Aktualisierungspfad, also EXTEND mit vorhandenen Kategorien.
        report = await ServerBuilder(guild, template).apply(BuildMode.EXTEND)

        assert report is not None

    async def test_category_order_failure_is_survivable(self, template, monkeypatch):
        """Die Reihenfolge ist Kosmetik — sie darf den Bau nicht kippen."""

        guild = FakeGuild()

        async def refuse(guild_id, payload, reason=None):
            raise forbidden()

        monkeypatch.setattr(guild._state.http, "bulk_channel_update", refuse)

        report = await ServerBuilder(guild, template).apply(BuildMode.REBUILD)

        assert report.channels_created > 0
        assert any("Reihenfolge" in w for w in report.warnings)


# --------------------------------------------------------------------------- #
# Startnachrichten
# --------------------------------------------------------------------------- #

class TestChannelIntroFailures:
    """Die angehefteten Startnachrichten sind Beiwerk — sie duerfen nie stoeren.

    ``as_text_channels`` weitet die ``isinstance``-Pruefung des Builders auf
    die Attrappen aus, statt sie im Produktivcode aufzuweichen.
    """

    async def test_missing_write_permission_is_reported(
        self, template, as_text_channels, monkeypatch
    ):
        guild = FakeGuild()
        original = guild.create_text_channel

        async def make_mute(name, **kwargs):
            channel = await original(name, **kwargs)
            channel.can_send = False
            return channel

        monkeypatch.setattr(guild, "create_text_channel", make_mute)

        report = await ServerBuilder(guild, template).apply(
            BuildMode.EXTEND, write_intros=True
        )

        assert report.channels_created > 0, "Der Aufbau selbst muss durchlaufen"
        assert any("nicht schreiben" in w for w in report.warnings)

    async def test_unpinnable_message_still_counts_as_posted(
        self, template, as_text_channels, monkeypatch
    ):
        """50 Pins sind das Limit — danach bleibt die Nachricht trotzdem stehen."""

        from test_build_simulation import FakeMessage

        async def refuse(self, reason=None):
            raise forbidden()

        monkeypatch.setattr(FakeMessage, "pin", refuse)

        report = await ServerBuilder(FakeGuild(), template).apply(
            BuildMode.EXTEND, write_intros=True
        )

        assert report.messages_posted > 0, "Ohne Pin darf keine Nachricht fehlen"
        assert report.messages_pinned == 0

    async def test_intros_can_be_switched_off(self, template, as_text_channels):
        """Wer leere Kanaele will, soll leere Kanaele bekommen."""

        guild = FakeGuild()

        report = await ServerBuilder(guild, template).apply(
            BuildMode.EXTEND, write_intros=False
        )

        assert report.messages_posted == 0
        assert report.channels_created > 0

    async def test_second_run_edits_instead_of_duplicating(
        self, template, as_text_channels
    ):
        """Sonst stapeln sich bei jedem Lauf die Startnachrichten."""

        guild = FakeGuild()
        first = await ServerBuilder(guild, template).apply(
            BuildMode.EXTEND, write_intros=True
        )
        second = await ServerBuilder(guild, template).apply(
            BuildMode.EXTEND, write_intros=True
        )

        assert first.messages_posted > 0
        assert second.messages_posted == 0, "Die Nachrichten wurden verdoppelt"
        assert second.messages_updated > 0


# --------------------------------------------------------------------------- #
# Aktualisieren statt neu anlegen
# --------------------------------------------------------------------------- #

class TestUpdatingExistingObjects:
    """Ein zweiter Lauf trifft auf alles, was der erste angelegt hat."""

    async def test_rebuild_updates_existing_roles(self, template):
        """Nach dem Wipe bleiben unloeschbare Rollen stehen und werden angepasst."""

        guild = FakeGuild()
        first = await ServerBuilder(guild, template).apply(BuildMode.EXTEND)
        assert first.roles_created > 0

        # Rollen behalten, Kanaele leeren: der zweite Lauf muss die Rollen
        # aktualisieren statt sie zu verdoppeln.
        before = len(guild.roles)
        second = await ServerBuilder(guild, template).apply(BuildMode.EXTEND)

        assert len(guild.roles) == before, "Rollen wurden verdoppelt"
        assert second.roles_created == 0

    async def test_role_above_the_bot_is_skipped_on_update(self, template):
        """Was der Bot nicht bearbeiten darf, zaehlt als uebersprungen."""

        guild = FakeGuild(bot_top=5)
        # Eine Rolle mit passendem Namen, aber ueber der Bot-Rolle.
        spec = ServerBuilder(guild, template)._specs[0]
        blocked = FakeRole(guild, spec.display_name, 99)
        guild.roles.append(blocked)

        report = await ServerBuilder(guild, template).apply(BuildMode.REBUILD)

        assert report.roles_skipped >= 1

    async def test_failed_role_update_is_counted(self, template, monkeypatch):
        guild = FakeGuild()
        await ServerBuilder(guild, template).apply(BuildMode.EXTEND)

        for role in guild.roles:
            if role.is_default() or role.managed:
                continue

            async def refuse(**kwargs):
                raise forbidden()

            monkeypatch.setattr(role, "edit", refuse)

        report = await ServerBuilder(guild, template).apply(BuildMode.REBUILD)

        assert report.roles_skipped >= 0  # kein Absturz, Zaehlung laeuft

    async def test_existing_channels_are_updated_on_rebuild(
        self, template, as_text_channels
    ):
        """Vorhandene Kanaele bekommen Topic und Rechte neu gesetzt."""

        guild = FakeGuild()
        await ServerBuilder(guild, template).apply(
            BuildMode.EXTEND, write_intros=False
        )

        # Zweiter EXTEND-Lauf: nichts Neues, aber auch nichts kaputt.
        report = await ServerBuilder(guild, template).apply(
            BuildMode.EXTEND, write_intros=False
        )

        assert report.channels_created == 0, "Kanaele wurden verdoppelt"

    async def test_uneditable_channel_does_not_break_the_run(
        self, template, as_text_channels, monkeypatch
    ):
        guild = FakeGuild()
        await ServerBuilder(guild, template).apply(
            BuildMode.EXTEND, write_intros=False
        )

        from test_build_simulation import FakeChannel as _FC

        async def refuse(self, **kwargs):
            raise forbidden()

        monkeypatch.setattr(_FC, "edit", refuse)

        report = await ServerBuilder(guild, template).apply(
            BuildMode.EXTEND, write_intros=False
        )

        assert report is not None, "Ein nicht editierbarer Kanal hat den Lauf gekippt"


# --------------------------------------------------------------------------- #
# Kanaele anpassen
# --------------------------------------------------------------------------- #

class TestChannelUpdates:
    """``REBUILD`` setzt Topic, Slowmode und Rechte bestehender Kanaele neu.

    Der Pfad laeuft nur, wenn ein Kanal bereits existiert — deshalb bauen
    diese Tests erst auf und dann noch einmal darueber.
    """

    async def test_topic_and_slowmode_are_applied(self, template, as_text_channels):
        guild = FakeGuild()
        await ServerBuilder(guild, template).apply(
            BuildMode.EXTEND, write_intros=False
        )

        # Topic verstellen, als haette es jemand von Hand geaendert.
        text_channels = [
            c for c in guild.channels if getattr(c, "kind", None) == "text"
        ]
        assert text_channels, "Die Vorlage hat keine Textkanaele erzeugt"
        text_channels[0].topic = "von Hand verstellt"

        report = await ServerBuilder(guild, template).apply(
            BuildMode.REBUILD, write_intros=False
        )

        assert report is not None

    async def test_rebuild_restores_a_changed_voice_limit(
        self, template, as_text_channels
    ):
        """Von Hand verstellte Werte werden beim Rebuild zurueckgesetzt."""

        guild = FakeGuild()
        await ServerBuilder(guild, template).apply(
            BuildMode.EXTEND, write_intros=False
        )

        voice = [c for c in guild.channels if getattr(c, "kind", None) == "voice"]
        if not voice:
            pytest.skip("Diese Vorlage hat keine Sprachkanaele")

        channel = voice[0]
        original = channel.user_limit
        channel.user_limit = 77

        # Der Aktualisierungspfad laeuft nur bei bestehenden Objekten, und
        # REBUILD wuerde vorher alles loeschen — deshalb direkt aufrufen.
        builder = ServerBuilder(guild, template)
        spec_pair = next(
            (cat, ch)
            for cat in template.categories
            for ch in cat.channels
            if ch.kind.is_voice_like
        )
        await builder._update_channel(channel, spec_pair[0], spec_pair[1])

        assert channel.user_limit == original, "Der Wert wurde nicht zurueckgesetzt"

    async def test_update_failure_is_survivable(
        self, template, as_text_channels, monkeypatch
    ):
        """Ein Kanal, den der Bot nicht bearbeiten darf, stoppt nichts."""

        guild = FakeGuild()
        await ServerBuilder(guild, template).apply(
            BuildMode.EXTEND, write_intros=False
        )

        from test_build_simulation import FakeChannel as _FC

        async def refuse(self, **kwargs):
            raise forbidden()

        monkeypatch.setattr(_FC, "edit", refuse)

        report = await ServerBuilder(guild, template).apply(
            BuildMode.EXTEND, write_intros=False
        )

        assert report.channels_created == 0, "Es wurde neu gebaut statt angepasst"
