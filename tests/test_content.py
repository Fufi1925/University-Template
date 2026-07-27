"""Kanalinhalte: Startnachrichten, Widgets, Modi, Reaktionen.

Der Bot schreibt jetzt in die Kanäle. Das ist der eingriffsintensivste Teil
des Projekts — deshalb prüft diese Datei besonders genau, dass

* nichts doppelt gepostet wird (zweiter Lauf bearbeitet statt sendet),
* Sprachkanäle keine Nachricht bekommen,
* die durchgesetzten Regeln das Team nicht aussperren,
* und der Modus einen Neustart übersteht (Topic-Marken).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import config  # noqa: E402
from core.content import MARKER, channel_guide, mode_rule, seed_message  # noqa: E402
from core.enforcement import (  # noqa: E402
    mode_tag,
    next_count,
    read_mode,
    read_reactions,
    reaction_tag,
    strip_tags,
)
from core.registry import TemplateRegistry  # noqa: E402
from core.schema import ChannelKind, ChannelMode, ChannelSpec, Widget  # noqa: E402


@pytest.fixture(scope="module")
def registry() -> TemplateRegistry:
    return TemplateRegistry(config.TEMPLATE_DIR).load()


# --------------------------------------------------------------------------- #
# Schema
# --------------------------------------------------------------------------- #

class TestSchema:
    def test_defaults_are_inert(self):
        """Ein Kanal ohne Angaben verhält sich wie vorher."""

        spec = ChannelSpec(label="test")
        assert spec.mode is ChannelMode.FREE
        assert spec.widget is Widget.NONE
        assert spec.reactions == ()

    def test_voice_channels_want_no_message(self):
        for kind in (ChannelKind.VOICE, ChannelKind.STAGE):
            spec = ChannelSpec(label="talk", kind=kind, topic="Reden")
            assert not spec.wants_message

    def test_text_channel_with_topic_wants_message(self):
        assert ChannelSpec(label="chat", topic="Reden").wants_message

    def test_bare_channel_wants_nothing(self):
        assert not ChannelSpec(label="leer").wants_message

    def test_widget_on_voice_is_rejected(self):
        from core.schema import Template, TemplateError

        with pytest.raises(TemplateError, match="Widget"):
            Template.parse(
                {
                    "key": "x", "name": "X",
                    "categories": [{
                        "label": "c",
                        "channels": [{"label": "v", "kind": "voice", "widget": "verify"}],
                    }],
                }
            )

    def test_unknown_mode_is_rejected(self):
        from core.schema import Template, TemplateError

        with pytest.raises(TemplateError, match="Modus"):
            Template.parse(
                {
                    "key": "x", "name": "X",
                    "categories": [{"label": "c", "channels": [{"label": "a", "mode": "chaos"}]}],
                }
            )

    def test_reaction_limit(self):
        from core.schema import Template, TemplateError

        with pytest.raises(TemplateError, match="Reaktionen"):
            Template.parse(
                {
                    "key": "x", "name": "X",
                    "categories": [{
                        "label": "c",
                        "channels": [{"label": "a", "reactions": list("123456")}],
                    }],
                }
            )


# --------------------------------------------------------------------------- #
# Texte
# --------------------------------------------------------------------------- #

class TestGuideText:
    def test_guide_beats_topic(self):
        spec = ChannelSpec(label="a", topic="Topic", guide=("Handgeschrieben",))
        _, lines = channel_guide(spec)
        assert "Handgeschrieben" in lines
        assert "Topic" not in lines

    def test_topic_is_the_fallback(self):
        _, lines = channel_guide(ChannelSpec(label="a", topic="Zweck des Kanals"))
        assert lines == ["Zweck des Kanals"]

    def test_mode_rule_is_appended(self):
        spec = ChannelSpec(label="bilder", topic="Bilder", mode=ChannelMode.MEDIA)
        _, lines = channel_guide(spec)
        assert any("Bild" in line and "Video" in line for line in lines)

    def test_media_rule_announces_deletion(self):
        """Wer gewarnt ist, ärgert sich nicht über gelöschte Nachrichten."""

        rule = mode_rule(ChannelSpec(label="x", mode=ChannelMode.MEDIA))
        assert "entfernt" in rule.lower()

    def test_log_channels_say_do_not_write(self):
        rule = mode_rule(ChannelSpec(label="mod-logs", mode=ChannelMode.LOG))
        assert "nicht" in rule.lower()

    def test_title_is_readable_not_small_caps(self):
        title, _ = channel_guide(ChannelSpec(label="bilder-und-clips", emoji="🖼️", topic="x"))
        assert "Bilder Und Clips" in title
        assert "ʙ" not in title

    def test_title_restores_umlauts(self):
        """Kanalnamen sind gefaltet, die Überschrift soll es nicht sein."""

        for label, expected in (
            ("zaehlen", "Zählen"),
            ("vorschlaege", "Vorschläge"),
            ("haeufige-fragen", "Häufige Fragen"),
        ):
            title, _ = channel_guide(ChannelSpec(label=label, topic="x"))
            assert expected in title, f"{label} -> {title}"

    def test_widget_channels_skip_the_mode_rule(self):
        """Der Button erklärt sich selbst; „Nur zum Lesen" wäre widersprüchlich."""

        from core.schema import Visibility

        spec = ChannelSpec(
            label="regeln",
            widget=Widget.RULES,
            visibility=Visibility.READONLY,
            topic="Serverregeln",
        )
        _, lines = channel_guide(spec)
        assert not any("Nur zum Lesen" in line for line in lines)

    def test_voice_channel_has_no_guide(self):
        assert channel_guide(ChannelSpec(label="talk", kind=ChannelKind.VOICE)) is None

    def test_counting_seeds_with_one(self):
        assert seed_message(ChannelSpec(label="zaehlen", mode=ChannelMode.COUNTING)) == "1"

    def test_no_seed_by_default(self):
        assert seed_message(ChannelSpec(label="chat", topic="x")) is None


