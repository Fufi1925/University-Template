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
„Premium freischalten" öffnet ein Key-Fenster; nach Eingabe des Keys stehen
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

Jeder Textkanal bekommt eine **angeheftete Startnachricht**, die seinen Zweck
erklärt — abschaltbar mit einem Klick, falls die Kanäle leer bleiben sollen.

---

## Die sieben Kernpunkte

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
und Action-Rows. Kein einziges `discord.Embed` ist übrig — das wird
[per Test erzwungen](tests/test_architect.py).

Das Layout folgt bewusst wenigen Regeln, damit es ruhig bleibt und nicht nach
Baukasten aussieht:

- **Blockzitate** (`>`) rücken Inhalt ein und erzeugen eine klare Spalte
- **Emojis sind Navigation**, keine Dekoration — höchstens eines pro Überschrift
- **Eine Betonungsebene**: fett nur für Zahlen und Namen, keine Ausrufezeichen
- **Grau** (`-#`) für alles Nebensächliche

So sieht das Startmenü aus:

```
## Discord Architect
-# Server-Templates in Sekunden
────────────────────────────────────────────────
**Kostenlos**
> 🌐  Community Discord — Der Allrounder
> -# 15 Kategorien · 93 Kanäle · 21 Sprachkanäle
> 🎭  RP Server — Fraktionen, Behörden, Wirtschaft
> -# 17 Kategorien · 100 Kanäle · 27 Sprachkanäle

**Premium**  ·  7 weitere
> 🌸  Anime & Manga Hub — Seasonals, Fanart
> 🏢  Business & Company — Abteilungen, Kunden
────────────────────────────────────────────────
  [ Vorlage auswählen ▾ ]   [ 💎 Premium freischalten ]
```

Während des Einrichtens läuft ein Fortschrittsbalken:

```
### Community Discord wird eingerichtet
-# Schritt 9 von 16
────────────────────────────────────────────────
> `━━━━━━━━━━━━━━──────────`  56%
> 🔊・ꜱᴘʀᴀᴄʜᴋᴀɴᴀᴇʟᴇ
```

### 4 · Kanäle, die sich selbst erklären

90 leere Kanäle sind ein Friedhof. Deshalb schreibt der Bot in jeden Textkanal
eine angeheftete Startnachricht:

```
### 😂  Memes
────────────────────────────────────────────────
> Nur Memes
> Nur Beiträge mit **Bild, Video oder Link**.
> Reine Textnachrichten werden automatisch entfernt.
```

Der Text entsteht aus dem `topic` der Vorlage, aus handgeschriebenen `guide`-
Zeilen und aus dem **Modus** des Kanals. Fünf Modi gibt es:

| Modus | Wirkung |
|---|---|
| `media` | nur Beiträge mit Bild, Video oder Link — Text wird entfernt |
| `threads` | jeder Beitrag bekommt einen eigenen Thread |
| `counting` | nur die nächste Zahl zählt |
| `announce` | nur das Team schreibt |
| `log` | automatische Einträge, Hinweis „nicht hineinschreiben" |

`media` und `counting` werden **durchgesetzt**: Wer im Bilder-Kanal reinen Text
schreibt, dessen Nachricht wird gelöscht, mit einem Hinweis, der nach zwölf
Sekunden von selbst verschwindet. Das Team ist davon ausgenommen — und wenn der
Member-Cache unvollständig ist, wird im Zweifel **nicht** gelöscht.

Vier Kanäle bekommen statt eines Hinweises ein **funktionierendes Widget**:

- `✅・ᴠᴇʀɪꜰɪᴢɪᴇʀᴇɴ` — Button vergibt die Verified-Rolle und nimmt Unverified weg
- `📜・ʀᴇɢᴇʟɴ` — Zustimmung per Knopf statt bloßer Behauptung
- `🏷️・ʀᴏʟʟᴇɴ-ᴠᴇʀɢᴀʙᴇ` — Dropdown für Ping- und Interessensrollen
- `🎫・ᴛɪᴄᴋᴇᴛꜱ` — öffnet einen privaten Thread

