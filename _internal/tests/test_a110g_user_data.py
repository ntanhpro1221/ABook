"""Regressions from a112; exercise real stores, not the review's bug assertions."""
import copy
import json
import shutil
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import pytest

from abook.webui import library, listening, notices

CAP = 2**40
FIXTURES = Path(__file__).parent / "fixtures/listening_revision"


@pytest.mark.parametrize("counter", [CAP, CAP - 1, 2**53 - 1])
def test_r1_peer_cannot_poison_clock_and_saves_keep_working(tmp_path, counter):
    saved = listening.Listening(tmp_path / "listening.json")
    saved.progress("book", 1, 10, 1000)
    before = saved.get("book")
    notices.NOTICES.clear()
    saved.merge("book", {"last": {"chapterId": 1, "seconds": 50, "at": 100,
                                    "rev": {"counter": counter, "node": "peer"}}, "_clock": counter})
    assert saved.get("book")["last"] == before["last"]
    assert any("Phiên bản đồng bộ" in n["text"] for n in notices.NOTICES.all())
    for store in (saved, listening.Listening(saved.path)):
        store.progress("book", 1, 600, 1000)
        store.set_reading("book", 1, 100)
        store.add_bookmark("book", 1, 600)
    assert listening.Listening(saved.path).get("book")["last"]["seconds"] == 600


def test_r1_ceiling_rolls_epoch_and_replays_without_losing_other_fields(tmp_path):
    saved = listening.Listening(tmp_path / "listening.json")
    mark = saved.add_bookmark("book", 1, 10, "kept")
    raw = json.loads(saved.path.read_text("utf-8"))
    next(iter(raw["records"].values()))["state"]["_clock"] = CAP
    saved.path.write_text(json.dumps(raw), encoding="utf-8")
    saved = listening.Listening(saved.path)
    saved.progress("book", 1, 600, 1000)
    state = listening.Listening(saved.path).get("book")
    assert state["last"]["rev"] == {"epoch": "1", "counter": 1, "node": saved._node()}
    assert state["bookmarks"][0]["id"] == mark["id"]
    saved.set_reading("book", 1, 100)
    assert saved.get("book")["reading"]["rev"]["counter"] == 2
    assert saved.get("book")["reading"]["rev"]["epoch"] == "1"


@pytest.mark.parametrize("peer", [
    {"last": {"chapterId": 1, "seconds": 600, "at": 200}},
    {"reading": {"chapterId": 1, "index": 100, "at": 200}},
    {"chapters": {"1": {"heard": 600, "at": 200}}},
    {"bookmarks": [{"id": "m", "chapterId": 1, "seconds": 20, "note": "changed", "at": 200}]},
    {"deleted": {"m": 200}}, {"rate": 1.5, "rateAt": 200},
])
def test_r2_missing_revision_is_rejected_atomically(tmp_path, peer):
    saved = listening.Listening(tmp_path / "listening.json")
    saved.progress("book", 1, 10, 1000)
    original = saved.path.read_bytes()
    with pytest.raises(ValueError, match="Dữ liệu đồng bộ thiếu phiên bản"):
        saved.merge("book", peer)
    assert saved.path.read_bytes() == original


def test_r2_note_edit_advances_revision(tmp_path):
    saved = listening.Listening(tmp_path / "listening.json")
    mark = saved.add_bookmark("book", 1, 10, "first")
    old = copy.deepcopy(mark["rev"])
    saved.update_bookmark("book", mark["id"], "changed")
    assert saved.get("book")["bookmarks"][0]["rev"]["counter"] > old["counter"]


def test_r3_clone_library_has_separate_install_identity_and_converges(tmp_path, monkeypatch):
    leftdir, rightdir = tmp_path / "left", tmp_path / "right"
    leftdir.mkdir()
    monkeypatch.setenv("ABOOK_PREFERENCES", str(tmp_path / "machine-left/preferences.json"))
    left = listening.Listening(leftdir / "listening.json")
    left.progress("book", 1, 10, 1000)
    shutil.copytree(leftdir, rightdir)
    monkeypatch.setenv("ABOOK_PREFERENCES", str(tmp_path / "machine-right/preferences.json"))
    right = listening.Listening(rightdir / "listening.json")
    left.set_reading("book", 1, 100, at=100)
    right.set_reading("book", 1, 200, at=100)
    a, b = left.get("book"), right.get("book")
    assert a["reading"]["rev"]["node"] != b["reading"]["rev"]["node"]
    assert not list(leftdir.glob("*.node.json"))
    assert listening.merge_states(a, b)["reading"] == listening.merge_states(b, a)["reading"]


