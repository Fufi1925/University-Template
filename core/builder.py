"""The provisioning engine.

Turns a :class:`~core.schema.Template` into real Discord roles, categories and
channels. Two modes:

``EXTEND``
    Only add what is missing. Nothing existing is touched or overwritten.

``REBUILD``
    Delete everything the bot is allowed to delete, then build fresh.

The engine is idempotent: running it twice in ``EXTEND`` mode is a no-op,
because objects are matched by their *decorated* name and by their plain
"stripped" name, so a channel renamed from ``general`` to ``💬・ɢᴇɴᴇʀᴀʟ`` is
still recognised.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Awaitable, Callable, Mapping, Sequence

import discord

from config import SETUP_REASON
from .permissions import (
    BASE_ROLES,
    category_overwrites,
    channel_overwrites,
    permissions_for_tier,
)
from .schema import CategorySpec, ChannelKind, ChannelSpec, RoleSpec, Template
from .small_caps import strip_decoration

LOGGER = logging.getLogger("architect.builder")

__all__ = ["BuildMode", "BuildReport", "ServerBuilder", "BuildError"]

# Discord tolerates bursts but sustained creation gets rate limited hard. A
# small delay between mutations keeps large templates (60+ channels) smooth.
_THROTTLE = 0.35


class BuildError(RuntimeError):
    """Raised for problems we can explain to the user in plain language."""


class BuildMode(str, Enum):
    EXTEND = "extend"
    REBUILD = "rebuild"


@dataclass(slots=True)
class BuildReport:
    """Everything that happened during a build, for the result screen."""

    mode: BuildMode
    template_key: str
    roles_created: int = 0
    roles_updated: int = 0
    roles_skipped: int = 0
    categories_created: int = 0
    channels_created: int = 0
    channels_updated: int = 0
    deleted_channels: int = 0
    deleted_roles: int = 0
    undeletable: int = 0
    warnings: list[str] = field(default_factory=list)

    @property
    def total_created(self) -> int:
        return self.roles_created + self.categories_created + self.channels_created

    def warn(self, message: str) -> None:
        if message not in self.warnings:
            self.warnings.append(message)


ProgressHook = Callable[[str, int, int], Awaitable[None]]


class ServerBuilder:
    """Applies templates to a guild."""

    def __init__(self, guild: discord.Guild, template: Template) -> None:
        self.guild = guild
        self.template = template
        self._roles: dict[str, discord.Role] = {}
        self._specs = self._resolve_role_specs()
        self._staff_keys = frozenset(
            spec.key for spec in self._specs if spec.tier.is_staff
        )
        self._leadership_keys = frozenset(
            spec.key for spec in self._specs if spec.tier.is_leadership
        )

    # ------------------------------------------------------------- roles ----
    def _resolve_role_specs(self) -> tuple[RoleSpec, ...]:
        """Base ladder first, then the template's own accent roles."""

        specs: list[RoleSpec] = []
        if self.template.extends_base_roles:
            specs.extend(
                RoleSpec(
                    key=key,
                    label=label,
                    emoji=emoji,
                    colour=colour,
                    tier=tier,
                    hoist=hoist,
                    mentionable=mentionable,
                )
                for key, label, emoji, colour, tier, hoist, mentionable in BASE_ROLES
            )

        existing = {spec.key for spec in specs}
        for spec in self.template.roles:
            if spec.key in existing:
                continue
            specs.append(spec)
            existing.add(spec.key)
        return tuple(specs)

    # ---------------------------------------------------------- preflight ---
    def preflight(self) -> None:
        """Fail early with an actionable message instead of a stack trace."""

        me = self.guild.me
        if me is None:
            raise BuildError("Der Bot ist auf diesem Server noch nicht vollständig geladen.")

        perms = me.guild_permissions
        missing = [
            label
            for flag, label in (
                (perms.manage_roles, "Rollen verwalten"),
                (perms.manage_channels, "Kanäle verwalten"),
            )
            if not flag
        ]
        if missing:
            raise BuildError(
                "Dem Bot fehlen Berechtigungen: **" + "**, **".join(missing) + "**."
            )

        if me.top_role <= self.guild.default_role:
            raise BuildError(
                "Die Bot-Rolle steht ganz unten in der Rollenliste. "
                "Schiebe sie über die Rollen, die verwaltet werden sollen."
            )

        projected = len(self.guild.channels) + self.template.channel_count
        if projected > 500:
            raise BuildError(
                f"Der Server hätte danach {projected} Kanäle — Discord erlaubt maximal 500. "
                "Nutze den Modus **Neu aufsetzen** oder räume vorher auf."
            )

    # ------------------------------------------------------------- lookup ---
    def _find_role(self, spec: RoleSpec) -> discord.Role | None:
        target = strip_decoration(spec.display_name)
        for role in self.guild.roles:
            if role.is_default():
                continue
            if role.name == spec.display_name or strip_decoration(role.name) == target:
                return role
        return None

    def _find_category(self, spec: CategorySpec) -> discord.CategoryChannel | None:
        target = strip_decoration(spec.display_name)
        for category in self.guild.categories:
            if category.name == spec.display_name or strip_decoration(category.name) == target:
                return category
        return None

    @staticmethod
    def _find_channel(
        category: discord.CategoryChannel, spec: ChannelSpec
    ) -> discord.abc.GuildChannel | None:
        target = strip_decoration(spec.display_name)
        for channel in category.channels:
            if channel.name == spec.display_name or strip_decoration(channel.name) == target:
                return channel
        return None

    # ------------------------------------------------------------ rebuild ---
    async def _wipe(self, report: BuildReport) -> None:
        """Delete everything Discord lets us delete."""

        # Children before categories, so nothing is orphaned mid-run.
        channels = sorted(
            self.guild.channels,
            key=lambda ch: isinstance(ch, discord.CategoryChannel),
        )
        for channel in channels:
            try:
                await channel.delete(reason=SETUP_REASON)
                report.deleted_channels += 1
                await asyncio.sleep(_THROTTLE)
            except discord.NotFound:
                continue
            except (discord.Forbidden, discord.HTTPException):
                report.undeletable += 1
                LOGGER.warning("Kanal '%s' nicht löschbar", channel.name)

        for role in sorted(self.guild.roles, key=lambda r: r.position, reverse=True):
            # @everyone, integration roles and roles above the bot are off limits.
            if role.is_default() or role.managed or not role.is_assignable():
                if not role.is_default() and not role.managed:
                    report.undeletable += 1
                continue
            try:
                await role.delete(reason=SETUP_REASON)
                report.deleted_roles += 1
                await asyncio.sleep(_THROTTLE)
            except discord.NotFound:
                continue
            except (discord.Forbidden, discord.HTTPException):
                report.undeletable += 1
                LOGGER.warning("Rolle '%s' nicht löschbar", role.name)

        if report.undeletable:
            report.warn(
                f"{report.undeletable} Objekt(e) konnten nicht gelöscht werden — "
                "sie stehen über der Bot-Rolle oder gehören zu einer Integration."
            )

    # ------------------------------------------------------------ building --
    async def _ensure_roles(self, report: BuildReport, *, update: bool) -> None:
        for spec in self._specs:
            existing = self._find_role(spec)
            permissions = permissions_for_tier(spec.tier)

            if existing is None:
                try:
                    role = await self.guild.create_role(
                        name=spec.display_name,
                        colour=discord.Colour(spec.colour),
                        permissions=permissions,
                        hoist=spec.hoist,
                        mentionable=spec.mentionable,
                        reason=SETUP_REASON,
                    )
                    report.roles_created += 1
                    self._roles[spec.key] = role
                    await asyncio.sleep(_THROTTLE)
                except discord.Forbidden:
                    report.roles_skipped += 1
                    report.warn(f"Rolle '{spec.display_name}' konnte nicht erstellt werden.")
                except discord.HTTPException as exc:
                    report.roles_skipped += 1
                    LOGGER.warning("Rolle '%s': %s", spec.display_name, exc)
                continue

            self._roles[spec.key] = existing
            if not update:
                continue
            if not existing.is_assignable() and existing >= (self.guild.me.top_role if self.guild.me else existing):
                report.roles_skipped += 1
                continue
            try:
                await existing.edit(
                    colour=discord.Colour(spec.colour),
                    permissions=permissions,
                    hoist=spec.hoist,
                    mentionable=spec.mentionable,
                    reason=SETUP_REASON,
                )
                report.roles_updated += 1
                await asyncio.sleep(_THROTTLE)
            except (discord.Forbidden, discord.HTTPException):
                report.roles_skipped += 1

    async def _order_roles(self, report: BuildReport) -> None:
        """Best-effort: put the ladder in the right visual order."""

        me = self.guild.me
        if me is None:
            return
        movable = [
            role
            for spec in self._specs
            if (role := self._roles.get(spec.key)) is not None
            and not role.is_default()
            and role < me.top_role
        ]
        if not movable:
            return
        try:
            await self.guild.edit_role_positions(
                positions={role: index for index, role in enumerate(movable, start=1)},
                reason=SETUP_REASON,
            )
        except (discord.Forbidden, discord.HTTPException):
            report.warn(
                "Die Rollen-Reihenfolge konnte nicht gesetzt werden — "
                "die Bot-Rolle steht dafür zu weit unten."
            )

    def _channel_kwargs(
        self, category_spec: CategorySpec, spec: ChannelSpec
    ) -> dict[str, object]:
        overwrites = channel_overwrites(
            self.guild,
            category_spec.visibility,
            category_spec.visibility_for(spec),
            self._roles,
            staff_keys=self._staff_keys,
            leadership_keys=self._leadership_keys,
        )
        kwargs: dict[str, object] = {"reason": SETUP_REASON}
        if overwrites:
            kwargs["overwrites"] = overwrites
        return kwargs

    async def _create_channel(
        self,
        category: discord.CategoryChannel,
        category_spec: CategorySpec,
        spec: ChannelSpec,
    ) -> discord.abc.GuildChannel:
        kwargs = self._channel_kwargs(category_spec, spec)
        name = spec.display_name

        if spec.kind is ChannelKind.VOICE:
            return await self.guild.create_voice_channel(
                name, category=category, user_limit=spec.user_limit, **kwargs
            )
        if spec.kind is ChannelKind.STAGE:
            try:
                return await self.guild.create_stage_channel(
                    name, category=category, **kwargs
                )
            except (discord.Forbidden, discord.HTTPException):
                # Stage channels need the COMMUNITY feature; fall back to voice.
                return await self.guild.create_voice_channel(
                    name, category=category, user_limit=spec.user_limit, **kwargs
                )
        if spec.kind is ChannelKind.FORUM:
            try:
                return await self.guild.create_forum(
                    name, category=category, topic=spec.topic, **kwargs
                )
            except (discord.Forbidden, discord.HTTPException):
                return await self.guild.create_text_channel(
                    name, category=category, topic=spec.topic, **kwargs
                )

        news = spec.kind is ChannelKind.NEWS
        channel = await self.guild.create_text_channel(
            name,
            category=category,
            topic=spec.topic,
            slowmode_delay=spec.slowmode,
            nsfw=spec.nsfw,
            **kwargs,
        )
        if news and "NEWS" in self.guild.features:
            try:
                await channel.edit(type=discord.ChannelType.news, reason=SETUP_REASON)
            except (discord.Forbidden, discord.HTTPException):
                pass
        return channel

    async def _update_channel(
        self,
        channel: discord.abc.GuildChannel,
        category_spec: CategorySpec,
        spec: ChannelSpec,
    ) -> bool:
        overwrites = channel_overwrites(
            self.guild,
            category_spec.visibility,
            category_spec.visibility_for(spec),
            self._roles,
            staff_keys=self._staff_keys,
            leadership_keys=self._leadership_keys,
        )
        payload: dict[str, object] = {}
        if overwrites:
            payload["overwrites"] = overwrites
        if isinstance(channel, discord.TextChannel):
            payload["topic"] = spec.topic
            payload["slowmode_delay"] = spec.slowmode
        elif isinstance(channel, discord.VoiceChannel):
            payload["user_limit"] = spec.user_limit
        if not payload:
            return False
        try:
            await channel.edit(reason=SETUP_REASON, **payload)
            return True
        except (discord.Forbidden, discord.HTTPException):
            return False

    # --------------------------------------------------------------- apply --
    async def apply(
        self,
        mode: BuildMode,
        *,
        progress: ProgressHook | None = None,
    ) -> BuildReport:
        """Run the build and return a report."""

        self.preflight()
        report = BuildReport(mode=mode, template_key=self.template.key)
        rebuild = mode is BuildMode.REBUILD

        total_steps = 1 + self.template.category_count
        step = 0

        async def tick(label: str) -> None:
            nonlocal step
            step += 1
            if progress is not None:
                try:
                    await progress(label, step, total_steps)
                except Exception:  # pragma: no cover - progress must never break a build
                    LOGGER.debug("Progress-Hook fehlgeschlagen", exc_info=True)

        if rebuild:
            await self._wipe(report)

        await self._ensure_roles(report, update=rebuild)
        await tick("Rollen")
        if rebuild:
            await self._order_roles(report)

        for category_spec in self.template.categories:
            category = self._find_category(category_spec)
            if category is None:
                try:
                    category = await self.guild.create_category(
                        category_spec.display_name,
                        overwrites=category_overwrites(
                            self.guild,
                            category_spec.visibility,
                            self._roles,
                            staff_keys=self._staff_keys,
                            leadership_keys=self._leadership_keys,
                        ),
                        reason=SETUP_REASON,
                    )
                    report.categories_created += 1
                    await asyncio.sleep(_THROTTLE)
                except discord.Forbidden as exc:
                    raise BuildError(
                        f"Kategorie '{category_spec.display_name}' konnte nicht erstellt werden."
                    ) from exc
            elif rebuild:
                try:
                    await category.edit(
                        overwrites=category_overwrites(
                            self.guild,
                            category_spec.visibility,
                            self._roles,
                            staff_keys=self._staff_keys,
                            leadership_keys=self._leadership_keys,
                        ),
                        reason=SETUP_REASON,
                    )
                except (discord.Forbidden, discord.HTTPException):
                    report.warn(f"Kategorie '{category.name}' nicht aktualisierbar.")

            for spec in category_spec.channels:
                existing = self._find_channel(category, spec)
                if existing is None:
                    try:
                        await self._create_channel(category, category_spec, spec)
                        report.channels_created += 1
                        await asyncio.sleep(_THROTTLE)
                    except discord.Forbidden:
                        report.warn(f"Kanal '{spec.display_name}' konnte nicht erstellt werden.")
                    except discord.HTTPException as exc:
                        LOGGER.warning("Kanal '%s': %s", spec.display_name, exc)
                        report.warn(f"Kanal '{spec.display_name}': {exc.text or exc}")
                elif rebuild and await self._update_channel(existing, category_spec, spec):
                    report.channels_updated += 1

            await tick(category_spec.display_name)

        # Keep the template's deliberate category order.
        if rebuild:
            await self._order_categories(report)

        return report

    async def _order_categories(self, report: BuildReport) -> None:
        for position, spec in enumerate(self.template.categories):
            category = self._find_category(spec)
            if category is None or category.position == position:
                continue
            try:
                await category.edit(position=position, reason=SETUP_REASON)
                await asyncio.sleep(0.2)
            except (discord.Forbidden, discord.HTTPException):
                report.warn("Die Kategorie-Reihenfolge konnte nicht vollständig gesetzt werden.")
                return
