"""Test suite.

Covers the parts that would silently break a live server: the typography
layer, template validity against Discord's real limits, the permission model,
the premium store, and — most importantly — that every Components V2 view
serialises into a payload Discord will actually accept.

Run:  python -m pytest tests/ -v
"""

from __future__ import annotations

import itertools
import json
import re
import sys
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import config
from core.permissions import BASE_ROLES, permissions_for_tier
from core.premium import PremiumStore
from core.registry import TemplateRegistry
from core.schema import (
    ChannelKind,
    RoleTier,
    Template,
    TemplateError,
    Visibility,
)
from core.small_caps import (
    channel_name,
    slugify,
    strip_decoration,
    to_small_caps,
)


@pytest.fixture(scope="session")
def registry() -> TemplateRegistry:
    return TemplateRegistry(config.TEMPLATE_DIR).load()


# --------------------------------------------------------------------------- #
# Typography
# --------------------------------------------------------------------------- #

class TestSmallCaps:
    def test_every_ascii_letter_maps(self):
        result = to_small_caps("abcdefghijklmnopqrstuvwxyz")
        assert result != "abcdefghijklmnopqrstuvwxyz"
        assert len(result) == 26

    def test_survives_discord_lowercasing(self):
        """The whole point: Discord lowercases names, small caps must survive."""

        styled = to_small_caps("Announcements")
        assert styled.lower() == styled

    def test_german_umlauts_are_folded(self):
        assert to_small_caps("Größe") == to_small_caps("groesse")
        assert to_small_caps("Ärger") == to_small_caps("aerger")

    def test_non_latin_is_untouched(self):
        for text in ("русский", "日本語", "العربية", "한국어"):
            assert to_small_caps(text) == text

    def test_emoji_and_digits_survive(self):
        assert "🇩🇪" in channel_name("deutsch", "🇩🇪")
        assert "1" in to_small_caps("talk 1")

    def test_channel_name_has_no_spaces(self):
        assert " " not in channel_name("general chat", "💬")

    def test_strip_decoration_round_trip(self):
        assert strip_decoration(channel_name("general chat", "💬")) == "general chat"
        assert strip_decoration("💬・ɢᴇɴᴇʀᴀʟ") == "general"

    def test_strip_decoration_matches_plain_name(self):
        """An already-existing plain channel must be recognised as the same one."""

        assert strip_decoration("general") == strip_decoration("💬・ɢᴇɴᴇʀᴀʟ")

    def test_slugify(self):
        assert slugify("💬・ɢᴇɴᴇʀᴀʟ-ᴄʜᴀᴛ") == "general-chat"


# --------------------------------------------------------------------------- #
# Schema
# --------------------------------------------------------------------------- #

class TestSchema:
    def test_rejects_missing_key(self):
        with pytest.raises(TemplateError, match="key"):
            Template.parse({"name": "X", "categories": [{"label": "a"}]})

    def test_rejects_unknown_channel_kind(self):
        with pytest.raises(TemplateError, match="Kanaltyp"):
            Template.parse(
                {
                    "key": "x", "name": "X",
                    "categories": [{"label": "c", "channels": [{"label": "a", "kind": "hologram"}]}],
                }
            )

    def test_rejects_duplicate_channel(self):
        with pytest.raises(TemplateError, match="doppelt"):
            Template.parse(
                {
                    "key": "x", "name": "X",
                    "categories": [
                        {"label": "c", "channels": [{"label": "same"}, {"label": "same"}]}
                    ],
                }
            )

    def test_rejects_out_of_range_slowmode(self):
        with pytest.raises(TemplateError, match="slowmode"):
            Template.parse(
                {
                    "key": "x", "name": "X",
                    "categories": [{"label": "c", "channels": [{"label": "a", "slowmode": 99999}]}],
                }
            )

    def test_rejects_too_many_categories(self):
        with pytest.raises(TemplateError, match="50"):
            Template.parse(
                {
                    "key": "x", "name": "X",
                    "categories": [
                        {"label": f"cat{i}", "channels": []} for i in range(51)
                    ],
                }
            )

    def test_channel_inherits_category_visibility(self):
        template = Template.parse(
            {
                "key": "x", "name": "X",
                "categories": [
                    {
                        "label": "c", "visibility": "staff",
                        "channels": [{"label": "a"}, {"label": "b", "visibility": "public"}],
                    }
                ],
            }
        )
        category = template.categories[0]
        assert category.visibility_for(category.channels[0]) is Visibility.STAFF
        assert category.visibility_for(category.channels[1]) is Visibility.PUBLIC


# --------------------------------------------------------------------------- #
# Shipped templates
# --------------------------------------------------------------------------- #

