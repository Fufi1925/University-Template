"""Permission model.

Two ideas keep this maintainable:

1. **Tiers, not per-role permissions.** Every role belongs to a
   :class:`~core.schema.RoleTier`; the tier decides the guild-level permissions.
   Adding a role to a template never means hand-picking 40 booleans.

2. **Categories are the source of truth.** A channel's overwrites always start
   from its category baseline, so a private log channel can never accidentally
   become public because someone forgot a flag.
"""

from __future__ import annotations

from typing import Mapping

import discord

from .schema import RoleTier, Visibility

__all__ = [
    "BASE_ROLES",
    "UNVERIFIED",
    "VERIFIED",
    "MEMBER",
    "VIP",
    "permissions_for_tier",
    "category_overwrites",
    "channel_overwrites",
]


def _perms(*names: str) -> dict[str, bool]:
    return {name: True for name in names}


# --------------------------------------------------------------------------- #
# Guild level permission tiers
# --------------------------------------------------------------------------- #

_GUEST = _perms("read_message_history", "change_nickname")

_MEMBER = _GUEST | _perms(
    "view_channel",
    "send_messages",
    "send_messages_in_threads",
    "add_reactions",
    "use_external_emojis",
    "connect",
    "speak",
    "stream",
    "use_voice_activation",
    "request_to_speak",
)

_TRUSTED = _MEMBER | _perms(
    "embed_links",
    "attach_files",
    "create_public_threads",
    "use_application_commands",
)

_VIP = _TRUSTED | _perms("create_private_threads", "use_external_stickers", "priority_speaker")

_HELPER = _TRUSTED | _perms(
    "manage_messages",
    "manage_threads",
    "mute_members",
    "deafen_members",
    "move_members",
)

_MODERATOR = _HELPER | _perms(
    "kick_members",
    "moderate_members",
    "manage_nicknames",
    "view_audit_log",
)

_SENIOR = _MODERATOR | _perms("ban_members", "manage_roles")

_ADMIN = _SENIOR | _perms(
    "manage_channels",
    "manage_webhooks",
    "manage_events",
    "mention_everyone",
)

_LEADERSHIP = _ADMIN | _perms("manage_guild", "manage_expressions")

_OWNER = {"administrator": True}


_TIER_PERMISSIONS: dict[RoleTier, Mapping[str, bool]] = {
    RoleTier.GUEST: _GUEST,
    RoleTier.MEMBER: _MEMBER,
    RoleTier.TRUSTED: _TRUSTED,
    RoleTier.VIP: _VIP,
    RoleTier.HELPER: _HELPER,
    RoleTier.MODERATOR: _MODERATOR,
    RoleTier.SENIOR: _SENIOR,
    RoleTier.ADMIN: _ADMIN,
    RoleTier.LEADERSHIP: _LEADERSHIP,
    RoleTier.OWNER: _OWNER,
}


def permissions_for_tier(tier: RoleTier) -> discord.Permissions:
    """Translate a tier into a concrete :class:`discord.Permissions` object."""

    permissions = discord.Permissions.none()
    permissions.update(**_TIER_PERMISSIONS[tier])
    return permissions


# --------------------------------------------------------------------------- #
# Shared base roles — every template starts from this ladder
# --------------------------------------------------------------------------- #

UNVERIFIED = "unverified"
VERIFIED = "verified"
MEMBER = "member"
VIP = "vip"

# (key, label, emoji, colour, tier, hoist, mentionable)
BASE_ROLES: tuple[tuple[str, str, str, int, RoleTier, bool, bool], ...] = (
    (UNVERIFIED, "Unverified", "🔰", 0x4E5058, RoleTier.GUEST, False, False),
    (VERIFIED, "Verified", "✅", 0x3BA55D, RoleTier.MEMBER, False, False),
    (MEMBER, "Member", "👤", 0x99AAB5, RoleTier.MEMBER, False, False),
    ("active", "Active", "🌟", 0xF0B232, RoleTier.TRUSTED, True, False),
    ("partner", "Partner", "🤝", 0x14B8A6, RoleTier.TRUSTED, True, True),
    ("booster", "Booster", "🚀", 0xF47FFF, RoleTier.VIP, True, False),
    (VIP, "VIP", "💎", 0xA855F7, RoleTier.VIP, True, True),
    ("support", "Support", "🛟", 0x10B981, RoleTier.HELPER, True, False),
    ("moderator", "Moderator", "🛡️", 0x3B82F6, RoleTier.MODERATOR, True, True),
    ("senior_mod", "Senior Mod", "⚔️", 0x2563EB, RoleTier.SENIOR, True, False),
    ("admin", "Administrator", "🔧", 0xEF4444, RoleTier.ADMIN, True, True),
    ("leadership", "Leitung", "🏛️", 0xDC2626, RoleTier.LEADERSHIP, True, True),
    ("owner", "Inhaber", "👑", 0xFACC15, RoleTier.OWNER, True, True),
)


