"""Das Laden der Vorlagen beim Start.

Die Registry ist die erste Amtshandlung des Bots: schlaegt sie fehl, startet
er gar nicht. Genau so ist es gedacht — eine kaputte Vorlage soll **beim
Start** auffallen und nicht mittendrin, wenn der Bot bereits die Haelfte
eines fremden Servers umgebaut hat.

Getestet wird deshalb vor allem, dass Fehler wirklich laut sind und die
Meldung die betroffene Datei nennt.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import config
from core.registry import TemplateRegistry
from core.schema import TemplateError

REAL_TEMPLATES = sorted(config.TEMPLATE_DIR.glob("*.json"))


@pytest.fixture
def template_dir(tmp_path) -> Path:
    """Ein Verzeichnis mit einer echten Vorlage als Ausgangspunkt."""

    directory = tmp_path / "templates"
    directory.mkdir()
    shutil.copy(REAL_TEMPLATES[0], directory / REAL_TEMPLATES[0].name)
    return directory


# --------------------------------------------------------------------------- #
# Fehlerfaelle
# --------------------------------------------------------------------------- #

class TestLoadingFails:
    def test_missing_directory_is_named(self, tmp_path):
        with pytest.raises(TemplateError) as excinfo:
            TemplateRegistry(tmp_path / "gibt-es-nicht").load()

        assert "nicht gefunden" in str(excinfo.value)

    def test_empty_directory_is_an_error(self, tmp_path):
        """Ein Bot ohne Vorlagen kann nichts tun — lieber gar nicht starten."""

        empty = tmp_path / "leer"
        empty.mkdir()

        with pytest.raises(TemplateError):
            TemplateRegistry(empty).load()

    def test_broken_json_names_the_file(self, template_dir):
        """Beim Debuggen zaehlt, welche der zehn Dateien es ist."""

        (template_dir / "kaputt.json").write_text("{ nicht wirklich json",
                                                  encoding="utf-8")

        with pytest.raises(TemplateError) as excinfo:
            TemplateRegistry(template_dir).load()

        assert "kaputt.json" in str(excinfo.value)
        assert "JSON" in str(excinfo.value)

    def test_duplicate_key_is_rejected(self, template_dir):
        """Sonst ueberschriebe eine Vorlage stillschweigend die andere."""

        original = json.loads(REAL_TEMPLATES[0].read_text(encoding="utf-8"))
        (template_dir / "zwilling.json").write_text(
            json.dumps(original, ensure_ascii=False), encoding="utf-8"
        )

        with pytest.raises(TemplateError) as excinfo:
            TemplateRegistry(template_dir).load()

        assert "bereits vergeben" in str(excinfo.value)
        assert original["key"] in str(excinfo.value)

    def test_schema_violation_stops_the_start(self, template_dir):
        """Eine Vorlage ohne Kategorien ist keine Vorlage."""

        broken = json.loads(REAL_TEMPLATES[0].read_text(encoding="utf-8"))
        broken["key"] = "kaputt"
        broken["categories"] = []
        (template_dir / "kaputt.json").write_text(
            json.dumps(broken, ensure_ascii=False), encoding="utf-8"
        )

        with pytest.raises(TemplateError):
            TemplateRegistry(template_dir).load()

    def test_a_file_that_is_not_an_object(self, template_dir):
        (template_dir / "liste.json").write_text("[1, 2, 3]", encoding="utf-8")

        with pytest.raises(TemplateError):
            TemplateRegistry(template_dir).load()


# --------------------------------------------------------------------------- #
# Erfolgsfall
# --------------------------------------------------------------------------- #

class TestLoadingWorks:
    def test_single_template_is_enough(self, template_dir):
        registry = TemplateRegistry(template_dir).load()

        assert len(registry) == 1

    def test_load_returns_itself_for_chaining(self, template_dir):
        registry = TemplateRegistry(template_dir)

        assert registry.load() is registry

    def test_reloading_replaces_the_contents(self, template_dir):
        """``load()`` ein zweites Mal darf nicht doppelt eintragen."""

        registry = TemplateRegistry(template_dir).load()
        before = len(registry)
        registry.load()

        assert len(registry) == before

    def test_non_json_files_are_ignored(self, template_dir):
        """Eine README im Vorlagenordner darf den Start nicht kippen."""

        (template_dir / "README.md").write_text("Hinweise", encoding="utf-8")
        (template_dir / "notiz.txt").write_text("egal", encoding="utf-8")

        assert len(TemplateRegistry(template_dir).load()) == 1


# --------------------------------------------------------------------------- #
# Zugriff auf die echten Vorlagen
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="module")
def registry() -> TemplateRegistry:
    return TemplateRegistry(config.TEMPLATE_DIR).load()


class TestAccessors:
    def test_get_returns_none_for_unknown_keys(self, registry):
        assert registry.get("gibt-es-nicht") is None

    def test_contains_works(self, registry):
        known = registry.all[0].key

        assert known in registry
        assert "gibt-es-nicht" not in registry

    def test_contains_tolerates_non_strings(self, registry):
        for candidate in (None, 42, object()):
            assert candidate not in registry

    def test_free_and_premium_partition_all(self, registry):
        assert len(registry.free) + len(registry.premium) == len(registry.all)
        assert not set(t.key for t in registry.free) & set(
            t.key for t in registry.premium
        )

    def test_available_to_respects_the_flag(self, registry):
        assert registry.available_to(premium=False) == registry.free
        assert registry.available_to(premium=True) == registry.all

    def test_ordering_is_stable_and_free_first(self, registry):
        """Die Startansicht zeigt kostenlose Vorlagen zuerst."""

        keys = [t.key for t in registry.all]
        assert keys == [t.key for t in registry.all], "Reihenfolge schwankt"

        flags = [t.premium for t in registry.all]
        assert flags == sorted(flags), "Premium-Vorlagen stehen nicht hinten"

    def test_iteration_covers_every_template(self, registry):
        assert len(list(registry)) == len(registry)

    def test_totals_match_the_templates(self, registry):
        totals = registry.totals

        assert totals["templates"] == len(registry)
        assert totals["channels"] == sum(t.channel_count for t in registry)
        assert totals["categories"] == sum(t.category_count for t in registry)
        assert totals["voice"] == sum(t.voice_count for t in registry)

    def test_totals_are_plausible(self, registry):
        """Grobe Plausibilitaet — faengt ein leeres oder halbes Laden ab."""

        totals = registry.totals

        assert totals["templates"] == 14
        assert totals["channels"] > 500
        assert totals["voice"] < totals["channels"]
