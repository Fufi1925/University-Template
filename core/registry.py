"""Template registry — loads and indexes every ``templates/*.json`` file."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Iterator

from .schema import Template, TemplateError

LOGGER = logging.getLogger("architect.registry")

__all__ = ["TemplateRegistry"]


class TemplateRegistry:
    """Loads templates from disk and keeps free/premium ordering stable."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self._templates: dict[str, Template] = {}

    # ------------------------------------------------------------- loading --
    def load(self) -> "TemplateRegistry":
        """(Re)load every template file. Raises on the first invalid file."""

        if not self.directory.is_dir():
            raise TemplateError(f"Template-Ordner nicht gefunden: {self.directory}")

        templates: dict[str, Template] = {}
        for path in sorted(self.directory.glob("*.json")):
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise TemplateError(f"{path.name}: ungültiges JSON — {exc}") from exc

            template = Template.parse(raw, source=path.name)
            if template.key in templates:
                raise TemplateError(
                    f"{path.name}: Template-Key '{template.key}' ist bereits vergeben"
                )
            templates[template.key] = template

        if not templates:
            raise TemplateError(f"Keine Templates in {self.directory} gefunden")

        self._templates = templates
        LOGGER.info(
            "%d Templates geladen (%d free, %d premium)",
            len(self.all),
            len(self.free),
            len(self.premium),
        )
        return self

    # ------------------------------------------------------------- access ---
    def get(self, key: str) -> Template | None:
        return self._templates.get(key)

    def __contains__(self, key: object) -> bool:
        return key in self._templates

    def __len__(self) -> int:
        return len(self._templates)

    def __iter__(self) -> Iterator[Template]:
        return iter(self.all)

    @staticmethod
    def _sort(templates: list[Template]) -> list[Template]:
        return sorted(templates, key=lambda t: (t.premium, t.name.lower()))

    @property
    def all(self) -> list[Template]:
        return self._sort(list(self._templates.values()))

    @property
    def free(self) -> list[Template]:
        return self._sort([t for t in self._templates.values() if not t.premium])

    @property
    def premium(self) -> list[Template]:
        return self._sort([t for t in self._templates.values() if t.premium])

    def available_to(self, *, premium: bool) -> list[Template]:
        return self.all if premium else self.free

    # -------------------------------------------------------------- stats ---
    @property
    def totals(self) -> dict[str, int]:
        return {
            "templates": len(self._templates),
            "categories": sum(t.category_count for t in self._templates.values()),
            "channels": sum(t.channel_count for t in self._templates.values()),
            "voice": sum(t.voice_count for t in self._templates.values()),
        }
