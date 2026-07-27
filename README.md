# 🏛️ Discord Architect

Ein Discord-Bot, der komplette Server-Strukturen aus fertigen Vorlagen baut —
**10 Templates, 886 Kanäle, 195 Voice-Räume** — komplett auf Deutsch, in
Small Caps, mit einer Oberfläche vollständig aus **Components V2**.

```
!start
```

---

## Was der Bot macht

Nach `!start` erscheint ein Menü mit drei kostenlosen Vorlagen. Ein Klick auf
den grünen Premium-Button öffnet ein Key-Fenster; nach Eingabe des Keys stehen
sieben weitere Vorlagen zur Verfügung.

| | Template | Kategorien | Kanäle | Voice |
|---|---|---:|---:|---:|
| 🆓 | **Community Discord** — der Allrounder | 15 | 93 | 21 |
| 🆓 | **RP Server** — Fraktionen, Behörden, Wirtschaft | 17 | 100 | 27 |
| 🆓 | **Social Lounge** — Gespräche, Medien, Aktivitäten | 15 | 95 | 22 |
| 💎 | **Gaming Pro Hub** — Squads, Turniere, Scrims | 15 | 99 | 26 |
| 💎 | **Anime & Manga Hub** — Seasonals, Watch-Partys | 17 | 96 | 22 |
| 💎 | **Study & University** — Fächer, Pomodoro-Räume | 16 | 96 | 19 |
| 💎 | **Creator Studio** — Produktionsablauf | 15 | 83 | 16 |
| 💎 | **Support Center** — Tickets, Eskalation | 13 | 67 | 14 |
| 💎 | **Esports Organisation** — Kader, Spieltag | 14 | 82 | 15 |
| 💎 | **Business & Company** — Abteilungen, Kunden | 13 | 75 | 13 |

Der Bot legt **ausschließlich die Struktur** an. Er schreibt keine
automatischen Nachrichten in deine Kanäle.

---

## Die vier Kernpunkte

### 1 · Deutsch als Hauptsprache, in Small Caps

Alle Kanal- und Kategorienamen sind deutsch. Discord schreibt Kanalnamen
zwangsweise klein — normale Formatierung geht dabei kaputt.
Unicode-Kapitälchen überstehen das, weil jedes Zeichen **selbst** schon seine
Kleinform ist:

```
📢・ᴀɴᴋᴜᴇɴᴅɪɢᴜɴɢᴇɴ    🔊・ᴀʟʟɢᴇᴍᴇɪɴᴇʀ-ᴛᴀʟᴋ    🛡️・ᴛᴇᴀᴍ-ᴄʜᴀᴛ
```

Umlaute werden zu `ae/oe/ue` gefaltet (`ankündigungen` → `ᴀɴᴋᴜᴇɴᴅɪɢᴜɴɢᴇɴ`).
Das ist keine Bequemlichkeit, sondern Notwendigkeit: Unicode kennt schlicht
keine Kapitälchen-Umlaute. Die Alternative wäre ein optischer Bruch mitten im
Wort gewesen.

Etablierte Lehnwörter bleiben stehen, wo eine Eindeutschung gestelzt wirken
würde — `memes`, `clips`, `tickets`, `podcast`, `budget`, `pomodoro`.

### 2 · Sprachbereich: Deutsch und English

Jede Vorlage hat einen eigenen Sprachbereich mit genau zwei Kanälen plus
passenden Talks:

```
🌍・ꜱᴘʀᴀᴄʜᴇɴ            🗣️・ꜱᴘʀᴀᴄʜ-ᴛᴀʟᴋꜱ
   🇩🇪・ᴅᴇᴜᴛꜱᴄʜ            🇩🇪・ᴅᴇᴜᴛꜱᴄʜ-ᴛᴀʟᴋ
   🇬🇧・ᴇɴɢʟɪꜱʜ            🇬🇧・ᴇɴɢʟɪꜱʜ-ᴛᴀʟᴋ
```

Deutsch ist die Hauptsprache, English der Kanal für internationale Mitglieder.
Bewusst nicht mehr: ein halb ausgestorbener Kanal je Sprache schadet einer
Community mehr, als er nutzt.

Dazu in **jeder** Vorlage die vollständige Log-Suite:

