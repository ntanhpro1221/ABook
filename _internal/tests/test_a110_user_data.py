"""a110: regression cases derived from the review's isolated durability harness."""
import errno
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from abook import io_utils
from abook.webui import library, listening, notices, packages


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("ABOOK_PREFERENCES", str(tmp_path / "preferences.json"))
    notices.NOTICES.clear()


@pytest.mark.parametrize("broken", ["state", "chapters", "bookmark", "links"])
def test_f1_nested_damage_keeps_original_and_readable_parts(tmp_path, broken):
    path = tmp_path / "listening.json"
    saved = listening.Listening(path)
    mark = saved.add_bookmark("book", 1, 10, "keep me")
    saved.add_bookmark("other", 2, 20, "other record")
    raw = json.loads(path.read_text("utf-8"))
    record = raw["records"][raw["links"]["book"]["active"]]
    if broken == "state":
        record["state"] = []
    elif broken == "chapters":
        record["state"]["chapters"] = []
    elif broken == "bookmark":
        record["state"]["bookmarks"].append("not-a-bookmark")
    else:
        raw["links"]["book"]["records"].append({"bad": "id"})
    original = json.dumps(raw).encode()
    path.write_bytes(original)
    reopened = listening.Listening(path)
    assert reopened.get("other")["bookmarks"][0]["note"] == "other record"
    assert isinstance(reopened.get("book")["chapters"], dict)
    if broken != "state":
        assert reopened.get("book")["bookmarks"][0]["id"] == mark["id"]
    reopened.add_bookmark("book", 3, 50, "new")
    assert any(p.read_bytes() == original for p in tmp_path.glob("listening.json.hong-*"))
    assert notices.NOTICES.all()


def test_f1_cannot_preserve_means_cannot_write(tmp_path, monkeypatch):
    path = tmp_path / "listening.json"
    path.write_text('{"version":2,"records":{},"links":[]}', encoding="utf-8")
    original = path.read_bytes()
    monkeypatch.setattr(notices, "keep_broken", lambda *a, **kw: None)
    saved = listening.Listening(path)
    with pytest.raises(OSError):
        saved.add_bookmark("book", 1, 10)
    assert path.read_bytes() == original


def test_f1_readable_subset_still_available_when_backup_cannot_be_written(tmp_path, monkeypatch):
    path = tmp_path / "listening.json"
    saved = listening.Listening(path)
    saved.add_bookmark("book", 1, 10, "precious")
    raw = json.loads(path.read_text("utf-8"))
    next(iter(raw["records"].values()))["state"]["chapters"] = []
    path.write_text(json.dumps(raw), encoding="utf-8")
    original = path.read_bytes()
    monkeypatch.setattr(notices, "keep_broken", lambda *a, **kw: None)
    reopened = listening.Listening(path)
    assert reopened.get("book")["bookmarks"][0]["note"] == "precious"
    with pytest.raises(notices.Unreadable):
        reopened.add_bookmark("book", 2, 30)
    assert path.read_bytes() == original


def test_f1_damaged_profile_does_not_hide_a_healthy_book_in_real_shelf(tmp_path):
    from abook.webui.server import App
    book = tmp_path / "book"
    book.mkdir()
    (book / "book.json").write_text(json.dumps({"title": "A book", "package": {}, "chapters": []}), encoding="utf-8")
    value = library.book_id(book)
    saved = listening.Listening(tmp_path / "listening.json")
    saved.add_bookmark(value, 1, 10, "kept")
    raw = json.loads(saved.path.read_text("utf-8"))
    next(iter(raw["records"].values()))["state"] = []
    saved.path.write_text(json.dumps(raw), encoding="utf-8")
    app = App.__new__(App)
    app.library = SimpleNamespace(projects=lambda: [], packages=lambda: [book])
    app.listening = listening.Listening(saved.path)
    app.refresh_remote = lambda: None
    app.capabilities = lambda *args: {"toolchain": False}
    app._built_workshop = lambda *args: None
    assert len(app.listen_library()) == 1
    assert notices.NOTICES.all()


@pytest.mark.parametrize("still_locked", [False, True])
def test_f2_unread_journal_retried_even_with_same_stamp(tmp_path, still_locked):
    path = tmp_path / "listening.json"
    saved = listening.Listening(path)
    saved.progress("book", 1, 10, 1000)
    saved.progress("book", 1, 600, 1000)
    journal = saved._journal
    original = journal.read_bytes()
    read = Path.read_bytes
    def locked(file):
        if file == journal:
            raise PermissionError(errno.EACCES, "locked", str(file))
        return read(file)
    with patch.object(Path, "read_bytes", locked):
        reopened = listening.Listening(path)
        assert reopened.get("book")["last"]["seconds"] == 10
        if still_locked:
            with pytest.raises(OSError, match="thử lại"):
                reopened.add_bookmark("book", 1, 40)
    assert journal.read_bytes() == original
    reopened.add_bookmark("book", 1, 40)
    assert listening.Listening(path).get("book")["last"]["seconds"] == 600
    assert notices.NOTICES.all()


