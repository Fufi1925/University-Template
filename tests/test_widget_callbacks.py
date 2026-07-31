"""Was passiert, wenn jemand tatsaechlich auf die Buttons klickt.

Die Widgets waren der am schwaechsten geprueften Teil des Projekts: getestet
war, dass sie einen Neustart ueberleben und die richtigen ``custom_id`` tragen
— nicht aber, was ihre Callbacks tun. Genau dort vergibt der Bot jedoch
Rollen, entfernt die Eingangssperre und legt Threads an.

Diese Datei ruft die Callbacks direkt auf, gegen nachgebaute Discord-Objekte.
Geprueft wird das Verhalten, das ein Mitglied merkt:

* wird die Rolle vergeben und die Unverified-Rolle entfernt?
* was passiert, wenn die Rolle fehlt oder der Bot sie nicht vergeben darf?
* bekommt der Nutzer in **jedem** Fall eine Rueckmeldung, statt ins Leere zu
  klicken?
"""

from __future__ import annotations

import sys
from pathlib import Path

import discord
import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from ui.widgets import (
    SELF_ROLES,
    ChecklistView,
    RulesView,
    SelfRoleView,
    TicketView,
    VerifyView,
    _find_role,
)

# --------------------------------------------------------------------------- #
# Nachbauten
# --------------------------------------------------------------------------- #

class FakeRole:
    def __init__(self, name: str, *, assignable: bool = True, default: bool = False) -> None:
        self.name = name
        self.id = abs(hash(name)) % 10**8
        self._assignable = assignable
        self._default = default

    def is_default(self) -> bool:
        return self._default

    def is_assignable(self) -> bool:
        return self._assignable

    def __repr__(self) -> str:  # pragma: no cover - nur fuer Fehlermeldungen
        return f"<Role {self.name}>"


class FakeMember:
    """Ein Mitglied, das sich Rollenaenderungen merkt."""

    def __init__(self, roles: list[FakeRole] | None = None, *, name: str = "tester") -> None:
        self.roles: list[FakeRole] = list(roles or [])
        self.name = name
        self.id = 4242
        self.mention = f"<@{self.id}>"
        self.added: list[str] = []
        self.removed: list[str] = []
        #: Rollen, deren Vergabe fehlschlagen soll.
        self.reject: set[str] = set()

    async def add_roles(self, role: FakeRole, reason: str | None = None) -> None:
        if role.name in self.reject:
            raise discord.HTTPException(_Response(), "abgelehnt")
        self.roles.append(role)
        self.added.append(role.name)

    async def remove_roles(self, role: FakeRole, reason: str | None = None) -> None:
        if role.name in self.reject:
            raise discord.HTTPException(_Response(), "abgelehnt")
        self.roles = [r for r in self.roles if r.name != role.name]
        self.removed.append(role.name)


class _Response:
    """Minimales aiohttp-Response-Double fuer discord.HTTPException."""

    status = 400
    reason = "Bad Request"




class FakeGuild:
    def __init__(self, roles: list[FakeRole] | None = None) -> None:
        self.roles = list(roles or [])
        self.id = 999
        self.created: list[str] = []
        self.create_fails = False

    async def create_role(self, *, name: str, reason: str | None = None, **kw) -> FakeRole:
        if self.create_fails:
            raise discord.HTTPException(_Response(), "keine Rechte")
        role = FakeRole(name)
        self.roles.append(role)
        self.created.append(name)
        return role


class FakeResponse:
    def __init__(self) -> None:
        self.messages: list[object] = []
        self.deferred = False

    def is_done(self) -> bool:
        return self.deferred or bool(self.messages)

    async def send_message(self, *, view=None, ephemeral: bool = False, **kw) -> None:
        self.messages.append(view)

    async def defer(self, *, ephemeral: bool = False, thinking: bool = False) -> None:
        self.deferred = True


class FakeFollowup:
    def __init__(self) -> None:
        self.messages: list[object] = []

    async def send(self, *, view=None, ephemeral: bool = False, **kw) -> None:
        self.messages.append(view)


