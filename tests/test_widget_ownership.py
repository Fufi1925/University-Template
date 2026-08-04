"""Wer postet die Knöpfe: Template-Bot oder University Bot?

Verify, Regeln, Rollen-Vergabe und Tickets hängen an Rollen und
Einstellungen, die der University Bot verwaltet: er kennt die
Verified-Rolle, führt das Verify-Protokoll, hält die Reaktions-Rollen
und die Ticket-Panels.

Postet der Template-Bot dort zusätzlich ein eigenes Panel, stehen zwei
Knöpfe im selben Kanal — und welcher davon wirkt, sieht man erst beim
Draufklicken. Genau das ist im Betrieb passiert.

Der Template-Bot schreibt weiterhin den Kanal-Header, damit der Kanal
nicht leer ist, bis der Speedrun bei Schritt 2 angekommen ist. Nur die
Knöpfe bleiben weg.

Die Checkliste bleibt dagegen beim Template-Bot: sie listet auf, was
beim Aufbau von Hand zu tun ist, und der University Bot weiß davon
nichts.
"""

from __future__ import annotations

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from discord import ui

import config
from core.content import channel_guide
from core.registry import TemplateRegistry
from core.schema import Widget
from ui.channel_intro import intro_view


def _interactive(view: ui.LayoutView) -> list:
    """Alles, was man anklicken kann — beliebig tief verschachtelt."""

    found: list = []

    def walk(item):
        if isinstance(item, (ui.Button, ui.Select)):
            found.append(item)
        for child in getattr(item, "children", []) or []:
            walk(child)

    for child in view.children:
        walk(child)
    return found


def _text(view: ui.LayoutView) -> str:
    parts: list[str] = []

    def walk(item):
        content = getattr(item, "content", None)
        if isinstance(content, str):
            parts.append(content)
        for child in getattr(item, "children", []) or []:
            walk(child)

    for child in view.children:
        walk(child)
    return "\n".join(parts)


def _specs():
    registry = TemplateRegistry(config.TEMPLATE_DIR).load()
    for template in registry.all:
        for _category, spec in template.iter_channels():
            yield template.key, spec


class TestWidgetsSitOnChannelsThatCanHoldThem:
    """Ein Widget besteht aus Knöpfen. Die brauchen einen Textkanal.

    Drei Templates hatten ``widget="ticket"`` auf einem **Forum**. Ein
    Forum hat keine Nachrichtenliste, sondern Beiträge — eine
    angeheftete Nachricht mit Knöpfen lässt sich dort nicht ablegen. Das
    Panel wurde nie gepostet, und niemand konnte sagen, warum.

    Das Schema verbot Widgets nur auf Sprachkanälen; Foren fielen durch.
    """

    def test_every_widget_sits_on_a_text_channel(self):
        from core.schema import ChannelKind

        checked = 0
        for key, spec in _specs():
            if spec.widget is Widget.NONE:
                continue
            assert spec.kind is ChannelKind.TEXT, (
                f"{key}/{spec.label}: Widget »{spec.widget.value}« auf einem "
                f"{spec.kind.value}-Kanal — dort erscheint kein Panel"
            )
            checked += 1

        assert checked > 20, f"nur {checked} Widgets geprüft"

    def test_the_schema_rejects_a_widget_on_a_forum(self):
        """Die Sperre muss beim Laden greifen, nicht erst beim Bauen.

        Ohne sie fällt so ein Template erst auf einem echten Server auf,
        wenn das Panel fehlt.
        """

        from core.schema import ChannelSpec, TemplateError

        try:
            ChannelSpec.parse(
                {"label": "tickets", "kind": "forum", "widget": "ticket"},
                "Test",
            )
        except TemplateError as exc:
            assert "Foren" in str(exc), str(exc)
        else:
            raise AssertionError(
                "ein Forum mit Ticket-Widget wurde angenommen"
            )

        # Gegenprobe: derselbe Kanal als Textkanal geht durch.
        spec = ChannelSpec.parse(
            {"label": "tickets", "widget": "ticket"}, "Test"
        )
        assert spec.widget is Widget.TICKET

    def test_the_templates_offer_a_ticket_channel(self):
        """Ohne Ticket-Widget bleibt »channels.tickets« leer.

        Früher übersprang der Speedrun den Ticket-Schritt dann stumm —
        das war die Meldung „Ticket-Kanal kam nicht“.

        Inzwischen meldet jede Vorlage über ``capabilities``, was sie
        hergibt, und das Dashboard bietet den Schritt gar nicht erst
        an. Eine Vorlage ohne Ticket-Panel ist damit kein Fehler mehr,
        sondern eine Entscheidung — aber sie muss hier eingetragen
        sein, sonst ist es ein Versehen.
        """

        registry = TemplateRegistry(config.TEMPLATE_DIR).load()

        without = {
            template.key
            for template in registry.all
            if not any(
                spec.widget is Widget.TICKET
                for _category, spec in template.iter_channels()
            )
        }
        # business: ein Firmen-Server regelt Support über eigene Kanäle.
        # minimal:  bewusst klein -- kein Ticket-System, keine Verify-
        #           Schleuse, keine Rollen-Vergabe.
        expected = {"business", "minimal"}
        assert without == expected, (
            f"ohne Ticket-Kanal: {sorted(without)}, erwartet: {sorted(expected)}"
        )

        # Und was kein Panel hat, darf es auch nicht behaupten.
        for template in registry.all:
            if template.key in without:
                assert not template.capabilities["tickets"], (
                    f"{template.key} meldet Tickets, hat aber kein Panel — "
                    "das Dashboard böte den Schritt an, und er liefe ins Leere"
                )


