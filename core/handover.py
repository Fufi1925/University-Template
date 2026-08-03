"""Was der University Bot nach dem Bau wissen muss.

Der Template-Bot legt Rollen und Kanaele an; der University Bot richtet
danach Verify, Anti-Nuke, Tickets und die Logs ein. Dazwischen fehlt eine
Information: *welcher* Kanal ist der Verify-Kanal, und *welche* Rolle ist
die Verified-Rolle.

Der naheliegende Weg -- der Hauptbot sucht nach Namen -- funktioniert
nicht. Die Kanalnamen stehen in Small Caps mit Emoji-Praefix
(``✅・ᴠᴇʀɪꜰɪᴢɪᴇʀᴇɴ``), und ein ``"verify" in channel.name`` trifft das
nicht. Ein Treffer auf gut Glueck ist ausserdem schlimmer als kein
Treffer: dann steht die Verify-Schleuse im falschen Kanal, und das faellt
erst auf, wenn die ersten Leute nicht durchkommen.

Deshalb wird die Zuordnung hier gebaut, wo die Template-Definition noch
vorliegt: ``widget == VERIFY`` sagt eindeutig, welcher Kanal gemeint ist,
``mode == LOG`` welcher Kanal ein Log-Kanal ist, und der Rollen-Key
(``verified``, ``unverified``, ...) ist ohnehin stabil.

Ergebnis ist ein flaches JSON-taugliches Dict. IDs sind Strings -- eine
JSON-Zahl verliert bei Snowflakes die letzten Stellen.
"""

from __future__ import annotations

import discord

from .schema import ChannelMode, Template, Widget
from .small_caps import slugify

__all__ = ["LOG_CATEGORY_BY_SLUG", "build_handover"]


# Welcher Log-Kanal zu welcher Kategorie des University Bots gehoert.
#
# Die Schluessel rechts sind die Kategorien aus dessen
# ``cogs/commands/logging.py``; sie stehen so auch im Dashboard. Die
# Slugs links sind die Kanalnamen der Templates, durch ``slugify``
# gedreht -- also ohne Emoji, ohne Small Caps, klein geschrieben.
LOG_CATEGORY_BY_SLUG: dict[str, str] = {
    "mod-logs": "member_moderation",
    "mitglieder-logs": "join_leave_events",
    "nachrichten-logs": "message_events",
    "sprach-logs": "voice_events",
    "rollen-logs": "role_events",
    "kanal-logs": "channel_events",
    "social-logs": "reaction_events",
    "server-logs": "system_events",
    # bot-logs und einladungs-logs haben im University Bot keine eigene
    # Kategorie. Sie bleiben absichtlich unzugeordnet: lieber ein Kanal
    # ohne Logs als Kanal-Ereignisse im falschen Kanal.
}

# Rollen-Keys, die der Hauptbot direkt verwenden kann.
_ROLE_KEYS = (
    "unverified",
    "verified",
    "member",
    "vip",
    "booster",
    "support",
    "moderator",
    "senior_mod",
    "admin",
    "leadership",
    "owner",
)

# Welche Rollen als Team gelten -- fuer die Staff-Rollen der Tickets und
# die Anti-Nuke-Whitelist.
_STAFF_KEYS = ("support", "moderator", "senior_mod", "admin", "leadership", "owner")


def _kind_of(channel: discord.abc.GuildChannel) -> str:
    return getattr(channel.type, "name", str(channel.type))


def _channel_entry(channel: discord.abc.GuildChannel) -> dict:
    category = getattr(channel, "category", None)
    return {
        "id": str(channel.id),
        "name": channel.name,
        "slug": slugify(channel.name),
        "type": _kind_of(channel),
        "category": category.name if category is not None else None,
    }


