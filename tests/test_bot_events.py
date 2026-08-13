"""Die Ereignisse und Befehle in ``bot.py``.

Diese Datei schließt die letzte große Lücke: ``bot.py`` hat 450 Zeilen und
wurde von der Abdeckungsmessung gar nicht erfasst — kein einziger Test hat das
Modul auch nur importiert. Die 96 % Gesamtabdeckung galten also für alles
*außer* dem Einstiegspunkt.

Was hier hängt, ist nicht nebensächlich:

* ``on_member_join`` vergibt die Unverified-Rolle. Bleibt sie aus, ist die
  Eingangsschleuse jedes gebauten Servers wirkungslos — Neulinge sähen sofort
  alles.
* ``on_message`` setzt die Kanal-Modi durch **und** verarbeitet Befehle. Ein
  früher Rücksprung an der falschen Stelle legt entweder die Moderation oder
  alle Befehle lahm.
* ``has_premium`` entscheidet über den Zugang zu sieben Vorlagen und muss mit
  zwei verschiedenen Objektarten umgehen (Interaction und Context).
"""

from __future__ import annotations

import asyncio
import runpy
import sys
from pathlib import Path
from typing import Any, ClassVar, cast

import discord
import pytest
from discord.ext import commands

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import bot as bot_module
from core.permissions import BASE_ROLES
from core.small_caps import role_name


def unverified_role_name() -> str:
    """Der Name, unter dem die Vorlagen die Schleusen-Rolle wirklich anlegen.

    Aus BASE_ROLES abgeleitet statt hier abgeschrieben: benennt jemand die
    Rolle um, schlaegt dieser Test fehl statt die Schleuse still zu oeffnen.
    """

    for key, label, emoji, *_ in BASE_ROLES:
        if key == "unverified":
            return role_name(label, emoji)
    raise AssertionError("BASE_ROLES kennt keine unverified-Rolle mehr")


class _Resp:
    status = 403
    reason = "Forbidden"
    headers: dict[str, str] = {}  # noqa: RUF012


# --------------------------------------------------------------------------- #
# Attrappen
# --------------------------------------------------------------------------- #

class FakeRole:
    def __init__(self, name: str, *, assignable: bool = True) -> None:
        self.name = name
        self.id = abs(hash(name)) % 10**8
        self._assignable = assignable

    def is_assignable(self) -> bool:
        return self._assignable


class FakeGuild:
    def __init__(self, roles: list[FakeRole] | None = None) -> None:
        self.id = 4242
        self.name = "Testserver"
        self.roles = list(roles or [])


class FakeMember:
    def __init__(
        self,
        guild: FakeGuild | None = None,
        *,
        is_bot: bool = False,
        add_fails: bool = False,
    ) -> None:
        self.id = 7
        self.name = "tester"
        self.bot = is_bot
        self.guild = guild if guild is not None else FakeGuild()
        self.added: list[str] = []
        self._add_fails = add_fails

    async def add_roles(self, role: FakeRole, reason: str | None = None) -> None:
        if self._add_fails:
            raise discord.HTTPException(_Resp(), "nein")
        self.added.append(role.name)


class FakeMessage:
    def __init__(
        self,
        *,
        author=None,
        guild: FakeGuild | None = None,
        content: str = "hallo",
    ) -> None:
        self.author = author if author is not None else FakeMember()
        self.guild = guild
        self.content = content
        self.channel = object()


class FakeContext:
    def __init__(self, guild: FakeGuild | None = None) -> None:
        self.guild = guild
        self.author = FakeMember()
        self.sent: list[object] = []

    async def send(self, *args, view=None, **kwargs) -> None:
        self.sent.append(view if view is not None else (args[0] if args else None))


class FakeResponse:
    def __init__(self) -> None:
        self.sent: list[object] = []
        self.edited: list[object] = []
        self.modals: list[object] = []
        self.deferred = False

    def is_done(self) -> bool:
        return bool(self.sent or self.edited or self.modals or self.deferred)

    async def send_message(self, *, view=None, **kwargs) -> None:
        self.sent.append(view)

    async def edit_message(self, *, view=None, **kwargs) -> None:
        self.edited.append(view)

    async def send_modal(self, modal) -> None:
        self.modals.append(modal)

    async def defer(self, *, ephemeral: bool = False, thinking: bool = False) -> None:
        self.deferred = True


class FakeFollowup:
    def __init__(self) -> None:
        self.sent: list[tuple[object, object]] = []

    async def send(self, *, view=None, file=None, **kwargs) -> None:
        self.sent.append((view, file))


class FakeInteraction:
    def __init__(self, guild: FakeGuild | None = None, user=None) -> None:
        self.guild = guild if guild is not None else FakeGuild()
        self.user = user if user is not None else FakeMember(self.guild)
        self.response = FakeResponse()
        self.followup = FakeFollowup()


def rendered(view) -> str:
    if view is None or not hasattr(view, "to_components"):
        return str(view)

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


def texts(ctx: FakeContext) -> str:
    return "\n".join(rendered(view) for view in ctx.sent)


@pytest.fixture
def architect():
    """Die echte Bot-Instanz aus dem Modul.

    ``bot.py`` legt sie beim Import an; ein zweites Exemplar zu bauen würde
    Registry und Premium-Store erneut laden, ohne etwas zu gewinnen.
    """

    return bot_module.bot


