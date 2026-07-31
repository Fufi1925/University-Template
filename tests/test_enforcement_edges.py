"""Kanal-Modi: die Faelle, in denen etwas schiefgeht.

``test_content.py`` prueft, dass die Durchsetzung im Normalfall greift. Hier
geht es um die Raender — und die sind bei diesem Modul heikler als sonst,
denn ``check_message`` **loescht Nachrichten von Menschen**.

Zwei Richtungen sind gleich wichtig:

* Es darf nichts geloescht werden, was bleiben soll (Team, Bots, unvollstaendiger
  Cache, Kanaele ohne Modus).
* Kann nicht geloescht werden, darf daraus kein Folgefehler entstehen — und
  erst recht kein Hinweis, der behauptet, es sei etwas passiert.

Der Zaehlkanal bekommt eigene Aufmerksamkeit, weil er als einziger Modus die
Kanalhistorie liest und damit von Discord-Antworten abhaengt.
"""

from __future__ import annotations

import sys
from pathlib import Path

import discord

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.enforcement import (
    HINT_SECONDS,
    apply_reactions,
    check_message,
    is_exempt,
    mode_tag,
    next_count,
    reaction_tag,
    read_mode,
    read_reactions,
    strip_tags,
)
from core.schema import ChannelMode


class _Resp:
    def __init__(self, status: int = 500) -> None:
        self.status = status
        self.reason = "Fehler"
        self.headers: dict[str, str] = {}


# --------------------------------------------------------------------------- #
# Attrappen
# --------------------------------------------------------------------------- #

class FakePerms:
    def __init__(self, manage: bool = False, admin: bool = False) -> None:
        self.manage_messages = manage
        self.administrator = admin


class FakeAuthor:
    def __init__(self, *, manage: bool = False, admin: bool = False, bot: bool = False) -> None:
        self.mention = "@tester"
        self.bot = bot
        self.guild_permissions = FakePerms(manage, admin)


class FakeChannel:
    def __init__(
        self,
        topic: str = "",
        *,
        history: list | None = None,
        history_error: Exception | None = None,
        send_error: Exception | None = None,
    ) -> None:
        self.topic = topic
        self.hints: list[tuple[str, float | None]] = []
        self._history = history or []
        self._history_error = history_error
        self._send_error = send_error

    async def send(self, content, delete_after=None):
        if self._send_error is not None:
            raise self._send_error
        self.hints.append((content, delete_after))

    def history(self, limit=None, before=None):
        error = self._history_error
        entries = list(self._history)

        async def walk():
            if error is not None:
                raise error
            for entry in entries[:limit] if limit else entries:
                yield entry

        return walk()


class FakeMessage:
    def __init__(
        self,
        channel: FakeChannel,
        content: str = "",
        *,
        author: FakeAuthor | None = None,
        attachment: bool = False,
        embed: bool = False,
        sticker: bool = False,
        delete_error: Exception | None = None,
    ) -> None:
        self.channel = channel
        self.content = content
        self.author = author or FakeAuthor()
        self.attachments = [object()] if attachment else []
        self.embeds = [object()] if embed else []
        self.stickers = [object()] if sticker else []
        self.deleted = False
        self.reactions: list[str] = []
        self._delete_error = delete_error
        #: Fehler, den ``add_reaction`` werfen soll — je Aufruf einer.
        self.reaction_errors: list[Exception | None] = []

    async def delete(self):
        if self._delete_error is not None:
            raise self._delete_error
        self.deleted = True

    async def add_reaction(self, emoji):
        if self.reaction_errors:
            error = self.reaction_errors.pop(0)
            if error is not None:
                raise error
        self.reactions.append(emoji)


def counting_channel(**kwargs) -> FakeChannel:
    return FakeChannel(f"Zaehlen {mode_tag(ChannelMode.COUNTING)}", **kwargs)


def media_channel(**kwargs) -> FakeChannel:
    return FakeChannel(f"Bilder {mode_tag(ChannelMode.MEDIA)}", **kwargs)


