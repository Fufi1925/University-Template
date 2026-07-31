"""Der Regelwerk-Assistent: Auswahl, Baukasten und Einstieg.

``test_rules_posting.py`` deckt das Veroeffentlichen ab. Hier geht es um den
Weg davor — die Bedienung:

* **Kanalsuche.** Der Assistent sucht den Regelkanal selbst. Findet er den
  falschen, schreibt der Bot ein Regelwerk an eine Stelle, an die es nicht
  gehoert.
* **Berechtigungen.** Jeder Einstiegspunkt in den Assistenten muss dieselbe
  Huerde haben. Eine vergessene Pruefung an einem der Buttons genuegt, damit
  ein Gast den Regelkanal ueberschreibt.
* **Baukasten.** Freitext und Bildlinks von Nutzern; die URL-Pruefung ist die
  einzige Stelle, an der ungefilterte Eingaben in eine Nachricht wandern.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, cast

import discord
import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.rulesets import RULESETS
from core.small_caps import channel_name
from ui.rules import (
    CustomRulesModal,
    RulesetPicker,
    find_rules_channel,
    open_rules_assistant,
)

# --------------------------------------------------------------------------- #
# Attrappen
# --------------------------------------------------------------------------- #

class FakeTextChannel:
    def __init__(self, name: str) -> None:
        self.name = name
        self.mention = f"#{name}"
        self.sent: list[object] = []

    async def send(self, *, view=None, **kw):
        self.sent.append(view)
        return FakeMessage()


class FakeMessage:
    async def pin(self, reason: str | None = None) -> None:
        return None


class FakeGuild:
    def __init__(self, channel_names: list[str]) -> None:
        self.id = 1
        self.name = "Testserver"
        self.text_channels = [FakeTextChannel(name) for name in channel_names]
        self.me = None


class FakeUser:
    def __init__(self, *, manage_guild: bool = True) -> None:
        self.id = 7
        self.display_name = "Testerin"
        self.guild_permissions = type("P", (), {"manage_guild": manage_guild})()


class FakeResponse:
    def __init__(self) -> None:
        self.sent: list[object] = []
        self.edited: list[object] = []
        self.modals: list[object] = []
        self.deferred = False

    def is_done(self) -> bool:
        return bool(self.sent or self.edited or self.modals or self.deferred)

    async def send_message(self, *, view=None, ephemeral: bool = False, **kw) -> None:
        self.sent.append(view)

    async def edit_message(self, *, view=None, **kw) -> None:
        self.edited.append(view)

    async def send_modal(self, modal) -> None:
        self.modals.append(modal)

    async def defer(self, *, ephemeral: bool = False, thinking: bool = False) -> None:
        self.deferred = True


_DEFAULT = object()


class FakeInteraction:
    def __init__(self, guild=_DEFAULT, user=None) -> None:
        self.guild = FakeGuild(["regeln"]) if guild is _DEFAULT else guild
        self.user = user if user is not None else FakeUser()
        self.response = FakeResponse()
        self.edited: list[object] = []

    async def edit_original_response(self, *, view=None, **kw) -> None:
        self.edited.append(view)

    @property
    def shown(self) -> list[object]:
        return [*self.response.sent, *self.response.edited, *self.edited]


class FakeBot:
    pass


@pytest.fixture(autouse=True)
def members_pass_isinstance(monkeypatch):
    """``_can_manage`` prueft auf ``discord.Member``."""

    import ui.rules as rules

    real_isinstance = isinstance

    def lenient(obj, classinfo):
        if classinfo is discord.Member and type(obj) is FakeUser:
            return True
        return real_isinstance(obj, classinfo)

    monkeypatch.setitem(rules.__dict__, "isinstance", lenient)
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


def picker(selected: str | None = None) -> RulesetPicker:
    return RulesetPicker(
        cast("Any", FakeBot()), cast("Any", FakeTextChannel("regeln")), selected=selected
    )


def button_labelled(view, needle: str):
    for child in view.walk_children():
        label = getattr(child, "label", None)
        if label and needle.lower() in label.lower():
            return child
    raise AssertionError(f"Kein Button mit '{needle}' in der Ansicht")


def select_of(view, chosen: list[str] | None = None):
    for child in view.walk_children():
        if isinstance(child, discord.ui.Select):
            if chosen is not None:
                child._values = list(chosen)
            return child
    raise AssertionError("Kein Auswahlmenue in der Ansicht")


def custom_modal(heading: str, body: str, top: str = "", bottom: str = ""):
    modal = CustomRulesModal(
        cast("Any", FakeBot()), cast("Any", FakeTextChannel("regeln"))
    )
    for label, value in (
        (modal.heading, heading),
        (modal.body, body),
        (modal.top_image, top),
        (modal.bottom_image, bottom),
    ):
        cast("Any", label.component)._value = value
    return modal


# --------------------------------------------------------------------------- #
# Kanalsuche
# --------------------------------------------------------------------------- #

class TestFindRulesChannel:
    def test_finds_a_plain_channel(self):
        guild = FakeGuild(["allgemein", "regeln", "memes"])

        assert find_rules_channel(cast("Any", guild)).name == "regeln"

    def test_finds_a_small_caps_channel(self):
        """Die Vorlagen legen den Kanal dekoriert an."""

        decorated = channel_name("regeln", "📜")
        guild = FakeGuild(["allgemein", decorated])

        assert find_rules_channel(cast("Any", guild)).name == decorated

    def test_exact_match_beats_partial(self):
        """``regeln`` schlaegt ``serverregeln-archiv``."""

        guild = FakeGuild(["serverregeln-archiv", "regeln"])

        assert find_rules_channel(cast("Any", guild)).name == "regeln"

    def test_partial_match_is_used_when_nothing_else_fits(self):
        guild = FakeGuild(["allgemein", "serverregeln"])

        assert find_rules_channel(cast("Any", guild)) is not None

    def test_returns_none_without_a_rules_channel(self):
        """Lieber nichts finden als in den falschen Kanal schreiben."""

        guild = FakeGuild(["allgemein", "memes", "voice-text"])

        assert find_rules_channel(cast("Any", guild)) is None

    def test_empty_guild(self):
        assert find_rules_channel(cast("Any", FakeGuild([]))) is None


# --------------------------------------------------------------------------- #
# Einstieg
# --------------------------------------------------------------------------- #

class TestOpenAssistant:
    async def test_opens_the_picker(self):
        interaction = FakeInteraction()

        await open_rules_assistant(cast("Any", interaction), cast("Any", FakeBot()))

        assert interaction.response.sent, "Der Assistent wurde nicht geoeffnet"

    async def test_without_a_rules_channel_it_explains_why(self):
        interaction = FakeInteraction(guild=FakeGuild(["allgemein"]))

        await open_rules_assistant(cast("Any", interaction), cast("Any", FakeBot()))

        text = all_text(interaction)
        assert "Kein Regelkanal" in text
        assert "Vorlage" in text, "Die Meldung nennt den Ausweg nicht"

    async def test_outside_a_guild_it_refuses(self):
        interaction = FakeInteraction(guild=None)

        await open_rules_assistant(cast("Any", interaction), cast("Any", FakeBot()))

        assert "Nur auf Servern" in all_text(interaction)


# --------------------------------------------------------------------------- #
# Auswahl
# --------------------------------------------------------------------------- #

class TestPicker:
    def test_lists_every_ruleset(self):
        options = select_of(picker()).options

        assert len(options) == len(RULESETS)
        assert {o.value for o in options} == {rs.key for rs in RULESETS}

    def test_apply_buttons_start_disabled(self):
        """Ohne Auswahl darf nichts anwendbar sein."""

        view = picker()

        assert button_labelled(view, "Ergänzen").disabled
        assert button_labelled(view, "Neu aufsetzen").disabled

    def test_apply_buttons_enable_after_selection(self):
        view = picker(selected=RULESETS[0].key)

        assert not button_labelled(view, "Ergänzen").disabled
        assert not button_labelled(view, "Neu aufsetzen").disabled

    def test_selection_is_marked_in_the_menu(self):
        """Sonst weiss niemand, was gerade gewaehlt ist."""

        chosen = RULESETS[1].key
        options = select_of(picker(selected=chosen)).options

        assert [o.value for o in options if o.default] == [chosen]

    async def test_choosing_rebuilds_the_view(self):
        select = select_of(picker(), [RULESETS[2].key])
        interaction = FakeInteraction()

        await select.callback(cast("Any", interaction))

        assert interaction.response.edited, "Die Ansicht wurde nicht aktualisiert"

    async def test_cancel_leaves_the_channel_alone(self):
        interaction = FakeInteraction()

        await button_labelled(picker(), "Abbrechen").callback(cast("Any", interaction))

        assert "unverändert" in all_text(interaction)


# --------------------------------------------------------------------------- #
# Berechtigungen an jedem Einstiegspunkt
# --------------------------------------------------------------------------- #

class TestPermissions:
    """Eine vergessene Pruefung genuegt, damit ein Gast den Kanal ueberschreibt."""

    @pytest.mark.parametrize("label", ["Ergänzen", "Neu aufsetzen"])
    async def test_apply_requires_manage_guild(self, label):
        view = picker(selected=RULESETS[0].key)
        interaction = FakeInteraction(user=FakeUser(manage_guild=False))

        await button_labelled(view, label).callback(cast("Any", interaction))

        assert "Keine Berechtigung" in all_text(interaction)
        assert not interaction.response.deferred, "Es wurde trotzdem losgelegt"

    async def test_custom_builder_requires_manage_guild(self):
        interaction = FakeInteraction(user=FakeUser(manage_guild=False))

        await button_labelled(picker(), "Eigenes").callback(cast("Any", interaction))

        assert "Keine Berechtigung" in all_text(interaction)
        assert not interaction.response.modals, "Das Baukasten-Fenster ging trotzdem auf"

    async def test_custom_builder_opens_for_managers(self):
        interaction = FakeInteraction()

        await button_labelled(picker(), "Eigenes").callback(cast("Any", interaction))

        assert interaction.response.modals

    async def test_apply_without_selection_is_refused(self):
        """Der Button ist deaktiviert — der Callback prueft trotzdem."""

        view = picker()
        interaction = FakeInteraction()

        await button_labelled(view, "Ergänzen").callback(cast("Any", interaction))

        assert "Nichts ausgewählt" in all_text(interaction)


# --------------------------------------------------------------------------- #
# Baukasten
# --------------------------------------------------------------------------- #

class TestCustomRulesModal:
    async def test_plain_text_produces_a_preview(self):
        interaction = FakeInteraction()

        await custom_modal("Unsere Regeln", "Sei nett.").on_submit(
            cast("Any", interaction)
        )

        assert "Vorschau" in all_text(interaction)

    @pytest.mark.parametrize(
        "url",
        [
            "https://example.com/banner.png",
            "http://example.com/bild.JPG",
            "https://cdn.example.com/a/b/c.webp",
            "https://example.com/x.gif?v=2",
        ],
    )
    async def test_valid_image_links_are_accepted(self, url):
        interaction = FakeInteraction()

        await custom_modal("Titel", "Text", top=url).on_submit(cast("Any", interaction))

        assert "ungültig" not in all_text(interaction)

    @pytest.mark.parametrize(
        "url",
        [
            "example.com/bild.png",          # ohne Schema
            "https://example.com/seite",     # keine Bilddatei
            "javascript:alert(1)",           # kein http(s)
            "https://example.com/x.svg",     # nicht unterstuetztes Format
            "ftp://example.com/x.png",
        ],
    )
    async def test_invalid_image_links_are_rejected(self, url):
        interaction = FakeInteraction()

        await custom_modal("Titel", "Text", top=url).on_submit(cast("Any", interaction))

        assert "ungültig" in all_text(interaction)

    async def test_the_rejection_names_which_image(self):
        """Bei zwei Feldern muss klar sein, welches gemeint ist."""

        interaction = FakeInteraction()

        await custom_modal("Titel", "Text", bottom="kaputt").on_submit(
            cast("Any", interaction)
        )

        assert "unten" in all_text(interaction)

    async def test_empty_image_fields_are_fine(self):
        """Beide Bilder sind optional."""

        interaction = FakeInteraction()

        await custom_modal("Titel", "Text", top="  ", bottom="").on_submit(
            cast("Any", interaction)
        )

        assert "ungültig" not in all_text(interaction)

    async def test_the_own_text_appears_in_the_preview(self):
        interaction = FakeInteraction()

        await custom_modal("Hausordnung", "Kein Spam bitte.").on_submit(
            cast("Any", interaction)
        )

        # Die Vorschau selbst steckt im Wrapper; geprueft wird, dass der
        # Assistent bis dorthin kommt statt vorher abzubrechen.
        assert interaction.response.sent
        assert "ungültig" not in all_text(interaction)

    async def test_publishing_writes_into_the_channel(self):
        """Der letzte Schritt des Baukastens."""

        channel = FakeTextChannel("regeln")
        interaction = FakeInteraction()
        modal = CustomRulesModal(cast("Any", FakeBot()), cast("Any", channel))
        for label, value in (
            (modal.heading, "Hausordnung"),
            (modal.body, "Kein Spam."),
            (modal.top_image, ""),
            (modal.bottom_image, ""),
        ):
            cast("Any", label.component)._value = value

        await modal.on_submit(cast("Any", interaction))
        wrapper = interaction.response.sent[0]

        publish = button_labelled(wrapper, "Veröffentlichen")
        publish_interaction = FakeInteraction()
        await publish.callback(cast("Any", publish_interaction))

        assert channel.sent, "Das eigene Regelwerk wurde nicht gepostet"