# --------------------------------------------------------------------------- #
# Eingangsschleuse
# --------------------------------------------------------------------------- #

class TestOnMemberJoin:
    """Ohne diese Rolle ist die Verify-Schleuse jedes Servers wirkungslos."""

    async def test_unverified_role_is_granted(self, architect):
        role = FakeRole(unverified_role_name())
        member = FakeMember(FakeGuild([role]))

        await architect.on_member_join(cast("Any", member))

        assert member.added == [role.name]

    async def test_bots_are_ignored(self, architect):
        """Ein Bot, der hinter der Schleuse landet, kann nicht arbeiten."""

        role = FakeRole(unverified_role_name())
        member = FakeMember(FakeGuild([role]), is_bot=True)

        await architect.on_member_join(cast("Any", member))

        assert not member.added

    async def test_missing_role_is_not_an_error(self, architect):
        """Server ohne Schleuse gibt es — das ist kein Fehlerfall."""

        member = FakeMember(FakeGuild([FakeRole("Mitglied")]))

        await architect.on_member_join(cast("Any", member))

        assert not member.added

    async def test_unassignable_role_is_skipped(self, architect):
        """Steht die Rolle über dem Bot, wird sie gar nicht erst versucht."""

        role = FakeRole(unverified_role_name(), assignable=False)
        member = FakeMember(FakeGuild([role]))

        await architect.on_member_join(cast("Any", member))

        assert not member.added

    async def test_http_failure_does_not_propagate(self, architect):
        """Ein Fehler hier darf den Gateway-Handler nicht mitreißen."""

        role = FakeRole(unverified_role_name())
        member = FakeMember(FakeGuild([role]), add_fails=True)

        await architect.on_member_join(cast("Any", member))  # darf nicht werfen

    async def test_role_is_found_despite_emoji_and_case(self, architect):
        """Die Suche laeuft ueber ``"unverified" in name.lower()``.

        Rollennamen behalten anders als Kanalnamen ihre normale Schreibweise
        (Discord schreibt nur Kanaele klein), aber Emoji und Trenner stehen
        davor — und Serverbetreiber schreiben gern gross.
        """

        for name in (
            unverified_role_name(),
            "Unverified",
            "unverified",
            "UNVERIFIED",
            "🔰・Unverified",
            "Unverified (bitte lesen)",
        ):
            member = FakeMember(FakeGuild([FakeRole(name)]))
            await architect.on_member_join(cast("Any", member))
            assert member.added, f"'{name}' wurde nicht erkannt"

    async def test_the_role_name_from_the_templates_matches(self, architect):
        """Bindeglied zwischen Builder und Gateway-Handler.

        Der Builder legt die Rolle nach BASE_ROLES an, der Handler sucht sie
        per Textvergleich. Driften beide auseinander, bleibt die Schleuse
        still offen — ohne Fehlermeldung.
        """

        assert "unverified" in unverified_role_name().lower()


# --------------------------------------------------------------------------- #
# Nachrichten
# --------------------------------------------------------------------------- #

class TestOnMessage:
    """Durchsetzung der Kanal-Modi, ohne die Befehlsverarbeitung zu verlieren."""

    @pytest.fixture(autouse=True)
    def _spy(self, architect, monkeypatch):
        """``process_commands`` beobachten statt ausführen."""

        seen: list[object] = []

        async def record(message):
            seen.append(message)

        monkeypatch.setattr(architect, "process_commands", record)
        return seen

    async def test_bot_messages_skip_enforcement(self, architect, _spy, monkeypatch):
        """Sonst löschte der Bot seine eigenen Hinweise."""

        import core.enforcement as enforcement

        called = []

        async def spy(message):
            called.append(message)
            return False

        monkeypatch.setattr(enforcement, "check_message", spy)

        message = FakeMessage(author=FakeMember(is_bot=True), guild=FakeGuild())
        await architect.on_message(cast("Any", message))

        assert not called, "Bot-Nachricht wurde geprüft"
        assert _spy == [message], "Befehle von Bots wurden nicht verarbeitet"

    async def test_direct_messages_skip_enforcement(self, architect, _spy):
        """Ohne Guild gibt es keinen Kanal-Modus."""

        message = FakeMessage(guild=None)

        await architect.on_message(cast("Any", message))

        assert _spy == [message]

    async def test_allowed_message_reaches_the_commands(
        self, architect, _spy, monkeypatch
    ):
        import core.enforcement as enforcement

        async def allow(message):
            return False

        async def react(message):
            return None

        monkeypatch.setattr(enforcement, "check_message", allow)
        monkeypatch.setattr(enforcement, "apply_reactions", react)

        message = FakeMessage(guild=FakeGuild())
        await architect.on_message(cast("Any", message))

        assert _spy == [message]

    async def test_removed_message_stops_everything(
        self, architect, _spy, monkeypatch
    ):
        """Eine gelöschte Nachricht darf keinen Befehl mehr auslösen."""

        import core.enforcement as enforcement

        reacted = []

        async def remove(message):
            return True

        async def react(message):
            reacted.append(message)

        monkeypatch.setattr(enforcement, "check_message", remove)
        monkeypatch.setattr(enforcement, "apply_reactions", react)

        await architect.on_message(cast("Any", FakeMessage(guild=FakeGuild())))

        assert not _spy, "Gelöschte Nachricht wurde noch als Befehl verarbeitet"
        assert not reacted, "Auf eine gelöschte Nachricht wurde reagiert"

    async def test_enforcement_failure_does_not_block_commands(
        self, architect, _spy, monkeypatch
    ):
        """Ein Discord-Fehler in der Moderation darf Befehle nicht lahmlegen."""

        import core.enforcement as enforcement

        async def explode(message):
            raise discord.HTTPException(_Resp(), "kaputt")

        async def react(message):
            return None

        monkeypatch.setattr(enforcement, "check_message", explode)
        monkeypatch.setattr(enforcement, "apply_reactions", react)

        message = FakeMessage(guild=FakeGuild())
        await architect.on_message(cast("Any", message))

        assert _spy == [message]

    async def test_reaction_failure_does_not_block_commands(
        self, architect, _spy, monkeypatch
    ):
        import core.enforcement as enforcement

        async def allow(message):
            return False

        async def explode(message):
            raise discord.HTTPException(_Resp(), "kaputt")

        monkeypatch.setattr(enforcement, "check_message", allow)
        monkeypatch.setattr(enforcement, "apply_reactions", explode)

        message = FakeMessage(guild=FakeGuild())
        await architect.on_message(cast("Any", message))

        assert _spy == [message]


