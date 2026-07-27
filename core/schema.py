"""Typed template model.

Templates live in ``templates/*.json`` as data, not code. This module turns that
JSON into validated, immutable Python objects so a malformed template fails
loudly at startup instead of halfway through rebuilding somebody's server.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterator, Mapping, Sequence

from .small_caps import category_name, channel_name, role_name

__all__ = [
    "ChannelKind",
    "Visibility",
    "RoleTier",
    "RoleSpec",
    "ChannelSpec",
    "CategorySpec",
    "Template",
    "TemplateError",
]


class TemplateError(ValueError):
    """Raised when a template file does not match the expected schema."""


class ChannelKind(str, Enum):
    TEXT = "text"
    VOICE = "voice"
    FORUM = "forum"
    NEWS = "news"
    STAGE = "stage"

    @property
    def is_voice_like(self) -> bool:
        return self in {ChannelKind.VOICE, ChannelKind.STAGE}


class Visibility(str, Enum):
    """Who may see and write in a channel or category."""

    PUBLIC = "public"          # everyone who passed verification
    GATE = "gate"              # visible to unverified members (welcome/verify)
    READONLY = "readonly"      # visible to all, writable by staff only
    MEMBER = "member"          # verified members only
    VIP = "vip"                # VIP + staff
    STAFF = "staff"            # any staff role
    LEADERSHIP = "leadership"  # senior staff only
    ARCHIVE = "archive"        # visible, nobody writes


class RoleTier(str, Enum):
    """Permission tiers, ordered from least to most privileged."""

    GUEST = "guest"
    MEMBER = "member"
    TRUSTED = "trusted"
    VIP = "vip"
    HELPER = "helper"
    MODERATOR = "moderator"
    SENIOR = "senior"
    ADMIN = "admin"
    LEADERSHIP = "leadership"
    OWNER = "owner"

    @property
    def is_staff(self) -> bool:
        return self in {
            RoleTier.HELPER,
            RoleTier.MODERATOR,
            RoleTier.SENIOR,
            RoleTier.ADMIN,
            RoleTier.LEADERSHIP,
            RoleTier.OWNER,
        }

    @property
    def is_leadership(self) -> bool:
        return self in {RoleTier.ADMIN, RoleTier.LEADERSHIP, RoleTier.OWNER}


def _require(data: Mapping[str, Any], key: str, where: str) -> Any:
    if key not in data:
        raise TemplateError(f"{where}: Pflichtfeld '{key}' fehlt")
    return data[key]


def _colour(raw: Any, where: str) -> int:
    if raw is None:
        return 0
    if isinstance(raw, int):
        return raw
    if isinstance(raw, str):
        try:
            return int(raw.lstrip("#"), 16)
        except ValueError as exc:
            raise TemplateError(f"{where}: '{raw}' ist keine gültige Farbe") from exc
    raise TemplateError(f"{where}: Farbe muss int oder Hex-String sein")


@dataclass(frozen=True, slots=True)
class RoleSpec:
    """A role the template creates, including its permission tier."""

    key: str
    label: str
    emoji: str | None = None
    colour: int = 0
    tier: RoleTier = RoleTier.MEMBER
    hoist: bool = False
    mentionable: bool = False
    small_caps: bool = False

    @property
    def display_name(self) -> str:
        return role_name(self.label, self.emoji, small_caps=self.small_caps)

    @property
    def is_staff(self) -> bool:
        return self.tier.is_staff

    @classmethod
    def parse(cls, data: Mapping[str, Any], where: str) -> "RoleSpec":
        label = _require(data, "label", where)
        raw_tier = data.get("tier", "member")
        try:
            tier = RoleTier(raw_tier)
        except ValueError as exc:
            raise TemplateError(f"{where}: unbekannter tier '{raw_tier}'") from exc
        return cls(
            key=data.get("key") or label,
            label=label,
            emoji=data.get("emoji"),
            colour=_colour(data.get("colour", data.get("color")), where),
            tier=tier,
            hoist=bool(data.get("hoist", tier.is_staff or tier is RoleTier.VIP)),
            mentionable=bool(data.get("mentionable", False)),
            small_caps=bool(data.get("small_caps", False)),
        )


@dataclass(frozen=True, slots=True)
class ChannelSpec:
    """A single channel inside a category."""

    label: str
    emoji: str | None = None
    kind: ChannelKind = ChannelKind.TEXT
    visibility: Visibility | None = None
    topic: str | None = None
    slowmode: int = 0
    user_limit: int = 0
    nsfw: bool = False
    small_caps: bool = True

    @property
    def display_name(self) -> str:
        return channel_name(self.label, self.emoji, small_caps=self.small_caps)

    @classmethod
    def parse(cls, data: Mapping[str, Any], where: str) -> "ChannelSpec":
        label = _require(data, "label", where)
        raw_kind = data.get("kind", "text")
        try:
            kind = ChannelKind(raw_kind)
        except ValueError as exc:
            raise TemplateError(f"{where}: unbekannter Kanaltyp '{raw_kind}'") from exc

        visibility: Visibility | None = None
        if "visibility" in data and data["visibility"] is not None:
            try:
                visibility = Visibility(data["visibility"])
            except ValueError as exc:
                raise TemplateError(
                    f"{where}: unbekannte visibility '{data['visibility']}'"
                ) from exc

        slowmode = int(data.get("slowmode", 0))
        if not 0 <= slowmode <= 21600:
            raise TemplateError(f"{where}: slowmode muss zwischen 0 und 21600 liegen")

        user_limit = int(data.get("user_limit", 0))
        if not 0 <= user_limit <= 99:
            raise TemplateError(f"{where}: user_limit muss zwischen 0 und 99 liegen")

        return cls(
            label=label,
            emoji=data.get("emoji"),
            kind=kind,
            visibility=visibility,
            topic=data.get("topic"),
            slowmode=slowmode,
            user_limit=user_limit,
            nsfw=bool(data.get("nsfw", False)),
            small_caps=bool(data.get("small_caps", True)),
        )


@dataclass(frozen=True, slots=True)
class CategorySpec:
    """A category plus the channels it contains."""

    label: str
    emoji: str | None = None
    visibility: Visibility = Visibility.PUBLIC
    channels: tuple[ChannelSpec, ...] = ()
    small_caps: bool = True

    @property
    def display_name(self) -> str:
        return category_name(self.label, self.emoji, small_caps=self.small_caps)

    def visibility_for(self, channel: ChannelSpec) -> Visibility:
        """Channel visibility, defaulting to the category's own setting."""

        return channel.visibility or self.visibility

    @classmethod
    def parse(cls, data: Mapping[str, Any], where: str) -> "CategorySpec":
        label = _require(data, "label", where)
        raw_visibility = data.get("visibility", "public")
        try:
            visibility = Visibility(raw_visibility)
        except ValueError as exc:
            raise TemplateError(f"{where}: unbekannte visibility '{raw_visibility}'") from exc

        raw_channels = data.get("channels", [])
        if not isinstance(raw_channels, Sequence):
            raise TemplateError(f"{where}: 'channels' muss eine Liste sein")

        channels = tuple(
            ChannelSpec.parse(entry, f"{where} → Kanal #{index + 1}")
            for index, entry in enumerate(raw_channels)
        )
        return cls(
            label=label,
            emoji=data.get("emoji"),
            visibility=visibility,
            channels=channels,
            small_caps=bool(data.get("small_caps", True)),
        )


