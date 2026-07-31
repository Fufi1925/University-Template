"""End-to-end build simulation against a fake guild.

The builder is the one component that mutates a real server, so it needs to be
exercised without touching Discord. These fakes implement just enough of the
API surface (create_*, edit, delete, permission overwrites) to prove:

* every channel and role of a template is actually created
* a second run in EXTEND mode changes nothing (idempotency)
* REBUILD wipes first and respects undeletable objects
* private categories never end up visible to @everyone
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import discord

import config
from core.builder import BuildError, BuildMode, BuildReport, ServerBuilder
from core.registry import TemplateRegistry
from core.schema import Visibility

# --------------------------------------------------------------------------- #
# Fakes
# --------------------------------------------------------------------------- #

class FakeRole:
    def __init__(self, guild, name, position, *, managed=False, default=False, **kwargs):
        self.guild = guild
        self.name = name
        self.position = position
        self.managed = managed
        self._default = default
        self.colour = kwargs.get("colour")
        self.permissions = kwargs.get("permissions")
        self.hoist = kwargs.get("hoist", False)
        self.mentionable = kwargs.get("mentionable", False)
        self.deleted = False
        self.edits = 0

    def is_default(self):
        return self._default

    def is_assignable(self):
        return not self._default and not self.managed and self.position < self.guild.bot_top

    def __lt__(self, other):
        return self.position < other.position

    def __le__(self, other):
        return self.position <= other.position

    def __gt__(self, other):
        return self.position > other.position

    def __ge__(self, other):
        return self.position >= other.position

    def __hash__(self):
        return id(self)

    async def edit(self, **kwargs):
        kwargs.pop("reason", None)
        self.edits += 1
        for key, value in kwargs.items():
            setattr(self, key, value)

    async def delete(self, reason=None):
        if self.guild.undeletable_roles and self.name in self.guild.undeletable_roles:
            raise discord.Forbidden(_FakeResponse(), "nope")
        self.deleted = True
        self.guild.roles.remove(self)


class _FakeResponse:
    status = 400
    reason = "Bad Request"


async def _bulk_noop(self, guild_id, data, reason=None):
    """Sammel-Endpunkt fuer Kanalpositionen — hier nur mitgezaehlt."""

    _BULK_CALLS.append(list(data))


_BULK_CALLS: list[list[dict]] = []


def _components_from_view(view):
    """Baut aus einer LayoutView die Objekte, die Discord zurueckliefert."""

    if view is None:
        return []
    from discord.components import _component_factory

    return [_component_factory(raw) for raw in view.to_components()]


class FakeChannel:
    _next_id = 700_000_000_000_000_000

    def __init__(self, guild, name, kind, category=None, **kwargs):
        FakeChannel._next_id += 1
        self.id = FakeChannel._next_id
        self.guild = guild
        self.name = name
        self.kind = kind
        self.category = category
        self.overwrites = kwargs.get("overwrites", {})
        self.topic = kwargs.get("topic")
        self.slowmode_delay = kwargs.get("slowmode_delay", 0)
        self.user_limit = kwargs.get("user_limit", 0)
        self.nsfw = kwargs.get("nsfw", False)
        self.position = kwargs.get("position", 0)
        self.deleted = False
        self.edits = 0
        self.sent: list[FakeMessage] = []
        self.pinned: list[FakeMessage] = []
        self.can_send = True

    async def send(self, content=None, view=None, **kwargs):
        if not self.can_send:
            raise discord.Forbidden(_FakeResponse(), "no")
        # Discord lehnt content zusammen mit Components V2 ab. Reine
        # Textnachrichten ohne View (z. B. die Start-1 im Zaehl-Kanal)
        # sind dagegen voellig in Ordnung.
        assert not (content and view), (
            "content darf nicht zusammen mit einer Components-V2-View gesendet werden"
        )
        message = FakeMessage(self, content=content, view=view)
        self.sent.append(message)
        return message

    async def pins(self):
        return list(self.pinned)

    async def edit(self, **kwargs):
        kwargs.pop("reason", None)
        self.edits += 1
        for key, value in kwargs.items():
            setattr(self, key, value)

    async def delete(self, reason=None):
        # Das Objekt bleibt im Cache stehen — genau so verhaelt sich
        # discord.py, bis das Gateway-Event eintrifft. Der Builder muss
        # selbst aufraeumen, sonst baut er auf Karteileichen.
        self.deleted = True

    def __hash__(self):
        return id(self)


class FakeMessage:
    """Nachricht mit genau den Faehigkeiten, die der Builder nutzt.

    Wichtig: ``components`` wird aus der View rekonstruiert — genau wie
    Discord es tut. Nur so prueft der Idempotenz-Test wirklich, ob der Bot
    seine eigene Nachricht anhand der Signatur in der Fusszeile wiederfindet.
    """

    def __init__(self, channel, content=None, view=None):
        self.channel = channel
        # Components V2 erlaubt kein content-Feld; Discord liefert "".
        self.content = content or ""
        self.view = view
        self.author = channel.guild.me
        self.edits = 0
        self.components = _components_from_view(view)

    async def edit(self, content=None, view=None, **kwargs):
        self.edits += 1
        if content is not None:
            self.content = content
        if view is not None:
            self.view = view
            self.components = _components_from_view(view)

    async def pin(self, reason=None):
        if self not in self.channel.pinned:
            self.channel.pinned.append(self)


class FakeCategory(FakeChannel):
    def __init__(self, guild, name, **kwargs):
        super().__init__(guild, name, "category", **kwargs)
        self._children: list[FakeChannel] = []

    @property
    def channels(self):
        return [c for c in self._children if not getattr(c, "deleted", False)]


class FakeMember:
    def __init__(self, guild, top_role):
        self.guild = guild
        self.top_role = top_role
        self.guild_permissions = discord.Permissions.all()
        self.id = 999_000_001
        self.bot = True


class FakeGuild:
    """Minimal guild good enough for the builder."""

    def __init__(self, *, bot_top=1000, undeletable_roles=None):
        self.id = 555_000_000_000_000_001
        self.roles: list[FakeRole] = []
        self.features: list[str] = []
        self.bot_top = bot_top
        self.undeletable_roles = undeletable_roles or set()
        self._position = 0

        self.default_role = FakeRole(self, "@everyone", 0, default=True)
        self.roles.append(self.default_role)
        self._bot_role = FakeRole(self, "ArchitectBot", bot_top, managed=True)
        self.roles.append(self._bot_role)
        self.me = FakeMember(self, self._bot_role)

        self.created_channels = 0
        self.created_roles = 0
        self.created_categories = 0

        # Wie discord.py: der Cache haelt Kanaele, bis das Gateway die
        # Loeschung meldet. Der Builder raeumt ihn selbst auf.
        self._channels: dict[int, object] = {}
        self._state = type(
            "S", (), {"http": type("H", (), {"bulk_channel_update": _bulk_noop})()}
        )()
        self.bulk_updates: list[list[dict]] = []

    @property
    def channels(self):
        """Wie discord.py: die Liste kommt aus dem Cache."""

        return list(self._channels.values())

    @property
    def categories(self):
        return [c for c in self._channels.values() if isinstance(c, FakeCategory)]

    def _next(self):
        self._position += 1
        return self._position

    async def create_role(self, **kwargs):
        kwargs.pop("reason", None)
        name = kwargs.pop("name")
        role = FakeRole(self, name, self._next(), **kwargs)
        self.roles.append(role)
        self.created_roles += 1
        return role

    async def create_category(self, name, **kwargs):
        kwargs.pop("reason", None)
        category = FakeCategory(self, name, **kwargs)
        self._channels[category.id] = category
        self.created_categories += 1
        return category

    async def _make(self, name, kind, category=None, **kwargs):
        kwargs.pop("reason", None)
        # Wie Discord: ein Kanal unter einer nicht mehr existierenden
        # Kategorie wird abgelehnt.
        if category is not None and category.id not in self._channels:
            raise discord.HTTPException(
                _FakeResponse(), "In parent_id: Category does not exist"
            )
        channel = FakeChannel(self, name, kind, category=category, **kwargs)
        self._channels[channel.id] = channel
        if category is not None:
            category._children.append(channel)
        self.created_channels += 1
        return channel

    async def create_text_channel(self, name, **kwargs):
        return await self._make(name, "text", **kwargs)

    async def create_voice_channel(self, name, **kwargs):
        return await self._make(name, "voice", **kwargs)

    async def create_stage_channel(self, name, **kwargs):
        return await self._make(name, "stage", **kwargs)

    async def create_forum(self, name, **kwargs):
        return await self._make(name, "forum", **kwargs)

    async def edit_role_positions(self, positions=None, reason=None):
        for role, position in (positions or {}).items():
            role.position = position


@pytest.fixture(scope="module")
def registry():
    return TemplateRegistry(config.TEMPLATE_DIR).load()


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    """Strip the rate-limit throttle so the suite stays fast."""

    async def instant(_seconds):
        return None

    monkeypatch.setattr("core.builder.asyncio.sleep", instant)


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
class TestBuildSimulation:
    async def test_extend_creates_everything(self, registry):
        template = registry.get("community")
        guild = FakeGuild()
        report = await ServerBuilder(guild, template).apply(BuildMode.EXTEND)

        assert report.categories_created == template.category_count
        assert report.channels_created == template.channel_count
        assert guild.created_channels == template.channel_count
        assert report.roles_created == 13 + len(template.roles)

    async def test_second_run_is_a_noop(self, registry):
        """Idempotency: running EXTEND twice must not duplicate anything."""

        template = registry.get("rp")
        guild = FakeGuild()
        await ServerBuilder(guild, template).apply(BuildMode.EXTEND)
        before = len(guild.channels), len(guild.roles)

        second = await ServerBuilder(guild, template).apply(BuildMode.EXTEND)

        assert (len(guild.channels), len(guild.roles)) == before
        assert second.channels_created == 0
        assert second.categories_created == 0
        assert second.roles_created == 0

    async def test_recognises_plain_named_channels(self, registry):
        """A pre-existing 'general' must not be duplicated as '💬・ɢᴇɴᴇʀᴀʟ'."""

        template = registry.get("community")
        guild = FakeGuild()
        await ServerBuilder(guild, template).apply(BuildMode.EXTEND)

        general = [c for c in guild.channels if "general" in c.name.lower() or "ɢᴇɴᴇʀᴀʟ" in c.name]
        names = [c.name for c in general]
        assert len(names) == len(set(names))

    async def test_all_templates_build(self, registry):
        for template in registry:
            guild = FakeGuild()
            report = await ServerBuilder(guild, template).apply(BuildMode.EXTEND)
            assert report.channels_created == template.channel_count, template.key
            assert not report.warnings, f"{template.key}: {report.warnings}"

    async def test_rebuild_wipes_first(self, registry):
        template = registry.get("social")
        guild = FakeGuild()

        # Pre-populate with junk that should disappear.
        await guild.create_category("old category")
        await guild.create_text_channel("old-channel")
        await guild.create_role(name="Old Role")

        report = await ServerBuilder(guild, template).apply(BuildMode.REBUILD)

        assert report.deleted_channels >= 2
        assert report.deleted_roles >= 1
        assert not any(c.name == "old-channel" for c in guild.channels)
        assert report.channels_created == template.channel_count

    async def test_rebuild_survives_undeletable_role(self, registry):
        template = registry.get("community")
        guild = FakeGuild(undeletable_roles={"Protected"})
        await guild.create_role(name="Protected")

        report = await ServerBuilder(guild, template).apply(BuildMode.REBUILD)

        assert report.undeletable >= 1
        assert report.warnings, "Der Nutzer muss darüber informiert werden"
        assert report.channels_created == template.channel_count

    async def test_private_categories_hide_everyone(self, registry):
        """The critical safety property: logs must never be public."""

        template = registry.get("community")
        guild = FakeGuild()
        await ServerBuilder(guild, template).apply(BuildMode.EXTEND)

        private_labels = {
            category.display_name
            for category in template.categories
            if category.visibility
            in {Visibility.STAFF, Visibility.LEADERSHIP, Visibility.VIP}
        }
        assert private_labels

        for category in guild.categories:
            if category.name not in private_labels:
                continue
            overwrite = category.overwrites.get(guild.default_role)
            assert overwrite is not None, f"{category.name} hat kein @everyone-Overwrite"
            assert overwrite.view_channel is False, f"{category.name} ist sichtbar!"

    async def test_gate_is_visible_to_unverified(self, registry):
        template = registry.get("community")
        guild = FakeGuild()
        await ServerBuilder(guild, template).apply(BuildMode.EXTEND)

        gate_names = {
            c.display_name for c in template.categories if c.visibility is Visibility.GATE
        }
        for category in guild.categories:
            if category.name in gate_names:
                overwrite = category.overwrites.get(guild.default_role)
                assert overwrite is not None
                assert overwrite.view_channel is True

    async def test_public_categories_hide_unverified(self, registry):
        template = registry.get("community")
        guild = FakeGuild()
        await ServerBuilder(guild, template).apply(BuildMode.EXTEND)

        unverified = next(r for r in guild.roles if "Unverified" in r.name)
        public_names = {
            c.display_name for c in template.categories if c.visibility is Visibility.PUBLIC
        }
        checked = 0
        for category in guild.categories:
            if category.name not in public_names:
                continue
            overwrite = category.overwrites.get(unverified)
            assert overwrite is not None and overwrite.view_channel is False
            checked += 1
        assert checked > 0

    async def test_voice_limits_are_applied(self, registry):
        template = registry.get("social")
        guild = FakeGuild()
        await ServerBuilder(guild, template).apply(BuildMode.EXTEND)

        expected = {
            ch.display_name: ch.user_limit
            for _, ch in template.iter_channels()
            if ch.kind.value == "voice" and ch.user_limit
        }
        assert expected
        for channel in guild.channels:
            if channel.name in expected:
                assert channel.user_limit == expected[channel.name]

    async def test_only_owner_role_is_admin(self, registry):
        template = registry.get("community")
        guild = FakeGuild()
        await ServerBuilder(guild, template).apply(BuildMode.EXTEND)

        admins = [
            r for r in guild.roles
            if getattr(r, "permissions", None) is not None and r.permissions.administrator
        ]
        assert len(admins) == 1
        assert "Inhaber" in admins[0].name

    async def test_preflight_rejects_missing_permissions(self, registry):
        guild = FakeGuild()
        guild.me.guild_permissions = discord.Permissions.none()

        with pytest.raises(BuildError, match="Berechtigungen"):
            ServerBuilder(guild, registry.get("community")).preflight()

    async def test_preflight_rejects_channel_overflow(self, registry):
        guild = FakeGuild()
        for index in range(450):
            await guild.create_text_channel(f"filler-{index}")

        with pytest.raises(BuildError, match="500"):
            ServerBuilder(guild, registry.get("community")).preflight()

    async def test_progress_hook_reports_completion(self, registry):
        template = registry.get("study")
        guild = FakeGuild()
        seen: list[tuple[int, int]] = []

        async def hook(_label, step, total):
            seen.append((step, total))

        await ServerBuilder(guild, template).apply(BuildMode.EXTEND, progress=hook)

        assert seen
        assert seen[-1][0] == seen[-1][1], "Fortschritt endet nicht bei 100%"

    async def test_progress_failure_does_not_break_build(self, registry):
        template = registry.get("community")
        guild = FakeGuild()

        async def broken(_label, _step, _total):
            raise RuntimeError("boom")

        report = await ServerBuilder(guild, template).apply(BuildMode.EXTEND, progress=broken)
        assert report.channels_created == template.channel_count


# --------------------------------------------------------------------------- #
# Kanalinhalte
# --------------------------------------------------------------------------- #

@pytest.fixture
def text_channel_patch(monkeypatch):
    """Lässt den Builder FakeChannel als Textkanal akzeptieren.

    Der Produktivcode prüft ``isinstance(channel, discord.TextChannel)``. Statt
    diese sinnvolle Prüfung aufzuweichen, wird sie hier für die Dauer des Tests
    auf die Fakes ausgeweitet.
    """

    import core.builder as builder_module

    real_isinstance = builder_module.isinstance if hasattr(builder_module, "isinstance") else isinstance

    def patched(obj, cls):
        if cls is discord.TextChannel:
            return isinstance(obj, FakeChannel) and not isinstance(obj, FakeCategory) \
                and obj.kind in {"text", "news", "forum"}
        if cls is discord.VoiceChannel:
            return isinstance(obj, FakeChannel) and obj.kind in {"voice", "stage"}
        return real_isinstance(obj, cls)

    monkeypatch.setattr(builder_module, "isinstance", patched, raising=False)
    return patched


@pytest.mark.asyncio
class TestChannelIntros:
    async def test_intros_are_written_and_pinned(self, registry, text_channel_patch):
        template = registry.get("community")
        guild = FakeGuild()
        report = await ServerBuilder(guild, template).apply(BuildMode.EXTEND)

        assert report.messages_posted > 0, "Es wurde keine Startnachricht geschrieben"
        assert report.messages_pinned == report.messages_posted

        expected = sum(
            1 for _, spec in template.iter_channels() if spec.wants_message
        )
        assert report.messages_posted == expected

    async def test_voice_channels_stay_empty(self, registry, text_channel_patch):
        template = registry.get("social")
        guild = FakeGuild()
        await ServerBuilder(guild, template).apply(BuildMode.EXTEND)

        for channel in guild.channels:
            if channel.kind in {"voice", "stage"}:
                assert not channel.sent, f"{channel.name} hat eine Nachricht bekommen"

    async def test_second_run_edits_instead_of_duplicating(self, registry, text_channel_patch):
        """Der wichtigste Test: kein Zuspammen beim erneuten Anwenden."""

        template = registry.get("community")
        guild = FakeGuild()
        await ServerBuilder(guild, template).apply(BuildMode.EXTEND)

        counts = {c.name: len(c.sent) for c in guild.channels}
        second = await ServerBuilder(guild, template).apply(BuildMode.EXTEND)

        assert second.messages_posted == 0, "Zweiter Lauf hat erneut gepostet"
        assert second.messages_updated > 0, "Bestehende Nachricht wurde nicht bearbeitet"
        for channel in guild.channels:
            assert len(channel.sent) == counts[channel.name], (
                f"{channel.name} hat eine doppelte Nachricht"
            )

    async def test_intros_can_be_switched_off(self, registry, text_channel_patch):
        template = registry.get("community")
        guild = FakeGuild()
        report = await ServerBuilder(guild, template).apply(
            BuildMode.EXTEND, write_intros=False
        )

        assert report.messages_posted == 0
        assert all(not c.sent for c in guild.channels)
        # Die Struktur muss trotzdem vollständig sein.
        assert report.channels_created == template.channel_count

    async def test_counting_channel_gets_seeded(self, registry, text_channel_patch):
        template = registry.get("community")
        guild = FakeGuild()
        await ServerBuilder(guild, template).apply(BuildMode.EXTEND)

        counting = [c for c in guild.channels if "ᴢᴀᴇʜʟᴇɴ" in c.name]
        assert counting, "Zähl-Kanal nicht gefunden"
        contents = [m.content for m in counting[0].sent]
        assert "1" in contents, "Der Zähl-Kanal wurde nicht mit 1 gestartet"

    async def test_topic_carries_mode_marker(self, registry, text_channel_patch):
        """Ohne die Marke im Topic kennt der Listener den Modus nach einem Neustart nicht."""

        from core.enforcement import read_mode
        from core.schema import ChannelMode

        template = registry.get("community")
        guild = FakeGuild()
        await ServerBuilder(guild, template).apply(BuildMode.EXTEND)

        memes = [c for c in guild.channels if "ᴍᴇᴍᴇꜱ" in c.name]
        assert memes
        assert read_mode(memes[0]) is ChannelMode.MEDIA

    async def test_no_write_permission_is_reported_not_fatal(self, registry, text_channel_patch):
        template = registry.get("business")
        guild = FakeGuild()

        original = FakeGuild._make

        async def make_locked(self, name, kind, category=None, **kwargs):
            channel = await original(self, name, kind, category=category, **kwargs)
            channel.can_send = False
            return channel

        FakeGuild._make = make_locked
        try:
            report = await ServerBuilder(guild, template).apply(BuildMode.EXTEND)
        finally:
            FakeGuild._make = original

        assert report.channels_created == template.channel_count
        assert report.messages_posted == 0
        assert any("schreiben" in w for w in report.warnings)

    async def test_progress_accounts_for_second_phase(self, registry, text_channel_patch):
        template = registry.get("study")
        guild = FakeGuild()
        seen: list[tuple[int, int]] = []

        async def hook(_label, step, total):
            seen.append((step, total))

        await ServerBuilder(guild, template).apply(BuildMode.EXTEND, progress=hook)

        assert seen[-1][0] == seen[-1][1], "Fortschritt endet nicht bei 100%"
        assert seen[-1][1] > template.category_count + 1, (
            "Die Schreibphase fehlt im Fortschritt"
        )

    async def test_all_templates_write_without_warnings(self, registry, text_channel_patch):
        for template in registry:
            guild = FakeGuild()
            report = await ServerBuilder(guild, template).apply(BuildMode.EXTEND)
            assert report.messages_posted > 0, template.key
            assert not report.warnings, f"{template.key}: {report.warnings}"


# --------------------------------------------------------------------------- #
# Regressionen aus dem Produktivbetrieb
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
class TestProductionRegressions:
    """Fehler, die auf einem echten Server aufgetreten sind."""

    async def test_rebuild_does_not_use_deleted_categories(
        self, registry, text_channel_patch
    ):
        """400 Invalid Form Body — In parent_id: Category does not exist.

        Nach dem Wipe standen die gelöschten Kategorien noch im Cache. Der
        Builder fand sie über ``guild.categories``, hielt sie für vorhanden
        und legte Kanäle unter einer parent_id an, die es nicht mehr gab.
        Vier Kanäle fehlten dadurch auf dem Server.
        """

        template = registry.get("community")
        guild = FakeGuild()

        # Erst befüllen, dann neu aufsetzen — so entstehen Karteileichen.
        await ServerBuilder(guild, template).apply(BuildMode.EXTEND)
        report = await ServerBuilder(guild, template).apply(BuildMode.REBUILD)

        assert report.channels_created == template.channel_count, (
            "Es fehlen Kanäle — vermutlich wieder eine tote Kategorie im Cache"
        )
        assert not any(
            "parent_id" in warning or "Category does not exist" in warning
            for warning in report.warnings
        ), report.warnings

    async def test_deleted_channels_leave_the_cache(self, registry, text_channel_patch):
        """Der Cache darf nach dem Wipe keine gelöschten Kanäle mehr führen."""

        template = registry.get("business")
        guild = FakeGuild()
        await ServerBuilder(guild, template).apply(BuildMode.EXTEND)

        before = len(guild._channels)
        builder = ServerBuilder(guild, template)
        await builder._wipe(BuildReport(mode=BuildMode.REBUILD, template_key="x"))

        assert len(guild._channels) < before, "Der Cache wurde nicht aufgeräumt"
        for category in guild.categories:
            assert category.id in guild._channels

    async def test_category_order_uses_one_bulk_request(
        self, registry, text_channel_patch
    ):
        """429 Too Many Requests beim Sortieren.

        Vorher: ein PATCH pro Kategorie auf denselben Endpunkt. Bei 15
        Kategorien antwortete Discord mit 429 und ließ den Bot minutenlang
        warten. Jetzt setzt ein einziger Request alle Positionen.
        """

        template = registry.get("community")
        guild = FakeGuild()
        _BULK_CALLS.clear()

        await ServerBuilder(guild, template).apply(BuildMode.REBUILD)

        assert len(_BULK_CALLS) == 1, (
            f"{len(_BULK_CALLS)} Sortier-Requests statt einem — "
            "das provoziert wieder 429er"
        )
        assert len(_BULK_CALLS[0]) == template.category_count

    async def test_bulk_order_carries_correct_positions(
        self, registry, text_channel_patch
    ):
        template = registry.get("rp")
        guild = FakeGuild()
        _BULK_CALLS.clear()

        await ServerBuilder(guild, template).apply(BuildMode.REBUILD)

        positions = [entry["position"] for entry in _BULK_CALLS[0]]
        assert positions == sorted(positions), "Positionen sind nicht aufsteigend"
        assert positions == list(range(len(positions)))

    async def test_failed_ordering_does_not_break_the_build(
        self, registry, text_channel_patch, monkeypatch
    ):
        """Die Reihenfolge ist Kosmetik — der Aufbau zählt."""

        async def refuse(self, guild_id, data, reason=None):
            raise discord.HTTPException(_FakeResponse(), "nope")

        template = registry.get("support")
        guild = FakeGuild()
        monkeypatch.setattr(guild._state.http.__class__, "bulk_channel_update", refuse)

        report = await ServerBuilder(guild, template).apply(BuildMode.REBUILD)

        assert report.channels_created == template.channel_count
        assert any("Reihenfolge" in warning for warning in report.warnings)

    async def test_all_templates_survive_a_rebuild(self, registry, text_channel_patch):
        """Der Fall aus dem Log: bestehender Server wird neu aufgesetzt."""

        for template in registry:
            guild = FakeGuild()
            await ServerBuilder(guild, template).apply(BuildMode.EXTEND)
            report = await ServerBuilder(guild, template).apply(BuildMode.REBUILD)

            assert report.channels_created == template.channel_count, (
                f"{template.key}: {report.channels_created} statt "
                f"{template.channel_count} Kanälen"
            )
            assert not report.warnings, f"{template.key}: {report.warnings}"

    async def test_vanishing_category_is_recovered(self, registry, text_channel_patch):
        """Das exakte Szenario aus dem Log.

        Eine Kategorie verschwindet mitten im Aufbau — etwa weil ein anderer
        Bot aufräumt. Discord antwortet mit *In parent_id: Category does not
        exist*. Vorher fehlten dadurch alle folgenden Kanäle dieser Kategorie
        dauerhaft (im Log waren es vier). Jetzt wird die Kategorie neu
        angelegt und der Kanal erneut versucht.
        """

        template = registry.get("community")
        guild = FakeGuild()
        state = {"sabotaged": False}

        original = FakeGuild._make

        async def vanish_once(self, name, kind, category=None, **kwargs):
            # Beim vierten Kanal die Kategorie unter den Füßen wegziehen.
            if (
                not state["sabotaged"]
                and category is not None
                and len(category._children) == 3
            ):
                state["sabotaged"] = True
                self._channels.pop(category.id, None)
            return await original(self, name, kind, category=category, **kwargs)

        FakeGuild._make = vanish_once
        try:
            report = await ServerBuilder(guild, template).apply(BuildMode.EXTEND)
        finally:
            FakeGuild._make = original

        assert state["sabotaged"], "Die Sabotage hat nie gegriffen"
        assert report.channels_created == template.channel_count, (
            f"{template.channel_count - report.channels_created} Kanäle fehlen — "
            "die Kategorie wurde nicht wiederhergestellt"
        )

    async def test_unrecoverable_error_is_reported_not_swallowed(
        self, registry, text_channel_patch
    ):
        """Andere Fehler dürfen nicht als Kategorie-Problem gedeutet werden."""

        template = registry.get("support")
        guild = FakeGuild()
        original = FakeGuild._make
        state = {"done": False}

        async def fail_once(self, name, kind, category=None, **kwargs):
            if not state["done"] and kind == "text":
                state["done"] = True
                raise discord.HTTPException(_FakeResponse(), "Something else broke")
            return await original(self, name, kind, category=category, **kwargs)

        FakeGuild._make = fail_once
        try:
            report = await ServerBuilder(guild, template).apply(BuildMode.EXTEND)
        finally:
            FakeGuild._make = original

        assert report.warnings, "Der Fehler wurde stillschweigend verschluckt"
        assert report.channels_created == template.channel_count - 1