```
🔨・mod-logs           ✏️・nachrichten-logs   🏷️・rollen-logs      📱・social-logs
👥・mitglieder-logs    🔊・sprach-logs        🗂️・kanal-logs       🤖・bot-logs
🔗・einladungs-logs    🗃️・server-logs
```

### 3 · Components V2 statt Embeds

Die gesamte Oberfläche nutzt `LayoutView` mit Containern, Sections, Separatoren
und Action-Rows. Kein einziges `discord.Embed` ist übrig — das wird sogar
[per Test erzwungen](tests/test_architect.py). Dazu gehört ein **Live-Fortschrittsbalken**
während des Baus:

```
⚙️  Community Discord wird gebaut
────────────────────────────────
`████████░░░░`  67%
Schritt 9/14 · 🔊・ᴠᴏɪᴄᴇ ʟᴏᴜɴɢᴇ
```

### 4 · Berechtigungen, die halten

Rollen bekommen keine handverlesenen Flags, sondern gehören zu einer von zehn
**Stufen** (`guest` → `member` → `helper` → `moderator` → `admin` → `owner`).
Jede Stufe ist eine echte Obermenge der darunterliegenden — auch das ist
getestet. Nur `👑・Inhaber` erhält `Administrator`.

Kanäle erben ihre Rechte immer von der Kategorie. Ein Log-Kanal kann damit
nicht versehentlich öffentlich werden, selbst wenn eine Einstellung vergessen
wird.

---

## Einrichtung

### 1 · Bot anlegen

