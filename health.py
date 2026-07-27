"""Tiny HTTP health endpoint.

Hosts like Railway expect a process to answer on ``$PORT``; without it the
container can be killed for "not responding". The Discord connection itself
runs over the gateway and is unaffected by this server.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiohttp import web

import config

if TYPE_CHECKING:
    from bot import ArchitectBot

LOGGER = logging.getLogger("architect.health")

__all__ = ["start_health_server"]


async def start_health_server(bot: "ArchitectBot") -> web.AppRunner:
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
            }
        )

    app = web.Application()
    app.router.add_get("/", status)
    app.router.add_get("/health", status)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", config.PORT)
    await site.start()
    LOGGER.info("Health-Server auf Port %s", config.PORT)
    return runner