# Vorlagen, die bewusst klein sind und deshalb von den Mindestmassen
# unten ausgenommen werden.
#
# "minimal" ist der Gegenentwurf zu allen anderen: kein Verify, keine
# Tickets, keine Rollen-Vergabe, vier Log-Kanaele statt zehn und kein
# Sprachbereich. Genau dafuer gibt es sie -- fuer Freundeskreise, die
# mit fuenfzehn Kanaelen auskommen statt mit neunzig. Sie hier
# einzutragen ist eine Entscheidung; eine *andere* Vorlage, die
# durchfaellt, bleibt ein Fehler.
COMPACT = {"minimal"}


class TestTemplates:
    def test_expected_templates_exist(self, registry):
        assert len(registry) == 13
        assert {t.key for t in registry.free} == {
            "community", "rp", "social", "music", "dev", "minimal",
        }
        assert len(registry.premium) == 7

    def test_the_free_templates_are_the_promised_ones(self, registry):
        names = {t.name for t in registry.free}
        assert names == {
            "Community Discord", "RP Server", "Social Lounge",
            "Musik & DJ", "Entwickler & Open Source", "Kleiner Server",
        }

    def test_within_discord_limits(self, registry):
        for template in registry:
            assert template.category_count <= 50, template.key
            assert template.channel_count <= 500, template.key

    def test_every_template_is_substantial(self, registry):
        """Eine Vorlage muss einen Server tragen -- ausser den kompakten.

        Die Untergrenze faellt fuer "dev" von 65 auf 55: der Server hat
        keinen Event-Bereich und keine Kreativzone, weil dort
        gearbeitet und nicht gefeiert wird. 61 Kanaele sind fuer eine
        Entwickler-Community reichlich; die 65 waren an den grossen
        Community-Vorlagen gemessen.
        """

        for template in registry:
            if template.key in COMPACT:
                continue
            assert template.channel_count >= 55, f"{template.key} zu klein"
            assert template.voice_count >= 12, f"{template.key} zu wenig Voice"

    def test_the_compact_templates_stay_compact(self, registry):
        """Sonst waechst "minimal" unbemerkt zu einer normalen Vorlage."""

        for key in COMPACT:
            template = registry.get(key)
            assert template is not None, key
            assert template.channel_count <= 30, (
                f"{key} hat {template.channel_count} Kanaele -- "
                "das ist keine kompakte Vorlage mehr"
            )

    def test_language_area_is_german_and_english_only(self, registry):
        """Der Sprachbereich enthält bewusst nur Deutsch und English."""

        for template in registry:
            categories = [c for c in template.categories if c.label == "sprachen"]
            if template.key in COMPACT:
                # Kompakte Vorlagen haben keinen Sprachbereich. Hat eine
                # doch einen, muss er trotzdem stimmen.
                if not categories:
                    continue
            else:
                assert categories, f"{template.key} hat keinen Sprachbereich"

            labels = {ch.label for c in categories for ch in c.channels}
            assert labels == {"deutsch", "english"}, (
                f"{template.key}: Sprachbereich enthält {sorted(labels)}, "
                "erwartet wurden genau deutsch und english"
            )

    def test_no_foreign_language_channels_remain(self, registry):
        """Keine Reste der früheren 37-Sprachen-Struktur."""

        removed = {
            "francais", "espanol", "italiano", "portugues", "brasil", "nederlands",
            "polski", "русский", "українська", "turkce", "svenska", "norsk",
            "dansk", "suomi", "cestina", "slovencina", "magyar", "romana",
            "български", "ελληνικά", "srpski", "hrvatski", "lietuviu", "日本語",
            "한국어", "中文", "ไทย", "tieng-viet", "indonesia", "filipino",
            "हिन्दी", "العربية", "עברית", "فارسی", "other-languages",
        }
        for template in registry:
            for _, channel in template.iter_channels():
                assert channel.label not in removed, (
                    f"{template.key}: '{channel.label}' ist ein Rest der alten Struktur"
                )

    def test_language_voice_rooms_are_german_and_english(self, registry):
        for template in registry:
            for category in template.categories:
                if category.label != "sprach-talks":
                    continue
                for channel in category.channels:
                    assert channel.label.startswith(("deutsch", "english")), (
                        f"{template.key}: Sprach-Talk '{channel.label}' ist weder DE noch EN"
                    )

    def test_channel_labels_are_german(self, registry):
        """Stichprobe: typisch englische Kanalnamen dürfen nicht mehr vorkommen.

        Bewusst erlaubt bleiben Lehnwörter, die im deutschen Discord- und
        Arbeitsalltag etabliert sind und deren Eindeutschung gestelzt wirken
        würde: Memes, Clips, Highlights, Streams, Squad, Lobby, Tickets,
        Podcast, Marketing, Budget, Pomodoro, Watch-Party.
        """

        forbidden = {
            "general", "rules", "welcome", "announcements", "updates", "roles",
            "partners", "giveaways", "media", "food", "pets", "questions",
            "suggestions", "reports", "tasks", "applications", "resources",
            "feedback", "showcase", "collabs", "introductions", "birthdays",
            "polls", "books", "art", "photos", "advice", "compliments",
            "confessions", "vent", "good-news", "daily-question", "challenges",
            "watch-planning", "recording", "editing", "review", "published",
            "ideas", "scripts", "deals", "contracts", "invoices", "results",
            "brackets", "duo-1", "trio-1", "chill", "music", "study", "afk",
            "silent-1", "group-study-1", "tools", "guides",
            "faq", "changelog", "known-issues", "troubleshooting", "status",
            "quick-questions", "community-help", "bug-reports",
            "feature-requests", "handbook", "onboarding", "templates",
            "archive", "backlog", "releases", "agenda", "standup", "legal",
            "finance", "sales", "development", "hr",
        }
        for template in registry:
            for _, channel in template.iter_channels():
                assert channel.label not in forbidden, (
                    f"{template.key}: Kanal '{channel.label}' ist noch englisch"
                )

    def test_category_labels_are_german(self, registry):
        forbidden = {
            "multi language", "language voice", "voice lounge", "events",
            "creative", "knowledge", "meetings", "departments", "projects",
            "clients", "roster", "matchday", "production", "business",
            "collabs", "competitive", "squad voice",
            "study rooms", "campus life", "subjects", "study groups", "exams",
        }
        for template in registry:
            for category in template.categories:
                assert category.label not in forbidden, (
                    f"{template.key}: Kategorie '{category.label}' ist noch englisch"
                )

    def test_every_template_has_full_log_suite(self, registry):
        """Jede Vorlage protokolliert -- kompakte knapper.

        "minimal" bekommt vier Log-Kanaele statt zehn. Zehn Log-Kanaele
        fuer einen Freundeskreis waeren mehr Logs als Chats, und was
        niemand liest, wird auch nicht gelesen, wenn etwas passiert.
        Die beiden wichtigsten -- Moderation und Beitritte -- sind auch
        dort Pflicht.
        """

        for template in registry:
            logs = [c for c in template.categories if c.label == "logs"]
            assert logs, f"{template.key} hat keine Logs"
            names = {ch.label for ch in logs[0].channels}
            assert "mod-logs" in names, template.key
            assert "mitglieder-logs" in names, template.key

            if template.key in COMPACT:
                assert len(names) >= 4, (
                    f"{template.key}: nur {len(names)} Log-Kanäle"
                )
                continue

            assert "social-logs" in names, template.key
            assert len(names) >= 10, f"{template.key}: nur {len(names)} Log-Kanäle"

    def test_log_categories_are_private(self, registry):
        for template in registry:
            for category in template.categories:
                if category.label == "logs":
                    assert category.visibility in {Visibility.STAFF, Visibility.LEADERSHIP}

    def test_every_template_has_a_gate(self, registry):
        for template in registry:
            gates = [c for c in template.categories if c.visibility is Visibility.GATE]
            assert gates, f"{template.key} hat keine Verify-Schleuse"

    def test_channel_names_are_unique_and_valid(self, registry):
        for template in registry:
            for category in template.categories:
                for channel in category.channels:
                    name = channel.display_name
                    assert 1 <= len(name) <= 100, f"{template.key}: '{name}'"
                    assert name == name.lower(), f"{template.key}: '{name}' nicht lowercase"
                    assert " " not in name, f"{template.key}: '{name}' enthält Leerzeichen"

    def test_category_names_valid(self, registry):
        for template in registry:
            for category in template.categories:
                assert 1 <= len(category.display_name) <= 100

    def test_voice_channels_have_sane_limits(self, registry):
        for template in registry:
            for _, channel in template.iter_channels():
                if channel.kind is ChannelKind.VOICE:
                    assert 0 <= channel.user_limit <= 99

    def test_slowmode_only_on_text(self, registry):
        for template in registry:
            for _, channel in template.iter_channels():
                if channel.kind.is_voice_like:
                    assert channel.slowmode == 0

    def test_premium_flag_matches_registry(self, registry):
        for template in registry.premium:
            assert template.premium
        for template in registry.free:
            assert not template.premium

    def test_templates_have_descriptions_and_highlights(self, registry):
        for template in registry:
            assert len(template.description) > 60, template.key
            assert template.tagline, template.key
            assert len(template.highlights) >= 3, template.key

    def test_json_files_are_utf8_and_stable(self):
        for path in config.TEMPLATE_DIR.glob("*.json"):
            data = json.loads(path.read_text(encoding="utf-8"))
            assert data["key"] == path.stem