Dazu Auto-Reaktionen (👍/👎 unter Vorschlägen, ⭐ im Showcase), eine `1` als
Startwert im Zähl-Kanal und eine Checkliste im Team-Bereich mit genau den
Dingen, die der Bot **nicht** automatisch erledigen kann.

Die Nachrichten sind idempotent: Ein zweiter Durchlauf bearbeitet die
vorhandene Nachricht, statt eine zweite zu posten. Der Bot erkennt seine
eigenen Nachrichten an einer unsichtbaren Signatur. Der Kanal-Modus überlebt
einen Neustart, weil er als unsichtbare Marke im Kanal-Topic steht — ganz ohne
Datenbank.

### 5 · Regelwerk-Assistent

Nach dem Bau bietet der Bot an, den Regelkanal zu füllen — oder später
jederzeit mit `!regeln`. Zur Auswahl stehen **22 fertige Regelwerke** im
Paragraphen-Stil:

```
## 📋  DISCORD REGELWERK
-# Mein Server
─────────────────────────────────────────────
> Mit dem Betreten dieses Servers akzeptierst
> du automatisch alle folgenden Regeln.
─────────────────────────────────────────────
> **§1 • Respekt**
> Behandle alle Mitglieder respektvoll.
> Beleidigungen, Mobbing, Diskriminierung,
> Hass und Provokationen sind verboten.

> **§2 • Chat**
> Spam, Flood, Capslock und sinnlose
> Nachrichten sind nicht erlaubt.
```

| Länge | Vorlagen |
|---|---|
| **Kurz** (5–6 §) | Minimal, Freundeskreis, Kurz & Streng, Gaming kompakt, Voice-Knigge, Lerngruppe, Kreativ |
| **Mittel** (9–16 §) | Standard, Community, Gaming ausführlich, **RP · OOC**, **RP · IC**, Creator, Support, Business, Anime, Social, Esports |
| **Ausführlich** (16–29 §) | Serverordnung, Rechtlich abgesichert, Großer Server, **RP · komplett** |

**Rollenspiel getrennt nach IC und OOC.** Ein RP-Projekt braucht zwei
Regelwerke, weil Discord und Spiel unterschiedlichen Regeln folgen:

- **OOC · Discord** (14 §) — Respekt, Werbung, Datenschutz, Tickets, und der
  Grundsatz, dass Spielkonflikte nicht auf Discord weitergeführt werden
- **IC · Ingame** (16 §) — FailRP, FearRP, RDM, VDM, Combat Logging,
  New Life Rule, Powergaming, Metagaming, Safezones, Cop-Baiting
- **komplett** (29 §) — beides in einem Dokument

Danach dieselben Optionen wie bei den Templates, plus eine vierte:

- **Ergänzen** — Regelwerk anhängen, nichts wird gelöscht
- **Neu aufsetzen** — leert **nur diesen Kanal**, und darin ausschließlich
  Nachrichten des Bots; Beiträge von Mitgliedern bleiben unangetastet
- **Abbrechen** — nichts passiert
- **Eigenes Regelwerk** — Formular mit Überschrift, Text und zwei Bildern

Beim eigenen Regelwerk sitzt das erste Bild als Thumbnail **oben rechts**
neben der Überschrift, das zweite als Banner **unter dem Text**:

```
## Serverregeln                          ┌────────┐
──────────────────────────────────────   │  Logo  │
> 1. Sei freundlich                      └────────┘
> 2. Kein Spam
──────────────────────────────────────
[         Banner unten, volle Breite         ]
```

Lange Regelwerke werden automatisch auf zwei Nachrichten verteilt — immer am
Paragraphenrand, nie mitten in einer Regel. Die Nummerierung läuft dabei
durch: §17 bleibt §17, auch auf der zweiten Nachricht.

### 6 · Automatische Einrichtung über einen Partner-Bot

