"""Central configuration for the Discord Architect bot.

Everything is read from environment variables so the exact same image can run
locally, on Railway, Docker, or any other container host without code changes.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")


def _flag(name: str, default: bool = False) -> bool:
    """Read a human friendly boolean environment variable."""

    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on", "y"}


def _int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        return default


# --------------------------------------------------------------------------- #
# Discord
# --------------------------------------------------------------------------- #

DISCORD_TOKEN: str | None = os.getenv("DISCORD_TOKEN") or os.getenv("DISCORD_BOT_TOKEN")
COMMAND_PREFIX: str = os.getenv("COMMAND_PREFIX", "!")
DISCORD_GUILD_ID: str | None = os.getenv("DISCORD_GUILD_ID")

# Prefix commands (`!start`) need the message content intent, and the automatic
# join role needs the members intent. Both are opt-in so a fresh deployment can
# still connect and expose `/start` before the Developer Portal is configured.
ENABLE_PRIVILEGED_INTENTS: bool = _flag("ENABLE_PRIVILEGED_INTENTS", default=True)

# --------------------------------------------------------------------------- #
# Premium
# --------------------------------------------------------------------------- #

PREMIUM_KEY: str = os.getenv("PREMIUM_KEY", "Vexo x Fufi KEY 2354")

# Optional comma separated list of additional accepted keys.
PREMIUM_EXTRA_KEYS: tuple[str, ...] = tuple(
    key.strip() for key in os.getenv("PREMIUM_EXTRA_KEYS", "").split(",") if key.strip()
)

# When true a single unlock enables premium for the whole guild instead of only
# for the person who entered the key.
PREMIUM_UNLOCKS_GUILD: bool = _flag("PREMIUM_UNLOCKS_GUILD", default=False)

PREMIUM_STORE: Path = Path(
    os.getenv("PREMIUM_STORE", str(BASE_DIR / "data" / "premium.json"))
).expanduser()

# --------------------------------------------------------------------------- #
# Runtime
# --------------------------------------------------------------------------- #

PORT: int = _int("PORT", 8080)
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
HEALTH_SERVER: bool = _flag("HEALTH_SERVER", default=True)

TEMPLATE_DIR: Path = BASE_DIR / "templates"

# --------------------------------------------------------------------------- #
# Branding
# --------------------------------------------------------------------------- #

BRAND_NAME: str = os.getenv("BRAND_NAME", "Discord Architect")
BRAND_TAGLINE: str = os.getenv("BRAND_TAGLINE", "Server-Templates in Sekunden")
BRAND_FOOTER: str = os.getenv("BRAND_FOOTER", "Discord Architect • Vexo × Fufi")

# Accent colours used by the Components V2 containers.
COLOR_BRAND = 0x5865F2
COLOR_PREMIUM = 0xF5B301
COLOR_SUCCESS = 0x3BA55D
COLOR_DANGER = 0xED4245
COLOR_NEUTRAL = 0x2B2D31
COLOR_INFO = 0x00A8FC

SETUP_REASON = f"{BRAND_NAME}: Server-Template angewendet"
