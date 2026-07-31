"""Partner-Handshake: Token-Prüfung, Speicher und automatische Einrichtung.

Diese Funktion entscheidet, ob ein fremder Server automatisch umgebaut wird.
Ein Fehler hier bedeutet nicht „Feature kaputt", sondern „beliebige Person
lässt unseren Bot einen fremden Server umbauen". Entsprechend gründlich
prüft diese Datei — inklusive der Angriffe, gegen die die Signatur schützt.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import sys
import time
from pathlib import Path
from typing import Any

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.handoff_store import PendingHandoffs, SetupLedger
from core.handshake import (
    MAX_AGE,
    SOURCE,
    Handoff,
    is_enabled,
    read_state,
    sign_state,
)

SECRET = "test-secret-mit-genug-entropie-1234567890"


@pytest.fixture(autouse=True)
def _secret(monkeypatch):
    """Standardmäßig ist die Automatik in den Tests aktiv."""

    monkeypatch.setenv("PARTNER_HANDSHAKE_SECRET", SECRET)


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _token(payload: dict, *, secret: str = SECRET) -> str:
    """Ein Token von Hand bauen — auch mit absichtlich kaputtem Inhalt."""

    body = _b64(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = _b64(
        hmac.new(secret.encode(), body.encode("ascii"), hashlib.sha256).digest()
    )
    return f"{body}.{signature}"


def _payload(**overrides) -> dict:
    base = {
        "g": "123456789012345678",
        "u": "987654321098765432",
        "t": int(time.time()),
        "src": SOURCE,
        "guild_name": "Mein Server",
    }
    base.update(overrides)
    return base


# --------------------------------------------------------------------------- #
# Gültige Token
# --------------------------------------------------------------------------- #

class TestValidToken:
    def test_valid_token_is_accepted(self):
        handoff = read_state(_token(_payload()))
        assert handoff is not None
        assert handoff.guild_id == 123456789012345678
        assert handoff.user_id == 987654321098765432
        assert handoff.source == SOURCE
        assert handoff.guild_name == "Mein Server"

    def test_sign_state_round_trip(self):
        """Was wir signieren, müssen wir auch lesen können."""

        state = sign_state(111, 222, guild_name="Test")
        handoff = read_state(state)
        assert handoff is not None
        assert handoff.guild_id == 111
        assert handoff.user_id == 222

    def test_guild_name_is_optional(self):
        payload = _payload()
        del payload["guild_name"]
        handoff = read_state(_token(payload))
        assert handoff is not None
        assert handoff.guild_name is None

    def test_token_at_the_edge_of_validity(self):
        """Eine Sekunde vor Ablauf gilt es noch."""

        handoff = read_state(_token(_payload(t=int(time.time()) - MAX_AGE + 5)))
        assert handoff is not None

    def test_token_has_no_padding(self):
        """Base64-Padding würde die URL unnötig verkomplizieren."""

        state = sign_state(1, 2)
        assert "=" not in state

    def test_handoff_is_immutable(self):
        """Ein geprüftes Token darf nachträglich nicht verändert werden."""

        handoff = read_state(_token(_payload()))
        # frozen dataclass -> FrozenInstanceError, eine AttributeError-Variante
        with pytest.raises(AttributeError):
            handoff.guild_id = 999


# --------------------------------------------------------------------------- #
# Angriffe
# --------------------------------------------------------------------------- #

class TestRejection:
    def test_forged_signature_is_rejected(self):
        body = _token(_payload()).split(".")[0]
        assert read_state(f"{body}.offensichtlichgefaelscht") is None

    def test_swapped_body_under_valid_signature_is_rejected(self):
        """Der klassische Angriff: fremde Signatur an eigenen Body kleben."""

        legit = _token(_payload())
        _, _, signature = legit.partition(".")

        evil_body = _b64(
            json.dumps(_payload(g="999999999999999999"), separators=(",", ":")).encode()
        )
        assert read_state(f"{evil_body}.{signature}") is None

    def test_token_signed_with_wrong_secret_is_rejected(self):
        assert read_state(_token(_payload(), secret="das-falsche-secret")) is None

    def test_wrong_source_is_rejected(self):
        """Korrekt signiert, aber von einem anderen Partner."""

        assert read_state(_token(_payload(src="anderer-bot"))) is None
        assert read_state(_token(_payload(src="oskar"))) is None
        assert read_state(_token(_payload(src=""))) is None

    def test_source_comparison_is_exact(self):
        for variant in ("University-Bot", "university-bot ", " university-bot"):
            assert read_state(_token(_payload(src=variant))) is None

    def test_expired_token_is_rejected(self):
        assert read_state(_token(_payload(t=int(time.time()) - MAX_AGE - 60))) is None

    def test_ancient_token_is_rejected(self):
        assert read_state(_token(_payload(t=1))) is None

    def test_missing_or_invalid_timestamp_is_rejected(self):
        for value in (0, -1, "", None, "gestern"):
            payload = _payload(t=value)
            assert read_state(_token(payload)) is None, value

    def test_plain_source_string_is_rejected(self):
        """Der Angriff, gegen den die Signatur überhaupt existiert."""

        assert read_state("university-bot") is None
        assert read_state("university-bot.") is None
        assert read_state(".university-bot") is None

    def test_malformed_tokens_are_rejected(self):
        for bad in (
            None,
            "",
            "kein-punkt",
            ".",
            "..",
            "a.b.c",
            "!!!.???",
            "a." + "x" * 500,
        ):
            assert read_state(bad) is None, bad

    def test_non_dict_payload_is_rejected(self):
        for payload in ([1, 2, 3], "text", 42):
            body = _b64(json.dumps(payload).encode())
            signature = _b64(
                hmac.new(SECRET.encode(), body.encode("ascii"), hashlib.sha256).digest()
            )
            assert read_state(f"{body}.{signature}") is None

    def test_broken_base64_is_rejected(self):
        signature = _b64(
            hmac.new(SECRET.encode(), b"###", hashlib.sha256).digest()
        )
        assert read_state(f"###.{signature}") is None

    def test_missing_guild_id_is_rejected(self):
        for value in ("0", "", "nicht-numerisch", None):
            assert read_state(_token(_payload(g=value))) is None, value


class TestWithoutSecret:
    def test_every_token_is_rejected_without_secret(self, monkeypatch):
        """Ohne Secret gibt es keine Automatik — auch nicht für gültige Token."""

        valid = _token(_payload())
        monkeypatch.delenv("PARTNER_HANDSHAKE_SECRET", raising=False)

        assert read_state(valid) is None
        assert not is_enabled()

    def test_empty_secret_counts_as_missing(self, monkeypatch):
        valid = _token(_payload())
        monkeypatch.setenv("PARTNER_HANDSHAKE_SECRET", "")

        assert read_state(valid) is None
        assert not is_enabled()

    def test_signing_without_secret_raises(self, monkeypatch):
        monkeypatch.delenv("PARTNER_HANDSHAKE_SECRET", raising=False)
        with pytest.raises(RuntimeError):
            sign_state(1, 2)


class TestSignatureIsMandatory:
    """Ohne Signaturprüfung wäre der ganze Handshake wertlos.

    Diese Tests prüfen die Wirkung, nicht die Schreibweise: Sie schlagen
    auch dann fehl, wenn jemand die Prüfung durch etwas ersetzt, das
    zufällig noch nach einem Vergleich aussieht.
    """

    def test_any_signature_is_not_accepted(self):
        body = _token(_payload()).split(".")[0]
        for fake in ("x", "AAAA", "0" * 43, body):
            assert read_state(f"{body}.{fake}") is None, fake

    def test_signature_of_a_different_body_is_rejected(self):
        """Eine echte Signatur, aber zu einem anderen Inhalt."""

        other = _token(_payload(g="111111111111111111"))
        other_signature = other.partition(".")[2]
        own_body = _token(_payload(g="222222222222222222")).split(".")[0]

        assert read_state(f"{own_body}.{other_signature}") is None

    def test_unsigned_payload_is_rejected(self):
        """Nur der Body, ohne jede Signatur."""

        body = _token(_payload()).split(".")[0]
        assert read_state(body) is None
        assert read_state(f"{body}.") is None


class TestConstantTimeComparison:
    def test_source_uses_compare_digest_not_equals(self):
        """Ein == beim Signaturvergleich verrät den Schlüssel über die Laufzeit."""

        source = (BASE_DIR / "core" / "handshake.py").read_text(encoding="utf-8")
        assert "hmac.compare_digest" in source

        # Kein direkter Vergleich der Signatur.
        for forbidden in (
            "signature ==",
            "== signature",
            "signature !=",
            "!= signature",
        ):
            assert forbidden not in source, f"Unsicherer Vergleich: {forbidden}"


# --------------------------------------------------------------------------- #
# Speicher
# --------------------------------------------------------------------------- #

def _handoff(guild_id: int = 1, **kwargs) -> Handoff:
    defaults: dict[str, Any] = {
        "guild_id": guild_id,
        "user_id": 2,
        "issued_at": int(time.time()),
        "source": SOURCE,
        "guild_name": "Test",
    }
    defaults.update(kwargs)
    return Handoff(**defaults)


class TestPendingHandoffs:
    def test_add_and_pop(self):
        store = PendingHandoffs()
        store.add(_handoff(42))
        assert store.pop(42) is not None

    def test_pop_consumes_the_entry(self):
        """Ein Handoff darf nur einmal wirken."""

        store = PendingHandoffs()
        store.add(_handoff(42))
        assert store.pop(42) is not None
        assert store.pop(42) is None

    def test_peek_keeps_the_entry(self):
        store = PendingHandoffs()
        store.add(_handoff(42))
        assert store.peek(42) is not None
        assert store.pop(42) is not None

    def test_unknown_guild(self):
        assert PendingHandoffs().pop(999) is None

    def test_entries_expire(self):
        store = PendingHandoffs(ttl=0)
        store.add(_handoff(42))
        time.sleep(0.01)
        assert store.pop(42) is None

    def test_discard(self):
        store = PendingHandoffs()
        store.add(_handoff(42))
        store.discard(42)
        assert store.pop(42) is None

    def test_guilds_are_independent(self):
        store = PendingHandoffs()
        store.add(_handoff(1))
        store.add(_handoff(2))
        assert store.pop(1) is not None
        assert store.pop(2) is not None


class TestSetupLedger:
    def test_records_and_reports(self, tmp_path):
        ledger = SetupLedger(tmp_path / "ledger.json")
        assert not ledger.was_set_up(1)
        ledger.record(1, template="community", source=SOURCE)
        assert ledger.was_set_up(1)

    def test_survives_restart(self, tmp_path):
        """Der entscheidende Unterschied zum Arbeitsspeicher."""

        path = tmp_path / "ledger.json"
        SetupLedger(path).record(7, template="rp", source=SOURCE)
        assert SetupLedger(path).was_set_up(7)

    def test_details(self, tmp_path):
        ledger = SetupLedger(tmp_path / "ledger.json")
        ledger.record(1, template="gaming", source=SOURCE)
        details = ledger.details(1)
        assert details["template"] == "gaming"
        assert details["source"] == SOURCE
        assert details["at"] > 0

    def test_forget_allows_a_rerun(self, tmp_path):
        ledger = SetupLedger(tmp_path / "ledger.json")
        ledger.record(1, template="community", source=SOURCE)
        assert ledger.forget(1) is True
        assert not ledger.was_set_up(1)
        assert ledger.forget(1) is False

    def test_corrupt_file_does_not_crash(self, tmp_path):
        path = tmp_path / "ledger.json"
        path.write_text("{kaputt", encoding="utf-8")
        assert not SetupLedger(path).was_set_up(1)

    def test_guilds_are_independent(self, tmp_path):
        ledger = SetupLedger(tmp_path / "ledger.json")
        ledger.record(1, template="community", source=SOURCE)
        assert not ledger.was_set_up(2)