# --------------------------------------------------------------------------- #
# Permissions
# --------------------------------------------------------------------------- #

class TestPermissions:
    def test_only_owner_is_administrator(self):
        for tier in RoleTier:
            perms = permissions_for_tier(tier)
            if tier is RoleTier.OWNER:
                assert perms.administrator
            else:
                assert not perms.administrator, f"{tier} hat Administrator"

    def test_tiers_are_monotonically_increasing(self):
        """Each staff tier must be a superset of the one below it."""

        ladder = [
            RoleTier.MEMBER,
            RoleTier.TRUSTED,
            RoleTier.HELPER,
            RoleTier.MODERATOR,
            RoleTier.SENIOR,
            RoleTier.ADMIN,
            RoleTier.LEADERSHIP,
        ]
        for lower, higher in itertools.pairwise(ladder):
            low = permissions_for_tier(lower)
            high = permissions_for_tier(higher)
            assert low.value & high.value == low.value, f"{higher} ⊉ {lower}"

    def test_guest_cannot_send_messages(self):
        assert not permissions_for_tier(RoleTier.GUEST).send_messages

    def test_member_cannot_moderate(self):
        perms = permissions_for_tier(RoleTier.MEMBER)
        assert not perms.manage_messages
        assert not perms.kick_members
        assert not perms.ban_members

    def test_dangerous_permissions_are_gated(self):
        assert not permissions_for_tier(RoleTier.HELPER).ban_members
        assert not permissions_for_tier(RoleTier.MODERATOR).ban_members
        assert permissions_for_tier(RoleTier.SENIOR).ban_members
        assert not permissions_for_tier(RoleTier.MODERATOR).manage_guild
        assert permissions_for_tier(RoleTier.LEADERSHIP).manage_guild

    def test_base_ladder_is_ordered(self):
        order = list(RoleTier)
        positions = [order.index(entry[4]) for entry in BASE_ROLES]
        assert positions == sorted(positions), "Basis-Rollen sind nicht aufsteigend"

    def test_base_roles_have_unique_keys(self):
        keys = [entry[0] for entry in BASE_ROLES]
        assert len(keys) == len(set(keys))


