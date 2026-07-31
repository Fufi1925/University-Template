"""Die CI-Konfiguration selbst.

Ein Tippfehler in ``ci.yml`` faellt sonst genau dann auf, wenn man die
Pipeline am dringendsten braucht — und ein Workflow, der versehentlich nur
noch die Tests ausfuehrt, meldet weiter brav gruen, waehrend Ruff und Mypy
still verschwunden sind.

Geprueft wird deshalb nicht nur, dass die Dateien gueltiges YAML sind,
sondern auch, dass die vier Pruefungen tatsaechlich darin vorkommen.
"""

from __future__ import annotations

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml", reason="pyyaml nicht installiert")

BASE_DIR = Path(__file__).resolve().parent.parent
WORKFLOW = BASE_DIR / ".github" / "workflows" / "ci.yml"
DEPENDABOT = BASE_DIR / ".github" / "dependabot.yml"


@pytest.fixture(scope="module")
def workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def raw_workflow() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def _commands(job: dict) -> str:
    """Alle ``run``-Bloecke eines Jobs als ein Text."""

    return "\n".join(step.get("run", "") for step in job.get("steps", []))


@pytest.fixture(scope="module")
def quality_commands(workflow: dict) -> str:
    return _commands(workflow["jobs"]["quality"])


@pytest.fixture(scope="module")
def docker_job(workflow: dict) -> dict:
    assert "docker" in workflow["jobs"], (
        "Ein gruener Testlauf nuetzt nichts, wenn das Image nicht baut"
    )
    return workflow["jobs"]["docker"]


class TestWorkflowIsValid:
    def test_files_exist(self):
        assert WORKFLOW.exists(), "Ohne Workflow laeuft nichts automatisch"
        assert DEPENDABOT.exists()

    def test_workflow_parses(self, workflow):
        assert isinstance(workflow, dict)

    def test_dependabot_parses(self):
        data = yaml.safe_load(DEPENDABOT.read_text(encoding="utf-8"))
        assert data["version"] == 2
        ecosystems = {entry["package-ecosystem"] for entry in data["updates"]}
        assert "pip" in ecosystems
        assert "github-actions" in ecosystems, (
            "Auch die Actions in der Pipeline veralten"
        )

    def test_runs_on_push_and_pull_request(self, workflow):
        # PyYAML liest das unquotierte ``on:`` als Boolean True — deshalb beide
        # Schluessel akzeptieren.
        triggers = workflow.get("on") or workflow.get(True)
        assert triggers, "Der Workflow hat keine Ausloeser"
        assert "push" in triggers
        assert "pull_request" in triggers


class TestAllChecksArePresent:
    """Die vier Pruefungen, die lokal auch gefordert werden."""

    @pytest.mark.parametrize(
        ("tool", "hint"),
        [
            ("ruff check", "Linting"),
            ("mypy", "Typpruefung"),
            ("pytest", "Testsuite"),
        ],
    )
    def test_tool_runs(self, tool, hint, quality_commands):
        assert tool in quality_commands, f"{hint} fehlt in der Pipeline"

    def test_lockfile_is_verified(self, quality_commands):
        """Deployt wird aus dem Lockfile — also muss es auch geprueft werden."""

        assert "--require-hashes" in quality_commands
        assert "requirements.lock" in quality_commands

    def test_coverage_is_measured(self, quality_commands):
        assert "--cov" in quality_commands

    def test_coverage_threshold_is_enforced(self):
        """Gemessene Abdeckung ohne Schwelle ist nur eine Zahl.

        ``fail_under`` laesst die Pipeline scheitern, wenn neue Zeilen ohne
        Tests dazukommen — sonst rutscht der Wert ueber Monate nach unten,
        ohne dass es jemandem auffaellt.
        """

        import tomllib

        data = tomllib.loads((BASE_DIR / "pyproject.toml").read_text(encoding="utf-8"))
        threshold = data["tool"]["coverage"]["report"]["fail_under"]

        assert threshold >= 90, f"Die Schwelle ist mit {threshold}% zu niedrig"

    def test_no_format_check(self, quality_commands):
        """Bewusste Entscheidung, die nicht versehentlich zurueckkommen soll.

        ``ruff format`` wuerde die von Hand ausgerichteten Zeichentabellen in
        core/small_caps.py umbrechen.
        """

        assert "ruff format" not in quality_commands


