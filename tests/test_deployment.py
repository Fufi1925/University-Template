"""Deployment-Konfiguration.

Railway lehnt Dockerfiles mit ``VOLUME`` ab:

    dockerfile invalid: docker VOLUME at Line 18 is not supported,
    use Railway Volumes

Der Build bricht dabei sofort ab, noch bevor irgendein Test laufen koennte.
Diese Datei prueft die Deployment-Dateien daher rein statisch, damit so ein
Fehler beim Commit auffaellt und nicht erst im Build-Log.
"""

from __future__ import annotations

import fnmatch
import tomllib
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent

# Anweisungen, die Railway im Dockerfile nicht akzeptiert.
RAILWAY_FORBIDDEN = {"VOLUME"}

VALID_INSTRUCTIONS = {
    "FROM", "RUN", "CMD", "LABEL", "EXPOSE", "ENV", "ADD", "COPY",
    "ENTRYPOINT", "VOLUME", "USER", "WORKDIR", "ARG", "ONBUILD",
    "STOPSIGNAL", "HEALTHCHECK", "SHELL",
}


def _instructions(dockerfile: str) -> list[str]:
    """Logische Anweisungen; Zeilenfortsetzungen werden zusammengefuehrt."""

    lines: list[str] = []
    buffer = ""
    for raw in dockerfile.splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        buffer += stripped
        if stripped.endswith("\\"):
            buffer = buffer[:-1] + " "
            continue
        lines.append(buffer)
        buffer = ""
    if buffer:
        lines.append(buffer)
    return lines


@pytest.fixture(scope="module")
def dockerfile() -> str:
    return (BASE_DIR / "Dockerfile").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def instructions(dockerfile: str) -> list[str]:
    return _instructions(dockerfile)


@pytest.fixture(scope="module")
def ignore_rules() -> tuple[list[str], list[str]]:
    patterns: list[str] = []
    negations: list[str] = []
    for line in (BASE_DIR / ".dockerignore").read_text(encoding="utf-8").splitlines():
        entry = line.strip()
        if not entry or entry.startswith("#"):
            continue
        (negations if entry.startswith("!") else patterns).append(entry.lstrip("!"))
    return patterns, negations


def _is_ignored(path: str, rules: tuple[list[str], list[str]]) -> bool:
    patterns, negations = rules
    segments = path.split("/")
    matched = any(
        fnmatch.fnmatch(path, pattern)
        or any(fnmatch.fnmatch(segment, pattern) for segment in segments)
        for pattern in patterns
    )
    if matched and any(
        fnmatch.fnmatch(path, neg) or fnmatch.fnmatch(segments[-1], neg)
        for neg in negations
    ):
        return False
    return matched


class TestDockerfile:
    def test_no_railway_forbidden_instructions(self, instructions):
        """Der Fehler, der den Railway-Build abgebrochen hat."""

        offenders = [
            line
            for line in instructions
            if line.split(None, 1)[0].upper() in RAILWAY_FORBIDDEN
        ]
        assert not offenders, (
            "Railway lehnt diese Anweisungen ab: "
            + "; ".join(offenders)
            + " — persistenten Speicher stattdessen im Dashboard mounten."
        )

    def test_volume_documented_as_comment(self, dockerfile):
        """Der Mount-Pfad muss dokumentiert bleiben, auch ohne VOLUME."""

        assert "/app/data" in dockerfile
        assert "Railway Volumes" in dockerfile or "Railway:" in dockerfile

    def test_starts_with_from(self, instructions):
        assert instructions[0].split(None, 1)[0].upper() == "FROM"

    def test_only_valid_instructions(self, instructions):
        unknown = [
            line.split(None, 1)[0]
            for line in instructions
            if line.split(None, 1)[0].upper() not in VALID_INSTRUCTIONS
        ]
        assert not unknown, f"Unbekannte Anweisungen: {unknown}"

    def test_exactly_one_cmd(self, instructions):
        cmds = [l for l in instructions if l.split(None, 1)[0].upper() == "CMD"]
        assert len(cmds) == 1
        assert "bot.py" in cmds[0]

    def test_data_directory_is_created(self, dockerfile):
        """Ohne das Verzeichnis schlaegt der erste Premium-Unlock fehl."""

        assert "mkdir -p /app/data" in dockerfile

    def test_copies_every_runtime_module(self, dockerfile):
        for required in ("bot.py", "config.py", "health.py", "core/", "ui/", "templates/"):
            assert required in dockerfile, f"{required} fehlt im Image"

    def test_copy_sources_exist(self, instructions):
        for line in instructions:
            if line.split(None, 1)[0].upper() != "COPY":
                continue
            for source in line.split()[1:-1]:
                assert (BASE_DIR / source.rstrip("/")).exists(), f"COPY-Quelle fehlt: {source}"

    def test_copy_sources_survive_dockerignore(self, instructions, ignore_rules):
        """Eine zu breite .dockerignore-Regel wuerde den Build stillschweigend leeren."""

        for line in instructions:
            if line.split(None, 1)[0].upper() != "COPY":
                continue
            for source in line.split()[1:-1]:
                path = BASE_DIR / source.rstrip("/")
                if path.is_dir():
                    files = [f for f in path.rglob("*") if f.is_file()]
                    kept = [
                        f
                        for f in files
                        if not _is_ignored(str(f.relative_to(BASE_DIR)), ignore_rules)
                    ]
                    assert kept, f"{source} wird komplett von .dockerignore entfernt"
                else:
                    rel = str(path.relative_to(BASE_DIR))
                    assert not _is_ignored(rel, ignore_rules), f"{rel} wird ausgeschlossen"


class TestDockerignore:
    def test_excludes_secrets_and_state(self, ignore_rules):
        patterns, _ = ignore_rules
        for entry in (".env", "data", ".venv"):
            assert entry in patterns, f"'{entry}' gehoert nicht ins Image"

    def test_keeps_env_example(self, ignore_rules):
        _, negations = ignore_rules
        assert ".env.example" in negations


@pytest.fixture(scope="module")
def railway() -> dict:
    return tomllib.loads((BASE_DIR / "railway.toml").read_text(encoding="utf-8"))


class TestRailwayConfig:

    def test_uses_dockerfile_builder(self, railway):
        assert railway["build"]["builder"] == "DOCKERFILE"
        assert (BASE_DIR / railway["build"]["dockerfilePath"]).exists()

    def test_healthcheck_matches_health_module(self, railway):
        """healthcheckPath muss einer Route in health.py entsprechen."""

        path = railway["deploy"]["healthcheckPath"]
        source = (BASE_DIR / "health.py").read_text(encoding="utf-8")
        assert f'add_get("{path}"' in source, f"Keine Route fuer {path} in health.py"

    def test_health_server_enabled_by_default(self):
        """Ein deaktivierter Health-Server laesst den Railway-Healthcheck scheitern."""

        import config

        assert config.HEALTH_SERVER is True

    def test_start_command_matches_dockerfile(self, railway, dockerfile):
        assert "bot.py" in railway["deploy"]["startCommand"]
        assert "bot.py" in dockerfile

    def test_procfile_agrees(self):
        assert "bot.py" in (BASE_DIR / "Procfile").read_text(encoding="utf-8")