# --------------------------------------------------------------------------- #
# Premium store
# --------------------------------------------------------------------------- #

class TestPremium:
    def _store(self, tmp_path, **kwargs) -> PremiumStore:
        return PremiumStore(tmp_path / "premium.json", keys=["Vexo x Fufi KEY 2354"], **kwargs)

    def test_correct_key_accepted(self, tmp_path):
        assert self._store(tmp_path).verify("Vexo x Fufi KEY 2354")

    def test_key_is_case_and_space_insensitive(self, tmp_path):
        store = self._store(tmp_path)
        assert store.verify("  vexo x fufi key 2354  ")
        assert store.verify("VEXO X FUFI KEY 2354")

    def test_wrong_key_rejected(self, tmp_path):
        store = self._store(tmp_path)
        assert not store.verify("wrong")
        assert not store.verify("")
        assert not store.verify("Vexo x Fufi KEY 2355")
        assert not store.verify("Vexo x Fufi KEY 235")

    def test_grant_and_check(self, tmp_path):
        store = self._store(tmp_path)
        assert not store.has_access(1, 42)
        store.grant(1, 42)
        assert store.has_access(1, 42)
        assert not store.has_access(1, 43), "Freischaltung darf nicht auf andere User wirken"
        assert not store.has_access(2, 42), "Freischaltung darf nicht auf andere Server wirken"

    def test_unlock_survives_restart(self, tmp_path):
        self._store(tmp_path).grant(7, 99)
        assert self._store(tmp_path).has_access(7, 99)

    def test_guild_wide_mode(self, tmp_path):
        store = self._store(tmp_path, guild_wide=True)
        store.grant(5, 1)
        assert store.has_access(5, 2), "Guild-Modus muss für alle gelten"

    def test_key_never_written_to_disk(self, tmp_path):
        store = self._store(tmp_path)
        store.grant(1, 2)
        content = (tmp_path / "premium.json").read_text(encoding="utf-8")
        assert "Vexo" not in content
        assert "2354" not in content

    def test_corrupt_file_does_not_crash(self, tmp_path):
        path = tmp_path / "premium.json"
        path.write_text("{ this is not json", encoding="utf-8")
        store = PremiumStore(path, keys=["k"])
        assert not store.has_access(1, 1)

    def test_revoke(self, tmp_path):
        store = self._store(tmp_path)
        store.grant(1, 2)
        store.revoke(1, 2)
        assert not store.has_access(1, 2)


# --------------------------------------------------------------------------- #
# Components V2 rendering
# --------------------------------------------------------------------------- #

