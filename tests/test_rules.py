"""Regelwerk-Assistent: 20 Vorlagen, vier Optionen, eigener Baukasten."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import config
from core.registry import TemplateRegistry
from core.rulesets import (
    RULESETS,
    RuleLength,
    RuleScope,
    by_length,
    by_scope,
    get_ruleset,
)
from core.small_caps import strip_decoration


def _walk(payload):
    for item in payload:
        yield item
        for child in item.get("components", []):
            yield from _walk([child])
        accessory = item.get("accessory")
        if accessory:
            yield accessory


def _texts(view) -> list[str]:
    return [
        component["content"]
        for component in _walk(view.to_components())
        if component.get("type") == 10
    ]


# --------------------------------------------------------------------------- #
# Die Sammlung
# --------------------------------------------------------------------------- #

class TestRulesetCollection:
    def test_at_least_twenty(self):
        assert len(RULESETS) >= 20

    def test_keys_and_names_unique(self):
        assert len({r.key for r in RULESETS}) == len(RULESETS)
        assert len({r.name for r in RULESETS}) == len(RULESETS)

    def test_lengths_are_actually_different(self):
        """Kurz muss kürzer sein als lang — sonst ist die Einteilung gelogen."""

        short = max(r.char_count for r in by_length(RuleLength.SHORT))
        long_min = min(r.char_count for r in by_length(RuleLength.LONG))
        assert short < long_min, "Kurze Regelwerke sind nicht kürzer als lange"

    def test_every_length_is_represented(self):
        for length in RuleLength:
            assert by_length(length), f"Keine Vorlage der Länge {length.value}"

    def test_shortest_is_genuinely_short(self):
        shortest = min(RULESETS, key=lambda r: r.char_count)
        assert shortest.rule_count <= 6

    def test_longest_is_substantial(self):
        longest = max(RULESETS, key=lambda r: r.char_count)
        assert longest.rule_count >= 25

    def test_every_ruleset_has_content(self):
        for ruleset in RULESETS:
            assert ruleset.paragraphs, f"{ruleset.key} hat keine Paragraphen"
            assert ruleset.rule_count >= 5, f"{ruleset.key} hat zu wenige Paragraphen"
            assert ruleset.tagline
            assert ruleset.emoji
            assert ruleset.display_title

    def test_paragraphs_are_complete(self):
        for ruleset in RULESETS:
            for paragraph in ruleset.paragraphs:
                assert paragraph.title, f"{ruleset.key}: Paragraph ohne Titel"
                assert paragraph.text, f"{ruleset.key}/{paragraph.title}: kein Text"

    def test_paragraph_text_is_prose_not_bullets(self):
        """Der Text soll ein ausformulierter Satz sein, keine Stichpunktliste."""

        for ruleset in RULESETS:
            for paragraph in ruleset.paragraphs:
                text = paragraph.text
                # Leitet der Text eine Aufzaehlung ein, darf er kurz sein.
                minimum = 30 if paragraph.bullets else 40
                assert len(text) >= minimum, (
                    f"{ruleset.key}/{paragraph.title}: '{text}' ist zu knapp"
                )
                assert text[0].isupper(), f"{ruleset.key}/{paragraph.title}: klein"
                assert text.rstrip().endswith((".", "!", "?", ":")), (
                    f"{ruleset.key}/{paragraph.title}: kein Satzende"
                )
                assert not text.lstrip().startswith(("-", "•", "*")), (
                    f"{ruleset.key}/{paragraph.title}: sieht aus wie ein Stichpunkt"
                )

    def test_paragraph_titles_are_short(self):
        """Der Titel steht in der Überschrift — lange Titel brechen um."""

        for ruleset in RULESETS:
            for paragraph in ruleset.paragraphs:
                assert len(paragraph.title) <= 32, (
                    f"{ruleset.key}: '{paragraph.title}' ist zu lang"
                )

    def test_select_menu_limits_are_respected(self):
        """Discord erlaubt 25 Optionen mit je 100 Zeichen Beschreibung."""

        assert len(RULESETS) <= 25, "Mehr als 25 passen nicht in ein Dropdown"
        for ruleset in RULESETS:
            assert len(ruleset.name) <= 100

    def test_get_ruleset(self):
        assert get_ruleset("standard") is not None
        assert get_ruleset("gibtsnicht") is None

    def test_legal_ruleset_carries_a_disclaimer(self):
        """Eine Rechtsvorlage ohne Hinweis wäre fahrlässig."""

        legal = get_ruleset("rechtssicher")
        assert "keine Rechtsberatung" in legal.closing


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #

class TestRuleRendering:
    MAX_COMPONENTS = 40
    MAX_CHARS = 4000

    def test_all_rulesets_render_within_limits(self):
        from ui.rules import ruleset_views

        for ruleset in RULESETS:
            for index, view in enumerate(ruleset_views(ruleset, guild_name="Testserver")):
                components = list(_walk(view.to_components()))
                assert len(components) <= self.MAX_COMPONENTS, f"{ruleset.key}#{index}"
                chars = sum(
                    len(c.get("content", "")) for c in components if c.get("type") == 10
                )
                assert chars <= self.MAX_CHARS, f"{ruleset.key}#{index}: {chars} Zeichen"

    def test_every_rule_appears_in_the_output(self):
        """Kein Regelwerk darf beim Rendern Paragraphen verlieren."""

        from ui.rules import ruleset_views

        for ruleset in RULESETS:
            blob = ""
            for view in ruleset_views(ruleset):
                blob += "".join(_texts(view))
            for paragraph in ruleset.paragraphs:
                assert paragraph.title in blob, (
                    f"{ruleset.key}: '{paragraph.title}' fehlt"
                )
                assert paragraph.text in blob, (
                    f"{ruleset.key}: Text von '{paragraph.title}' fehlt"
                )
                for bullet in paragraph.bullets:
                    assert bullet in blob, f"{ruleset.key}: '{bullet}' fehlt"

    def test_rules_use_blockquotes(self):
        from ui.rules import ruleset_views

        for ruleset in RULESETS:
            view = ruleset_views(ruleset)[0]
            quoted = [
                line
                for text in _texts(view)
                for line in text.splitlines()
                if line.startswith(">")
            ]
            assert quoted, f"{ruleset.key} nutzt keine Blockzitate"

    def test_no_h1_and_quotes_never_become_headings(self):
        from ui.rules import ruleset_views

        for ruleset in RULESETS:
            for view in ruleset_views(ruleset):
                for text in _texts(view):
                    for line in text.splitlines():
                        assert not line.startswith("# "), f"{ruleset.key}: H1"
                        if line.startswith(">"):
                            body = line.lstrip(">").lstrip()
                            assert not body.startswith("#"), (
                                f"{ruleset.key}: Zitatzeile wird Überschrift"
                            )

    def test_paragraphs_are_numbered_continuously(self):
        """§1, §2, §3 … ohne Sprung und ohne Neustart."""

        from ui.rules import ruleset_views

        for ruleset in RULESETS:
            blob = ""
            for view in ruleset_views(ruleset):
                blob += "\n".join(_texts(view))
            for number in range(1, ruleset.rule_count + 1):
                assert f"**§{number} •" in blob, (
                    f"{ruleset.key}: §{number} fehlt in der Ausgabe"
                )
            missing = f"**§{ruleset.rule_count + 1} •"
            assert missing not in blob, f"{ruleset.key}: zu viele Paragraphen"

    def test_guild_name_is_used_as_subtitle(self):
        from ui.rules import ruleset_views

        blob = "\n".join(_texts(ruleset_views(get_ruleset("minimal"), guild_name="Mein Server")[0]))
        assert "Mein Server" in blob


# --------------------------------------------------------------------------- #
# Eigenes Regelwerk mit Bildern
# --------------------------------------------------------------------------- #

class TestCustomRules:
    TOP = "https://example.com/logo.png"
    BOTTOM = "https://example.com/banner.png"

    def test_top_image_sits_in_a_section_accessory(self):
        """Bild oben rechts = Thumbnail als Accessory einer Section."""

        from ui.rules import custom_rules_view

        payload = custom_rules_view("Regeln", "1. Test", self.TOP, None).to_components()
        sections = [c for c in _walk(payload) if c.get("type") == 9]
        assert sections, "Keine Section — das Bild steht nicht oben rechts"
        accessory = sections[0].get("accessory")
        assert accessory and accessory["type"] == 11
        assert accessory["media"]["url"] == self.TOP

    def test_bottom_image_is_a_media_gallery(self):
        from ui.rules import custom_rules_view

        payload = custom_rules_view("Regeln", "1. Test", None, self.BOTTOM).to_components()
        galleries = [c for c in _walk(payload) if c.get("type") == 12]
        assert galleries, "Kein Bild unten"
        assert galleries[0]["items"][0]["media"]["url"] == self.BOTTOM

    def test_both_images_together(self):
        from ui.rules import custom_rules_view

        components = list(
            _walk(custom_rules_view("Regeln", "1. Test", self.TOP, self.BOTTOM).to_components())
        )
        assert any(c.get("type") == 11 for c in components)
        assert any(c.get("type") == 12 for c in components)

    def test_works_without_any_image(self):
        from ui.rules import custom_rules_view

        view = custom_rules_view("Regeln", "1. Test\n2. Noch was", None, None)
        blob = "\n".join(_texts(view))
        assert "Regeln" in blob
        assert "> 1. Test" in blob

    def test_body_is_quoted_line_by_line(self):
        from ui.rules import custom_rules_view

        view = custom_rules_view("R", "Eins\nZwei\nDrei", None, None)
        blob = "\n".join(_texts(view))
        for word in ("Eins", "Zwei", "Drei"):
            assert f"> {word}" in blob

    def test_blank_lines_are_dropped(self):
        from ui.rules import custom_rules_view

        view = custom_rules_view("R", "Eins\n\n\nZwei", None, None)
        blob = "\n".join(_texts(view))
        assert ">\n>" not in blob

    def test_image_url_validation(self):
        from ui.rules import _URL_RE

        for good in (
            "https://example.com/a.png",
            "http://x.de/b.JPG",
            "https://cdn.discordapp.com/x/y.webp?size=512",
            "https://example.com/c.gif",
        ):
            assert _URL_RE.match(good), good

        for bad in (
            "example.com/a.png",
            "https://example.com/a.txt",
            "javascript:alert(1)",
            "https://example.com/",
            "nicht mal eine url",
        ):
            assert not _URL_RE.match(bad), bad

    def test_modal_fields_are_labelled(self):
        """ui.Label statt des veralteten label=-Arguments."""

        from ui.rules import CustomRulesModal

        for field in ("heading", "body", "top_image", "bottom_image"):
            label = getattr(CustomRulesModal, field)
            assert label.text
            assert label.description
            assert label.component is not None

    def test_only_heading_and_body_are_required(self):
        from ui.rules import CustomRulesModal

        assert CustomRulesModal.heading.component.required
        assert CustomRulesModal.body.component.required
        assert not CustomRulesModal.top_image.component.required
        assert not CustomRulesModal.bottom_image.component.required


# --------------------------------------------------------------------------- #
# Auswahl-Oberfläche
# --------------------------------------------------------------------------- #

class _FakeChannel:
    def __init__(self, name="📜・ʀᴇɢᴇʟɴ"):
        self.name = name
        self.mention = f"#{name}"


class _FakeBot:
    def __init__(self):
        self.registry = None


class TestPickerView:
    def test_picker_lists_every_ruleset(self):
        from ui.rules import RulesetPicker

        payload = RulesetPicker(_FakeBot(), _FakeChannel()).to_components()
        selects = [c for c in _walk(payload) if c.get("type") == 3]
        assert selects
        assert len(selects[0]["options"]) == len(RULESETS)

    def test_picker_offers_all_four_options(self):
        from ui.rules import RulesetPicker

        payload = RulesetPicker(_FakeBot(), _FakeChannel(), selected="standard").to_components()
        labels = [
            c.get("label", "") for c in _walk(payload) if c.get("type") == 2
        ]
        assert any("Ergänzen" in label for label in labels)
        assert any("Neu aufsetzen" in label for label in labels)
        assert any("Abbrechen" in label for label in labels)
        assert any("Eigenes" in label for label in labels)

    def test_apply_buttons_disabled_until_selection(self):
        from ui.rules import RulesetPicker

        payload = RulesetPicker(_FakeBot(), _FakeChannel()).to_components()
        buttons = {
            c.get("label"): c.get("disabled", False)
            for c in _walk(payload)
            if c.get("type") == 2
        }
        assert buttons.get("Ergänzen") is True
        assert buttons.get("Neu aufsetzen") is True
        # Abbrechen und der Baukasten bleiben immer nutzbar.
        assert buttons.get("Abbrechen") is False

    def test_selection_enables_apply(self):
        from ui.rules import RulesetPicker

        payload = RulesetPicker(
            _FakeBot(), _FakeChannel(), selected="minimal"
        ).to_components()
        buttons = {
            c.get("label"): c.get("disabled", False)
            for c in _walk(payload)
            if c.get("type") == 2
        }
        assert buttons.get("Ergänzen") is False

    def test_picker_within_component_limits(self):
        from ui.rules import RulesetPicker

        for selected in (None, "minimal", "ausfuehrlich", "rechtssicher"):
            view = RulesetPicker(_FakeBot(), _FakeChannel(), selected=selected)
            components = list(_walk(view.to_components()))
            assert len(components) <= 40, selected
            chars = sum(
                len(c.get("content", "")) for c in components if c.get("type") == 10
            )
            assert chars <= 4000, f"{selected}: {chars}"

    def test_only_one_option_marked_default(self):
        from ui.rules import RulesetPicker

        payload = RulesetPicker(_FakeBot(), _FakeChannel(), selected="rp_ic").to_components()
        select = next(c for c in _walk(payload) if c.get("type") == 3)
        defaults = [o for o in select["options"] if o.get("default")]
        assert len(defaults) == 1
        assert defaults[0]["value"] == "rp_ic"


# --------------------------------------------------------------------------- #
# Kanalerkennung
# --------------------------------------------------------------------------- #

class _Guild:
    def __init__(self, names):
        self.text_channels = [_FakeChannel(n) for n in names]


class TestChannelDetection:
    def test_finds_small_caps_channel(self):
        from ui.rules import find_rules_channel

        guild = _Guild(["💬・ᴀʟʟɢᴇᴍᴇɪɴ", "📜・ʀᴇɢᴇʟɴ", "🔊・ᴛᴀʟᴋ"])
        found = find_rules_channel(guild)
        assert found is not None
        assert strip_decoration(found.name) == "regeln"

    def test_finds_plain_channel(self):
        from ui.rules import find_rules_channel

        for name in ("regeln", "rules", "regelwerk", "serverregeln"):
            assert find_rules_channel(_Guild(["general", name])) is not None

    def test_returns_none_without_match(self):
        from ui.rules import find_rules_channel

        assert find_rules_channel(_Guild(["allgemein", "memes"])) is None

    def test_exact_match_wins_over_partial(self):
        from ui.rules import find_rules_channel

        guild = _Guild(["📜・ʀᴇɢᴇʟᴡᴇʀᴋ-ᴀʀᴄʜɪᴠ", "📜・ʀᴇɢᴇʟɴ"])
        assert strip_decoration(find_rules_channel(guild).name) == "regeln"


# --------------------------------------------------------------------------- #
# Verzahnung mit den Templates
# --------------------------------------------------------------------------- #

class TestTemplateIntegration:
    def test_every_template_has_a_detectable_rules_channel(self):
        """Ohne Regelkanal läuft der Assistent ins Leere."""

        from ui.rules import RULES_CHANNEL_HINTS

        registry = TemplateRegistry(config.TEMPLATE_DIR).load()
        for template in registry:
            names = [
                strip_decoration(channel.display_name)
                for _, channel in template.iter_channels()
            ]
            assert any(
                hint in name for name in names for hint in RULES_CHANNEL_HINTS
            ), f"{template.key} hat keinen erkennbaren Regelkanal"

    def test_report_offers_the_next_step(self):
        """Nach dem Bau soll der Weg zum Regelwerk sichtbar sein."""

        from core.builder import BuildMode, BuildReport
        from ui.views import _report_view

        registry = TemplateRegistry(config.TEMPLATE_DIR).load()
        template = registry.get("community")
        report = BuildReport(mode=BuildMode.EXTEND, template_key="community")
        report.channels_created = 93

        # Ohne Guild-Kontext bleibt der Bericht wie bisher.
        view = _report_view(template, report)
        labels = [c.get("label", "") for c in _walk(view.to_components()) if c.get("type") == 2]
        assert not any("Regelwerk" in label for label in labels)


# --------------------------------------------------------------------------- #
# Schreiben in den Kanal
# --------------------------------------------------------------------------- #

class _Msg:
    def __init__(self, channel, author_id, content="", view=None):
        self.channel = channel
        self.author = type("A", (), {"id": author_id})()
        self.content = content
        self.view = view
        self.deleted = False
        self.pinned = False
        self.components = []
        if view is not None:
            from discord.components import _component_factory

            self.components = [_component_factory(c) for c in view.to_components()]

    async def delete(self):
        self.deleted = True
        if self in self.channel.existing:
            self.channel.existing.remove(self)

    async def pin(self, reason=None):
        self.pinned = True


class _WritableChannel:
    def __init__(self, bot_id=1, forbidden=False):
        self.name = "📜・ʀᴇɢᴇʟɴ"
        self.mention = "#regeln"
        self.bot_id = bot_id
        self.forbidden = forbidden
        self.sent: list[_Msg] = []
        self.existing: list[_Msg] = []

    async def send(self, content=None, view=None):
        if self.forbidden:
            import discord

            raise discord.Forbidden(
                type("R", (), {"status": 403, "reason": "Forbidden"})(), "no"
            )
        assert not (content and view), (
            "content darf nicht zusammen mit einer Components-V2-View gesendet werden"
        )
        message = _Msg(self, self.bot_id, content or "", view=view)
        self.sent.append(message)
        return message

    def history(self, limit=100):
        items = list(self.existing)

        async def gen():
            for item in items:
                yield item

        return gen()


class _Me:
    id = 1


class _InteractionStub:
    def __init__(self, guild=None):
        self.guild = guild
        self.responses: list[object] = []

    async def edit_original_response(self, view=None, **kwargs):
        self.responses.append(view)


class _GuildStub:
    def __init__(self, channel):
        self.me = _Me()
        self.name = "Testserver"
        self.text_channels = [channel]


@pytest.mark.asyncio
class TestWriting:
    async def test_extend_keeps_foreign_messages(self):
        """Ergänzen darf nichts löschen — auch keine eigenen Nachrichten."""

        from ui.rules import _post, ruleset_views

        channel = _WritableChannel()
        foreign = _Msg(channel, author_id=42, content="Text eines Menschen")
        own = _Msg(channel, author_id=1, content="alte Bot-Nachricht")
        channel.existing = [foreign, own]

        interaction = _InteractionStub(_GuildStub(channel))
        await _post(interaction, channel, ruleset_views(get_ruleset("minimal")), reset=False)

        assert not foreign.deleted
        assert not own.deleted
        assert len(channel.sent) == 1

    async def test_reset_removes_only_bot_messages(self):
        """Neu aufsetzen räumt auf, ohne fremde Beiträge anzutasten."""

        from ui.rules import _post, ruleset_views

        channel = _WritableChannel()
        foreign = _Msg(channel, author_id=42, content="Beitrag eines Mitglieds")
        own = _Msg(channel, author_id=1, content="altes Regelwerk")
        channel.existing = [foreign, own]

        interaction = _InteractionStub(_GuildStub(channel))
        await _post(interaction, channel, ruleset_views(get_ruleset("standard")), reset=True)

        assert own.deleted, "Eigene alte Nachricht wurde nicht entfernt"
        assert not foreign.deleted, "Fremde Nachricht wurde angetastet!"

    async def test_first_message_is_pinned(self):
        from ui.rules import _post, ruleset_views

        channel = _WritableChannel()
        interaction = _InteractionStub(_GuildStub(channel))
        await _post(interaction, channel, ruleset_views(get_ruleset("community")), reset=False)

        assert channel.sent[0].pinned

    async def test_messages_carry_the_bot_marker(self):
        """Die Signatur steckt im View, nicht im verbotenen content-Feld."""

        from core.content import MARKER, has_marker
        from ui.rules import _post, ruleset_views

        channel = _WritableChannel()
        interaction = _InteractionStub(_GuildStub(channel))
        await _post(interaction, channel, ruleset_views(get_ruleset("minimal")), reset=False)

        message = channel.sent[0]
        assert message.content == "", "content muss bei Components V2 leer bleiben"
        assert MARKER in "".join(_texts(message.view))
        assert has_marker(message)

    async def test_missing_permission_is_reported(self):
        from ui.rules import _post, ruleset_views

        channel = _WritableChannel(forbidden=True)
        interaction = _InteractionStub(_GuildStub(channel))
        await _post(interaction, channel, ruleset_views(get_ruleset("minimal")), reset=False)

        assert interaction.responses, "Der Fehler wurde nicht gemeldet"
        blob = "".join(_texts(interaction.responses[-1]))
        assert "Schreibrecht" in blob or "nicht schreiben" in blob

    async def test_success_message_names_the_channel(self):
        from ui.rules import _post, ruleset_views

        channel = _WritableChannel()
        interaction = _InteractionStub(_GuildStub(channel))
        await _post(interaction, channel, ruleset_views(get_ruleset("minimal")), reset=False)

        blob = "".join(_texts(interaction.responses[-1]))
        assert channel.mention in blob

    async def test_all_rulesets_can_be_posted(self):
        from ui.rules import _post, ruleset_views

        for ruleset in RULESETS:
            channel = _WritableChannel()
            interaction = _InteractionStub(_GuildStub(channel))
            await _post(interaction, channel, ruleset_views(ruleset), reset=False)
            assert channel.sent, f"{ruleset.key} wurde nicht gesendet"


# --------------------------------------------------------------------------- #
# Rollenspiel: IC und OOC
# --------------------------------------------------------------------------- #

class TestRoleplayScopes:
    """RP-Server brauchen getrennte Regeln für Discord (OOC) und Spiel (IC)."""

    def test_all_three_variants_exist(self):
        assert by_scope(RuleScope.OOC), "Kein OOC-Regelwerk"
        assert by_scope(RuleScope.IC), "Kein IC-Regelwerk"
        assert by_scope(RuleScope.BOTH), "Keine kombinierte Fassung"

    def test_ic_covers_the_classic_rp_rules(self):
        """FailRP, RDM, VDM und Metagaming gehören in jedes IC-Regelwerk."""

        ic = by_scope(RuleScope.IC)[0]
        titles = " ".join(p.title for p in ic.paragraphs)
        for term in ("Roleplay", "FearRP", "RDM", "VDM", "Combat Logging",
                     "New Life Rule", "Powergaming", "Metagaming"):
            assert term in titles, f"IC-Regelwerk ohne '{term}'"

    def test_ooc_covers_discord_topics(self):
        ooc = by_scope(RuleScope.OOC)[0]
        titles = " ".join(p.title for p in ooc.paragraphs)
        for term in ("Respekt", "Werbung", "Datenschutz", "Team"):
            assert term in titles, f"OOC-Regelwerk ohne '{term}'"

    def test_ooc_explains_the_ic_separation(self):
        """Der wichtigste Grundsatz: Spielkonflikte bleiben im Spiel."""

        ooc = by_scope(RuleScope.OOC)[0]
        blob = ooc.intro + " ".join(p.title + p.text for p in ooc.paragraphs)
        assert "OOC" in blob
        assert "IC" in blob

    def test_ic_has_no_discord_only_rules(self):
        """Profilbilder und Werbung sind OOC-Themen, nicht IC."""

        ic = by_scope(RuleScope.IC)[0]
        titles = [p.title.lower() for p in ic.paragraphs]
        for off_topic in ("profil", "werbung", "tickets"):
            assert off_topic not in titles, f"IC enthält OOC-Thema '{off_topic}'"

    def test_intros_name_the_scope(self):
        for scope, needle in ((RuleScope.OOC, "OOC"), (RuleScope.IC, "IC")):
            ruleset = by_scope(scope)[0]
            assert needle in ruleset.intro, f"{ruleset.key}: Einleitung erklärt {needle} nicht"

    def test_combined_contains_both_sides(self):
        combined = by_scope(RuleScope.BOTH)[0]
        titles = " ".join(p.title for p in combined.paragraphs)
        assert "Metagaming" in titles, "IC-Teil fehlt"
        assert "Werbung" in titles, "OOC-Teil fehlt"

    def test_combined_is_the_longest(self):
        combined = by_scope(RuleScope.BOTH)[0]
        assert combined.rule_count > by_scope(RuleScope.OOC)[0].rule_count
        assert combined.rule_count > by_scope(RuleScope.IC)[0].rule_count

    def test_ic_and_ooc_use_distinct_titles(self):
        """Die Überschrift muss auf einen Blick zeigen, worum es geht."""

        assert "IN GAME" in by_scope(RuleScope.IC)[0].display_title
        assert "DISCORD" in by_scope(RuleScope.OOC)[0].display_title

    def test_scope_is_visible_in_the_picker(self):
        from ui.rules import RulesetPicker

        payload = RulesetPicker(_FakeBot(), _FakeChannel()).to_components()
        select = next(c for c in _walk(payload) if c.get("type") == 3)
        descriptions = " ".join(o.get("description", "") for o in select["options"])
        assert "IC" in descriptions
        assert "OOC" in descriptions


class TestParagraphStyle:
    """Das Format aus dem Vorbild: §n • Titel, darunter Fließtext."""

    def test_rendered_paragraphs_use_the_section_sign(self):
        from ui.rules import ruleset_views

        blob = "\n".join(_texts(ruleset_views(get_ruleset("standard"))[0]))
        assert "**§1 • Respekt**" in blob
        assert "**§2 • Chat**" in blob

    def test_title_and_text_are_on_separate_lines(self):
        from ui.rules import ruleset_views

        blob = "\n".join(_texts(ruleset_views(get_ruleset("standard"))[0]))
        lines = [line for line in blob.splitlines() if line.startswith("> **§")]
        assert lines
        for line in lines:
            # Die Überschrift steht allein in ihrer Zeile.
            assert line.rstrip().endswith("**"), f"Titelzeile enthält Text: {line}"

    def test_bullets_render_below_their_paragraph(self):
        from ui.rules import ruleset_views

        blob = "\n".join(_texts(ruleset_views(get_ruleset("standard"))[0]))
        assert "> • Verwarnung bei leichten Verstößen" in blob

    def test_document_title_is_uppercase(self):
        for ruleset in RULESETS:
            title = ruleset.display_title
            assert title == title.upper(), f"{ruleset.key}: '{title}' nicht in Versalien"

    def test_long_rulesets_split_at_paragraph_boundaries(self):
        """Ein Paragraph darf niemals über zwei Nachrichten zerrissen werden."""

        from ui.rules import ruleset_views

        for ruleset in RULESETS:
            views = ruleset_views(ruleset)
            if len(views) < 2:
                continue
            for paragraph in ruleset.paragraphs:
                hits = sum(
                    1 for view in views if paragraph.text in "".join(_texts(view))
                )
                assert hits == 1, (
                    f"{ruleset.key}: '{paragraph.title}' steht {hits}× — zerrissen?"
                )

    def test_continuation_messages_are_marked(self):
        from ui.rules import ruleset_views

        views = ruleset_views(get_ruleset("rp_komplett"))
        assert len(views) >= 2
        assert "Fortsetzung" in "".join(_texts(views[1]))
