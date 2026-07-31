"""Der Weg durch die Oberfläche: Menü, Vorschau, Bestätigung, Bericht.

``test_build_guards.py`` prüft, wer bauen darf. Hier geht es um das, was der
Nutzer dabei sieht — und darum, dass die Anzeige die Wirklichkeit trifft:

* Der Bestätigungsdialog muss sagen, was gleich passiert. „Neu aufsetzen"
  löscht einen Server; steht daneben der falsche Hinweistext, klickt jemand
  aus Versehen.
* Der Abschlussbericht ist die einzige Stelle, an der Teilausfälle sichtbar
  werden. Verschluckt er Warnungen, sieht ein halb gebauter Server aus wie
  ein fertiger.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, cast

import discord
import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import config
from core.builder import BuildMode, BuildReport
from core.registry import TemplateRegistry


@pytest.fixture(scope="module")
def registry() -> TemplateRegistry:
    return TemplateRegistry(config.TEMPLATE_DIR).load()


@pytest.fixture(scope="module")
def template(registry):
    return registry.free[0]


# --------------------------------------------------------------------------- #
# Attrappen
# --------------------------------------------------------------------------- #

class FakeUser:
    def __init__(self, *, manage_guild: bool = True) -> None:
        self.id = 7
        self.display_name = "Testerin"
        self.guild_permissions = type("P", (), {"manage_guild": manage_guild})()


class FakeGuild:
    def __init__(self) -> None:
        self.id = 123
        self.name = "Testserver"
        self.me = None
        self.text_channels: list[Any] = []


class FakeResponse:
    def __init__(self) -> None:
        self.sent: list[object] = []
        self.edited: list[object] = []
        self.deferred = False

    def is_done(self) -> bool:
        return bool(self.sent or self.edited or self.deferred)

    async def send_message(self, *, view=None, ephemeral: bool = False, **kw) -> None:
        self.sent.append(view)

    async def edit_message(self, *, view=None, **kw) -> None:
        self.edited.append(view)

    async def defer(self, *, ephemeral: bool = False, thinking: bool = False) -> None:
        self.deferred = True


class FakeFollowup:
    def __init__(self) -> None:
        self.sent: list[object] = []

    async def send(self, *, view=None, ephemeral: bool = False, **kw) -> None:
        self.sent.append(view)


_DEFAULT = object()


class FakeInteraction:
    def __init__(self, guild=_DEFAULT, user=None) -> None:
        self.guild = FakeGuild() if guild is _DEFAULT else guild
        self.user = user if user is not None else FakeUser()
        self.channel = None
        self.response = FakeResponse()
        self.followup = FakeFollowup()
        self.originals: list[object] = []

    async def edit_original_response(self, *, view=None, **kw) -> None:
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
    def __init__(self, registry: TemplateRegistry) -> None:
        self.registry = registry
        self.active_builds: set[int] = set()
        self.premium = type("P", (), {"has_access": lambda *a: True})()


@pytest.fixture(autouse=True)
def members_pass_isinstance(monkeypatch):
    import ui.views as views

    real_isinstance = isinstance

    def lenient(obj, classinfo):
        if classinfo is discord.Member and type(obj) is FakeUser:
            return True
        return real_isinstance(obj, classinfo)

    monkeypatch.setitem(views.__dict__, "isinstance", lenient)
    yield


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
    return "\n".join(rendered(v) for v in interaction.shown if v is not None)


def button_labelled(view, needle: str):
    for child in view.walk_children():
        label = getattr(child, "label", None)
        if label and needle.lower() in label.lower():
            return child
    raise AssertionError(f"Kein Button mit '{needle}'")


def report_with(**kwargs) -> BuildReport:
    report = BuildReport(mode=BuildMode.EXTEND, template_key="test")
    for key, value in kwargs.items():
        if key == "warnings":
            for warning in value:
                report.warn(warning)
        else:
            setattr(report, key, value)
    return report


# --------------------------------------------------------------------------- #
# Bestätigung
# --------------------------------------------------------------------------- #

class TestConfirmView:
    def _confirm(self, registry, template, **kwargs):
        from ui.views import ConfirmView

        return ConfirmView(cast("Any", FakeBot(registry)), template, **kwargs)

    def test_offers_both_modes_and_a_way_out(self, registry, template):
        view = self._confirm(registry, template)

        button_labelled(view, "Ergänzen")
        button_labelled(view, "Neu aufsetzen")
        button_labelled(view, "Abbrechen")

    def test_only_the_destructive_mode_is_red(self, registry, template):
        """Rot muss eine Warnung bleiben, sonst nutzt es sich ab."""

        view = self._confirm(registry, template)

        assert button_labelled(view, "Ergänzen").style is discord.ButtonStyle.primary
        assert (
            button_labelled(view, "Neu aufsetzen").style is discord.ButtonStyle.danger
        )

    def test_intro_hint_matches_the_setting(self, registry, template):
        """Der Text muss sagen, was der Schalter gerade bewirkt."""

        on = rendered(self._confirm(registry, template, write_intros=True))
        off = rendered(self._confirm(registry, template, write_intros=False))

        assert "angeheftete Startnachricht" in on
        assert "bleiben leer" in off

    def test_toggle_label_reflects_the_state(self, registry, template):
        on = self._confirm(registry, template, write_intros=True)
        off = self._confirm(registry, template, write_intros=False)

        assert "an" in button_labelled(on, "Startnachrichten").label
        assert "aus" in button_labelled(off, "Startnachrichten").label

    async def test_toggling_flips_the_setting(self, registry, template):
        view = self._confirm(registry, template, write_intros=True)
        interaction = FakeInteraction()

        await button_labelled(view, "Startnachrichten").callback(
            cast("Any", interaction)
        )

        assert interaction.response.edited
        assert "bleiben leer" in rendered(interaction.response.edited[0])

    async def test_cancel_changes_nothing(self, registry, template):
        view = self._confirm(registry, template)
        interaction = FakeInteraction()

        await button_labelled(view, "Abbrechen").callback(cast("Any", interaction))

        assert "nichts verändert" in all_text(interaction)

    def test_the_template_name_is_visible(self, registry, template):
        """Damit niemand die falsche Vorlage bestaetigt."""

        assert template.name in rendered(self._confirm(registry, template))


# --------------------------------------------------------------------------- #
# Bericht
# --------------------------------------------------------------------------- #

class TestReportView:
    def _report_view(self, registry, template, report):
        from ui.views import _report_view

        return _report_view(template, report, cast("Any", FakeBot(registry)), None)

    def test_counts_appear_in_the_summary(self, registry, template):
        report = report_with(
            channels_created=42, roles_created=7, categories_created=5
        )

        text = self._report_view(registry, template, report)

        assert "42" in rendered(text)
        assert "7" in rendered(text)

    def test_warnings_are_shown(self, registry, template):
        """Sonst sieht ein halb gebauter Server aus wie ein fertiger."""

        report = report_with(
            channels_created=10,
            warnings=["Rolle 'Admin' konnte nicht erstellt werden."],
        )

        text = rendered(self._report_view(registry, template, report))

        assert "Hinweise" in text
        assert "Admin" in text

    def test_a_clean_run_shows_no_warning_block(self, registry, template):
        report = report_with(channels_created=10)

        text = rendered(self._report_view(registry, template, report))

        assert "Hinweise" not in text

    def test_partner_summary_also_reports_warnings(self, registry, template):
        """Die Partner-Zusammenfassung ist eine zweite, eigene Ansicht."""

        from ui.views import partner_summary_view

        report = report_with(
            channels_created=10, warnings=["Rolle 'Admin' fehlt."]
        )

        text = rendered(partner_summary_view(template, report))

        assert "Nicht vollständig übernommen" in text
        assert "Admin" in text

    def test_partner_summary_stays_quiet_without_warnings(self, registry, template):
        from ui.views import partner_summary_view

        text = rendered(partner_summary_view(template, report_with(channels_created=10)))

        assert "Nicht vollständig" not in text

    def test_many_warnings_are_capped(self, registry, template):
        """Zwanzig Zeilen Fehlermeldung liest niemand — und Discord bricht ab."""

        report = report_with(
            channels_created=10,
            warnings=[f"Problem Nummer {i}" for i in range(12)],
        )

        text = rendered(self._report_view(registry, template, report))

        assert "Problem Nummer 0" in text
        assert "Problem Nummer 11" not in text

    def test_written_messages_are_mentioned(self, registry, template):
        report = report_with(channels_created=10, messages_posted=8)

        text = rendered(self._report_view(registry, template, report))

        assert "8" in text

    def test_report_fits_discord_limits(self, registry, template):
        """Ein Bericht, den Discord ablehnt, ist kein Bericht."""

        report = report_with(
            channels_created=99,
            roles_created=18,
            categories_created=15,
            messages_posted=90,
            warnings=[f"Sehr ausführliche Warnung Nummer {i}" for i in range(10)],
        )

        text = rendered(self._report_view(registry, template, report))

        assert len(text) < 4000, "Der Bericht sprengt das Zeichenlimit"


# --------------------------------------------------------------------------- #
# Vorschau
# --------------------------------------------------------------------------- #

class TestPreview:
    async def test_preview_lists_the_channels(self, registry, template):
        from ui.views import DetailView

        view = DetailView(cast("Any", FakeBot(registry)), template)
        interaction = FakeInteraction()

        await button_labelled(view, "Struktur ansehen").callback(cast("Any", interaction))

        text = all_text(interaction)
        first_category = template.categories[0]
        assert first_category.display_name in text

    async def test_large_templates_are_split(self, registry):
        """Ein Kanalbaum mit 100 Eintraegen passt nicht in eine Nachricht."""

        from ui.views import DetailView

        biggest = max(registry.all, key=lambda t: t.channel_count)
        view = DetailView(cast("Any", FakeBot(registry)), biggest)
        interaction = FakeInteraction()

        await button_labelled(view, "Struktur ansehen").callback(cast("Any", interaction))

        assert interaction.response.sent, "Die erste Seite fehlt"
        for shown in interaction.shown:
            assert len(rendered(shown)) < 4000

    async def test_apply_requires_permission(self, registry, template):
        from ui.views import DetailView

        view = DetailView(cast("Any", FakeBot(registry)), template)
        interaction = FakeInteraction(user=FakeUser(manage_guild=False))

        await button_labelled(view, "Anwenden").callback(cast("Any", interaction))

        assert "Keine Berechtigung" in all_text(interaction)

    async def test_apply_opens_the_confirmation(self, registry, template):
        from ui.views import DetailView

        view = DetailView(cast("Any", FakeBot(registry)), template)
        interaction = FakeInteraction()

        await button_labelled(view, "Anwenden").callback(cast("Any", interaction))

        assert interaction.response.edited
        assert "Neu aufsetzen" in rendered(interaction.response.edited[0])


# --------------------------------------------------------------------------- #
# Erfolgreicher Bau
# --------------------------------------------------------------------------- #

class TestSuccessfulBuild:
    async def test_progress_and_report_reach_the_user(
        self, registry, template, monkeypatch
    ):
        """Der komplette Ablauf mit einem Builder, der einfach durchlaeuft."""

        import ui.views as views

        async def fake_apply(self, mode, progress=None, write_intros=True):
            if progress is not None:
                await progress("Rollen", 1, 2)
                await progress("Fertig", 2, 2)
            return report_with(channels_created=12, roles_created=3)

        monkeypatch.setattr(views.ServerBuilder, "preflight", lambda self: None)
        monkeypatch.setattr(views.ServerBuilder, "apply", fake_apply)

        interaction = FakeInteraction()
        bot = FakeBot(registry)

        await views._run_build(
            cast("Any", interaction), cast("Any", bot), template, BuildMode.EXTEND
        )

        text = all_text(interaction)
        assert "12" in text, "Die Zahl der Kanaele fehlt im Bericht"
        assert not bot.active_builds, "Die Sperre wurde nicht freigegeben"

    async def test_progress_updates_are_throttled(
        self, registry, template, monkeypatch
    ):
        """Discord begrenzt Nachrichtenbearbeitungen pro Kanal."""

        import ui.views as views

        async def many_steps(self, mode, progress=None, write_intros=True):
            for step in range(1, 21):
                await progress(f"Schritt {step}", step, 20)
            return report_with(channels_created=1)

        monkeypatch.setattr(views.ServerBuilder, "preflight", lambda self: None)
        monkeypatch.setattr(views.ServerBuilder, "apply", many_steps)

        interaction = FakeInteraction()

        await views._run_build(
            cast("Any", interaction),
            cast("Any", FakeBot(registry)),
            template,
            BuildMode.EXTEND,
        )

        # 20 Schritte, aber deutlich weniger Bearbeitungen.
        assert len(interaction.originals) < 20, "Jeder Schritt wurde einzeln gesendet"


# --------------------------------------------------------------------------- #
# Weiterleitung zum Regelwerk
# --------------------------------------------------------------------------- #

class FakeRulesChannel:
    def __init__(self, name: str = "regeln") -> None:
        self.name = name
        self.mention = f"#{name}"


class TestNextStepToRules:
    """Nach dem Bau steht der Regelkanal — leer.

    Der Bericht bietet deshalb direkt den Regelwerk-Assistenten an. Das ist
    der einzige Ort, an dem die beiden Teile des Bots verbunden sind.
    """

    def _view(self, registry, template, guild):
        from ui.views import _report_view

        return _report_view(
            template,
            report_with(channels_created=10),
            cast("Any", FakeBot(registry)),
            cast("Any", guild),
        )

    def test_offers_the_assistant_when_a_rules_channel_exists(
        self, registry, template, monkeypatch
    ):
        import ui.rules as rules_module

        channel = FakeRulesChannel()
        monkeypatch.setattr(rules_module, "find_rules_channel", lambda guild: channel)

        view = self._view(registry, template, FakeGuild())
        text = rendered(view)

        assert "Nächster Schritt" in text
        assert "#regeln" in text
        button_labelled(view, "Regelwerk")

    def test_stays_silent_without_a_rules_channel(
        self, registry, template, monkeypatch
    ):
        import ui.rules as rules_module

        monkeypatch.setattr(rules_module, "find_rules_channel", lambda guild: None)

        text = rendered(self._view(registry, template, FakeGuild()))

        assert "Nächster Schritt" not in text

    def test_no_guild_means_no_offer(self, registry, template):
        from ui.views import _report_view

        text = rendered(
            _report_view(
                template,
                report_with(channels_created=10),
                cast("Any", FakeBot(registry)),
                None,
            )
        )

        assert "Nächster Schritt" not in text

    async def test_the_button_opens_the_picker(
        self, registry, template, monkeypatch
    ):
        import ui.rules as rules_module

        channel = FakeRulesChannel()
        monkeypatch.setattr(rules_module, "find_rules_channel", lambda guild: channel)

        view = self._view(registry, template, FakeGuild())
        interaction = FakeInteraction()

        await button_labelled(view, "Regelwerk").callback(cast("Any", interaction))

        assert interaction.response.sent, "Der Assistent ging nicht auf"