class FakeInteraction:
    def __init__(self, guild: FakeGuild | None, user: object, channel: object = None) -> None:
        self.guild = guild
        self.user = user
        self.channel = channel
        self.response = FakeResponse()
        self.followup = FakeFollowup()

    @property
    def replies(self) -> list[object]:
        """Alles, was der Nutzer zu sehen bekommt — egal ueber welchen Weg."""

        return [*self.response.messages, *self.followup.messages]


@pytest.fixture(autouse=True)
def members_pass_isinstance(monkeypatch):
    """``isinstance(user, discord.Member)`` fuer die Attrappen wahr machen.

    Die Callbacks pruefen die Klasse, bevor sie Rollen anfassen — zu Recht,
    denn in Direktnachrichten gibt es kein Member-Objekt. Ein echtes
    ``discord.Member`` aufzubauen hiesse, den halben Gateway-Zustand
    nachzustellen, und davon zu erben scheitert an dessen Properties ohne
    Setter.

    Deshalb bekommt nur das Modul ``ui.widgets`` ein nachsichtiges
    ``isinstance``. Der Rest des Prozesses bleibt unberuehrt, und der echte
    Pfad — Direktnachricht ohne Member — wird weiterhin korrekt abgelehnt,
    weil dort ``guild is None`` schon vorher greift.
    """

    import builtins

    import ui.widgets as widgets

    real_isinstance = builtins.isinstance

    def lenient(obj, classinfo):
        if classinfo is discord.Member and type(obj) is FakeMember:
            return True
        if classinfo is discord.Guild and type(obj) is FakeGuild:
            return True
        return real_isinstance(obj, classinfo)

    monkeypatch.setitem(widgets.__dict__, "isinstance", lenient)
    yield


def rendered(view) -> str:
    """Alle Textbausteine einer View als ein durchsuchbarer String."""

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


def button_of(view) -> object:
    """Den ersten Button einer View herausfischen."""

    for child in view.walk_children():
        if isinstance(child, discord.ui.Button):
            return child
    raise AssertionError("View enthaelt keinen Button")


def select_of(view, chosen: list[str] | None = None) -> object:
    """Das Auswahlmenue einer View holen und eine Auswahl hineinlegen.

    ``Select.values`` ist ein Property, das die Auswahl aus einem
    ContextVar oder aus ``_values`` liest — beim direkten Aufruf des
    Callbacks gibt es keinen Gateway, der das fuellt.
    """

    for child in view.walk_children():
        if isinstance(child, discord.ui.Select):
            if chosen is not None:
                child._values = list(chosen)
            return child
    raise AssertionError("View enthaelt kein Auswahlmenue")


# --------------------------------------------------------------------------- #
# Rollensuche
# --------------------------------------------------------------------------- #

class TestFindRole:
    def test_matches_through_small_caps_decoration(self):
        """Die Rollen heissen dekoriert — gesucht wird im Klartext."""

        guild = FakeGuild([FakeRole("✅・ᴠᴇʀɪꜰɪᴇᴅ")])
        assert _find_role(guild, "verified") is not None

    def test_ignores_the_everyone_role(self):
        guild = FakeGuild([FakeRole("@everyone", default=True)])
        assert _find_role(guild, "everyone") is None

    def test_first_needle_wins(self):
        """Die Reihenfolge der Suchbegriffe ist eine Rangfolge."""

        guild = FakeGuild([FakeRole("Member"), FakeRole("Verified")])
        assert _find_role(guild, "verified", "member").name == "Verified"

    def test_returns_none_when_nothing_matches(self):
        assert _find_role(FakeGuild([FakeRole("Irgendwas")]), "verified") is None


# --------------------------------------------------------------------------- #
# Verify / Regeln
# --------------------------------------------------------------------------- #

