"""Speedrun-Jobs: Server bauen und dabei live berichten.

Das Dashboard startet einen Bau und liest danach den Fortschritt ab.
Beides braucht einen gemeinsamen Zustand, denn der Bau laeuft im
Hintergrund weiter, waehrend die Abfrage schon wieder vorbei ist.

Bewusst nur im Arbeitsspeicher. Ein Bau dauert Minuten, nicht Tage --
laeuft der Bot neu an, ist der Bau ohnehin abgebrochen, und ein auf
Platte gespeicherter Job wuerde dann fuer immer auf "laeuft" stehen
bleiben.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum

LOGGER = logging.getLogger(__name__)

# Wie lange ein abgeschlossener Job noch abrufbar bleibt. Lang genug,
# dass das Dashboard die letzten Zeilen sicher mitbekommt.
KEEP_FINISHED = 15 * 60

# Obergrenze fuer die Zeilen eines Jobs. Ein Bau erzeugt ~40; die Grenze
# faengt nur den Fall ab, dass etwas in einer Schleife haengt.
MAX_LINES = 500


class JobState(str, Enum):
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


@dataclass(slots=True)
class LogLine:
    """Eine Zeile fuer das Terminal im Dashboard."""

    text: str
    # "template" oder "main" -- das Dashboard faerbt danach ein, damit
    # man sieht, welcher Bot gerade arbeitet.
    source: str = "template"
    level: str = "info"
    at: float = field(default_factory=time.time)

    def as_dict(self) -> dict:
        return {
            "text": self.text,
            "source": self.source,
            "level": self.level,
            "at": self.at,
        }


@dataclass(slots=True)
class Job:
    """Ein laufender oder abgeschlossener Speedrun."""

    guild_id: int
    template_key: str
    state: JobState = JobState.RUNNING
    step: int = 0
    total: int = 0
    lines: list[LogLine] = field(default_factory=list)
    error: str = ""
    started: float = field(default_factory=time.time)
    finished: float = 0.0
    # Was gebaut wurde -- der University Bot braucht die Namen, um
    # danach Verify, Logs und den Rest zu verdrahten.
    result: dict = field(default_factory=dict)

    def log(self, text: str, *, source: str = "template", level: str = "info") -> None:
        if len(self.lines) >= MAX_LINES:
            return
        self.lines.append(LogLine(text=text, source=source, level=level))
        LOGGER.info("[speedrun %s] %s", self.guild_id, text)

    def as_dict(self, since: int = 0) -> dict:
        """Zustand plus die Zeilen ab ``since``.

        Das Dashboard merkt sich, wie viele Zeilen es schon hat, und
        holt nur die neuen -- sonst waechst jede Abfrage mit.
        """
        return {
            "guild_id": str(self.guild_id),
            "template": self.template_key,
            "state": self.state.value,
            "step": self.step,
            "total": self.total,
            "error": self.error,
            "started": self.started,
            "finished": self.finished,
            "result": self.result,
            "line_count": len(self.lines),
            "lines": [line.as_dict() for line in self.lines[since:]],
        }


class JobStore:
    """Alle Jobs, einer pro Server."""

    def __init__(self) -> None:
        self._jobs: dict[int, Job] = {}
        self._tasks: dict[int, asyncio.Task] = {}

    def get(self, guild_id: int) -> Job | None:
        self._prune()
        return self._jobs.get(guild_id)

    def running(self, guild_id: int) -> bool:
        job = self._jobs.get(guild_id)
        return job is not None and job.state is JobState.RUNNING

    def start(self, guild_id: int, template_key: str) -> Job:
        self._prune()
        job = Job(guild_id=guild_id, template_key=template_key)
        self._jobs[guild_id] = job
        return job

    def attach(self, guild_id: int, task: asyncio.Task) -> None:
        """Task festhalten.

        asyncio haelt nur eine schwache Referenz auf laufende Tasks --
        ohne das hier kann der Bau mitten drin eingesammelt werden.
        """
        self._tasks[guild_id] = task
        task.add_done_callback(lambda _t: self._tasks.pop(guild_id, None))

    def _prune(self) -> None:
        now = time.time()
        for guild_id, job in list(self._jobs.items()):
            if job.state is JobState.RUNNING:
                continue
            if job.finished and now - job.finished > KEEP_FINISHED:
                del self._jobs[guild_id]


STORE = JobStore()