def test_f3_timeout_never_enters_critical_section(tmp_path):
    path = tmp_path / "preferences.json"
    with io_utils.file_lock(path):
        with pytest.raises(TimeoutError, match="thử lại"):
            with io_utils.file_lock(path, timeout=0.03):
                pytest.fail("entered without holding lock")


def test_f3_cannot_create_lock_never_enters_critical_section(tmp_path):
    path = tmp_path / "preferences.json"
    with patch("builtins.open", side_effect=PermissionError("read only")):
        with pytest.raises(OSError, match="thử lại"):
            with io_utils.file_lock(path):
                pytest.fail("entered without holding lock")


def test_f3_http_returns_retryable_503_without_technical_exception_name(monkeypatch):
    import re
    from abook.webui import server
    result = []
    def locked(*args):
        raise io_utils.FileLockUnavailable("Dữ liệu của bạn đang được lưu. Bạn hãy thử lại.")
    monkeypatch.setattr(server, "ROUTES", [("PUT", re.compile("/api/lock-test"), locked)])
    fake = SimpleNamespace(path="/api/lock-test", _allowed_host=lambda: True, _authorized=lambda _: True,
                           _send_json=lambda status, body: result.append((status, body)))
    server.Handler._route(fake, "PUT")
    assert result[0][0] == 503 and result[0][1]["retryable"] is True
    assert "thử lại" in result[0][1]["error"] and "FileLockUnavailable" not in result[0][1]["error"]


def test_f2_real_windows_read_lock_keeps_latest_committed_progress(tmp_path):
    if os.name != "nt":
        pytest.skip("Windows sharing lock")
    import ctypes
    from ctypes import wintypes
    saved = listening.Listening(tmp_path / "listening.json")
    saved.progress("book", 1, 10, 1000)
    saved.progress("book", 1, 600, 1000)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    create = kernel.CreateFileW
    create.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    create.restype = wintypes.HANDLE
    close = kernel.CloseHandle
    close.argtypes, close.restype = [wintypes.HANDLE], wintypes.BOOL
    handle = create(str(saved._journal), 0x80000000, 0, None, 3, 0x80, None)
    assert handle != ctypes.c_void_p(-1).value
    try:
        reopened = listening.Listening(saved.path)
        assert reopened.get("book")["last"]["seconds"] == 10
    finally:
        assert close(handle)
    reopened.add_bookmark("book", 1, 30, "after release")
    assert listening.Listening(saved.path).get("book")["last"]["seconds"] == 600
    assert notices.NOTICES.all()


