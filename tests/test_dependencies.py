"""Reproduzierbarkeit der Abhaengigkeiten.

``requirements.txt`` nennt nur Bereiche (``discord.py>=2.6,<3.0``). Das ist
richtig fuer die Entwicklung, aber als Grundlage eines Deployments zu wenig:
ein Patch-Release kann das Verhalten des Bots aendern, ohne dass ein einziger
Commit stattgefunden hat. Deshalb installiert das Image aus
``requirements.lock`` — voll gepinnt und mit Hashes.

Diese Datei prueft die Stellen, an denen das leise kaputtgehen kann:

* Steht im Lockfile ueberhaupt noch jede direkte Abhaengigkeit?
* Verletzt eine gepinnte Version die Bereiche aus ``requirements.txt``?
* Installiert das Dockerfile wirklich aus dem Lockfile — und mit Hashes?
* Passt das Lockfile noch zu der Python-Version, die das Image benutzt?
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
LOCKFILE = BASE_DIR / "requirements.lock"
REQUIREMENTS = BASE_DIR / "requirements.txt"
DOCKERFILE = BASE_DIR / "Dockerfile"


def _normalise(name: str) -> str:
    """``discord.py``, ``discord-py`` und ``Discord_PY`` sind dasselbe Paket."""

    return re.sub(r"[-_.]+", "-", name).lower()


@pytest.fixture(scope="module")
def locked() -> dict[str, str]:
    """Paketname -> Version, aus dem Lockfile."""

    entries: dict[str, str] = {}
    for line in LOCKFILE.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==([^\s;\\]+)", line)
        if match:
            entries[_normalise(match.group(1))] = match.group(2)
    return entries


@pytest.fixture(scope="module")
def declared() -> dict[str, str]:
    """Paketname -> Bereichsangabe, aus requirements.txt."""

    entries: dict[str, str] = {}
    for line in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        entry = line.strip()
        if not entry or entry.startswith(("#", "-")):
            continue
        match = re.match(r"^([A-Za-z0-9][A-Za-z0-9._-]*)(.*)$", entry)
        if match:
            entries[_normalise(match.group(1))] = match.group(2).strip()
    return entries


@pytest.fixture(scope="module")
def dockerfile() -> str:
    return DOCKERFILE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def image_python(dockerfile: str) -> tuple[int, int]:
    """Die Python-Version des Basis-Images, als Zahlenpaar."""

    match = re.search(r"FROM python:(\d+)\.(\d+)", dockerfile)
    assert match, "Das Basis-Image nennt keine Python-Version"
    return int(match.group(1)), int(match.group(2))


class TestLockfileExists:
    def test_lockfile_is_present(self):
        assert LOCKFILE.exists(), (
            "requirements.lock fehlt — ohne Lockfile sind Deployments nicht "
            "reproduzierbar. Erzeugen mit: uv pip compile requirements.txt "
            "--generate-hashes --universal -o requirements.lock"
        )

    def test_every_entry_is_pinned(self, locked):
        """Ein Bereich im Lockfile waere ein Widerspruch in sich."""

        raw = LOCKFILE.read_text(encoding="utf-8")
        loose = [
            line.strip()
            for line in raw.splitlines()
            if re.match(r"^[A-Za-z0-9]", line) and "==" not in line
        ]
        assert not loose, f"Nicht gepinnte Eintraege im Lockfile: {loose}"

    def test_every_package_carries_hashes(self):
        """Ohne Hash nuetzt das Pinning wenig: PyPI-Dateien sind ersetzbar."""

        raw = LOCKFILE.read_text(encoding="utf-8")
        blocks = re.split(r"\n(?=[A-Za-z0-9])", raw)
        for block in blocks:
            name = block.split("==")[0].strip()
            if not name or name.startswith("#"):
                continue
            assert "--hash=sha256:" in block, f"{name} steht ohne Hash im Lockfile"


class TestLockfileMatchesRequirements:
    def test_all_direct_dependencies_are_locked(self, declared, locked):
        missing = sorted(set(declared) - set(locked))
        assert not missing, (
            f"Diese direkten Abhaengigkeiten fehlen im Lockfile: {missing}. "
            "Lockfile neu erzeugen."
        )

    @pytest.mark.parametrize("package", ["discord-py", "aiohttp", "python-dotenv"])
    def test_pinned_version_satisfies_the_declared_range(
        self, package, declared, locked
    ):
        """Ein Lockfile, das die Bereiche verletzt, ist schlimmer als keins."""

        assert package in locked, f"{package} fehlt im Lockfile"
        version = locked[package]
        spec = declared.get(package, "")

        for constraint in (part.strip() for part in spec.split(",") if part.strip()):
            match = re.match(r"^(>=|<=|==|!=|<|>|~=)\s*(.+)$", constraint)
            if not match:
                continue
            operator, bound = match.group(1), match.group(2)

            actual = tuple(int(p) for p in re.findall(r"\d+", version)[:3])
            expected = tuple(int(p) for p in re.findall(r"\d+", bound)[:3])
            # Auf gleiche Laenge bringen, damit 2.7 und 2.7.1 vergleichbar sind.
            width = max(len(actual), len(expected))
            actual += (0,) * (width - len(actual))
            expected += (0,) * (width - len(expected))

            if operator == ">=":
                assert actual >= expected, f"{package} {version} < {bound}"
            elif operator == "<":
                assert actual < expected, f"{package} {version} >= {bound}"
            elif operator == "<=":
                assert actual <= expected, f"{package} {version} > {bound}"
            elif operator == ">":
                assert actual > expected, f"{package} {version} <= {bound}"
            elif operator == "==":
                assert actual == expected, f"{package} {version} != {bound}"


class TestDockerfileUsesTheLockfile:
    def test_installs_from_the_lockfile(self, dockerfile):
        assert "requirements.lock" in dockerfile, (
            "Das Image installiert nicht aus dem Lockfile — dann bringt es nichts."
        )

    def test_requires_hashes(self, dockerfile):
        """Ohne --require-hashes werden die Hashes im Lockfile ignoriert."""

        assert "--require-hashes" in dockerfile

    def test_copies_the_lockfile_before_installing(self, dockerfile):
        """Sonst schlaegt der Build fehl, weil die Datei noch nicht da ist."""

        copy_at = dockerfile.find("COPY requirements.lock")
        install_at = dockerfile.find("pip install")
        assert copy_at != -1, "requirements.lock wird nie ins Image kopiert"
        assert copy_at < install_at, "COPY steht hinter dem pip install"

    def test_lockfile_survives_dockerignore(self):
        """Eine zu breite Ignore-Regel wuerde den Build leer laufen lassen."""

        ignored = [
            line.strip()
            for line in (BASE_DIR / ".dockerignore").read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith(("#", "!"))
        ]
        assert "requirements.lock" not in ignored


class TestPythonVersionsAgree:
    """Image, Projektangabe und CI duerfen nicht auseinanderlaufen."""


    def test_requires_python_covers_the_image(self, image_python):
        data = tomllib.loads((BASE_DIR / "pyproject.toml").read_text(encoding="utf-8"))
        spec = data["project"]["requires-python"]
        floor = tuple(int(p) for p in re.findall(r"\d+", spec)[:2])
        assert image_python >= floor, (
            f"Das Image nutzt Python {image_python}, pyproject verlangt {spec}"
        )

    def test_ci_tests_the_image_version(self, image_python):
        """Getestet werden muss die Version, die auch produktiv laeuft."""

        workflow = (BASE_DIR / ".github" / "workflows" / "ci.yml").read_text(
            encoding="utf-8"
        )
        expected = f"{image_python[0]}.{image_python[1]}"
        assert f'"{expected}"' in workflow, (
            f"Die CI testet nicht gegen Python {expected} (Basis-Image)"
        )

    def test_lockfile_is_universal_enough_for_newer_pythons(self):
        """discord.py braucht ab 3.13 audioop-lts.

        Ein nur fuer 3.12 erzeugtes Lockfile scheitert dort mit
        ``--require-hashes``. Der Marker belegt, dass universal gelockt wurde.
        """

        raw = LOCKFILE.read_text(encoding="utf-8")
        assert "audioop-lts" in raw, (
            "audioop-lts fehlt — das Lockfile wurde vermutlich ohne --universal "
            "erzeugt und laesst sich auf Python 3.13 nicht installieren."
        )
        assert "python_full_version" in raw, "Keine Umgebungsmarker im Lockfile"
