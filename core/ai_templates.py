"""Regelbasierter Vorlagen-Assistent fuer ``/template ai``.

Ohne Netz und ohne externe API: Die Beschreibung wird nach Themen
durchsucht, das am besten passende Template liefert die Basis, und bis zu
zwei weitere Themen steuern zusaetzliche Kategorien und Rollen bei. Das
Ergebnis ist ein ganz normales :class:`~core.schema.Template` — dieselbe
Validierung, dieselbe Vorschau, derselbe Builder wie bei den fertigen
Vorlagen.

Bewusst kein Sprachmodell: ein LLM-Aufruf hinge an einem API-Key, einem
Anbieter und an Antworten, die mal gueltiges JSON sind und mal nicht. Die
Regeln hier sind deterministisch, kosten nichts und lassen sich testen.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .registry import TemplateRegistry
from .schema import Template

__all__ = ["TOPICS", "Topic", "compose_template", "detect_topics"]

#: Mehr Themen als diese werden ignoriert — die Vorlage soll eine klare
#: Linie haben, kein Sammelsurium aus allen 14 Templates sein.
MAX_TOPICS = 3

#: Kategorien-Grenze als letztes Sicherheitsnetz; das Schema erzwingt
#: ohnehin Discords Limit von 50.
MAX_CATEGORIES = 50


@dataclass(frozen=True, slots=True)
class Topic:
    """Ein erkennbares Thema und das Template, das es abdeckt."""

    key: str
    label: str
    template_key: str
    keywords: tuple[str, ...]


# Reihenfolge ist Bedeutung: das erste passende Thema wird zur Basis der
# Vorlage. Die Keywords sind bewusst markant — "team", "chat" oder "server"
# stehen in fast jeder Beschreibung und wuerden nur Rauschen erzeugen.
TOPICS: tuple[Topic, ...] = (
    Topic(
        "rp",
        "Rollenspiel",
        "rp",
        ("rollenspiel", "roleplay", "rp", "fraktion", "behörde", "failrp", "powergaming"),
    ),
    Topic(
        "gaming",
        "Gaming",
        "gaming",
        ("gaming", "gamer", "zock", "spiele", "game", "playstation", "xbox", "nintendo"),
    ),
    Topic(
        "esports",
        "Esports",
        "esports",
        ("esport", "e-sport", "liga", "turnier", "scrim", "wettkampf"),
    ),
    Topic(
        "clan",
        "Clan",
        "clan",
        ("clan", "gilde", "squad"),
    ),
    Topic(
        "musik",
        "Musik",
        "music",
        ("musik", "music", "dj", "band", "beats", "gesang", "konzert"),
    ),
    Topic(
        "anime",
        "Anime & Manga",
        "anime",
        ("anime", "manga", "weeb", "seasonal", "japan"),
    ),
    Topic(
        "study",
        "Study & University",
        "study",
        ("studium", "schule", "uni", "universität", "lernen", "student", "pomodoro", "seminar"),
    ),
    Topic(
        "creator",
        "Creator Studio",
        "creator",
        ("creator", "youtube", "twitch", "stream", "content", "video", "podcast"),
    ),
    Topic(
        "business",
        "Business",
        "business",
        ("business", "firma", "unternehmen", "kunde", "büro", "abteilung", "startup"),
    ),
    Topic(
        "support",
        "Support",
        "support",
        ("support", "ticket", "hilfe", "service", "kundendienst"),
    ),
    Topic(
        "social",
        "Social",
        "social",
        ("social", "lounge", "freunde", "quatschen", "treff"),
    ),
    Topic(
        "dev",
        "Entwickler",
        "dev",
        ("developer", "entwickler", "code", "programmier", "open source", "github", "dev"),
    ),
)


def _matches(keyword: str, lowered: str) -> bool:
    """Kurze Keywords nur als ganzes Wort, lange als Teilstring.

    ``uni`` darf nicht in ``community`` anschlagen und ``dj`` nicht in
    ``adjacent`` — sonst trifft jede Beschreibung jedes Thema. Bei laengeren
    Woertern ist der Teilstring gewollt: ``zock`` findet ``zocken``,
    ``stream`` findet ``streaming``.
    """

    if len(keyword) <= 3:
        return bool(re.search(rf"(?<![a-z0-9äöüß]){re.escape(keyword)}(?![a-z0-9äöüß])", lowered))
    return keyword in lowered


def detect_topics(text: str) -> list[Topic]:
    """Die Themen einer Beschreibung, sortiert nach erstem Auftauchen."""

    lowered = text.lower()
    hits: list[tuple[int, Topic]] = []
    for topic in TOPICS:
        positions = [
            match.start()
            for keyword in topic.keywords
            if (match := re.search(re.escape(keyword), lowered)) is not None
            and _matches(keyword, lowered)
        ]
        if positions:
            hits.append((min(positions), topic))
    hits.sort(key=lambda pair: pair[0])
    return [topic for _, topic in hits[:MAX_TOPICS]]


def _find_base(registry: TemplateRegistry, topics: list[Topic]) -> Template:
    """Das Basistemplate: erstes erkanntes Thema, sonst Community."""

    for topic in topics:
        template = registry.get(topic.template_key)
        if template is not None:
            return template
    community = registry.get("community")
    if community is not None:
        return community
    return registry.all[0]


def compose_template(
    registry: TemplateRegistry, *, name: str, description: str
) -> Template:
    """Stellt aus Name + Beschreibung eine vollstaendige Vorlage zusammen.

    Wirft :class:`TemplateError`, wenn die Kombination die Discord-Limits
    sprengen wuerde — dieselbe Pruefung wie beim Laden jeder JSON-Vorlage.
    """

    topics = detect_topics(description)
    base = _find_base(registry, topics)

    categories = list(base.categories)
    roles = list(base.roles)
    known_categories = {category.display_name for category in categories}
    known_roles = {role.key for role in roles}

    # Zusaetzliche Themen steuern ihre Kategorien und Rollen bei, soweit
    # keine Namenskollision mit der Basis besteht. Die Eingangsschleuse,
    # Info- und Teambereiche kommen immer aus der Basis.
    for topic in topics[1:]:
        extra = registry.get(topic.template_key)
        if extra is None or extra.key == base.key:
            continue
        for category in extra.categories:
            if category.display_name in known_categories:
                continue
            categories.append(category)
            known_categories.add(category.display_name)
            if len(categories) >= MAX_CATEGORIES:
                break
        for role in extra.roles:
            if role.key in known_roles:
                continue
            roles.append(role)
            known_roles.add(role.key)

    channel_count = sum(len(category.channels) for category in categories)
    highlights = [
        f"Basis: {base.name}",
        f"Erkannte Themen: {', '.join(topic.label for topic in topics)}"
        if topics
        else "Kein Thema erkannt — Basis ist die Community-Vorlage",
        f"{len(categories)} Kategorien · {channel_count} Kanäle · {len(roles)} eigene Rollen",
    ]

    template = Template(
        key="ai",
        name=name.strip() or "Mein Server",
        emoji=base.emoji,
        tagline="Aus deiner Beschreibung zusammengestellt",
        description=description.strip() or base.description,
        premium=False,
        accent=base.accent,
        highlights=tuple(highlights),
        categories=tuple(categories),
        roles=tuple(roles),
        extends_base_roles=True,
    )
    template.validate()
    return template
