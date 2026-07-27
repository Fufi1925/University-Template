"""Die fertigen Regelwerke.

Nach dem Bau eines Templates bietet der Bot an, den Regelkanal zu fuellen.
Die Auswahl deckt bewusst sehr unterschiedliche Laengen ab: von einem
Kurzregelwerk fuer einen Freundeskreis bis zu einer ausformulierten Ordnung
mit ueber zwanzig Paragraphen fuer grosse oeffentliche Server.

Aufbau
------
Jeder Paragraph hat eine **Ueberschrift** und einen **Fliesstext**. Das liest
sich fluessiger als eine Stichpunktliste und entspricht dem, was Discord-Nutzer
von Regelkanaelen kennen:

    §1 • Respekt
    Behandle alle Mitglieder respektvoll. Beleidigungen, Mobbing,
    Diskriminierung und Provokationen sind verboten.

Rollenspiel-Server brauchen zwei getrennte Regelwerke, weil Discord und
Ingame unterschiedlichen Regeln folgen:

* **OOC** (Out of Character) — das Verhalten auf dem Discord-Server
* **IC** (In Character) — das Verhalten im Spiel

Beide gibt es hier einzeln und als kombinierte Fassung.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

__all__ = [
    "RuleLength",
    "RuleScope",
    "Paragraph",
    "RuleSet",
    "RULESETS",
    "get_ruleset",
    "by_length",
    "by_scope",
]


class RuleLength(str, Enum):
    """Grobe Groessenordnung — steuert die Gruppierung in der Auswahl."""

    SHORT = "kurz"
    MEDIUM = "mittel"
    LONG = "lang"

    @property
    def label(self) -> str:
        return {"kurz": "Kurz", "mittel": "Mittel", "lang": "Ausführlich"}[self.value]


class RuleScope(str, Enum):
    """Wofuer das Regelwerk gilt."""

    DISCORD = "discord"  # allgemeiner Discord-Server
    OOC = "ooc"          # Discord-Teil eines Rollenspiel-Projekts
    IC = "ic"            # Ingame-Regeln eines Rollenspiel-Projekts
    BOTH = "both"        # OOC und IC in einem Regelwerk

    @property
    def label(self) -> str:
        return {
            "discord": "Discord",
            "ooc": "OOC · Discord",
            "ic": "IC · Ingame",
            "both": "OOC + IC",
        }[self.value]


@dataclass(frozen=True, slots=True)
class Paragraph:
    """Ein Paragraph: Ueberschrift plus ausformulierter Text."""

    title: str
    text: str
    #: Optionale Unterpunkte fuer Aufzaehlungen, die als Fliesstext
    #: unuebersichtlich waeren (etwa Strafstufen).
    bullets: tuple[str, ...] = ()

    @property
    def char_count(self) -> int:
        return len(self.title) + len(self.text) + sum(len(b) for b in self.bullets)


@dataclass(frozen=True, slots=True)
class RuleSet:
    key: str
    name: str
    emoji: str
    tagline: str
    length: RuleLength
    scope: RuleScope = RuleScope.DISCORD
    title: str = ""
    intro: str = ""
    paragraphs: tuple[Paragraph, ...] = ()
    closing: str = ""

    @property
    def display_title(self) -> str:
        return self.title or "REGELWERK"

    @property
    def rule_count(self) -> int:
        return len(self.paragraphs)

    @property
    def char_count(self) -> int:
        total = len(self.intro) + len(self.closing) + len(self.display_title)
        return total + sum(p.char_count for p in self.paragraphs)


def _p(title: str, text: str, *bullets: str) -> Paragraph:
    return Paragraph(title=title, text=text, bullets=bullets)


# --------------------------------------------------------------------------- #
# Wiederverwendete Paragraphen
# --------------------------------------------------------------------------- #

_DISCORD_TOS = _p(
    "Discord",
    "Zusätzlich gelten die Discord Community-Richtlinien und die "
    "Nutzungsbedingungen von Discord. Sie stehen über diesem Regelwerk.",
)

_PENALTIES = _p(
    "Strafen",
    "Verstöße werden je nach Schwere und Wiederholung geahndet. Das Team "
    "entscheidet im Einzelfall und ist nicht verpflichtet, jede Maßnahme "
    "vorher anzukündigen.",
    "Verwarnung bei leichten Verstößen",
    "Timeout zwischen einer Stunde und sieben Tagen",
    "Kick bei wiederholtem Fehlverhalten",
    "Bann bei schweren oder andauernden Verstößen",
)


# --------------------------------------------------------------------------- #
# Discord-Regelwerke
# --------------------------------------------------------------------------- #

_MINIMAL = RuleSet(
    key="minimal",
    name="Minimal",
    emoji="🌱",
    tagline="Fünf Paragraphen für kleine Server",
    length=RuleLength.SHORT,
    scope=RuleScope.DISCORD,
    title="SERVERREGELN",
    intro="Mit dem Betreten dieses Servers akzeptierst du die folgenden Regeln.",
    paragraphs=(
        _p(
            "Respekt",
            "Behandle alle Mitglieder so, wie du selbst behandelt werden "
            "möchtest. Beleidigungen und persönliche Angriffe haben hier "
            "keinen Platz.",
        ),
        _p(
            "Chat",
            "Kein Spam, kein Flood, kein Dauer-Caps. Schreibe in dem Kanal, "
            "der zum Thema passt.",
        ),
        _p(
            "Werbung",
            "Werbung für andere Server, Kanäle oder Produkte ist ohne "
            "Absprache mit dem Team nicht gestattet. Das gilt auch für "
            "Direktnachrichten an Mitglieder.",
        ),
        _p(
            "Inhalte",
            "Keine NSFW-, Gewalt- oder illegalen Inhalte. Im Zweifel gilt: "
            "lieber nicht posten.",
        ),
        _p(
            "Team",
            "Den Anweisungen des Teams ist Folge zu leisten. Wer eine "
            "Entscheidung für falsch hält, klärt das ruhig in einem Ticket.",
        ),
    ),
    closing="Danke, dass du dich an die Regeln hältst.",
)

_FREUNDESKREIS = RuleSet(
    key="freundeskreis",
    name="Freundeskreis",
    emoji="🫶",
    tagline="Locker formuliert für private Server",
    length=RuleLength.SHORT,
    scope=RuleScope.DISCORD,
    title="UNSERE REGELN",
    intro=(
        "Wir sind hier unter Freunden. Trotzdem ein paar Grundsätze, damit es "
        "das auch bleibt."
    ),
    paragraphs=(
        _p(
            "Miteinander",
            "Behandelt euch fair. Wenn es Streit gibt, wird er geklärt und "
            "nicht vor allen ausgetragen.",
        ),
        _p(
            "Vertrauen",
            "Was hier gesagt wird, bleibt hier. Screenshots aus privaten "
            "Gesprächen gehen niemanden von außen etwas an.",
        ),
        _p(
            "Gäste",
            "Ladet niemanden ohne Absprache ein. Dieser Server ist ein "
            "geschlossener Kreis, und das soll so bleiben.",
        ),
        _p(
            "Kanäle",
            "Nutzt die Kanäle, für die sie gedacht sind. Es sind nicht viele, "
            "also ist das keine große Aufgabe.",
        ),
        _p(
            "Grenzen",
            "Ein Nein ist ein Nein. Das gilt für Themen, für Späße und für "
            "alles andere.",
        ),
    ),
)

_KURZ_STRENG = RuleSet(
    key="kurz_streng",
    name="Kurz & Streng",
    emoji="⚖️",
    tagline="Wenige Paragraphen, klare Konsequenzen",
    length=RuleLength.SHORT,
    scope=RuleScope.DISCORD,
    title="SERVERREGELN",
    intro=(
        "Diese Regeln sind bewusst kurz gehalten. Sie werden konsequent "
        "durchgesetzt."
    ),
    paragraphs=(
        _p(
            "Verbotenes Verhalten",
            "Beleidigungen, Rassismus, Sexismus, Hetze und jede Form von "
            "Diskriminierung führen zum sofortigen Ausschluss. Es gibt hier "
            "keine Verwarnung und keine zweite Chance.",
        ),
        _p(
            "Inhalte",
            "NSFW-Inhalte, Gewaltdarstellungen und illegale Inhalte sind "
            "verboten. Das gilt auch für Profilbilder und Nicknamen.",
        ),
        _p(
            "Werbung",
            "Jede Form von Werbung ohne vorherige Erlaubnis wird als Spam "
            "gewertet und entsprechend behandelt.",
        ),
        _p(
            "Spam und Raids",
            "Spam, Massenpings und Raid-Versuche führen ohne Vorwarnung zum "
            "dauerhaften Bann.",
        ),
        _PENALTIES,
        _DISCORD_TOS,
    ),
    closing="Bei schweren Verstößen entfällt die Abstufung der Strafen.",
)

_GAMING_KURZ = RuleSet(
    key="gaming_kurz",
    name="Gaming kompakt",
    emoji="🎮",
    tagline="Das Nötigste für Gaming-Communities",
    length=RuleLength.SHORT,
    scope=RuleScope.DISCORD,
    title="GAMING REGELWERK",
    intro="Diese Regeln gelten im Chat, im Voice und in gemeinsamen Runden.",
    paragraphs=(
        _p(
            "Fairplay",
            "Cheats, Hacks und Exploits sind verboten. Wer beim Betrügen "
            "erwischt wird, fliegt aus der Community.",
        ),
        _p(
            "Umgangston",
            "Kein Flame, kein Blaming nach einer Niederlage. Toxisches "
            "Verhalten wird auch dann geahndet, wenn es außerhalb dieses "
            "Servers stattgefunden hat.",
        ),
        _p(
            "Sprachkanäle",
            "Stelle dein Mikrofon vernünftig ein. Kein Hintergrundlärm, kein "
            "Soundboard-Spam, keine ungefragte Musik.",
        ),
        _p(
            "Spoiler",
            "Markiere Spoiler zu Spielen und Filmen. Auch ein Screenshot "
            "kann spoilern.",
        ),
        _p(
            "Handel",
            "Der Verkauf von Accounts, Keys oder Ingame-Währung ist auf "
            "diesem Server nicht gestattet.",
        ),
    ),
)

_VOICE = RuleSet(
    key="voice_fokus",
    name="Voice-Knigge",
    emoji="🎙️",
    tagline="Für Server, auf denen vor allem gesprochen wird",
    length=RuleLength.SHORT,
    scope=RuleScope.DISCORD,
    title="SPRACHKANAL-REGELN",
    intro="Diese Regeln gelten in allen Sprachkanälen dieses Servers.",
    paragraphs=(
        _p(
            "Technik",
            "Nutze Push-to-Talk, wenn deine Umgebung laut ist. Tastaturlärm, "
            "Rückkopplungen und offene Lautsprecher stören alle anderen.",
        ),
        _p(
            "Lautstärke",
            "Kein Schreien, kein absichtliches Übersteuern. Wer dauerhaft zu "
            "laut ist, wird stummgeschaltet.",
        ),
        _p(
            "Musik und Soundboards",
            "Musik läuft ausschließlich im dafür vorgesehenen Kanal. "
            "Soundboards sind nur erlaubt, solange sich niemand gestört fühlt.",
        ),
        _p(
            "Gesprächskultur",
            "Lasst einander ausreden. Wer dauerhaft dazwischenredet, wird "
            "aus dem Kanal entfernt.",
        ),
        _p(
            "Aufnahmen",
            "Mitschnitte und Streams sind nur zulässig, wenn alle Beteiligten "
            "vorher zugestimmt haben.",
        ),
        _p(
            "Kanalwechsel",
            "Ständiges Betreten und Verlassen von Kanälen gilt als Störung "
            "und wird entsprechend behandelt.",
        ),
    ),
)

_LERNSERVER = RuleSet(
    key="lernserver",
    name="Lerngruppe",
    emoji="📚",
    tagline="Ruhe, Fairness und Urheberrecht",
    length=RuleLength.SHORT,
    scope=RuleScope.DISCORD,
    title="REGELN DER LERNGRUPPE",
    intro="Hier wird gearbeitet. Darauf beruhen diese Regeln.",
    paragraphs=(
        _p(
            "Arbeitsklima",
            "In den Lernräumen ist Stille die Grundeinstellung. Wer reden "
            "möchte, wechselt in den Pausenkanal.",
        ),
        _p(
            "Fragen",
            "Stelle deine Frage im passenden Fachkanal und beschreibe, was du "
            "schon versucht hast. Das erhöht die Chance auf eine gute Antwort "
            "erheblich.",
        ),
        _p(
            "Zusammenarbeit",
            "Erklären ja, abschreiben lassen nein. Wer fremde Arbeiten als "
            "eigene ausgibt, riskiert mehr als eine Serverstrafe.",
        ),
        _p(
            "Material",
            "Teile nur Unterlagen, die weitergegeben werden dürfen. "
            "Kostenpflichtige Skripte und Prüfungsunterlagen gehören nicht "
            "hierher.",
        ),
        _p(
            "Quellen",
            "Gib bei geteilten Materialien an, woher sie stammen. Das "
            "schützt dich und hilft allen anderen.",
        ),
    ),
)

_KREATIV = RuleSet(
    key="kreativ",
    name="Kreativ-Community",
    emoji="🎨",
    tagline="Feedback, Urheberrecht und Aufträge",
    length=RuleLength.SHORT,
    scope=RuleScope.DISCORD,
    title="REGELWERK",
    intro="Ein Ort für eigene Werke, ehrliches Feedback und faire Aufträge.",
    paragraphs=(
        _p(
            "Eigene Werke",
            "Poste nur Arbeiten, die von dir stammen. Bei Vorlagen, "
            "Referenzen und Pinseln gehört die Quelle dazu.",
        ),
        _p(
            "KI-Inhalte",
            "Mit KI erzeugte Werke müssen als solche gekennzeichnet werden. "
            "Sie sind erlaubt, aber sie werden nicht als eigene Handarbeit "
            "ausgegeben.",
        ),
        _p(
            "Feedback",
            "Kritik richtet sich immer an das Werk, niemals an die Person. "
            "Wer Feedback gibt, benennt auch, was gelungen ist.",
        ),
        _p(
            "Ungefragte Kritik",
            "Ein Verriss ohne Bitte um Feedback ist keine Kritik, sondern "
            "eine Störung. Frag nach, bevor du zerlegst.",
        ),
        _p(
            "Aufträge",
            "Preise, Fristen und Nutzungsrechte werden vorher schriftlich "
            "geklärt. Der Server vermittelt nicht und haftet nicht für "
            "Absprachen zwischen Mitgliedern.",
        ),
        _p(
            "Diebstahl",
            "Das Hochladen fremder Werke als eigene führt zum sofortigen "
            "Ausschluss.",
        ),
    ),
)

_STANDARD = RuleSet(
    key="standard",
    name="Standard",
    emoji="📋",
    tagline="Der ausgewogene Allrounder mit elf Paragraphen",
    length=RuleLength.MEDIUM,
    scope=RuleScope.DISCORD,
    title="DISCORD REGELWERK",
    intro=(
        "Mit dem Betreten dieses Servers akzeptierst du automatisch alle "
        "folgenden Regeln."
    ),
    paragraphs=(
        _p(
            "Respekt",
            "Behandle alle Mitglieder respektvoll. Beleidigungen, Mobbing, "
            "Diskriminierung, Hass und Provokationen sind verboten.",
        ),
        _p(
            "Chat",
            "Spam, Flood, Capslock und sinnlose Nachrichten sind nicht "
            "erlaubt. Nutze die passenden Kanäle.",
        ),
        _p(
            "Werbung",
            "Werbung für Discord-Server, Webseiten oder Social Media ist ohne "
            "Erlaubnis verboten. Einladungslinks per Direktnachricht sind "
            "ebenfalls untersagt.",
        ),
        _p(
            "Inhalte",
            "NSFW-, illegale, extremistische oder gewaltverherrlichende "
            "Inhalte sind verboten. Schadsoftware und IP-Logger dürfen nicht "
            "verbreitet werden.",
        ),
        _p(
            "Sprachkanäle",
            "Kein Schreien, Trollen, Soundboard-Spam oder absichtliches "
            "Stören. Verhalte dich respektvoll.",
        ),
        _p(
            "Datenschutz",
            "Teile keine persönlichen Daten von dir oder anderen. Dazu "
            "gehören Adressen, Telefonnummern und Bilder ohne Einwilligung.",
        ),
        _p(
            "Profil",
            "Nicknamen, Profilbilder, Banner und Status dürfen keine "
            "unangemessenen Inhalte enthalten.",
        ),
        _p(
            "Tickets",
            "Erstelle Tickets nur für ernst gemeinte Anliegen. Wer das "
            "System missbraucht, verliert den Zugriff darauf.",
        ),
        _p(
            "Team",
            "Den Anweisungen des Teams ist Folge zu leisten. Diskussionen "
            "über Strafen gehören in ein Ticket und nicht in den Chat.",
        ),
        _PENALTIES,
        _DISCORD_TOS,
    ),
    closing="Vielen Dank, dass du die Regeln einhältst.",
)

_COMMUNITY = RuleSet(
    key="community",
    name="Community",
    emoji="🌐",
    tagline="Für wachsende öffentliche Server",
    length=RuleLength.MEDIUM,
    scope=RuleScope.DISCORD,
    title="DISCORD REGELWERK",
    intro=(
        "Damit sich hier alle wohlfühlen, gelten die folgenden Regeln. Sie "
        "gelten für jeden, unabhängig von Rolle oder Verweildauer."
    ),
    paragraphs=(
        _p(
            "Respekt",
            "Ein respektvoller Umgang ist Pflicht und keine Höflichkeitsfloskel. "
            "Diskutiert Meinungen, nicht Menschen.",
        ),
        _p(
            "Diskriminierung",
            "Herabwürdigungen wegen Herkunft, Hautfarbe, Geschlecht, "
            "Orientierung, Religion, Alter oder Behinderung führen zum "
            "sofortigen Ausschluss.",
        ),
        _p(
            "Mobbing",
            "Gezieltes Bloßstellen, Nachtreten und das Aufhetzen anderer gegen "
            "einzelne Mitglieder werden wie schwere Verstöße behandelt.",
        ),
        _p(
            "Kanalordnung",
            "Halte dich an das Thema des jeweiligen Kanals. Was das Thema ist, "
            "steht in der angehefteten Nachricht.",
        ),
        _p(
            "Spam",
            "Kettennachrichten, Massenpings, Buchstabenketten und wiederholte "
            "Beiträge sind untersagt.",
        ),
        _p(
            "Werbung",
            "Selbstpromotion ist ausschließlich im dafür vorgesehenen Kanal "
            "erlaubt. Werbung per Direktnachricht führt zum Ausschluss.",
        ),
        _p(
            "Zweitaccounts",
            "Pro Person ist ein Account zulässig. Zweitaccounts zur Umgehung "
            "einer Strafe führen zum dauerhaften Bann beider Konten.",
        ),
        _p(
            "Identität",
            "Das Vortäuschen einer fremden Identität oder einer Teamrolle ist "
            "verboten.",
        ),
        _p(
            "Datenschutz",
            "Veröffentliche keine Daten anderer Personen. Screenshots privater "
            "Gespräche benötigen die Zustimmung aller Beteiligten.",
        ),
        _p(
            "Meldungen",
            "Melde Verstöße über ein Ticket, statt sie öffentlich zu "
            "diskutieren. Eine öffentliche Anklage macht die Sache selten besser.",
        ),
        _PENALTIES,
        _DISCORD_TOS,
    ),
    closing="Unwissenheit schützt nicht vor Konsequenzen.",
)

_GAMING_VOLL = RuleSet(
    key="gaming_voll",
    name="Gaming ausführlich",
    emoji="🕹️",
    tagline="Mit Fairplay, Turnieren und Voice-Regeln",
    length=RuleLength.MEDIUM,
    scope=RuleScope.DISCORD,
    title="GAMING REGELWERK",
    intro=(
        "Diese Regeln gelten im gesamten Server sowie in allen Spielrunden und "
        "Turnieren, die hier organisiert werden."
    ),
    paragraphs=(
        _p(
            "Fairplay",
            "Cheats, Hacks, Exploits und Drittanbieter-Software sind in jeder "
            "Form verboten. Das gilt auch für Spiele außerhalb dieses Servers, "
            "wenn du dabei als Mitglied auftrittst.",
        ),
        _p(
            "Smurfing",
            "Das Spielen auf Zweitkonten in Ranglistenrunden der Community ist "
            "nicht gestattet.",
        ),
        _p(
            "Griefing",
            "Absichtliches Verlieren, Sabotage, Trollen und grundloses "
            "Abwesendsein zerstören die Runde für alle anderen und werden "
            "geahndet.",
        ),
        _p(
            "Umgangston",
            "Kein Flame, kein Blaming nach einer Niederlage. Kritik im Spiel "
            "bleibt sachlich und kurz.",
        ),
        _p(
            "Sprachkanäle",
            "Wer im Team spielt, hört auf Ansagen. Soundboard-Spam während "
            "laufender Runden ist untersagt.",
        ),
        _p(
            "Turnieranmeldung",
            "Eine Anmeldung ist verbindlich. Wer unentschuldigt nicht antritt, "
            "wird beim nächsten Turnier nachrangig berücksichtigt.",
        ),
        _p(
            "Turnierleitung",
            "Entscheidungen der Turnierleitung sind endgültig. Einsprüche "
            "werden nach dem Turnier in einem Ticket behandelt.",
        ),
        _p(
            "Ergebnisse",
            "Absprachen über Spielausgänge sind Betrug und führen zum "
            "Ausschluss aus allen künftigen Turnieren.",
        ),
        _p(
            "Handel",
            "Der Verkauf von Accounts, Keys oder Ingame-Währung ist verboten. "
            "Tauschgeschäfte zwischen Mitgliedern sind Privatsache und erfolgen "
            "auf eigenes Risiko.",
        ),
        _p(
            "Spoiler",
            "Markiere Spoiler zu Spielen, Turnieren und Übertragungen.",
        ),
        _PENALTIES,
        _DISCORD_TOS,
    ),
)

_CREATOR = RuleSet(
    key="creator",
    name="Creator & Community",
    emoji="🎬",
    tagline="Für Kanäle mit Publikum",
    length=RuleLength.MEDIUM,
    scope=RuleScope.DISCORD,
    title="COMMUNITY REGELWERK",
    intro="Dieser Server gehört zur Community rund um den Kanal.",
    paragraphs=(
        _p(
            "Respekt",
            "Respekt gilt gegenüber allen, auch gegenüber Kritikern. "
            "Meinungsverschiedenheiten sind erlaubt, Anfeindungen nicht.",
        ),
        _p(
            "Drama",
            "Dieser Server ist kein Ort für Auseinandersetzungen mit anderen "
            "Creators oder Communities. Solche Themen werden kommentarlos "
            "entfernt.",
        ),
        _p(
            "Leaks",
            "Unveröffentlichte Inhalte, Vorabversionen und interne "
            "Informationen dürfen nicht geteilt werden.",
        ),
        _p(
            "Spoiler",
            "Spoiler zu neuen Videos gehören in den dafür vorgesehenen Kanal, "
            "und zwar für mindestens achtundvierzig Stunden nach "
            "Veröffentlichung.",
        ),
        _p(
            "Clips",
            "Ausschnitte dürfen geteilt werden, solange die Quelle genannt "
            "wird und der Zusammenhang erhalten bleibt.",
        ),
        _p(
            "Selbstpromotion",
            "Eigene Projekte gehören ausschließlich in den Promo-Kanal. "
            "Abo-Betteln und Follow-for-Follow sind untersagt.",
        ),
        _p(
            "Direktnachrichten",
            "Werbung per Direktnachricht an Mitglieder führt zum sofortigen "
            "Ausschluss.",
        ),
        _p(
            "Kontakt",
            "Geschäftliche Anfragen laufen über die angegebene Adresse. Das "
            "Team antwortet nicht auf private Anfragen zu Videos.",
        ),
        _p(
            "Moderation",
            "Moderationsentscheidungen werden nicht im öffentlichen Chat "
            "diskutiert.",
        ),
        _PENALTIES,
        _DISCORD_TOS,
    ),
)

_SUPPORT = RuleSet(
    key="support",
    name="Support-Server",
    emoji="🛟",
    tagline="Tickets, Reaktionszeiten und Umgangston",
    length=RuleLength.MEDIUM,
    scope=RuleScope.DISCORD,
    title="SUPPORT REGELWERK",
    intro="Damit dir schnell geholfen werden kann, beachte bitte Folgendes.",
    paragraphs=(
        _p(
            "Vorab",
            "Sieh zuerst in die häufigen Fragen und die Anleitungen. Viele "
            "Anliegen sind dort bereits beantwortet.",
        ),
        _p(
            "Ticketinhalt",
            "Beschreibe dein Problem in ganzen Sätzen. Nenne, was du bereits "
            "versucht hast, und füge Screenshots oder Fehlermeldungen bei.",
        ),
        _p(
            "Ein Ticket pro Anliegen",
            "Mehrere Tickets für dasselbe Problem verlangsamen die Bearbeitung "
            "für alle.",
        ),
        _p(
            "Geduld",
            "Das Team hilft freiwillig und in seiner Freizeit. Nachfassen im "
            "Minutentakt beschleunigt nichts.",
        ),
        _p(
            "Direktnachrichten",
            "Schreibe einzelne Teammitglieder nicht privat an. Alle Anliegen "
            "laufen über das Ticketsystem.",
        ),
        _p(
            "Umgangston",
            "Beleidigungen gegenüber dem Team führen zum sofortigen Schließen "
            "des Tickets.",
        ),
        _p(
            "Missbrauch",
            "Tickets ohne ernstes Anliegen und Scherzanfragen führen zum "
            "Entzug der Ticketberechtigung.",
        ),
        _p(
            "Abschluss",
            "Gib kurz Bescheid, wenn dein Problem gelöst ist. Geschlossene "
            "Tickets werden archiviert, nicht gelöscht.",
        ),
        _PENALTIES,
        _DISCORD_TOS,
    ),
)

_BUSINESS = RuleSet(
    key="business",
    name="Business",
    emoji="🏢",
    tagline="Für Firmen- und Projektserver",
    length=RuleLength.MEDIUM,
    scope=RuleScope.DISCORD,
    title="NUTZUNGSORDNUNG",
    intro=(
        "Dieser Server ist ein Arbeitsmittel. Es gelten die Regeln des "
        "Unternehmens sowie die folgenden Bestimmungen."
    ),
    paragraphs=(
        _p(
            "Vertraulichkeit",
            "Interne Informationen verlassen diesen Server nicht. Das gilt "
            "auch nach dem Ausscheiden aus dem Projekt.",
        ),
        _p(
            "Kundendaten",
            "Daten von Kunden werden ausschließlich in den dafür vorgesehenen "
            "Kanälen behandelt und niemals in offenen Bereichen.",
        ),
        _p(
            "Screenshots",
            "Bildschirmaufnahmen interner Kanäle sind untersagt.",
        ),
        _p(
            "Zugangsdaten",
            "Passwörter und Zugangsdaten werden niemals im Chat geteilt, auch "
            "nicht in privaten Kanälen.",
        ),
        _p(
            "Kommunikation",
            "Schreibe sachlich, knapp und nachvollziehbar. Entscheidungen "
            "gehören dokumentiert in den Projektkanal.",
        ),
        _p(
            "Erreichbarkeit",
            "Antworten werden innerhalb der Arbeitszeiten erwartet. Außerhalb "
            "besteht keine Antwortpflicht.",
        ),
        _p(
            "Abwesenheit",
            "Urlaub und längere Abwesenheiten gehören rechtzeitig in den "
            "Kalender.",
        ),
        _p(
            "Externe",
            "Gäste und Kunden erhalten ausschließlich Zugriff auf den "
            "Kundenbereich.",
        ),
        _p(
            "Verstöße",
            "Verstöße gegen die Vertraulichkeit werden nicht als Serversache "
            "behandelt, sondern arbeitsrechtlich.",
        ),
    ),
)

_ANIME = RuleSet(
    key="anime",
    name="Anime & Manga",
    emoji="🌸",
    tagline="Spoiler, Fanart und Quellen",
    length=RuleLength.MEDIUM,
    scope=RuleScope.DISCORD,
    title="REGELWERK",
    intro="Ein Server für alle, die Anime und Manga mögen.",
    paragraphs=(
        _p(
            "Spoiler",
            "Alles, was noch nicht offiziell erschienen ist, gilt als Spoiler "
            "und gehört in den Spoiler-Kanal oder hinter Spoilertags.",
        ),
        _p(
            "Titel und Bilder",
            "Auch Nachrichtentitel und Vorschaubilder können spoilern. Denke "
            "daran, bevor du etwas verlinkst.",
        ),
        _p(
            "Fanart",
            "Poste nur eigene Werke oder solche mit ausdrücklicher "
            "Quellenangabe. Reposts ohne Erlaubnis sind untersagt.",
        ),
        _p(
            "KI-Bilder",
            "Mit KI erzeugte Bilder müssen gekennzeichnet werden.",
        ),
        _p(
            "Inhalte",
            "Keine NSFW-Inhalte, auch nicht als Zeichnung. Das gilt "
            "ausdrücklich auch für Profilbilder.",
        ),
        _p(
            "Illegale Quellen",
            "Links zu illegalen Streaming- oder Scanseiten werden entfernt.",
        ),
        _p(
            "Geschmack",
            "Geschmack ist keine Verhandlungssache. Fandom-Kriege und das "
            "Herabsetzen anderer Serien haben hier keinen Platz.",
        ),
        _p(
            "Empfehlungen",
            "Empfehlungen sind willkommen. Ein Nein zu einer Empfehlung ist "
            "keine Beleidigung.",
        ),
        _PENALTIES,
        _DISCORD_TOS,
    ),
)

_SOCIAL = RuleSet(
    key="social",
    name="Social & Lounge",
    emoji="☕",
    tagline="Für Server, auf denen vor allem geredet wird",
    length=RuleLength.MEDIUM,
    scope=RuleScope.DISCORD,
    title="REGELWERK",
    intro="Hier geht es ums Reden. Damit das für alle angenehm bleibt:",
    paragraphs=(
        _p(
            "Gesprächskultur",
            "Lasst einander ausreden, auch im Text. Wer eine Frage nicht "
            "beantworten möchte, muss das nicht begründen.",
        ),
        _p(
            "Grenzen",
            "Ein Nein ist ein Nein, beim Thema wie beim Kontakt. Ungefragte "
            "Annäherungsversuche per Direktnachricht führen zum Ausschluss.",
        ),
        _p(
            "Vertraulichkeit",
            "Was hier im Vertrauen gesagt wird, bleibt hier. Das Weitergeben "
            "privater Gespräche ist ein schwerer Verstoß.",
        ),
        _p(
            "Ernste Themen",
            "Belastende Themen gehören in den dafür vorgesehenen Kanal und "
            "werden dort mit dem nötigen Ernst behandelt.",
        ),
        _p(
            "Keine Therapie",
            "Dieser Server ersetzt weder eine Therapie noch einen Notruf. Bei "
            "akuter Not wende dich bitte an professionelle Hilfe. Das Team "
            "nennt dir auf Wunsch Anlaufstellen.",
        ),
        _p(
            "Ratschläge",
            "Gib keine ungefragten Ratschläge. Frage vorher, ob jemand "
            "Lösungen hören möchte oder einfach nur reden will.",
        ),
        _p(
            "Alltag",
            "Kein Dauerspam, keine Massenpings. Musik läuft nur im Musikkanal.",
        ),
        _p(
            "Trigger",
            "Kennzeichne Inhalte, die belasten können. Ein kurzer Hinweis "
            "kostet nichts.",
        ),
        _PENALTIES,
        _DISCORD_TOS,
    ),
)

_ESPORTS = RuleSet(
    key="esports",
    name="Esports-Organisation",
    emoji="🏆",
    tagline="Kader, Auftreten und Vertraulichkeit",
    length=RuleLength.MEDIUM,
    scope=RuleScope.DISCORD,
    title="ORGANISATIONSREGELN",
    intro=(
        "Wer diese Organisation vertritt, vertritt sie auch außerhalb dieses "
        "Servers."
    ),
    paragraphs=(
        _p(
            "Auftreten",
            "Kein toxisches Verhalten in Spielen, Streams oder sozialen "
            "Medien. Dein Verhalten fällt auf die gesamte Organisation zurück.",
        ),
        _p(
            "Kritik",
            "Kritik an Mitspielern oder Gegnern wird intern geäußert, niemals "
            "öffentlich.",
        ),
        _p(
            "Sponsoren",
            "Partner und Sponsoren werden nicht negativ erwähnt. Anfragen "
            "dazu laufen über die Leitung.",
        ),
        _p(
            "Training",
            "Trainingszeiten sind verbindlich. Absagen erfolgen rechtzeitig "
            "und mit Begründung.",
        ),
        _p(
            "Matchtermine",
            "Offizielle Matchtermine haben Vorrang vor privaten Spielrunden.",
        ),
        _p(
            "Vertraulichkeit",
            "Strategien, Aufstellungen und Analysen bleiben intern. Die "
            "Weitergabe an Dritte gilt als schwerer Vertrauensbruch.",
        ),
        _p(
            "Presse",
            "Presseanfragen werden nicht eigenständig beantwortet, sondern an "
            "die Organisation weitergeleitet.",
        ),
        _p(
            "Kaderwechsel",
            "Wechselabsichten werden zuerst mit der Leitung besprochen. "
            "Doppelmitgliedschaften in konkurrierenden Teams sind "
            "ausgeschlossen.",
        ),
        _p(
            "Ausrüstung",
            "Gestellte Ausrüstung und Accounts bleiben Eigentum der "
            "Organisation.",
        ),
        _PENALTIES,
    ),
)

_AUSFUEHRLICH = RuleSet(
    key="ausfuehrlich",
    name="Ausführlich",
    emoji="📖",
    tagline="Vollständige Serverordnung mit 20 Paragraphen",
    length=RuleLength.LONG,
    scope=RuleScope.DISCORD,
    title="SERVERORDNUNG",
    intro=(
        "Diese Serverordnung gilt für alle Mitglieder. Mit dem Verbleib auf "
        "dem Server erkennst du sie an. Ergänzend gelten die "
        "Discord-Nutzungsbedingungen und die Community-Richtlinien."
    ),
    paragraphs=(
        _p(
            "Geltungsbereich",
            "Diese Ordnung gilt in allen Text- und Sprachkanälen, in Threads "
            "sowie in Direktnachrichten zwischen Mitgliedern, soweit diese den "
            "Server betreffen.",
        ),
        _p(
            "Umgangston",
            "Begegne allen Mitgliedern mit Respekt. Beleidigungen, Drohungen "
            "und Herabwürdigungen sind untersagt. Ironie entschuldigt keinen "
            "verletzenden Inhalt.",
        ),
        _p(
            "Diskriminierung",
            "Herabwürdigungen wegen Herkunft, Hautfarbe, Geschlecht, "
            "Orientierung, Religion, Alter oder Behinderung führen zum "
            "sofortigen und dauerhaften Ausschluss.",
        ),
        _p(
            "Belästigung",
            "Wiederholte unerwünschte Kontaktaufnahme, Nachstellen und "
            "sexuelle Belästigung werden ohne Verwarnung mit einem Bann "
            "geahndet.",
        ),
        _p(
            "Verbotene Inhalte",
            "Pornografische, gewaltverherrlichende, extremistische und "
            "verstörende Inhalte sind verboten. Das gilt für Nachrichten, "
            "Dateien, Links und Profilangaben gleichermaßen.",
        ),
        _p(
            "Illegale Inhalte",
            "Inhalte, die gegen geltendes Recht verstoßen, werden entfernt und "
            "können zur Anzeige gebracht werden.",
        ),
        _p(
            "Urheberrecht",
            "Teile nur Werke, an denen du die nötigen Rechte besitzt. Bei "
            "fremden Werken ist die Quelle zu nennen.",
        ),
        _p(
            "Schadsoftware",
            "Das Verbreiten von Schadsoftware, Phishing-Links oder IP-Loggern "
            "führt zum sofortigen dauerhaften Bann.",
        ),
        _p(
            "Chatverhalten",
            "Schreibe im thematisch passenden Kanal. Spam, Buchstabenketten "
            "und wiederholte Beiträge sind untersagt.",
        ),
        _p(
            "Erwähnungen",
            "Massenpings sowie die Erwähnung von @everyone und @here sind dem "
            "Team vorbehalten. Pinge einzelne Personen nicht wiederholt ohne "
            "Anlass.",
        ),
        _p(
            "Sprachkanäle",
            "Störgeräusche, Rückkopplungen und Soundboard-Spam sind zu "
            "unterlassen. Wiederholtes Betreten und Verlassen gilt als "
            "Störung.",
        ),
        _p(
            "Aufnahmen",
            "Mitschnitte und Streams aus Sprachkanälen sind nur mit "
            "Zustimmung aller Beteiligten zulässig.",
        ),
        _p(
            "Werbung",
            "Werbung für Server, Kanäle, Produkte oder Dienstleistungen ist "
            "genehmigungspflichtig. Werbung per Direktnachricht ist stets "
            "untersagt.",
        ),
        _p(
            "Accounts",
            "Pro Person ist ein Account zulässig. Zweitaccounts zur Umgehung "
            "von Sanktionen führen zum dauerhaften Ausschluss aller beteiligten "
            "Konten.",
        ),
        _p(
            "Identität",
            "Das Vortäuschen einer fremden Identität, einer Teamrolle oder "
            "einer Partnerschaft ist verboten.",
        ),
        _p(
            "Profil",
            "Benutzernamen, Nicknamen, Profilbilder, Banner und Statusangaben "
            "müssen dieser Ordnung entsprechen.",
        ),
        _p(
            "Datenschutz",
            "Persönliche Daten Dritter dürfen nicht veröffentlicht werden. "
            "Screenshots privater Gespräche bedürfen der Zustimmung.",
        ),
        _p(
            "Team",
            "Den Anweisungen des Teams ist Folge zu leisten. Beschwerden über "
            "Maßnahmen gehören ausschließlich in ein Ticket.",
        ),
        _p(
            "Sanktionen",
            "Als Maßnahmen kommen Verwarnung, Stummschaltung, Timeout, "
            "Ausschluss und dauerhafte Sperre in Betracht. Die Wahl richtet "
            "sich nach Schwere, Vorsatz und Wiederholung.",
        ),
        _p(
            "Änderungen",
            "Das Team kann diese Ordnung anpassen. Änderungen werden im "
            "Ankündigungskanal bekanntgegeben. Regelungslücken werden im Sinne "
            "dieser Ordnung ausgelegt.",
        ),
    ),
    closing="Fragen zu einzelnen Punkten beantwortet das Team in einem Ticket.",
)

_RECHTSSICHER = RuleSet(
    key="rechtssicher",
    name="Rechtlich abgesichert",
    emoji="⚖️",
    tagline="Mit Jugendschutz, Haftung und Datenverarbeitung",
    length=RuleLength.LONG,
    scope=RuleScope.DISCORD,
    title="NUTZUNGSBEDINGUNGEN",
    intro=(
        "Diese Bedingungen richten sich an öffentliche Server mit vielen "
        "Mitgliedern und ergänzen die geltenden gesetzlichen Bestimmungen."
    ),
    paragraphs=(
        _p(
            "Geltungsbereich",
            "Diese Bedingungen gelten für alle Kanäle, Threads und "
            "Sprachkanäle dieses Servers. Mit dem Beitritt werden sie "
            "anerkannt.",
        ),
        _p(
            "Mindestalter",
            "Die Nutzung von Discord setzt ein Mindestalter von dreizehn "
            "Jahren voraus. In einzelnen Ländern gelten höhere Altersgrenzen. "
            "Bei begründeten Zweifeln kann der Zugang gesperrt werden.",
        ),
        _p(
            "Jugendschutz",
            "Inhalte, die die Entwicklung Minderjähriger beeinträchtigen "
            "können, sind unzulässig. Altersbeschränkte Bereiche sind "
            "entsprechend gekennzeichnet.",
        ),
        _p(
            "Verbotene Inhalte",
            "Unzulässig sind insbesondere Volksverhetzung, Gewaltdarstellung, "
            "kinder- und jugendgefährdende Inhalte sowie Aufrufe zu "
            "Straftaten.",
        ),
        _p(
            "Urheberrecht",
            "Es dürfen nur Inhalte geteilt werden, an denen die erforderlichen "
            "Rechte bestehen. Rechteinhaber können die Entfernung über ein "
            "Ticket verlangen.",
        ),
        _p(
            "Persönlichkeitsrechte",
            "Die Veröffentlichung von Bildern, Aufnahmen oder Daten anderer "
            "Personen bedarf deren Einwilligung.",
        ),
        _p(
            "Datenverarbeitung",
            "Über die von Discord bereitgestellten Daten hinaus werden keine "
            "personenbezogenen Daten gespeichert. Moderationsprotokolle dienen "
            "ausschließlich der Durchsetzung dieser Bedingungen.",
        ),
        _p(
            "Auskunft",
            "Auf Anfrage wird Auskunft über gespeicherte Moderationsvermerke "
            "erteilt. Die Anfrage erfolgt über ein Ticket.",
        ),
        _p(
            "Haftung",
            "Für veröffentlichte Inhalte haften die Mitglieder selbst. Der "
            "Betreiber übernimmt keine Haftung für Absprachen zwischen "
            "Mitgliedern.",
        ),
        _p(
            "Externe Inhalte",
            "Verlinkte externe Angebote liegen außerhalb der Verantwortung "
            "dieses Servers. Für deren Inhalte wird keine Gewähr übernommen.",
        ),
        _p(
            "Hausrecht",
            "Der Betreiber übt das virtuelle Hausrecht aus. Ein Anspruch auf "
            "Mitgliedschaft oder auf bestimmte Rollen besteht nicht.",
        ),
        _p(
            "Sanktionen",
            "Bei Verstößen kommen Verwarnung, Stummschaltung, Ausschluss und "
            "Sperre in Betracht. Die Maßnahme wird nach Schwere, Vorsatz und "
            "Wiederholung gewählt.",
        ),
        _p(
            "Widerspruch",
            "Gegen Maßnahmen kann über ein Ticket Widerspruch eingelegt "
            "werden. Der Widerspruch wird von einer nicht beteiligten Person "
            "geprüft und die Entscheidung begründet mitgeteilt.",
        ),
        _p(
            "Löschung",
            "Auf Wunsch werden von dir verfasste Beiträge entfernt, soweit dies "
            "technisch möglich und rechtlich zulässig ist.",
        ),
        _p(
            "Änderungen",
            "Änderungen dieser Bedingungen werden mit einer Frist von sieben "
            "Tagen angekündigt. Die fortgesetzte Nutzung gilt als Zustimmung.",
        ),
        _p(
            "Salvatorische Klausel",
            "Sollte eine Bestimmung unwirksam sein, bleibt die Wirksamkeit der "
            "übrigen Bestimmungen unberührt.",
        ),
    ),
    closing=(
        "Dieses Regelwerk ist eine Vorlage und ersetzt keine Rechtsberatung. "
        "Prüfe es vor dem Einsatz auf deinen Anwendungsfall."
    ),
)

_GROSSSERVER = RuleSet(
    key="grossserver",
    name="Großer Server",
    emoji="🏙️",
    tagline="Für Server ab mehreren tausend Mitgliedern",
    length=RuleLength.LONG,
    scope=RuleScope.DISCORD,
    title="SERVERREGELN",
    intro=(
        "Je größer eine Community, desto klarer müssen die Regeln sein. Dieses "
        "Regelwerk ist bewusst ausführlich."
    ),
    paragraphs=(
        _p(
            "Grundsatz",
            "Respektvoller Umgang ohne Ausnahme. Wer das nicht leisten kann, "
            "ist hier falsch.",
        ),
        _p(
            "Diskriminierung",
            "Jede Form von Diskriminierung führt zum Ausschluss. Darüber wird "
            "nicht diskutiert.",
        ),
        _p(
            "Belästigung",
            "Belästigung, Stalking und Nachstellen werden ohne Verwarnung mit "
            "einem dauerhaften Bann geahndet.",
        ),
        _p(
            "Selbstschädigung",
            "Aufrufe zu Gewalt oder Selbstschädigung sind verboten. Wer Hilfe "
            "braucht, findet beim Team Anlaufstellen.",
        ),
        _p(
            "Kanalordnung",
            "Jeder Kanal hat ein Thema, das in der angehefteten Nachricht "
            "steht. Medienkanäle sind für Medien, nicht für Diskussionen.",
        ),
        _p(
            "Bot-Befehle",
            "Bot-Befehle gehören in den dafür vorgesehenen Kanal.",
        ),
        _p(
            "Sprachkanäle",
            "Kein Missbrauch von Stummschaltung oder Verschiebefunktion, kein "
            "Dauerbelegen leerer Kanäle.",
        ),
        _p(
            "Events",
            "Bei Events gelten die Anweisungen der Moderation. Störungen "
            "führen zum Ausschluss vom Event.",
        ),
        _p(
            "Werbung",
            "Werbung ist ausschließlich im Promo-Kanal und höchstens einmal pro "
            "Woche gestattet.",
        ),
        _p(
            "Handel",
            "Der Handel mit Accounts, Währungen oder Dienstleistungen ist "
            "untersagt. Spendenaufrufe bedürfen der Absprache.",
        ),
        _p(
            "Automatisierung",
            "Selfbots und die Automatisierung des eigenen Accounts sind "
            "verboten. Das gilt auch für Scraper und Massen-Direktnachrichten.",
        ),
        _p(
            "Moderation",
            "Moderationsentscheidungen werden nicht öffentlich diskutiert. Wer "
            "eine Entscheidung für falsch hält, nutzt den Widerspruchsweg.",
        ),
        _p(
            "Direktnachrichten an das Team",
            "Das Anschreiben einzelner Moderatoren ist unerwünscht. Alle "
            "Anliegen laufen über Tickets.",
        ),
        _p(
            "Sanktionsstufen",
            "Maßnahmen werden abgestuft verhängt:",
            "Stufe 1: Hinweis ohne Eintrag",
            "Stufe 2: Verwarnung mit Eintrag",
            "Stufe 3: Timeout zwischen einer Stunde und sieben Tagen",
            "Stufe 4: Ausschluss mit Rückkehrmöglichkeit",
            "Stufe 5: dauerhafte Sperre",
        ),
        _p(
            "Schwere Verstöße",
            "Bei Doxxing, Raids, Schadsoftware oder Straftaten entfällt die "
            "Abstufung. In diesen Fällen erfolgt die sofortige Sperre.",
        ),
        _p(
            "Verjährung",
            "Verwarnungen verfallen nach sechs Monaten ohne weiteren Verstoß.",
        ),
        _p(
            "Überprüfung",
            "Diese Regeln werden regelmäßig überprüft und bei Bedarf "
            "angepasst.",
        ),
        _DISCORD_TOS,
    ),
)


# --------------------------------------------------------------------------- #
# Rollenspiel: OOC (Discord) und IC (Ingame)
# --------------------------------------------------------------------------- #

_RP_OOC_PARAGRAPHS: tuple[Paragraph, ...] = (
    _p(
        "Respekt",
        "Behandle alle Mitglieder respektvoll. Beleidigungen, Mobbing, "
        "Diskriminierung, Hass und Provokationen sind verboten.",
    ),
    _p(
        "IC und OOC trennen",
        "Was deinem Charakter im Spiel widerfährt, hat nichts mit dir als "
        "Person zu tun. Konflikte aus dem Spiel werden nicht auf Discord "
        "weitergeführt.",
    ),
    _p(
        "Chat",
        "Spam, Flood, Capslock und sinnlose Nachrichten sind nicht erlaubt. "
        "Nutze die passenden Kanäle.",
    ),
    _p(
        "Werbung",
        "Werbung für andere Server, Webseiten oder Social Media ist ohne "
        "Erlaubnis verboten. Einladungslinks per Direktnachricht sind ebenfalls "
        "untersagt.",
    ),
    _p(
        "Inhalte",
        "NSFW-, illegale, extremistische oder gewaltverherrlichende Inhalte "
        "sind verboten. Schadsoftware und IP-Logger dürfen nicht verbreitet "
        "werden.",
    ),
    _p(
        "Sprachkanäle",
        "Kein Schreien, Trollen oder Soundboard-Spam. Wer andere absichtlich "
        "stört, wird aus dem Kanal entfernt.",
    ),
    _p(
        "Datenschutz",
        "Teile keine persönlichen Daten von dir oder anderen. Das gilt auch "
        "für Angaben, die du im Rollenspiel erfahren hast.",
    ),
    _p(
        "Profil",
        "Nicknamen, Profilbilder, Banner und Status dürfen keine "
        "unangemessenen Inhalte enthalten.",
    ),
    _p(
        "Bewerbungen",
        "Bewerbungen werden eigenständig verfasst. Abgeschriebene oder mit KI "
        "erzeugte Bewerbungen werden abgelehnt.",
    ),
    _p(
        "Tickets",
        "Erstelle Tickets nur für ernst gemeinte Anliegen. Laufende "
        "Spielsituationen werden nicht über Tickets unterbrochen.",
    ),
    _p(
        "Beschwerden",
        "Beschwerden über andere Spieler gehören in ein Ticket, niemals in den "
        "öffentlichen Chat. Füge nach Möglichkeit Belege bei.",
    ),
    _p(
        "Team",
        "Den Anweisungen des Teams ist Folge zu leisten. Diskussionen über "
        "Strafen gehören in ein Ticket.",
    ),
)

_RP_IC_PARAGRAPHS: tuple[Paragraph, ...] = (
    _p(
        "Roleplay",
        "Realistisches Rollenspiel ist jederzeit Pflicht. Unrealistisches "
        "Verhalten, das die Spielwelt bricht, wird als FailRP gewertet.",
    ),
    _p(
        "FearRP",
        "Habe Angst um das Leben deines Charakters. Wer mit einer Waffe "
        "bedroht wird, verhält sich entsprechend und spielt nicht den Helden.",
    ),
    _p(
        "RDM",
        "Random Deathmatch, also das grundlose Verletzen oder Töten anderer "
        "Spieler, ist verboten. Jeder Angriff braucht einen nachvollziehbaren "
        "Grund im Rollenspiel.",
    ),
    _p(
        "VDM",
        "Fahrzeuge dürfen nicht als Waffe eingesetzt werden. Absichtliches "
        "Überfahren und Rammen ist untersagt.",
    ),
    _p(
        "Combat Logging",
        "Das Verlassen des Spiels während einer laufenden Spielsituation ist "
        "verboten und wird wie eine Flucht vor den Konsequenzen behandelt.",
    ),
    _p(
        "New Life Rule",
        "Nach dem Tod deines Charakters erinnerst du dich nicht mehr an die "
        "Ereignisse davor. Rache für den eigenen Tod ist ausgeschlossen.",
    ),
    _p(
        "Powergaming",
        "Erzwinge keine Handlungen und verschaffe dir keine unrealistischen "
        "Vorteile. Gib deinem Gegenüber immer die Möglichkeit zu reagieren.",
    ),
    _p(
        "Metagaming",
        "Informationen aus Discord, Streams oder anderen Quellen außerhalb des "
        "Spiels dürfen im Rollenspiel nicht verwendet werden.",
    ),
    _p(
        "Charakter",
        "Dein Charakter braucht eine glaubwürdige Geschichte. Niemand ist "
        "unbesiegbar, allwissend oder unbegrenzt vermögend.",
    ),
    _p(
        "Fahrzeug-Roleplay",
        "Fahre realistisch. Sprünge, absichtliche Unfälle und unrealistische "
        "Fahrmanöver gehören nicht in die Spielwelt.",
    ),
    _p(
        "Safezones",
        "In gekennzeichneten Schutzzonen sind Verbrechen jeder Art untersagt.",
    ),
    _p(
        "Cop-Baiting",
        "Das gezielte Provozieren von Einsatzkräften ohne Rollenspielgrund ist "
        "verboten.",
    ),
    _p(
        "Support im Spiel",
        "Laufende Spielsituationen werden nicht durch Support unterbrochen. "
        "Kläre Probleme nach der Situation in einem Ticket.",
    ),
    _p(
        "Bugs und Exploits",
        "Fehler im Spiel dürfen nicht ausgenutzt werden. Melde sie stattdessen "
        "dem Team.",
    ),
    _p(
        "Modifikationen",
        "Cheats, Trainer und unerlaubte Modifikationen führen zum sofortigen "
        "dauerhaften Ausschluss.",
    ),
)

_RP_PENALTIES_IC = _p(
    "Strafen",
    "Verstöße werden je nach Schwere mit Kick, Verwarnung, zeitweiligem oder "
    "dauerhaftem Ausschluss geahndet. Bei schweren Verstößen entfällt die "
    "Abstufung.",
)

_RP_OOC = RuleSet(
    key="rp_ooc",
    name="Roleplay · OOC (Discord)",
    emoji="💬",
    tagline="Discord-Regeln für Rollenspiel-Server",
    length=RuleLength.MEDIUM,
    scope=RuleScope.OOC,
    title="DISCORD REGELWERK",
    intro=(
        "Mit dem Betreten dieses Servers akzeptierst du automatisch alle "
        "folgenden OOC-Regeln. OOC steht für Out of Character und meint alles, "
        "was außerhalb des Spiels passiert."
    ),
    paragraphs=(*_RP_OOC_PARAGRAPHS, _PENALTIES, _DISCORD_TOS),
    closing="Vielen Dank, dass du die Regeln einhältst.",
)

_RP_IC = RuleSet(
    key="rp_ic",
    name="Roleplay · IC (Ingame)",
    emoji="🎭",
    tagline="Ingame-Regeln: FailRP, RDM, VDM, Metagaming",
    length=RuleLength.MEDIUM,
    scope=RuleScope.IC,
    title="IN GAME REGELWERK",
    intro=(
        "Mit dem Betreten des Ingame-Servers akzeptierst du automatisch alle "
        "folgenden IC-Regeln. IC steht für In Character und meint alles, was "
        "dein Charakter im Spiel tut."
    ),
    paragraphs=(*_RP_IC_PARAGRAPHS, _RP_PENALTIES_IC),
    closing="Im Zweifel entscheidet die Rollenspielleitung.",
)

_RP_BEIDES = RuleSet(
    key="rp_komplett",
    name="Roleplay · komplett",
    emoji="🎬",
    tagline="OOC und IC zusammen in einem Regelwerk",
    length=RuleLength.LONG,
    scope=RuleScope.BOTH,
    title="REGELWERK",
    intro=(
        "Dieses Regelwerk gilt für den Discord-Server und für das Spiel. "
        "OOC bezeichnet alles außerhalb des Spiels, IC alles, was dein "
        "Charakter in der Spielwelt tut. Beide Bereiche werden strikt getrennt."
    ),
    paragraphs=(
        *_RP_OOC_PARAGRAPHS,
        *_RP_IC_PARAGRAPHS,
        _PENALTIES,
        _DISCORD_TOS,
    ),
    closing="Im Zweifel entscheidet die Rollenspielleitung.",
)


# --------------------------------------------------------------------------- #
# Register
# --------------------------------------------------------------------------- #

RULESETS: tuple[RuleSet, ...] = (
    # kurz
    _MINIMAL,
    _FREUNDESKREIS,
    _KURZ_STRENG,
    _GAMING_KURZ,
    _VOICE,
    _LERNSERVER,
    _KREATIV,
    # mittel
    _STANDARD,
    _COMMUNITY,
    _GAMING_VOLL,
    _RP_OOC,
    _RP_IC,
    _CREATOR,
    _SUPPORT,
    _BUSINESS,
    _ANIME,
    _SOCIAL,
    _ESPORTS,
    # lang
    _AUSFUEHRLICH,
    _RECHTSSICHER,
    _GROSSSERVER,
    _RP_BEIDES,
)


_BY_KEY = {ruleset.key: ruleset for ruleset in RULESETS}


def get_ruleset(key: str) -> RuleSet | None:
    return _BY_KEY.get(key)


def by_length(length: RuleLength) -> list[RuleSet]:
    return [ruleset for ruleset in RULESETS if ruleset.length is length]


def by_scope(scope: RuleScope) -> list[RuleSet]:
    return [ruleset for ruleset in RULESETS if ruleset.scope is scope]