# --------------------------------------------------------------------------- #
# Premium-Auflösung
# --------------------------------------------------------------------------- #

class TestHasPremium:
    """Muss mit Interaction *und* Context umgehen — beide Wege existieren."""

    async def test_interaction_style_object(self, architect, monkeypatch):
        seen: list[tuple] = []
        monkeypatch.setattr(
            architect.premium,
            "has_access",
            lambda guild_id, user_id: seen.append((guild_id, user_id)) or True,
        )

        interaction = type(
            "I", (), {"guild": FakeGuild(), "user": FakeMember()}
        )()

        assert await architect.has_premium(interaction)
        assert seen == [(4242, 7)]

    async def test_context_style_object(self, architect, monkeypatch):
        """Prefix-Befehle liefern ``author`` statt ``user``."""

        seen: list[tuple] = []
        monkeypatch.setattr(
            architect.premium,
            "has_access",
            lambda guild_id, user_id: seen.append((guild_id, user_id)) or True,
        )

        ctx = type("C", (), {"guild": FakeGuild(), "author": FakeMember()})()

        assert await architect.has_premium(ctx)
        assert seen == [(4242, 7)]

    async def test_without_a_user_there_is_no_premium(self, architect):
        empty = type("X", (), {"guild": None})()

        assert not await architect.has_premium(empty)

    async def test_direct_message_passes_no_guild(self, architect, monkeypatch):
        seen: list[tuple] = []
        monkeypatch.setattr(
            architect.premium,
            "has_access",
            lambda guild_id, user_id: seen.append((guild_id, user_id)) or False,
        )

        interaction = type("I", (), {"guild": None, "user": FakeMember()})()

        await architect.has_premium(interaction)
        assert seen == [(None, 7)]


# --------------------------------------------------------------------------- #
# Befehlsfläche
# --------------------------------------------------------------------------- #

def slash_command(*path: str):
    """Der Callback eines Befehls aus der /template-Gruppe."""

    current: Any = bot_module.template_group
    for name in path:
        current = current.get_command(name)
        assert current is not None, f"Unterbefehl '{name}' fehlt"
    return current.callback


def tree_command(name: str):
    """Der Callback eines Slash-Befehls auf oberster Baumebene."""

    command = bot_module.bot.tree.get_command(name)
    assert command is not None, f"Slash-Befehl '{name}' fehlt"
    return cast("Any", command).callback


class TestCommandSurface:
    """Die /template-Gruppe ersetzt die alten Prefix-Befehle komplett."""

    def test_prefix_commands_are_gone(self, architect):
        for name in ("start", "regeln", "partner-setup", "ping"):
            assert architect.get_command(name) is None, f"!{name} existiert noch"

    def test_the_group_is_registered(self, architect):
        names = {command.name for command in architect.tree.get_commands()}

        assert names >= {"template", "ping"}

    def test_the_group_has_all_subcommands(self, architect):
        group = architect.tree.get_command("template")
        assert group is not None

        names = {command.name for command in group.commands}
        assert names == {
            "start",
            "list",
            "löschen",
            "ai",
            "regeln",
            "partner-setup",
            "backup",
        }

    def test_backup_has_erstellen(self, architect):
        group = architect.tree.get_command("template")
        assert group is not None

        backup = group.get_command("backup")
        assert isinstance(backup, discord.app_commands.Group)
        assert backup.get_command("erstellen") is not None

    def test_destructive_commands_need_manage_guild(self, architect):
        """Loeschen, Wipe und Partner-Setup gehoeren hinter die Huerde."""

        group = architect.tree.get_command("template")
        assert group is not None

        protected = [
            group.get_command("löschen"),
            group.get_command("partner-setup"),
            group.get_command("backup").get_command("erstellen"),
        ]
        for command in protected:
            permissions = getattr(command, "default_permissions", None)
            assert permissions is not None, f"{command.name} hat keine Huerde"
            assert permissions.manage_guild