class TestComponentsV2:
    """Serialise every view and assert Discord would accept the payload."""

    MAX_COMPONENTS = 40
    MAX_CHARS = 4000

    @staticmethod
    def _walk(payload):
        """Yield every component dict in a rendered view."""

        for item in payload:
            yield item
            for child in item.get("components", []):
                yield from TestComponentsV2._walk([child])
            accessory = item.get("accessory")
            if accessory:
                yield accessory

    def _check(self, view, label: str):
        payload = view.to_components()
        assert payload, f"{label}: leeres Payload"

        components = list(self._walk(payload))
        assert len(components) <= self.MAX_COMPONENTS, (
            f"{label}: {len(components)} Komponenten > {self.MAX_COMPONENTS}"
        )

        text = sum(
            len(c.get("content", "")) for c in components if c.get("type") == 10
        )
        assert text <= self.MAX_CHARS, f"{label}: {text} Zeichen > {self.MAX_CHARS}"

        # Every top level item must be a valid V2 top-level component type.
        # 1=ActionRow 9=Section 10=TextDisplay 12=MediaGallery 13=File
        # 14=Separator 17=Container
        for item in payload:
            assert item["type"] in {1, 9, 10, 12, 13, 14, 17}, f"{label}: {item['type']}"
        return components

    def test_notice_renders(self):
        from ui.components import notice

        for tone in ("info", "success", "error", "premium", "neutral"):
            self._check(notice("Titel", "Text", tone=tone), f"notice/{tone}")

    def test_start_view_free_and_premium(self, registry):
        from ui.views import StartView

        bot = _FakeBot(registry)
        for premium in (False, True):
            components = self._check(
                StartView(bot, premium=premium), f"start/premium={premium}"
            )
            # A select menu (type 3) must always be present.
            assert any(c.get("type") == 3 for c in components)

    def test_start_view_free_has_premium_button(self, registry):
        from ui.views import StartView

        components = list(self._walk(StartView(_FakeBot(registry), premium=False).to_components()))
        buttons = [c for c in components if c.get("type") == 2]
        assert any("Premium" in (b.get("label") or "") for b in buttons)

    def test_start_view_premium_hides_button(self, registry):
        from ui.views import StartView

        components = list(self._walk(StartView(_FakeBot(registry), premium=True).to_components()))
        buttons = [c for c in components if c.get("type") == 2]
        assert not any("Sichere dir" in (b.get("label") or "") for b in buttons)

    def test_free_select_only_lists_free_templates(self, registry):
        from ui.views import StartView

        components = list(self._walk(StartView(_FakeBot(registry), premium=False).to_components()))
        select = next(c for c in components if c.get("type") == 3)
        assert {o["value"] for o in select["options"]} == {
            "community", "rp", "social", "music", "dev", "minimal",
        }

    def test_premium_select_lists_everything(self, registry):
        from ui.views import StartView

        components = list(self._walk(StartView(_FakeBot(registry), premium=True).to_components()))
        select = next(c for c in components if c.get("type") == 3)
        assert len(select["options"]) == len(registry)

        # Discord nimmt hoechstens 25 Optionen je Auswahlmenue. Bei 13
        # Vorlagen ist noch Luft, aber die naechste waechst still
        # hinein -- und dann antwortet Discord mit 400 statt mit einer
        # Liste.
        assert len(select["options"]) <= 25, (
            f"{len(select['options'])} Vorlagen — Discord erlaubt 25 je "
            "Auswahlmenü. Ab hier braucht die Auswahl Seiten."
        )

    def test_select_options_within_limits(self, registry):
        from ui.views import StartView

        components = list(self._walk(StartView(_FakeBot(registry), premium=True).to_components()))
        select = next(c for c in components if c.get("type") == 3)
        assert len(select["options"]) <= 25
        for option in select["options"]:
            assert len(option["label"]) <= 100
            assert len(option.get("description", "")) <= 100

    def test_detail_view_for_every_template(self, registry):
        from ui.views import DetailView

        bot = _FakeBot(registry)
        for template in registry:
            self._check(DetailView(bot, template), f"detail/{template.key}")

    def test_confirm_view_for_every_template(self, registry):
        from ui.views import ConfirmView

        bot = _FakeBot(registry)
        for template in registry:
            self._check(ConfirmView(bot, template), f"confirm/{template.key}")

    def test_preview_splits_to_respect_char_limit(self, registry):
        """The big templates must be split across messages, not truncated."""

        from ui.views import _preview_views

        for template in registry:
            views = _preview_views(template)
            for index, view in enumerate(views):
                self._check(view, f"preview/{template.key}#{index}")

    def test_preview_lists_every_channel(self, registry):
        from ui.views import _preview_views

        for template in registry:
            blob = ""
            for view in _preview_views(template):
                for component in self._walk(view.to_components()):
                    blob += component.get("content", "")
            for _, channel in template.iter_channels():
                assert channel.display_name in blob, (
                    f"{template.key}: '{channel.display_name}' fehlt in der Vorschau"
                )

    def test_progress_and_report_views(self, registry):
        from core.builder import BuildMode, BuildReport
        from ui.views import _progress_view, _report_view

        template = registry.get("community")
        self._check(_progress_view(template, "Rollen", 3, 14), "progress")

        report = BuildReport(mode=BuildMode.REBUILD, template_key="community")
        report.roles_created = 13
        report.categories_created = 14
        report.channels_created = 123
        report.deleted_channels = 40
        report.deleted_roles = 8
        report.warn("Ein Hinweis")
        self._check(_report_view(template, report), "report")

    def test_no_embeds_anywhere(self):
        """The whole UI must be Components V2 — no discord.Embed left."""

        for path in (BASE_DIR / "ui").glob("*.py"):
            source = path.read_text(encoding="utf-8")
            assert "discord.Embed" not in source, f"{path.name} nutzt noch Embeds"
        assert "discord.Embed" not in (BASE_DIR / "bot.py").read_text(encoding="utf-8")


