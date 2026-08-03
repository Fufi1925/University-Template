"""Die Landkarte, die der University Bot nach dem Bau bekommt.

Geprueft wird nicht "der Schluessel ist da", sondern "er zeigt auf den
richtigen Kanal". Ein Handover, das die Verify-Schleuse auf den
Memes-Kanal legt, hat alle Schluessel und ist trotzdem falsch.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import config
from core.builder import BuildMode, ServerBuilder
from core.handover import LOG_CATEGORY_BY_SLUG, build_handover
from core.registry import TemplateRegistry
from core.schema import ChannelMode, Widget
from core.small_caps import slugify
from tests.test_build_simulation import FakeGuild


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


@pytest.mark.asyncio
class TestHandover:
    async def test_verify_channel_is_the_verify_channel(self, registry):
        """Die ID muss auf den Kanal mit widget=verify zeigen."""

        guild, template, builder = await _build(registry)
        handover = build_handover(guild, template, builder.created_roles)

        verify_id = handover["channels"]["verify"]
        assert verify_id, "kein Verify-Kanal gefunden"

        channel = next(c for c in guild.channels if str(c.id) == verify_id)

        # Gegenprobe ueber das Template: welcher Kanal traegt widget=verify?
        expected = next(
            spec
            for _category, spec in template.iter_channels()
            if spec.widget is Widget.VERIFY
        )
        assert slugify(channel.name) == slugify(expected.display_name)

    async def test_verified_role_is_the_verified_role(self, registry):
        guild, template, builder = await _build(registry)
        handover = build_handover(guild, template, builder.created_roles)

        role_id = handover["roles"].get("verified")
        assert role_id, "keine Verified-Rolle"

        role = next(r for r in guild.roles if str(r.id) == role_id)
        assert slugify(role.name) == "verified"

        # Und sie ist nicht dieselbe wie Unverified -- der Unterschied ist
        # der ganze Punkt der Schleuse.
        assert handover["roles"]["unverified"] != role_id

    async def test_log_channels_land_in_the_right_category(self, registry):
        """Jeder Log-Kanal muss zur passenden Kategorie zeigen.

        Die Erwartung steht hier ausgeschrieben und wird *nicht* aus
        LOG_CATEGORY_BY_SLUG gelesen. Ein erster Versuch tat genau das
        und verglich die Tabelle mit sich selbst -- damit blieb der Test
        gruen, als ich zwei Kategorien vertauschte.
        """

        expected = {
            "member_moderation": "mod-logs",
            "join_leave_events": "mitglieder-logs",
            "message_events": "nachrichten-logs",
            "voice_events": "sprach-logs",
            "role_events": "rollen-logs",
            "channel_events": "kanal-logs",
            "reaction_events": "social-logs",
            "system_events": "server-logs",
        }

        guild, template, builder = await _build(registry)
        handover = build_handover(guild, template, builder.created_roles)

        logs = handover["log_channels"]
        assert set(logs) == set(expected), (
            f"zugeordnet: {sorted(logs)}, erwartet: {sorted(expected)}"
        )

        by_id = {str(c.id): c for c in guild.channels}
        for category, wanted_slug in expected.items():
            channel = by_id[logs[category]]
            assert slugify(channel.name) == wanted_slug, (
                f"{category} zeigt auf {slugify(channel.name)}, "
                f"erwartet {wanted_slug}"
            )

        # Und jeder Kanal genau einmal: zwei Kategorien im selben Kanal
        # waere ein stiller Datenverlust.
        assert len(set(logs.values())) == len(logs)

    async def test_every_log_channel_of_the_template_is_mapped_or_named(
        self, registry
    ):
        """Ein Log-Kanal ohne Zuordnung muss eine bewusste Entscheidung sein.

        Sonst faellt ein neuer Log-Kanal im Template stillschweigend unter
        den Tisch: er wird gebaut, aber nie befuellt.
        """

        template = registry.get("community")
        unmapped = {
            slugify(spec.display_name)
            for _category, spec in template.iter_channels()
            if spec.mode is ChannelMode.LOG
            and slugify(spec.display_name) not in LOG_CATEGORY_BY_SLUG
        }
        # Diese beiden haben im University Bot keine eigene Kategorie.
        assert unmapped == {"bot-logs", "einladungs-logs"}, (
            f"unerwartet ohne Zuordnung: {sorted(unmapped)}"
        )

    async def test_the_counting_channel_is_handed_over(self, registry):
        """Ohne diese ID bleibt das Zählspiel im Hauptbot auf None.

        Der Kanal steht dann da, der Template-Bot hat eine 1
        hineingeschrieben, und auf jede weitere Zahl passiert nichts.
        Genau so wurde es gemeldet.
        """

        guild, template, builder = await _build(registry)
        handover = build_handover(guild, template, builder.created_roles)

        channel_id = handover["channels"]["counting"]
        assert channel_id, "kein Zähl-Kanal übergeben"

        channel = next(c for c in guild.channels if str(c.id) == channel_id)
        # Gegenprobe über das Template: welcher Kanal trägt mode=counting?
        expected = next(
            spec
            for _category, spec in template.iter_channels()
            if spec.mode is ChannelMode.COUNTING
        )
        assert slugify(channel.name) == slugify(expected.display_name)

    async def test_the_j2c_channel_is_a_voice_channel(self, registry):
        """Join to Create auf einem Textkanal wäre wirkungslos."""

        guild, template, builder = await _build(registry)
        handover = build_handover(guild, template, builder.created_roles)

        channel_id = handover["channels"]["j2c"]
        assert channel_id, "kein Sprachkanal für Join to Create übergeben"

        channel = next(c for c in guild.channels if str(c.id) == channel_id)
        assert channel.type.name in ("voice", "stage_voice"), (
            f"j2c zeigt auf einen {channel.type.name}-Kanal"
        )

    async def test_the_ticket_channel_is_a_text_channel(self, registry):
        """In ein Forum lässt sich kein Panel mit Knöpfen stellen."""

        guild, template, builder = await _build(registry)
        handover = build_handover(guild, template, builder.created_roles)

        channel_id = handover["channels"]["tickets"]
        assert channel_id, "kein Ticket-Kanal übergeben"

        channel = next(c for c in guild.channels if str(c.id) == channel_id)
        assert channel.type.name == "text", (
            f"tickets zeigt auf einen {channel.type.name}-Kanal — "
            "dort erscheint kein Panel"
        )

    async def test_staff_roles_are_staff(self, registry):
        guild, template, builder = await _build(registry)
        handover = build_handover(guild, template, builder.created_roles)

        staff = set(handover["staff_roles"])
        assert staff, "keine Team-Rollen"

        # Verified ist kein Team. Stuende sie hier drin, bekaeme jedes
        # verifizierte Mitglied Zugriff auf Tickets und stuende auf der
        # Anti-Nuke-Whitelist.
        assert handover["roles"]["verified"] not in staff
        assert handover["roles"]["member"] not in staff
        assert handover["roles"]["moderator"] in staff
        assert handover["roles"]["admin"] in staff

    async def test_ids_are_strings(self, registry):
        """Snowflakes als JSON-Zahl verlieren die letzten Stellen."""

        guild, template, builder = await _build(registry)
        handover = build_handover(guild, template, builder.created_roles)

        for value in handover["roles"].values():
            assert isinstance(value, str)
        for value in handover["channels"].values():
            assert value is None or isinstance(value, str)
        for value in handover["log_channels"].values():
            assert isinstance(value, str)

    async def test_every_widget_channel_is_resolved(self, registry):
        """Nicht nur Verify: jedes Widget muss auf seinen eigenen Kanal zeigen.

        Ohne diesen Test bliebe eine Verwechslung von Regeln und
        Rollen-Vergabe unbemerkt -- beide sind vorhanden, beide sind
        eine gueltige ID, nur eben die falsche.
        """

        guild, template, builder = await _build(registry)
        handover = build_handover(guild, template, builder.created_roles)

        wanted = {
            "verify": Widget.VERIFY,
            "rules": Widget.RULES,
            "roles": Widget.ROLES,
        }
        by_id = {str(c.id): c for c in guild.channels}

        seen: set[str] = set()
        for key, widget in wanted.items():
            spec = next(
                (
                    spec
                    for _category, spec in template.iter_channels()
                    if spec.widget is widget
                ),
                None,
            )
            if spec is None:
                continue  # dieses Template kennt das Widget nicht
            channel_id = handover["channels"][key]
            assert channel_id, f"{key} wurde nicht aufgeloest"
            assert slugify(by_id[channel_id].name) == slugify(spec.display_name), (
                f"{key} zeigt auf {by_id[channel_id].name}"
            )
            seen.add(channel_id)

        # Drei Zwecke, drei verschiedene Kanaele.
        assert len(seen) == 3, "zwei Zwecke zeigen auf denselben Kanal"

    async def test_it_survives_a_half_built_server(self, registry):
        """Fehlt ein Kanal, kommt None -- kein Absturz, kein falscher Treffer.

        Genau dieser Fall tritt ein, wenn Discord mitten im Bau
        ratenbegrenzt oder dem Bot ein Recht fehlt: der Bericht traegt
        eine Warnung, aber der Kanal ist nicht da. Die Uebergabe darf
        daran nicht zerbrechen -- sonst gaebe es keinen Bericht, obwohl
        der halbe Server steht.
        """

        guild, template, builder = await _build(registry)

        # Zwei Sorten wegnehmen: ein Widget-Kanal und ein Log-Kanal.
        # Der Log-Kanal ist der wichtigere Fall, weil dort eine ID
        # gelesen wird -- an einem fehlenden Kanal knallt das sofort.
        verify_spec = next(
            spec
            for _category, spec in template.iter_channels()
            if spec.widget is Widget.VERIFY
        )
        doomed = {slugify(verify_spec.display_name), "mod-logs"}
        for channel in list(guild.channels):
            if slugify(channel.name) in doomed:
                del guild._channels[channel.id]

        handover = build_handover(guild, template, builder.created_roles)

        assert handover["channels"]["verify"] is None
        # Der fehlende Log-Kanal fehlt, statt als None eingetragen zu sein:
        # der Hauptbot wuerde sonst "None" als Kanal-ID speichern.
        assert "member_moderation" not in handover["log_channels"]
        # Der Rest bleibt heil.
        assert handover["channels"]["rules"]
        assert handover["log_channels"]["message_events"]
        assert handover["roles"]["verified"]

    async def test_json_round_trip(self, registry):
        """Das Ergebnis geht ueber HTTP -- es muss serialisierbar sein."""

        import json

        guild, template, builder = await _build(registry)
        handover = build_handover(guild, template, builder.created_roles)
        assert json.loads(json.dumps(handover)) == handover