# --------------------------------------------------------------------------- #
# Weitere Bausteine
# --------------------------------------------------------------------------- #

class TestBotBasics:
    def test_no_mentions_are_allowed_by_default(self, architect):
        """Ein Bot, der 900 Kanäle anlegt, darf niemanden anpingen."""

        mentions = architect.allowed_mentions

        assert mentions.everyone is False
        assert mentions.roles is False
        assert mentions.users is False

    def test_the_default_help_command_is_disabled(self, architect):
        """Discords Standardhilfe passt nicht zu Components V2."""

        assert architect.help_command is None

    def test_scheduling_without_a_handoff_does_nothing(self, architect):
        """Kein vorgemerkter Handoff heißt: kein automatischer Umbau."""

        architect.pending_handoffs.pop(999)  # sicherstellen, dass nichts liegt
        architect.schedule_partner_setup(cast("Any", FakeGuild()))


# --------------------------------------------------------------------------- #
# Befehle: /template start, list, löschen, ai, regeln, partner-setup, backup
# --------------------------------------------------------------------------- #

class TestTemplateStartCommand:
    """``/template start`` ist der Einstieg ins Vorlagen-Menü."""

    async def test_shows_the_template_menu(self, monkeypatch):
        shown: list[tuple] = []

        def fake_view(bot, *, premium):
            shown.append(premium)
            return "MENÜ"

        monkeypatch.setattr(bot_module, "build_start_view", fake_view)

        interaction = FakeInteraction(FakeGuild())
        await slash_command("start")(cast("Any", interaction))

        assert interaction.response.sent == ["MENÜ"]
        assert shown == [False], "Der Premium-Status wurde nicht uebergeben"

    async def test_premium_is_passed_along(self, architect, monkeypatch):
        shown: list[tuple] = []

        def fake_view(bot, *, premium):
            shown.append(premium)
            return object()

        monkeypatch.setattr(bot_module, "build_start_view", fake_view)
        monkeypatch.setattr(architect.premium, "has_access", lambda *a: True)

        await slash_command("start")(cast("Any", FakeInteraction(FakeGuild())))

        assert shown == [True]


class TestTemplateListCommand:
    async def test_shows_the_list_view(self, monkeypatch):
        import ui.management as management

        created: list = []

        class FakeListView:
            def __init__(self, bot):
                created.append(bot)

        monkeypatch.setattr(management, "TemplateListView", FakeListView)

        interaction = FakeInteraction(FakeGuild())
        await slash_command("list")(cast("Any", interaction))

        assert created == [bot_module.bot]
        assert isinstance(interaction.response.sent[0], FakeListView)


class TestTemplateDeleteCommand:
    async def test_with_a_template_it_asks_for_confirmation(self):
        import ui.management as management

        interaction = FakeInteraction(FakeGuild())
        await slash_command("löschen")(cast("Any", interaction), "community")

        view = interaction.response.sent[0]
        assert isinstance(view, management.DeleteConfirmView)
        assert view.template is bot_module.bot.registry.get("community")

    async def test_an_unknown_template_is_explained(self):
        interaction = FakeInteraction(FakeGuild())
        await slash_command("löschen")(cast("Any", interaction), "gibt-es-nicht")

        assert "Vorlage nicht gefunden" in rendered(interaction.response.sent[0])

    async def test_without_an_argument_it_opens_the_picker(self):
        import ui.management as management

        interaction = FakeInteraction(FakeGuild())
        await slash_command("löschen")(cast("Any", interaction), None)

        assert isinstance(interaction.response.sent[0], management.DeletePickerView)

    async def test_autocomplete_suggests_matching_templates(self):
        choices = await bot_module.template_delete_autocomplete(cast("Any", None), "anime")

        assert [choice.value for choice in choices] == ["anime"]

    async def test_autocomplete_lists_everything_when_empty(self):
        choices = await bot_module.template_delete_autocomplete(cast("Any", None), "")

        assert len(choices) == len(bot_module.bot.registry)


class TestTemplateAiCommand:
    async def test_opens_the_description_modal(self):
        import ui.management as management

        interaction = FakeInteraction(FakeGuild())
        await slash_command("ai")(cast("Any", interaction))

        assert isinstance(interaction.response.modals[0], management.AiTemplateModal)


class TestTemplateRegelnCommand:
    async def test_delegates_to_the_assistant(self, monkeypatch):
        import ui.rules as rules_module

        seen: list = []

        async def spy(interaction, bot):
            seen.append((interaction, bot))

        monkeypatch.setattr(rules_module, "open_rules_assistant", spy)

        interaction = FakeInteraction(FakeGuild())
        await slash_command("regeln")(cast("Any", interaction))

        assert seen == [(interaction, bot_module.bot)]


