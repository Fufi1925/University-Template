"""Die kleinen Hilfsfunktionen, die überall benutzt werden.

Einzeln unscheinbar, aber sie tragen das Erscheinungsbild und ein paar
Zusagen des Projekts:

* ``small_caps`` erzeugt die Typografie, an der die gesamte Oberfläche hängt —
  inklusive der Umlaut-Faltung, ohne die Kanalnamen optisch zerbrechen.
* ``components`` baut die Bausteine, aus denen jede Ansicht besteht.
* ``content`` entscheidet, welcher Kanal überhaupt eine Startnachricht bekommt.
* ``handshake`` liefert das Alter eines Tokens und den Umgang mit
  unbrauchbaren Feldern.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.handshake import Handoff, read_state, sign_state
from core.small_caps import (
    category_name,
    channel_name,
    from_small_caps,
    is_small_caps,
    role_name,
    slugify,
    strip_decoration,
    to_small_caps,
)


def rendered(view_or_item) -> str:
    """Textinhalt einer View oder eines einzelnen Bausteins."""

    if hasattr(view_or_item, "to_components"):
        payload = view_or_item.to_components()
    else:
        payload = [view_or_item.to_component_dict()]

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

    walk(payload)
    return "\n".join(out)


# --------------------------------------------------------------------------- #
# Small Caps
# --------------------------------------------------------------------------- #

class TestSmallCaps:
    def test_letters_are_converted(self):
        assert to_small_caps("abc") == "ᴀʙᴄ"

    def test_conversion_is_reversible(self):
        assert from_small_caps(to_small_caps("hallo welt")) == "hallo welt"

    def test_x_keeps_its_plain_form(self):
        """Unicode hat kein Small-Cap-x — dokumentierte Ausnahme."""

        assert to_small_caps("x") == "x"

    def test_digits_are_left_alone(self):
        assert to_small_caps("kanal 42") == "ᴋᴀɴᴀʟ 42"

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")],
    )
    def test_umlauts_are_folded(self, raw, expected):
        """Unicode kennt keine Small-Caps-Umlaute — sonst bricht die Zeile."""

        assert to_small_caps(raw) == to_small_caps(expected)

    def test_accents_are_folded_too(self):
        assert to_small_caps("café") == to_small_caps("cafe")

    def test_is_small_caps_detects_converted_text(self):
        assert is_small_caps(to_small_caps("test"))

    def test_is_small_caps_rejects_plain_text(self):
        assert not is_small_caps("test")

    def test_empty_string_is_not_small_caps(self):
        assert not is_small_caps("")

    def test_channel_names_carry_emoji_and_separator(self):
        name = channel_name("allgemein", "💬")

        assert name.startswith("💬")
        assert "・" in name
        assert is_small_caps(name)

    def test_channel_name_without_emoji(self):
        assert "・" not in channel_name("allgemein", "")

    def test_category_names_are_converted(self):
        assert is_small_caps(category_name("willkommen", "🚪"))

    def test_role_names_keep_normal_case(self):
        """Rollennamen werden von Discord nicht kleingeschrieben."""

        name = role_name("Moderator", "🛡️")

        assert "Moderator" in name

    def test_strip_decoration_recovers_the_plain_name(self):
        assert strip_decoration(channel_name("allgemein", "💬")) == "allgemein"

    def test_strip_decoration_leaves_plain_names_alone(self):
        assert strip_decoration("allgemein") == "allgemein"

    def test_slugify_produces_a_discord_safe_name(self):
        slug = slugify("Hallo Welt! Ärger?")

        assert " " not in slug
        assert slug == slug.lower()

    def test_round_trip_through_a_channel_name(self):
        """Der Weg, den der Builder beim Wiederfinden geht."""

        for label in ("allgemein", "ankuendigungen", "memes"):
            assert strip_decoration(channel_name(label, "📢")) == label

    def test_strip_decoration_normalises_separators(self):
        """Bindestriche werden zu Leerzeichen — der Builder vergleicht so.

        Dadurch findet er einen Kanal auch wieder, wenn jemand ``team-chat``
        in ``team chat`` umbenannt hat.
        """

        assert strip_decoration(channel_name("team-chat", "🛡️")) == "team chat"


# --------------------------------------------------------------------------- #
# Components
# --------------------------------------------------------------------------- #

class TestComponents:
    def test_heading_uses_the_requested_level(self):
        from ui.components import heading

        assert rendered(heading("Titel", level=3)).startswith("### ")

    def test_heading_adds_a_grey_subtitle(self):
        from ui.components import heading

        text = rendered(heading("Titel", "Unterzeile"))

        assert "## Titel" in text
        assert "-# Unterzeile" in text

    def test_heading_without_subtitle_stays_single_line(self):
        from ui.components import heading

        assert "-#" not in rendered(heading("Titel"))

    def test_no_h1_headings(self):
        """Layout-Regel des Projekts: H1 ist der Oberflaeche zu laut."""

        from ui.components import heading

        assert not rendered(heading("Titel")).startswith("# ")

    def test_quote_prefixes_every_line(self):
        from ui.components import quote

        text = quote("eins", "zwei")

        assert all(line.startswith(">") for line in text.splitlines())

    def test_quote_keeps_empty_lines_inside_the_block(self):
        """Discord bricht ein Blockzitat bei einer echten Leerzeile ab."""

        from ui.components import quote

        lines = quote("oben", "", "unten").splitlines()

        assert lines[1] == ">"

    def test_progress_bar_reaches_both_ends(self):
        from ui.components import progress_bar

        assert "0%" in progress_bar(0, 10)
        assert "100%" in progress_bar(10, 10)

    def test_progress_bar_survives_a_zero_total(self):
        """Eine Vorlage ohne Schritte darf nicht durch Null teilen."""

        from ui.components import progress_bar

        assert "0%" in progress_bar(0, 0)

    def test_notice_carries_title_body_and_hint(self):
        from ui.components import notice

        text = rendered(notice("Titel", "Nachricht", hint="Hinweis"))

        assert "Titel" in text
        assert "Nachricht" in text
        assert "-# Hinweis" in text

    def test_notice_accepts_extra_items(self):
        """Der Pfad, ueber den Buttons an eine Meldung kommen."""

        import discord
        from discord import ui

        from ui.components import notice

        row = ui.ActionRow()
        row.add_item(
            ui.Button(label="Weiter", style=discord.ButtonStyle.primary)
        )

        text = rendered(notice("Titel", "Text", extra=[row]))

        assert "Titel" in text

    @pytest.mark.parametrize(
        "tone", ["info", "success", "error", "premium", "neutral"]
    )
    def test_every_tone_renders(self, tone):
        from ui.components import notice

        assert rendered(notice("T", "B", tone=tone))

    def test_field_value_reads_a_text_input(self):
        from ui.components import field_value

        class Component:
            value = "  Eingabe  "

        class Label:
            component = Component()

        assert field_value(Label()) == "  Eingabe  "

    def test_field_value_turns_none_into_an_empty_string(self):
        """Ein leeres optionales Feld liefert None statt ''."""

        from ui.components import field_value

        class Component:
            value = None

        class Label:
            component = Component()

        assert field_value(Label()) == ""


# --------------------------------------------------------------------------- #
# Content
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="module")
def channels():
    import config
    from core.registry import TemplateRegistry

    registry = TemplateRegistry(config.TEMPLATE_DIR).load()
    return [c for t in registry for _, c in t.iter_channels()]


class TestContentDecisions:
    def test_counting_channels_are_seeded_with_one(self, channels):
        """Ohne die erste Zahl wuesste niemand, wo die Reihe beginnt.

        Der Startwert steht nicht im Template, sondern kommt aus dem Modus —
        so verhaelt sich jeder Zaehlkanal in jeder Vorlage gleich.
        """

        from core.content import seed_message
        from core.schema import ChannelMode

        counting = [c for c in channels if c.mode is ChannelMode.COUNTING]
        assert counting, "Keine Zaehlkanaele in den Vorlagen"

        for channel in counting:
            assert seed_message(channel) == "1", f"{channel.label}: falscher Start"

    def test_ordinary_channels_get_no_seed(self, channels):
        """Nur der Zaehlkanal braucht einen Startwert."""

        from core.content import seed_message
        from core.schema import ChannelMode

        for channel in channels:
            if channel.mode is not ChannelMode.COUNTING and not channel.seed:
                assert seed_message(channel) is None

    def test_voice_channels_never_want_a_message(self, channels):
        for channel in channels:
            if channel.kind.is_voice_like:
                assert not channel.wants_message


# --------------------------------------------------------------------------- #
# Handshake
# --------------------------------------------------------------------------- #

class TestHandoffDetails:
    def test_age_grows_with_time(self, monkeypatch):
        handoff = Handoff(
            guild_id=1,
            user_id=2,
            issued_at=int(time.time()) - 30,
            source="university-bot",
        )

        assert 25 <= handoff.age <= 35

    def test_a_fresh_token_is_almost_new(self):
        handoff = Handoff(
            guild_id=1, user_id=2, issued_at=int(time.time()), source="university-bot"
        )

        assert handoff.age < 2

    def test_non_string_guild_name_is_dropped(self, monkeypatch):
        """Der Partner koennte irgendetwas in das Feld schreiben."""

        monkeypatch.setenv("PARTNER_HANDSHAKE_SECRET", "test-secret-lang-genug-1234")

        import base64
        import hashlib
        import hmac
        import json

        payload = {
            "g": "1",
            "u": "2",
            "t": int(time.time()),
            "src": "university-bot",
            "guild_name": {"kein": "string"},
        }
        body = (
            base64.urlsafe_b64encode(json.dumps(payload).encode())
            .decode()
            .rstrip("=")
        )
        signature = (
            base64.urlsafe_b64encode(
                hmac.new(
                    b"test-secret-lang-genug-1234", body.encode(), hashlib.sha256
                ).digest()
            )
            .decode()
            .rstrip("=")
        )

        handoff = read_state(f"{body}.{signature}")

        assert handoff is not None
        assert handoff.guild_name is None, "Unbrauchbares Feld wurde uebernommen"

    def test_sign_and_read_round_trip(self, monkeypatch):
        monkeypatch.setenv("PARTNER_HANDSHAKE_SECRET", "test-secret-lang-genug-1234")

        token = sign_state(123, 456, guild_name="Testserver")
        handoff = read_state(token)

        assert handoff is not None
        assert handoff.guild_id == 123
        assert handoff.user_id == 456
        assert handoff.guild_name == "Testserver"