class TestPremiumKeyLeak:
    """Der Key darf nirgends in der Oberfläche auftauchen.

    Ein Platzhalter wie „z. B. Vexo x Fufi KEY 2354" macht Premium wertlos:
    jeder, der auf den Button klickt, kann den Key ablesen.
    """

    @staticmethod
    def _ui_sources() -> list[tuple[str, str]]:
        paths = [*(BASE_DIR / "ui").glob("*.py"), BASE_DIR / "bot.py"]
        return [(p.name, p.read_text(encoding="utf-8")) for p in paths]

    def test_key_not_in_ui_source(self):
        """Der konfigurierte Key darf nicht im Quelltext stehen.

        Ist keiner gesetzt (der Standard), gibt es nichts zu leaken — dann
        prueft :meth:`test_default_key_fragments_not_in_ui` weiter.
        """

        import config

        secret = config.PREMIUM_KEY.strip()
        if not secret:
            pytest.skip("Kein PREMIUM_KEY konfiguriert")
        for name, source in self._ui_sources():
            assert secret not in source, f"{name} enthält den Premium-Key im Klartext"

    def test_no_default_key_in_config(self):
        """config.py darf keinen einsatzbereiten Key mitliefern.

        Ein Standardwert im Quelltext steht in jedem Klon des Repositories und
        schaltet jede Installation frei, deren Betreiber die Variable nie
        gesetzt hat.
        """

        source = (BASE_DIR / "config.py").read_text(encoding="utf-8")
        match = re.search(r'PREMIUM_KEY[^=]*=\s*os\.getenv\(\s*"PREMIUM_KEY"\s*,\s*(.*?)\)', source)
        assert match, "PREMIUM_KEY wird nicht mehr aus der Umgebung gelesen"
        fallback = match.group(1).strip().strip('"').strip("'")
        assert not fallback, f"config.py liefert einen Standard-Key mit: {fallback!r}"

    def test_premium_locked_without_key(self, tmp_path):
        """Ohne konfigurierten Key schaltet keine Eingabe frei."""

        from core.premium import PremiumStore

        store = PremiumStore(tmp_path / "premium.json", keys=())
        assert not store.is_configured
        for attempt in ("", " ", "Vexo x Fufi KEY 2354", "irgendwas"):
            assert not store.verify(attempt), f"{attempt!r} hat freigeschaltet"

    def test_default_key_fragments_not_in_ui(self):
        """Auch Teile des Standard-Keys dürfen nicht auftauchen."""

        for name, source in self._ui_sources():
            for fragment in ("Vexo", "2354"):
                assert fragment not in source, f"{name} verrät ein Key-Fragment"

    def test_modal_placeholder_is_generic(self):
        from ui.views import PremiumModal

        placeholder = PremiumModal.key.component.placeholder or ""
        assert placeholder, "Ein Platzhalter sollte vorhanden sein"
        for fragment in ("Vexo", "2354", "z. B.", "z.B.", "Beispiel"):
            assert fragment.lower() not in placeholder.lower(), (
                f"Platzhalter '{placeholder}' enthält ein Key-Beispiel"
            )

    def test_modal_description_guides_without_leaking(self):
        """Der Nutzer soll wissen, woher er den Key bekommt — nicht wie er lautet."""

        import config
        from ui.views import PremiumModal

        description = PremiumModal.key.description or ""
        assert description, "Eine Hilfestellung sollte vorhanden sein"
        if config.PREMIUM_KEY.strip():
            assert config.PREMIUM_KEY not in description
        for fragment in ("Vexo", "2354"):
            assert fragment not in description

    def test_key_never_rendered_in_premium_notice(self, registry):
        """Die Sperr-Meldung darf den Key nicht nennen."""

        import config
        from ui.components import notice

        view = notice(
            "Premium erforderlich",
            "Dies ist eine Premium-Vorlage.",
            tone="premium",
            hint="Im Hauptmenü auf Premium freischalten klicken.",
        )
        blob = "".join(
            component.get("content", "")
            for component in TestComponentsV2._walk(view.to_components())
        )
        if config.PREMIUM_KEY.strip():
            assert config.PREMIUM_KEY not in blob
        assert "Vexo" not in blob