class TestTemplatePartnerSetupCommand:
    async def test_a_previous_run_is_announced(self, architect, monkeypatch):
        """Wer den Befehl zweimal nutzt, soll wissen, was ihn erwartet."""

        monkeypatch.setattr(
            architect.setup_ledger, "details", lambda gid: {"template": "community"}
        )

        ran: list = []

        async def fake_run(guild, handoff, *, force=False):
            ran.append(force)

        monkeypatch.setattr(architect.autosetup, "run", fake_run)

        interaction = FakeInteraction(FakeGuild())
        await slash_command("partner-setup")(cast("Any", interaction))

        text = rendered(interaction.response.sent[0])
        assert "erneut" in text.lower()
        assert "community" in text
        assert ran == [True], "Der erneute Aufbau wurde nicht erzwungen"

    async def test_a_first_run_starts_silently(self, architect, monkeypatch):
        monkeypatch.setattr(architect.setup_ledger, "details", lambda gid: None)

        ran: list = []

        async def fake_run(guild, handoff, *, force=False):
            ran.append(handoff)

        monkeypatch.setattr(architect.autosetup, "run", fake_run)

        interaction = FakeInteraction(FakeGuild())
        await slash_command("partner-setup")(cast("Any", interaction))

        assert not interaction.response.sent, "Beim ersten Lauf braucht es keine Vorwarnung"
        assert ran, "Die Einrichtung wurde nicht angestossen"
        assert ran[0].source == "manual", "Der Handoff ist nicht als manuell markiert"


class TestPingCommand:
    async def test_reports_latency_and_template_count(self, architect, monkeypatch):
        monkeypatch.setattr(type(architect), "latency", property(lambda self: 0.042))

        interaction = FakeInteraction(FakeGuild())
        await tree_command("ping")(cast("Any", interaction))

        text = rendered(interaction.response.sent[0])
        assert "Pong" in text
        assert "42 ms" in text
        assert str(len(architect.registry)) in text

    async def test_survives_an_unmeasured_latency(self, architect):
        """Vor dem ersten Heartbeat liefert discord.py NaN.

        ``round(nan)`` wirft einen ValueError — und ausgerechnet direkt nach
        dem Start greift man am ehesten zu /ping.
        """

        import math

        assert math.isnan(architect.latency), "Testannahme stimmt nicht mehr"

        interaction = FakeInteraction(FakeGuild())
        await tree_command("ping")(cast("Any", interaction))

        text = rendered(interaction.response.sent[0])
        assert "Pong" in text
        assert "nan" not in text.lower()


class _BackupRole:
    id = 1
    name = "Moderator"
    position = 3
    colour = 0
    permissions = discord.Permissions.none()
    hoist = False
    mentionable = False
    managed = False

    def is_default(self) -> bool:
        return False


class _BackupChannel:
    id = 2
    name = "allgemein"
    position = 0
    type = discord.ChannelType.text
    category = None
    topic = "Plauderecke"
    slowmode_delay = 0
    nsfw = False
    user_limit = 0
    overwrites: ClassVar[dict] = {}


class _BackupGuild:
    def __init__(self) -> None:
        self.id = 4242
        self.name = "Testserver"
        self.member_count = 12
        self.roles = [_BackupRole()]
        self.channels = [_BackupChannel()]
        self.me = None


class TestBackupCommand:
    async def test_writes_and_attaches_the_backup(self, monkeypatch, tmp_path):
        monkeypatch.setattr(bot_module.config, "BACKUP_DIR", tmp_path)

        interaction = FakeInteraction(_BackupGuild())
        await slash_command("backup", "erstellen")(cast("Any", interaction))

        assert interaction.response.deferred, "Der Befehl hat nicht zuerst geantwortet"
        view, file = interaction.followup.sent[0]
        assert file is not None
        assert "Backup erstellt" in rendered(view)

        backups = list(tmp_path.glob("backup-*.json"))
        assert len(backups) == 1
        assert backups[0].name == file.filename

    async def test_a_failed_write_is_explained(self, monkeypatch, tmp_path):
        import core.backup as backup_module

        async def broken(guild, directory):
            raise OSError("kein Platz")

        monkeypatch.setattr(backup_module, "save_backup", broken)
        monkeypatch.setattr(bot_module.config, "BACKUP_DIR", tmp_path)

        interaction = FakeInteraction(_BackupGuild())
        await slash_command("backup", "erstellen")(cast("Any", interaction))

        view, file = interaction.followup.sent[0]
        assert file is None
        assert "Backup fehlgeschlagen" in rendered(view)


# --------------------------------------------------------------------------- #
# Fehlerbehandlung
# --------------------------------------------------------------------------- #

class TestCommandErrors:
    async def test_unknown_command_stays_silent(self, architect):
        """Sonst antwortet der Bot auf jedes '!' in jedem Chat."""

        ctx = FakeContext(FakeGuild())

        await bot_module.on_command_error(
            cast("Any", ctx), commands.CommandNotFound("weg")
        )

        assert not ctx.sent

    async def test_direct_message_is_explained(self):
        ctx = FakeContext(None)

        await bot_module.on_command_error(
            cast("Any", ctx), commands.NoPrivateMessage()
        )

        assert "Nur auf Servern" in texts(ctx)

    async def test_missing_permission_is_explained(self):
        ctx = FakeContext(FakeGuild())

        await bot_module.on_command_error(
            cast("Any", ctx), commands.MissingPermissions(["manage_guild"])
        )

        assert "Keine Berechtigung" in texts(ctx)

    async def test_unexpected_errors_are_logged_not_shown(self, caplog):
        """Ein Traceback im Chat hilft niemandem — im Log schon."""

        ctx = FakeContext(FakeGuild())
        ctx.command = "start"

        with caplog.at_level("ERROR"):
            await bot_module.on_command_error(
                cast("Any", ctx), commands.CommandInvokeError(ValueError("kaputt"))
            )

        assert not ctx.sent
        assert "Command-Fehler" in caplog.text