@dataclass(frozen=True, slots=True)
class Template:
    """A complete server blueprint."""

    key: str
    name: str
    emoji: str
    tagline: str
    description: str
    premium: bool = False
    accent: int = 0x5865F2
    highlights: tuple[str, ...] = ()
    categories: tuple[CategorySpec, ...] = ()
    roles: tuple[RoleSpec, ...] = ()
    extends_base_roles: bool = True

    # ---------------------------------------------------------------- stats --
    @property
    def category_count(self) -> int:
        return len(self.categories)

    @property
    def channel_count(self) -> int:
        return sum(len(category.channels) for category in self.categories)

    @property
    def voice_count(self) -> int:
        return sum(
            1
            for category in self.categories
            for channel in category.channels
            if channel.kind.is_voice_like
        )

    @property
    def text_count(self) -> int:
        return self.channel_count - self.voice_count

    def iter_channels(self) -> Iterator[tuple[CategorySpec, ChannelSpec]]:
        for category in self.categories:
            for channel in category.channels:
                yield category, channel

    # ---------------------------------------------------------------- parse --
    @classmethod
    def parse(cls, data: Mapping[str, Any], *, source: str = "<memory>") -> "Template":
        key = _require(data, "key", source)
        where = f"Template '{key}' ({source})"

        raw_categories = data.get("categories", [])
        if not raw_categories:
            raise TemplateError(f"{where}: mindestens eine Kategorie ist erforderlich")

        categories = tuple(
            CategorySpec.parse(entry, f"{where} → Kategorie #{index + 1}")
            for index, entry in enumerate(raw_categories)
        )
        roles = tuple(
            RoleSpec.parse(entry, f"{where} → Rolle #{index + 1}")
            for index, entry in enumerate(data.get("roles", []))
        )

        template = cls(
            key=key,
            name=_require(data, "name", where),
            emoji=data.get("emoji", "📦"),
            tagline=data.get("tagline", ""),
            description=data.get("description", ""),
            premium=bool(data.get("premium", False)),
            accent=_colour(data.get("accent", 0x5865F2), where),
            highlights=tuple(data.get("highlights", [])),
            categories=categories,
            roles=roles,
            extends_base_roles=bool(data.get("extends_base_roles", True)),
        )
        template.validate()
        return template

    def validate(self) -> None:
        """Catch the Discord hard limits before we hit the API."""

        if self.category_count > 50:
            raise TemplateError(
                f"Template '{self.key}': {self.category_count} Kategorien "
                "überschreiten das Discord-Limit von 50"
            )
        if self.channel_count > 500:
            raise TemplateError(
                f"Template '{self.key}': {self.channel_count} Kanäle "
                "überschreiten das Discord-Limit von 500"
            )

        seen_categories: set[str] = set()
        for category in self.categories:
            name = category.display_name
            if name in seen_categories:
                raise TemplateError(f"Template '{self.key}': Kategorie '{name}' ist doppelt")
            seen_categories.add(name)

            seen_channels: set[str] = set()
            for channel in category.channels:
                if channel.display_name in seen_channels:
                    raise TemplateError(
                        f"Template '{self.key}' / '{name}': "
                        f"Kanal '{channel.display_name}' ist doppelt"
                    )
                seen_channels.add(channel.display_name)
