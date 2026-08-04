"""HTTP-Endpunkte: Health-Check und OAuth-Callback.

Der ``state``-Wert eines Partner-Handoffs erreicht uns **nicht** ueber das
``on_guild_join``-Event — Discord liefert ihn ausschliesslich an die
Redirect-URI. Deshalb braucht der Bot einen kleinen Webserver.

Der Callback nimmt den Wert entgegen, prueft ihn und merkt den Server vor.
Den eigentlichen Aufbau uebernimmt danach ``on_guild_join``.
"""

from __future__ import annotations

import asyncio
import hmac
import html
import logging
import time
from typing import TYPE_CHECKING

from aiohttp import web

import config
from core import speedrun
from core.builder import BuildMode, ServerBuilder
from core.handover import build_handover
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

    def _check_partner(request: web.Request) -> web.Response | None:
        """Partner-Token pruefen. Gibt eine Fehlerantwort zurueck oder None."""

        expected = config.PREMIUM_PARTNER_TOKEN
        if not expected:
            return web.json_response(
                {"error": "PREMIUM_PARTNER_TOKEN ist nicht gesetzt."}, status=503
            )

        supplied = (request.headers.get("X-Partner-Token") or "").strip()
        # compare_digest: ein zeichenweiser Vergleich verraet ueber die
        # Laufzeit, wie viele Zeichen stimmen.
        if not supplied or not hmac.compare_digest(supplied, expected):
            return web.json_response({"error": "Ungültiges Token."}, status=401)
        return None

    async def _read_user_id(request: web.Request):
        """``user_id`` aus dem Rumpf lesen. (id, None) oder (None, Fehler)."""

        try:
            payload = await request.json()
        except Exception:
            return None, web.json_response({"error": "Kein gültiges JSON."}, status=400)

        raw = str(payload.get("user_id") or "").strip()
        if not raw.isdigit():
            return None, web.json_response({"error": "user_id fehlt."}, status=400)
        return int(raw), None

    async def licence_revoked(request: web.Request) -> web.Response:
        """
        Der University Bot meldet, dass eine Lizenz erloschen ist.

        Ohne diesen Weg wirkt ein Widerruf erst, wenn der
        Zwischenspeicher ablaeuft — und lokale Freischaltungen aus dem
        Master-Key blieben ganz bestehen. Beides zusammen hiesse: im
        Dashboard weggenommen, im Bot weiter aktiv.

        Authentifiziert mit demselben Token wie die Abfrage. Ohne
        gesetztes Token ist der Endpunkt abgeschaltet, nicht offen.
        """

        error = _check_partner(request)
        if error is not None:
            return error

        user_id, error = await _read_user_id(request)
        if error is not None:
            return error

        removed = bot.premium.revoke_user(user_id)
        # Auch den Zwischenspeicher leeren, sonst gilt die Lizenz noch
        # bis zu fuenf Minuten weiter.
        bot.licence.forget(user_id)

        LOGGER.info(
            "Lizenz widerrufen für user=%s — %d lokale Freischaltung(en) entfernt",
            user_id,
            removed,
        )
        return web.json_response({"status": "ok", "removed": removed})

    async def licence_refresh(request: web.Request) -> web.Response:
        """
        Der University Bot meldet, dass sich eine Lizenz geaendert hat.

        Gebraucht wird das vor allem beim *Wieder*-Freigeben. Bisher
        passierte dabei nichts, und das Ergebnis war die schlimmste
        Sorte Fehler: im Dashboard stand "aktiv", im Bot galt weiter
        "nein" — bis zu fuenf Minuten durch den Zwischenspeicher.

        Der Zwischenspeicher wird geleert, damit die naechste Pruefung
        wirklich nachfragt.

        Die lokale Freischaltung aus dem Master-Key wird *nicht*
        wiederhergestellt: die stammte aus einer Key-Eingabe hier und
        gehoert nicht dem University Bot. Wer eine gueltige Lizenz hat,
        bekommt Premium ueber die Abfrage — dafuer reicht das Leeren.
        """

        error = _check_partner(request)
        if error is not None:
            return error

        user_id, error = await _read_user_id(request)
        if error is not None:
            return error

        bot.licence.forget(user_id)
        LOGGER.info("Lizenz aufgefrischt für user=%s", user_id)
        return web.json_response({"status": "ok"})

    # ----------------------------------------------------------------- #
    # Speedrun: das Dashboard laesst hier einen Server bauen
    # ----------------------------------------------------------------- #

    async def speedrun_templates(request: web.Request) -> web.Response:
        """Welche Templates es gibt -- fuer die Auswahl im Dashboard."""

        error = _check_partner(request)
        if error is not None:
            return error

        items = []
        # ``all`` ist eine Property, kein Aufruf -- genau wie ``free``,
        # ``premium`` und ``totals``. Mit Klammern kommt die Liste
        # zurueck und wird dann aufgerufen: TypeError, HTTP 500.
        for template in bot.registry.all:
            items.append(
                {
                    "key": template.key,
                    "name": template.name,
                    "emoji": template.emoji,
                    "tagline": template.tagline,
                    "description": template.description,
                    "premium": bool(template.premium),
                    "accent": template.accent,
                    "highlights": list(template.highlights),
                    "role_count": len(template.roles),
                    "category_count": template.category_count,
                }
            )
        return web.json_response({"templates": items})

    async def speedrun_precheck(request: web.Request) -> web.Response:
        """Ist der Template-Bot auf diesem Server -- und darf er bauen?

        Der University Bot kann das nicht selbst feststellen: er sieht
        nur seine eigene Mitgliedschaft. Ohne diese Frage wuerde der
        Speedrun erst beim Bauen merken, dass der zweite Bot fehlt.
        """

        error = _check_partner(request)
        if error is not None:
            return error

        try:
            payload = await request.json()
        except Exception:
            return web.json_response({"error": "Kein gültiges JSON."}, status=400)

        raw = str(payload.get("guild_id") or "").strip()
        if not raw.isdigit():
            return web.json_response({"error": "guild_id fehlt."}, status=400)

        guild = bot.get_guild(int(raw))
        if guild is None:
            return web.json_response(
                {
                    "present": False,
                    "can_manage": False,
                    "detail": "Der Template-Bot ist nicht auf diesem Server.",
                }
            )

        me = guild.me
        perms = me.guild_permissions if me is not None else None
        can_manage = bool(
            perms
            and (
                perms.administrator
                or (perms.manage_roles and perms.manage_channels)
            )
        )

        return web.json_response(
            {
                "present": True,
                "can_manage": can_manage,
                "guild_name": guild.name,
                "detail": (
                    ""
                    if can_manage
                    else "Dem Template-Bot fehlen Rechte für Rollen und Kanäle."
                ),
            }
        )

    async def speedrun_start(request: web.Request) -> web.Response:
        """Bau starten. Antwortet sofort, gebaut wird im Hintergrund.

        Ein Bau dauert je nach Template ueber eine Minute. Wuerde hier
        auf das Ergebnis gewartet, liefe die HTTP-Anfrage in einen
        Timeout und das Dashboard wuesste nicht, ob der Bau laeuft oder
        gescheitert ist.
        """

        error = _check_partner(request)
        if error is not None:
            return error

        try:
            payload = await request.json()
        except Exception:
            return web.json_response({"error": "Kein gültiges JSON."}, status=400)

        raw_guild = str(payload.get("guild_id") or "").strip()
        if not raw_guild.isdigit():
            return web.json_response({"error": "guild_id fehlt."}, status=400)
        guild_id = int(raw_guild)

        template_key = str(payload.get("template") or "").strip()
        template = bot.registry.get(template_key)
        if template is None:
            return web.json_response(
                {"error": f"Unbekanntes Template: {template_key!r}"}, status=400
            )

        guild = bot.get_guild(guild_id)
        if guild is None:
            return web.json_response(
                {
                    "error": "Der Template-Bot ist nicht auf diesem Server.",
                    "code": "bot_missing",
                },
                status=404,
            )

        if speedrun.STORE.running(guild_id):
            return web.json_response(
                {"error": "Für diesen Server läuft bereits ein Bau.",
                 "code": "already_running"},
                status=409,
            )

        # Der Bot baut sonst gleichzeitig zweimal am selben Server.
        if guild_id in bot.active_builds:
            return web.json_response(
                {"error": "Für diesen Server läuft bereits ein Bau.",
                 "code": "already_running"},
                status=409,
            )

        options = payload.get("options") or {}
        write_intros = bool(options.get("intros", True))
        rebuild = bool(options.get("rebuild", False))

        job = speedrun.STORE.start(guild_id, template.key)
        job.log(f"Speedrun gestartet — Template »{template.name}«")

        task = asyncio.create_task(
            _run_speedrun(
                bot,
                guild,
                template,
                job,
                write_intros=write_intros,
                rebuild=rebuild,
            )
        )
        speedrun.STORE.attach(guild_id, task)

        # run_id mitgeben: nur damit kann das Dashboard spaeter
        # erkennen, ob der Bau, den es sieht, auch der ist, den es
        # gestartet hat.
        return web.json_response(
            {"status": "started", "guild_id": str(guild_id), "run_id": job.run_id}
        )

    async def speedrun_cancel(request: web.Request) -> web.Response:
        """Einen laufenden Bau abbrechen.

        Der Server bleibt halb gebaut stehen; das steht auch so im Log.
        Ohne diesen Weg haengt ein blockierter Bau fuer immer und
        sperrt jeden zweiten Versuch.
        """

        error = _check_partner(request)
        if error is not None:
            return error

        raw_guild = request.match_info.get("guild_id", "")
        if not raw_guild.isdigit():
            return web.json_response({"error": "guild_id fehlt."}, status=400)

        guild_id = int(raw_guild)
        stopped = speedrun.STORE.cancel(guild_id)
        # Auch die Sperre loesen, sonst bleibt der Server als
        # "wird gerade gebaut" markiert.
        bot.active_builds.discard(guild_id)

        return web.json_response({"cancelled": stopped})

    async def speedrun_status(request: web.Request) -> web.Response:
        """Fortschritt abfragen. ``since`` = schon gelesene Zeilen."""

        error = _check_partner(request)
        if error is not None:
            return error

        raw_guild = request.match_info.get("guild_id", "")
        if not raw_guild.isdigit():
            return web.json_response({"error": "guild_id fehlt."}, status=400)

        job = speedrun.STORE.get(int(raw_guild))
        if job is None:
            return web.json_response({"state": "none", "lines": [], "line_count": 0})

        try:
            since = int(request.query.get("since", "0"))
        except ValueError:
            since = 0

        return web.json_response(job.as_dict(since=max(since, 0)))

    app = web.Application()
    app.router.add_get("/", status)
    app.router.add_get("/health", status)
    app.router.add_get("/oauth/callback", oauth_callback)
    app.router.add_post("/internal/licence-revoked", licence_revoked)
    app.router.add_post("/internal/licence-refresh", licence_refresh)
    app.router.add_post("/internal/speedrun/precheck", speedrun_precheck)
    app.router.add_get("/internal/speedrun/templates", speedrun_templates)
    app.router.add_post("/internal/speedrun/start", speedrun_start)
    app.router.add_post("/internal/speedrun/{guild_id}/cancel", speedrun_cancel)
    app.router.add_get("/internal/speedrun/{guild_id}", speedrun_status)

    runner = web.AppRunner(app)
    await runner.setup()

    # Auf IPv4 *und* IPv6 lauschen.
    #
    # Railways privates Netz (<dienst>.railway.internal) ist IPv6-only.
    # Mit "0.0.0.0" horcht der Server nur auf IPv4, und jeder Aufruf des
    # University Bots endet in "connection refused" -- im Dashboard als
    # 502 sichtbar, obwohl beide Dienste laufen. Genau das ist passiert:
    # /precheck ging (der Hauptbot beantwortet es selbst), /templates
    # nicht (das muss hierher).
    #
    # host=None statt "::": asyncio setzt auf einem "::"-Socket
    # IPV6_V6ONLY, dann waere IPv4 tot -- und damit der Health-Check und
    # die oeffentliche Domain. Ohne host legt aiohttp pro Familie einen
    # eigenen Socket an, also beide.
    site = web.TCPSite(runner, None, config.PORT)
    await site.start()

    LOGGER.info("Webserver auf Port %s", config.PORT)
    if is_enabled():
        LOGGER.info("Partner-Handshake aktiv (Quelle: university-bot)")
    else:
        LOGGER.warning(
            "PARTNER_HANDSHAKE_SECRET fehlt — automatische Einrichtung ist aus"
        )
    return runner