def test_r4_constructor_reads_after_lock_and_keeps_committed_bookmark(tmp_path):
    path = tmp_path / "listening.json"
    store = listening.Listening(path)
    store.add_bookmark("book", 1, 10, "initial")
    raw = json.loads(path.read_text("utf-8"))
    next(iter(raw["records"].values()))["state"]["chapters"] = []
    path.write_text(json.dumps(raw), encoding="utf-8")
    lock, read = listening.file_lock, listening.notices.read_json
    held = False
    injected = False
    @contextmanager
    def acquire(target, **kwargs):
        nonlocal held, injected
        if target == path and not injected:
            injected = True
            with patch.object(listening, "file_lock", lock), patch.object(listening.notices, "read_json", read):
                other = listening.Listening(path)
                other.add_bookmark("book", 1, 20, "committed-by-other-writer")
        with lock(target, **kwargs):
            held = True
            try:
                yield
            finally:
                held = False
    def checked_read(target, *args, **kwargs):
        if target == path:
            assert held, "constructor read/repair outside file lock"
        return read(target, *args, **kwargs)
    with patch.object(listening, "file_lock", acquire), patch.object(listening.notices, "read_json", checked_read):
        opened = listening.Listening(path)
    assert [m["note"] for m in opened.get("book")["bookmarks"]] == ["initial", "committed-by-other-writer"]


def test_r4_constructor_snapshot_stamp_cannot_hide_a_writer_after_unlock(tmp_path):
    path = tmp_path / "listening.json"
    original = listening.Listening(path)
    original.add_bookmark("book", 1, 10, "initial")
    lock = listening.file_lock
    injected = False
    @contextmanager
    def acquire(target, **kwargs):
        nonlocal injected
        with lock(target, **kwargs):
            yield
        if target == path and not injected:
            injected = True
            with patch.object(listening, "file_lock", lock):
                other = listening.Listening(path)
                other.add_bookmark("book", 1, 20, "after-unlock")
    with patch.object(listening, "file_lock", acquire):
        opened = listening.Listening(path)
    opened.add_bookmark("book", 1, 30, "ours")
    assert [m["note"] for m in listening.Listening(path).get("book")["bookmarks"]] == ["initial", "after-unlock", "ours"]


@pytest.mark.parametrize("case", json.loads((FIXTURES / "malformed.json").read_text("utf-8")), ids=lambda c: c["name"])
def test_r6_shared_revision_validation(case):
    from abook.webui.listening_revision import revision
    assert bool(revision({"rev": case["rev"]})[0]) == case["valid"]


@pytest.mark.parametrize("case", json.loads((FIXTURES / "boundary.json").read_text("utf-8")), ids=lambda c: c["name"])
def test_r1_shared_boundary_fixture(case):
    merged = listening.merge_states(case["ours"], case["theirs"])
    assert merged["reading"] == case["expected"]
    assert merged["_clock"] == case["clock"]


def test_r3_backup_rules_exclude_writer_identity_for_both_android_backups():
    import xml.etree.ElementTree as ET
    base = Path(__file__).parents[1] / "mobile/android/app/src/main/res/xml"
    for file, groups in (("backup_rules.xml", ["."]), ("data_extraction_rules.xml", ["cloud-backup", "device-transfer"])):
        root = ET.parse(base / file).getroot()
        for group in groups:
            assert root.find(f"{group}/exclude[@domain='file'][@path='library/listening-node.json']") is not None