# --------------------------------------------------------------------------- #
# Lebenszyklus
# --------------------------------------------------------------------------- #

class TestStatusRotation:
    """Die Praesenz zeigt Serverzahl und Mitglieder — beides veraendert sich."""

    async def test_numbers_are_recomputed_each_round(self, architect, monkeypatch):
        """Sonst zeigt der Bot nach dem ersten Beitritt dauerhaft 'Auf 0 Servern'."""

        shown: list[str] = []
        guilds: list = []

        class FakeGuildWithMembers:
            member_count = 50

        async def ready():
            return None

        async def presence(*, status=None, activity=None):
            shown.append(activity.name)
            # Nach der ersten Runde tritt der Bot einem Server bei.
            if len(shown) == 3:
                guilds.append(FakeGuildWithMembers())

        async def no_sleep(_seconds):
            if len(shown) >= 6:
                raise asyncio.CancelledError

        monkeypatch.setattr(architect, "wait_until_ready", ready)
        monkeypatch.setattr(architect, "change_presence", presence)
        monkeypatch.setattr(type(architect), "guilds", property(lambda self: guilds))
        monkeypatch.setattr(bot_module.asyncio, "sleep", no_sleep)
        monkeypatch.setattr(architect, "is_closed", lambda: False)

        with pytest.raises(asyncio.CancelledError):
            await architect._rotate_status()

        assert "Auf 0 Servern" in shown[1]
        assert "Auf 1 Servern" in shown[4], "Die Zahl wurde nicht aktualisiert"
        assert "50 User" in shown[5]

    async def test_template_count_is_shown(self, architect, monkeypatch):
        shown: list[str] = []

        async def ready():
            return None

        async def presence(*, status=None, activity=None):
            shown.append(activity.name)

        async def stop(_seconds):
            raise asyncio.CancelledError

        monkeypatch.setattr(architect, "wait_until_ready", ready)
        monkeypatch.setattr(architect, "change_presence", presence)
        monkeypatch.setattr(bot_module.asyncio, "sleep", stop)
        monkeypatch.setattr(architect, "is_closed", lambda: False)

        with pytest.raises(asyncio.CancelledError):
            await architect._rotate_status()

        assert str(len(architect.registry)) in shown[0]

    async def test_presence_errors_do_not_stop_the_loop(
        self, architect, monkeypatch
    ):
        """Discord lehnt Praesenz-Updates gelegentlich ab."""

        attempts: list[int] = []

        async def ready():
            return None

        async def refuse(*, status=None, activity=None):
            attempts.append(1)
            raise discord.HTTPException(_Resp(), "nein")

        async def stop(_seconds):
            if len(attempts) >= 3:
                raise asyncio.CancelledError

        monkeypatch.setattr(architect, "wait_until_ready", ready)
        monkeypatch.setattr(architect, "change_presence", refuse)
        monkeypatch.setattr(bot_module.asyncio, "sleep", stop)
        monkeypatch.setattr(architect, "is_closed", lambda: False)

        with pytest.raises(asyncio.CancelledError):
            await architect._rotate_status()

        assert len(attempts) == 3, "Ein abgelehntes Update hat die Rotation gestoppt"


class TestOnReady:
    async def test_the_rotation_starts_once(self, architect, monkeypatch):
        """on_ready feuert nach jedem Reconnect — ohne Sperre laufen viele Tasks."""

        created: list = []

        class FakeTask:
            def done(self):
                return False

            def cancel(self):
                return None

        class FakeLoop:
            @staticmethod
            def create_task(coro):
                # Die Coroutine nie starten, aber sauber schliessen — sonst
                # meldet Python "was never awaited".
                coro.close()
                created.append(coro)
                return FakeTask()

        monkeypatch.setattr(architect, "loop", FakeLoop())
        monkeypatch.setattr(type(architect), "guilds", property(lambda self: []))
        architect._status_task = None

        await architect.on_ready()
        await architect.on_ready()
        await architect.on_ready()

        assert len(created) == 1, f"{len(created)} Rotationen statt einer"

        architect._status_task = None

    async def test_a_finished_task_is_restarted(self, architect, monkeypatch):
        """Ist die Rotation gestorben, muss der naechste Reconnect sie neu starten."""

        created: list = []

        class DeadTask:
            def done(self):
                return True

            def cancel(self):
                return None

        class FakeLoop:
            @staticmethod
            def create_task(coro):
                coro.close()
                created.append(coro)
                return DeadTask()

        monkeypatch.setattr(architect, "loop", FakeLoop())
        monkeypatch.setattr(type(architect), "guilds", property(lambda self: []))
        architect._status_task = DeadTask()

        await architect.on_ready()

        assert len(created) == 1

        architect._status_task = None