class TestVerifyButton:
    async def test_grants_role_and_opens_the_gate(self):
        """Der Kernfall: Rolle rauf, Eingangssperre runter."""

        verified = FakeRole("✅・ᴠᴇʀɪꜰɪᴇᴅ")
        unverified = FakeRole("🚪・ᴜɴᴠᴇʀɪꜰɪᴇᴅ")
        guild = FakeGuild([verified, unverified])
        member = FakeMember([unverified])

        interaction = FakeInteraction(guild, member)
        await button_of(VerifyView()).callback(interaction)

        assert member.added == [verified.name], "Verified wurde nicht vergeben"
        assert member.removed == [unverified.name], "Die Schleuse bleibt zu"
        assert interaction.replies, "Der Nutzer bekommt keine Rueckmeldung"

    async def test_reports_missing_role_instead_of_failing_silently(self):
        guild = FakeGuild([FakeRole("Irgendwas")])
        member = FakeMember()

        interaction = FakeInteraction(guild, member)
        await button_of(VerifyView()).callback(interaction)

        assert not member.added
        assert "Rolle fehlt" in rendered(interaction.replies[0])

    async def test_already_verified_is_not_an_error(self):
        verified = FakeRole("✅・ᴠᴇʀɪꜰɪᴇᴅ")
        member = FakeMember([verified])

        interaction = FakeInteraction(FakeGuild([verified]), member)
        await button_of(VerifyView()).callback(interaction)

        assert not member.added
        assert "Schon erledigt" in rendered(interaction.replies[0])

    async def test_explains_when_the_bot_role_is_too_low(self):
        """Der haeufigste Einrichtungsfehler ueberhaupt."""

        verified = FakeRole("✅・ᴠᴇʀɪꜰɪᴇᴅ", assignable=False)
        member = FakeMember()

        interaction = FakeInteraction(FakeGuild([verified]), member)
        await button_of(VerifyView()).callback(interaction)

        text = rendered(interaction.replies[0])
        assert "Nicht möglich" in text
        assert "über dieser Rolle" in text, "Der Hinweis nennt die Loesung nicht"

    async def test_http_failure_still_answers_the_user(self):
        verified = FakeRole("✅・ᴠᴇʀɪꜰɪᴇᴅ")
        member = FakeMember()
        member.reject.add(verified.name)

        interaction = FakeInteraction(FakeGuild([verified]), member)
        await button_of(VerifyView()).callback(interaction)

        assert "Fehlgeschlagen" in rendered(interaction.replies[0])

    async def test_ignores_direct_messages(self):
        """Ohne Guild gibt es keine Rollen — und keinen Absturz."""

        interaction = FakeInteraction(None, FakeMember())
        await button_of(VerifyView()).callback(interaction)
        assert not interaction.replies

    async def test_gate_stays_closed_when_unverified_is_unassignable(self):
        """Kann die Sperre nicht entfernt werden, bleibt die Vergabe trotzdem."""

        verified = FakeRole("✅・ᴠᴇʀɪꜰɪᴇᴅ")
        unverified = FakeRole("🚪・ᴜɴᴠᴇʀɪꜰɪᴇᴅ", assignable=False)
        member = FakeMember([unverified])

        interaction = FakeInteraction(FakeGuild([verified, unverified]), member)
        await button_of(VerifyView()).callback(interaction)

        assert member.added == [verified.name]
        assert not member.removed


class TestRulesButton:
    async def test_accepting_rules_verifies(self):
        verified = FakeRole("✅・ᴠᴇʀɪꜰɪᴇᴅ")
        member = FakeMember()

        interaction = FakeInteraction(FakeGuild([verified]), member)
        await button_of(RulesView()).callback(interaction)

        assert member.added == [verified.name]
        assert "akzeptiert" in rendered(interaction.replies[0])


# --------------------------------------------------------------------------- #
# Selbstrollen
# --------------------------------------------------------------------------- #

