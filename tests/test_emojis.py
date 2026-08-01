"""Die eigenen App-Emojis.

Warum es dieses Modul ueberhaupt gibt: App-Emojis gehoeren genau einer
Anwendung. Discord schreibt dazu

    "An application can own up to 2000 emojis that can only be used by
     that app."

Die Emojis des University Bots lassen sich hier also *nicht* einsetzen.
Ein ``<:zbot:1530375453142159521>`` aus dessen App erscheint bei uns als
roher Text mitten im Satz -- derselbe Fehler, der dort schon einmal live
war, als vier Emojis auf geloeschte IDs zeigten.

Deshalb legt ``core.emoji_sync`` sie beim Start unter dieser App an.
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
        assert "EMOJI_SYNC" in body, "der Hinweis nennt die Variable nicht"


class TestAutomaticSync:
    """
    Der Abgleich laeuft beim Start, nicht von Hand.

    Zwei Dinge duerfen dabei nicht schiefgehen: er muss *vor* den
    persistenten Views laufen, und er darf den Start nie kippen.
    """

    def test_it_runs_before_the_persistent_views(self):
        """
        Die angehefteten Views bauen ihre Buttons beim Erzeugen, und
        button_emoji() liest die Tabelle in genau diesem Moment. Laeuft
        der Sync danach, haben diese Nachrichten fuer immer die
        Unicode-Rueckfaelle -- sie werden nie neu gebaut.
        """

        body = (BASE_DIR / "bot.py").read_text(encoding="utf-8")
        setup = body[body.index("async def setup_hook"):]
        setup = setup[: setup.index("async def ", 10)]

        assert "sync_emojis" in setup, "der Sync laeuft nicht im setup_hook"
        assert setup.index("sync_emojis") < setup.index("PERSISTENT_VIEWS"), (
            "der Sync laeuft nach den Views -- die Buttons blieben Unicode"
        )

    def test_the_result_is_loaded(self):
        body = (BASE_DIR / "bot.py").read_text(encoding="utf-8")
        assert "load_emojis" in body, "das Ergebnis wird nirgends uebernommen"

    def test_the_variable_controls_it(self):
        config_body = (BASE_DIR / "config.py").read_text(encoding="utf-8")
        assert "EMOJI_SYNC" in config_body
        bot_body = (BASE_DIR / "bot.py").read_text(encoding="utf-8")
        assert "config.EMOJI_SYNC" in bot_body, (
            "die Variable wird gelesen, aber nicht benutzt"
        )

    async def test_disabled_makes_no_requests(self, monkeypatch):
        from core import emoji_sync

        called = []
        monkeypatch.setattr(
            emoji_sync.aiohttp, "ClientSession",
            lambda *a, **k: called.append(1),
        )

        result = await emoji_sync.sync_emojis("token", enabled=False)

        assert result == {}
        assert not called, "EMOJI_SYNC=false hat trotzdem angefragt"

    async def test_without_a_token_nothing_happens(self, monkeypatch):
        from core import emoji_sync

        called = []
        monkeypatch.setattr(
            emoji_sync.aiohttp, "ClientSession",
            lambda *a, **k: called.append(1),
        )

        assert await emoji_sync.sync_emojis("", enabled=True) == {}
        assert not called

    async def test_a_network_failure_does_not_raise(self, monkeypatch):
        """Ein Emoji ist Zierde. Daran darf kein Start scheitern."""

        from core import emoji_sync

        def boom(*args, **kwargs):
            raise OSError("kein Netz")

        monkeypatch.setattr(emoji_sync.aiohttp, "ClientSession", boom)

        # Kein pytest.raises: der Punkt ist, dass es *nicht* wirft.
        assert await emoji_sync.sync_emojis("token", enabled=True) == {}

    async def test_a_broken_source_is_survived(self, monkeypatch, tmp_path):
        from core import emoji_sync

        broken = tmp_path / "kaputt.json"
        broken.write_text("{ das ist kein JSON", encoding="utf-8")
        monkeypatch.setattr(emoji_sync, "SOURCE_FILE", broken)

        assert await emoji_sync.sync_emojis("token", enabled=True) == {}

    async def test_an_oversized_source_is_refused(self, monkeypatch, tmp_path):
        """Eine kaputte Quelle darf keine tausend Uploads ausloesen."""

        from core import emoji_sync

        huge = tmp_path / "viele.json"
        huge.write_text(
            json.dumps([
                {"name": f"emoji_{i}", "id": str(1000 + i), "animated": False}
                for i in range(emoji_sync.MAX_UPLOADS + 1)
            ]),
            encoding="utf-8",
        )
        monkeypatch.setattr(emoji_sync, "SOURCE_FILE", huge)

        called = []
        monkeypatch.setattr(
            emoji_sync.aiohttp, "ClientSession",
            lambda *a, **k: called.append(1),
        )

        assert await emoji_sync.sync_emojis("token", enabled=True) == {}
        assert not called, "es wurde trotz Ueberschreitung angefragt"