# --------------------------------------------------------------------------- #
# Topic-Marken (überleben den Neustart)
# --------------------------------------------------------------------------- #

class _Chan:
    def __init__(self, topic):
        self.topic = topic


class TestTopicTags:
    def test_mode_survives_round_trip(self):
        for mode in ChannelMode:
            channel = _Chan(f"Beschreibung {mode_tag(mode)}")
            assert read_mode(channel) is mode

    def test_free_mode_writes_no_tag(self):
        assert mode_tag(ChannelMode.FREE) == ""

    def test_reactions_survive_round_trip(self):
        channel = _Chan(f"Text {reaction_tag(('👍', '👎'))}")
        assert read_reactions(channel) == ("👍", "👎")

    def test_missing_topic_is_free(self):
        assert read_mode(_Chan(None)) is ChannelMode.FREE
        assert read_reactions(_Chan(None)) == ()

    def test_broken_tag_does_not_crash(self):
        assert read_mode(_Chan("[mode:quatsch]")) is ChannelMode.FREE

    def test_strip_tags_hides_them_from_users(self):
        topic = f"Sichtbarer Text {mode_tag(ChannelMode.MEDIA)}{reaction_tag(('⭐',))}"
        assert strip_tags(topic) == "Sichtbarer Text"


class TestCounting:
    def test_first_number_is_one(self):
        assert next_count(None) == 1
        assert next_count("kein zahl") == 1

    def test_increments(self):
        assert next_count("41") == 42
        assert next_count("41 nice") == 42


# --------------------------------------------------------------------------- #
# Inhalte der ausgelieferten Vorlagen
# --------------------------------------------------------------------------- #