class TestShutdown:
    async def test_close_cancels_the_rotation(self, architect, monkeypatch):
        """Ein weiterlaufender Task haelt den Prozess am Leben."""

        cancelled: list[bool] = []

        class Task:
            def cancel(self):
                cancelled.append(True)

            def done(self):
                return False

        async def noop_close():
            return None

        architect._status_task = Task()
        architect._health_runner = None
        monkeypatch.setattr(
            bot_module.commands.Bot, "close", lambda self: noop_close()
        )

        await architect.close()

        assert cancelled == [True]
        assert architect._status_task is None

    async def test_close_shuts_down_the_web_server(self, architect, monkeypatch):
        cleaned: list[bool] = []

        class Runner:
            async def cleanup(self):
                cleaned.append(True)

        async def noop_close():
            return None

        architect._status_task = None
        architect._health_runner = Runner()
        monkeypatch.setattr(
            bot_module.commands.Bot, "close", lambda self: noop_close()
        )

        await architect.close()

        assert cleaned == [True]
        assert architect._health_runner is None

    async def test_a_failing_cleanup_does_not_block_shutdown(
        self, architect, monkeypatch
    ):
        class BrokenRunner:
            async def cleanup(self):
                raise RuntimeError("kaputt")

        async def noop_close():
            return None

        architect._status_task = None
        architect._health_runner = BrokenRunner()
        monkeypatch.setattr(
            bot_module.commands.Bot, "close", lambda self: noop_close()
        )

        await architect.close()  # darf nicht werfen

        assert architect._health_runner is None


# --------------------------------------------------------------------------- #
# Start
# --------------------------------------------------------------------------- #

class TestSetupHook:
    """Was beim Start passieren muss, bevor der Bot brauchbar ist."""

    @pytest.fixture
    def quiet_start(self, architect, monkeypatch):
        """setup_hook ohne Netzwerk: Webserver und Slash-Sync abfangen."""

        state: dict[str, Any] = {"views": [], "synced": [], "web": False}

        def add_view(view, **kwargs):
            state["views"].append(type(view).__name__)

        async def sync(*, guild=None):
            state["synced"].append(guild)
            return []

        async def serve(bot_obj):
            state["web"] = True
            return object()

        monkeypatch.setattr(architect, "add_view", add_view)
        monkeypatch.setattr(architect.tree, "sync", sync)
        monkeypatch.setattr(architect.tree, "copy_global_to", lambda guild: None)

        import web as web_module

        monkeypatch.setattr(web_module, "start_web_server", serve)
        monkeypatch.setattr(bot_module.config, "HEALTH_SERVER", False)
        monkeypatch.setattr(bot_module.config, "DISCORD_GUILD_ID", None)
        return state

    async def test_persistent_views_are_registered(self, architect, quiet_start):
        """Ohne das sind alle angehefteten Buttons nach einem Neustart tot."""

        from ui.widgets import PERSISTENT_VIEWS

        await architect.setup_hook()

        assert len(quiet_start["views"]) == len(PERSISTENT_VIEWS)
        for view_cls in PERSISTENT_VIEWS:
            assert view_cls.__name__ in quiet_start["views"]

    async def test_slash_commands_are_synced_globally(self, architect, quiet_start):
        await architect.setup_hook()

        assert quiet_start["synced"] == [None]

    async def test_a_test_guild_gets_an_instant_sync(
        self, architect, quiet_start, monkeypatch
    ):
        """DISCORD_GUILD_ID beschleunigt das Testen — global dauert bis zu 1h."""

        monkeypatch.setattr(bot_module.config, "DISCORD_GUILD_ID", "123456789")

        await architect.setup_hook()

        assert quiet_start["synced"] and quiet_start["synced"][0] is not None

    async def test_a_failed_sync_does_not_stop_the_start(
        self, architect, quiet_start, monkeypatch, caplog
    ):
        """Lieber ohne Slash-Befehle laufen als gar nicht."""

        async def refuse(*, guild=None):
            raise discord.HTTPException(_Resp(), "abgelehnt")

        monkeypatch.setattr(architect.tree, "sync", refuse)

        with caplog.at_level("WARNING"):
            await architect.setup_hook()

        assert "Slash-Sync fehlgeschlagen" in caplog.text

    async def test_an_invalid_guild_id_is_survivable(
        self, architect, quiet_start, monkeypatch, caplog
    ):
        """int('abc') wirft ValueError — abgefangen wie ein HTTP-Fehler."""

        monkeypatch.setattr(bot_module.config, "DISCORD_GUILD_ID", "keine-zahl")

        with caplog.at_level("WARNING"):
            await architect.setup_hook()

        assert "Slash-Sync fehlgeschlagen" in caplog.text

    async def test_the_web_server_starts_when_enabled(
        self, architect, quiet_start, monkeypatch
    ):
        """Railway prueft /health — ohne Webserver gilt der Deploy als tot."""

        monkeypatch.setattr(bot_module.config, "HEALTH_SERVER", True)

        await architect.setup_hook()

        assert quiet_start["web"], "Der Health-Server wurde nicht gestartet"
        architect._health_runner = None

    async def test_missing_intents_are_announced(
        self, architect, quiet_start, monkeypatch, caplog
    ):
        monkeypatch.setattr(bot_module.config, "ENABLE_PRIVILEGED_INTENTS", False)

        with caplog.at_level("WARNING"):
            await architect.setup_hook()

        assert "Privileged Intents" in caplog.text

    async def test_missing_premium_key_is_announced(
        self, architect, quiet_start, monkeypatch, caplog
    ):
        """Der Betreiber soll wissen, dass Premium nicht freischaltbar ist."""

        monkeypatch.setattr(
            type(architect.premium), "is_configured", property(lambda self: False)
        )

        with caplog.at_level("WARNING"):
            await architect.setup_hook()

        assert "PREMIUM_KEY" in caplog.text

    async def test_a_configured_licence_is_announced(
        self, architect, quiet_start, monkeypatch, caplog
    ):
        monkeypatch.setattr(
            type(architect.licence), "is_configured", property(lambda self: True)
        )

        with caplog.at_level("INFO"):
            await architect.setup_hook()

        assert "Lizenzabfrage aktiv" in caplog.text

    async def test_transferred_emojis_are_announced(
        self, architect, quiet_start, monkeypatch, caplog
    ):
        import ui.emojis as emojis

        monkeypatch.setattr(emojis, "has_emojis", lambda: True)
        monkeypatch.setattr(emojis, "EMOJIS", {"premium": "123"})

        with caplog.at_level("INFO"):
            await architect.setup_hook()

        assert "eigene Emojis aktiv" in caplog.text