# --------------------------------------------------------------------------- #
# Speedrun: der eigentliche Bau
# --------------------------------------------------------------------------- #


async def _run_speedrun(
    bot: ArchitectBot,
    guild,
    template,
    job: speedrun.Job,
    *,
    write_intros: bool,
    rebuild: bool,
) -> None:
    """Baut den Server und schreibt dabei ins Job-Log.

    Laeuft als Hintergrund-Task, damit die HTTP-Antwort sofort raus
    kann. Jeder Fehler landet im Job statt in einem Traceback, den
    niemand sieht -- das Dashboard zeigt ihn dann im Terminal an.
    """

    guild_id = guild.id
    bot.active_builds.add(guild_id)

    try:
        builder = ServerBuilder(guild, template)

        try:
            builder.preflight()
        except Exception as exc:  # BuildError und alles andere
            job.state = speedrun.JobState.FAILED
            job.error = str(exc)
            job.finished = time.time()
            job.log(f"Abbruch: {exc}", level="error")
            return

        job.total = 1 + template.category_count + (
            template.category_count if write_intros else 0
        )
        job.log(f"Vorprüfung ok — {template.category_count} Kategorien geplant")

        async def progress(label: str, step: int, total: int) -> None:
            job.step = step
            job.total = total
            job.log(f"[{step}/{total}] {label}")

        # Eine Zeile pro Rolle und pro Kanal. Ohne die kommt nur alle
        # paar Sekunden etwas an -- der Fortschritt meldet sich nur je
        # Kategorie, und bei vierzehn Kanaelen darin steht das Terminal
        # fuenf Sekunden still. Es sieht dann aus, als haenge der Bau.
        async def detail(line: str) -> None:
            job.log(line)

        mode = BuildMode.REBUILD if rebuild else BuildMode.EXTEND
        report = await builder.apply(
            mode, progress=progress, write_intros=write_intros, detail=detail
        )

        # Was der University Bot danach braucht: nicht nur die Namen,
        # sondern die Zuordnung nach Zweck. Welcher Kanal der
        # Verify-Kanal ist, steht in der Template-Definition
        # (widget=verify) -- der Hauptbot koennte es am Namen nicht
        # erkennen, weil der in Small Caps mit Emoji-Praefix steht.
        job.result = {
            "roles_created": report.roles_created,
            "channels_created": report.channels_created,
            "categories_created": report.categories_created,
            "warnings": list(report.warnings),
            **build_handover(guild, template, builder.created_roles),
        }

        job.log(
            f"Fertig — {report.roles_created} Rollen, "
            f"{report.categories_created} Kategorien, "
            f"{report.channels_created} Kanäle angelegt",
            level="success",
        )
        for warning in report.warnings:
            job.log(f"Hinweis: {warning}", level="warn")

        job.state = speedrun.JobState.DONE
        job.finished = time.time()

    except Exception as exc:
        LOGGER.exception("Speedrun fehlgeschlagen für guild=%s", guild_id)
        job.state = speedrun.JobState.FAILED
        job.error = f"{type(exc).__name__}: {exc}"
        job.finished = time.time()
        job.log(f"Fehler: {type(exc).__name__}: {exc}", level="error")
    finally:
        bot.active_builds.discard(guild_id)