class TestShippedContent:
    def test_every_template_has_a_verify_widget(self, registry):
        for template in registry:
            widgets = {c.widget for _, c in template.iter_channels()}
            assert Widget.VERIFY in widgets, f"{template.key} ohne Verify-Button"

    def test_every_template_has_rules_widget(self, registry):
        for template in registry:
            widgets = {c.widget for _, c in template.iter_channels()}
            assert Widget.RULES in widgets, f"{template.key} ohne Regel-Zustimmung"

    def test_widgets_only_on_text_channels(self, registry):
        for template in registry:
            for _, channel in template.iter_channels():
                if channel.widget is not Widget.NONE:
                    assert not channel.kind.is_voice_like

    def test_log_channels_are_marked_as_log(self, registry):
        for template in registry:
            for _, channel in template.iter_channels():
                if channel.label.endswith("-logs"):
                    assert channel.mode is ChannelMode.LOG, (
                        f"{template.key}/{channel.label} ist nicht als Log markiert"
                    )

    def test_media_channels_exist_and_are_sensible(self, registry):
        template = registry.get("community")
        media = {c.label for _, c in template.iter_channels() if c.mode is ChannelMode.MEDIA}
        assert "memes" in media
        assert "bilder-und-clips" in media
        # Der Hauptchat darf niemals Media-only sein.
        assert "allgemein" not in media

    def test_counting_channel_is_configured(self, registry):
        template = registry.get("community")
        counting = [c for _, c in template.iter_channels() if c.mode is ChannelMode.COUNTING]
        assert len(counting) == 1
        assert seed_message(counting[0]) == "1"

    def test_suggestion_channels_get_vote_reactions(self, registry):
        for template in registry:
            for _, channel in template.iter_channels():
                if channel.label == "vorschlaege":
                    assert "👍" in channel.reactions

    def test_reactions_only_where_useful(self, registry):
        """Nicht jeder Kanal soll Reaktionen bekommen — das wäre Lärm."""

        template = registry.get("community")
        with_reactions = sum(1 for _, c in template.iter_channels() if c.reactions)
        assert 0 < with_reactions < template.channel_count / 4

    def test_enforced_modes_stay_on_text_channels(self, registry):
        for template in registry:
            for _, channel in template.iter_channels():
                if channel.mode.is_enforced:
                    assert channel.kind is ChannelKind.TEXT

    def test_most_channels_have_something_to_say(self, registry):
        """Ein Kanal ohne Hinweis ist genau das Problem, das wir lösen."""

        for template in registry:
            text_channels = [
                c for _, c in template.iter_channels() if not c.kind.is_voice_like
            ]
            with_message = [c for c in text_channels if c.wants_message]
            ratio = len(with_message) / len(text_channels)
            assert ratio > 0.95, f"{template.key}: nur {ratio:.0%} der Kanäle erklärt"

    def test_marker_is_invisible(self):
        """Die Signatur darf im Client nicht sichtbar sein."""

        import unicodedata

        assert len(MARKER) <= 4
        for char in MARKER:
            # Cf = "Format", also steuernde Zeichen ohne eigene Darstellung.
            assert unicodedata.category(char) == "Cf", (
                f"{char!r} ist im Client sichtbar"
            )


# --------------------------------------------------------------------------- #
# Durchsetzung
# --------------------------------------------------------------------------- #

class _Perms:
    def __init__(self, manage: bool = False, admin: bool = False) -> None:
        self.manage_messages = manage
        self.administrator = admin


class _Author:
    def __init__(self, manage: bool = False, admin: bool = False) -> None:
        self.mention = "@user"
        self.bot = False
        self.guild_permissions = _Perms(manage, admin)


class _CachelessUser:
    """Ein User ohne Member-Daten — passiert bei unvollständigem Cache."""

    mention = "@user"
    bot = False


class _Channel:
    def __init__(self, topic: str) -> None:
        self.topic = topic
        self.hints: list[str] = []

    async def send(self, content, delete_after=None):
        self.hints.append(content)

    def history(self, **kwargs):
        async def empty():
            return
            yield  # pragma: no cover

        return empty()


class _Message:
    def __init__(self, channel, content="", author=None, attachment=False, embed=False):
        self.channel = channel
        self.content = content
        self.author = author or _Author()
        self.attachments = [object()] if attachment else []
        self.embeds = [object()] if embed else []
        self.stickers = []
        self.deleted = False

    async def delete(self):
        self.deleted = True