Ein Partner (*University Bot*) kann Server direkt an diesen Bot übergeben.
Kommt ein Server auf diesem Weg, richtet er sich **von selbst** ein — ohne
dass jemand einen Befehl tippt. Ein normaler Beitritt bleibt unverändert.

Der Partner hängt an den Einladungslink einen signierten `state`-Wert.
Discord reicht ihn an unsere Redirect-URI weiter — **nicht** an
`on_guild_join`, deshalb hat der Bot einen `/oauth/callback`-Endpunkt.

Der Token wird in dieser Reihenfolge geprüft:

1. Form: genau ein Punkt, beide Teile nicht leer
2. Signatur per `hmac.compare_digest` — **niemals** mit `==`, sonst ließe
   sich die richtige Signatur über Laufzeitunterschiede Zeichen für Zeichen
   erraten
3. erst danach JSON dekodieren
4. `src == "university-bot"`
5. Alter: `t > 0` und höchstens eine Stunde alt

Scheitert ein Schritt, wird der Token verworfen und der Server als ganz
normaler Beitritt behandelt. **Ohne `PARTNER_HANDSHAKE_SECRET` gilt kein
Token** — lieber keine Automatik als eine manipulierbare. Ohne Signatur
könnte sonst jeder `?state=university-bot` an seinen eigenen Link hängen.

Zusätzlich wird geprüft, ob die von Discord gemeldete `guild_id` zu der im
Token passt. Sonst ließe sich ein echtes Token an eine fremde Einladung
kleben.

**Das Wettrennen.** Der Callback kann vor *oder* nach `on_guild_join`
eintreffen — beides kommt vor. Kommt der Join zuerst, sieht er zweimal im
Abstand von zwei Sekunden erneut nach. Kommt der Callback zuerst und der Bot
ist schon auf dem Server, zieht der Endpunkt die Einrichtung nach.

**Kein zweites Mal.** Erfolgreiche Einrichtungen stehen in
`data/setup_ledger.json`. Wird der Bot entfernt und neu hinzugefügt, baut er
nicht alles erneut auf. Der Vermerk entsteht **erst nach dem Erfolg** —
bricht der Aufbau ab, ist ein zweiter Versuch nicht blockiert. Bewusst
wiederholen lässt es sich mit `!partner-setup`.

Vor dem Aufbau prüft der Bot Rechte (`manage_channels`, `manage_roles`) und
beide Discord-Limits (**500 Kanäle**, **250 Rollen**) — und meldet ein
Problem verständlich, statt mitten im Aufbau abzubrechen.

### 7 · Berechtigungen, die halten

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
2. Unter **Variables**: `DISCORD_TOKEN` und `ENABLE_PRIVILEGED_INTENTS=true`.
   Für die Partner-Automatik zusätzlich `PARTNER_HANDSHAKE_SECRET`,
   `OAUTH_REDIRECT_URI`, `DISCORD_CLIENT_ID` und `DISCORD_CLIENT_SECRET`
3. Unter **Settings → Volumes**: **Add Volume**, Mount path `/app/data`

> Ohne Volume gehen die Premium-Freischaltungen **und** das Register bereits
> eingerichteter Server bei jedem Redeploy verloren. Letzteres hätte zur
> Folge, dass ein Partner-Server nach einem Deploy erneut aufgebaut wird.

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