def test_f3_two_processes_production_timeout_preserves_both_updates(tmp_path):
    path = tmp_path / "preferences.json"
    library.Preferences(path).update({"theme": "light", "autoMusic": True})
    code = '''
import sys
from pathlib import Path
from abook.webui.library import Preferences
prefs = Preferences(Path(sys.argv[1]))
def change(data):
    print("READY", flush=True)
    sys.stdin.readline()
    return {"theme": "dark"}
prefs.modify(change)
'''
    child = subprocess.Popen([sys.executable, "-B", "-c", code, str(path)], stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")
    try:
        assert child.stdout.readline().strip() == "READY"
        with pytest.raises(TimeoutError, match="thử lại"):
            library.Preferences(path).update({"autoMusic": False})
    finally:
        out, error = child.communicate("release\n", timeout=15)
        assert child.returncode == 0, (out, error)
    library.Preferences(path).update({"autoMusic": False})
    result = library.Preferences(path).get()
    assert result["theme"] == "dark" and result["autoMusic"] is False


def test_f4_reading_survives_clock_rollback_and_reopen(tmp_path):
    saved = listening.Listening(tmp_path / "listening.json")
    saved.set_reading("book", 1, 10, at=2_000_000_000)
    saved = listening.Listening(saved.path)
    saved.set_reading("book", 1, 100, at=1_999_913_600)
    assert listening.Listening(saved.path).get("book")["reading"]["index"] == 100


def test_f4_stale_future_progress_cannot_replace_a_later_edit(tmp_path):
    saved = listening.Listening(tmp_path / "listening.json")
    with patch.object(listening.time, "time", return_value=2_000_000_000):
        saved.progress("book", 1, 10, 1000)
    stale = saved.get("book")
    with patch.object(listening.time, "time", return_value=1_999_913_600):
        saved.progress("book", 1, 600, 1000)
    saved.merge("book", stale)
    assert listening.Listening(saved.path).get("book")["last"]["seconds"] == 600


@pytest.mark.parametrize("case", json.loads((Path(__file__).parent / "fixtures/listening_revision/merge.json").read_text("utf-8")), ids=lambda v: v["name"])
def test_f4_shared_python_kotlin_merge_contract(case):
    for ours, theirs in ((case["ours"], case["theirs"]), (case["theirs"], case["ours"])):
        merged = listening.merge_states(ours, theirs)
        assert merged[case["field"]] == case["expected"]
        assert merged["_clock"] == case["clock"]


def test_f4_delayed_reading_is_rejected_without_false_ack(tmp_path):
    saved = listening.Listening(tmp_path / "listening.json")
    saved.set_reading("book", 1, 100, at=100, rev={"counter": 2, "node": "reader"})
    original = saved.path.read_bytes()
    with pytest.raises(listening.StalePlayback):
        saved.set_reading("book", 1, 10, at=200, rev={"counter": 1, "node": "reader"})
    assert saved.path.read_bytes() == original


def test_f4_journal_compaction_interrupted_with_rolled_back_clock_does_not_rewind(tmp_path):
    saved = listening.Listening(tmp_path / "listening.json")
    saved.progress("book", 1, 10, 1000)
    with patch.object(listening.time, "time", return_value=2_000_000_000):
        saved.progress("book", 1, 100, 1000)
    stale_journal = saved._journal.read_bytes()
    with patch.object(listening.time, "time", return_value=1_999_913_600):
        saved.progress("book", 1, 600, 1000)
    saved.compact()
    saved._journal.write_bytes(stale_journal)
    assert listening.Listening(saved.path).get("book")["last"]["seconds"] == 600


def test_f4_hearing_again_after_clock_rollback_is_not_stuck_finished(tmp_path):
    saved = listening.Listening(tmp_path / "listening.json")
    with patch.object(listening.time, "time", return_value=2_000_000_000):
        saved.set_finished("book", True)
    with patch.object(listening.time, "time", return_value=1_999_913_600):
        saved.progress("book", 1, 10, 1000)
    assert listening.book_progress(saved.get("book"), [{"id": 1, "duration": 1000}])["rewound"] is True


@pytest.mark.parametrize("restart", [False, True])
@pytest.mark.parametrize("failure", ["journal", "preferences", "listening", "positions", "cleanup"])
def test_f5_root_change_recovers_after_listening_save_fails(tmp_path, restart, failure):
    from abook.webui.server import App, Handler
    from abook.webui import server
    oldroot, newroot = tmp_path / "old-library", tmp_path / "new-library"
    book = oldroot / packages.IMPORTED_FOLDER / "my-book"
    book.mkdir(parents=True)
    (book / "book.json").write_text(json.dumps({"title": "My book", "package": {}, "chapters": []}), encoding="utf-8")
    pref = library.Preferences(tmp_path / "preferences.json")
    pref.update({"libraryRoot": str(oldroot)})
    saved = listening.Listening(tmp_path / "listening.json")
    oldid = library.book_id(book)
    mark = saved.add_bookmark(oldid, 1, 30, "precious note")
    pref.remember_position(oldid, 1, 30, 1000)
    oldroot.rename(newroot)
    newid = library.book_id(newroot / packages.IMPORTED_FOLDER / "my-book")
    def app_for(prefs, store):
        app = App.__new__(App)
        app.preferences, app.listening, app.library = prefs, store, library.Library(prefs)
        return app
    app = app_for(pref, saved)
    handler = SimpleNamespace(app=app, _body=lambda: {"libraryRoot": str(newroot)}, _send_json=lambda *args: None)
    target, method = {"journal": (server, "atomic_write_json"), "preferences": (pref, "_save"),
                      "listening": (listening, "atomic_write_json"), "positions": (pref, "rename_positions"),
                      "cleanup": (server.os, "remove")}[failure]
    with patch.object(target, method, side_effect=OSError(errno.ENOSPC, "full")):
        with pytest.raises(OSError):
            Handler.put_preferences(handler, {})
    intent_path = app._library_move_path()
    if failure != "journal":
        intent = json.loads(intent_path.read_text("utf-8"))
        assert intent["renamed"] == {oldid: newid}
    else:
        assert library.Preferences(pref.path).get()["libraryRoot"] == str(oldroot)
    reopened = app_for(library.Preferences(pref.path), listening.Listening(saved.path)) if restart else app
    reopened._recover_library_move()
    handler.app = reopened
    Handler.put_preferences(handler, {})
    assert reopened.listening.get(newid)["bookmarks"][0]["id"] == mark["id"]
    assert reopened.preferences.get()["libraryRoot"] == str(newroot)
    assert newid in reopened.preferences.get()["positions"]
    assert not intent_path.exists()


def test_f5_unknown_journal_is_preserved_and_blocks_a_new_root(tmp_path):
    from abook.webui.server import App
    pref = library.Preferences(tmp_path / "preferences.json")
    app = App.__new__(App)
    app.preferences, app.listening, app.library = pref, listening.Listening(tmp_path / "listening.json"), library.Library(pref)
    path = app._library_move_path()
    original = b'{"oldRoot": [], "renamed": {}}'
    path.write_bytes(original)
    with pytest.raises(notices.Unreadable):
        app.change_library_preferences({"libraryRoot": str(tmp_path / "new")})
    assert path.read_bytes() == original
    assert any(p.read_bytes() == original for p in tmp_path.glob("library-move.json.hong-*"))