1. [Discord Developer Portal](https://discord.com/developers/applications) → **New Application**
2. **Bot** → Token kopieren *(niemals in Git oder Chat)*
3. **Bot → Privileged Gateway Intents**: **Server Members** und **Message Content** aktivieren
4. **OAuth2 → URL Generator**: Scopes `bot` + `applications.commands`

Benötigte Rechte: *Rollen verwalten*, *Kanäle verwalten*, *Nachrichten senden*,
*Links einbetten*, *Nachrichtenverlauf anzeigen*.

> **Wichtig:** Die Bot-Rolle muss in der Serverliste **über** allen Rollen
> stehen, die sie verwalten soll. Sonst kann Discord die Rollen zwar anlegen,
> aber nicht sortieren oder vergeben.

### 2 · Lokal starten

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env      # DISCORD_TOKEN eintragen
python bot.py
```

Ohne aktivierte Intents startet der Bot trotzdem — setze
`ENABLE_PRIVILEGED_INTENTS=false` und nutze `/start` statt `!start`.

### 3 · Railway

`Dockerfile`, `Procfile` und `railway.toml` liegen bereit.

1. **New Project → Deploy from GitHub Repo**
2. Unter **Variables**: `DISCORD_TOKEN` und `ENABLE_PRIVILEGED_INTENTS=true`
3. Unter **Settings → Volumes**: **Add Volume**, Mount path `/app/data`

> Ohne Volume gehen die Premium-Freischaltungen bei jedem Redeploy verloren,
> weil der Container-Speicher flüchtig ist.

> **Warum kein `VOLUME` im Dockerfile?** Railway lehnt das ab
> (`docker VOLUME ... is not supported, use Railway Volumes`) und bricht den
> Build sofort ab. Persistenter Speicher wird dort ausschließlich im Dashboard
> konfiguriert. Ein Test stellt sicher, dass die Anweisung nicht zurückkehrt.

Bei reinem Docker ohne Railway wird das Volume beim Start gemountet:

```bash
docker build -t architect .
docker run -d --env-file .env -v architect-data:/app/data architect
```

`/health` liefert Live-Status:

```json
{"status":"online","guilds":3,"templates":10,"channels":886,"active_builds":0}
```

---

## Premium

Standard-Key: `Vexo x Fufi KEY 2354` — änderbar über `PREMIUM_KEY`.

Der Key wird **nie gespeichert**. Abgelegt wird nur das Paar aus Server- und
Benutzer-ID, und der Vergleich läuft über `hmac.compare_digest`, damit die
Antwortzeit nichts über den Key verrät. Mit `PREMIUM_UNLOCKS_GUILD=true` gilt
eine Freischaltung für den ganzen Server statt nur für den Einlöser.

> Vor dem öffentlichen Einsatz den Standard-Key ersetzen — er steht hier im
> Klartext in der Dokumentation.

---

## Die zwei Bau-Modi

Nach der Template-Auswahl fragt der Bot, wie vorgegangen werden soll:

**➕ Ergänzen** *(empfohlen)* — fügt nur hinzu, was fehlt. Bestehende Kanäle,
Rollen und Rechte bleiben unangetastet. Der Vorgang ist **idempotent**: ein
zweiter Durchlauf ändert nachweislich nichts, weil Objekte sowohl über ihren
dekorierten als auch über ihren einfachen Namen erkannt werden — ein bereits
vorhandener `general` wird also nicht als `💬・ɢᴇɴᴇʀᴀʟ` verdoppelt.

**🧨 Neu aufsetzen** — löscht alles Löschbare und baut frisch. `@everyone`,
Integrationsrollen und Rollen über der Bot-Rolle kann Discord aus
Sicherheitsgründen nicht entfernen; diese werden übersprungen und im Ergebnis
gemeldet. **Nicht umkehrbar.**

Beide Modi kann nur starten, wer **Server verwalten** darf.

---

## Projektstruktur

```
bot.py                  Einstiegspunkt, Commands, Fehlerbehandlung
config.py               Konfiguration aus Umgebungsvariablen
health.py               HTTP-Health-Endpunkt für Railway

core/
  small_caps.py         Typografie + Namensvergleich
  schema.py             Typisiertes Template-Modell mit Validierung
  permissions.py        Rollenstufen und Sichtbarkeitsregeln
  registry.py           Lädt und indexiert templates/*.json
  premium.py            Key-Prüfung und atomarer Unlock-Speicher
  builder.py            Die Engine: erstellt Rollen, Kategorien, Kanäle

ui/
  components.py         Components-V2-Bausteine
  views.py              Startmenü, Premium-Modal, Vorschau, Fortschritt

templates/*.json        Die 10 Vorlagen — reine Daten
tools/
  generate_templates.py Erzeugt die JSONs aus gemeinsamen Bausteinen
  preview.py            Templates im Terminal ansehen
tests/                  98 Tests
```

**Templates sind Daten, kein Code.** Eine neue Vorlage ist eine JSON-Datei —
kein Eingriff in die Engine nötig. Beim Start werden alle Dateien gegen das
Schema geprüft, inklusive Discord-Limits (50 Kategorien, 500 Kanäle) und
doppelter Namen. Ein Fehler bricht den Start ab, statt mitten im Umbau eines
echten Servers aufzufallen.

---

## Entwicklung

```bash
pip install -r requirements-dev.txt

python -m pytest tests/ -v          # 98 Tests
python tools/preview.py             # Übersicht aller Templates
python tools/preview.py rp          # Kanalbaum einer Vorlage
python tools/generate_templates.py  # JSONs neu erzeugen
```

Die Testsuite prüft unter anderem:

- **Components V2** — jede View wird zu echtem API-Payload serialisiert und
  gegen Discords Limits geprüft (40 Komponenten, 4.000 Zeichen, 25 Select-Optionen)
- **Bau-Simulation** — alle 10 Templates werden gegen ein nachgebildetes Guild
  gebaut; geprüft werden Idempotenz, Wipe-Verhalten und dass private
  Kategorien für `@everyone` unsichtbar sind
- **Berechtigungen** — dass jede Stufe eine Obermenge der vorherigen ist und
  nur der Inhaber `Administrator` bekommt
- **Deployment** — dass kein `VOLUME` im Dockerfile steht (Railway bricht sonst
  den Build ab) und jeder `COPY`-Pfad die `.dockerignore` überlebt
- **Premium** — dass der Key nie auf der Festplatte landet und eine
  Freischaltung nicht auf andere Nutzer oder Server überspringt

---

## Grenzen

- Discord erlaubt **500 Kanäle** und **50 Kategorien** pro Server. Der Bot
  prüft das vorher und lehnt ab, statt mittendrin zu scheitern.
- Beim Anlegen von 120+ Kanälen greifen Rate-Limits; der Bot drosselt sich
  selbst, ein großes Template braucht daher **ein bis zwei Minuten**.
- `stage`- und `forum`-Kanäle brauchen die Community-Funktion des Servers. Ist
  sie aus, weicht der Bot automatisch auf Voice- bzw. Textkanäle aus.

---

## Lizenz

MIT · erstellt von **Vexo × Fufi**
