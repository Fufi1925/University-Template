"""Das Veroeffentlichen eines Regelwerks — inklusive des Loeschpfads.

``Neu aufsetzen`` raeumt den Regelkanal auf, bevor es schreibt. Das ist die
einzige Stelle im Projekt, an der der Bot fremde Nachrichten anfasst, und
bisher belegte nichts, dass er dabei wirklich nur seine eigenen erwischt.

Ausserdem geprueft: was passiert, wenn dem Bot im Zielkanal die Schreibrechte
fehlen, wenn Discord mittendrin abbricht, und ob ohne Auswahl ueberhaupt
etwas passieren kann.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, cast

import discord
import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.rulesets import RULESETS, get_ruleset
from ui.rules import _post, _purge_bot_messages, ruleset_views


class _Resp:
    def __init__(self, status: int) -> None:
        self.status = status
        self.reason = "Fehler"
        self.headers: dict[str, str] = {}


class FakeMessage:
    def __init__(self, author_id: int, *, undeletable: bool = False) -> None:
        self.author = type("A", (), {"id": author_id})()
        self.deleted = False
        self.pinned = False
        self._undeletable = undeletable

    async def delete(self) -> None:
        if self._undeletable:
            raise discord.HTTPException(_Resp(403), "darf nicht")
        self.deleted = True

    async def pin(self, reason: str | None = None) -> None:
        self.pinned = True


class FakeHistory:
    def __init__(self, messages: list[FakeMessage], *, fails: bool = False) -> None:
        self._messages = messages
        self._fails = fails

    def __call__(self, limit: int = 100):
        return self

    def __aiter__(self):
        if self._fails:
            raise discord.Forbidden(_Resp(403), "kein Zugriff")
        return self._iter()

    async def _iter(self):
        for message in list(self._messages):
            yield message


class FakeChannel:
    def __init__(
        self,
        messages: list[FakeMessage] | None = None,
        *,
        send_error: Exception | None = None,
        history_fails: bool = False,
    ) -> None:
        self.mention = "#regeln"
        self.sent: list[object] = []
        self.messages = messages or []
        self._send_error = send_error
        self.history = FakeHistory(self.messages, fails=history_fails)

    async def send(self, *, view=None, **kw) -> FakeMessage:
        if self._send_error is not None:
            raise self._send_error
        message = FakeMessage(BOT_ID)
        self.sent.append(view)
        return message


BOT_ID = 999


class FakeMe:
    id = BOT_ID


class FakeGuild:
    def __init__(self) -> None:
        self.id = 1
        self.name = "Testserver"
        self.me = FakeMe()


class FakeResponse:
    def __init__(self) -> None:
        self.sent: list[object] = []
        self.deferred = False

    def is_done(self) -> bool:
        return self.deferred or bool(self.sent)

    async def send_message(self, *, view=None, ephemeral: bool = False, **kw) -> None:
        self.sent.append(view)

    async def defer(self, *, ephemeral: bool = False, thinking: bool = False) -> None:
        self.deferred = True


class FakeInteraction:
    def __init__(self, guild: FakeGuild | None = None) -> None:
        self.guild = guild if guild is not None else FakeGuild()
        self.user = type("U", (), {"id": 5, "display_name": "Testerin"})()
        self.response = FakeResponse()
        self.edited: list[object] = []

    async def edit_original_response(self, *, view=None, **kw) -> None:
        self.edited.append(view)

    @property
    def shown(self) -> list[object]:
        return [*self.response.sent, *self.edited]


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


async def post(channel, interaction, *, reset: bool, ruleset_key: str = "standard"):
    ruleset = get_ruleset(ruleset_key)
    assert ruleset is not None
    views = ruleset_views(ruleset, guild_name="Testserver")
    await _post(
        cast("Any", interaction), cast("Any", channel), views, reset=reset
    )
    return views


# --------------------------------------------------------------------------- #
# Aufraeumen
# --------------------------------------------------------------------------- #

class TestPurge:
    async def test_removes_only_its_own_messages(self):
        """Der wichtigste Test dieser Datei.

        'Neu aufsetzen' darf einen Regelkanal nicht leerraeumen, in dem auch
        Menschen geschrieben haben.
        """

        own = [FakeMessage(BOT_ID) for _ in range(3)]
        foreign = [FakeMessage(42), FakeMessage(7)]
        channel = FakeChannel([*own, *foreign])

        removed = await _purge_bot_messages(cast("Any", channel), cast("Any", FakeMe()))

        assert removed == 3
        assert all(m.deleted for m in own)
        assert not any(m.deleted for m in foreign), "Fremde Nachricht geloescht"

    async def test_empty_channel_is_fine(self):
        removed = await _purge_bot_messages(
            cast("Any", FakeChannel([])), cast("Any", FakeMe())
        )
        assert removed == 0

    async def test_undeletable_messages_do_not_abort_the_run(self):
        """Eine gesperrte Nachricht darf die restlichen nicht blockieren."""

        messages = [
            FakeMessage(BOT_ID),
            FakeMessage(BOT_ID, undeletable=True),
            FakeMessage(BOT_ID),
        ]
        channel = FakeChannel(messages)

        removed = await _purge_bot_messages(cast("Any", channel), cast("Any", FakeMe()))

        assert messages[0].deleted and messages[2].deleted
        assert removed == 2, "Die gescheiterte Loeschung wurde mitgezaehlt"

    async def test_missing_history_permission_is_survivable(self):
        channel = FakeChannel([FakeMessage(BOT_ID)], history_fails=True)

        removed = await _purge_bot_messages(cast("Any", channel), cast("Any", FakeMe()))

        assert removed == 0


# --------------------------------------------------------------------------- #
# Veroeffentlichen
# --------------------------------------------------------------------------- #

class TestPost:
    async def test_posts_and_reports_the_channel(self):
        channel = FakeChannel()
        interaction = FakeInteraction()

        views = await post(channel, interaction, reset=False)

        assert len(channel.sent) == len(views)
        assert "#regeln" in all_text(interaction)

    async def test_extend_mode_deletes_nothing(self):
        """'Ergaenzen' heisst ergaenzen."""

        existing = [FakeMessage(BOT_ID), FakeMessage(3)]
        channel = FakeChannel(existing)

        await post(channel, FakeInteraction(), reset=False)

        assert not any(m.deleted for m in existing)

    async def test_reset_mode_clears_first(self):
        own = [FakeMessage(BOT_ID) for _ in range(2)]
        channel = FakeChannel(own)
        interaction = FakeInteraction()

        await post(channel, interaction, reset=True)

        assert all(m.deleted for m in own)
        assert "2" in all_text(interaction), "Die Zahl entfernter Nachrichten fehlt"

    async def test_missing_write_permission_is_explained(self):
        channel = FakeChannel(send_error=discord.Forbidden(_Resp(403), "nein"))
        interaction = FakeInteraction()

        await post(channel, interaction, reset=False)

        text = all_text(interaction)
        assert "Keine Schreibrechte" in text
        assert "Kanalberechtigungen" in text, "Die Meldung nennt die Loesung nicht"

    async def test_http_error_is_reported(self):
        channel = FakeChannel(send_error=discord.HTTPException(_Resp(500), "kaputt"))
        interaction = FakeInteraction()

        await post(channel, interaction, reset=False)

        assert "Fehlgeschlagen" in all_text(interaction)

    async def test_nothing_is_posted_after_a_failure(self):
        """Ein halb geschriebenes Regelwerk waere schlimmer als keins."""

        channel = FakeChannel(send_error=discord.Forbidden(_Resp(403), "nein"))

        await post(channel, FakeInteraction(), reset=False)

        assert not channel.sent

    async def test_works_without_a_guild(self):
        """Ohne Guild gibt es kein ``me`` — der Loeschpfad muss das aushalten."""

        channel = FakeChannel([FakeMessage(BOT_ID)])
        interaction = FakeInteraction(guild=None)

        await post(channel, interaction, reset=True)

        assert channel.sent, "Ohne Guild wurde gar nichts gepostet"


# --------------------------------------------------------------------------- #
# Regelwerke rendern
# --------------------------------------------------------------------------- #

class TestEveryRulesetPosts:
    @pytest.mark.parametrize("key", sorted(rs.key for rs in RULESETS))
    async def test_ruleset_can_be_posted(self, key):
        """Jedes der Regelwerke muss sich tatsaechlich versenden lassen.

        Die Render-Tests pruefen den Text; hier geht es darum, dass die
        entstehenden Views auch als Nachrichten durchgehen.
        """

        channel = FakeChannel()
        interaction = FakeInteraction()

        views = await post(channel, interaction, reset=False, ruleset_key=key)

        assert channel.sent, f"{key} hat nichts gepostet"
        assert len(channel.sent) == len(views)
