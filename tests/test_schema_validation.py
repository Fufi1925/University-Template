"""Was passiert, wenn eine Vorlage fehlerhaft ist.

``Template.parse`` ist die Eingangskontrolle des Projekts. Sie laeuft beim
Start, und ihre Zusage ist deutlich: **eine kaputte Vorlage bricht den Start
ab, statt mitten im Umbau eines fremden Servers aufzufallen.**

Damit diese Zusage etwas wert ist, muss zweierlei stimmen: es darf nichts
durchrutschen, und die Meldung muss sagen, wo der Fehler steckt. Bei zehn
Dateien mit zusammen 886 Kanaelen ist ein blankes ``ValueError`` wertlos.

Geprueft wird jeder Validierungszweig einzeln, jeweils an einer sonst
gueltigen Vorlage — so steht im Fehlerfall fest, welche Regel gegriffen hat.
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path
from typing import Any

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.schema import (
    ChannelKind,
    ChannelMode,
    RoleTier,
    Template,
    TemplateError,
    Visibility,
)


def minimal() -> dict[str, Any]:
    """Die kleinstmoegliche gueltige Vorlage."""

    return {
        "key": "test",
        "name": "Test",
        "emoji": "🧪",
        "tagline": "Zum Pruefen",
        "premium": False,
        "categories": [
            {
                "label": "allgemein",
                "emoji": "💬",
                "visibility": "public",
                "channels": [{"label": "chat", "emoji": "💬"}],
            }
        ],
    }


def parse(data: dict[str, Any]) -> Template:
    return Template.parse(data, source="test.json")


def broken(**changes: Any) -> dict[str, Any]:
    data = minimal()
    data.update(changes)
    return data


def with_channel(**channel_changes: Any) -> dict[str, Any]:
    data = copy.deepcopy(minimal())
    data["categories"][0]["channels"][0].update(channel_changes)
    return data


def with_category(**category_changes: Any) -> dict[str, Any]:
    data = copy.deepcopy(minimal())
    data["categories"][0].update(category_changes)
    return data


# --------------------------------------------------------------------------- #
# Grundgeruest
# --------------------------------------------------------------------------- #

class TestMinimalTemplate:
    def test_the_baseline_is_valid(self):
        """Sonst prueften alle folgenden Tests am falschen Objekt."""

        template = parse(minimal())

        assert template.key == "test"
        assert template.channel_count == 1

    def test_a_non_object_is_rejected(self):
        with pytest.raises(TemplateError):
            Template.parse(["keine", "vorlage"], source="test.json")

    @pytest.mark.parametrize("field", ["key", "name", "categories"])
    def test_required_fields(self, field):
        data = minimal()
        del data[field]

        with pytest.raises(TemplateError) as excinfo:
            parse(data)

        assert field in str(excinfo.value) or "test.json" in str(excinfo.value)

    def test_empty_categories_are_rejected(self):
        """Eine Vorlage ohne Kategorien wuerde nichts bauen."""

        with pytest.raises(TemplateError):
            parse(broken(categories=[]))

    def test_categories_must_be_a_list(self):
        with pytest.raises(TemplateError) as excinfo:
            parse(broken(categories={"nicht": "liste"}))

        assert "test.json" in str(excinfo.value)

    def test_channels_must_be_a_list(self):
        """Ein String ist iterierbar — deshalb landet er in der Kanalpruefung."""

        with pytest.raises(TemplateError) as excinfo:
            parse(with_category(channels="kein array"))

        message = str(excinfo.value)
        assert "Kategorie #1" in message, "Die Meldung lokalisiert den Fehler nicht"

    def test_error_messages_locate_the_problem(self):
        """Bei zehn Dateien mit 886 Kanaelen ist das der halbe Wert der Pruefung."""

        data = copy.deepcopy(minimal())
        data["categories"][0]["channels"].append({"emoji": "❓"})  # ohne label

        with pytest.raises(TemplateError) as excinfo:
            parse(data)

        message = str(excinfo.value)
        assert "test.json" in message, "Der Dateiname fehlt"
        assert "Kanal #2" in message, "Die Position fehlt"
        assert "label" in message, "Das fehlende Feld wird nicht benannt"


# --------------------------------------------------------------------------- #
# Enums
# --------------------------------------------------------------------------- #

class TestEnumValues:
    """Ein Tippfehler in einem Enum-Wert muss beim Start auffallen."""

    def test_unknown_visibility(self):
        with pytest.raises(TemplateError) as excinfo:
            parse(with_category(visibility="halboeffentlich"))

        assert "halboeffentlich" in str(excinfo.value)

    def test_unknown_channel_kind(self):
        with pytest.raises(TemplateError) as excinfo:
            parse(with_channel(kind="hologramm"))

        assert "hologramm" in str(excinfo.value)

    def test_unknown_mode(self):
        with pytest.raises(TemplateError) as excinfo:
            parse(with_channel(mode="streng"))

        assert "streng" in str(excinfo.value)

    def test_unknown_widget(self):
        with pytest.raises(TemplateError) as excinfo:
            parse(with_channel(widget="zauberstab"))

        assert "zauberstab" in str(excinfo.value)

    def test_unknown_role_tier(self):
        data = minimal()
        data["roles"] = [{"key": "x", "label": "X", "tier": "halbgott"}]

        with pytest.raises(TemplateError) as excinfo:
            parse(data)

        assert "halbgott" in str(excinfo.value)

    @pytest.mark.parametrize("value", [v.value for v in Visibility])
    def test_every_documented_visibility_parses(self, value):
        parse(with_category(visibility=value))

    @pytest.mark.parametrize("value", [k.value for k in ChannelKind])
    def test_every_documented_kind_parses(self, value):
        data = with_channel(kind=value)
        # Modi gelten nur fuer Textkanaele — hier keinen setzen.
        parse(data)


# --------------------------------------------------------------------------- #
# Regeln zwischen Feldern
# --------------------------------------------------------------------------- #

class TestCrossFieldRules:
    def test_mode_on_a_voice_channel_is_rejected(self):
        """Ein Sprachkanal kann keine Bildpflicht durchsetzen."""

        with pytest.raises(TemplateError) as excinfo:
            parse(with_channel(kind="voice", mode="media"))

        assert "Textkanäle" in str(excinfo.value)

    @pytest.mark.parametrize("limit", [-1, 100, 999])
    def test_user_limit_out_of_range(self, limit):
        """Discord erlaubt 0 bis 99."""

        with pytest.raises(TemplateError) as excinfo:
            parse(with_channel(kind="voice", user_limit=limit))

        assert "user_limit" in str(excinfo.value)

    @pytest.mark.parametrize("limit", [0, 1, 99])
    def test_user_limit_within_range(self, limit):
        parse(with_channel(kind="voice", user_limit=limit))

    def test_duplicate_category_names_are_rejected(self):
        """Zwei gleich benannte Kategorien waeren nicht unterscheidbar."""

        data = copy.deepcopy(minimal())
        data["categories"].append(copy.deepcopy(data["categories"][0]))

        with pytest.raises(TemplateError) as excinfo:
            parse(data)

        assert "doppelt" in str(excinfo.value)

    def test_duplicate_channel_names_are_rejected(self):
        data = copy.deepcopy(minimal())
        channels = data["categories"][0]["channels"]
        channels.append(copy.deepcopy(channels[0]))

        with pytest.raises(TemplateError):
            parse(data)


# --------------------------------------------------------------------------- #
# Abgeleitete Werte
# --------------------------------------------------------------------------- #

class TestDerivedValues:
    def test_counts_add_up(self):
        data = copy.deepcopy(minimal())
        data["categories"][0]["channels"].extend(
            [
                {"label": "talk", "emoji": "🔊", "kind": "voice"},
                {"label": "musik", "emoji": "🎵", "kind": "voice"},
            ]
        )

        template = parse(data)

        assert template.category_count == 1
        assert template.channel_count == 3
        assert template.voice_count == 2

    def test_iter_channels_visits_everything(self):
        template = parse(minimal())

        pairs = list(template.iter_channels())
        assert len(pairs) == template.channel_count

    def test_display_names_are_small_caps(self):
        """Die Typografie ist Teil des Datenmodells, nicht der Anzeige."""

        template = parse(minimal())
        channel = next(c for _, c in template.iter_channels())

        assert channel.display_name != "chat"
        assert "ᴄʜᴀᴛ" in channel.display_name

    def test_colour_accepts_hex_strings(self):
        data = minimal()
        data["roles"] = [
            {"key": "x", "label": "X", "tier": "member", "colour": "#FF00AA"}
        ]

        template = parse(data)

        assert template.roles[0].colour == 0xFF00AA

    def test_invalid_colour_is_rejected(self):
        data = minimal()
        data["roles"] = [
            {"key": "x", "label": "X", "tier": "member", "colour": "knallrot"}
        ]

        with pytest.raises(TemplateError):
            parse(data)

    def test_staff_flag_follows_the_tier(self):
        assert RoleTier.MODERATOR.is_staff
        assert not RoleTier.MEMBER.is_staff
        assert RoleTier.OWNER.is_leadership

    def test_enforced_modes_are_marked(self):
        """Nur diese beiden brauchen einen Listener auf on_message."""

        assert ChannelMode.MEDIA.is_enforced
        assert ChannelMode.COUNTING.is_enforced
        assert not ChannelMode.FREE.is_enforced
        assert not ChannelMode.ANNOUNCE.is_enforced


# --------------------------------------------------------------------------- #
# Die echten Vorlagen
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="module")
def templates():
    import config
    from core.registry import TemplateRegistry

    return TemplateRegistry(config.TEMPLATE_DIR).load().all


class TestShippedTemplatesAreSound:
    """Was ausgeliefert wird, muss die eigenen Regeln einhalten."""

    def test_no_voice_channel_carries_a_mode(self, templates):
        for template in templates:
            for _, channel in template.iter_channels():
                if channel.kind.is_voice_like:
                    assert channel.mode is ChannelMode.FREE, (
                        f"{template.key}: {channel.label} ist Voice mit Modus"
                    )

    def test_every_user_limit_is_valid(self, templates):
        for template in templates:
            for _, channel in template.iter_channels():
                assert 0 <= channel.user_limit <= 99

    def test_category_names_are_unique_per_template(self, templates):
        for template in templates:
            names = [c.display_name for c in template.categories]
            assert len(names) == len(set(names)), f"{template.key}: doppelte Kategorie"