Der Key wird über `PREMIUM_KEY` gesetzt. Es gibt **keinen Standardwert**: ohne
gesetzte Variable lässt sich Premium schlicht nicht freischalten, und der Bot
weist beim Start darauf hin. Ein im Quelltext hinterlegter Key wäre keiner —
er stünde in jedem Klon dieses Repositories.

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(24))"
```

Der Key wird **nie gespeichert**. Abgelegt wird nur das Paar aus Server- und
Benutzer-ID, und der Vergleich läuft über `hmac.compare_digest`, damit die
Antwortzeit nichts über den Key verrät. Mit `PREMIUM_UNLOCKS_GUILD=true` gilt
eine Freischaltung für den ganzen Server statt nur für den Einlöser.

Der Key erscheint außerdem **nirgends in der Oberfläche**. Das Eingabefeld
zeigt nur „Key hier eingeben" — ein Platzhalter mit Beispiel-Key wäre für
jeden lesbar, der den Button anklickt, und würde Premium wertlos machen. Vier
Tests halten das fest, unter anderem ein Abgleich des gesamten UI-Quelltexts
gegen den konfigurierten Key und eine Prüfung, dass `config.py` keinen
einsatzbereiten Standard-Key mitliefert.

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
web.py                  Health-Endpunkt + OAuth-Callback

core/
  small_caps.py         Typografie + Namensvergleich
  handshake.py          Signierte Partner-Token prüfen
  handoff_store.py      Vormerkungen + Register bereits eingerichteter Server
  autosetup.py          Automatische Einrichtung nach einem Handoff
  rulesets.py           Die 22 Regelwerke (inkl. RP · IC/OOC)
  content.py            Texte der Startnachrichten
  enforcement.py        Durchsetzung der Kanal-Modi
  schema.py             Typisiertes Template-Modell mit Validierung
  permissions.py        Rollenstufen und Sichtbarkeitsregeln
  registry.py           Lädt und indexiert templates/*.json
  premium.py            Key-Prüfung und atomarer Unlock-Speicher
  builder.py            Die Engine: erstellt Rollen, Kategorien, Kanäle

ui/
  components.py         Components-V2-Bausteine
  views.py              Startmenü, Premium-Modal, Vorschau, Fortschritt
  widgets.py            Verify, Regeln, Rollen, Ticket, Checkliste
  channel_intro.py      Die angeheftete Startnachricht
  rules.py              Regelwerk-Assistent und Baukasten

templates/*.json        Die 10 Vorlagen — reine Daten
tools/
  generate_templates.py Erzeugt die JSONs aus gemeinsamen Bausteinen
  enrich_content.py     Weist Modi, Widgets und Reaktionen regelbasiert zu
  preview.py            Templates im Terminal ansehen
tests/                  Testsuite (siehe unten)
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

pytest                              # gesamte Testsuite
pytest --cov=core --cov=ui          # mit Abdeckungsbericht
ruff check .                        # Linting
mypy .                              # Typprüfung

python tools/preview.py             # Übersicht aller Templates
python tools/preview.py rp          # Kanalbaum einer Vorlage
python tools/generate_templates.py  # JSONs neu erzeugen
```

