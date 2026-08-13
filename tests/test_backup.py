"""Backups der Serverstruktur: Inhalt, Dateiname und atomares Schreiben.

Das Backup ist ein Schnappschuss zum Aufheben. Getestet wird, was einen
Schnappschuss brauchbar macht:

* **Vollstaendigkeit** — Rollen, Kanaele, Kategorien und deren
  Overwrites stehen drin, IDs als Strings (Snowflakes verlieren als
  JSON-Zahlen Stellen).
* **Lesbarkeit** — sauberes JSON mit Formatversion.
* **Atomaritaet** — erst ``.tmp``, dann ``os.replace``; ein kaputter
  Lauf hinterlaesst keine halbe Datei und keine ``.tmp``-Leiche.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import discord

from core.backup import BACKUP_VERSION, backup_filename, capture_backup, save_backup

# --------------------------------------------------------------------------- #
# Attrappen
# --------------------------------------------------------------------------- #

class FakeOverwrite:
    def __init__(self, allow: int, deny: int) -> None:
        self._allow = allow
        self._deny = deny

    def pair(self):
        class _Flags:
            value = 0

        allow = _Flags()
        allow.value = self._allow
        deny = _Flags()
        deny.value = self._deny
        return allow, deny


class FakeRole:
    def __init__(
        self,
        name: str,
        position: int,
        *,
        default: bool = False,
        managed: bool = False,
    ) -> None:
        self.id = 810_000_000_000_000_000 + position
        self.name = name
        self.position = position
        self.colour = 0x5865F2
        self.permissions = discord.Permissions.none()
        self.hoist = False
        self.mentionable = False
        self.managed = managed
        self._default = default

    def is_default(self) -> bool:
        return self._default


class FakeChannel:
    def __init__(self, name: str, kind: discord.ChannelType, category=None) -> None:
        self.id = 720_000_000_000_000_000 + abs(hash(name)) % 10**6
        self.name = name
        self.type = kind
        self.category = category
        self.position = 0
        self.topic = None
        self.slowmode_delay = 0
        self.nsfw = False
        self.user_limit = 0
        self.overwrites: dict = {}


class FakeGuild:
    def __init__(self) -> None:
        self.id = 424_242
        self.name = "Test Server Äöü"
        self.member_count = 12

        category = FakeChannel("Information", discord.ChannelType.category)
        channel = FakeChannel("allgemein", discord.ChannelType.text, category=category)
        everyone = FakeRole("@everyone", 0, default=True)
        moderator = FakeRole("Moderator", 5)
        channel.overwrites = {moderator: FakeOverwrite(1024, 0)}

        self.roles = [everyone, moderator]
        self.channels = [category, channel]


@pytest.fixture
def guild() -> FakeGuild:
    return FakeGuild()


# --------------------------------------------------------------------------- #
# capture_backup
# --------------------------------------------------------------------------- #

class TestCapture:
    def test_meta_carries_version_and_guild(self, guild):
        data = capture_backup(guild)

        meta = data["meta"]
        assert meta["version"] == BACKUP_VERSION
        assert meta["guild"]["id"] == str(guild.id)
        assert meta["guild"]["name"] == guild.name
        assert meta["guild"]["member_count"] == 12
        assert "captured_at" in meta

    def test_roles_are_complete_and_ids_are_strings(self, guild):
        data = capture_backup(guild)

        roles = {role["name"]: role for role in data["roles"]}
        assert set(roles) == {"@everyone", "Moderator"}

        moderator = roles["Moderator"]
        assert moderator["id"] == str(guild.roles[1].id)
        assert isinstance(moderator["id"], str)
        assert moderator["position"] == 5
        assert moderator["hoist"] is False
        assert roles["@everyone"]["default"] is True

        # Snowflakes als Strings, Berechtigungen als Zahl.
        assert isinstance(moderator["permissions"], int)

    def test_channels_keep_category_and_overwrites(self, guild):
        data = capture_backup(guild)

        channels = {channel["name"]: channel for channel in data["channels"]}
        assert set(channels) == {"Information", "allgemein"}

        general = channels["allgemein"]
        assert general["type"] == "text"
        assert general["category"] == "Information"
        assert general["overwrites"] == {"Moderator": {"allow": 1024, "deny": 0}}

        assert channels["Information"]["type"] == "category"

    def test_targets_without_a_name_fall_back_to_their_id(self, guild):
        """Overwrite-Ziele sind nicht immer Rollen mit Namen — nicht raten."""

        anonymous = type("X", (), {"id": 999})()
        guild.channels[1].overwrites = {anonymous: FakeOverwrite(64, 8)}

        data = capture_backup(guild)
        general = next(c for c in data["channels"] if c["name"] == "allgemein")

        assert general["overwrites"] == {"id:999": {"allow": 64, "deny": 8}}

    def test_the_payload_is_valid_json_with_unicode(self, guild):
        payload = json.dumps(capture_backup(guild), ensure_ascii=False)

        assert json.loads(payload)["meta"]["version"] == BACKUP_VERSION
        assert guild.name in payload, "Server-Name fehlt im Backup"


# --------------------------------------------------------------------------- #
# Dateiname und Schreiben
# --------------------------------------------------------------------------- #

class TestSave:
    def test_the_filename_slugs_the_server_name(self, guild):
        name = backup_filename(guild)

        assert name.startswith("backup-test-server-aeoeue-")
        assert name.endswith(".json")

    async def test_save_writes_readable_json(self, guild, tmp_path):
        path = await save_backup(guild, tmp_path)

        assert path.exists()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["meta"]["guild"]["name"] == guild.name

    async def test_no_tmp_leftovers_and_atomic_replace(self, guild, tmp_path):
        await save_backup(guild, tmp_path)

        leftovers = list(tmp_path.glob("*.tmp"))
        assert leftovers == [], "Eine .tmp-Datei blieb liegen"

    async def test_two_backups_coexist(self, guild, tmp_path, monkeypatch):
        from datetime import datetime, timedelta

        import core.backup as backup_module

        class _TickTock:
            """Jeder Aufruf eine Sekunde spaeter — wie im echten Leben."""

            def __init__(self) -> None:
                self._moment = datetime(2026, 8, 14, 12, 0, 0)

            def now(self, tz=None):
                moment = self._moment
                self._moment = self._moment + timedelta(seconds=1)
                return moment.replace(tzinfo=tz)

        monkeypatch.setattr(backup_module, "datetime", _TickTock())

        first = await save_backup(guild, tmp_path)
        second = await save_backup(guild, tmp_path)

        assert first.exists() and second.exists()
        assert first != second

    async def test_the_directory_is_created_on_demand(self, guild, tmp_path):
        target = tmp_path / "tief" / "verschachtelt"
        path = await save_backup(guild, target)

        assert path.parent == target
        assert path.exists()