class TestTheTemplateBotKeepsItsHandsOff:
    def test_no_buttons_in_the_main_bots_channels(self):
        """Kein anklickbares Element in Verify, Regeln, Rollen, Tickets."""

        owned = {Widget.VERIFY, Widget.RULES, Widget.ROLES, Widget.TICKET}
        checked = 0

        for key, spec in _specs():
            if spec.widget not in owned:
                continue
            guide = channel_guide(spec)
            if guide is None:
                continue

            view = intro_view(spec, *guide)
            clickable = _interactive(view)
            assert not clickable, (
                f"{key}/{spec.label} ({spec.widget.value}): der Template-Bot "
                f"postet {len(clickable)} Bedienelement(e) — daneben steht "
                "dann noch das Panel des University Bots"
            )
            checked += 1

        assert checked >= 3, f"nur {checked} Kanäle geprüft — findet der Test sie?"

    def test_the_text_does_not_promise_a_button(self):
        """„Klicke auf den Button“ ohne Button sieht nach Defekt aus."""

        owned = {Widget.VERIFY, Widget.RULES, Widget.ROLES, Widget.TICKET}

        for key, spec in _specs():
            if spec.widget not in owned:
                continue
            guide = channel_guide(spec)
            if guide is None:
                continue

            body = _text(intro_view(spec, *guide)).lower()
            for phrase in ("klicke auf den button", "mit dem button",
                           "im menü aus", "button unten"):
                assert phrase not in body, (
                    f"{key}/{spec.label}: Text verspricht »{phrase}«, "
                    "aber in dieser Nachricht ist kein Knopf"
                )

    def test_the_channel_is_not_left_empty(self):
        """Ohne Knopf muss wenigstens der Header dastehen.

        Sonst steht der Kanal leer, bis der Speedrun bei Schritt 2 ist —
        und bei einem Bau ohne den University Bot für immer.
        """

        owned = {Widget.VERIFY, Widget.RULES, Widget.ROLES, Widget.TICKET}

        for key, spec in _specs():
            if spec.widget not in owned:
                continue
            guide = channel_guide(spec)
            if guide is None:
                continue

            body = _text(intro_view(spec, *guide)).strip()
            assert len(body) > 40, (
                f"{key}/{spec.label}: die Startnachricht ist praktisch leer "
                f"({len(body)} Zeichen)"
            )
            # Und sie sagt, dass da noch was kommt.
            assert "University Bot" in body, (
                f"{key}/{spec.label}: es steht nicht da, wer das Panel stellt"
            )

    def test_the_checklist_keeps_its_own_view(self):
        """Die Checkliste bleibt beim Template-Bot.

        Sie listet auf, was beim Aufbau von Hand zu tun ist — davon weiß
        der University Bot nichts.

        Geprüft wird die *ChecklistView*, nicht „hat Knöpfe“: mein
        erster Versuch verlangte Bedienelemente, aber die Checkliste
        hatte nie welche, sie ist reiner Text. Der Test wäre also rot
        gewesen, ohne dass am Code etwas falsch war. Unterscheidbar ist
        sie an ihrer eigenen View-Klasse und an den Aufgabenpunkten.
        """

        from core.content import CHECKLIST_ITEMS
        from ui.widgets import ChecklistView

        found = False
        for _key, spec in _specs():
            if spec.widget is not Widget.CHECKLIST:
                continue
            guide = channel_guide(spec)
            if guide is None:
                continue

            view = intro_view(spec, *guide)
            assert isinstance(view, ChecklistView), (
                f"die Checkliste bekommt {type(view).__name__} statt "
                "ihrer eigenen View — sie wurde mit abgeschaltet"
            )
            body = _text(view)
            for item in CHECKLIST_ITEMS:
                assert item in body, f"Aufgabenpunkt fehlt: {item}"
            found = True

        assert found, "kein Checklisten-Kanal gefunden"

    def test_the_owned_channels_get_a_plain_header(self):
        """Gegenprobe: Verify & Co. bekommen wirklich die Header-View.

        Ohne das wäre nicht belegt, dass oben überhaupt unterschieden
        wird — die Prüfungen wären auch grün, wenn gar keine View mehr
        gebaut würde.
        """

        from ui.widgets import RulesView, SelfRoleView, TicketView, VerifyView

        interactive_views = (VerifyView, RulesView, SelfRoleView, TicketView)
        owned = {Widget.VERIFY, Widget.RULES, Widget.ROLES, Widget.TICKET}

        for key, spec in _specs():
            if spec.widget not in owned:
                continue
            guide = channel_guide(spec)
            if guide is None:
                continue
            view = intro_view(spec, *guide)
            assert not isinstance(view, interactive_views), (
                f"{key}/{spec.label}: bekommt weiterhin {type(view).__name__}"
            )

    def test_the_widgets_still_exist_for_the_main_bot(self):
        """Die Kanäle behalten ihr Widget-Feld.

        Nur das *Posten* wandert zum University Bot -- die Angabe im
        Template bleibt, denn daran erkennt die Übergabe, welcher Kanal
        der Verify-Kanal ist.
        """

        registry = TemplateRegistry(config.TEMPLATE_DIR).load()
        community = registry.get("community")

        widgets = {
            spec.widget
            for _category, spec in community.iter_channels()
            if spec.widget is not Widget.NONE
        }
        assert Widget.VERIFY in widgets, "die Übergabe fände den Verify-Kanal nicht"
        assert Widget.RULES in widgets
        assert Widget.ROLES in widgets
