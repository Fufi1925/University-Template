"""Die Verwaltungsoberflaeche: Liste, Loesch-Dialog und AI-Formular.

Hier zaehlt der Bildschirm, nicht die Engine — gebaut und geloescht wird
in ``test_build_simulation`` und ``test_template_removal``. Geprueft wird:

* **Liste** — alle Vorlagen stehen drauf, und die Auswahl fuehrt zur
  Detailansicht (Premium-Vorlagen nur mit Freischaltung).
* **Loeschen** — beide Wege (Vorlage / Wipe) fuehren durch eine
  Bestaetigung, ohne Berechtigung geht gar nichts, und waehrend eines
  laufenden Baus bleibt die Loeschung aussen vor.
* **AI-Formular** — gueltige Beschreibungen werden zur Vorlage, eine
  ungueltige Kombination wird erklaert statt verschluckt.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, cast

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import discord

import config
from core.builder import RemovalReport
from core.registry import TemplateRegistry
from core.schema import TemplateError
from ui.management import (
    AiTemplateModal,
    DeleteConfirmView,
    DeletePickerView,
    TemplateListView,
)

# --------------------------------------------------------------------------- #
# Attrappen
# --------------------------------------------------------------------------- #

class FakeResponse:
    def __init__(self) -> None:
        self.sent: list[object] = []
        self.edited: list[object] = []
        self.modals: list[object] = []

    def is_done(self) -> bool:
        return bool(self.sent or self.edited or self.modals)

    async def send_message(self, *, view=None, **kwargs) -> None:
        self.sent.append(view)

    async def edit_message(self, *, view=None, **kwargs) -> None:
        self.edited.append(view)

    async def send_modal(self, modal) -> None:
        self.modals.append(modal)

    async def defer(self, *, ephemeral: bool = False, thinking: bool = False) -> None:
        return None


class FakeUser:
    def __init__(self, *, manage_guild: bool = True) -> None:
        self.id = 7
        self.display_name = "Testerin"
        self.guild_permissions = type("P", (), {"manage_guild": manage_guild})()


_DEFAULT = object()


class FakeInteraction:
    def __init__(self, guild=_DEFAULT, user=None) -> None:
        self.guild = FakeGuild() if guild is _DEFAULT else guild
        self.user = user if user is not None else FakeUser()
        self.response = FakeResponse()
        self.followup = type("F", (), {"sent": []})()
        self.originals: list[object] = []

    async def edit_original_response(self, *, view=None, **kwargs) -> None:
        self.originals.append(view)


class FakeGuild:
    def __init__(self, *, bot_can_manage: bool = True) -> None:
        self.id = 4242
        self.name = "Testserver"
        permissions = type(
            "P",
            (),
            {
                "manage_channels": bot_can_manage,
                "manage_roles": bot_can_manage,
                "manage_guild": bot_can_manage,
            },
        )()
        self.me = type("M", (), {"guild_permissions": permissions})()
        self.categories: list = []
        self.channels: list = []


class FakeBot:
    def __init__(self, registry: TemplateRegistry) -> None:
        self.registry = registry
        self.active_builds: set[int] = set()
        self._premium = False

    async def has_premium(self, interaction) -> bool:
        return self._premium


@pytest.fixture(scope="module")
def registry():
    return TemplateRegistry(config.TEMPLATE_DIR).load()


@pytest.fixture
def bot(registry) -> FakeBot:
    return FakeBot(registry)


@pytest.fixture(autouse=True)
def members_pass_isinstance(monkeypatch):
    """FakeUser darf als discord.Member durchgehen (siehe test_views_flow)."""

    import ui.management as management

    real_isinstance = isinstance

    def lenient(obj, classinfo):
        if classinfo is discord.Member and type(obj) is FakeUser:
            return True
        return real_isinstance(obj, classinfo)

    monkeypatch.setitem(management.__dict__, "isinstance", lenient)


def select_value(select, interaction, value: str) -> None:
    """Die Auswahl so setzen, wie Discord sie an den Select schickt."""

    select._refresh_state(cast("Any", interaction), {"values": [value]})


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


# --------------------------------------------------------------------------- #
# /template list
# --------------------------------------------------------------------------- #

class TestTemplateListView:
    def test_every_template_is_listed(self, bot):
        view = TemplateListView(bot)
        text = rendered(view)

        for template in bot.registry:
            assert template.name in text, f"{template.name} fehlt in der Liste"

        assert str(len(bot.registry)) in text

    def test_it_serializes_within_discords_limits(self, bot):
        view = TemplateListView(bot)
        payload = view.to_components()

        assert len(payload) <= 40, "Zu viele Komponenten"
        assert len(rendered(view)) <= 4000, "Zu viel Text"

    async def test_selecting_a_free_template_opens_details(self, bot):
        from ui.management import _ListSelect
        from ui.views import DetailView

        select = _ListSelect(bot, bot.registry.all)
        interaction = FakeInteraction()
        select_value(select, interaction, "community")

        await select.callback(cast("Any", interaction))

        assert isinstance(interaction.response.sent[0], DetailView)

    async def test_premium_needs_an_unlock(self, bot):
        from ui.management import _ListSelect

        select = _ListSelect(bot, bot.registry.all)
        interaction = FakeInteraction()
        select_value(select, interaction, "anime")

        await select.callback(cast("Any", interaction))

        assert "Premium erforderlich" in rendered(interaction.response.sent[0])

    async def test_premium_unlocked_opens_details(self, bot):
        from ui.management import _ListSelect
        from ui.views import DetailView

        bot._premium = True
        select = _ListSelect(bot, bot.registry.all)
        interaction = FakeInteraction()
        select_value(select, interaction, "anime")

        await select.callback(cast("Any", interaction))

        assert isinstance(interaction.response.sent[0], DetailView)

    async def test_a_vanished_template_is_explained(self, bot):
        from ui.management import _ListSelect

        select = _ListSelect(bot, bot.registry.all)
        interaction = FakeInteraction()
        select_value(select, interaction, "gibt-es-nicht")

        await select.callback(cast("Any", interaction))

        assert "Vorlage nicht gefunden" in rendered(interaction.response.sent[0])


# --------------------------------------------------------------------------- #
# /template löschen — der Dialog
# --------------------------------------------------------------------------- #

class TestDeleteDialog:
    def test_the_picker_offers_both_ways(self, bot):
        view = DeletePickerView(bot)
        text = rendered(view)

        assert "Vorlage rückgängig" in text
        assert "Alles löschen" in text

    async def test_choosing_a_template_asks_for_confirmation(self, bot):
        from ui.management import _DeleteSelect

        select = _DeleteSelect(bot)
        interaction = FakeInteraction()
        select_value(select, interaction, "community")

        await select.callback(cast("Any", interaction))

        view = interaction.response.edited[0]
        assert isinstance(view, DeleteConfirmView)
        assert view.template is bot.registry.get("community")

    async def test_the_wipe_button_asks_for_confirmation(self, bot):
        from ui.management import _WipeButton

        picker = DeletePickerView(bot)
        button = _WipeButton()
        button._view = picker  # wie discord.py beim Ausliefern der Interaktion

        interaction = FakeInteraction()
        await button.callback(cast("Any", interaction))

        view = interaction.response.edited[0]
        assert isinstance(view, DeleteConfirmView)
        assert view.template is None

    async def test_a_vanished_template_is_explained(self, bot):
        from ui.management import _DeleteSelect

        select = _DeleteSelect(bot)
        interaction = FakeInteraction()
        select_value(select, interaction, "gibt-es-nicht")

        await select.callback(cast("Any", interaction))

        assert "Vorlage nicht gefunden" in rendered(interaction.response.sent[0])

    async def test_buttons_survive_a_missing_view(self, bot):
        """Defensiv: ohne View (z. B. Stale-Klick) passiert einfach nichts."""

        from ui.management import _ConfirmDeleteButton, _WipeButton

        interaction = FakeInteraction()
        await _WipeButton().callback(cast("Any", interaction))
        await _ConfirmDeleteButton(bot.registry.get("community")).callback(
            cast("Any", interaction)
        )

        assert not interaction.response.edited
        assert not interaction.response.sent

    async def test_confirming_really_deletes(self, bot, monkeypatch):
        """Der Klick auf 'Löschen' fuehrt in die Ausfuehrung."""

        import ui.management as management
        from ui.management import _ConfirmDeleteButton

        class FakeBuilder:
            def __init__(self, guild, template):
                self.template = template

            async def unapply(self):
                return RemovalReport(
                    template_key="community", deleted_channels=1, deleted_categories=1
                )

        monkeypatch.setattr(management, "ServerBuilder", FakeBuilder)

        view = DeleteConfirmView(bot, bot.registry.get("community"))
        button = _ConfirmDeleteButton(view.template)
        button._view = view

        interaction = FakeInteraction()
        await button.callback(cast("Any", interaction))

        assert "entfernt" in rendered(interaction.originals[0])
        assert bot.active_builds == set()

    def test_the_result_view_shows_warnings(self):
        from ui.management import _deletion_view

        report = RemovalReport(deleted_channels=3, warnings=["Zwei Rollen blieben stehen."])

        text = rendered(_deletion_view(report, None))

        assert "Hinweise" in text
        assert "Zwei Rollen blieben stehen." in text

    async def test_cancel_does_nothing(self, bot):
        from ui.management import _CancelButton

        button = _CancelButton()

        interaction = FakeInteraction()
        await button.callback(cast("Any", interaction))

        assert "Abgebrochen" in rendered(interaction.response.edited[0])

    def test_the_confirmation_names_the_template(self, bot):
        template = bot.registry.get("community")
        view = DeleteConfirmView(bot, template)
        text = rendered(view)

        assert template.name in text
        assert "Basis-Rollen" in text, "Der Hinweis auf die bleibende Leiter fehlt"

    def test_the_wipe_confirmation_warns(self, bot):
        view = DeleteConfirmView(bot, None)
        text = rendered(view)

        assert "nicht rückgängig" in text


# --------------------------------------------------------------------------- #
# /template löschen — die Ausführung
# --------------------------------------------------------------------------- #

class TestRunDeletion:
    async def test_a_missing_guild_stops_immediately(self, bot):
        import ui.management as management

        interaction = FakeInteraction(guild=None)
        await management._run_deletion(cast("Any", interaction), cast("Any", bot), None)

        assert not interaction.response.sent

    async def test_removes_the_chosen_template(self, bot, monkeypatch):
        import ui.management as management

        report = RemovalReport(
            template_key="community",
            deleted_channels=90,
            deleted_categories=15,
            deleted_roles=3,
        )

        class FakeBuilder:
            def __init__(self, guild, template):
                self.template = template

            async def unapply(self):
                assert self.template is bot.registry.get("community")
                return report

        monkeypatch.setattr(management, "ServerBuilder", FakeBuilder)

        interaction = FakeInteraction(FakeGuild())
        await management._run_deletion(
            cast("Any", interaction), cast("Any", bot), bot.registry.get("community")
        )

        view = interaction.originals[0]
        text = rendered(view)
        assert "entfernt" in text
        assert "90" in text and "15" in text and "3" in text
        assert bot.active_builds == set(), "Die Bausperre wurde nicht freigegeben"

    async def test_wipes_everything_when_no_template_is_given(self, bot, monkeypatch):
        import ui.management as management

        report = RemovalReport(deleted_channels=120, deleted_roles=14)

        async def fake_wipe(guild):
            return report

        monkeypatch.setattr(management, "wipe_guild", fake_wipe)

        interaction = FakeInteraction(FakeGuild())
        await management._run_deletion(cast("Any", interaction), cast("Any", bot), None)

        assert "Alles gelöscht" in rendered(interaction.originals[0])
        assert bot.active_builds == set()

    async def test_without_manage_guild_nothing_happens(self, bot):
        import ui.management as management

        interaction = FakeInteraction(FakeGuild(), user=FakeUser(manage_guild=False))
        await management._run_deletion(
            cast("Any", interaction), cast("Any", bot), bot.registry.get("community")
        )

        assert "Keine Berechtigung" in rendered(interaction.response.sent[0])

    async def test_a_running_build_blocks_the_deletion(self, bot):
        import ui.management as management

        guild = FakeGuild()
        bot.active_builds.add(guild.id)

        interaction = FakeInteraction(guild)
        await management._run_deletion(
            cast("Any", interaction), cast("Any", bot), bot.registry.get("community")
        )

        assert "läuft bereits" in rendered(interaction.response.sent[0])

    async def test_missing_bot_permissions_are_explained(self, bot):
        import ui.management as management

        interaction = FakeInteraction(FakeGuild(bot_can_manage=False))
        await management._run_deletion(
            cast("Any", interaction), cast("Any", bot), bot.registry.get("community")
        )

        assert "Einrichtung nicht möglich" in rendered(interaction.response.sent[0])

    async def test_the_lock_is_released_after_a_failure(self, bot, monkeypatch):
        import ui.management as management

        class BrokenBuilder:
            def __init__(self, guild, template):
                self.template = template

            async def unapply(self):
                response = type("R", (), {"status": 400, "reason": "Bad Request", "text": "kaputt"})()
                raise discord.HTTPException(response, "kaputt")

        monkeypatch.setattr(management, "ServerBuilder", BrokenBuilder)

        guild = FakeGuild()
        interaction = FakeInteraction(guild)
        await management._run_deletion(
            cast("Any", interaction), cast("Any", bot), bot.registry.get("community")
        )

        assert bot.active_builds == set(), "Die Sperre blieb haengen"
        assert "Discord meldet einen Fehler" in rendered(interaction.originals[0])

    async def test_a_build_error_is_explained(self, bot, monkeypatch):
        import ui.management as management
        from core.builder import BuildError

        class ErrorBuilder:
            def __init__(self, guild, template):
                self.template = template

            async def unapply(self):
                raise BuildError("Keine Rechte")

        monkeypatch.setattr(management, "ServerBuilder", ErrorBuilder)

        interaction = FakeInteraction(FakeGuild())
        await management._run_deletion(
            cast("Any", interaction), cast("Any", bot), bot.registry.get("community")
        )

        assert "Löschen abgebrochen" in rendered(interaction.originals[0])
        assert bot.active_builds == set()

    async def test_a_forbidden_is_explained(self, bot, monkeypatch):
        import ui.management as management

        class ForbidBuilder:
            def __init__(self, guild, template):
                self.template = template

            async def unapply(self):
                response = type("R", (), {"status": 403, "reason": "Forbidden", "text": "nein"})()
                raise discord.Forbidden(response, "nein")

        monkeypatch.setattr(management, "ServerBuilder", ForbidBuilder)

        interaction = FakeInteraction(FakeGuild())
        await management._run_deletion(
            cast("Any", interaction), cast("Any", bot), bot.registry.get("community")
        )

        assert "abgelehnt" in rendered(interaction.originals[0])
        assert bot.active_builds == set()

    async def test_a_dead_interaction_falls_back_to_the_channel(self, bot, monkeypatch):
        """Ist die Interaktion abgelaufen, geht das Ergebnis in den Kanal."""

        import ui.management as management

        class FakeChannel:
            def __init__(self) -> None:
                self.sent: list = []

            async def send(self, *, view=None, **kwargs) -> None:
                self.sent.append(view)

            def permissions_for(self, member):
                return type("P", (), {"send_messages": True})()

        class DeadInteraction(FakeInteraction):
            def __init__(self, guild, channel) -> None:
                super().__init__(guild)
                self.channel = channel

            async def edit_original_response(self, *, view=None, **kwargs) -> None:
                response = type("R", (), {"status": 404, "reason": "Not Found", "text": ""})()
                raise discord.NotFound(response, "weg")

        class FakeBuilder:
            def __init__(self, guild, template):
                self.template = template

            async def unapply(self):
                return RemovalReport(deleted_channels=1)

        monkeypatch.setattr(management, "ServerBuilder", FakeBuilder)

        channel = FakeChannel()
        interaction = DeadInteraction(FakeGuild(), channel)
        await management._run_deletion(
            cast("Any", interaction), cast("Any", bot), bot.registry.get("community")
        )

        assert channel.sent, "Das Ergebnis kam nicht als normale Nachricht an"
        assert bot.active_builds == set()


# --------------------------------------------------------------------------- #
# /template ai — das Formular
# --------------------------------------------------------------------------- #

class TestAiModal:
    async def test_a_description_becomes_a_template(self, bot, monkeypatch):
        import core.ai_templates as ai_module

        template = bot.registry.get("gaming")
        monkeypatch.setattr(
            ai_module,
            "compose_template",
            lambda registry, *, name, description: template,
        )

        modal = AiTemplateModal(cast("Any", bot))
        modal.name.component._value = "Zockerbude"
        modal.description.component._value = "Ein Server zum Zocken"

        interaction = FakeInteraction()
        await modal.on_submit(cast("Any", interaction))

        from ui.views import DetailView

        assert isinstance(interaction.response.sent[0], DetailView)

    async def test_an_impossible_combination_is_explained(self, bot, monkeypatch):
        import core.ai_templates as ai_module

        def broken(registry, *, name, description):
            raise TemplateError("Die Kombination sprengt die Limits.")

        monkeypatch.setattr(ai_module, "compose_template", broken)

        modal = AiTemplateModal(cast("Any", bot))
        modal.name.component._value = "Zu viel"
        modal.description.component._value = "Alles auf einmal und noch mehr"

        interaction = FakeInteraction()
        await modal.on_submit(cast("Any", interaction))

        assert "Daraus wird keine Vorlage" in rendered(interaction.response.sent[0])
