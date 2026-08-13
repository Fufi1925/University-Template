"""Persoenliche Premium-Keys: Ausgabe per DM und Einloesung.

Der neue Weg zu Premium: Klick auf den Freischalt-Knopf, der Bot schickt
per DM einen persoenlichen Key, der im Key-Fenster eingeloest wird. Was
dabei stimmen muss:

* **Gebunden** — der Key eines Kontos funktioniert bei keinem anderen.
* **Einmalig** — nach dem Einloesen ist er verbraucht.
* **Begrenzt** — nach Ablauf der Frist ist er wertlos, ein neuer Klick
  ersetzt alte offene Keys.
* **Sparsam** — auf der Platte liegt nur der Hash, nie der Klartext.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.premium import PERSONAL_KEY_TTL, PremiumStore

MASTER = "Master-Key-123"


@pytest.fixture
def store(tmp_path) -> PremiumStore:
    return PremiumStore(tmp_path / "premium.json", keys=(MASTER,))


class TestIssue:
    def test_the_key_is_grouped_and_redemeable(self, store):
        key = store.issue_key(user_id=7)

        parts = key.split("-")
        assert len(parts) == 6 and all(len(part) == 4 for part in parts)
        assert store.redeem_key(key, user_id=7)

    def test_formatting_is_tolerated_when_typing(self, store):
        """Ohne Bindestriche, klein, mit Leerzeichen — alles derselbe Key."""

        key = store.issue_key(user_id=7)
        mangled = f"  {key.lower().replace('-', ' ')}  "

        assert store.redeem_key(mangled, user_id=7)

    def test_the_key_is_bound_to_the_account(self, store):
        key = store.issue_key(user_id=7)

        assert not store.redeem_key(key, user_id=8)

    def test_a_key_can_only_be_used_once(self, store):
        key = store.issue_key(user_id=7)

        assert store.redeem_key(key, user_id=7)
        assert not store.redeem_key(key, user_id=7)

    def test_a_new_issue_replaces_open_keys(self, store):
        """Wer mehrmals klickt, bekommt einen neuen Key — die alten sterben."""

        first = store.issue_key(user_id=7)
        second = store.issue_key(user_id=7)

        assert not store.redeem_key(first, user_id=7)
        assert store.redeem_key(second, user_id=7)

    def test_other_accounts_keep_their_keys(self, store):
        other = store.issue_key(user_id=8)
        store.issue_key(user_id=7)

        assert store.redeem_key(other, user_id=8)

    def test_expired_keys_are_worthless(self, store, monkeypatch):
        now = time.time()

        key = store.issue_key(user_id=7)
        monkeypatch.setattr(time, "time", lambda: now + PERSONAL_KEY_TTL + 1)

        assert not store.redeem_key(key, user_id=7)

    def test_unknown_keys_are_rejected(self, store):
        assert not store.redeem_key("ABCD-EFGH-IJKL-MNOP-QRST-UVWX", user_id=7)

    def test_the_master_key_still_works(self, store):
        """Der klassische Weg bleibt — Serverleitungen aendern nichts."""

        assert store.redeem_key(MASTER, user_id=7)


class TestPersistence:
    def test_open_keys_survive_a_restart(self, store, tmp_path):
        key = store.issue_key(user_id=7)

        reloaded = PremiumStore(tmp_path / "premium.json", keys=(MASTER,))

        assert reloaded.redeem_key(key, user_id=7)

    def test_redeemed_keys_do_not_survive(self, store, tmp_path):
        key = store.issue_key(user_id=7)
        assert store.redeem_key(key, user_id=7)

        reloaded = PremiumStore(tmp_path / "premium.json", keys=(MASTER,))

        assert not reloaded.redeem_key(key, user_id=7)

    def test_the_plaintext_key_is_never_on_disk(self, store, tmp_path):
        key = store.issue_key(user_id=7)

        raw = (tmp_path / "premium.json").read_text(encoding="utf-8")
        assert key not in raw, "Der Klartext-Key steht in der Datei"
        assert key.replace("-", "") not in raw

        payload = json.loads(raw)
        assert payload.get("pending"), "Die offenen Keys wurden nicht gespeichert"

    def test_a_legacy_file_without_pending_section_loads(self, tmp_path):
        legacy = tmp_path / "premium.json"
        legacy.write_text(
            json.dumps({"users": [[1, 7]], "guilds": [1]}), encoding="utf-8"
        )

        store = PremiumStore(legacy, keys=(MASTER,))

        assert store.has_access(1, 7)
        assert store.pending_key_count == 0

    def test_corrupt_pending_entries_are_ignored(self, tmp_path):
        """Ein kaputter Eintrag darf den Start nicht verhindern."""

        path = tmp_path / "premium.json"
        good = "a" * 64
        path.write_text(
            json.dumps(
                {
                    "users": [],
                    "guilds": [],
                    "pending": {
                        good: {"user": 7, "issued": 1, "expires": time.time() + 1000},
                        "b" * 64: {"user": "keine-zahl", "expires": 1},
                        "c" * 64: {"user": 7},
                        "kaputt": 42,
                    },
                }
            ),
            encoding="utf-8",
        )

        store = PremiumStore(path, keys=(MASTER,))

        assert store.pending_key_count == 1

    def test_a_failing_write_does_not_crash_the_issue(self, store, monkeypatch):
        """Kein Speicherplatz? Der Key kommt trotzdem per DM an."""

        from pathlib import Path

        def broken(self, *args, **kwargs):
            raise OSError("kein Platz")

        monkeypatch.setattr(Path, "write_text", broken)

        key = store.issue_key(user_id=7)

        assert key  # Der Key wurde trotzdem ausgegeben.

    def test_a_failing_cleanup_is_survived(self, store, monkeypatch):
        """Auch das Aufraeumen der .tmp-Datei darf nicht knallen."""

        from pathlib import Path

        def broken_write(self, *args, **kwargs):
            raise OSError("voll")

        def broken_unlink(self, *args, **kwargs):
            raise OSError("gesperrt")

        monkeypatch.setattr(Path, "write_text", broken_write)
        monkeypatch.setattr(Path, "unlink", broken_unlink)

        key = store.issue_key(user_id=7)

        assert key