# --------------------------------------------------------------------------- #
# Channel / category overwrites
# --------------------------------------------------------------------------- #

def _ow(**flags: bool) -> discord.PermissionOverwrite:
    return discord.PermissionOverwrite(**flags)


_HIDDEN = _ow(view_channel=False)

_CAN_READ = _ow(view_channel=True, read_message_history=True)

_CAN_TALK = _ow(
    view_channel=True,
    read_message_history=True,
    send_messages=True,
    add_reactions=True,
    connect=True,
    speak=True,
)

_READ_ONLY = _ow(
    view_channel=True,
    read_message_history=True,
    send_messages=False,
    add_reactions=True,
    create_public_threads=False,
    create_private_threads=False,
)

_FROZEN = _ow(
    view_channel=True,
    read_message_history=True,
    send_messages=False,
    add_reactions=False,
    create_public_threads=False,
    create_private_threads=False,
)

_STAFF_FULL = _ow(
    view_channel=True,
    read_message_history=True,
    send_messages=True,
    add_reactions=True,
    manage_messages=True,
    embed_links=True,
    attach_files=True,
    connect=True,
    speak=True,
)

_BOT_FULL = _ow(
    view_channel=True,
    read_message_history=True,
    send_messages=True,
    embed_links=True,
    attach_files=True,
    manage_messages=True,
    manage_channels=True,
    connect=True,
    speak=True,
)


def category_overwrites(
    guild: discord.Guild,
    visibility: Visibility,
    roles: Mapping[str, discord.Role],
    *,
    staff_keys: frozenset[str],
    leadership_keys: frozenset[str],
) -> dict[discord.abc.Snowflake, discord.PermissionOverwrite]:
    """Build the overwrite map for a category with the given visibility."""

    everyone = guild.default_role
    result: dict[discord.abc.Snowflake, discord.PermissionOverwrite] = {}

    def grant(keys: frozenset[str] | set[str], overwrite: discord.PermissionOverwrite) -> None:
        for key in keys:
            role = roles.get(key)
            if role is not None:
                result[role] = overwrite

    unverified = roles.get(UNVERIFIED)

    if visibility is Visibility.GATE:
        # The only area an unverified member is supposed to see.
        result[everyone] = _CAN_READ
        if unverified is not None:
            result[unverified] = _CAN_TALK
        grant(staff_keys, _STAFF_FULL)

    elif visibility in {Visibility.PUBLIC, Visibility.MEMBER}:
        result[everyone] = _CAN_TALK
        if unverified is not None:
            result[unverified] = _HIDDEN
        grant(staff_keys, _STAFF_FULL)

    elif visibility is Visibility.READONLY:
        result[everyone] = _READ_ONLY
        if unverified is not None:
            result[unverified] = _HIDDEN
        grant(staff_keys, _STAFF_FULL)

    elif visibility is Visibility.ARCHIVE:
        result[everyone] = _FROZEN
        if unverified is not None:
            result[unverified] = _HIDDEN
        grant(staff_keys, _READ_ONLY)

    elif visibility is Visibility.VIP:
        result[everyone] = _HIDDEN
        for key in (VIP, "booster", "partner"):
            role = roles.get(key)
            if role is not None:
                result[role] = _CAN_TALK
        grant(staff_keys, _STAFF_FULL)

    elif visibility is Visibility.STAFF:
        result[everyone] = _HIDDEN
        grant(staff_keys, _STAFF_FULL)

    elif visibility is Visibility.LEADERSHIP:
        result[everyone] = _HIDDEN
        grant(leadership_keys, _STAFF_FULL)

    else:  # pragma: no cover - defensive
        result[everyone] = _CAN_TALK

    bot_member = guild.me
    if bot_member is not None:
        result[bot_member] = _BOT_FULL

    return result


def channel_overwrites(
    guild: discord.Guild,
    category_visibility: Visibility,
    channel_visibility: Visibility,
    roles: Mapping[str, discord.Role],
    *,
    staff_keys: frozenset[str],
    leadership_keys: frozenset[str],
) -> dict[discord.abc.Snowflake, discord.PermissionOverwrite]:
    """Overwrites for a single channel.

    A channel that matches its category needs no overwrites at all — it simply
    inherits, which keeps the Discord UI clean. Only a deviating visibility
    produces an explicit map, and that map is always built on top of the
    stricter of the two baselines.
    """

    if channel_visibility is category_visibility:
        return {}

    return category_overwrites(
        guild,
        channel_visibility,
        roles,
        staff_keys=staff_keys,
        leadership_keys=leadership_keys,
    )