class TestSelfRoles:
    async def test_creates_missing_roles_on_first_use(self):
        """Das Widget soll auf jedem Server funktionieren, auch ohne Vorarbeit."""

        guild = FakeGuild()
        member = FakeMember()
        select = select_of(SelfRoleView(), ["Events"])

        interaction = FakeInteraction(guild, member)
        await select.callback(interaction)

        assert guild.created, "Die fehlende Rolle wurde nicht angelegt"
        assert member.added == [guild.created[0]]
        assert "Hinzugefügt" in rendered(interaction.followup.messages[0])

    async def test_deselecting_removes_the_role(self):
        events = FakeRole("🎉・Events")
        member = FakeMember([events])
        select = select_of(SelfRoleView(), [])

        interaction = FakeInteraction(FakeGuild([events]), member)
        await select.callback(interaction)

        assert member.removed == [events.name]
        assert "Entfernt" in rendered(interaction.followup.messages[0])

    async def test_unchanged_selection_says_so(self):
        select = select_of(SelfRoleView(), [])

        interaction = FakeInteraction(FakeGuild(), FakeMember())
        await select.callback(interaction)

        assert "nichts geändert" in rendered(interaction.followup.messages[0])

    async def test_failure_is_reported_but_does_not_abort_the_rest(self):
        guild = FakeGuild()
        guild.create_fails = True
        member = FakeMember()
        select = select_of(SelfRoleView(), ["Events", "Gaming"])

        interaction = FakeInteraction(guild, member)
        await select.callback(interaction)

        text = rendered(interaction.followup.messages[0])
        assert "nicht gesetzt werden" in text

    async def test_defers_before_working(self):
        """Rollen anlegen dauert — ohne defer laeuft die Interaktion ab."""

        select = select_of(SelfRoleView(), [])

        interaction = FakeInteraction(FakeGuild(), FakeMember())
        await select.callback(interaction)

        assert interaction.response.deferred

    def test_every_option_is_selectable(self):
        """max_values muss zur Anzahl der Optionen passen."""

        select = select_of(SelfRoleView())
        assert select.max_values == len(SELF_ROLES)
        assert select.min_values == 0, "Abwaehlen muss moeglich bleiben"


# --------------------------------------------------------------------------- #
# Ticket
# --------------------------------------------------------------------------- #

class TestTicketButton:
    async def test_rejects_non_text_channels(self):
        interaction = FakeInteraction(FakeGuild(), FakeMember(), channel=object())
        await button_of(TicketView()).callback(interaction)

        assert "Nicht möglich" in rendered(interaction.replies[0])


# --------------------------------------------------------------------------- #
# Aufbau
# --------------------------------------------------------------------------- #

class TestWidgetStructure:
    @pytest.mark.parametrize(
        "factory", [VerifyView, RulesView, SelfRoleView, TicketView, ChecklistView]
    )
    def test_survives_a_restart(self, factory):
        """Persistente Views brauchen timeout=None und feste custom_ids."""

        view = factory()
        assert view.timeout is None, f"{factory.__name__} laeuft ab"

        for child in view.walk_children():
            custom_id = getattr(child, "custom_id", None)
            if custom_id is None:
                continue
            assert custom_id.startswith("architect:"), (
                f"{factory.__name__}: '{custom_id}' ohne Namensraum — "
                "kollidiert mit anderen Bots"
            )

    @pytest.mark.parametrize(
        "factory", [VerifyView, RulesView, SelfRoleView, TicketView]
    )
    def test_custom_titles_and_lines_are_used(self, factory):
        view = factory("Eigene Überschrift", ["Eigener Text"])
        text = rendered(view)
        assert "Eigene Überschrift" in text
        assert "Eigener Text" in text

    def test_checklist_keeps_its_own_items(self):
        """Die Checkliste ist inhaltlich fest — nur die Ueberschrift ist frei.

        Ihre Punkte stehen in ``core.content.CHECKLIST_ITEMS``, damit auf
        jedem Server dieselben Aufgaben erscheinen.
        """

        from core.content import CHECKLIST_ITEMS

        text = rendered(ChecklistView("Eigene Überschrift", ["wird ignoriert"]))
        assert "Eigene Überschrift" in text
        assert "wird ignoriert" not in text
        for item in CHECKLIST_ITEMS:
            assert item in text, f"Checklisten-Punkt fehlt: {item}"
