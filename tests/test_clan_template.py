"""Die Clan-Vorlage.

Aufgebaut wie der Gaming Hub, aber alles dreht sich um den Clan statt
um einzelne Spiele: Clan Talk statt Squad-Lobby, Fight Call vor dem
Match, War Room fuer die Planung.

Zwei Dinge, die hier wirklich schiefgehen koennen und deshalb geprueft
werden:

  * **Der Premium-Bereich muss dicht sein.** Eine Kategorie „premium“
    zu nennen und dann jedem zu zeigen waere schlimmer als gar keine:
    Leute zahlen fuer etwas, das ohnehin offen steht. Geprueft wird
    nicht der Name, sondern die Overwrite-Map -- also das, was Discord
    am Ende bekommt.

  * **Die Sprachkanaele muessen die versprochenen sein.** „Clan Talk“
    und „Fight Call“ stehen in der Beschreibung; fehlen sie, stimmt
    die Vorlage nicht mit dem ueberein, was im Dashboard angeboten
    wird.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import config
from core.permissions import VIP, category_overwrites, channel_overwrites
from core.registry import TemplateRegistry
from core.schema import ChannelKind, Visibility, Widget


@pytest.fixture(scope="module")
def registry():
    return TemplateRegistry(config.TEMPLATE_DIR).load()


@pytest.fixture(scope="module")
def clan(registry):
    template = registry.get("clan")
    assert template is not None, "die Clan-Vorlage fehlt"
    return template


class TestTheClanTemplateExists:
    def test_it_is_premium(self, clan):
        assert clan.premium is True

    def test_it_is_substantial(self, clan):
        """Ein Clan-Server soll tragen, nicht nur existieren."""

        assert clan.channel_count >= 60, clan.channel_count
        # Ein Clan lebt von Voice. Weniger als zwanzig Raeume waeren
        # fuer einen Server, dessen Zweck gemeinsames Spielen ist, zu
        # wenig.
        assert clan.voice_count >= 20, clan.voice_count

    def test_it_looks_like_the_gaming_hub(self, registry, clan):
        """Gleicher Aufbau -- das war die Ansage."""

        gaming = registry.get("gaming")
        assert gaming is not None

        # Beide bringen dieselben Grundbereiche mit.
        for label in ("willkommen", "information", "team", "leitung", "logs"):
            assert any(c.label == label for c in clan.categories), label
            assert any(c.label == label for c in gaming.categories), label

        # Und liegen in derselben Groessenordnung.
        assert abs(clan.category_count - gaming.category_count) <= 3


class TestTheClanVoiceRooms:
    """Die Kanäle, die der Vorlage ihren Namen geben."""

    def test_clan_talk_and_fight_call_exist(self, clan):
        voice = {
            spec.label
            for _category, spec in clan.iter_channels()
            if spec.kind.is_voice_like
        }

        for wanted in ("clan-talk", "fight-call", "war-room"):
            assert wanted in voice, f"{wanted} fehlt — {sorted(voice)}"

    def test_they_sit_in_the_clan_talks_category(self, clan):
        category = next(
            (c for c in clan.categories if c.label == "clan talks"), None
        )
        assert category is not None, "die Kategorie »clan talks« fehlt"

        labels = {spec.label for spec in category.channels}
        assert {"clan-talk", "fight-call", "war-room"} <= labels

    def test_the_fight_call_is_a_voice_channel(self, clan):
        """Ein Fight Call in einem Textkanal waere sinnlos."""

        for _category, spec in clan.iter_channels():
            if spec.label.startswith("fight-call"):
                assert spec.kind is ChannelKind.VOICE, spec.label


class TestThePremiumAreaIsActuallyClosed:
    """
    Der Teil, bei dem ein Fehler Geld kostet.

    Geprueft wird die Overwrite-Map, nicht der Name der Kategorie: nur
    sie entscheidet, wer den Bereich sieht.
    """

    def test_the_category_exists_and_is_vip(self, clan):
        category = next(
            (c for c in clan.categories if c.label == "premium"), None
        )
        assert category is not None, "die Premium-Kategorie fehlt"
        assert category.visibility is Visibility.VIP, (
            f"sie steht auf {category.visibility.value} — damit sähe sie "
            "jeder"
        )

    def test_everyone_is_locked_out(self, clan):
        """@everyone darf den Bereich nicht sehen."""

        category = next(c for c in clan.categories if c.label == "premium")

        guild = _FakeGuild()
        overwrites = category_overwrites(
            guild,
            category.visibility,
            guild.role_map,
            staff_keys=frozenset({"moderator", "admin"}),
            leadership_keys=frozenset({"admin"}),
        )

        everyone = overwrites.get(guild.default_role)
        assert everyone is not None, "für @everyone steht keine Regel da"
        assert everyone.view_channel is False, (
            "@everyone darf den Premium-Bereich sehen — er ist offen"
        )

    def test_vip_gets_in(self, clan):
        category = next(c for c in clan.categories if c.label == "premium")

        guild = _FakeGuild()
        overwrites = category_overwrites(
            guild,
            category.visibility,
            guild.role_map,
            staff_keys=frozenset({"moderator", "admin"}),
            leadership_keys=frozenset({"admin"}),
        )

        vip_role = guild.role_map[VIP]
        entry = overwrites.get(vip_role)
        assert entry is not None, "VIP steht gar nicht in der Regelliste"
        assert entry.view_channel is True, "VIP kommt nicht in den Bereich"

    def test_a_normal_member_stays_out(self, clan):
        """
        Die Verified-Rolle darf nicht hineinkommen.

        Das ist der Unterschied zwischen „nur für zahlende Mitglieder“
        und „für jeden, der die Schleuse passiert hat“.
        """

        category = next(c for c in clan.categories if c.label == "premium")

        guild = _FakeGuild()
        overwrites = category_overwrites(
            guild,
            category.visibility,
            guild.role_map,
            staff_keys=frozenset({"moderator", "admin"}),
            leadership_keys=frozenset({"admin"}),
        )

        member_role = guild.role_map["member"]
        entry = overwrites.get(member_role)
        # Entweder gar nicht genannt (erbt das Verbot von @everyone)
        # oder ausdrücklich ausgesperrt. Beides ist in Ordnung; ein
        # ausdrückliches "darf sehen" nicht.
        if entry is not None:
            assert entry.view_channel is not True, (
                "eine normale Mitgliedsrolle sieht den Premium-Bereich"
            )

    def test_no_premium_channel_declares_itself_visible(self, clan):
        """
        Ein einzelner Kanal darf die Kategorie nicht aushebeln.

        Genau das ist in diesem Projekt schon passiert: ein
        ``readonly``-Kanal in einer versteckten Kategorie machte sich
        wieder sichtbar (``vip-vorteile``, ``rp/akten``).

        Geprüft wird die **Wirkung**, nicht die Absicht. Ein erster
        Versuch verlangte, dass kein Kanal eine weichere Sichtbarkeit
        trägt als die Kategorie -- und schlug bei
        ``premium-vorteile: readonly`` an, obwohl der Kanal
        nachweislich dicht ist: ``channel_overwrites`` nimmt seit dem
        damaligen Fix immer die strengere der beiden Stufen. Der Test
        hätte also eine Schreibweise verboten, die längst sicher ist,
        statt ein echtes Loch zu finden.
        """

        category = next(c for c in clan.categories if c.label == "premium")
        guild = _FakeGuild()

        for spec in category.channels:
            overwrites = channel_overwrites(
                guild,
                category.visibility,
                category.visibility_for(spec),
                guild.role_map,
                staff_keys=frozenset({"moderator", "admin"}),
                leadership_keys=frozenset({"admin"}),
            )

            # Leer heißt: der Kanal erbt die Kategorie -- also dicht.
            if not overwrites:
                continue

            everyone = overwrites.get(guild.default_role)
            assert everyone is not None and everyone.view_channel is False, (
                f"{spec.label} ist für @everyone sichtbar, obwohl die "
                "Kategorie versteckt ist"
            )


class TestTheMemberAreaIsForTheRoster:
    def test_it_is_not_public(self, clan):
        category = next(
            (c for c in clan.categories if c.label == "mitglieder"), None
        )
        assert category is not None, "der Mitglieder-Bereich fehlt"
        assert category.visibility is not Visibility.PUBLIC


class TestTheClanTemplateBehavesLikeTheOthers:
    """Was für jede Vorlage gilt, gilt auch hier."""

    def test_it_has_a_gate(self, clan):
        assert any(
            c.visibility is Visibility.GATE for c in clan.categories
        )

    def test_it_has_verify_and_rules(self, clan):
        widgets = {spec.widget for _c, spec in clan.iter_channels()}
        assert Widget.VERIFY in widgets
        assert Widget.RULES in widgets

    def test_it_has_the_full_log_suite(self, clan):
        logs = next((c for c in clan.categories if c.label == "logs"), None)
        assert logs is not None
        assert len(logs.channels) >= 10

    def test_the_capabilities_match_reality(self, clan):
        """
        Was die Vorlage meldet, muss stimmen.

        Meldet sie ein Ticket-Panel, das es nicht gibt, bietet das
        Dashboard den Schritt an und er läuft ins Leere.
        """

        caps = clan.capabilities
        widgets = {spec.widget for _c, spec in clan.iter_channels()}

        assert caps["verify"] is (Widget.VERIFY in widgets)
        assert caps["rules"] is (Widget.RULES in widgets)
        assert caps["selfroles"] is (Widget.ROLES in widgets)
        assert caps["tickets"] is (Widget.TICKET in widgets)


# --------------------------------------------------------------------------- #
# Attrappe
# --------------------------------------------------------------------------- #


class _FakeRole:
    def __init__(self, name):
        self.name = name

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        return isinstance(other, _FakeRole) and other.name == self.name


class _FakeGuild:
    """Gerade so viel Server, wie ``category_overwrites`` anfasst."""

    def __init__(self):
        self.default_role = _FakeRole("@everyone")
        self.me = _FakeRole("University Bot")
        # Die Rollen, die die Rechteregeln nachschlagen.
        self.role_map = {
            key: _FakeRole(key)
            for key in (
                "unverified", "verified", "member", VIP, "booster",
                "partner", "support", "moderator", "senior_mod", "admin",
                "leadership", "owner",
            )
        }
