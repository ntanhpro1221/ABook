"""Current schema only: initialization, refusal without writes, and crash recovery."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

from abook import database
from abook.config import ANALYSIS_RETRY_SETTING_KEYS, DIRECTOR_CRITIC_SETTING_KEYS, build_settings, load_settings
from abook.database import ProjectDB, SCHEMA_VERSION, UnsupportedProjectSchema
from abook.webui import store
from abook.webui.listening import Listening


def _bytes(root: Path) -> dict[str, bytes]:
    return {path.name: path.read_bytes() for path in root.iterdir() if path.is_file()}


@pytest.mark.parametrize("version", [*range(SCHEMA_VERSION), SCHEMA_VERSION + 1])
def test_unsupported_version_refused_before_writable_open(tmp_path, monkeypatch, version):
    path = tmp_path / store.DB_NAME
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE old_data(value TEXT)")
        conn.execute("INSERT INTO old_data VALUES ('keep this')")
        conn.execute(f"PRAGMA user_version={version}")
    before = _bytes(tmp_path)

    def no_writer(*args, **kwargs):
        pytest.fail("unsupported DB reached a writable ProjectDB connection")

    monkeypatch.setattr(ProjectDB, "connect", no_writer)
    with pytest.raises(UnsupportedProjectSchema, match="Unsupported project schema version"):
        ProjectDB(path)
    # Store's observational API remains read only, including for diagnostics of
    # unsupported projects; it must never become another initializer.
    with store.connect(tmp_path) as reader:
        assert reader.execute("PRAGMA query_only").fetchone()[0] == 1
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            reader.execute("CREATE TABLE forbidden(value)")
    reader.close()
    assert _bytes(tmp_path) == before


@pytest.mark.parametrize("damage", [
    "ALTER TABLE segments DROP COLUMN listener_text",
    "ALTER TABLE segments DROP COLUMN listener_retakes",
    "ALTER TABLE segments DROP COLUMN listener_retake_at",
    "DROP TABLE analysis_responses",
    "DROP TABLE character_exposure",
    "DROP INDEX idx_segments_status",
    "DROP TRIGGER segment_candidates_repair_binding_insert",
    "CREATE TABLE unexpected(value TEXT)",
])
def test_current_version_with_incomplete_layout_is_not_repaired(tmp_path, monkeypatch, damage):
    path = tmp_path / store.DB_NAME
    ProjectDB(path)
    with sqlite3.connect(path) as conn:
        conn.execute("PRAGMA journal_mode=DELETE")
        conn.execute(damage)
    before = _bytes(tmp_path)
    monkeypatch.setattr(ProjectDB, "connect", lambda *a, **kw: pytest.fail("writer opened"))
    with pytest.raises(UnsupportedProjectSchema, match="layout"):
        ProjectDB(path)
    assert _bytes(tmp_path) == before


def test_fresh_schema_is_complete_and_reopen_does_not_recreate_it(tmp_path, monkeypatch):
    path = tmp_path / store.DB_NAME
    db = ProjectDB(path)
    with db.connect() as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert len(list(conn.execute("SELECT name FROM sqlite_master WHERE type='trigger'"))) == 6
        cols = {row[1] for row in conn.execute("PRAGMA table_info(segments)")}
        assert {"listener_text", "listener_retakes", "listener_retake_at"} <= cols
        cookie = conn.execute("PRAGMA schema_version").fetchone()[0]
    monkeypatch.setattr(database, "_schema_statements", lambda: pytest.fail("schema recreated on reopen"))
    reopened = ProjectDB(path)
    with reopened.connect() as conn:
        assert conn.execute("PRAGMA schema_version").fetchone()[0] == cookie
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert not list(tmp_path.glob("*.bak"))


def test_failed_initialization_rolls_back_all_ddl_and_can_retry(tmp_path, monkeypatch):
    path = tmp_path / store.DB_NAME
    statements = database._schema_statements

    def broken_schema():
        for index, statement in enumerate(statements()):
            if index == 3:
                raise RuntimeError("injected schema interruption")
            yield statement

    monkeypatch.setattr(database, "_schema_statements", broken_schema)
    with pytest.raises(RuntimeError, match="injected"):
        ProjectDB(path)
    with sqlite3.connect(path) as conn:
        assert not list(conn.execute("SELECT name FROM sqlite_master"))
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 0
    monkeypatch.setattr(database, "_schema_statements", statements)
    ProjectDB(path)


@pytest.mark.parametrize("during_creation", [False, True])
def test_process_crash_reopens_only_committed_state(tmp_path, during_creation):
    path = tmp_path / store.DB_NAME
    code = f"""
import sys, os
from pathlib import Path
sys.path.insert(0, {str(Path(database.__file__).parent.parent)!r})
from abook import database
path = Path({str(path)!r})
if {during_creation!r}:
    original = database._schema_statements
    def interrupted():
        for index, statement in enumerate(original()):
            if index == 3: os._exit(91)
            yield statement
    database._schema_statements = interrupted
    database.ProjectDB(path)
else:
    db = database.ProjectDB(path)
    with db.connect() as conn:
        conn.execute("INSERT INTO runtime_events(timestamp,level,code,message) VALUES(1,'info','committed','kept')")
        conn.execute('BEGIN IMMEDIATE')
        conn.execute("INSERT INTO runtime_events(timestamp,level,code,message) VALUES(2,'info','uncommitted','discarded')")
        os._exit(91)
"""
    child = subprocess.run([sys.executable, "-X", "utf8", "-c", code], capture_output=True,
                           creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    assert child.returncode == 91, child.stderr.decode("utf-8", errors="replace")
    db = ProjectDB(path)
    with db.connect() as conn:
        assert [row[0] for row in conn.execute("SELECT code FROM runtime_events")] == ([] if during_creation else ["committed"])
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert not list(tmp_path.glob("*.bak"))


def test_old_backup_is_not_offered_for_restore(tmp_path):
    old = tmp_path / "project.sqlite3.pre-v0-to-v13.bak"
    with sqlite3.connect(old) as conn:
        conn.execute("CREATE TABLE old_data(value TEXT)")
    before = _bytes(tmp_path)
    assert store.db_backups(tmp_path) == []
    assert _bytes(tmp_path) == before


@pytest.mark.parametrize("version", [None, 1, 3])
def test_unsupported_listening_profile_is_not_converted_or_written(tmp_path, version):
    path = tmp_path / "listening.json"
    data = {"records": {}, "links": {}}
    if version is not None:
        data["version"] = version
    path.write_text(json.dumps(data), encoding="utf-8")
    before = _bytes(tmp_path)
    with pytest.raises(ValueError, match="Unsupported listening profile version"):
        Listening(path)
    assert {name: data for name, data in _bytes(tmp_path).items() if not name.endswith(".lock")} == before


@pytest.mark.parametrize("keys", [DIRECTOR_CRITIC_SETTING_KEYS, ANALYSIS_RETRY_SETTING_KEYS])
def test_old_locked_settings_are_refused_without_default_injection(tmp_path, keys):
    settings = build_settings()
    for key in keys:
        settings["analysis"].pop(key)
    path = tmp_path / "book_settings.json"
    path.write_text(json.dumps(settings), encoding="utf-8")
    before = path.read_bytes()
    with pytest.raises(ValueError, match="Missing analysis"):
        load_settings(path)
    assert path.read_bytes() == before