@pytest.mark.asyncio
class TestEnforcement:
    async def test_plain_text_is_removed_in_media_channel(self):
        from core.enforcement import check_message

        channel = _Channel(f"Bilder {mode_tag(ChannelMode.MEDIA)}")
        message = _Message(channel, "nur text")
        assert await check_message(message) is True
        assert message.deleted
        assert channel.hints, "Ohne Hinweis versteht niemand die Löschung"

    async def test_attachment_survives(self):
        from core.enforcement import check_message

        channel = _Channel(f"Bilder {mode_tag(ChannelMode.MEDIA)}")
        message = _Message(channel, "", attachment=True)
        assert await check_message(message) is False
        assert not message.deleted

    async def test_link_survives(self):
        from core.enforcement import check_message

        channel = _Channel(f"Bilder {mode_tag(ChannelMode.MEDIA)}")
        message = _Message(channel, "schau mal https://example.com/x.png")
        assert await check_message(message) is False

    async def test_team_is_never_touched(self):
        """Ein Bot, der Moderatoren löscht, fliegt sofort vom Server."""

        from core.enforcement import check_message

        channel = _Channel(f"Bilder {mode_tag(ChannelMode.MEDIA)}")
        for author in (_Author(manage=True), _Author(admin=True)):
            message = _Message(channel, "text", author=author)
            assert await check_message(message) is False
            assert not message.deleted

    async def test_unknown_member_is_spared(self):
        """Fehlt der Cache, wird im Zweifel nicht gelöscht."""

        from core.enforcement import check_message

        channel = _Channel(f"Bilder {mode_tag(ChannelMode.MEDIA)}")
        message = _Message(channel, "text", author=_CachelessUser())
        assert await check_message(message) is False

    async def test_free_channels_are_untouched(self):
        from core.enforcement import check_message

        channel = _Channel("Ganz normaler Kanal")
        message = _Message(channel, "irgendwas")
        assert await check_message(message) is False

    async def test_log_mode_is_not_enforced_on_messages(self):
        """Log-Kanäle werden über Rechte geschützt, nicht per Löschung."""

        from core.enforcement import check_message

        channel = _Channel(f"Logs {mode_tag(ChannelMode.LOG)}")
        message = _Message(channel, "hallo")
        assert await check_message(message) is False

    async def test_counting_rejects_wrong_number(self):
        from core.enforcement import check_message

        channel = _Channel(f"Zählen {mode_tag(ChannelMode.COUNTING)}")
        message = _Message(channel, "57")
        assert await check_message(message) is True
        assert "1" in channel.hints[0]

    async def test_counting_accepts_the_next_number(self):
        from core.enforcement import check_message

        channel = _Channel(f"Zählen {mode_tag(ChannelMode.COUNTING)}")
        message = _Message(channel, "1")
        assert await check_message(message) is False


class TestPersistence:
    """Ein Verify-Button, der nach dem Deploy tot ist, ist schlimmer als keiner."""

    def test_widgets_have_no_timeout(self):
        from ui.widgets import PERSISTENT_VIEWS

        for view_cls in PERSISTENT_VIEWS:
            assert view_cls().timeout is None, f"{view_cls.__name__} läuft ab"

    def test_widgets_have_stable_custom_ids(self):
        from ui.widgets import PERSISTENT_VIEWS

        found: list[str] = []

        def walk(items):
            for item in items:
                cid = getattr(item, "custom_id", None)
                if cid:
                    found.append(cid)
                walk(getattr(item, "children", []) or [])

        for view_cls in PERSISTENT_VIEWS:
            walk(view_cls().children)

        assert found, "Keine custom_id gefunden"
        assert len(found) == len(set(found)), "custom_ids sind nicht eindeutig"
        assert all(cid.startswith("architect:") for cid in found)

    def test_every_widget_type_is_buildable(self):
        from core.schema import Widget
        from ui.widgets import build_widget_view

        for widget in Widget:
            if widget is Widget.NONE:
                continue
            view = build_widget_view(widget.value, "Titel", ["Zeile"])
            assert view is not None, f"{widget.value} lässt sich nicht bauen"
            assert view.to_components()

    def test_widget_views_respect_component_limits(self):
        from core.schema import Widget
        from ui.widgets import build_widget_view

        for widget in Widget:
            if widget is Widget.NONE:
                continue
            view = build_widget_view(widget.value, "Titel", ["Zeile"])
            payload = view.to_components()

            def walk(items):
                for item in items:
                    yield item
                    yield from walk(item.get("components", []))

            components = list(walk(payload))
            assert len(components) <= 40
            text = sum(
                len(c.get("content", "")) for c in components if c.get("type") == 10
            )
            assert text <= 4000