class TestDockerJob:
    def test_builds_the_image(self, docker_job):
        uses = [step.get("uses", "") for step in docker_job["steps"]]
        assert any("build-push-action" in entry for entry in uses)

    def test_does_not_push_anything(self, docker_job):
        """Die CI soll pruefen, nicht veroeffentlichen."""

        for step in docker_job["steps"]:
            if "build-push-action" in step.get("uses", ""):
                assert step["with"]["push"] is False

    def test_checks_the_container_user(self, docker_job):
        commands = _commands(docker_job)
        assert "root" in commands, "Niemand prueft, ob der Container als root laeuft"

    def test_checks_the_token_message(self, docker_job):
        commands = _commands(docker_job)
        assert "DISCORD_TOKEN" in commands


class TestJobsAreBounded:
    """Ein haengender Job blockiert sonst stundenlang einen Runner."""

    @pytest.mark.parametrize("job", ["quality", "docker"])
    def test_timeout_is_set(self, job, workflow):
        assert "timeout-minutes" in workflow["jobs"][job], (
            f"Job '{job}' laeuft ohne Zeitlimit"
        )

    def test_concurrency_cancels_outdated_runs(self, workflow):
        concurrency = workflow.get("concurrency")
        assert concurrency, "Ohne concurrency laufen ueberholte Pushes weiter"
        assert concurrency.get("cancel-in-progress") is True


class TestPythonVersionMatchesTheImage:
    def test_ci_uses_the_same_python_as_the_dockerfile(self, raw_workflow):
        """Getestet werden muss die Version, die produktiv laeuft."""

        import re

        dockerfile = (BASE_DIR / "Dockerfile").read_text(encoding="utf-8")
        match = re.search(r"FROM python:(\d+\.\d+)", dockerfile)
        assert match, "Das Basis-Image nennt keine Python-Version"
        assert f'"{match.group(1)}"' in raw_workflow, (
            f"Die CI testet nicht gegen Python {match.group(1)}"
        )


class TestCoverageScope:
    """Die Messung muss alles erfassen, was im Betrieb laeuft.

    Diese Klasse entstand aus einem konkreten Versaeumnis: ``bot.py`` stand
    monatelang nicht in ``source`` und wurde von keinem Test importiert. Die
    gemeldete Abdeckung galt fuer alles ausser dem Einstiegspunkt — 450
    ungetestete Zeilen, die in keiner Zahl auftauchten.
    """

    @staticmethod
    def _configured_sources() -> set[str]:
        import tomllib

        data = tomllib.loads((BASE_DIR / "pyproject.toml").read_text(encoding="utf-8"))
        return set(data["tool"]["coverage"]["run"]["source"])

    def test_every_runtime_module_is_measured(self):
        """Neue Module am Projektrand duerfen nicht still durchrutschen."""

        sources = self._configured_sources()

        runtime = {
            path.stem if path.parent == BASE_DIR else path.parent.name
            for path in BASE_DIR.glob("*.py")
        }
        runtime |= {
            package.name
            for package in BASE_DIR.iterdir()
            if package.is_dir() and (package / "__init__.py").exists()
        }
        # tools/ sind Entwickler-Skripte, kein Teil des Laufzeit-Images
        # (siehe .dockerignore). test_generator_sync.py fuehrt sie trotzdem aus.
        runtime -= {"tools", "tests"}

        missing = sorted(runtime - sources)
        assert not missing, (
            f"Diese Module werden nicht gemessen: {missing}. "
            "In pyproject.toml unter [tool.coverage.run] source ergaenzen."
        )

    def test_the_entry_point_is_measured(self):
        """Ausdruecklich, weil genau das einmal gefehlt hat."""

        assert "bot" in self._configured_sources()

    def test_tools_are_excluded_but_exercised(self):
        """Nicht gemessen heisst nicht ungeprueft.

        Der Generator laeuft in test_generator_sync.py real durch; dort wird
        sein Ergebnis mit den eingecheckten Vorlagen verglichen.
        """

        assert "tools" not in self._configured_sources()
        assert (BASE_DIR / "tests" / "test_generator_sync.py").exists()
