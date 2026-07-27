"""Zwanzig fertige Regelwerke.

Nach dem Bau eines Templates bietet der Bot an, den Regelkanal zu fuellen.
Die Auswahl deckt bewusst sehr unterschiedliche Laengen ab: von vier Zeilen
fuer einen kleinen Freundeskreis bis zu einem ausformulierten Regelwerk mit
Paragraphen fuer grosse oeffentliche Server.

Alle Regeln werden als Blockzitat gerendert (``>``), damit sie im Kanal als
ruhige, eingerueckte Spalte stehen statt als Textwand.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

__all__ = ["RuleLength", "RuleSet", "RULESETS", "get_ruleset", "by_length"]


class RuleLength(str, Enum):
    """Grobe Groessenordnung — steuert nur die Anzeige in der Auswahl."""

    SHORT = "kurz"
    MEDIUM = "mittel"
    LONG = "lang"

    @property
    def label(self) -> str:
        return {"kurz": "Kurz", "mittel": "Mittel", "lang": "Ausführlich"}[self.value]


@dataclass(frozen=True, slots=True)
class RuleSection:
    """Ein Abschnitt mit Ueberschrift und Punkten."""

    heading: str
    items: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RuleSet:
    key: str
    name: str
    emoji: str
    tagline: str
    length: RuleLength
    intro: str = ""
    sections: tuple[RuleSection, ...] = ()
    closing: str = ""

    @property
    def rule_count(self) -> int:
        return sum(len(section.items) for section in self.sections)

    @property
    def char_count(self) -> int:
        total = len(self.intro) + len(self.closing)
        for section in self.sections:
            total += len(section.heading) + sum(len(item) for item in section.items)
        return total


def _s(heading: str, *items: str) -> RuleSection:
    return RuleSection(heading=heading, items=items)


# --------------------------------------------------------------------------- #
# Die Regelwerke
# --------------------------------------------------------------------------- #

RULESETS: tuple[RuleSet, ...] = (
    # ---------------------------------------------------------------- kurz --
    RuleSet(
        key="minimal",
        name="Minimal",
        emoji="🌱",
        tagline="Vier Sätze, mehr braucht ein kleiner Server nicht",
        length=RuleLength.SHORT,
        sections=(
            _s(
                "Regeln",
                "Sei freundlich.",
                "Kein Spam, keine Werbung.",
                "Halte dich an die Discord-Richtlinien.",
                "Was das Team sagt, gilt.",
            ),
        ),
    ),
    RuleSet(
        key="freundeskreis",
        name="Freundeskreis",
        emoji="🫶",
        tagline="Locker formuliert für private Server",
        length=RuleLength.SHORT,
        intro="Wir sind hier unter Freunden — trotzdem ein paar Grundsätze.",
        sections=(
            _s(
                "Miteinander",
                "Behandelt euch so, wie ihr behandelt werden wollt.",
                "Streit wird geklärt, nicht ausgetragen.",
                "Was hier gesagt wird, bleibt hier.",
            ),
            _s(
                "Praktisches",
                "Nutzt die Kanäle, für die sie gedacht sind.",
                "Keine fremden Leute ohne Absprache einladen.",
            ),
        ),
    ),
    RuleSet(
        key="kurz_streng",
        name="Kurz & Streng",
        emoji="⚖️",
        tagline="Wenige Regeln, klare Konsequenzen",
        length=RuleLength.SHORT,
        sections=(
            _s(
                "Verboten",
                "Beleidigungen, Rassismus, Sexismus, Hetze.",
                "NSFW-Inhalte außerhalb dafür vorgesehener Kanäle.",
                "Werbung ohne Erlaubnis.",
                "Spam, Massenpings, Raid-Versuche.",
            ),
            _s(
                "Konsequenz",
                "Erster Verstoß: Verwarnung.",
                "Zweiter Verstoß: Timeout.",
                "Dritter Verstoß: Bann.",
            ),
        ),
        closing="Bei schweren Verstößen entfällt die Abstufung.",
    ),
    RuleSet(
        key="gaming_kurz",
        name="Gaming kompakt",
        emoji="🎮",
        tagline="Das Nötigste für Gaming-Communities",
        length=RuleLength.SHORT,
        sections=(
            _s(
                "Im Chat",
                "Kein Flame, kein Toxic-Verhalten.",
                "Keine Cheats, keine Exploits, keine Accounts zum Verkauf.",
                "Spoiler markieren.",
            ),
            _s(
                "Im Voice",
                "Kein Ohrenschmerz: Mikro einstellen, Hintergrundlärm vermeiden.",
                "Nicht ungefragt Musik einspielen.",
                "Wer stört, wird verschoben.",
            ),
        ),
    ),
    RuleSet(
        key="voice_fokus",
        name="Voice-Knigge",
        emoji="🎙️",
        tagline="Für Server, die vor allem gesprochen werden",
        length=RuleLength.SHORT,
        intro="Diese Regeln gelten in allen Sprachkanälen.",
        sections=(
            _s(
                "Technik",
                "Push-to-Talk bei lauter Umgebung.",
                "Keine Störgeräusche, kein Tastaturlärm ins offene Mikro.",
                "Musik nur im dafür vorgesehenen Kanal.",
            ),
            _s(
                "Umgang",
                "Lasst einander ausreden.",
                "Keine Aufnahmen ohne Zustimmung aller Beteiligten.",
                "Wer gehen will, geht — ohne Erklärung.",
            ),
        ),
    ),
    RuleSet(
        key="lernserver",
        name="Lerngruppe",
        emoji="📚",
        tagline="Ruhe, Fairness und Urheberrecht",
        length=RuleLength.SHORT,
        intro="Hier wird gearbeitet — darauf beruhen diese Regeln.",
        sections=(
            _s(
                "Arbeitsklima",
                "In Lernräumen ist Stille die Grundeinstellung.",
                "Fragen gehören in den passenden Fachkanal.",
                "Keine Lösungen abschreiben lassen — erklären statt liefern.",
            ),
            _s(
                "Material",
                "Nur teilen, was geteilt werden darf.",
                "Quellen angeben.",
                "Keine kostenpflichtigen Skripte hochladen.",
            ),
        ),
    ),
    RuleSet(
        key="kreativ",
        name="Kreativ-Community",
        emoji="🎨",
        tagline="Feedback, Urheberrecht und Aufträge",
        length=RuleLength.SHORT,
        sections=(
            _s(
                "Deine Werke",
                "Nur eigene Arbeiten posten.",
                "Bei Vorlagen und Referenzen die Quelle nennen.",
                "KI-generiertes klar kennzeichnen.",
            ),
            _s(
                "Feedback",
                "Kritik bezieht sich auf das Werk, nie auf die Person.",
                "Wer Feedback gibt, sagt auch, was funktioniert.",
                "Ungefragte Verrisse sind keine Kritik.",
            ),
            _s(
                "Aufträge",
                "Preise und Bedingungen vorher klären.",
                "Der Server haftet nicht für Absprachen zwischen Mitgliedern.",
            ),
        ),
    ),
    # -------------------------------------------------------------- mittel --
    RuleSet(
        key="standard",
        name="Standard",
        emoji="📋",
        tagline="Der ausgewogene Allrounder für die meisten Server",
        length=RuleLength.MEDIUM,
        intro=(
            "Mit dem Betreten dieses Servers erklärst du dich mit diesen Regeln "
            "einverstanden."
        ),
        sections=(
            _s(
                "Respekt",
                "Beleidigungen, Diskriminierung und persönliche Angriffe sind verboten.",
                "Diskutiert Meinungen, nicht Menschen.",
                "Provokation und bewusstes Stänkern werden wie ein Verstoß behandelt.",
            ),
            _s(
                "Inhalte",
                "Keine NSFW-, Gewalt- oder Schockinhalte.",
                "Keine illegalen Inhalte, keine Raubkopien.",
                "Keine Weitergabe privater Daten — weder eigener noch fremder.",
            ),
            _s(
                "Chat",
                "Nutze den Kanal, der zum Thema passt.",
                "Kein Spam, keine Massenpings, keine Kettennachrichten.",
                "Werbung nur mit ausdrücklicher Erlaubnis des Teams.",
            ),
            _s(
                "Sprachkanäle",
                "Kein Störgeräusch, kein Soundboard-Missbrauch.",
                "Aufnahmen nur mit Zustimmung aller Beteiligten.",
            ),
            _s(
                "Team",
                "Anweisungen des Teams ist Folge zu leisten.",
                "Beschwerden gehören ins Ticket, nicht in den Chat.",
            ),
        ),
        closing=(
            "Das Team behält sich vor, bei Verstößen zu verwarnen, stummzuschalten "
            "oder auszuschließen."
        ),
    ),
    RuleSet(
        key="community",
        name="Community",
        emoji="🌐",
        tagline="Für wachsende öffentliche Server",
        length=RuleLength.MEDIUM,
        intro="Damit sich hier alle wohlfühlen, gelten folgende Regeln.",
        sections=(
            _s(
                "Grundsätze",
                "Respektvoller Umgang ist Pflicht, keine Höflichkeitsfloskel.",
                "Keine Diskriminierung wegen Herkunft, Geschlecht, Religion, Orientierung oder Behinderung.",
                "Kein Mobbing, kein Bloßstellen, kein Nachtreten.",
            ),
            _s(
                "Beiträge",
                "Halte dich an das Thema des jeweiligen Kanals.",
                "Keine Werbung, keine Selbstpromo außerhalb des dafür gedachten Kanals.",
                "Keine Kettenbriefe, Gewinnspiel-Scams oder dubiosen Links.",
                "Bilder und Videos müssen jugendfrei sein.",
            ),
            _s(
                "Identität",
                "Ein Account pro Person. Zweitaccounts zur Umgehung von Strafen führen zum Bann.",
                "Name und Profilbild müssen angemessen sein.",
                "Kein Ausgeben als Teammitglied oder andere Person.",
            ),
            _s(
                "Datenschutz",
                "Keine fremden Daten ohne Einwilligung.",
                "Screenshots privater Gespräche nur mit Zustimmung.",
                "Der Server ist kein Ort für persönliche Dokumente.",
            ),
            _s(
                "Bei Problemen",
                "Melde Verstöße über ein Ticket statt sie öffentlich zu diskutieren.",
                "Bei Streit: erst zurücktreten, dann das Team einschalten.",
            ),
        ),
        closing="Unwissenheit schützt nicht vor Konsequenzen.",
    ),
    RuleSet(
        key="gaming_voll",
        name="Gaming ausführlich",
        emoji="🕹️",
        tagline="Mit Fairplay, Turnieren und Voice-Regeln",
        length=RuleLength.MEDIUM,
        intro="Diese Regeln gelten im gesamten Server und in allen Spielrunden.",
        sections=(
            _s(
                "Fairplay",
                "Keine Cheats, Hacks, Exploits oder Drittanbieter-Software.",
                "Kein Smurfing in Ranked-Runden der Community.",
                "Kein absichtliches Verlieren, kein Griefing, kein AFK-Gehen.",
                "Ergebnisse werden nicht abgesprochen.",
            ),
            _s(
                "Kommunikation",
                "Kein Flame, kein Blaming nach einer Niederlage.",
                "Kritik im Spiel bleibt sachlich und kurz.",
                "Toxisches Verhalten wird auch dann geahndet, wenn es außerhalb des Servers stattfand.",
            ),
            _s(
                "Sprachkanäle",
                "Wer im Team spielt, hört auf Ansagen.",
                "Kein Soundboard-Spam während laufender Runden.",
                "Kein Kanal-Hopping.",
            ),
            _s(
                "Turniere",
                "Anmeldung ist verbindlich.",
                "Wer nicht antritt, wird beim nächsten Turnier nachrangig behandelt.",
                "Entscheidungen der Turnierleitung sind endgültig.",
            ),
            _s(
                "Handel",
                "Kein Verkauf von Accounts, Keys oder Ingame-Währung.",
                "Tauschgeschäfte zwischen Mitgliedern sind Privatsache.",
            ),
        ),
    ),
    RuleSet(
        key="roleplay",
        name="Roleplay",
        emoji="🎭",
        tagline="IC/OOC-Trennung, Metagaming und Charaktertod",
        length=RuleLength.MEDIUM,
        intro=(
            "Rollenspiel lebt von gemeinsamen Regeln. Wer sie bricht, zerstört "
            "die Szene für alle anderen."
        ),
        sections=(
            _s(
                "Grundbegriffe",
                "IC bedeutet In Character — dein Charakter handelt.",
                "OOC bedeutet Out of Character — du als Spieler sprichst.",
                "Beides wird strikt getrennt.",
            ),
            _s(
                "Verbotene Spielweisen",
                "Metagaming: OOC-Wissen im Rollenspiel verwenden.",
                "Powergaming: Handlungen erzwingen, ohne dem Gegenüber eine Reaktion zu lassen.",
                "Random Deathmatch: Gewalt ohne nachvollziehbaren Grund.",
                "Combat Logging: Ausloggen während einer laufenden Szene.",
            ),
            _s(
                "Charaktere",
                "Ein Charakter braucht eine glaubwürdige Geschichte.",
                "Kein Charakter ist unbesiegbar oder allwissend.",
                "Charaktertod ist endgültig, wenn er fair herbeigeführt wurde.",
            ),
            _s(
                "Szenen",
                "Wer eine Szene beginnt, gibt anderen Raum zu reagieren.",
                "Bei Unstimmigkeiten wird die Szene pausiert, nicht eskaliert.",
                "Konflikte werden OOC im Support geklärt.",
            ),
            _s(
                "Fraktionen",
                "Absprachen zwischen Fraktionen sind IC bindend.",
                "Kein Fraktionswechsel zur Umgehung von Konsequenzen.",
            ),
        ),
        closing="Im Zweifel entscheidet die Rollenspielleitung.",
    ),
    RuleSet(
        key="creator",
        name="Creator & Community",
        emoji="🎬",
        tagline="Für Kanäle mit Publikum",
        length=RuleLength.MEDIUM,
        intro="Dieser Server gehört zur Community rund um den Kanal.",
        sections=(
            _s(
                "Umgang",
                "Respekt gilt gegenüber allen — auch gegenüber Kritikern.",
                "Keine Drama-Threads über andere Creator.",
                "Keine Diskussion über Moderationsentscheidungen im öffentlichen Chat.",
            ),
            _s(
                "Inhalte",
                "Keine Leaks unveröffentlichter Inhalte.",
                "Spoiler zu neuen Videos gehören in den Spoiler-Kanal.",
                "Clips und Ausschnitte dürfen geteilt werden, mit Quellenangabe.",
            ),
            _s(
                "Selbstpromo",
                "Eigene Projekte nur im Promo-Kanal.",
                "Kein Abo-Betteln, keine Follow-for-Follow-Angebote.",
                "Keine Direktnachrichten mit Werbung an Mitglieder.",
            ),
            _s(
                "Kontakt",
                "Geschäftliches läuft über die angegebene Adresse, nicht per DM.",
                "Das Team antwortet nicht auf Privatanfragen zu Videos.",
            ),
        ),
    ),
    RuleSet(
        key="support",
        name="Support-Server",
        emoji="🛟",
        tagline="Tickets, Reaktionszeiten und Umgangston",
        length=RuleLength.MEDIUM,
        intro="Damit dir schnell geholfen werden kann, beachte bitte Folgendes.",
        sections=(
            _s(
                "Bevor du fragst",
                "Sieh in die häufigen Fragen und die Anleitungen.",
                "Prüfe, ob dein Problem bereits bekannt ist.",
            ),
            _s(
                "Ein gutes Ticket",
                "Beschreibe das Problem in ganzen Sätzen.",
                "Nenne, was du bereits versucht hast.",
                "Füge Screenshots oder Fehlermeldungen bei.",
                "Ein Ticket pro Anliegen.",
            ),
            _s(
                "Umgangston",
                "Das Team hilft freiwillig — Druck beschleunigt nichts.",
                "Kein Anschreiben einzelner Teammitglieder per DM.",
                "Kein Nachfassen im Minutentakt.",
            ),
            _s(
                "Nach der Lösung",
                "Bestätige kurz, wenn dein Problem gelöst ist.",
                "Geschlossene Tickets werden archiviert, nicht gelöscht.",
            ),
        ),
    ),
    RuleSet(
        key="business",
        name="Business",
        emoji="🏢",
        tagline="Für Firmen- und Projektserver",
        length=RuleLength.MEDIUM,
        intro="Dieser Server ist ein Arbeitsmittel. Es gelten die Regeln des Hauses.",
        sections=(
            _s(
                "Vertraulichkeit",
                "Interne Informationen verlassen den Server nicht.",
                "Kundendaten werden ausschließlich in den dafür vorgesehenen Kanälen behandelt.",
                "Screenshots interner Kanäle sind untersagt.",
            ),
            _s(
                "Kommunikation",
                "Sachlich, knapp und nachvollziehbar.",
                "Entscheidungen gehören dokumentiert in den Projektkanal.",
                "Dringendes per Ping, alles andere ohne.",
            ),
            _s(
                "Erreichbarkeit",
                "Antworten werden innerhalb der Arbeitszeiten erwartet.",
                "Außerhalb der Arbeitszeit besteht keine Antwortpflicht.",
                "Abwesenheiten gehören in den Kalender.",
            ),
            _s(
                "Zugänge",
                "Zugangsdaten werden niemals im Chat geteilt.",
                "Externe erhalten nur Zugriff auf den Kundenbereich.",
            ),
        ),
    ),
    RuleSet(
        key="anime",
        name="Anime & Manga",
        emoji="🌸",
        tagline="Spoiler, Fanart und Quellen",
        length=RuleLength.MEDIUM,
        sections=(
            _s(
                "Spoiler",
                "Alles, was nicht offiziell erschienen ist, gilt als Spoiler.",
                "Spoiler gehören in den Spoiler-Kanal oder hinter Spoilertags.",
                "Auch Titel und Thumbnails können spoilern.",
            ),
            _s(
                "Fanart",
                "Nur eigene Werke oder solche mit Quellenangabe.",
                "Reposts ohne Erlaubnis der Urheber sind untersagt.",
                "KI-Bilder klar kennzeichnen.",
            ),
            _s(
                "Inhalte",
                "Keine NSFW-Inhalte, auch nicht als Zeichnung.",
                "Keine Links zu illegalen Streaming- oder Scanseiten.",
            ),
            _s(
                "Diskussion",
                "Geschmack ist keine Verhandlungssache.",
                "Keine Fandom-Kriege, kein Herabsetzen anderer Serien.",
            ),
        ),
    ),
    RuleSet(
        key="social",
        name="Social & Lounge",
        emoji="☕",
        tagline="Für Server, auf denen vor allem geredet wird",
        length=RuleLength.MEDIUM,
        intro="Hier geht es ums Reden. Damit das angenehm bleibt:",
        sections=(
            _s(
                "Gespräche",
                "Lasst einander ausreden, auch im Text.",
                "Kein Ausfragen, wenn jemand nicht antworten möchte.",
                "Themen, die belasten, gehören in den dafür vorgesehenen Kanal.",
            ),
            _s(
                "Grenzen",
                "Ein Nein ist ein Nein — beim Thema wie beim Kontakt.",
                "Keine ungefragten Privatnachrichten mit Anmachen.",
                "Kein Weitergeben privater Gespräche.",
            ),
            _s(
                "Ernste Themen",
                "Der Server ersetzt keine Therapie und keinen Notruf.",
                "Bei akuter Not: wende dich an professionelle Hilfe.",
                "Das Team vermittelt Anlaufstellen, wenn du fragst.",
            ),
            _s(
                "Alltag",
                "Kein Dauerspam, keine Massenpings.",
                "Musik nur im Musikkanal.",
            ),
        ),
    ),
    RuleSet(
        key="esports",
        name="Esports-Organisation",
        emoji="🏆",
        tagline="Kader, Auftreten und Vertraulichkeit",
        length=RuleLength.MEDIUM,
        intro="Wer diese Organisation vertritt, vertritt sie auch außerhalb des Servers.",
        sections=(
            _s(
                "Auftreten",
                "Kein toxisches Verhalten in Spielen, Streams oder sozialen Medien.",
                "Keine öffentliche Kritik an Mitspielern oder Gegnern.",
                "Sponsoren werden nicht negativ erwähnt.",
            ),
            _s(
                "Verpflichtungen",
                "Trainingszeiten sind verbindlich.",
                "Absagen rechtzeitig und mit Grund.",
                "Matchtermine haben Vorrang vor privaten Spielrunden.",
            ),
            _s(
                "Vertraulichkeit",
                "Strategien, Aufstellungen und interne Absprachen bleiben intern.",
                "Keine Weitergabe von Analysen an Dritte.",
                "Presseanfragen laufen über die Organisation.",
            ),
            _s(
                "Kader",
                "Wechsel werden mit der Leitung besprochen.",
                "Doppelmitgliedschaften in konkurrierenden Teams sind ausgeschlossen.",
            ),
        ),
    ),
    # ----------------------------------------------------------------- lang --
    RuleSet(
        key="ausfuehrlich",
        name="Ausführlich",
        emoji="📖",
        tagline="Vollständiges Regelwerk mit Paragraphen",
        length=RuleLength.LONG,
        intro=(
            "Dieses Regelwerk gilt für alle Mitglieder. Mit dem Verbleib auf dem "
            "Server erkennst du es an. Ergänzend gelten die Discord-Nutzungs"
            "bedingungen und die Community-Richtlinien."
        ),
        sections=(
            _s(
                "§1 Umgangston",
                "Begegne allen Mitgliedern mit Respekt.",
                "Beleidigungen, Bedrohungen und Herabwürdigungen sind untersagt.",
                "Diskriminierung wegen Herkunft, Hautfarbe, Geschlecht, Orientierung, Religion, Alter oder Behinderung führt zum sofortigen Ausschluss.",
                "Ironie und Sarkasmus entschuldigen keinen verletzenden Inhalt.",
            ),
            _s(
                "§2 Inhalte",
                "Keine pornografischen, gewaltverherrlichenden oder verstörenden Inhalte.",
                "Keine extremistischen Symbole, Parolen oder Verharmlosungen.",
                "Keine urheberrechtlich geschützten Werke ohne Berechtigung.",
                "Keine Links zu Schadsoftware, Phishing oder illegalen Angeboten.",
            ),
            _s(
                "§3 Chatverhalten",
                "Schreibe im thematisch passenden Kanal.",
                "Kein Spam, keine Buchstabenketten, keine Wiederholungen.",
                "Massenpings und @everyone sind dem Team vorbehalten.",
                "Kein Missbrauch von Threads, Reaktionen oder Umfragen.",
            ),
            _s(
                "§4 Sprachkanäle",
                "Störgeräusche, Rückkopplungen und Soundboard-Spam sind zu unterlassen.",
                "Kein wiederholtes Betreten und Verlassen von Kanälen.",
                "Aufnahmen und Streams nur mit Zustimmung aller Beteiligten.",
                "Anweisungen zur Kanalnutzung sind zu befolgen.",
            ),
            _s(
                "§5 Werbung",
                "Werbung für andere Server, Kanäle oder Produkte ist genehmigungspflichtig.",
                "Auch Werbung per Direktnachricht an Mitglieder ist untersagt.",
                "Partnerschaften werden ausschließlich über das Team vereinbart.",
            ),
            _s(
                "§6 Accounts und Identität",
                "Pro Person ist ein Account zulässig.",
                "Zweitaccounts zur Umgehung von Sanktionen führen zum dauerhaften Ausschluss.",
                "Benutzernamen und Profilbilder müssen den Regeln entsprechen.",
                "Das Vortäuschen einer fremden Identität ist verboten.",
            ),
            _s(
                "§7 Datenschutz",
                "Persönliche Daten Dritter dürfen nicht veröffentlicht werden.",
                "Screenshots privater Konversationen bedürfen der Zustimmung.",
                "Das Team gibt keine Mitgliederdaten an Dritte weiter.",
            ),
            _s(
                "§8 Team und Sanktionen",
                "Anweisungen des Teams ist Folge zu leisten.",
                "Mögliche Maßnahmen sind Verwarnung, Timeout, Kick und Bann.",
                "Die Wahl der Maßnahme richtet sich nach Schwere und Wiederholung.",
                "Beschwerden über Maßnahmen gehören ins Ticket.",
            ),
            _s(
                "§9 Schlussbestimmungen",
                "Das Team kann diese Regeln jederzeit anpassen.",
                "Änderungen werden im Ankündigungskanal bekanntgegeben.",
                "Regelungslücken werden im Sinne dieser Regeln ausgelegt.",
            ),
        ),
        closing="Stand: bei Anwendung dieser Vorlage. Fragen beantwortet das Team.",
    ),
    RuleSet(
        key="rechtssicher",
        name="Rechtlich abgesichert",
        emoji="⚖️",
        tagline="Mit Jugendschutz, Haftung und Datenverarbeitung",
        length=RuleLength.LONG,
        intro=(
            "Dieses Regelwerk richtet sich an öffentliche Server mit vielen "
            "Mitgliedern und ergänzt die geltenden gesetzlichen Bestimmungen."
        ),
        sections=(
            _s(
                "1 · Geltungsbereich",
                "Diese Regeln gelten für alle Kanäle, Threads und Sprachkanäle.",
                "Sie gelten ebenso für Direktnachrichten zwischen Mitgliedern, soweit sie den Server betreffen.",
                "Mit dem Beitritt werden sie anerkannt.",
            ),
            _s(
                "2 · Mindestalter",
                "Die Nutzung von Discord setzt ein Mindestalter von 13 Jahren voraus.",
                "In einzelnen Ländern gelten höhere Altersgrenzen.",
                "Das Team ist berechtigt, bei Zweifeln den Zugang zu sperren.",
            ),
            _s(
                "3 · Verbotene Inhalte",
                "Inhalte, die gegen geltendes Recht verstoßen, sind untersagt.",
                "Dazu zählen insbesondere Volksverhetzung, Gewaltdarstellung und jugendgefährdende Inhalte.",
                "Verstöße können zur Anzeige gebracht werden.",
            ),
            _s(
                "4 · Urheberrecht",
                "Es dürfen nur Inhalte geteilt werden, an denen die erforderlichen Rechte bestehen.",
                "Bei fremden Werken ist die Quelle zu nennen.",
                "Rechteinhaber können die Entfernung über ein Ticket verlangen.",
            ),
            _s(
                "5 · Datenverarbeitung",
                "Der Server speichert keine personenbezogenen Daten über das hinaus, was Discord bereitstellt.",
                "Moderationsprotokolle dienen ausschließlich der Durchsetzung dieser Regeln.",
                "Auf Anfrage wird Auskunft über gespeicherte Moderationsvermerke erteilt.",
            ),
            _s(
                "6 · Haftung",
                "Für Inhalte, die Mitglieder veröffentlichen, haften diese selbst.",
                "Der Betreiber übernimmt keine Haftung für Absprachen zwischen Mitgliedern.",
                "Verlinkte externe Angebote liegen außerhalb der Verantwortung des Servers.",
            ),
            _s(
                "7 · Sanktionen",
                "Bei Verstößen kommen Verwarnung, Stummschaltung, Ausschluss oder Sperre in Betracht.",
                "Die Maßnahme wird nach Schwere, Vorsatz und Wiederholung gewählt.",
                "Ein Anspruch auf Mitgliedschaft besteht nicht.",
            ),
            _s(
                "8 · Widerspruch",
                "Gegen Maßnahmen kann über ein Ticket Widerspruch eingelegt werden.",
                "Der Widerspruch wird von einer nicht beteiligten Person geprüft.",
                "Die Entscheidung wird begründet mitgeteilt.",
            ),
            _s(
                "9 · Änderungen",
                "Änderungen werden mit einer Frist von sieben Tagen angekündigt.",
                "Wer widerspricht, kann den Server verlassen.",
                "Die fortgesetzte Nutzung gilt als Zustimmung.",
            ),
        ),
        closing=(
            "Dieses Regelwerk ist eine Vorlage und ersetzt keine Rechtsberatung. "
            "Prüfe es vor dem Einsatz auf deinen Anwendungsfall."
        ),
    ),
    RuleSet(
        key="grossserver",
        name="Großer Server",
        emoji="🏙️",
        tagline="Für Server ab mehreren tausend Mitgliedern",
        length=RuleLength.LONG,
        intro=(
            "Je größer eine Community, desto klarer müssen die Regeln sein. "
            "Dieses Regelwerk ist bewusst detailliert."
        ),
        sections=(
            _s(
                "Grundregeln",
                "Respektvoller Umgang ohne Ausnahme.",
                "Keine Diskriminierung in jeglicher Form.",
                "Keine Belästigung, kein Stalking, kein Nachstellen.",
                "Kein Aufruf zu Gewalt oder Selbstschädigung.",
            ),
            _s(
                "Kanalordnung",
                "Jeder Kanal hat ein Thema — es steht in der angehefteten Nachricht.",
                "Bild- und Medienkanäle sind für Medien, nicht für Diskussionen.",
                "Bot-Befehle gehören in den Bot-Kanal.",
                "Off-Topic hat einen eigenen Bereich.",
            ),
            _s(
                "Sprachkanäle",
                "Kein Missbrauch von Stummschaltung oder Verschiebefunktion.",
                "Kein Dauerbelegen leerer Kanäle.",
                "Bei Events gelten die Anweisungen der Moderation.",
            ),
            _s(
                "Werbung und Handel",
                "Werbung ausschließlich im Promo-Kanal und nur einmal pro Woche.",
                "Kein Handel mit Accounts, Währungen oder Dienstleistungen.",
                "Keine Spendenaufrufe ohne Absprache.",
            ),
            _s(
                "Bots und Automatisierung",
                "Selfbots und Automatisierung des eigenen Accounts sind verboten.",
                "Keine Scraper, keine Massen-DMs.",
                "Bot-Missbrauch führt zum Ausschluss.",
            ),
            _s(
                "Moderation",
                "Moderationsentscheidungen werden nicht öffentlich diskutiert.",
                "Wer eine Entscheidung für falsch hält, nutzt den Widerspruchsweg.",
                "Das Ansprechen einzelner Moderatoren per DM ist unerwünscht.",
            ),
            _s(
                "Sanktionsstufen",
                "Stufe 1: Hinweis ohne Vermerk.",
                "Stufe 2: Verwarnung mit Eintrag.",
                "Stufe 3: Timeout zwischen einer Stunde und sieben Tagen.",
                "Stufe 4: Ausschluss mit Rückkehrmöglichkeit.",
                "Stufe 5: dauerhafte Sperre.",
            ),
            _s(
                "Schwerwiegende Verstöße",
                "Bei Doxxing, Raids, Schadsoftware oder Straftaten entfällt die Abstufung.",
                "In diesen Fällen erfolgt die sofortige Sperre.",
            ),
        ),
        closing="Diese Regeln werden regelmäßig überprüft und angepasst.",
    ),
)


_BY_KEY = {ruleset.key: ruleset for ruleset in RULESETS}


def get_ruleset(key: str) -> RuleSet | None:
    return _BY_KEY.get(key)


def by_length(length: RuleLength) -> list[RuleSet]:
    return [ruleset for ruleset in RULESETS if ruleset.length is length]
