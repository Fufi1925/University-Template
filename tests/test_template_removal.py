"""Das Entfernen von Strukturen: ``unapply`` und ``wipe_guild``.

Dieselbe Sorgfalt wie beim Bauen, nur rueckwaerts:

* **``unapply``** loescht genau, was zur Vorlage passt — und laesst die
  geteilte Basis-Leiter stehen. Fremde Kanaele in einer passenden Kategorie
  bleiben unangetastet; die Kategorie faellt nur, wenn sie danach leer ist.
* **``wipe_guild``** loescht alles Loeschbare. @everyone und
  Integrationsrollen sind tabu.

Gefahren wird gegen die nachgebildete Guild (gleiche Bauart wie in
``test_build_simulation.py``): erst bauen, dann entfernen, dann nachzaehlen.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import discord

import config
from core.builder import BuildMode, ServerBuilder, wipe_guild
from core.permissions import BASE_ROLES
from core.registry import TemplateRegistry
from core.small_caps import role_name

# --------------------------------------------------------------------------- #
# Attrappen
# --------------------------------------------------------------------------- #

_CHANNEL_TYPES = {
    "text": discord.ChannelType.text,
    "voice": discord.ChannelType.voice,
    "stage": discord.ChannelType.stage_voice,
    "forum": discord.ChannelType.forum,
    "news": discord.ChannelType.news,
    "category": discord.ChannelType.category,
}


class _FakeResponse:
    status = 400
    reason = "Bad Request"


class FakeRole:
    _next_id = 800_000_000_000_000_000

    def __init__(self, guild, name, position, *, managed=False, default=False, **kwargs):
        FakeRole._next_id += 1
        self.id = FakeRole._next_id
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

    async def delete(self, reason=None):
        if self.guild.undeletable_roles and self.name in self.guild.undeletable_roles:
            raise discord.Forbidden(_FakeResponse(), "nope")
        if getattr(self.guild, "missing_roles", set()) and self.name in self.guild.missing_roles:
            raise discord.NotFound(_FakeResponse(), "already gone")
        self.deleted = True
        self.guild.roles.remove(self)


class FakeChannel:
    _next_id = 700_000_000_000_000_000

    def __init__(self, guild, name, kind, category=None, **kwargs):
        FakeChannel._next_id += 1
        self.id = FakeChannel._next_id
        self.guild = guild
        self.name = name
        self.kind = kind
        self.category = category
        self.position = kwargs.get("position", 0)
        self.deleted = False

    @property
    def type(self):
        return _CHANNEL_TYPES[self.kind]

    async def delete(self, reason=None):
        # Wie discord.py: das Objekt bleibt im Cache, bis der Builder
        # selbst aufraeumt.
        blocked = getattr(self.guild, "undeletable_channels", set())
        gone = getattr(self.guild, "missing_channels", set())
        if self.name in blocked:
            raise discord.Forbidden(_FakeResponse(), "nope")
        if self.name in gone:
            raise discord.NotFound(_FakeResponse(), "already gone")
        self.deleted = True


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
    """Minimal-Guild, gut genug fuer Bauen *und* Entfernen."""

    def __init__(self, *, bot_top=1000, undeletable_roles=None):
        self.id = 555_000_000_000_000_001
        self.roles: list[FakeRole] = []
        self.features: list[str] = []
        self.bot_top = bot_top
        self.undeletable_roles = undeletable_roles or set()
        self.missing_roles: set[str] = set()
        self.undeletable_channels: set[str] = set()
        self.missing_channels: set[str] = set()
        self._position = 0

        self.default_role = FakeRole(self, "@everyone", 0, default=True)
        self.roles.append(self.default_role)
        self._bot_role = FakeRole(self, "ArchitectBot", bot_top, managed=True)
        self.roles.append(self._bot_role)
        self.me = FakeMember(self, self._bot_role)

        self._channels: dict[int, object] = {}

    @property
    def channels(self):
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
        return role

    async def create_category(self, name, **kwargs):
        kwargs.pop("reason", None)
        category = FakeCategory(self, name, **kwargs)
        self._channels[category.id] = category
        return category

    async def _make(self, name, kind, category=None, **kwargs):
        kwargs.pop("reason", None)
        channel = FakeChannel(self, name, kind, category=category, **kwargs)
        self._channels[channel.id] = channel
        if category is not None:
            category._children.append(channel)
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

    async def edit(self, **kwargs):
        return None


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    """Der Throttle ist fuer echte Server gedacht, nicht fuer Tests."""

    async def instant(_seconds):
        return None

    monkeypatch.setattr("core.builder.asyncio.sleep", instant)


@pytest.fixture(scope="module")
def registry():
    return TemplateRegistry(config.TEMPLATE_DIR).load()


@pytest.fixture
async def built_guild(registry):
    """Eine Guild, auf der die Community-Vorlage fertig gebaut ist."""

    guild = FakeGuild()
    template = registry.get("community")
    assert template is not None
    await ServerBuilder(guild, template).apply(BuildMode.EXTEND, write_intros=False)
    return guild, template


def base_role_names() -> list[str]:
    """Die Namen der geteilten Basis-Leiter, wie der Builder sie anlegt."""

    return [role_name(label, emoji) for _key, label, emoji, *_ in BASE_ROLES]


# --------------------------------------------------------------------------- #
# unapply
# --------------------------------------------------------------------------- #

class TestUnapply:
    async def test_removes_the_template_structure_but_keeps_the_ladder(self, built_guild):
        guild, template = built_guild

        report = await ServerBuilder(guild, template).unapply()

        assert report.deleted_channels == template.channel_count
        assert report.deleted_categories == template.category_count
        assert report.deleted_roles == len(template.roles)
        assert report.undeletable == 0

        # Die Basis-Leiter bleibt: Verified & Co. gehoeren jeder Vorlage.
        remaining = {role.name for role in guild.roles}
        for name in base_role_names():
            assert name in remaining, f"Basis-Rolle '{name}' wurde mitgeloescht"

        # Die eigenen Rollen der Vorlage sind weg.
        for role in template.roles:
            assert role_name(role.label, role.emoji) not in remaining

        assert not guild.categories
        assert guild.channels == []

    async def test_a_second_run_changes_nothing(self, built_guild):
        guild, template = built_guild

        builder = ServerBuilder(guild, template)
        await builder.unapply()
        report = await builder.unapply()

        assert report.total_deleted == 0
        assert not report.warnings

    async def test_foreign_channels_keep_their_category_alive(self, built_guild):
        """Nur leere Kategorien fallen — fremde Inhalte bleiben stehen."""

        guild, template = built_guild
        category = guild.categories[0]

        await guild.create_text_channel("fremder-kanal", category=category)
        report = await ServerBuilder(guild, template).unapply()

        assert report.kept_categories == 1
        assert any("fremde Kanäle" in warning for warning in report.warnings)
        assert any(c.name == "fremder-kanal" for c in guild.channels)

    async def test_undeletable_roles_are_reported_not_ignored(self, built_guild):
        guild, template = built_guild

        # Die erste eigene Rolle der Vorlage lehnt Discord ab.
        target = role_name(template.roles[0].label, template.roles[0].emoji)
        guild.undeletable_roles = {target}

        report = await ServerBuilder(guild, template).unapply()

        assert report.undeletable >= 1
        assert any("nicht gelöscht" in warning for warning in report.warnings)

    async def test_forbidden_and_missing_channels_are_survived(self, built_guild):
        """Ein 403 hier, ein 404 dort — der Rest wird trotzdem entfernt."""

        guild, template = built_guild

        category_spec = template.categories[0]
        first = category_spec.channels[0]
        second = category_spec.channels[1]
        guild.undeletable_channels = {first.display_name}
        guild.missing_channels = {second.display_name}

        report = await ServerBuilder(guild, template).unapply()

        assert report.undeletable >= 1
        # Beide Sonderfaelle zaehlen nicht als geloescht — alle anderen schon.
        assert report.deleted_channels == template.channel_count - 2

    async def test_a_missing_role_is_not_an_error(self, built_guild):
        guild, template = built_guild

        target = role_name(template.roles[0].label, template.roles[0].emoji)
        guild.missing_roles = {target}

        report = await ServerBuilder(guild, template).unapply()

        assert report.deleted_roles == len(template.roles) - 1
        assert not report.warnings

    async def test_a_renamed_channel_is_simply_not_found(self, built_guild):
        """Wer umbenannt hat, hat den Kanal 'entfernt' — kein Fehlerfall."""

        guild, template = built_guild

        guild.categories[0].channels[0].name = "umbenannt"

        report = await ServerBuilder(guild, template).unapply()

        assert report.deleted_channels == template.channel_count - 1
        assert report.kept_categories == 1, "Der umbenannte Kanal haelt seine Kategorie"

    async def test_a_forbidden_or_missing_category_is_survived(self, built_guild):
        guild, template = built_guild

        first = template.categories[0].display_name
        second = template.categories[1].display_name
        guild.undeletable_channels = {first}
        guild.missing_channels = {second}

        report = await ServerBuilder(guild, template).unapply()

        assert report.undeletable >= 1
        assert report.deleted_categories == template.category_count - 2

    async def test_an_unassignable_role_is_counted_not_deleted(self, built_guild):
        guild, template = built_guild

        # Die Rolle steht ueber der Bot-Rolle — Discord laesst sie stehen.
        target = role_name(template.roles[0].label, template.roles[0].emoji)
        for role in guild.roles:
            if role.name == target:
                role.position = guild.bot_top + 1

        report = await ServerBuilder(guild, template).unapply()

        assert report.undeletable == 1
        assert target in {role.name for role in guild.roles}


# --------------------------------------------------------------------------- #
# wipe_guild
# --------------------------------------------------------------------------- #

class TestWipeGuild:
    async def test_wipes_everything_deletable(self, built_guild):
        guild, _template = built_guild
        total = len(guild.channels)

        report = await wipe_guild(guild)

        assert report.deleted_channels == total
        assert guild.channels == []
        assert {role.name for role in guild.roles} == {"@everyone", "ArchitectBot"}
        assert report.undeletable == 0, "Geschuetzte Rollen sind keine Fehler"

    async def test_a_wiped_guild_can_be_rebuilt(self, registry, built_guild):
        """Wipe und frischer Aufbau sind das Kernstueck von 'Neu aufsetzen'."""

        guild, template = built_guild

        await wipe_guild(guild)
        report = await ServerBuilder(guild, template).apply(
            BuildMode.EXTEND, write_intros=False
        )

        assert report.categories_created == template.category_count
        assert report.channels_created == template.channel_count
