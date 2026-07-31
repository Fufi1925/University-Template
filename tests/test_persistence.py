"""Was den Neustart ueberlebt — und was passiert, wenn die Datei kaputt ist.

Zwei Speicher liegen auf der Platte: die Premium-Freischaltungen und das
Register bereits eingerichteter Server. Beide teilen dieselbe Zusage:

* **Atomar schreiben.** Ein Absturz mitten im Schreiben darf nicht dazu
  fuehren, dass beim naechsten Start alle Freischaltungen weg sind.
* **Nie den Start verhindern.** Eine unlesbare Datei, ein voller Datentraeger
  oder ein fehlendes Verzeichnis kosten hoechstens den gespeicherten Zustand,
  aber nie den Bot.

Auf Railway liegen diese Dateien auf einem gemounteten Volume — genau dort,
wo Schreibfehler tatsaechlich vorkommen.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.handoff_store import PendingHandoffs, SetupLedger
from core.handshake import Handoff
from core.premium import PremiumStore

KEY = "Ein Test Key"


def store(path: Path, **kwargs) -> PremiumStore:
    return PremiumStore(path, keys=(KEY,), **kwargs)


# --------------------------------------------------------------------------- #
# Premium: Schluesselpruefung
# --------------------------------------------------------------------------- #

class TestKeyVerification:
    def test_correct_key(self, tmp_path):
        assert store(tmp_path / "p.json").verify(KEY)

    def test_wrong_key(self, tmp_path):
        assert not store(tmp_path / "p.json").verify("etwas anderes")

    def test_empty_input(self, tmp_path):
        assert not store(tmp_path / "p.json").verify("")
        assert not store(tmp_path / "p.json").verify("   ")

    def test_whitespace_is_trimmed(self, tmp_path):
        """Beim Kopieren aus einer Nachricht haengt fast immer etwas dran."""

        assert store(tmp_path / "p.json").verify(f"\n  {KEY}\t ")

    def test_case_is_ignored(self, tmp_path):
        """Bewusste Komfortentscheidung — siehe casefold() in premium.py."""

        assert store(tmp_path / "p.json").verify(KEY.upper())

    def test_partial_key_is_rejected(self, tmp_path):
        assert not store(tmp_path / "p.json").verify(KEY[:-1])
        assert not store(tmp_path / "p.json").verify(KEY + "x")

    def test_several_keys_are_all_valid(self, tmp_path):
        multi = PremiumStore(tmp_path / "p.json", keys=("erster", "zweiter"))

        assert multi.verify("erster")
        assert multi.verify("zweiter")
        assert not multi.verify("dritter")

    def test_without_keys_nothing_unlocks(self, tmp_path):
        """Der sichere Standard: ohne PREMIUM_KEY ist Premium zu."""

        empty = PremiumStore(tmp_path / "p.json", keys=())

        assert not empty.is_configured
        for attempt in ("", "irgendwas", KEY):
            assert not empty.verify(attempt)

    def test_blank_keys_are_filtered_out(self, tmp_path):
        """``PREMIUM_EXTRA_KEYS=","`` darf nicht alles freischalten."""

        sloppy = PremiumStore(tmp_path / "p.json", keys=("", "   ", ""))

        assert not sloppy.is_configured
        assert not sloppy.verify("")


# --------------------------------------------------------------------------- #
# Premium: Zugriff
# --------------------------------------------------------------------------- #

class TestAccess:
    def test_grant_and_check(self, tmp_path):
        premium = store(tmp_path / "p.json")
        premium.grant(1, 2)

        assert premium.has_access(1, 2)

    def test_access_does_not_leak_between_users(self, tmp_path):
        premium = store(tmp_path / "p.json")
        premium.grant(1, 2)

        assert not premium.has_access(1, 3)

    def test_access_does_not_leak_between_guilds(self, tmp_path):
        premium = store(tmp_path / "p.json")
        premium.grant(1, 2)

        assert not premium.has_access(9, 2)

    def test_guild_wide_mode_covers_everyone(self, tmp_path):
        shared = store(tmp_path / "p.json", guild_wide=True)
        shared.grant(1, 2)

        assert shared.has_access(1, 999), "guild_wide gilt fuer den ganzen Server"

    def test_guild_wide_stops_at_the_server_border(self, tmp_path):
        shared = store(tmp_path / "p.json", guild_wide=True)
        shared.grant(1, 2)

        assert not shared.has_access(2, 999)

    def test_revoke_removes_access(self, tmp_path):
        premium = store(tmp_path / "p.json")
        premium.grant(1, 2)
        premium.revoke(1, 2)

        assert not premium.has_access(1, 2)

    def test_direct_message_unlock_is_kept_apart(self, tmp_path):
        """Ohne Guild wird 0 als Schluessel benutzt — nicht 'ueberall'."""

        premium = store(tmp_path / "p.json")
        premium.grant(None, 5)

        assert premium.has_access(None, 5)
        assert not premium.has_access(77, 5)

    def test_unlock_count(self, tmp_path):
        premium = store(tmp_path / "p.json")
        premium.grant(1, 2)
        premium.grant(1, 3)
        premium.grant(1, 2)  # doppelt zaehlt nicht

        assert premium.unlock_count == 2


# --------------------------------------------------------------------------- #
# Premium: Platte
# --------------------------------------------------------------------------- #

class TestPremissionPersistence:
    def test_unlocks_survive_a_restart(self, tmp_path):
        path = tmp_path / "p.json"
        store(path).grant(1, 2)

        assert store(path).has_access(1, 2), "Freischaltung nach Neustart weg"

    def test_the_key_is_never_written_to_disk(self, tmp_path):
        """Die zentrale Zusage des Moduls."""

        path = tmp_path / "p.json"
        premium = store(path)
        premium.verify(KEY)
        premium.grant(1, 2)

        raw = path.read_text(encoding="utf-8")
        assert KEY not in raw
        assert KEY.casefold() not in raw.casefold()

    def test_missing_file_is_not_an_error(self, tmp_path):
        assert store(tmp_path / "gibt-es-nicht.json").unlock_count == 0

    def test_broken_json_does_not_prevent_startup(self, tmp_path):
        """Lieber ohne gespeicherte Freischaltungen starten als gar nicht."""

        path = tmp_path / "p.json"
        path.write_text("{kaputt", encoding="utf-8")

        premium = store(path)

        assert premium.unlock_count == 0
        assert premium.verify(KEY), "Der Store ist trotzdem benutzbar"

    def test_garbage_entries_are_skipped_individually(self, tmp_path):
        """Ein defekter Eintrag darf die intakten nicht mitreissen."""

        path = tmp_path / "p.json"
        path.write_text(
            json.dumps({"users": [[1, 2], "quatsch", [3], ["a", "b"], [4, 5]]}),
            encoding="utf-8",
        )

        premium = store(path)

        assert premium.has_access(1, 2)
        assert premium.has_access(4, 5)
        assert premium.unlock_count == 2

    def test_legacy_list_format_is_still_read(self, tmp_path):
        """Aeltere Versionen schrieben eine blanke Liste."""

        path = tmp_path / "p.json"
        path.write_text(json.dumps([[1, 2]]), encoding="utf-8")

        assert store(path).has_access(1, 2)

    def test_guild_wide_unlocks_survive(self, tmp_path):
        path = tmp_path / "p.json"
        store(path, guild_wide=True).grant(1, 2)

        assert store(path, guild_wide=True).has_access(1, 999)

    def test_parent_directory_is_created(self, tmp_path):
        """Beim ersten Start auf einem frischen Volume fehlt data/."""

        path = tmp_path / "tief" / "verschachtelt" / "p.json"
        store(path).grant(1, 2)

        assert path.exists()

    def test_unwritable_location_does_not_crash(self, tmp_path, monkeypatch):
        """Volle Platte oder schreibgeschuetztes Volume."""

        import core.premium as premium_module

        premium = store(tmp_path / "p.json")

        def refuse(*args, **kwargs):
            raise OSError("kein Platz")

        monkeypatch.setattr(premium_module.Path, "write_text", refuse)

        premium.grant(1, 2)  # darf nicht werfen

        assert premium.has_access(1, 2), "Im Speicher muss es trotzdem gelten"

    def test_no_temporary_file_is_left_behind(self, tmp_path):
        """Atomares Schreiben legt eine .tmp an — sie darf nicht bleiben."""

        path = tmp_path / "p.json"
        store(path).grant(1, 2)

        leftovers = [p.name for p in tmp_path.iterdir() if p.suffix == ".tmp"]
        assert not leftovers, f"Temporaerdateien uebrig: {leftovers}"


# --------------------------------------------------------------------------- #
# Setup-Register
# --------------------------------------------------------------------------- #

class TestSetupLedger:
    def test_remembers_configured_guilds(self, tmp_path):
        path = tmp_path / "ledger.json"
        ledger = SetupLedger(path)
        ledger.record(1, template="community", source="test")

        assert SetupLedger(path).was_set_up(1), "Nach Neustart vergessen"

    def test_unknown_guild(self, tmp_path):
        assert not SetupLedger(tmp_path / "l.json").was_set_up(42)

    def test_details_are_kept(self, tmp_path):
        path = tmp_path / "l.json"
        SetupLedger(path).record(1, template="rp", source="test")

        details = SetupLedger(path).details(1)
        assert details is not None
        assert details.get("template") == "rp"

    def test_broken_file_does_not_prevent_startup(self, tmp_path):
        path = tmp_path / "l.json"
        path.write_text("[[[", encoding="utf-8")

        ledger = SetupLedger(path)

        assert not ledger.was_set_up(1)
        ledger.record(1, template="community", source="test")
        assert ledger.was_set_up(1)

    def test_invalid_keys_are_skipped(self, tmp_path):
        path = tmp_path / "l.json"
        path.write_text(
            json.dumps({"1": {"template": "a"}, "keine-zahl": {}}), encoding="utf-8"
        )

        ledger = SetupLedger(path)

        assert ledger.was_set_up(1)
        assert len(ledger) == 1

    def test_unwritable_location_does_not_crash(self, tmp_path, monkeypatch):
        import core.handoff_store as module

        ledger = SetupLedger(tmp_path / "l.json")

        def refuse(*args, **kwargs):
            raise OSError("kein Platz")

        monkeypatch.setattr(module.Path, "write_text", refuse)

        ledger.record(1, template="community", source="test")

        assert ledger.was_set_up(1)


# --------------------------------------------------------------------------- #
# Vorgemerkte Handoffs
# --------------------------------------------------------------------------- #

def handoff(guild_id: int = 1) -> Handoff:
    import time

    return Handoff(
        guild_id=guild_id,
        user_id=2,
        issued_at=int(time.time()),
        source="university-bot",
        guild_name="Test",
    )


class TestPendingHandoffs:
    def test_add_and_pop(self):
        pending = PendingHandoffs()
        pending.add(handoff(1))

        assert pending.pop(1) is not None

    def test_each_handoff_is_used_once(self):
        """Sonst koennte ein Link zweimal einen Server umbauen."""

        pending = PendingHandoffs()
        pending.add(handoff(1))
        pending.pop(1)

        assert pending.pop(1) is None

    def test_peek_does_not_consume(self):
        pending = PendingHandoffs()
        pending.add(handoff(1))

        assert pending.peek(1) is not None
        assert pending.pop(1) is not None

    def test_contains_accepts_strings(self):
        """Guild-IDs kommen aus HTTP-Parametern oft als Text."""

        pending = PendingHandoffs()
        pending.add(handoff(1))

        assert 1 in pending
        assert "1" in pending

    def test_contains_tolerates_nonsense(self):
        """``in`` darf mit allem aufgerufen werden, ohne zu werfen."""

        pending = PendingHandoffs()

        for candidate in (None, object(), "keine-zahl", 3.5, []):
            assert candidate not in pending

    def test_expired_entries_disappear(self):
        pending = PendingHandoffs(ttl=0)
        pending.add(handoff(1))

        assert pending.pop(1) is None, "Abgelaufener Handoff wurde noch genutzt"

    def test_length_reflects_live_entries(self):
        pending = PendingHandoffs()
        pending.add(handoff(1))
        pending.add(handoff(2))

        assert len(pending) == 2

        pending.pop(1)
        assert len(pending) == 1

    def test_same_guild_twice_keeps_the_newer_one(self):
        pending = PendingHandoffs()
        pending.add(handoff(1))
        pending.add(handoff(1))

        assert len(pending) == 1
