"""Der Premium-Pfad und die Zustellung von Ergebnissen.

Zwei Bereiche, die bisher unbelegt waren, obwohl an beiden etwas haengt:

**Premium.** Hier entscheidet sich, wer sieben zusaetzliche Vorlagen bekommt.
Ein Fehler in die eine Richtung macht das Feature wertlos, in die andere
sperrt er zahlende Nutzer aus. Getestet wird der ganze Weg: Button -> Modal
-> Key -> Freischaltung -> Auswahlmenue.

**Zustellung.** Ein grosses Template braucht Minuten, Discord-Interaktionen
leben aber nur 15. Laeuft die Interaktion waehrend des Baus ab, ist der Server
fertig — sagt es aber niemandem. Fuer diesen Fall gibt es einen Rueckfall in
den Kanal, und der war ebenfalls ungeprueft.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, cast

import discord
import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import config
from core.premium import PremiumStore
from core.registry import TemplateRegistry

KEY = "Test Key 12345"


@pytest.fixture(scope="module")
def registry() -> TemplateRegistry:
    return TemplateRegistry(config.TEMPLATE_DIR).load()


# --------------------------------------------------------------------------- #
# Nachbauten
# --------------------------------------------------------------------------- #

class FakeUser:
    def __init__(self, user_id: int = 7, *, manage_guild: bool = True) -> None:
        self.id = user_id
        self.display_name = "Testerin"
        self.guild_permissions = type("P", (), {"manage_guild": manage_guild})()


class FakeGuild:
    def __init__(self, guild_id: int = 123) -> None:
        self.id = guild_id
        self.name = "Testserver"
        self.me = None


class FakeResponse:
    def __init__(self) -> None:
        self.sent: list[object] = []
        self.edited: list[object] = []
        self.modals: list[object] = []

    def is_done(self) -> bool:
        return bool(self.sent or self.edited or self.modals)

    async def send_message(self, *, view=None, ephemeral: bool = False, **kw) -> None:
        self.sent.append(view)

    async def edit_message(self, *, view=None, **kw) -> None:
        self.edited.append(view)

    async def send_modal(self, modal) -> None:
        self.modals.append(modal)


class FakeFollowup:
    def __init__(self) -> None:
        self.sent: list[object] = []

    async def send(self, *, view=None, ephemeral: bool = False, **kw) -> None:
        self.sent.append(view)


class FakeChannel:
    """Ein Kanal, der mitschreibt, ob in ihn gepostet wurde."""

    def __init__(self, *, may_send: bool = True) -> None:
        self.posted: list[object] = []
        self._may_send = may_send

    def permissions_for(self, member):
        return type("P", (), {"send_messages": self._may_send})()

    async def send(self, *, view=None, **kw) -> None:
        self.posted.append(view)


_DEFAULT = object()


class FakeInteraction:
    def __init__(self, guild=_DEFAULT, user=None, channel=None) -> None:
        # ``guild=None`` muss ausdruecklich moeglich sein (Direktnachricht);
        # deshalb ein eigener Marker statt None als Vorgabewert.
        self.guild = FakeGuild() if guild is _DEFAULT else guild
        self.user = user if user is not None else FakeUser()
        self.channel = channel
        self.response = FakeResponse()
        self.followup = FakeFollowup()
        self.originals: list[object] = []
        #: Fehler, den ``edit_original_response`` werfen soll.
        self.edit_raises: Exception | None = None

    async def edit_original_response(self, *, view=None, **kw) -> None:
        if self.edit_raises is not None:
            raise self.edit_raises
        self.originals.append(view)

    @property
    def shown(self) -> list[object]:
        return [
            *self.response.sent,
            *self.response.edited,
            *self.followup.sent,
            *self.originals,
        ]


class FakeBot:
    def __init__(self, registry: TemplateRegistry, store: PremiumStore) -> None:
        self.registry = registry
        self.premium = store
        self.active_builds: set[int] = set()

    async def has_premium(self, interaction_or_ctx) -> bool:
        """
        Wie im echten Bot: lokaler Store zuerst.

        Der Lizenz-Client wird hier nicht nachgebildet — diese Tests
        pruefen die Views, nicht die HTTP-Abfrage. Die hat ihre eigenen
        Tests in test_licence.py.
        """

        guild = getattr(interaction_or_ctx, "guild", None)
        user = getattr(interaction_or_ctx, "user", None) or getattr(
            interaction_or_ctx, "author", None
        )
        if user is None:
            return False
        return self.premium.has_access(guild.id if guild else None, user.id)


class TestRevokeUser:
    """
    Nimmt der University Bot eine Lizenz weg, muss sie hier auch weg
    sein — sofort und dauerhaft.

    ``revoke`` allein reicht nicht: es braucht die Server-ID, und beim
    Widerruf ueber das Dashboard kennt niemand die. Dort wird eine
    *Lizenz* gesperrt, und die gehoert einem Konto.
    """

    def test_every_unlock_of_that_account_goes(self, tmp_path):
        store = PremiumStore(tmp_path / "premium.json", keys=(KEY,))
        store.grant(111, 42)
        store.grant(222, 42)

        removed = store.revoke_user(42)

        assert removed == 2
        assert store.has_access(111, 42) is False
        assert store.has_access(222, 42) is False

    def test_other_accounts_are_untouched(self, tmp_path):
        store = PremiumStore(tmp_path / "premium.json", keys=(KEY,))
        store.grant(111, 42)
        store.grant(111, 99)

        store.revoke_user(42)

        assert store.has_access(111, 99) is True

    def test_an_unknown_account_changes_nothing(self, tmp_path):
        store = PremiumStore(tmp_path / "premium.json", keys=(KEY,))
        store.grant(111, 42)

        assert store.revoke_user(555) == 0
        assert store.has_access(111, 42) is True

    def test_guild_wide_unlock_goes_too(self, tmp_path):
        """
        Bei ``guild_wide`` galt die Freischaltung fuer den ganzen Server.
        Bleibt sie stehen, hat der Server weiter Premium, obwohl niemand
        mehr eine gueltige Lizenz besitzt.
        """

        store = PremiumStore(
            tmp_path / "premium.json", keys=(KEY,), guild_wide=True
        )
        store.grant(111, 42)
        assert store.has_access(111, 999) is True  # ganzer Server

        store.revoke_user(42)

        assert store.has_access(111, 999) is False

    def test_the_revoke_survives_a_restart(self, tmp_path):
        """Sonst waere Premium nach dem naechsten Deploy wieder da."""

        path = tmp_path / "premium.json"
        first = PremiumStore(path, keys=(KEY,))
        first.grant(111, 42)
        first.revoke_user(42)

        second = PremiumStore(path, keys=(KEY,))

        assert second.has_access(111, 42) is False


class TestStorageIsPersistent:
    """
    Freischaltungen muessen ein Redeploy ueberleben.

    Ohne gemountetes Volume schreibt der Bot in den Container, und nach
    dem naechsten Deploy ist jede Freischaltung weg — lautlos. Railway
    zeigt beim Mounten nur den Host-Pfad an, deshalb sagt der Bot beim
    Start selbst, ob er auf einem Volume liegt.
    """

    def test_a_plain_directory_is_not_persistent(self, tmp_path):
        store = PremiumStore(tmp_path / "premium.json", keys=(KEY,))

        assert store.storage_is_persistent is False

    def test_a_missing_directory_is_not_persistent(self, tmp_path):
        store = PremiumStore(tmp_path / "weg" / "premium.json", keys=(KEY,))

        assert store.storage_is_persistent is False

    def test_a_mount_is_recognised(self, tmp_path, monkeypatch):
        """Ein Mount hat eine andere Geraete-ID als sein Elternordner."""

        store = PremiumStore(tmp_path / "premium.json", keys=(KEY,))
        directory = store.path.parent
        real_stat = Path.stat

        class Faked:
            """Reicht alles durch und aendert nur st_dev.

            Ein Objekt mit *nur* st_dev reicht nicht: is_dir() liest
            st_mode aus demselben Ergebnis.
            """

            def __init__(self, real):
                self._real = real

            def __getattr__(self, name):
                return getattr(self._real, name)

            @property
            def st_dev(self):
                return self._real.st_dev + 1

        def fake_stat(self, *args, **kwargs):
            result = real_stat(self, *args, **kwargs)
            if self == directory:
                return Faked(result)
            return result

        monkeypatch.setattr(Path, "stat", fake_stat)

        assert store.storage_is_persistent is True

    def test_the_warning_names_the_mount_path(self, tmp_path, caplog):
        """
        Die Meldung muss sagen, wo das Volume hin soll — sonst weiss
        niemand, welchen Pfad er in Railway eintragen muss.
        """

        store = PremiumStore(tmp_path / "premium.json", keys=(KEY,))

        with caplog.at_level("WARNING"):
            store.log_storage_state()

        text = caplog.text
        assert "NICHT" in text
        assert str(tmp_path) in text

    def test_unlocks_survive_a_restart(self, tmp_path):
        """Der eigentliche Zweck: neu geladen, Freischaltung noch da."""

        path = tmp_path / "premium.json"
        first = PremiumStore(path, keys=(KEY,))
        first.grant(4242, 7)

        second = PremiumStore(path, keys=(KEY,))

        assert second.has_access(4242, 7) is True


class _Resp:
    def __init__(self, status: int) -> None:
        self.status = status
        self.reason = "Fehler"
        self.headers: dict[str, str] = {}


@pytest.fixture
def store(tmp_path) -> PremiumStore:
    return PremiumStore(tmp_path / "premium.json", keys=(KEY,))


@pytest.fixture
def bot(registry, store) -> FakeBot:
    return FakeBot(registry, store)


@pytest.fixture(autouse=True)
def members_pass_isinstance(monkeypatch):
    """``_can_manage`` prueft auf ``discord.Member``."""

    import ui.views as views

    real_isinstance = isinstance

    def lenient(obj, classinfo):
        if classinfo is discord.Member and type(obj) is FakeUser:
            return True
        return real_isinstance(obj, classinfo)

    monkeypatch.setitem(views.__dict__, "isinstance", lenient)
    yield


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


def submit_key(bot: FakeBot, value: str):
    """Ein PremiumModal mit vorbelegtem Eingabefeld bauen.

    Ohne Gateway fuellt niemand das TextInput; ``_value`` ist die Stelle, aus
    der ``value`` beim echten Absenden gelesen wird.
    """

    from ui.views import PremiumModal

    modal = PremiumModal(cast("Any", bot))
    cast("Any", modal.key.component)._value = value
    return modal


# --------------------------------------------------------------------------- #
# Premium-Button
# --------------------------------------------------------------------------- #

class TestPremiumButton:
    async def test_opens_the_modal_for_new_users(self, bot):
        from ui.views import PremiumButton

        interaction = FakeInteraction()
        await PremiumButton(bot).callback(interaction)

        assert interaction.response.modals, "Es wurde kein Key-Fenster geoeffnet"
        assert not interaction.response.sent

    async def test_tells_existing_users_they_already_have_it(self, bot):
        """Ein zweites Key-Fenster waere nur verwirrend."""

        from ui.views import PremiumButton

        user = FakeUser()
        bot.premium.grant(None, user.id)

        interaction = FakeInteraction(user=user, guild=None)
        await PremiumButton(bot).callback(interaction)

        assert not interaction.response.modals
        assert "Bereits freigeschaltet" in all_text(interaction)


# --------------------------------------------------------------------------- #
# Key-Eingabe
# --------------------------------------------------------------------------- #

class TestPremiumModal:
    async def test_correct_key_unlocks(self, bot):
        interaction = FakeInteraction()
        await submit_key(bot, KEY).on_submit(interaction)

        assert bot.premium.has_access(interaction.guild.id, interaction.user.id)
        text = all_text(interaction)
        assert "Premium freigeschaltet" in text

    async def test_unlock_screen_lists_every_premium_template(self, bot, registry):
        interaction = FakeInteraction()
        await submit_key(bot, KEY).on_submit(interaction)

        text = all_text(interaction)
        for template in registry.premium:
            assert template.name in text, f"{template.name} fehlt in der Uebersicht"

    async def test_wrong_key_does_not_unlock(self, bot):
        interaction = FakeInteraction()
        await submit_key(bot, "falsch").on_submit(interaction)

        assert not bot.premium.has_access(interaction.guild.id, interaction.user.id)
        assert "nicht erkannt" in all_text(interaction)

    async def test_empty_key_does_not_unlock(self, bot):
        interaction = FakeInteraction()
        await submit_key(bot, "   ").on_submit(interaction)

        assert not bot.premium.has_access(interaction.guild.id, interaction.user.id)

    async def test_surrounding_whitespace_is_tolerated(self, bot):
        """Beim Kopieren aus einer Nachricht haengt fast immer ein Leerzeichen dran."""

        interaction = FakeInteraction()
        await submit_key(bot, f"  {KEY}  ").on_submit(interaction)

        assert bot.premium.has_access(interaction.guild.id, interaction.user.id)

    async def test_the_key_is_never_echoed_back(self, bot):
        """Weder bei Erfolg noch bei Misserfolg darf der Key in der Antwort stehen."""

        for supplied in (KEY, "falscher-key-abc"):
            interaction = FakeInteraction()
            await submit_key(bot, supplied).on_submit(interaction)
            assert supplied not in all_text(interaction)

    async def test_unlock_does_not_leak_to_other_users(self, bot):
        """Eine Freischaltung gilt fuer den Einloeser, nicht fuer den Kanal."""

        guild = FakeGuild()
        await submit_key(bot, KEY).on_submit(
            FakeInteraction(guild=guild, user=FakeUser(1))
        )

        assert bot.premium.has_access(guild.id, 1)
        assert not bot.premium.has_access(guild.id, 2)

    async def test_works_without_a_guild(self, bot):
        """In Direktnachrichten gibt es keine Guild-ID — das darf nicht knallen."""

        user = FakeUser(99)
        await submit_key(bot, KEY).on_submit(FakeInteraction(guild=None, user=user))

        assert bot.premium.has_access(None, user.id)


# --------------------------------------------------------------------------- #
# Auswahlmenue
# --------------------------------------------------------------------------- #

class TestTemplateSelect:
    def _select(self, bot, chosen: str):
        from ui.views import build_start_view

        view = build_start_view(bot, premium=True)
        for child in view.walk_children():
            if isinstance(child, discord.ui.Select):
                child._values = [chosen]
                return child
        raise AssertionError("Kein Auswahlmenue in der Startansicht")

    async def test_premium_template_is_blocked_without_access(self, bot, registry):
        premium_template = registry.premium[0]
        select = self._select(bot, premium_template.key)

        interaction = FakeInteraction()
        await select.callback(interaction)

        text = all_text(interaction)
        assert "Premium erforderlich" in text
        assert premium_template.name in text

    async def test_premium_template_opens_after_unlocking(self, bot, registry):
        premium_template = registry.premium[0]
        user = FakeUser(5)
        guild = FakeGuild()
        bot.premium.grant(guild.id, user.id)

        select = self._select(bot, premium_template.key)
        interaction = FakeInteraction(guild=guild, user=user)
        await select.callback(interaction)

        assert "Premium erforderlich" not in all_text(interaction)

    async def test_free_template_needs_no_unlock(self, bot, registry):
        select = self._select(bot, registry.free[0].key)

        interaction = FakeInteraction()
        await select.callback(interaction)

        assert "Premium erforderlich" not in all_text(interaction)

    async def test_unknown_key_is_reported(self, bot):
        """Etwa nach dem Entfernen einer Vorlage bei offenem Menue."""

        select = self._select(bot, "gibt-es-nicht")

        interaction = FakeInteraction()
        await select.callback(interaction)

        assert "nicht gefunden" in all_text(interaction)


# --------------------------------------------------------------------------- #
# Zustellung des Ergebnisses
# --------------------------------------------------------------------------- #

class TestResultDelivery:
    async def test_safe_edit_reports_success(self):
        from ui.components import notice
        from ui.views import _safe_edit

        interaction = FakeInteraction()
        assert await _safe_edit(interaction, notice("Fertig", "Alles gut")) is True
        assert interaction.originals

    async def test_expired_interaction_is_not_an_error(self):
        """404 heisst: Interaktion abgelaufen oder Nachricht geloescht."""

        from ui.components import notice
        from ui.views import _safe_edit

        interaction = FakeInteraction()
        interaction.edit_raises = discord.NotFound(_Resp(404), "weg")

        assert await _safe_edit(interaction, notice("Fertig", "Alles gut")) is False

    async def test_other_http_errors_are_swallowed_too(self):
        from ui.components import notice
        from ui.views import _safe_edit

        interaction = FakeInteraction()
        interaction.edit_raises = discord.HTTPException(_Resp(500), "kaputt")

        assert await _safe_edit(interaction, notice("Fertig", "Alles gut")) is False

    async def test_fallback_posts_into_the_channel(self):
        """Sonst bleibt ein mehrminuetiger Umbau ohne jede Rueckmeldung."""

        from ui.components import notice
        from ui.views import _fallback_notify

        channel = FakeChannel()
        interaction = FakeInteraction(channel=channel)
        await _fallback_notify(interaction, notice("Fertig", "Server steht"))

        assert channel.posted, "Das Ergebnis wurde nirgends zugestellt"

    async def test_fallback_stays_silent_without_permission(self):
        """Ohne Schreibrecht wuerde der Versuch nur eine Exception erzeugen."""

        from ui.components import notice
        from ui.views import _fallback_notify

        channel = FakeChannel(may_send=False)
        guild = FakeGuild()
        guild.me = object()

        interaction = FakeInteraction(guild=guild, channel=channel)
        await _fallback_notify(interaction, notice("Fertig", "Server steht"))

        assert not channel.posted

    async def test_fallback_handles_a_missing_channel(self):
        from ui.components import notice
        from ui.views import _fallback_notify

        interaction = FakeInteraction(channel=None)
        await _fallback_notify(interaction, notice("Fertig", "Server steht"))

    async def test_report_falls_back_when_the_interaction_died(self):
        """Der Zweck der ganzen Konstruktion, an einem Stueck."""

        from ui.components import notice
        from ui.views import _report

        channel = FakeChannel()
        interaction = FakeInteraction(channel=channel)
        interaction.edit_raises = discord.NotFound(_Resp(404), "weg")

        await _report(interaction, notice("Fertig", "Server steht"))

        assert channel.posted, "Nach Ablauf der Interaktion kam nichts an"

    async def test_report_uses_the_interaction_when_it_still_works(self):
        from ui.components import notice
        from ui.views import _report

        channel = FakeChannel()
        interaction = FakeInteraction(channel=channel)

        await _report(interaction, notice("Fertig", "Server steht"))

        assert interaction.originals
        assert not channel.posted, "Doppelte Zustellung"