# --------------------------------------------------------------------------- #
# Topic-Marken
# --------------------------------------------------------------------------- #

class TestTopicMarkers:
    """Der Modus lebt im Kanal-Topic — er muss einen Neustart ueberstehen."""

    def test_unknown_mode_falls_back_to_free(self):
        """Ein Topic von Hand bearbeitet: lieber nichts durchsetzen."""

        assert read_mode(FakeChannel("[mode:erfunden]")) is ChannelMode.FREE

    def test_channel_without_topic_attribute_is_free(self):
        """Sprachkanaele und Threads haben kein ``topic``."""

        assert read_mode(object()) is ChannelMode.FREE

    def test_empty_topic_is_free(self):
        assert read_mode(FakeChannel("")) is ChannelMode.FREE

    def test_free_mode_writes_no_marker(self):
        """Sonst stuende in fast jedem Kanal eine sinnlose Marke."""

        assert mode_tag(ChannelMode.FREE) == ""

    def test_marker_survives_extra_text(self):
        channel = FakeChannel(f"Nur Bilder bitte {mode_tag(ChannelMode.MEDIA)} danke")
        assert read_mode(channel) is ChannelMode.MEDIA

    def test_reactions_are_read_back(self):
        channel = FakeChannel(f"Vorschlaege {reaction_tag(('👍', '👎'))}")
        assert read_reactions(channel) == ("👍", "👎")

    def test_no_reaction_tag_means_no_reactions(self):
        assert read_reactions(FakeChannel("Nur Text")) == ()

    def test_display_topic_hides_every_marker(self):
        """Die Marken sollen im Client nicht auffallen."""

        raw = f"Bilderkanal {mode_tag(ChannelMode.MEDIA)}{reaction_tag(('👍',))}"
        cleaned = strip_tags(raw)

        assert cleaned == "Bilderkanal"
        assert "[" not in cleaned

    def test_strip_tags_handles_none(self):
        assert strip_tags(None) == ""


# --------------------------------------------------------------------------- #
# Wer ausgenommen ist
# --------------------------------------------------------------------------- #

class TestExemptions:
    def test_team_may_write_anywhere(self):
        assert is_exempt(FakeAuthor(manage=True))

    def test_administrator_counts_as_team(self):
        assert is_exempt(FakeAuthor(admin=True))

    def test_normal_member_is_not_exempt(self):
        assert not is_exempt(FakeAuthor())

    def test_unknown_permissions_mean_exempt(self):
        """Bei unvollstaendigem Member-Cache im Zweifel nichts loeschen.

        Einem Moderator die Nachricht zu entfernen, weil der Cache leer war,
        ist deutlich schaedlicher als eine durchgerutschte Textzeile.
        """

        class CachelessUser:
            mention = "@user"
            bot = False

        assert is_exempt(CachelessUser())


# --------------------------------------------------------------------------- #
# Medienkanal
# --------------------------------------------------------------------------- #

class TestMediaMode:
    async def test_sticker_counts_as_media(self):
        message = FakeMessage(media_channel(), "", sticker=True)
        assert await check_message(message) is False
        assert not message.deleted

    async def test_link_counts_as_media(self):
        """Discord erzeugt das Embed erst verzoegert — der Text muss reichen."""

        message = FakeMessage(media_channel(), "schaut mal https://example.com/x.png")
        assert await check_message(message) is False

    async def test_plain_text_is_removed(self):
        channel = media_channel()
        message = FakeMessage(channel, "nur text")

        assert await check_message(message) is True
        assert message.deleted
        assert channel.hints, "Der Nutzer erfaehrt nicht, warum die Nachricht weg ist"

    async def test_hint_is_self_deleting(self):
        """Sonst muellt der Bot den Kanal zu, den er sauber halten soll."""

        channel = media_channel()
        await check_message(FakeMessage(channel, "nur text"))

        _, delete_after = channel.hints[0]
        assert delete_after == HINT_SECONDS

    async def test_hint_mentions_the_author(self):
        channel = media_channel()
        await check_message(FakeMessage(channel, "nur text"))

        assert "@tester" in channel.hints[0][0]