Alle vier Prüfungen laufen bei jedem Push automatisch
([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) — zusätzlich wird dort
das Docker-Image gebaut und geprüft, dass der Container nicht als `root` läuft
und ohne Token mit einer verständlichen Meldung abbricht.

Konfiguration für Ruff, Mypy und Pytest steht gesammelt in `pyproject.toml`.

### Abhängigkeiten

`requirements.txt` nennt Bereiche und ist die Quelle für die Entwicklung.
Deployt wird aus `requirements.lock` — voll gepinnt, mit Hashes, für Python
3.12 und 3.13 gültig:

```bash
uv pip compile requirements.txt --generate-hashes --universal \
    -o requirements.lock
```

Ohne Lockfile kann ein Patch-Release einer Abhängigkeit das Verhalten des Bots
ändern, ohne dass ein einziger Commit stattgefunden hat. Das Image installiert
mit `--require-hashes`, sodass auch ein ausgetauschtes PyPI-Archiv auffällt.
Nach jeder Änderung an `requirements.txt` das Lockfile neu erzeugen —
`tests/test_dependencies.py` prüft, dass beide zusammenpassen.

Die Testsuite prüft unter anderem:

- **Components V2** — jede View wird zu echtem API-Payload serialisiert und
  gegen Discords Limits geprüft (40 Komponenten, 4.000 Zeichen, 25 Select-Optionen)
- **Bau-Simulation** — alle 10 Templates werden gegen ein nachgebildetes Guild
  gebaut; geprüft werden Idempotenz, Wipe-Verhalten und dass private
  Kategorien für `@everyone` unsichtbar sind
- **Berechtigungen** — dass jede Stufe eine Obermenge der vorherigen ist und
  nur der Inhaber `Administrator` bekommt
- **Partner-Handshake** — dass gefälschte Signaturen, vertauschte Bodies,
  fremde `src`-Werte und abgelaufene Token abgelehnt werden, dass ohne Secret
  **jedes** Token scheitert, und dass beide Reihenfolgen des Wettrennens den
  Server genau einmal einrichten
- **Deployment** — dass kein `VOLUME` im Dockerfile steht (Railway bricht sonst
  den Build ab) und jeder `COPY`-Pfad die `.dockerignore` überlebt
- **Premium** — dass der Key nie auf der Festplatte landet, **nirgends in der
  Oberfläche auftaucht** und eine Freischaltung nicht auf andere Nutzer oder
  Server überspringt
- **Layout** — dass Blockzitate genutzt werden, keine H1-Überschriften und
  keine Emoji-Häufung vorkommen, und dass eine Zitatzeile nicht versehentlich
  als Markdown-Überschrift gerendert wird
- **Kanalinhalte** — dass ein zweiter Durchlauf keine doppelten Nachrichten
  erzeugt, Sprachkanäle leer bleiben, das Team nie von der Löschregel
  getroffen wird und die Widget-Buttons einen Neustart überstehen
- **Widget-Klicks** — dass der Verify-Button die Rolle wirklich vergibt und die
  Eingangssperre entfernt, dass eine fehlende oder zu hoch stehende Rolle
  erklärt statt verschluckt wird, und dass der Nutzer in **jedem** Fehlerfall
  eine Rückmeldung bekommt
- **Bau-Wächter** — dass ohne `Server verwalten` nichts angefasst wird, zwei
  Läufe sich nicht überschneiden und die Sperre nach jedem Abbruch wieder
  freigegeben wird (sonst bliebe der Server bis zum Neustart blockiert)
- **Rate-Limits** — dass ein 429 wiederholt wird, Discords `Retry-After` dabei
  Vorrang hat und ein `403` **nicht** wiederholt wird
- **Generator-Synchronität** — dass `tools/generate_templates.py` exakt die
  eingecheckten JSONs erzeugt. Ohne diese Prüfung geht eine Handänderung am
  JSON beim nächsten Generator-Lauf still verloren
- **Deployment-Härtung** — dass der Container einen eigenen Benutzer hat, einen
  `HEALTHCHECK` mitbringt und `/app/data` dem Laufzeitbenutzer gehört
- **Abhängigkeiten** — dass jedes Paket im Lockfile gepinnt ist und Hashes
  trägt, keine gepinnte Version die Bereiche aus `requirements.txt` verletzt
  und das Dockerfile wirklich mit `--require-hashes` daraus installiert
- **CI-Konfiguration** — dass Ruff, Mypy, Pytest und die Lockfile-Prüfung
  tatsächlich in der Pipeline stehen. Ein Workflow, aus dem still eine Prüfung
  verschwindet, meldet sonst weiter grün
- **Persistenz** — dass ein Absturz mitten im Schreiben keine Freischaltungen
  vernichtet, eine unlesbare Datei den Start nicht verhindert und der
  Premium-Key nie im Dateisystem landet
- **Startverhalten** — dass eine fehlerhafte Vorlage den Bot beim Start
  abbricht und die Meldung die betroffene Datei nennt, statt mitten im Umbau
  eines fremden Servers aufzufallen
- **Regelwerke** — dass alle 22 vollständig gerendert werden ohne einen
  Paragraphen zu verlieren, die Nummerierung lückenlos durchläuft, kein
  Paragraph beim Aufteilen zerrissen wird, das IC-Regelwerk die klassischen
  RP-Begriffe abdeckt und „Neu aufsetzen" nur Bot-Nachrichten entfernt

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

MIT — siehe [LICENSE](LICENSE) · erstellt von **Vexo × Fufi**
