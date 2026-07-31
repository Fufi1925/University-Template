"""Die Schutzpruefungen vor und waehrend eines Serverumbaus.

``_run_build`` ist der eingriffsintensivste Pfad im gesamten Projekt: danach
sieht der Server eines Fremden anders aus. Vier Waechter stehen davor —
Serverkontext, Berechtigung, Doppellauf-Sperre und Preflight — und keiner
davon war bisher geprueft.

Getestet wird hier bewusst das Verhalten an den Raendern, nicht der Bau
selbst (den deckt ``test_build_simulation.py`` ab):

* Wird ohne Berechtigung wirklich **nichts** angefasst?
* Bleibt die Sperre nach einem Fehler zurueck und blockiert den Server
  dauerhaft?
* Bekommt der Nutzer bei jedem Abbruch eine verstaendliche Meldung?
"""

from __future__ import annotations

import sys
from pathlib import Path

import discord
import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import config
from core.builder import BuildError, BuildMode
from core.registry import TemplateRegistry


@pytest.fixture(scope="module")
def registry() -> TemplateRegistry:
    return TemplateRegistry(config.TEMPLATE_DIR).load()


@pytest.fixture(scope="module")
def template(registry):
    return registry.free[0]


# --------------------------------------------------------------------------- #
# Nachbauten
# --------------------------------------------------------------------------- #

class FakePermissions:
    def __init__(self, manage_guild: bool = True) -> None:
        self.manage_guild = manage_guild


class FakeUser:
    """Ein Klickender ohne Server-Rechte, sofern nicht anders gesagt."""

    def __init__(self, *, manage_guild: bool = True) -> None:
        self.id = 7
        self.guild_permissions = FakePermissions(manage_guild)


class FakeGuild:
    def __init__(self) -> None:
        self.id = 123
        self.name = "Testserver"


class FakeResponse:
    def __init__(self) -> None:
        self.sent: list[object] = []
        self.edited: list[object] = []

    def is_done(self) -> bool:
        return bool(self.sent or self.edited)

    async def send_message(self, *, view=None, ephemeral: bool = False, **kw) -> None:
        self.sent.append(view)

    async def edit_message(self, *, view=None, **kw) -> None:
        self.edited.append(view)


class FakeFollowup:
    def __init__(self) -> None:
        self.sent: list[object] = []

    async def send(self, *, view=None, ephemeral: bool = False, **kw) -> None:
        self.sent.append(view)


class FakeInteraction:
    def __init__(self, guild, user) -> None:
        self.guild = guild
        self.user = user
        self.response = FakeResponse()
        self.followup = FakeFollowup()
        self.originals: list[object] = []

    async def edit_original_response(self, *, view=None, **kw) -> None:
        """Der Weg, ueber den Fortschritt und Endbericht aktualisiert werden."""

        self.originals.append(view)

    @property
    def shown(self) -> list[object]:
        return [
            *self.response.sent,
            *self.response.edited,
            *self.followup.sent,
            *self.originals,
        ]


class FakeBot:
    def __init__(self) -> None:
        self.active_builds: set[int] = set()


def rendered(view) -> str:
    out: list[str] = []

    def walk(items) -> None:
        for item in items:
            if isinstance(item, dict):
                if isinstance(item.get("content"), str):
                    out.append(item["content"])
                for value in item.values():
                    if isinstance(value, (list, dict)):
                        walk(value if isinstance(value, list) else [value])
            elif isinstance(item, list):
                walk(item)

    walk(view.to_components())
    return "\n".join(out)


def all_text(interaction: FakeInteraction) -> str:
    return "\n".join(rendered(view) for view in interaction.shown if view is not None)


@pytest.fixture(autouse=True)
def members_pass_isinstance(monkeypatch):
    """``_can_manage`` prueft auf ``discord.Member`` — siehe test_widget_callbacks."""

    import ui.views as views

    real_isinstance = isinstance

    def lenient(obj, classinfo):
        if classinfo is discord.Member and type(obj) is FakeUser:
            return True
        return real_isinstance(obj, classinfo)

    monkeypatch.setitem(views.__dict__, "isinstance", lenient)
    yield


async def run_build(interaction, bot, template, **kw):
    from ui.views import _run_build

    await _run_build(interaction, bot, template, BuildMode.EXTEND, **kw)


# --------------------------------------------------------------------------- #
# Die vier Waechter
# --------------------------------------------------------------------------- #

