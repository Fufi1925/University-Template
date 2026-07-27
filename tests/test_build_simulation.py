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

import discord  # noqa: E402

import config  # noqa: E402
from core.builder import BuildError, BuildMode, ServerBuilder  # noqa: E402
from core.registry import TemplateRegistry  # noqa: E402
from core.schema import Visibility  # noqa: E402


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
    status = 403
    reason = "Forbidden"


class FakeChannel:
    def __init__(self, guild, name, kind, category=None, **kwargs):
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
        self.edits = 0

    async def edit(self, **kwargs):
        kwargs.pop("reason", None)
        self.edits += 1
        for key, value in kwargs.items():
            setattr(self, key, value)

    async def delete(self, reason=None):
        self.guild.channels.remove(self)
        if self in self.guild._categories:
            self.guild._categories.remove(self)

    def __hash__(self):
        return id(self)


class FakeCategory(FakeChannel):
    def __init__(self, guild, name, **kwargs):
        super().__init__(guild, name, "category", **kwargs)
        self._children: list[FakeChannel] = []

    @property
    def channels(self):
        return self._children


class FakeMember:
    def __init__(self, guild, top_role):
        self.guild = guild
        self.top_role = top_role
        self.guild_permissions = discord.Permissions.all()


class FakeGuild:
    """Minimal guild good enough for the builder."""

    def __init__(self, *, bot_top=1000, undeletable_roles=None):
        self.channels: list[FakeChannel] = []
        self._categories: list[FakeCategory] = []
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

    @property
    def categories(self):
        return list(self._categories)

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
        self.channels.append(category)
        self._categories.append(category)
        self.created_categories += 1
        return category

    async def _make(self, name, kind, category=None, **kwargs):
        kwargs.pop("reason", None)
        channel = FakeChannel(self, name, kind, category=category, **kwargs)
        self.channels.append(channel)
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
