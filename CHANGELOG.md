# Änderungsverlauf

Format nach [Keep a Changelog](https://keepachangelog.com/de/1.1.0/),
Versionierung nach [Semantic Versioning](https://semver.org/lang/de/).

## [3.1.0] — 2026-07-31

Diese Version ändert nichts an dem, was der Bot *tut*. Sie schließt die Lücke
zwischen einem sorgfältig geschriebenen Projekt und einem, dessen Qualität
auch automatisch überprüft wird.

### Sicherheit

- **Kein Standard-Premium-Key mehr.** `PREMIUM_KEY` hatte den Wert
  `Vexo x Fufi KEY 2354` im Quelltext, in `.env.example` **und** in der README.
  Damit hatte jeder Leser des Repositories Premium-Zugang auf jeder Installation,
  deren Betreiber die Variable nie gesetzt hatte. Ohne Wert ist Premium jetzt
  schlicht nicht freischaltbar (Fail-Closed), und der Bot weist beim Start
  darauf hin.
- **Container läuft nicht mehr als `root`.** Eigener Benutzer `app` (UID 10001),
  `/app/data` gehört ihm.

### Hinzugefügt

- **Lockfile** (`requirements.lock`) — voll gepinnt, mit Hashes, per
  `uv pip compile --universal` für Python 3.12 und 3.13 gültig. Das Image
  installiert mit `--require-hashes`. Bisher konnte ein Patch-Release einer
  Abhängigkeit das Deployment verändern, ohne dass ein Commit stattfand.
- **CI-Pipeline** (`.github/workflows/ci.yml`): Ruff, Mypy und die Testsuite bei
  jedem Push. Zusätzlich wird das Docker-Image gebaut und geprüft, dass der
  Container nicht als root läuft und ohne Token verständlich abbricht.
- **Dependabot** für Python-Pakete und GitHub-Actions.
- **`pyproject.toml`** als Projektwurzel — Ruff, Mypy und Pytest zentral
  konfiguriert. `pytest.ini` ist darin aufgegangen.
- **`LICENSE`** — die README versprach MIT, die Datei fehlte. Das Projekt war
  damit formal unlizenziert.
- **Wiederholung bei Rate-Limits** (`core.builder.with_retry`): Ein 429 wird bis
  zu dreimal wiederholt, Discords `Retry-After` hat Vorrang, die Wartezeit ist
  auf 60 s gedeckelt. Ein `403` wird bewusst **nicht** wiederholt.
- **`HEALTHCHECK`** im Dockerfile — prüft denselben Endpunkt wie Railway, aber
  auch bei einem einfachen `docker run`.
- **193 neue Tests** (329 → 522):
  - `test_widget_callbacks.py` — was passiert, wenn jemand tatsächlich klickt:
    Rollenvergabe, Eingangssperre, fehlende und zu hoch stehende Rollen,
    Selbstrollen, Rückmeldung in jedem Fehlerfall.
  - `test_build_guards.py` — die vier Wächter vor einem Serverumbau, inklusive
    der Frage, ob die Sperre nach einem Abbruch wieder freigegeben wird.
  - `test_retry.py` — das neue Rate-Limit-Verhalten.
  - `test_generator_sync.py` — dass `tools/generate_templates.py` exakt die
    eingecheckten JSONs erzeugt. Bisher konnten Generator und Templates
    auseinanderlaufen, ohne dass es jemandem auffiel.
  - Deployment-Tests für die Container-Härtung.
  - `test_dependencies.py` — Lockfile vollständig, gepinnt, mit Hashes, im
    Einklang mit `requirements.txt`; Dockerfile nutzt es auch wirklich.
  - `test_ci_config.py` — dass die Pipeline-Datei gültig ist und alle vier
    Prüfungen enthält. Ein Workflow, aus dem still eine Prüfung verschwindet,
    meldet sonst weiter grün.
  - `test_premium_flow.py` — der Weg vom Button über das Key-Fenster bis ins
    Auswahlmenü, plus die Zustellung des Ergebnisses, wenn die Interaktion
    während eines minutenlangen Baus abgelaufen ist.
  - `test_rules_posting.py` — das Veröffentlichen eines Regelwerks inklusive
    des Löschpfads: „Neu aufsetzen" darf nur eigene Nachrichten entfernen.
  - `test_builder_resilience.py` — die Fehlerpfade des Builders: Preflight-
    Grenzen, abgelehnte Rollen, Stage→Voice- und Forum→Text-Rückfälle, und
    was der Wipe **nicht** anfassen darf.

### Geändert

- **Ruff: 146 Findings → 0.** Überflüssige `# noqa`, ungenutzte und unsortierte
  Importe, veraltete `typing`-Importe, quotierte Annotationen. Die
  Small-Caps-Zeichentabellen bleiben von Hand ausgerichtet (`ruff format` läuft
  bewusst nicht).
- **Mypy: 93 Fehler → 0**, im gesamten Projekt inklusive Tests.
  - `bot.py` reichte an fünf Stellen `Guild | None` ungeprüft weiter. Zur
    Laufzeit schützte nur `@commands.guild_only()` — ein verschobener Dekorator
    hätte gereicht. Jetzt über einen gemeinsamen Helfer `_require_guild`.
  - `core/permissions.py` typisiert die Overwrite-Map jetzt als
    `Role | Member | Object` statt als zu breites `abc.Snowflake`.
  - `PremiumModal.on_error` hatte eine Signatur, die nicht zur Basisklasse passte.
- **`ui/components.field_value()`** — das Auslesen von Modal-Eingaben steht an
  einer Stelle statt fünfmal verstreut.
- `__import__("contextlib")` mitten im Code durch einen normalen Import ersetzt.
- Testabdeckung 81 % → 88 %; `ui/widgets.py` von 50 % auf 88 %, `ui/views.py` von 67 % auf 86 %, `core/builder.py` von 78 % auf 84 %.

### Dokumentation

- README: veraltete Testzahl entfernt, Abschnitt „Entwicklung" um CI, Coverage,
  Ruff und Mypy erweitert, Premium-Abschnitt ohne Klartext-Key.
- `CONTRIBUTING.md` neu — Setup, Teststrategie, Sprachkonvention.

---

## [3.0.0] — 2026-07-28

- Discord Architect V3: Components V2, 10 Templates, neue Engine
- Partner-Handshake mit HMAC-signierten OAuth-`state`-Token
- Regelwerk-Assistent mit 20 Vorlagen und eigenem Baukasten
- Deutsch als Hauptsprache, Sprachbereich auf DE/EN reduziert
- Kanäle erklären sich selbst: angeheftete Startnachrichten, Widgets, Modi
