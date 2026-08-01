"""Die eigenen App-Emojis.

Warum es dieses Modul ueberhaupt gibt: App-Emojis gehoeren genau einer
Anwendung. Discord schreibt dazu

    "An application can own up to 2000 emojis that can only be used by
     that app."

Die Emojis des University Bots lassen sich hier also *nicht* einsetzen.
Ein ``<:zbot:1530375453142159521>`` aus dessen App erscheint bei uns als
roher Text mitten im Satz -- derselbe Fehler, der dort schon einmal live
war, als vier Emojis auf geloeschte IDs zeigten.

Deshalb kopiert ``tools/sync_emojis.py`` die Bilder unter eigene IDs.
Bis das gelaufen ist, ist ``EMOJIS`` leer, und alles faellt auf Unicode
zurueck. Genau dieser Zustand wird hier geprueft: er muss unauffaellig
funktionieren, nicht scheitern.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from ui import emojis as emoji_module
from ui.emojis import EMOJIS, button_emoji, emoji

SOURCE = BASE_DIR / "tools" / "emoji_source.json"


class TestFallback:
    """Ohne uebertragene Emojis muss alles normal aussehen."""

    def test_a_missing_emoji_returns_the_fallback(self):
        assert emoji("gibtesnicht", "💎") == "💎"

    def test_without_a_fallback_nothing_is_left(self):
        # Lieber nichts als ein roher <:name:123>-Platzhalter im Text.
        assert emoji("gibtesnicht") == ""

    def test_it_never_raises(self):
        for name in ("", "  ", "?!", "a" * 200, "123"):
            assert isinstance(emoji(name, "x"), str)

    def test_a_present_emoji_wins_over_the_fallback(self, monkeypatch):
        monkeypatch.setitem(EMOJIS, "zbot", "<:zbot:999>")
        assert emoji("zbot", "🤖") == "<:zbot:999>"


class TestButtonEmoji:
    """
    Knoepfe vertragen kein leeres Emoji.

    discord.py baut daraus klaglos ein PartialEmoji mit leerem Namen;
    Discord lehnt die Komponente dann beim Senden ab. Das faellt sonst
    erst live auf.
    """

    def test_it_uses_the_fallback_when_nothing_is_uploaded(self):
        assert button_emoji("gibtesnicht", "💎") == "💎"

    def test_an_empty_fallback_is_refused(self):
        with pytest.raises(ValueError):
            button_emoji("gibtesnicht", "")

    def test_a_present_emoji_wins(self, monkeypatch):
        monkeypatch.setitem(EMOJIS, "premium", "<a:premium:42>")
        assert button_emoji("premium", "💎") == "<a:premium:42>"

    def test_the_result_is_never_empty(self, monkeypatch):
        # Auch wenn jemand einen leeren Eintrag hineinschreibt, darf
        # nichts Leeres herauskommen.
        monkeypatch.setitem(EMOJIS, "kaputt", "")
        assert button_emoji("kaputt", "💎") == "💎"


class TestSourceList:
    """Die Vorlage, aus der uebertragen wird."""

    def test_the_source_exists(self):
        assert SOURCE.exists(), "tools/emoji_source.json fehlt"

    def test_every_entry_is_usable(self):
        data = json.loads(SOURCE.read_text(encoding="utf-8"))
        assert data, "die Liste ist leer"

        for entry in data:
            name = entry.get("name", "")
            # Discord lehnt den ganzen Upload mit 400 ab, wenn ein Name
            # nicht passt -- lieber hier auffallen als mitten im Lauf.
            assert re.fullmatch(r"[A-Za-z0-9_]{2,32}", name), f"Name: {name!r}"
            assert str(entry.get("id", "")).isdigit(), f"ID bei {name}"
            assert isinstance(entry.get("animated"), bool), f"animated bei {name}"

    def test_names_are_unique(self):
        data = json.loads(SOURCE.read_text(encoding="utf-8"))
        names = [e["name"] for e in data]
        # Discord lehnt einen doppelten Namen ab; ein Duplikat in der
        # Liste haette also mitten im Lauf einen Fehlschlag erzeugt.
        assert len(names) == len(set(names)), "doppelte Namen in der Liste"


class TestUsage:
    """Die Stellen, die Emojis tatsaechlich benutzen."""

    @staticmethod
    def _read(name: str) -> str:
        text = (BASE_DIR / "ui" / name).read_text(encoding="utf-8")
        # Blockkommentare raus: die erklaeren genau das, was hier
        # geprueft wird, und wuerden jede Suche bestehen lassen.
        text = re.sub(r'"""_.*?"""', "", text, flags=re.DOTALL)
        return "\n".join(
            line for line in text.splitlines() if not line.lstrip().startswith("#")
        )

    def test_buttons_use_the_helper(self):
        views = self._read("views.py")
        assert 'button_emoji("premium"' in views
        assert 'button_emoji("RedRulesBook"' in views

    def test_no_hardcoded_foreign_ids(self):
        """
        Eine fest eingetragene Emoji-ID aus einer anderen App wuerde als
        Text erscheinen. Das ist der Fehler, den dieses Modul verhindert.
        """

        for name in ("views.py", "rules.py", "widgets.py", "components.py"):
            body = self._read(name)
            found = re.findall(r"<a?:\w+:\d+>", body)
            assert not found, f"{name} enthaelt feste Emoji-IDs: {found}"

    def test_every_button_emoji_has_a_fallback(self):
        """Ohne Rueckfall waere der Knopf leer, sobald nichts uebertragen ist."""

        for name in ("views.py", "rules.py"):
            body = self._read(name)
            for call in re.findall(r"button_emoji\(([^)]*)\)", body):
                assert "," in call, f"{name}: button_emoji({call}) ohne Rueckfall"


class TestStartupNotice:
    def test_has_emojis_reports_the_truth(self, monkeypatch):
        monkeypatch.setattr(emoji_module, "EMOJIS", {})
        assert emoji_module.has_emojis() is False

        monkeypatch.setattr(emoji_module, "EMOJIS", {"zbot": "<:zbot:1>"})
        assert emoji_module.has_emojis() is True

    def test_the_bot_says_which_case_applies(self):
        body = (BASE_DIR / "bot.py").read_text(encoding="utf-8")
        assert "has_emojis" in body, (
            "der Start sagt nicht, ob Emojis uebertragen wurden"
        )
        assert "sync_emojis" in body, "der Hinweis nennt das Werkzeug nicht"
