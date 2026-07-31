"""Der Generator und die eingecheckten Vorlagen duerfen nicht auseinanderlaufen.

``tools/generate_templates.py`` ist die eigentliche Quelle der zehn Dateien in
``templates/``. Beides liegt parallel im Repository, und nichts hat bisher
geprueft, ob sie noch zusammenpassen.

Das ist die einzige Stelle im Projekt, an der stille Datenverluste moeglich
sind: Wer eine Kategorie von Hand im JSON aendert, verliert die Aenderung beim
naechsten Generator-Lauf kommentarlos — moeglicherweise Wochen spaeter, wenn
niemand mehr den Zusammenhang sieht.

Diese Datei laesst den Generator in einer Kopie des Projekts laufen und
vergleicht das Ergebnis mit dem, was im Repository steht. Das eigentliche
``templates/``-Verzeichnis wird dabei **nicht** angefasst.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = BASE_DIR / "templates"
GENERATOR = BASE_DIR / "tools" / "generate_templates.py"


@pytest.fixture(scope="module")
def regenerated(tmp_path_factory: pytest.TempPathFactory) -> dict[str, dict]:
    """Den Generator in einer Wegwerf-Kopie laufen lassen.

    Kopiert wird nur, was er braucht: der Generator selbst, das Schema, mit dem
    er seine Ausgabe validiert, und ein leeres Zielverzeichnis. Damit kann der
    Test das echte ``templates/`` unmoeglich beschaedigen, auch wenn er
    mittendrin abbricht.
    """

    workdir = tmp_path_factory.mktemp("generator")

    shutil.copytree(BASE_DIR / "tools", workdir / "tools")
    shutil.copytree(BASE_DIR / "core", workdir / "core")
    shutil.copy(BASE_DIR / "config.py", workdir / "config.py")
    (workdir / "templates").mkdir()

    result = subprocess.run(
        [sys.executable, str(workdir / "tools" / "generate_templates.py")],
        cwd=workdir,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, (
        "Der Generator laeuft nicht mehr durch:\n"
        f"{result.stdout}\n{result.stderr}"
    )

    produced = sorted((workdir / "templates").glob("*.json"))
    assert produced, "Der Generator hat keine Dateien geschrieben"

    return {
        path.name: json.loads(path.read_text(encoding="utf-8")) for path in produced
    }


@pytest.fixture(scope="module")
def committed() -> dict[str, dict]:
    return {
        path.name: json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(TEMPLATE_DIR.glob("*.json"))
    }


HINT = (
    "Die eingecheckten Vorlagen passen nicht mehr zum Generator. "
    "Entweder 'python tools/generate_templates.py' ausfuehren und das "
    "Ergebnis committen, oder die Aenderung in den Generator uebernehmen — "
    "eine Handaenderung am JSON allein geht beim naechsten Lauf verloren."
)


class TestGeneratorStaysInSync:
    def test_same_set_of_files(self, regenerated, committed):
        """Kein Template darf nur in einer der beiden Quellen existieren."""

        only_generated = sorted(set(regenerated) - set(committed))
        only_committed = sorted(set(committed) - set(regenerated))

        assert not only_generated, (
            f"Der Generator erzeugt Dateien, die nicht eingecheckt sind: "
            f"{only_generated}. {HINT}"
        )
        assert not only_committed, (
            f"Eingecheckt, aber der Generator kennt sie nicht: "
            f"{only_committed}. Entweder in TEMPLATES eintragen oder loeschen."
        )

    @pytest.mark.parametrize(
        "name",
        sorted(p.name for p in TEMPLATE_DIR.glob("*.json")),
    )
    def test_content_matches(self, name, regenerated, committed):
        """Jede Vorlage einzeln — so nennt der Fehlschlag die betroffene Datei."""

        assert name in regenerated, f"{name} wird vom Generator nicht erzeugt. {HINT}"
        assert regenerated[name] == committed[name], f"{name} weicht ab. {HINT}"

    def test_generator_is_deterministic(self, regenerated, tmp_path):
        """Zwei Laeufe muessen dasselbe ergeben.

        Waere die Ausgabe von Mengen- oder Dict-Reihenfolgen abhaengig, wuerde
        dieser Test wackeln — und der Vergleich oben waere wertlos.
        """

        shutil.copytree(BASE_DIR / "tools", tmp_path / "tools")
        shutil.copytree(BASE_DIR / "core", tmp_path / "core")
        shutil.copy(BASE_DIR / "config.py", tmp_path / "config.py")
        (tmp_path / "templates").mkdir()

        result = subprocess.run(
            [sys.executable, str(tmp_path / "tools" / "generate_templates.py")],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.returncode == 0, result.stderr

        second = {
            path.name: json.loads(path.read_text(encoding="utf-8"))
            for path in sorted((tmp_path / "templates").glob("*.json"))
        }
        assert second == regenerated, (
            "Zwei Generator-Laeufe liefern unterschiedliche Ergebnisse — "
            "vermutlich haengt die Ausgabe an einer Mengen-Reihenfolge."
        )


class TestGeneratedFilesAreWellFormed:
    """Formalia, die beim Bearbeiten von Hand leicht verloren gehen."""

    @pytest.mark.parametrize(
        "path",
        sorted(TEMPLATE_DIR.glob("*.json")),
        ids=lambda p: p.name,
    )
    def test_two_space_indent_and_trailing_newline(self, path: Path):
        raw = path.read_text(encoding="utf-8")
        assert raw.endswith("\n"), f"{path.name}: kein Zeilenumbruch am Ende"
        assert not raw.endswith("\n\n"), f"{path.name}: mehrere Leerzeilen am Ende"

        data = json.loads(raw)
        expected = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
        assert raw == expected, (
            f"{path.name} ist anders formatiert als der Generator schreibt "
            "(2 Leerzeichen Einzug, echte Umlaute statt \\u-Escapes)."
        )

    @pytest.mark.parametrize(
        "path",
        sorted(TEMPLATE_DIR.glob("*.json")),
        ids=lambda p: p.name,
    )
    def test_filename_matches_key(self, path: Path):
        """``community.json`` muss auch den Key ``community`` tragen.

        Die Registry laedt ueber den Key, nicht ueber den Dateinamen — eine
        Abweichung faellt sonst erst zur Laufzeit auf.
        """

        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["key"] == path.stem, (
            f"{path.name} enthaelt den Key '{data['key']}'"
        )