def test_r2_invalid_active_state_rejects_before_record_deletions(tmp_path):
    saved = listening.Listening(tmp_path / "listening.json")
    saved.progress("book", 1, 10, 1000)
    record = saved.records("book")[0]["id"]
    original = saved.path.read_bytes()
    with pytest.raises(ValueError, match="Dữ liệu đồng bộ thiếu phiên bản"):
        saved.merge_reply("book", record, {"record": record, "deletedRecords": {record: 100},
                                          "activeState": {"reading": {"chapterId": 1, "index": 200, "at": 100}}})
    assert saved.path.read_bytes() == original
    assert saved.get("book")["last"]["seconds"] == 10


def test_r7_broken_move_journal_opens_real_app_in_recovery(tmp_path):
    from abook.webui.server import App
    from abook.webui.actions import FakeRunner
    root = tmp_path / "library"
    root.mkdir()
    prefs = library.Preferences(tmp_path / "preferences.json")
    prefs.update({"libraryRoot": str(root)})
    intent = tmp_path / "library-move.json"
    original = b'{"oldRoot":'
    intent.write_bytes(original)
    for _ in range(2):
        app = App(preferences=prefs, runner=FakeRunner(), token="t")
        try:
            assert app.library_move_recovery
            assert intent.read_bytes() == original
            assert any(p.read_bytes() == original for p in tmp_path.glob("library-move.json.hong-*"))
            with pytest.raises(notices.Unreadable):
                app.change_library_preferences({"libraryRoot": str(tmp_path / "another")})
        finally:
            app.close()


@pytest.mark.parametrize("action", ["finish", "rollback", "ignore"])
def test_r7_explicit_recovery_checks_directories_and_keeps_journal(tmp_path, action):
    from abook.webui.server import App
    app = App.__new__(App)
    prefs = library.Preferences(tmp_path / "preferences.json")
    old, new = tmp_path / "old", tmp_path / "new"
    old.mkdir()
    new.mkdir()
    prefs.update({"libraryRoot": str(old)})
    app.preferences, app.library = prefs, library.Library(prefs)
    app.listening = listening.Listening(tmp_path / "listening.json")
    original = b'{"oldRoot":'
    app._library_move_path().write_bytes(original)
    with pytest.raises(ValueError, match="thư mục"):
        if action == "ignore":
            app.resolve_library_move(action, "", "")
        else:
            app.resolve_library_move(action, str(tmp_path / "missing"), str(tmp_path / "missing"))
    app.resolve_library_move(action, str(old), str(new))
    assert app.library.root == (new if action == "finish" else old)
    assert not app._library_move_path().exists()
    assert any(p.read_bytes() == original for p in tmp_path.glob("library-move.json.hong-*"))


@pytest.mark.parametrize("action", ["finish", "rollback"])
def test_r7_recovery_rekeys_profiles_and_survives_a_failed_commit(tmp_path, action):
    from abook.webui.server import App
    from abook.webui import packages
    old, new = tmp_path / "old", tmp_path / "new"
    source, target = (old, new) if action == "finish" else (new, old)
    book = source / packages.IMPORTED_FOLDER / "book"
    book.mkdir(parents=True)
    (book / "book.json").write_text(json.dumps({"title": "Book", "package": {}, "chapters": []}), encoding="utf-8")
    before = library.book_id(book)
    prefs = library.Preferences(tmp_path / "preferences.json")
    prefs.update({"libraryRoot": str(source)})
    saved = listening.Listening(tmp_path / "listening.json")
    mark = saved.add_bookmark(before, 1, 30, "precious")
    prefs.remember_position(before, 1, 30, 1000)
    source.rename(target)
    after = library.book_id(target / packages.IMPORTED_FOLDER / "book")
    app = App.__new__(App)
    app.preferences, app.listening, app.library = prefs, saved, library.Library(prefs)
    original = b'{"oldRoot":'
    app._library_move_path().write_bytes(original)
    with patch.object(saved, "_save", side_effect=OSError("full")):
        with pytest.raises(OSError):
            app.resolve_library_move(action, str(old), str(new))
    assert app._library_move_path().exists()
    assert any(p.read_bytes() == original for p in tmp_path.glob("library-move.json.hong-*"))
    app._adopt_new_book_ids()
    assert not app._library_move_path().exists()
    assert app.library.root == target
    assert saved.get(after)["bookmarks"][0]["id"] == mark["id"]
    assert after in prefs.get()["positions"]
