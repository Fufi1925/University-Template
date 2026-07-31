# Mitarbeiten

## Einrichten

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env        # Token eintragen
```

Vor jedem Push:

```bash
ruff check .
mypy .
pytest
```

Dieselben drei Befehle laufen in der CI. Läuft eins davon lokal nicht durch,
läuft es dort auch nicht durch.

## Sprache

**Deutsch** — im Code, in Kommentaren, in Commit-Nachrichten und in der
Oberfläche. Ältere Module sind teilweise englisch dokumentiert; das wird bei
Gelegenheit angeglichen, aber niemand soll deswegen fremden Code umschreiben.

Dateinamen, Bezeichner und Docstring-Konventionen bleiben englisch, wo es
etabliert ist (`def build_start_view`, `Args:`, `Returns:`).

In Quelltext-Kommentaren stehen Umlaute als `ae/oe/ue`, in Nutzertexten und
Docstrings echte Umlaute — die Kanalnamen erzwingen das ohnehin, weil Unicode
keine Small-Caps-Umlaute kennt.

## Kommentare

Die Regel, die dieses Projekt trägt: **Kommentare erklären das Warum, nicht das
Was.** Der Code sagt bereits, was passiert.

```python
# Schlecht: Wartet 0,35 Sekunden
# Gut:      Discord verträgt Bursts, aber anhaltendes Erstellen läuft in
#           harte Rate-Limits — der Abstand hält große Templates ruhig.
```

Besonders wertvoll sind Kommentare an Stellen, die falsch aussehen und es nicht
sind: warum kein `VOLUME` im Dockerfile steht, warum `compare_digest` statt `==`,
warum der Handshake ohne Secret *jedes* Token ablehnt.

## Tests

Neuer Code kommt mit Tests. Die Suite prüft Verhalten, nicht Implementierung —
ein Test soll fehlschlagen, wenn der Bot etwas Falsches *tut*, nicht wenn eine
Funktion umbenannt wurde.

Was sich bewährt hat:

- **Fehlerfälle sind wichtiger als der Erfolgsfall.** Beim Verify-Button ist
  interessant, was passiert, wenn die Rolle fehlt oder der Bot sie nicht
  vergeben darf — nicht, dass er im Normalfall funktioniert.
- **Nachbauten statt Mocks**, wo möglich. Ein `FakeMember`, der sich seine
  Rollenänderungen merkt, prüft mehr als ein `assert_called_once_with`.
- **Aussagekräftige Assertion-Meldungen.** `assert not bot.active_builds,
  "Der Server bleibt dauerhaft gesperrt"` erklärt beim Fehlschlag sofort,
  worum es ging.

## Templates ändern

Die Dateien in `templates/` sind **generiert**. Eine Handänderung am JSON geht
beim nächsten Generator-Lauf verloren.

```bash
# 1. tools/generate_templates.py bearbeiten
python tools/generate_templates.py
python tools/enrich_content.py      # falls Modi/Widgets betroffen
pytest tests/test_generator_sync.py
```

`test_generator_sync.py` erzwingt, dass Generator und eingecheckte Dateien
übereinstimmen — der Test schlägt fehl, wenn sie auseinanderlaufen, und nennt
die betroffene Datei.

## Commits

Kurze Betreffzeile im Imperativ, auf Deutsch, ohne Punkt am Ende:

```
Regelwerke im Paragraphen-Stil, RP getrennt nach IC und OOC
fix: content-Feld bei Components V2 entfernen
```

Ein Präfix (`fix:`, `docs:`) ist willkommen, aber nicht Pflicht. Wichtiger ist,
dass der Betreff sagt, was sich für den Nutzer ändert.