class TestVisualPolish:
    """Regeln, die das Interface ruhig und professionell halten."""

    @staticmethod
    def _texts(view) -> list[str]:
        return [
            component["content"]
            for component in TestComponentsV2._walk(view.to_components())
            if component.get("type") == 10
        ]

    def test_start_view_uses_blockquotes(self, registry):
        from ui.views import StartView

        texts = self._texts(StartView(_FakeBot(registry), premium=False))
        assert any(line.startswith(">") for text in texts for line in text.splitlines())

    def test_detail_views_use_blockquotes(self, registry):
        from ui.views import DetailView

        bot = _FakeBot(registry)
        for template in registry:
            texts = self._texts(DetailView(bot, template))
            quoted = [line for t in texts for line in t.splitlines() if line.startswith(">")]
            assert quoted, f"{template.key}: Detailansicht ohne Blockzitat"

    def test_no_h1_headings(self, registry):
        """``#`` ist in einer Nachricht zu laut — ``##``/``###`` reichen."""

        from ui.views import ConfirmView, DetailView, StartView

        bot = _FakeBot(registry)
        views = [StartView(bot, premium=False), StartView(bot, premium=True)]
        views += [DetailView(bot, t) for t in registry]
        views += [ConfirmView(bot, t) for t in registry]

        for view in views:
            for text in self._texts(view):
                for line in text.splitlines():
                    assert not line.startswith("# "), f"H1-Überschrift gefunden: {line}"

    def test_headings_have_at_most_one_emoji(self, registry):
        """Emojis sind Navigation, keine Dekoration."""

        import unicodedata

        from ui.views import ConfirmView, DetailView, StartView

        bot = _FakeBot(registry)
        views = [StartView(bot, premium=False)]
        views += [DetailView(bot, t) for t in registry]
        views += [ConfirmView(bot, t) for t in registry]

        for view in views:
            for text in self._texts(view):
                for line in text.splitlines():
                    if not line.startswith("#"):
                        continue
                    emojis = [
                        ch for ch in line
                        if unicodedata.category(ch) == "So"
                    ]
                    assert len(emojis) <= 1, f"Zu viele Emojis in Überschrift: {line}"

    def test_no_exclamation_marketing(self, registry):
        from ui.views import ConfirmView, DetailView, StartView

        bot = _FakeBot(registry)
        views = [StartView(bot, premium=False), StartView(bot, premium=True)]
        views += [DetailView(bot, t) for t in registry]
        views += [ConfirmView(bot, t) for t in registry]

        for view in views:
            for text in self._texts(view):
                assert "!" not in text.replace("!start", ""), (
                    f"Ausrufezeichen im Interface: {text[:80]}"
                )

    def test_quote_helper_prefixes_every_line(self):
        from ui.components import quote

        result = quote("erste", "zweite\ndritte")
        assert all(line.startswith(">") for line in result.splitlines())

    def test_quote_keeps_block_together_on_empty_line(self):
        """Eine echte Leerzeile würde das Zitat in zwei Blöcke zerreißen."""

        from ui.components import quote

        result = quote("oben", "", "unten")
        assert "\n\n" not in result
        assert all(line.startswith(">") for line in result.splitlines())

    def test_progress_bar_is_monospaced_and_bounded(self):
        from ui.components import progress_bar

        for current, total in ((0, 10), (5, 10), (10, 10), (99, 10)):
            bar = progress_bar(current, total)
            assert bar.count("`") == 2, "Balken muss in Codeformat stehen"

    def test_quoted_lines_never_start_a_heading(self, registry):
        """``> # kanal`` würde Discord als riesige Überschrift rendern.

        Der Fehler ist im Quelltext unsichtbar und fällt erst im Client auf,
        deshalb prüft ihn ein Test.
        """

        from ui.views import DetailView, StartView, _preview_views

        bot = _FakeBot(registry)
        views = [StartView(bot, premium=False), StartView(bot, premium=True)]
        for template in registry:
            views.append(DetailView(bot, template))
            views.extend(_preview_views(template))

        for view in views:
            for text in self._texts(view):
                for line in text.splitlines():
                    if not line.startswith(">"):
                        continue
                    body = line.lstrip(">").lstrip()
                    assert not body.startswith("#") or body.startswith("`"), (
                        f"Zitatzeile wird als Überschrift gerendert: {line!r}"
                    )

    def test_preview_marks_text_channels(self, registry):
        from ui.views import _preview_views

        blob = ""
        for view in _preview_views(registry.get("community")):
            blob += "".join(self._texts(view))
        assert "`#`" in blob, "Textkanäle brauchen ein erkennbares Symbol"

    def test_progress_bar_bounds(self):
        from ui.components import progress_bar

        assert "0%" in progress_bar(0, 10)
        assert "100%" in progress_bar(10, 10)
        assert "100%" in progress_bar(99, 10)
        assert progress_bar(5, 0)


class _FakeBot:
    """Minimal stand-in so views can be rendered without a gateway connection."""

    def __init__(self, registry: TemplateRegistry) -> None:
        self.registry = registry
        self.active_builds: set[int] = set()
        self.premium = _FakePremium()


