"""Wer darf wo schreiben — geprüft am fertig gebauten Server.

Zwei Sorten Fehler soll das hier verhindern:

* **Ein Kanal, in den jeder schreiben kann, obwohl er es nicht soll.**
  Willkommen, Verify, Regeln und Ankündigungen sind zum Lesen da. Die
  Gate-Kategorie gab Unverifizierten früher volles Schreibrecht — und
  genau dorthin kommen Spam-Bots, denn sie verifizieren sich nie.

* **Ein Kanal, den jeder sieht, obwohl er nicht soll.** Team, Leitung,
  Logs und der VIP-Bereich sind für @everyone unsichtbar.

Geprüft wird nicht die Template-Datei, sondern der *gebaute* Server:
die Rechte entstehen aus Kategorie-Sichtbarkeit plus Kanal-Abweichung,
und ob die Rechnung stimmt, sieht man erst am Ergebnis.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import config
from core.builder import BuildMode, ServerBuilder
from core.registry import TemplateRegistry
from core.schema import ChannelKind, Visibility
from core.small_caps import slugify
from tests.test_build_simulation import FakeCategory, FakeGuild


@pytest.fixture(scope="module")
def registry():
    return TemplateRegistry(config.TEMPLATE_DIR).load()


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    async def instant(_seconds):
        return None

    monkeypatch.setattr("core.builder.asyncio.sleep", instant)


async def _build(registry, key="community"):
    template = registry.get(key)
    guild = FakeGuild()
    builder = ServerBuilder(guild, template)
    await builder.apply(BuildMode.EXTEND, write_intros=False)
    return guild, template, builder


def _effective(guild, channel, role, field: str):
    """Was für `role` in `channel` gilt — inklusive Vererbung.

    Discord wertet die Kategorie aus, wenn der Kanal selbst nichts sagt.
    Ein Test, der nur den Kanal ansieht, liest bei jedem geerbten Recht
    None und hält das fälschlich für „nicht gesetzt“.
    """

    own = channel.overwrites.get(role)
    value = getattr(own, field, None) if own else None
    if value is not None:
        return value

    category = getattr(channel, "category", None)
    if category is None:
        return None
    inherited = category.overwrites.get(role)
    return getattr(inherited, field, None) if inherited else None


def _by_slug(guild):
    return {
        slugify(c.name): c
        for c in guild.channels
        if not isinstance(c, FakeCategory)
    }


@pytest.mark.asyncio
class TestNobodyWritesWhereTheyShouldNot:
    async def test_the_gate_is_read_only(self, registry):
        """Willkommen, Verify, Regeln, FAQ: lesen ja, schreiben nein.

        Das war der Fehler: die Gate-Kategorie gab @everyone *und* der
        Unverifiziert-Rolle volles Schreibrecht. Wer gerade beigetreten
        war, konnte im Verify-Kanal posten — und wer sich nie
        verifiziert, kommt nirgendwo anders hin. Spam-Bots landen genau
        dort.
        """

        guild, template, _builder = await _build(registry)
        everyone = guild.default_role
        unverified = next(
            (r for r in guild.roles if slugify(r.name) == "unverified"), None
        )
        assert unverified is not None, "keine Unverifiziert-Rolle gebaut"

        channels = _by_slug(guild)
        gate_specs = [
            spec
            for category, spec in template.iter_channels()
            if category.visibility is Visibility.GATE
        ]
        assert gate_specs, "keine Gate-Kanäle im Template"

        for spec in gate_specs:
            channel = channels[slugify(spec.display_name)]
            for role, label in ((everyone, "@everyone"), (unverified, "Unverified")):
                assert _effective(guild, channel, role, "send_messages") is False, (
                    f"{spec.label}: {label} darf schreiben"
                )
                # Sehen müssen sie ihn -- sonst kommt niemand durch.
                assert _effective(guild, channel, role, "view_channel") is True, (
                    f"{spec.label}: {label} sieht den Kanal nicht"
                )

    async def test_announcements_are_read_only(self, registry):
        """Ankündigungen und Infos schreibt das Team, nicht jeder."""

        guild, template, _builder = await _build(registry)
        everyone = guild.default_role
        channels = _by_slug(guild)

        # Nur Kanäle, die @everyone überhaupt sieht. `vip-vorteile` ist
        # zwar als readonly markiert, liegt aber im VIP-Bereich -- dort
        # gewinnt die Sichtbarkeit der Kategorie, und wer den Kanal nicht
        # sieht, kann auch nicht hineinschreiben. Mein erster Versuch
        # zählte ihn mit und war deshalb rot, ohne dass etwas falsch war.
        readonly = [
            spec
            for category, spec in template.iter_channels()
            if category.visibility_for(spec) is Visibility.READONLY
            and category.visibility
            in {Visibility.PUBLIC, Visibility.READONLY, Visibility.GATE}
            and not spec.kind.is_voice_like
        ]
        assert readonly, "keine Nur-Lesen-Kanäle im Template"

        for spec in readonly:
            channel = channels[slugify(spec.display_name)]
            assert _effective(guild, channel, everyone, "send_messages") is False, (
                f"{spec.label}: @everyone darf schreiben"
            )
            assert _effective(guild, channel, everyone, "view_channel") is True, (
                f"{spec.label}: @everyone sieht ihn nicht — dann ist die "
                "Nur-Lesen-Prüfung wertlos"
            )

    async def test_the_ticket_channel_is_read_only(self, registry):
        """Im Ticket-Kanal drückt man den Knopf, man schreibt nicht hinein.

        Sonst steht unter dem Panel eine Wand aus »hallo?« und »hilfe
        bitte«, und die eigentlichen Tickets gehen darin unter.
        """

        guild, _template, _builder = await _build(registry)
        everyone = guild.default_role
        channel = _by_slug(guild)["ticket-eroeffnen"]

        assert _effective(guild, channel, everyone, "send_messages") is False
        assert _effective(guild, channel, everyone, "view_channel") is True

    async def test_the_normal_chats_stay_open(self, registry):
        """Gegenprobe: irgendwo muss man ja reden dürfen.

        Ohne diese Prüfung wären die drei oben auch grün, wenn der ganze
        Server stummgeschaltet wäre.
        """

        guild, _template, _builder = await _build(registry)
        everyone = guild.default_role
        channels = _by_slug(guild)

        for slug in ("allgemein", "plauderecke", "memes"):
            channel = channels[slug]
            assert _effective(guild, channel, everyone, "send_messages") is True, (
                f"{slug}: dort darf niemand schreiben"
            )


@pytest.mark.asyncio
class TestPrivateStaysPrivate:
    async def test_staff_areas_are_hidden(self, registry):
        """Team, Leitung und Logs sieht @everyone nicht."""

        guild, template, _builder = await _build(registry)
        everyone = guild.default_role
        channels = _by_slug(guild)

        hidden = [
            spec
            for category, spec in template.iter_channels()
            if category.visibility in {Visibility.STAFF, Visibility.LEADERSHIP}
        ]
        assert hidden, "keine Team-Kanäle im Template"

        for spec in hidden:
            channel = channels[slugify(spec.display_name)]
            assert _effective(guild, channel, everyone, "view_channel") is False, (
                f"{spec.label}: @everyone sieht den Team-Kanal"
            )

    async def test_the_vip_area_is_hidden(self, registry):
        guild, template, _builder = await _build(registry)
        everyone = guild.default_role
        channels = _by_slug(guild)

        for category, spec in template.iter_channels():
            if category.visibility is not Visibility.VIP:
                continue
            channel = channels[slugify(spec.display_name)]
            assert _effective(guild, channel, everyone, "view_channel") is False, (
                f"{spec.label}: der VIP-Bereich ist offen"
            )

    async def test_every_template_keeps_its_logs_private(self, registry):
        """Nicht nur community -- Log-Kanäle verraten alles über einen Server."""

        for template in registry.all:
            guild = FakeGuild()
            await ServerBuilder(guild, template).apply(
                BuildMode.EXTEND, write_intros=False
            )
            everyone = guild.default_role
            channels = _by_slug(guild)

            for category, spec in template.iter_channels():
                if category.visibility not in {
                    Visibility.STAFF, Visibility.LEADERSHIP
                }:
                    continue
                channel = channels.get(slugify(spec.display_name))
                if channel is None:
                    continue
                assert _effective(guild, channel, everyone, "view_channel") is False, (
                    f"{template.key}/{spec.label}: für alle sichtbar"
                )


@pytest.mark.asyncio
class TestVoiceChannelsAreUsable:
    async def test_public_voice_can_be_joined(self, registry):
        """Ein Sprachkanal, den niemand betreten kann, ist Dekoration."""

        guild, template, _builder = await _build(registry)
        everyone = guild.default_role
        channels = _by_slug(guild)

        checked = 0
        for category, spec in template.iter_channels():
            if spec.kind is not ChannelKind.VOICE:
                continue
            if category.visibility is not Visibility.PUBLIC:
                continue
            channel = channels[slugify(spec.display_name)]
            assert _effective(guild, channel, everyone, "connect") is True, (
                f"{spec.label}: niemand kann beitreten"
            )
            checked += 1

        assert checked > 5, f"nur {checked} Sprachkanäle geprüft"
