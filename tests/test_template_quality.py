"""Der Qualitaetsstandard aller Vorlagen.

``test_architect.py`` prueft die harten Grenzen (Discord-Limits, deutsche
Namen, Log-Suite). Diese Datei prueft den *Anspruch*: Was gehoert auf
jeden ernsthaften Server, und woran merkt man, dass eine Vorlage
lieblos wurde?

* **Kein toter Kanal** — jeder Textkanal hat Topic, Guide oder Widget,
  sonst steht dort eine angeheftete Nachricht ohne Inhalt.
* **Die fuenf Kern-Widgets** — Verify, Regeln, Rollen, Tickets und die
  Team-Checkliste gehoeren auf jeden grossen Server.
* **Konsistente Pflichtbereiche** — Team, Leitung und Hilfe sehen
  ueberall gleich aus, damit sich keine Vorlage „arm baut".
* **Sprachbereich** — ueberall dieselben zwei Text- und vier
  Sprachkanal-Raeume.

Ausnahme bleibt ``minimal`` — bewusst klein, dokumentiert in der README.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import config
from core.registry import TemplateRegistry
from core.schema import ChannelKind, Widget

#: Kompakte Vorlagen duerfen bewusst weniger: siehe README.
COMPACT = {"minimal"}


@pytest.fixture(scope="module")
def registry() -> TemplateRegistry:
    return TemplateRegistry(config.TEMPLATE_DIR).load()


@pytest.fixture(scope="module")
def full_templates(registry):
    """Alle Vorlagen, die den vollen Standard erfuellen muessen."""

    return [t for t in registry if t.key not in COMPACT]


def _labels(template, category_label: str) -> set[str]:
    category = next((c for c in template.categories if c.label == category_label), None)
    if category is None:
        return set()
    return {channel.label for channel in category.channels}


def _widgets(template) -> set[Widget]:
    return {
        channel.widget
        for _category, channel in template.iter_channels()
        if channel.widget is not Widget.NONE
    }


class TestNoDeadChannels:
    def test_every_text_channel_has_an_intro(self, registry):
        """Kein Textkanal ohne Topic/Guide/Widget — sonst steht die
        angeheftete Startnachricht mit leeren Haenden da."""

        for template in registry:
            for category, channel in template.iter_channels():
                if channel.kind in {ChannelKind.VOICE, ChannelKind.STAGE}:
                    continue
                assert channel.wants_message, (
                    f"{template.key}/{category.label}/{channel.label}: "
                    "kein topic, kein guide, kein widget, kein modus"
                )

    def test_every_category_has_channels(self, registry):
        for template in registry:
            for category in template.categories:
                assert category.channels, f"{template.key}: Kategorie '{category.label}' ist leer"


class TestCoreWidgets:
    def test_every_full_template_has_the_five_core_widgets(self, full_templates):
        """Verify, Regeln, Rollen, Tickets, Checkliste — der Standard."""

        expected = {
            Widget.VERIFY,
            Widget.RULES,
            Widget.ROLES,
            Widget.TICKET,
            Widget.CHECKLIST,
        }
        for template in full_templates:
            widgets = _widgets(template)
            missing = expected - widgets
            assert not missing, f"{template.key} fehlen: {sorted(w.value for w in missing)}"

    def test_every_full_template_has_a_forum(self, full_templates):
        for template in full_templates:
            forums = [
                channel
                for _category, channel in template.iter_channels()
                if channel.kind is ChannelKind.FORUM
            ]
            assert forums, f"{template.key} hat kein Forum"

    def test_every_full_template_has_a_join_to_create_room(self, full_templates):
        for template in full_templates:
            assert any(
                channel.label == "eigenen-talk-erstellen"
                for _category, channel in template.iter_channels()
            ), f"{template.key} hat keinen Join-to-Create-Kanal"


class TestSharedSections:
    """Die Pflichtbereiche sehen in jeder Vorlage gleich aus."""

    def test_team_section_is_complete(self, full_templates):
        for template in full_templates:
            labels = _labels(template, "team")
            assert {
                "team-chat",
                "team-ankuendigungen",
                "aufgaben",
                "meldungen",
                "team-talk",
                "besprechungsraum",
            } <= labels, f"{template.key}: Team-Bereich unvollstaendig: {sorted(labels)}"
            # Bewerbungen duerfen einen eigenen Namen tragen (z. B. der
            # Clan nennt sie "bewerbungs-sichtung") — aber es muss einen
            # geben.
            assert any(label.startswith("bewerb") for label in labels), (
                f"{template.key}: kein Bewerbungs-Kanal im Team"
            )

    def test_leitung_section_is_complete(self, full_templates):
        for template in full_templates:
            labels = _labels(template, "leitung")
            assert "leitungs-talk" in labels, f"{template.key} hat keine Leitung"
            assert len(labels) >= 4, f"{template.key}: Leitung zu klein: {sorted(labels)}"

    def test_hilfe_section_is_complete(self, full_templates):
        for template in full_templates:
            labels = _labels(template, "hilfe")
            assert "ticket-eroeffnen" in labels, f"{template.key} hat kein Ticket-Panel"
            assert len(labels) >= 5, f"{template.key}: Hilfe zu klein: {sorted(labels)}"

    def test_every_full_template_has_a_suggestion_channel(self, full_templates):
        """Ideen muessen irgendwo hin — Vorschlaege oder Funktionswuensche."""

        for template in full_templates:
            names = {channel.label for _c, channel in template.iter_channels()}
            assert {"vorschlaege", "funktionswuensche"} & names, (
                f"{template.key} hat keinen Vorschlags-Kanal"
            )

    def test_sprach_talks_have_the_same_four_rooms(self, full_templates):
        for template in full_templates:
            assert _labels(template, "sprach-talks") == {
                "deutsch-talk",
                "english-talk",
                "deutsch-talk-2",
                "english-talk-2",
            }, f"{template.key}: Sprach-Talks weichen ab"

    def test_info_section_offers_self_roles(self, full_templates):
        """Die Rollen-Vergabe gehoert in den Infobereich jeder Vorlage."""

        for template in full_templates:
            has_roles_widget = any(
                channel.widget is Widget.ROLES
                for _category, channel in template.iter_channels()
            )
            assert has_roles_widget, f"{template.key} hat keine Rollen-Vergabe"


class TestReactions:
    """Auto-Reaktionen dort, wo sie hingehoeren — und sonst nirgends."""

    def test_feedback_channels_get_up_and_down_votes(self, full_templates):
        for template in full_templates:
            for _category, channel in template.iter_channels():
                if channel.label in {"vorschlaege", "umfragen", "funktionswuensche"}:
                    assert "👍" in channel.reactions and "👎" in channel.reactions, (
                        f"{template.key}: {channel.label} ohne Abstimmung"
                    )

    def test_memes_channels_laugh(self, full_templates):
        for template in full_templates:
            for _category, channel in template.iter_channels():
                if channel.label in {"memes", "meme", "memes-und-more"}:
                    assert channel.reactions, f"{template.key}: {channel.label} ohne Reaktion"
