"""Verhalten bei Discords Rate-Limits.

Der Builder drosselt sich mit einem festen Abstand zwischen den Mutationen.
Das ist eine Schaetzung: laeuft parallel ein anderer Bot oder aendert Discord
seine Buckets, kommt trotzdem ein 429. Ohne Wiederholung faellt dann ein
einzelner Kanal aus — mitten in einem sonst erfolgreichen Aufbau.

Geprueft wird, dass ``with_retry``

* nur bei 429 wiederholt und jeden anderen Fehler sofort durchreicht,
* Discords ``Retry-After`` respektiert statt blind zu warten,
* nicht endlos wiederholt und
* die Wartezeit nach oben begrenzt.
"""

from __future__ import annotations

import sys
from pathlib import Path

import discord
import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.builder import (
    MAX_RETRY_WAIT,
    RETRY_ATTEMPTS,
    with_retry,
)


class FakeResponse:
    def __init__(self, status: int = 429, headers: dict | None = None) -> None:
        self.status = status
        self.reason = "Too Many Requests" if status == 429 else "Fehler"
        self.headers = headers or {}


def http_error(status: int = 429, retry_after: str | None = None):
    headers = {"Retry-After": retry_after} if retry_after is not None else {}
    response = FakeResponse(status, headers)
    if status == 403:
        return discord.Forbidden(response, "verboten")
    return discord.HTTPException(response, "gedrosselt")


@pytest.fixture(autouse=True)
def no_real_waiting(monkeypatch):
    """Die Wartezeiten mitschreiben statt sie abzusitzen."""

    waited: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        waited.append(seconds)

    import core.builder as builder

    monkeypatch.setattr(builder.asyncio, "sleep", fake_sleep)
    return waited


class TestWithRetry:
    async def test_returns_the_result_without_retrying(self, no_real_waiting):
        calls = []

        async def action():
            calls.append(1)
            return "fertig"

        assert await with_retry(action) == "fertig"
        assert len(calls) == 1
        assert not no_real_waiting, "Ohne Fehler darf nicht gewartet werden"

    async def test_retries_on_429_and_then_succeeds(self, no_real_waiting):
        """Der eigentliche Zweck: ein gedrosselter Aufruf geht doch noch durch."""

        attempts = []

        async def action():
            attempts.append(1)
            if len(attempts) < 2:
                raise http_error(429, "0.5")
            return "fertig"

        assert await with_retry(action, what="Testkanal") == "fertig"
        assert len(attempts) == 2
        assert no_real_waiting == [0.5], "Retry-After wurde nicht beachtet"

    async def test_respects_retry_after_header(self, no_real_waiting):
        async def action():
            raise http_error(429, "3.25")

        with pytest.raises(discord.HTTPException):
            await with_retry(action)

        assert all(w == 3.25 for w in no_real_waiting)

    async def test_falls_back_to_exponential_backoff(self, no_real_waiting):
        """Ohne Header waechst die Wartezeit, statt sofort zu haemmern."""

        async def action():
            raise http_error(429)

        with pytest.raises(discord.HTTPException):
            await with_retry(action, attempts=4)

        assert no_real_waiting == [1.0, 2.0, 4.0]

    async def test_caps_absurd_waiting_times(self, no_real_waiting):
        """Bei globalen Limits nennt Discord gelegentlich Minutenwerte."""

        async def action():
            raise http_error(429, "9999")

        with pytest.raises(discord.HTTPException):
            await with_retry(action)

        assert all(w <= MAX_RETRY_WAIT for w in no_real_waiting)

    async def test_ignores_an_unreadable_header(self, no_real_waiting):
        async def action():
            raise http_error(429, "bald")

        with pytest.raises(discord.HTTPException):
            await with_retry(action, attempts=2)

        assert no_real_waiting == [1.0], "Kaputter Header muss zum Backoff fuehren"

    async def test_gives_up_after_the_configured_attempts(self, no_real_waiting):
        attempts = []

        async def action():
            attempts.append(1)
            raise http_error(429, "0.1")

        with pytest.raises(discord.HTTPException):
            await with_retry(action)

        assert len(attempts) == RETRY_ATTEMPTS
        assert len(no_real_waiting) == RETRY_ATTEMPTS - 1

    async def test_other_http_errors_are_not_retried(self, no_real_waiting):
        """Ein 403 wird durch Warten nicht besser."""

        attempts = []

        async def action():
            attempts.append(1)
            raise http_error(403)

        with pytest.raises(discord.Forbidden):
            await with_retry(action)

        assert len(attempts) == 1, "Ein Berechtigungsfehler wurde wiederholt"
        assert not no_real_waiting

    async def test_unexpected_exceptions_pass_straight_through(self, no_real_waiting):
        """Ein Programmierfehler darf nicht als Rate-Limit missverstanden werden."""

        async def action():
            raise ValueError("kaputt")

        with pytest.raises(ValueError):
            await with_retry(action)

        assert not no_real_waiting

    async def test_logs_the_operation_name(self, no_real_waiting, caplog):
        """Im Log muss stehen, *was* gedrosselt wurde."""

        async def action():
            raise http_error(429, "0.1")

        with caplog.at_level("WARNING"), pytest.raises(discord.HTTPException):
            await with_retry(action, what="Textkanal ᴀʟʟɢᴇᴍᴇɪɴ")

        assert "Textkanal" in caplog.text
        assert "Rate-Limit" in caplog.text