class TestGuards:
    async def test_refuses_outside_a_server(self, template):
        """In Direktnachrichten gibt es nichts zu bauen."""

        interaction = FakeInteraction(None, FakeUser())
        bot = FakeBot()

        await run_build(interaction, bot, template)

        assert "Nur auf Servern verfügbar" in all_text(interaction)
        assert not bot.active_builds, "Die Sperre wurde trotzdem gesetzt"

    async def test_refuses_without_manage_guild(self, template):
        """Sonst baut jeder Gast den Server um."""

        interaction = FakeInteraction(FakeGuild(), FakeUser(manage_guild=False))
        bot = FakeBot()

        await run_build(interaction, bot, template)

        text = all_text(interaction)
        assert "Keine Berechtigung" in text
        assert "Server verwalten" in text, "Die Meldung nennt das fehlende Recht nicht"
        assert not bot.active_builds

    async def test_refuses_while_another_build_runs(self, template):
        """Zwei parallele Laeufe wuerden sich gegenseitig die Kanaele wegziehen."""

        guild = FakeGuild()
        interaction = FakeInteraction(guild, FakeUser())
        bot = FakeBot()
        bot.active_builds.add(guild.id)

        await run_build(interaction, bot, template)

        assert "läuft bereits" in all_text(interaction)
        assert bot.active_builds == {guild.id}, "Die fremde Sperre wurde angefasst"

    async def test_preflight_failure_releases_the_lock(self, template, monkeypatch):
        """Der wichtigste Fall: nach einem Abbruch muss der Server frei sein.

        Bleibt die ID in ``active_builds`` haengen, ist der Server bis zum
        naechsten Neustart des Bots blockiert — mit der irrefuehrenden Meldung
        'Einrichtung laeuft bereits'.
        """

        import ui.views as views

        def explode(self):
            raise BuildError("Die Bot-Rolle steht zu weit unten.")

        monkeypatch.setattr(views.ServerBuilder, "preflight", explode)

        guild = FakeGuild()
        interaction = FakeInteraction(guild, FakeUser())
        bot = FakeBot()

        await run_build(interaction, bot, template)

        text = all_text(interaction)
        assert "nicht möglich" in text.lower()
        assert "zu weit unten" in text, "Der Grund wird nicht durchgereicht"
        assert not bot.active_builds, "Der Server bleibt dauerhaft gesperrt"

    async def test_lock_is_released_after_a_failed_build(self, template, monkeypatch):
        """Auch wenn der Bau selbst mittendrin scheitert."""

        import ui.views as views

        def ok(self):
            return None

        async def fail(self, mode, progress=None, write_intros=True):
            raise BuildError("Discord hat abgelehnt.")

        monkeypatch.setattr(views.ServerBuilder, "preflight", ok)
        monkeypatch.setattr(views.ServerBuilder, "apply", fail)

        guild = FakeGuild()
        interaction = FakeInteraction(guild, FakeUser())
        bot = FakeBot()

        await run_build(interaction, bot, template)

        assert not bot.active_builds
        assert "abgebrochen" in all_text(interaction).lower()

    async def test_missing_permissions_are_explained_not_dumped(
        self, template, monkeypatch
    ):
        """Ein Forbidden soll die Loesung nennen, nicht den Statuscode."""

        import ui.views as views

        class _Resp:
            status = 403
            reason = "Forbidden"

        async def forbidden(self, mode, progress=None, write_intros=True):
            raise discord.Forbidden(_Resp(), "missing permissions")

        monkeypatch.setattr(views.ServerBuilder, "preflight", lambda self: None)
        monkeypatch.setattr(views.ServerBuilder, "apply", forbidden)

        interaction = FakeInteraction(FakeGuild(), FakeUser())
        bot = FakeBot()

        await run_build(interaction, bot, template)

        text = all_text(interaction)
        assert "Rollen verwalten" in text and "Kanäle verwalten" in text
        assert not bot.active_builds


class TestGuardOrder:
    """Die Reihenfolge der Pruefungen ist selbst eine Zusicherung."""

    async def test_permission_is_checked_before_the_lock(self, template):
        """Ein Unbefugter darf nicht einmal erfahren, dass ein Bau laeuft."""

        guild = FakeGuild()
        bot = FakeBot()
        bot.active_builds.add(guild.id)

        interaction = FakeInteraction(guild, FakeUser(manage_guild=False))
        await run_build(interaction, bot, template)

        assert "Keine Berechtigung" in all_text(interaction)
        assert "läuft bereits" not in all_text(interaction)

    async def test_guild_is_checked_before_the_permission(self, template):
        """Ohne Server gibt es keine Guild-Rechte, die man pruefen koennte."""

        interaction = FakeInteraction(None, FakeUser(manage_guild=False))
        await run_build(interaction, FakeBot(), template)

        assert "Nur auf Servern verfügbar" in all_text(interaction)
