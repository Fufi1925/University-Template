"""HTTP-Endpunkte: Health-Check und OAuth-Callback.

Der ``state``-Wert eines Partner-Handoffs erreicht uns **nicht** ueber das
``on_guild_join``-Event — Discord liefert ihn ausschliesslich an die
Redirect-URI. Deshalb braucht der Bot einen kleinen Webserver.

Der Callback nimmt den Wert entgegen, prueft ihn und merkt den Server vor.
Den eigentlichen Aufbau uebernimmt danach ``on_guild_join``.
"""

from __future__ import annotations

import html
import logging
from typing import TYPE_CHECKING

from aiohttp import web

import config
from core.handshake import is_enabled, read_state

if TYPE_CHECKING:
    from bot import ArchitectBot

LOGGER = logging.getLogger("architect.web")

__all__ = ["start_web_server"]


# --------------------------------------------------------------------------- #
# Antwortseiten
# --------------------------------------------------------------------------- #

_PAGE = """<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  :root {{ color-scheme: dark; }}
  body {{
    margin: 0; min-height: 100vh; display: grid; place-items: center;
    background: #1a1b1e; color: #e6e7ea;
    font: 16px/1.6 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  }}
  main {{
    max-width: 30rem; padding: 2.5rem; text-align: center;
    background: #232428; border-radius: 14px;
    border-top: 3px solid {accent};
  }}
  h1 {{ margin: 0 0 .75rem; font-size: 1.35rem; }}
  p  {{ margin: 0 0 .5rem; color: #b6b9bf; }}
  .small {{ font-size: .85rem; color: #7d818a; margin-top: 1.5rem; }}
</style>
</head>
<body>
  <main>
    <h1>{title}</h1>
    <p>{message}</p>
    <p class="small">{footer}</p>
  </main>
</body>
</html>
"""


def _page(title: str, message: str, *, accent: str, status: int) -> web.Response:
    body = _PAGE.format(
        title=html.escape(title),
        message=html.escape(message),
        accent=accent,
        footer=html.escape(config.BRAND_NAME),
    )
    return web.Response(text=body, content_type="text/html", status=status)


def _ok(title: str, message: str) -> web.Response:
    return _page(title, message, accent="#3ba55d", status=200)


def _problem(title: str, message: str, status: int = 400) -> web.Response:
    return _page(title, message, accent="#ed4245", status=status)


# --------------------------------------------------------------------------- #
# Server
# --------------------------------------------------------------------------- #

async def start_web_server(bot: ArchitectBot) -> web.AppRunner:
    async def status(_: web.Request) -> web.Response:
        totals = bot.registry.totals
        return web.json_response(
            {
                "status": "online" if bot.is_ready() else "starting",
                "service": "discord-architect",
                "bot": str(bot.user) if bot.user else None,
                "guilds": len(bot.guilds),
                "latency_ms": round(bot.latency * 1000) if bot.latency else None,
                "templates": totals["templates"],
                "channels": totals["channels"],
                "active_builds": len(bot.active_builds),
                "partner_handshake": is_enabled(),
                "pending_handoffs": len(bot.pending_handoffs),
                "configured_guilds": len(bot.setup_ledger),
            }
        )

    async def oauth_callback(request: web.Request) -> web.Response:
        """Discord leitet den Nutzer nach der Autorisierung hierher."""

        query = request.query

        # Der Nutzer hat abgebrochen — das ist kein Fehler unsererseits.
        if error := query.get("error"):
            LOGGER.info("OAuth abgebrochen: %s", error)
            return _problem(
                "Abgebrochen",
                "Die Autorisierung wurde abgebrochen. Du kannst das Fenster schließen.",
                status=200,
            )

        handoff = read_state(query.get("state"))

        if handoff is None:
            # Entweder ein normaler Beitritt ohne Partner-Token oder ein
            # ungueltiges. Beides ist harmlos: der Bot ist eingeladen, nur
            # die Automatik entfaellt.
            if not is_enabled():
                LOGGER.info("OAuth-Callback ohne aktives Handshake-Secret")
            else:
                LOGGER.info("OAuth-Callback ohne gültigen Handoff-Token")
            return _ok(
                "Bot hinzugefügt",
                "Der Bot ist auf deinem Server. Richte ihn mit "
                f"{config.COMMAND_PREFIX}start ein.",
            )

        # Discord haengt guild_id separat an. Weicht sie vom Token ab, wurde
        # ein fremdes Token an eine andere Einladung geklebt.
        raw_guild = query.get("guild_id")
        if raw_guild:
            try:
                if int(raw_guild) != handoff.guild_id:
                    LOGGER.warning(
                        "Handoff verworfen: Token nennt Guild %s, Discord meldet %s",
                        handoff.guild_id,
                        raw_guild,
                    )
                    return _problem(
                        "Nicht zuzuordnen",
                        "Der Einladungslink gehört zu einem anderen Server.",
                    )
            except ValueError:
                return _problem("Ungültige Anfrage", "Die Server-ID ist unlesbar.")

        bot.pending_handoffs.add(handoff)

        # Der Bot kann bereits auf dem Server sein: dann kam on_guild_join
        # zuerst und hat nichts vorgefunden. Hier nachziehen.
        guild = bot.get_guild(handoff.guild_id)
        if guild is not None:
            LOGGER.info(
                "Guild %s war schon da — Einrichtung wird jetzt angestoßen",
                handoff.guild_id,
            )
            bot.schedule_partner_setup(guild)

        name = handoff.guild_name or "deinem Server"
        return _ok(
            "Alles bereit",
            f"Der Bot richtet {name} gleich automatisch ein. "
            "Du kannst dieses Fenster schließen.",
        )

    app = web.Application()
    app.router.add_get("/", status)
    app.router.add_get("/health", status)
    app.router.add_get("/oauth/callback", oauth_callback)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", config.PORT)
    await site.start()

    LOGGER.info("Webserver auf Port %s", config.PORT)
    if is_enabled():
        LOGGER.info("Partner-Handshake aktiv (Quelle: university-bot)")
    else:
        LOGGER.warning(
            "PARTNER_HANDSHAKE_SECRET fehlt — automatische Einrichtung ist aus"
        )
    return runner
