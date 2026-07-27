#!/usr/bin/env python3
"""Inspect templates from the terminal — no Discord connection needed.

    python tools/preview.py                 # overview of every template
    python tools/preview.py community       # full channel tree
    python tools/preview.py rp --json       # machine readable
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import config  # noqa: E402
from core.registry import TemplateRegistry  # noqa: E402
from core.schema import ChannelKind, Template, TemplateError  # noqa: E402
from core.small_caps import slugify  # noqa: E402

ICONS = {
    ChannelKind.TEXT: "💬",
    ChannelKind.VOICE: "🔊",
    ChannelKind.FORUM: "🧵",
    ChannelKind.NEWS: "📢",
    ChannelKind.STAGE: "🎤",
}


def overview(registry: TemplateRegistry) -> None:
    print(f"\n  {'Template':<24}{'Typ':<10}{'Kat.':>6}{'Kanäle':>8}{'Text':>7}{'Voice':>7}{'Rollen':>8}")
    print("  " + "─" * 70)
    for template in registry:
        print(
            f"  {template.emoji} {template.name:<22}"
            f"{'premium' if template.premium else 'free':<10}"
            f"{template.category_count:>6}{template.channel_count:>8}"
            f"{template.text_count:>7}{template.voice_count:>7}{len(template.roles):>8}"
        )
    totals = registry.totals
    print("  " + "─" * 70)
    print(
        f"  {totals['templates']} Templates · {totals['categories']} Kategorien · "
        f"{totals['channels']} Kanäle · {totals['voice']} Voice\n"
    )


def detail(template: Template) -> None:
    print(f"\n  {template.emoji}  {template.name}")
    print(f"  {'💎 Premium' if template.premium else '🆓 Free'} · {template.tagline}")
    print("  " + "─" * 70)
    print(f"  {template.description}\n")

    for line in template.highlights:
        print(f"    › {line}")
    print()

    for category in template.categories:
        print(f"  📂 {category.display_name}   [{category.visibility.value}]")
        for channel in category.channels:
            icon = ICONS.get(channel.kind, "•")
            extras = []
            if channel.user_limit:
                extras.append(f"max {channel.user_limit}")
            if channel.slowmode:
                extras.append(f"slow {channel.slowmode}s")
            if channel.visibility:
                extras.append(channel.visibility.value)
            suffix = f"  ({', '.join(extras)})" if extras else ""
            print(f"       {icon} {channel.display_name}{suffix}")
        print()

    if template.roles:
        print("  🎭 Zusatzrollen")
        for role in template.roles:
            print(f"       {role.display_name}  [{role.tier.value}]")
        print()

    print(
        f"  Σ {template.category_count} Kategorien · {template.channel_count} Kanäle "
        f"({template.text_count} Text, {template.voice_count} Voice)\n"
    )


def as_json(template: Template) -> None:
    payload = {
        "key": template.key,
        "name": template.name,
        "premium": template.premium,
        "stats": {
            "categories": template.category_count,
            "channels": template.channel_count,
            "voice": template.voice_count,
        },
        "categories": [
            {
                "display_name": category.display_name,
                "slug": slugify(category.display_name),
                "visibility": category.visibility.value,
                "channels": [
                    {
                        "display_name": channel.display_name,
                        "slug": slugify(channel.display_name),
                        "kind": channel.kind.value,
                        "visibility": category.visibility_for(channel).value,
                        "user_limit": channel.user_limit,
                        "topic": channel.topic,
                    }
                    for channel in category.channels
                ],
            }
            for category in template.categories
        ],
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def main() -> int:
    parser = argparse.ArgumentParser(description="Template-Vorschau")
    parser.add_argument("template", nargs="?", help="Template-Key (z. B. community)")
    parser.add_argument("--json", action="store_true", help="Als JSON ausgeben")
    args = parser.parse_args()

    try:
        registry = TemplateRegistry(config.TEMPLATE_DIR).load()
    except TemplateError as exc:
        print(f"\n  ❌  {exc}\n", file=sys.stderr)
        return 1

    if not args.template:
        overview(registry)
        return 0

    template = registry.get(args.template)
    if template is None:
        available = ", ".join(t.key for t in registry)
        print(f"\n  ❌  '{args.template}' unbekannt.\n      Verfügbar: {available}\n", file=sys.stderr)
        return 1

    as_json(template) if args.json else detail(template)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