# --------------------------------------------------------------------------- #
# Zaehlkanal
# --------------------------------------------------------------------------- #

class TestCountingMode:
    async def test_correct_number_passes(self):
        previous = FakeMessage(FakeChannel(), "41")
        message = FakeMessage(counting_channel(history=[previous]), "42")

        assert await check_message(message) is False
        assert not message.deleted

    async def test_wrong_number_is_removed_with_the_expected_one(self):
        previous = FakeMessage(FakeChannel(), "41")
        channel = counting_channel(history=[previous])

        assert await check_message(FakeMessage(channel, "99")) is True
        assert "42" in channel.hints[0][0]

    async def test_empty_channel_expects_one(self):
        channel = counting_channel(history=[])

        assert await check_message(FakeMessage(channel, "1")) is False

    async def test_empty_channel_rejects_anything_else(self):
        channel = counting_channel(history=[])

        assert await check_message(FakeMessage(channel, "7")) is True
        assert "1" in channel.hints[0][0]

    async def test_bot_chatter_is_skipped_when_counting(self):
        """Der eigene Hinweis darf die Zaehlung nicht verschieben."""

        hint = FakeMessage(FakeChannel(), "@x als Nächstes kommt 42",
                           author=FakeAuthor(bot=True))
        real = FakeMessage(FakeChannel(), "41")
        channel = counting_channel(history=[hint, real])

        assert await check_message(FakeMessage(channel, "42")) is False

    async def test_a_bot_number_still_counts(self):
        """Zaehlt ein Bot mit, ist seine Zahl echter Teil der Reihe."""

        bot_number = FakeMessage(FakeChannel(), "41", author=FakeAuthor(bot=True))
        channel = counting_channel(history=[bot_number])

        assert await check_message(FakeMessage(channel, "42")) is False

    async def test_unreadable_history_falls_back_to_one(self):
        """Ohne History-Recht darf der Kanal nicht komplett blockieren."""

        channel = counting_channel(
            history_error=discord.HTTPException(_Resp(403), "kein Zugriff")
        )

        assert await check_message(FakeMessage(channel, "1")) is False

    async def test_text_in_a_counting_channel_is_removed(self):
        channel = counting_channel(history=[])

        assert await check_message(FakeMessage(channel, "hallo")) is True

    async def test_number_with_trailing_text_is_accepted(self):
        """``42 nice`` ist noch eine Zaehlung."""

        previous = FakeMessage(FakeChannel(), "41")
        channel = counting_channel(history=[previous])

        assert await check_message(FakeMessage(channel, "42 nice")) is False

    def test_next_count_reads_at_most_nine_digits(self):
        """Die Zahl ist auf neun Stellen begrenzt.

        Eine absichtlich riesige Zahl wird dadurch abgeschnitten und passt
        anschliessend nicht mehr zur Erwartung — der Beitrag fliegt raus,
        statt die Reihe in astronomische Hoehen zu schrauben.
        """

        assert next_count("9" * 12) == 1_000_000_000

    async def test_absurdly_long_number_is_rejected(self):
        """Der Fall aus Sicht des Kanals: die Reihe bleibt intakt."""

        previous = FakeMessage(FakeChannel(), "41")
        channel = counting_channel(history=[previous])

        assert await check_message(FakeMessage(channel, "1" * 13)) is True
        assert "42" in channel.hints[0][0]


# --------------------------------------------------------------------------- #
# Fehlerpfade beim Loeschen
# --------------------------------------------------------------------------- #