class TestMain:
    """``main()`` uebersetzt Startfehler in Klartext statt Stacktraces."""

    def test_missing_token_exits_with_a_hint(self, monkeypatch, capsys):
        monkeypatch.setattr(bot_module.config, "DISCORD_TOKEN", None)

        with pytest.raises(SystemExit) as excinfo:
            bot_module.main()

        assert excinfo.value.code == 1
        assert "DISCORD_TOKEN" in capsys.readouterr().err

    def test_an_invalid_token_is_explained(self, monkeypatch, capsys):
        monkeypatch.setattr(bot_module.config, "DISCORD_TOKEN", "ungueltig")

        def refuse(token, **kwargs):
            raise discord.LoginFailure("nope")

        monkeypatch.setattr(bot_module.bot, "run", refuse)

        with pytest.raises(SystemExit):
            bot_module.main()

        error = capsys.readouterr().err
        assert "Token ungültig" in error
        assert "Developer Portal" in error, "Der Ausweg wird nicht genannt"

    def test_missing_intents_are_explained(self, monkeypatch, capsys):
        monkeypatch.setattr(bot_module.config, "DISCORD_TOKEN", "x")

        def refuse(token, **kwargs):
            raise discord.PrivilegedIntentsRequired(shard_id=None)

        monkeypatch.setattr(bot_module.bot, "run", refuse)

        with pytest.raises(SystemExit):
            bot_module.main()

        error = capsys.readouterr().err
        assert "Privileged Intents" in error
        assert "ENABLE_PRIVILEGED_INTENTS" in error

    def test_a_network_problem_shows_no_traceback(self, monkeypatch, capsys):
        """Kein Bug, sondern Umgebung — ein Stacktrace waere irrefuehrend."""

        monkeypatch.setattr(bot_module.config, "DISCORD_TOKEN", "x")

        def refuse(token, **kwargs):
            raise OSError("Name or service not known")

        monkeypatch.setattr(bot_module.bot, "run", refuse)

        with pytest.raises(SystemExit):
            bot_module.main()

        error = capsys.readouterr().err
        assert "Keine Verbindung" in error
        assert "Traceback" not in error

    def test_a_clean_run_does_not_exit(self, monkeypatch):
        monkeypatch.setattr(bot_module.config, "DISCORD_TOKEN", "x")
        monkeypatch.setattr(bot_module.bot, "run", lambda token, **kwargs: None)

        bot_module.main()


class TestMainGuard:
    """Der ``__main__``-Block: Template-Fehler und Ctrl-C bleiben hoeflich.

    ``runpy.run_path`` fuehrt bot.py in einem frischen Namensraum aus —
    Module wie ``config`` und die Klasse ``Bot`` kommen aber aus dem Cache
    und lassen sich deshalb hier ueber ``bot_module`` steuern.
    """

    def test_the_guard_runs_main(self, monkeypatch):
        monkeypatch.setattr(bot_module.config, "DISCORD_TOKEN", "x")
        monkeypatch.setattr(
            bot_module.commands.Bot, "run", lambda self, token, **kwargs: None
        )

        runpy.run_path(str(BASE_DIR / "bot.py"), run_name="__main__")

    def test_a_template_error_exits_cleanly(self, monkeypatch):
        from core.schema import TemplateError

        monkeypatch.setattr(bot_module.config, "DISCORD_TOKEN", "x")

        def boom(self, token, **kwargs):
            raise TemplateError("kaputte Vorlage")

        monkeypatch.setattr(bot_module.commands.Bot, "run", boom)

        with pytest.raises(SystemExit) as excinfo:
            runpy.run_path(str(BASE_DIR / "bot.py"), run_name="__main__")

        assert excinfo.value.code == 1

    def test_keyboard_interrupt_is_silent(self, monkeypatch):
        monkeypatch.setattr(bot_module.config, "DISCORD_TOKEN", "x")

        def boom(self, token, **kwargs):
            raise KeyboardInterrupt

        monkeypatch.setattr(bot_module.commands.Bot, "run", boom)

        runpy.run_path(str(BASE_DIR / "bot.py"), run_name="__main__")
