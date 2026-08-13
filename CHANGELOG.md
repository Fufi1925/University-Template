# Änderungsverlauf

Format nach [Keep a Changelog](https://keepachangelog.com/de/1.1.0/),
Versionierung nach [Semantic Versioning](https://semver.org/lang/de/).

## [3.5.0] — 2026-08-14

### Hinzugefügt

- **7-Tage-Premium mit Ablaufdatum.** Ein persönlicher Key schaltet
  Premium jetzt für genau sieben Tage frei (`grant(…, expires_at=…)`).
  Nach Ablauf fällt die Freischaltung beim ersten Zugriff von selbst weg;
  das Ablaufdatum übersteht einen Neustart. Master-Keys bleiben
  dauerhaft. Die Freischalt-Nachricht zeigt „· 7 Tage".
- **Meldung an den University Bot.** Beim Einlösen eines persönlichen
  Keys meldet der Bot den Grant an `POST /api/v1/premium/grant`
  (X-Partner-Token, mit `user_id`, `guild_id`, `expires_at`,
  `duration_days`) — das Gegenstück zur bestehenden `check`-Abfrage.
  Damit kann das Dashboard des University Bots „7 Tage Premium"
  anzeigen. Die Meldung wirft nie: schlägt sie fehl, gilt Premium lokal
  trotzdem, und der Bot warnt im Log.

### Geändert

- `PremiumStore.redeem_key()` meldet jetzt, was eingelöst wurde
  (`"master"`, `"personal"` oder `None`), statt nur Ja/Nein zu sagen.
- Befristete Freischaltungen lösen `PREMIUM_UNLOCKS_GUILD` bewusst
  nicht aus — ein persönlicher 7-Tage-Key gehört einem Konto, nicht
  einer ganzen Community.
- `revoke_user` räumt auch befristete Freischaltungen ab;
  `unlock_count` zählt sie mit.

## [3.4.0] — 2026-08-14

### Hinzugefügt

- **TikTok-Gate vor dem Premium-Key.** „Jetzt mehr Templates mit Premium
  freischalten" öffnet jetzt ein Fenster mit dem TikTok-Account
  (`@university6421`, konfigurierbar über `TIKTOK_HANDLE`/`TIKTOK_URL`),
  einem Link-Knopf und dem Knopf **„Ich habe abonniert"**. Der Klick
  darauf schickt den persönlichen Key per Direktnachricht — mit einer
  ausführlichen Anleitung, wie er einzulösen ist.
- **`/template key`** — öffnet das Key-Fenster direkt, damit der Key aus
  der DM ohne Umweg eingelöst werden kann. Wer bereits Premium hat,
  bekommt das gesagt statt eines leeren Fensters.

### Geändert

- **Template-Angebot gestrafft.** Neun Nischen-Vorlagen sind entfernt
  (Film & Serien, Reisen, Sammeln, Bücher, Kunst, Kochen, Haustiere,
  Finanzen, Wissenschaft) — geblieben sind 15 Vorlagen, die einen echten
  Server tragen: die 14 bewährten plus Fitness & Sport. Der
  AI-Assistent kennt entsprechend nur noch die vorhandenen Themen.
- Die Direktnachricht mit dem Key erklärt den Einlöseweg jetzt
  vollständig (`/template key`), statt nur den Key zu zeigen.

### Hinweis

- Der TikTok-Follow ist technisch nicht prüfbar (Discord und TikTok
  sprechen nicht miteinander; die TikTok-API verlangt eine
  Partnerfreigabe). Die Bestätigung läuft deshalb über den Knopf
  „Ich habe abonniert" — dokumentiert in der README.

## [3.3.0] — 2026-08-14

### Hinzugefügt

- **Zehn neue Premium-Vorlagen** (alle über den Generator erzeugt, mit
  Gate, Sprachbereich, Ticket-Panel, Rollenvergabe, Checkliste und
  voller Log-Suite): Fitness & Sport, Haustiere & Tierwelt, Kochen &
  Genuss, Reisen & Abenteuer, Kunst & Kreativ, Bücher & Geschichten,
  Film & Serien, Wissenschaft & Technik, Finanzen & Krypto und Sammeln
  & Tauschen. Zusammen 24 Vorlagen, 1812 Kanäle, 399 Voice-Räume.
- **Persönliche Premium-Keys per DM.** „Jetzt mehr Templates mit
  Premium freischalten" schickt einen persönlichen, einmaligen,
  7 Tage gültigen Key per Direktnachricht; eingelöst wird er im
  Key-Fenster. Der Key ist an das Konto gebunden, ein neuer Klick
  ersetzt alte offene Keys, gespeichert wird nur der SHA-256-Hash.
  Sind die DMs geschlossen, erklärt der Bot das und bietet den Knopf
  „Key eingeben" an. Der Master-Key (`PREMIUM_KEY`) bleibt gültig.
- **Neues Startmenü.** Die kostenlosen Vorlagen stehen als eigene
  Karten mit dem Akzent ihrer Vorlage; die Premium-Sektion zeigt
  gesperrt nur eine Vorschau mit dem Freischalt-Knopf und nach dem
  Unlock alle Vorlagen. Kopf mit Kennzahlen über der Liste.
- **Backup aufgewertet:** `/template backup erstellen` nennt jetzt
  Rollen- und Kanalzahlen in der Antwort, legt `BACKUP_DIR` beim Start
  an (mit Log, ob das Volume greift) und übersteht eine abgelaufene
  Interaktion — das Backup liegt dann trotzdem auf der Platte.

### Geändert

- **Premium-Verteilung neu:** fünf Vorlagen bleiben kostenlos
  (Community, Social Lounge, Musik & DJ, Entwickler, Kleiner Server),
  der **RP Server ist jetzt Premium** — insgesamt 5 kostenlos,
  19 Premium.
- Der AI-Assistent kennt die zehn neuen Themen (Fitness, Haustiere,
  Kochen, Reisen, Kunst, Bücher, Film, Wissenschaft, Finanzen,
  Sammeln) und kann sie zu Vorlagen kombinieren.

## [3.2.0] — 2026-08-14

### Hinzugefügt

- **`/template`-Befehlsgruppe** ersetzt die Prefix-Befehle. `!start`,
  `!regeln`, `!partner-setup`, `!ping` und die alten `/start`- und
  `/regeln`-Slash-Befehle sind entfernt; alles lebt jetzt unter
  `/template …` plus einem eigenständigen `/ping`.
- **`/template list`** — alle Vorlagen mit Kategorien, Kanälen und Rollen;
  die Auswahl öffnet die Detailansicht mit Strukturvorschau.
- **`/template löschen [vorlage]`** — mit Argument oder Auswahl-Dialog:
  eine Vorlage rückgängig machen (nur passende Kategorien, Kanäle und
  eigene Rollen — fremde Kanäle und die geteilte Basis-Leiter bleiben)
  oder kompletter Wipe. Beides erst nach Bestätigung, mit derselben
  Bausperre wie ein Build.
- **`/template ai`** — regelbasierter Assistent ohne externe API:
  Beschreibung abfragen, Themen per Keywords erkennen, bis zu drei zu
  einer Vorlage kombinieren. Das Ergebnis läuft durch dieselbe
  Validierung wie jede JSON-Vorlage.
- **`/template backup erstellen`** — Serverstruktur (Rollen, Kategorien,
  Kanäle, Topics, Overwrites) als lesbare JSON-Datei, atomar geschrieben
  unter `BACKUP_DIR`; IDs als Strings, damit Snowflakes keine Stellen
  verlieren.
- **`ServerBuilder.unapply()` und `wipe_guild()`** — das Entfernen teilt
  Namensabgleich, Throttle, Cache-Aufräumen und Berichtswarnungen mit
  dem Bauen; 404/403 auf einzelnen Objekten brechen den Durchlauf nicht ab.

### Geändert

- Meldungen in UI, Webserver, Autosetup und Statusrotation nennen
  `/template …` statt `!start`.
- Mypy: `explicit_package_bases = true` in `pyproject.toml`. Neuere
  Mypy-Versionen entdeckten die Testdateien unter zwei Modulnamen
  (``test_x`` und ``tests.test_x``) und brachen die Prüfung ab — die CI
  lief dadurch auf Rot. Zusätzlich eine umbenannte Schleifenvariable in
  `core/handover.py`, damit die Typenprüfung wieder durchläuft.
- `.env.example`: `COMMAND_PREFIX` entfernt, `BACKUP_DIR` dokumentiert,
  der Intent-Kommentar beschreibt jetzt Kanal-Modi und Eingangsschleuse
  statt Prefix-Befehle.

## [3.1.0] — 2026-07-31

Diese Version ändert nichts an dem, was der Bot *tut*. Sie schließt die Lücke
zwischen einem sorgfältig geschriebenen Projekt und einem, dessen Qualität
auch automatisch überprüft wird.

### Behoben

- **`!ping` stürzte vor dem ersten Heartbeat ab.** `round(bot.latency * 1000)`
  bekommt in diesem Fenster `NaN` und wirft einen `ValueError`. Ausgerechnet
  direkt nach dem Start greift man am ehesten zu `!ping`; jetzt steht dort ein
  Gedankenstrich statt eines Tracebacks.
- **`bot.py` wurde nie gemessen.** Die Coverage-Konfiguration nannte nur
  `core`, `ui` und `web` — 450 Zeilen Einstiegspunkt tauchten in keiner Zahl
  auf, kein Test hatte das Modul importiert. Jetzt bei 92 %, mit einem
  Wächter-Test gegen einen Rückfall.

### Sicherheit

- **Kein Standard-Premium-Key mehr.** `PREMIUM_KEY` hatte den Wert
  `Vexo x Fufi KEY 2354` im Quelltext, in `.env.example` **und** in der README.
  Damit hatte jeder Leser des Repositories Premium-Zugang auf jeder Installation,
  deren Betreiber die Variable nie gesetzt hatte. Ohne Wert ist Premium jetzt
  schlicht nicht freischaltbar (Fail-Closed), und der Bot weist beim Start
  darauf hin.
- **Container läuft nicht mehr als `root`.** Eigener Benutzer `app` (UID 10001),
  `/app/data` gehört ihm.
- **`PremiumStore.is_configured` meldete bei einem Key aus reinen Leerzeichen
  fälschlich `True`.** Die Startwarnung blieb dadurch aus, obwohl niemand
  freischalten konnte. `verify()` hatte solche Eingaben ohnehin abgelehnt — der
  Fehler war nur unsichtbar.

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
- **566 neue Tests** (329 → 895):
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
  - `test_enforcement_edges.py` — die Ränder des einzigen Moduls, das
    Nachrichten von Menschen löscht: Team und Bots bleiben unangetastet, ein
    fehlgeschlagener Löschversuch erzeugt keinen irreführenden Hinweis, und
    der Zählkanal übersteht eine unlesbare Historie.
  - `test_persistence.py` — beide Speicher auf der Platte: atomares Schreiben,
    kaputte Dateien verhindern den Start nicht, der Premium-Key landet nie im
    Dateisystem.
  - `test_registry_loading.py` — dass ein Fehler in einer Vorlage den Start
    abbricht und die Meldung die betroffene Datei nennt.
  - `test_rules_assistant.py` — Kanalsuche, Berechtigungen an allen drei
    Einstiegspunkten und die URL-Prüfung des Baukastens.
  - `test_schema_validation.py` — jeder Validierungszweig einzeln, plus die
    Zusage, dass Fehlermeldungen Datei, Position und Feld benennen.
  - `test_small_helpers.py` — Small-Caps-Typografie, UI-Bausteine,
    Token-Details.
  - `test_views_flow.py` — Bestätigungsdialog, Abschlussbericht, Vorschau und
    die Weiterleitung zum Regelwerk-Assistenten.
  - `test_bot_events.py` — der Einstiegspunkt: Eingangsschleuse, Modi-
    Durchsetzung, alle vier Befehle, Statusrotation, Abschaltung und die
    Startfehler-Meldungen von `main()`.

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
- **Testabdeckung 81 % → 96 %**, per `fail_under = 95` in der CI abgesichert —
  und auf einer um 264 Zeilen größeren Grundlage als vorher, weil `bot.py` und
  `config.py` jetzt mitgemessen werden.
  Sieben Module stehen bei 100 %: `permissions`, `registry`, `rulesets`,
  `handshake`, `channel_intro`, `components`, `widgets`. Im Einzelnen:
  `ui/widgets.py` 50 → 100 %, `ui/rules.py` 77 → 99 %, `ui/views.py` 67 → 96 %,
  `core/enforcement.py` 81 → 99 %, `core/builder.py` 78 → 89 %,
  `core/autosetup.py` 91 → 97 %, `web.py` 95 → 98 %.

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