class TestDeletionFailures:
    async def test_missing_permission_reports_nothing_happened(self):
        """Ohne Loeschrecht darf kein Hinweis behaupten, es sei etwas passiert."""

        channel = media_channel()
        message = FakeMessage(
            channel, "text", delete_error=discord.Forbidden(_Resp(403), "nein")
        )

        assert await check_message(message) is False
        assert not channel.hints, "Hinweis trotz fehlgeschlagener Loeschung"

    async def test_already_deleted_message_is_not_an_error(self):
        channel = media_channel()
        message = FakeMessage(
            channel, "text", delete_error=discord.NotFound(_Resp(404), "weg")
        )

        assert await check_message(message) is False
        assert not channel.hints

    async def test_http_error_is_swallowed(self):
        channel = media_channel()
        message = FakeMessage(
            channel, "text", delete_error=discord.HTTPException(_Resp(500), "kaputt")
        )

        assert await check_message(message) is False

    async def test_undeliverable_hint_does_not_undo_the_deletion(self):
        """Die Nachricht ist weg — das bleibt so, auch ohne Schreibrecht."""

        channel = media_channel(
            send_error=discord.Forbidden(_Resp(403), "kein Schreibrecht")
        )
        message = FakeMessage(channel, "text")

        assert await check_message(message) is True
        assert message.deleted


# --------------------------------------------------------------------------- #
# Nichts anfassen
# --------------------------------------------------------------------------- #

class TestHandsOff:
    async def test_free_channel_is_never_touched(self):
        message = FakeMessage(FakeChannel("Normaler Kanal"), "irgendwas")

        assert await check_message(message) is False
        assert not message.deleted

    async def test_announce_mode_is_not_enforced_at_runtime(self):
        """``announce`` wird ueber Berechtigungen geloest, nicht per Loeschen."""

        channel = FakeChannel(f"News {mode_tag(ChannelMode.ANNOUNCE)}")

        assert await check_message(FakeMessage(channel, "text")) is False

    async def test_log_mode_is_not_enforced_at_runtime(self):
        channel = FakeChannel(f"Logs {mode_tag(ChannelMode.LOG)}")

        assert await check_message(FakeMessage(channel, "text")) is False

    async def test_team_messages_survive_every_mode(self):
        for channel in (media_channel(), counting_channel(history=[])):
            message = FakeMessage(channel, "text", author=FakeAuthor(manage=True))

            assert await check_message(message) is False
            assert not message.deleted


# --------------------------------------------------------------------------- #
# Auto-Reaktionen
# --------------------------------------------------------------------------- #

class TestAutoReactions:
    async def test_reactions_are_applied_in_order(self):
        channel = FakeChannel(f"Vorschlaege {reaction_tag(('👍', '👎'))}")
        message = FakeMessage(channel, "Idee")

        await apply_reactions(message)

        assert message.reactions == ["👍", "👎"]

    async def test_channel_without_tag_gets_none(self):
        message = FakeMessage(FakeChannel("Normal"), "Hallo")

        await apply_reactions(message)

        assert message.reactions == []

    async def test_missing_permission_stops_immediately(self):
        """Fehlt das Recht fuer die erste, fehlt es fuer alle."""

        channel = FakeChannel(f"Vorschlaege {reaction_tag(('👍', '👎'))}")
        message = FakeMessage(channel, "Idee")
        message.reaction_errors = [discord.Forbidden(_Resp(403), "nein")]

        await apply_reactions(message)

        assert message.reactions == []

    async def test_a_single_broken_emoji_does_not_stop_the_rest(self):
        """Ein geloeschtes Server-Emoji darf die uebrigen nicht verhindern."""

        channel = FakeChannel(f"Vorschlaege {reaction_tag(('👍', '👎'))}")
        message = FakeMessage(channel, "Idee")
        message.reaction_errors = [discord.HTTPException(_Resp(400), "unbekannt")]

        await apply_reactions(message)

        assert message.reactions == ["👎"]

    async def test_deleted_message_stops_the_loop(self):
        channel = FakeChannel(f"Vorschlaege {reaction_tag(('👍', '👎'))}")
        message = FakeMessage(channel, "Idee")
        message.reaction_errors = [discord.NotFound(_Resp(404), "weg")]

        await apply_reactions(message)

        assert message.reactions == []