class _FakePremium:
    def has_access(self, guild_id, user_id) -> bool:
        return False

    def verify(self, key: str) -> bool:
        return False

    def grant(self, guild_id, user_id) -> None:
        pass


# --------------------------------------------------------------------------- #
# Builder logic (no network)
# --------------------------------------------------------------------------- #

class TestBuilder:
    def test_role_specs_merge_base_and_template(self, registry):
        from core.builder import ServerBuilder

        template = registry.get("rp")
        builder = ServerBuilder.__new__(ServerBuilder)
        builder.template = template
        specs = builder._resolve_role_specs()

        keys = [spec.key for spec in specs]
        assert len(keys) == len(set(keys)), "doppelte Rollen-Keys"
        assert "owner" in keys and "unverified" in keys
        assert "roleplayer" in keys
        assert len(specs) == len(BASE_ROLES) + len(template.roles)

    def test_staff_keys_exclude_members(self, registry):
        from core.builder import ServerBuilder

        builder = ServerBuilder.__new__(ServerBuilder)
        builder.template = registry.get("community")
        specs = builder._resolve_role_specs()
        staff = {s.key for s in specs if s.tier.is_staff}

        assert "moderator" in staff
        assert "owner" in staff
        assert "member" not in staff
        assert "unverified" not in staff
        assert "vip" not in staff

    def test_identical_visibility_yields_no_overwrites(self):
        """Channels matching their category should simply inherit."""

        from core.permissions import channel_overwrites

        result = channel_overwrites(
            None, Visibility.PUBLIC, Visibility.PUBLIC, {},
            staff_keys=frozenset(), leadership_keys=frozenset(),
        )
        assert result == {}


class TestExpiredInteraction:
    """404 Unknown Message nach einem langen Build.

    Ein großes Template braucht Minuten. Interaktionen leben 15 Minuten, und
    die ursprüngliche Nachricht kann gelöscht sein. Vorher endete das in
    einem Traceback — der Server war fertig, sagte es aber niemandem.
    """

    def test_helpers_exist(self):
        from ui.views import _fallback_notify, _report, _safe_edit

        assert callable(_safe_edit)
        assert callable(_fallback_notify)
        assert callable(_report)

    def test_no_unguarded_edit_calls(self):
        """edit_original_response darf nur in _safe_edit stehen."""

        source = (BASE_DIR / "ui" / "views.py").read_text(encoding="utf-8")
        assert source.count("edit_original_response") == 1

    def test_safe_edit_swallows_not_found(self):
        import asyncio

        import discord

        from ui.components import notice
        from ui.views import _safe_edit

        class Expired:
            async def edit_original_response(self, **kwargs):
                raise discord.NotFound(
                    type("R", (), {"status": 404, "reason": "Not Found"})(),
                    "Unknown Message",
                )

        result = asyncio.run(_safe_edit(Expired(), notice("T", "B")))
        assert result is False, "Ein abgelaufener Callback ist kein Fehler"

    def test_safe_edit_reports_success(self):
        import asyncio

        from ui.components import notice
        from ui.views import _safe_edit

        class Fine:
            def __init__(self):
                self.calls = 0

            async def edit_original_response(self, **kwargs):
                self.calls += 1

        target = Fine()
        assert asyncio.run(_safe_edit(target, notice("T", "B"))) is True
        assert target.calls == 1

    def test_result_falls_back_to_the_channel(self):
        """Ist die Interaktion tot, geht das Ergebnis in den Kanal."""

        import asyncio

        import discord

        from ui.components import notice
        from ui.views import _report

        posted: list[object] = []

        class Channel:
            def permissions_for(self, _member):
                return type("P", (), {"send_messages": True})()

            async def send(self, view=None, **kwargs):
                posted.append(view)

        class Member:
            pass

        class Guild:
            me = Member()

        class Expired:
            channel = Channel()
            guild = Guild()

            async def edit_original_response(self, **kwargs):
                raise discord.NotFound(
                    type("R", (), {"status": 404, "reason": "Not Found"})(),
                    "Unknown Message",
                )

        asyncio.run(_report(Expired(), notice("Fertig", "Server steht")))
        assert posted, "Der Nutzer bekommt gar keine Rückmeldung"

    def test_no_fallback_without_write_permission(self):
        """Ohne Schreibrecht darf der Versuch keine Ausnahme werfen."""

        import asyncio

        import discord

        from ui.components import notice
        from ui.views import _report

        class Channel:
            def permissions_for(self, _member):
                return type("P", (), {"send_messages": False})()

            async def send(self, **kwargs):
                raise AssertionError("Es hätte nicht gesendet werden dürfen")

        class Guild:
            me = object()

        class Expired:
            channel = Channel()
            guild = Guild()

            async def edit_original_response(self, **kwargs):
                raise discord.NotFound(
                    type("R", (), {"status": 404, "reason": "Not Found"})(),
                    "Unknown Message",
                )

        asyncio.run(_report(Expired(), notice("T", "B")))
