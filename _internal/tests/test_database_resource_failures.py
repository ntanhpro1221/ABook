"""SQLite FULL must reach the worker with its original diagnostic (a96 V3)."""
import contextlib
import sqlite3

import pytest

from abook.database import ProjectDB


def test_sqlite_full_keeps_original_error(tmp_path, monkeypatch):
    con = sqlite3.connect(tmp_path / "quota.sqlite", isolation_level=None)
    con.execute("PRAGMA page_size=512")
    con.execute("PRAGMA max_page_count=8")
    con.execute("CREATE TABLE items(data BLOB)")
    @contextlib.contextmanager
    def connect():
        yield con
    db = ProjectDB.__new__(ProjectDB)
    monkeypatch.setattr(db, "connect", connect)
    try:
        with pytest.raises(sqlite3.OperationalError, match="database or disk is full") as caught:
            with db.transaction() as conn:
                for _ in range(10):
                    conn.execute("INSERT INTO items VALUES (?)", (b"x" * 2048,))
        assert caught.value.sqlite_errorcode == sqlite3.SQLITE_FULL
        assert not con.in_transaction
        assert con.execute("SELECT COUNT(*) FROM items").fetchone()[0] == 0
    finally:
        con.close()


def test_rollback_failure_does_not_replace_original_error(monkeypatch):
    commands = []
    class Connection:
        in_transaction = True
        def execute(self, command):
            commands.append(command)
            if command == "ROLLBACK":
                raise sqlite3.OperationalError("cleanup failed")
    @contextlib.contextmanager
    def connect():
        yield Connection()
    db = ProjectDB.__new__(ProjectDB)
    monkeypatch.setattr(db, "connect", connect)
    original = OSError("original write failure")
    with pytest.raises(OSError) as caught:
        with db.transaction():
            raise original
    assert caught.value is original
    assert commands == ["BEGIN IMMEDIATE", "ROLLBACK"]
