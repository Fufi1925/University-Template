"""Der regelbasierte Assistent hinter ``/template ai``.

Ohne API und ohne Netz muss trotzdem alles stimmen, was eine Vorlage
ausmacht:

* **Treffer** — Themen werden erkannt, kurze Keywords (``uni``, ``rp``,
  ``dj``) nur als ganze Woerter, damit ``community`` nicht ``uni`` trifft.
* **Kombination** — die Basis kommt vom ersten Thema, bis zu zwei weitere
  steuern ihre Kategorien und Rollen bei, ohne Namen zu verdoppeln.
* **Fallback** — ohne erkanntes Thema entsteht die Community-Vorlage mit
  neuem Namen.
* **Validierung** — das Ergebnis besteht dieselben Pruefungen wie jede
  JSON-Vorlage, inklusive Discord-Limits.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import config
from core.ai_templates import TOPICS, compose_template, detect_topics
from core.registry import TemplateRegistry


@pytest.fixture(scope="module")
def registry():
    return TemplateRegistry(config.TEMPLATE_DIR).load()


# --------------------------------------------------------------------------- #
# Themen erkennen
# --------------------------------------------------------------------------- #

class TestDetectTopics:
    def test_long_keywords_match_inside_words(self):
        topics = detect_topics("Wir sind eine große Zockerrunde")

        assert topics and topics[0].key == "gaming"

    def test_short_keywords_need_word_boundaries(self):
        """``community`` enthaelt ``uni`` — darf aber nicht treffen."""

        assert detect_topics("Eine Community für alle") == []
        assert detect_topics("Ich studiere an der uni")[0].key == "study"

    def test_topics_are_ordered_by_first_appearance(self):
        topics = detect_topics("Musik und Gaming im Mix")

        assert [topic.key for topic in topics] == ["musik", "gaming"]

    def test_more_than_three_topics_are_ignored(self):
        description = (
            "Gaming, Anime, Rollenspiel, Musik und ein Support-Bereich — "
            "alles auf einmal"
        )

        assert len(detect_topics(description)) == 3

    def test_no_topics_no_match(self):
        assert detect_topics("Einfach nur ein Server") == []

    def test_every_topic_knows_a_template(self, registry):
        """Jedes Thema muss auf eine existierende Vorlage zeigen."""

        for topic in TOPICS:
            assert registry.get(topic.template_key) is not None, (
                f"Thema {topic.key} zeigt auf unbekanntes Template "
                f"'{topic.template_key}'"
            )


# --------------------------------------------------------------------------- #
# Vorlagen zusammensetzen
# --------------------------------------------------------------------------- #

class TestCompose:
    def test_no_topic_falls_back_to_community(self, registry):
        template = compose_template(
            registry, name="Mein Server", description="Einfach ein netter Ort"
        )

        assert template.name == "Mein Server"
        assert template.key == "ai"
        assert template.categories == registry.get("community").categories
        assert not template.premium

    def test_a_single_topic_uses_its_template(self, registry):
        template = compose_template(
            registry, name="Zockerbude", description="Ein Server zum Zocken"
        )

        base = registry.get("gaming")
        assert template.emoji == base.emoji
        assert template.accent == base.accent
        assert template.categories == base.categories

    def test_mixed_topics_contribute_categories(self, registry):
        template = compose_template(
            registry,
            name="Mix",
            description="Gaming mit Musik und Anime für alle",
        )

        gaming = {c.display_name for c in registry.get("gaming").categories}
        music = {c.display_name for c in registry.get("music").categories}

        own = {category.display_name for category in template.categories}
        assert gaming < own, "Basis-Kategorien fehlen"
        assert music & own, "Keine Musikkategorien beigesteuert"

    def test_colliding_categories_are_not_duplicated(self, registry):
        template = compose_template(
            registry,
            name="Doppelt",
            description="Community und Social Lounge zugleich",
        )

        names = [category.display_name for category in template.categories]
        assert len(names) == len(set(names)), "Doppelte Kategorien im Ergebnis"

    def test_roles_from_extra_topics_are_added_without_duplicates(self, registry):
        template = compose_template(
            registry,
            name="Mit Rollen",
            description="Gaming und Creator Studio",
        )

        keys = [role.key for role in template.roles]
        assert len(keys) == len(set(keys)), "Doppelte Rollen im Ergebnis"
        assert len(keys) > len(registry.get("gaming").roles), (
            "Rollen des zweiten Themas fehlen"
        )

    def test_the_result_passes_schema_validation(self, registry):
        template = compose_template(
            registry,
            name="Alles",
            description="Gaming, Musik, Anime, Business und Support",
        )

        # validate() lief bereits in compose_template — dieser Aufruf ist
        # die explizite Zusage, dass die Limits wirklich gehalten werden.
        template.validate()
        assert template.channel_count <= 500
        assert template.category_count <= 50

    def test_an_empty_name_gets_a_default(self, registry):
        template = compose_template(
            registry, name="   ", description="Ein Server zum Zocken"
        )

        assert template.name == "Mein Server"

    def test_highlights_mention_the_topics(self, registry):
        template = compose_template(
            registry, name="Mit Highlights", description="Musik und Rollenspiel"
        )

        joined = " ".join(template.highlights)
        assert "Musik" in joined
        assert "Rollenspiel" in joined


class TestComposeEdgeCases:
    """Die Raender: fehlende Templates, Deckel, doppelte Rollen-Keys."""

    @staticmethod
    def fake_registry(**templates):
        """Eine Registry, die nur die genannten Vorlagen kennt."""

        return type(
            "R",
            (),
            {
                "all": list(templates.values()),
                "get": lambda self, key: templates.get(key),
            },
        )()

    def test_without_community_the_first_template_is_the_fallback(self, registry):
        """Kein Thema *und* keine Community-Vorlage: die erste gewinnt."""

        base = registry.get("gaming")
        fake = type("R", (), {"all": [base], "get": lambda self, key: None})()

        template = compose_template(fake, name="Fallback", description="Kein Thema")

        assert template.categories == base.categories

    def test_a_missing_extra_template_is_skipped(self, registry):
        gaming = registry.get("gaming")

        fake = self.fake_registry(gaming=gaming)

        template = compose_template(
            fake, name="Nur die Basis", description="Gaming und Musik"
        )

        # Musik fehlt in der Fake-Registry — die Basis bleibt unveraendert.
        assert template.categories == gaming.categories

    def test_the_category_cap_stops_collecting(self, registry, monkeypatch):
        import core.ai_templates as ai_module

        base = registry.get("gaming")
        monkeypatch.setattr(ai_module, "MAX_CATEGORIES", len(base.categories) + 1)

        template = compose_template(
            registry, name="Gedeckelt", description="Gaming und Musik"
        )

        assert len(template.categories) == len(base.categories) + 1

    def test_duplicate_role_keys_are_skipped(self, registry):
        from core.schema import Template

        base = registry.get("gaming")
        shared_key = base.roles[0].key
        extra = Template.parse(
            {
                "key": "mini",
                "name": "Mini",
                "categories": [
                    {"label": "bonus", "channels": [{"label": "bonus"}]}
                ],
                "roles": [{"key": shared_key, "label": "Doppelgaenger"}],
            },
            source="<test>",
        )
        fake = self.fake_registry(gaming=base, music=extra)

        template = compose_template(
            fake, name="Doppelt", description="Gaming und Musik"
        )

        keys = [role.key for role in template.roles]
        assert keys.count(shared_key) == 1, "Der geteilte Rollen-Key ist doppelt"
        # Die Kategorie des Extras ist trotzdem dabei.
        assert any(category.label == "bonus" for category in template.categories)