class TestComponentsV2Contract:
    """Discord verbietet ``content`` zusammen mit Components V2.

    Der Fehler lautet:

        Invalid Form Body — In content: The 'content' field cannot be used
        when using IS_COMPONENTS_V2

    Er tritt erst zur Laufzeit auf und traf jede einzelne Kanalnachricht.
    Diese Tests halten die Regel im gesamten Quelltext fest.
    """

    @staticmethod
    def _sources():
        roots = [BASE_DIR / "core", BASE_DIR / "ui"]
        files = [p for root in roots for p in root.glob("*.py")]
        files.append(BASE_DIR / "bot.py")
        return [(p.name, p.read_text(encoding="utf-8")) for p in files]

    def test_no_send_with_content_and_view(self):
        import re

        # Findet send(...) / edit(...) mit content= UND view= im selben Aufruf.
        pattern = re.compile(
            r"\.(?:send|edit|edit_original_response)\(\s*[^)]*\bcontent\s*=[^)]*\bview\s*=",
            re.S,
        )
        for name, source in self._sources():
            match = pattern.search(source)
            assert match is None, (
                f"{name}: content= und view= im selben Aufruf — "
                f"Discord lehnt das ab:\n{match.group(0)[:120]}"
            )

    def test_no_view_then_content(self):
        """Auch die umgekehrte Reihenfolge ist verboten."""

        import re

        pattern = re.compile(
            r"\.(?:send|edit|edit_original_response)\(\s*[^)]*\bview\s*=[^)]*\bcontent\s*=",
            re.S,
        )
        for name, source in self._sources():
            match = pattern.search(source)
            assert match is None, f"{name}: view= und content= im selben Aufruf"

    def test_marker_lives_in_the_view_not_in_content(self):
        """Die Signatur muss im gerenderten View stehen, damit sie ankommt."""

        from core.registry import TemplateRegistry
        from ui.channel_intro import intro_view

        registry = TemplateRegistry(config.TEMPLATE_DIR).load()
        template = registry.get("community")

        checked = 0
        for _, spec in template.iter_channels():
            guide = channel_guide(spec)
            if guide is None:
                continue
            view = intro_view(spec, *guide)
            rendered = _flatten_text(view)
            assert MARKER in rendered, f"{spec.label}: Signatur fehlt im View"
            checked += 1
        assert checked > 20

    def test_marker_is_readable_from_a_received_message(self):
        """has_marker muss die Signatur aus message.components lesen können."""

        from discord.components import _component_factory

        from core.content import has_marker
        from core.registry import TemplateRegistry
        from ui.channel_intro import intro_view

        registry = TemplateRegistry(config.TEMPLATE_DIR).load()
        template = registry.get("community")
        _, spec = next(
            (c, s) for c, s in template.iter_channels() if s.wants_message
        )
        view = intro_view(spec, *channel_guide(spec))

        class Received:
            content = ""  # Discord liefert bei Components V2 einen leeren String
            components = [_component_factory(raw) for raw in view.to_components()]

        assert has_marker(Received())

    def test_unmarked_message_is_not_claimed(self):
        """Fremde Nachrichten dürfen nicht als eigene erkannt werden."""

        from core.content import has_marker

        class Foreign:
            content = "Ein normaler Beitrag"
            components = []

        assert not has_marker(Foreign())

    def test_ephemeral_dialogs_are_not_marked(self):
        """Nur dauerhafte Nachrichten tragen die Signatur."""

        from ui.components import notice

        assert MARKER not in _flatten_text(notice("Titel", "Text"))


def _flatten_text(view) -> str:
    """Alle Textinhalte einer View als ein String."""

    def walk(items):
        for item in items:
            yield item
            yield from walk(item.get("components", []))
            accessory = item.get("accessory")
            if accessory:
                yield accessory

    return "".join(
        component.get("content", "") for component in walk(view.to_components())
    )