def build_handover(
    guild: discord.Guild,
    template: Template,
    roles: dict[str, discord.Role],
) -> dict:
    """Die Landkarte des frisch gebauten Servers.

    ``roles`` ist die Zuordnung Key -> Rolle, die der ServerBuilder
    ohnehin gefuehrt hat. Sie wird uebernommen statt neu gesucht: der
    Builder weiss, welche Rolle er zu welchem Key angelegt hat, eine
    Namenssuche wuerde bei zwei aehnlich benannten Rollen daneben
    greifen.

    Kanaele werden dagegen ueber die Template-Definition aufgeloest, weil
    der Builder sie nicht behaelt. Gesucht wird nach dem Slug, also nach
    dem Namen ohne Emoji und ohne Small Caps -- das ist derselbe
    Vergleich, den der Builder selbst zum Wiederfinden benutzt.
    """

    # ---------------------------------------------------------------- #
    # Kanaele: erst alles einsammeln, dann nach Slug nachschlagen
    # ---------------------------------------------------------------- #
    # Kategorien raus: sie tragen dieselben Namen wie ihre Kanaele nicht,
    # aber ein Slug-Zusammenstoss (Kategorie „logs“ / Kanal „logs“) wuerde
    # sonst die Kategorie zurueckgeben, und in die kann man nicht posten.
    category_ids = {category.id for category in guild.categories}

    by_slug: dict[str, discord.abc.GuildChannel] = {}
    for channel in guild.channels:
        if channel.id in category_ids:
            continue
        by_slug.setdefault(slugify(channel.name), channel)

    verify_channel = None
    rules_channel = None
    roles_channel = None
    ticket_channel = None
    announce_channel = None
    welcome_channel = None
    log_channels: dict[str, str] = {}

    for category_spec, spec in template.iter_channels():
        channel = by_slug.get(slugify(spec.display_name))
        if channel is None:
            # Der Kanal wurde nicht angelegt -- fehlende Rechte oder ein
            # Rate-Limit. Das steht bereits als Warnung im Bericht.
            continue

        if spec.widget is Widget.VERIFY and verify_channel is None:
            verify_channel = channel
        elif spec.widget is Widget.RULES and rules_channel is None:
            rules_channel = channel
        elif spec.widget is Widget.ROLES and roles_channel is None:
            roles_channel = channel
        elif spec.widget is Widget.TICKET and ticket_channel is None:
            ticket_channel = channel

        if spec.mode is ChannelMode.LOG:
            category = LOG_CATEGORY_BY_SLUG.get(slugify(spec.display_name))
            if category:
                log_channels[category] = str(channel.id)

        if spec.mode is ChannelMode.ANNOUNCE and announce_channel is None:
            announce_channel = channel

        # Der Willkommenskanal traegt kein Widget; er ist der erste
        # Textkanal der Gate-Kategorie, der kein Verify und keine Regeln
        # ist. Genau so liest ihn auch ein Mensch ab.
        if (
            welcome_channel is None
            and category_spec.visibility.value == "gate"
            and spec.widget is Widget.NONE
            and slugify(spec.display_name).startswith("willkommen")
        ):
            welcome_channel = channel

    # ---------------------------------------------------------------- #
    # Rollen
    # ---------------------------------------------------------------- #
    role_ids = {
        key: str(role.id)
        for key in _ROLE_KEYS
        if (role := roles.get(key)) is not None
    }
    staff_role_ids = [
        str(role.id)
        for key in _STAFF_KEYS
        if (role := roles.get(key)) is not None
    ]

    return {
        "template": template.key,
        "guild_id": str(guild.id),
        # Die Rollen, die der Hauptbot direkt einsetzt.
        "roles": role_ids,
        "staff_roles": staff_role_ids,
        # Die Kanaele, ebenfalls nach Zweck statt nach Namen.
        "channels": {
            "verify": str(verify_channel.id) if verify_channel else None,
            "rules": str(rules_channel.id) if rules_channel else None,
            "roles": str(roles_channel.id) if roles_channel else None,
            "tickets": str(ticket_channel.id) if ticket_channel else None,
            "announcements": str(announce_channel.id) if announce_channel else None,
            "welcome": str(welcome_channel.id) if welcome_channel else None,
        },
        "log_channels": log_channels,
        # Und alles im Rohzustand, damit das Dashboard eine Liste zeigen
        # kann und ein spaeterer Schritt nicht neu abfragen muss.
        "all_roles": [
            {"id": str(role.id), "name": role.name}
            for role in guild.roles
            if not role.is_default()
        ],
        "all_channels": [_channel_entry(c) for c in guild.channels],
    }
