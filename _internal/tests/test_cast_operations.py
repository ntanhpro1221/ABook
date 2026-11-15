"""Original examples for durable cast batches, compensation and crash recovery."""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

import pytest

from abook import aliases, cast_operations as ops, listener_overrides as wishes
from abook.config import build_settings, settings_hash
from abook.database import ProjectDB
from abook.io_utils import sha256_file, sha256_text
from abook.models import ProjectPaths


@pytest.fixture
def book(tmp_path):
    paths = ProjectPaths.build(tmp_path / "book")
    db = ProjectDB(paths.db)
    settings = build_settings()
    db.initialize_book(title="Receipt example", project_root=paths.root, settings=settings,
                       settings_hash=settings_hash(settings), input_manifest_hash="fixture")
    source = paths.root / "sources" / "001.txt"
    source.parent.mkdir(parents=True)
    texts = ["Tôi mang hộp bút màu tím.", "Mai đặt khay gỗ lên bàn.", "Cửa sổ vừa mở được nửa chừng.", "Hải cất chiếc thước vào túi."]
    source.write_text("\n".join(texts), encoding="utf-8")
    chapter = db.ensure_chapters([{"chapter_index": 1, "title": "Example", "input_path": source,
                                  "input_sha256": sha256_file(source), "input_size": source.stat().st_size,
                                  "output_mp3": paths.chapters / "001.mp3"}])[0]
    db.replace_chapter_segments(chapter, [{"stable_id": f"line{i}", "seq": i, "text": text,
                                          "text_sha256": sha256_text(text), "kind_hint": "dialogue"}
                                         for i, text in enumerate(texts)])
    with db.connect() as conn:
        for i, name in enumerate(("AN", "MAI", "HẢI"), 1):
            conn.execute("INSERT INTO characters(id,canonical_name,display_name,gender,age,created_at,updated_at) VALUES(?,?,?,'unknown','adult',0,0)", (i, name, name.title()))
            conn.execute("INSERT INTO voice_profiles(id,voice_key,engine,preset_name,description,seed,status,created_at,updated_at) VALUES(?,?, 'vieneu',?,'',?,'ready',0,0)", (i, f"voice{i}", f"voice{i}", 100+i))
        for i, name in enumerate(("AN", "AN", "MAI", "HẢI")):
            person = (1, 1, 2, 3)[i]
            conn.execute("UPDATE segments SET kind='dialogue',speaker=?,canonical_character_id=?,voice_profile_id=?,gender='unknown',age='adult',status='verified',wav_path='evidence.wav',wav_sha256='kept' WHERE stable_id=?", (name, person, person, f"line{i}"))
    db.finalize_casting()
    db.update_chapter_status(chapter, "completed")
    return paths, db, settings


def row(db, stable="line0"):
    with db.connect() as conn:
        return dict(conn.execute("SELECT * FROM segments WHERE stable_id=?", (stable,)).fetchone())


def merge(book, *, target="MAI", source="AN", ids=("line0", "line1"), at=10, op=None):
    paths, db, settings = book
    lines = [(stable, row(db, stable)["text_sha256"]) for stable in ids]
    operation = ops.request_batch(paths.root, lines, target, source=source, now=at, op=op)
    ops.apply_pending(db, paths.root, settings["voices"])
    return operation


def undo(book, original):
    paths, db, settings = book
    op = ops.request_undo(paths.root, original, now=30)
    ops.apply_pending(db, paths.root, settings["voices"])
    return op


def test_merge_apply_undo_reopen_and_idempotent(book):
    paths, db, settings = book
    before = paths.root.joinpath("sources/001.txt").read_bytes()
    untouched = row(db, "line3")
    op = merge(book)
    assert row(db)["speaker"] == "MAI" and row(db)["wav_path"] is None
    assert row(db, "line3") == untouched
    assert ops.apply_pending(db, paths.root, settings["voices"]) == set()
    db = ProjectDB(paths.db)
    compensation = undo((paths, db, settings), op)
    assert row(db)["speaker"] == "AN"
    assert row(db)["listener_retakes"] == 0
    assert row(db, "line3") == untouched
    assert paths.root.joinpath("sources/001.txt").read_bytes() == before
    assert aliases.load(paths.root) == {}
    assert ops.history(paths.root)["items"][0]["state"] == "undone"
    assert undo((paths, db, settings), op) == compensation
    with db.connect() as conn:
        assert len(ops.receipts(conn)) == 2
    assert ops.apply_pending(db, paths.root, settings["voices"]) == set()
    assert aliases.load(paths.root) == {}
    merge((paths, db, settings), op=op)
    assert row(db)["speaker"] == "AN" and aliases.load(paths.root) == {}


def test_two_merges_undo_newest_then_first(book):
    paths, db, _ = book
    first = merge(book)
    second = merge(book, source="MAI", target="HẢI", ids=("line0", "line1", "line2"), at=20)
    undo(book, second)
    assert aliases.load(paths.root) == {aliases.key("AN"): "MAI"}
    assert row(db)["speaker"] == "MAI"
    undo(book, first)
    assert row(db)["speaker"] == "AN"
    assert row(db, "line2")["speaker"] == "MAI"
    assert aliases.load(paths.root) == {}


def test_two_merges_restore_an_existing_wish_without_a_false_conflict(book):
    paths, db, _ = book
    wishes.request_speaker(paths.root, "line0", row(db)["text_sha256"], "AN", now=5)
    first = merge(book)
    second = merge(book, source="MAI", target="HẢI", ids=("line0", "line1", "line2"), at=20)
    undo(book, second)
    undo(book, first)
    assert row(db)["speaker"] == "AN"
    assert all(item["conflicts"] == 0 for item in ops.history(paths.root)["items"])


def test_undo_earlier_merge_keeps_later_decisions_and_aliases(book):
    paths, db, _ = book
    first = merge(book)
    merge(book, source="MAI", target="HẢI", ids=("line0", "line1", "line2"), at=20)
    undo(book, first)
    assert row(db)["speaker"] == "HẢI"
    assert aliases.load(paths.root)[aliases.key("AN")] == "HẢI"
    assert next(item for item in ops.history(paths.root)["items"] if item["operationId"] == first)["conflicts"] == 2


@pytest.mark.parametrize("change", ["wish", "line", "voice", "seed", "source", "id", "retake"])
def test_new_decisions_are_never_overwritten(book, change):
    paths, db, _ = book
    original = merge(book)
    current = row(db)
    if change == "wish":
        wishes.request_speaker(paths.root, "line0", current["text_sha256"], "MAI", now=20)
    elif change == "line":
        wishes.request_line(paths.root, "line0", current["text_sha256"], emotion="happy", now=20)
    else:
        with db.connect() as conn:
            if change == "voice":
                conn.execute("UPDATE segments SET voice_profile_id=3 WHERE stable_id='line0'")
            elif change == "seed":
                conn.execute("UPDATE voice_profiles SET seed=seed+1 WHERE id=2")
            elif change == "source":
                conn.execute("UPDATE segments SET text_sha256='changed' WHERE stable_id='line0'")
            elif change == "id":
                conn.execute("UPDATE segments SET stable_id='other' WHERE stable_id='line0'")
            elif change == "retake":
                conn.execute("UPDATE segments SET listener_retakes=1 WHERE stable_id='line0'")
    with db.connect() as conn:
        preserved = [dict(r) for r in conn.execute("SELECT * FROM segments WHERE id=?", (current["id"],))]
    undo(book, original)
    with db.connect() as conn:
        assert [dict(r) for r in conn.execute("SELECT * FROM segments WHERE id=?", (current["id"],))] == preserved
    assert ops.history(paths.root)["items"][0]["conflicts"] >= 1


def test_failure_between_apply_and_receipt_rolls_back(book):
    paths, db, settings = book
    op = ops.request_batch(paths.root, [("line0", row(db)["text_sha256"])], "MAI", now=10, source="AN")
    before = row(db)
    with db.connect() as conn:
        conn.execute(f"CREATE TRIGGER crash_receipt BEFORE INSERT ON runtime_events WHEN NEW.code='{ops.RECEIPT_CODE}' BEGIN SELECT RAISE(ABORT, 'power loss'); END")
    with pytest.raises(sqlite3.IntegrityError, match="power loss"):
        ops.apply_pending(db, paths.root, settings["voices"])
    assert row(db) == before
    with db.connect() as conn:
        assert ops.receipts(conn) == {}
        conn.execute("DROP TRIGGER crash_receipt")
    ops.apply_pending(ProjectDB(paths.db), paths.root, settings["voices"])
    assert ops.history(paths.root)["items"][0]["operationId"] == op


def test_crash_after_commit_before_file_ack_replays_once(book, monkeypatch):
    paths, db, settings = book
    op = merge(book)
    ops.request_undo(paths.root, op, now=20)
    real_write = wishes._write
    monkeypatch.setattr(wishes, "_write", lambda *_: (_ for _ in ()).throw(OSError("power loss")))
    with pytest.raises(OSError, match="power loss"):
        ops.apply_pending(db, paths.root, settings["voices"])
    state = row(db)
    monkeypatch.setattr(wishes, "_write", real_write)
    assert ops.apply_pending(ProjectDB(paths.db), paths.root, settings["voices"]) == set()
    assert row(db) == state and aliases.load(paths.root) == {}


def test_pending_unmerge_and_continuation(book, tmp_path):
    paths, db, _ = book
    op = ops.request_batch(paths.root, [("line0", row(db)["text_sha256"])], "MAI", now=10, source="AN")
    target = tmp_path / "part2"
    target.mkdir()
    assert aliases.carry(paths.root, target) == 1
    wishes.withdraw_requests(paths.root, "speakers", ["line0"], 10)
    assert wishes.read_overrides(paths.root)[ops.SECTION][op]["cancelled"]
    assert aliases.load(paths.root) == {}
    assert aliases.load(target) == {aliases.key("AN"): "MAI"}


def test_pending_unmerge_crash_replays_alias_cancellation_without_applying_rows(book, monkeypatch):
    paths, db, settings = book
    op = ops.request_batch(paths.root, [("line0", row(db)["text_sha256"])], "MAI", now=10, source="AN")
    original_write = aliases._write
    monkeypatch.setattr(aliases, "_write", lambda *_: (_ for _ in ()).throw(OSError("power loss")))
    with pytest.raises(OSError, match="power loss"):
        wishes.withdraw_requests(paths.root, "speakers", ["line0"], 10)
    journal = wishes.read_overrides(paths.root)
    assert journal[ops.SECTION][op]["cancelled"] and not journal["speakers"]
    monkeypatch.setattr(aliases, "_write", original_write)
    ops.apply_pending(ProjectDB(paths.db), paths.root, settings["voices"])
    assert aliases.load(paths.root) == {} and row(db)["speaker"] == "AN"


def test_same_voice_preserves_audio_evidence(book):
    paths, db, _ = book
    with db.connect() as conn:
        conn.execute("UPDATE segments SET voice_profile_id=1 WHERE stable_id='line2'")
    before = row(db)
    merge(book)
    assert (row(db)["wav_path"], row(db)["wav_sha256"], row(db)["status"]) == (before["wav_path"], before["wav_sha256"], before["status"])


def test_only_changed_voices_lose_db_evidence_and_other_wav_bytes_survive(book):
    import wave

    paths, db, _ = book
    files = {}
    for i in range(4):
        path = paths.root / f"sample{i}.wav"
        with wave.open(str(path), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(16000)
            output.writeframes(b"\x00\x00" * 1600)
        files[f"line{i}"] = (path, path.read_bytes(), sha256_file(path))
        with db.connect() as conn:
            conn.execute("UPDATE segments SET wav_path=?,wav_sha256=? WHERE stable_id=?", (str(path), files[f"line{i}"][2], f"line{i}"))
    untouched = {stable: row(db, stable) for stable in ("line2", "line3")}
    original = merge(book)
    assert all(row(db, stable)["wav_path"] is None for stable in ("line0", "line1"))
    undo(book, original)
    for stable, expected in untouched.items():
        path, content, digest = files[stable]
        assert row(db, stable) == expected
        assert path.read_bytes() == content and sha256_file(path) == digest


def test_no_receipt_means_manual_split_and_no_schema_write(tmp_path):
    root = tmp_path / "old_book"
    root.mkdir()
    db = root / "project.sqlite3"
    sqlite3.connect(db).close()
    before = db.read_bytes()
    assert ops.history(root) == {"items": [], "manualOnly": True}
    assert db.read_bytes() == before


def test_same_id_different_payload_refused(book):
    paths, db, _ = book
    op = merge(book)
    with pytest.raises(ValueError, match="different content"):
        ops.request_batch(paths.root, [("line0", row(db)["text_sha256"])], "HẢI", now=50, source="AN", op=op)


def test_newer_alias_is_preserved_and_reported_separately(book):
    paths, db, _ = book
    op = merge(book)
    aliases.add(paths.root, "AN", "HẢI", now=20)
    undo(book, op)
    assert row(db)["speaker"] == "AN"
    assert aliases.load(paths.root)[aliases.key("AN")] == "HẢI"
    item = ops.history(paths.root)["items"][0]
    assert item["conflicts"] == 0 and item["aliasConflicts"] == 1


def test_receipts_contain_hashes_and_no_story_text(book):
    paths, db, _ = book
    merge(book)
    with db.connect() as conn:
        data = json.dumps(ops.receipts(conn), ensure_ascii=False)
    for line in (paths.root / "sources/001.txt").read_text(encoding="utf-8").splitlines():
        assert line not in data
    assert '"seed": 101' in data and '"voice_key": "voice1"' in data


def test_packaged_history_two_senders_sync_and_source_ownership(book, tmp_path):
    from abook.webui import book_edits, book_wishes

    paths, db, settings = book
    original = merge(book)
    package = tmp_path / "package"
    package.mkdir()
    (package / "book.json").write_text(json.dumps({"cast": "cast.json", "chapters": []}), encoding="utf-8")
    exported = ops.with_history(paths.root, {"characters": [], "extras": [], "narrator": {}})
    (package / "cast.json").write_text(json.dumps(exported), encoding="utf-8")
    assert ops.history(package, package=True)["items"][0]["operationId"] == original
    first = book_wishes.request_cast_undo(package, original, now=50)
    book_wishes.request_cast_undo(package, original, now=99)
    portable = book_wishes.validate(book_edits.load(package)["wishes"])
    assert portable["cast_undos"][first]["requested_at"] == 50
    merged, conflicts = book_wishes.merge(portable, portable)
    assert conflicts == 0 and book_wishes.count(merged) == 1
    assert ops.history(package, package=True)["items"][0]["state"] == "pending"
    report = book_wishes.fold(paths.root, merged, now=100)
    assert report == {"requests": 1, "skipped": 0}
    ops.apply_pending(db, paths.root, settings["voices"])
    book_wishes.fold(paths.root, merged, now=200)
    assert ops.apply_pending(db, paths.root, settings["voices"]) == set()
    assert row(db)["speaker"] == "AN"
    with db.connect() as conn:
        assert len(ops.receipts(conn)) == 2


def test_unknown_portable_receipt_is_refused_and_counted(book):
    from abook.webui import book_wishes

    paths, db, _ = book
    fixture = json.loads((Path(__file__).parent / "fixtures/cast_history.json").read_text(encoding="utf-8"))
    assert ops.undo_id(fixture["original"]) == fixture["undoId"]
    portable = book_wishes.validate(fixture["wishes"])
    before = row(db)
    dropped = []
    assert book_wishes.fold(paths.root, portable, now=100, dropped=dropped) == {"requests": 0, "skipped": 1}
    assert dropped == [("cast_undos", fixture["undoId"])] and row(db) == before


@pytest.mark.parametrize("with_portrait", [False, True])
def test_listening_package_and_sync_export_the_same_history(book, with_portrait):
    from abook.config import save_settings
    from abook.webui import bookfile
    from abook.webui.sync import SyncApp

    paths, db, settings = book
    save_settings(paths.settings, settings)
    op = merge(book)
    portrait = None
    if with_portrait:
        import io
        from PIL import Image
        from abook import avatars

        image = io.BytesIO()
        Image.new("RGB", (256, 256), "blue").save(image, format="PNG")
        portrait = avatars.choose(paths.root, "MAI", image.getvalue())
    _manifest, files = bookfile.listening_layer(paths.root)
    packaged_cast = json.loads(files["cast.json"])
    packaged = packaged_cast["castHistory"]
    # This route needs no network transport or application state to serialize cast.json.
    synced_cast = json.loads(SyncApp.resolve_file(None, paths.root, "cast.json"))
    synced = synced_cast["castHistory"]
    assert packaged == synced
    assert packaged_cast == synced_cast
    assert packaged["items"][0]["operationId"] == op
    assert "before" not in json.dumps(packaged)
    if portrait:
        people = [person for group in ("characters", "extras", "carried") for person in packaged_cast.get(group, [])]
        assert any((person.get("avatar") or {}).get("file") == portrait["file"] for person in people)
        assert SyncApp.resolve_file(None, paths.root, portrait["file"]) == files[portrait["file"]]
        assert files[portrait["file"]].read_bytes() == avatars.image_file(paths.root, portrait["file"]).read_bytes()


def test_pending_undo_can_be_withdrawn_then_requested_again(book):
    paths, db, settings = book
    original = merge(book)
    compensation = ops.request_undo(paths.root, original, now=20)
    assert wishes.withdraw_requests(paths.root, "cast_undos", [compensation], 20) == [compensation]
    assert ops.history(paths.root)["items"][0]["state"] == "applied"
    ops.apply_pending(db, paths.root, settings["voices"])
    assert row(db)["speaker"] == "MAI"
    assert ops.request_undo(paths.root, original, now=30) == compensation
    ops.apply_pending(db, paths.root, settings["voices"])
    assert row(db)["speaker"] == "AN"


def test_listen_only_can_read_history_but_cannot_queue_undo():
    from abook.webui.remote_studio import permitted

    assert permitted("GET", "/api/books/b1/cast-history", producing=False)
    assert not permitted("POST", "/api/books/b1/cast-history/undo", producing=False)
    assert permitted("POST", "/api/books/b1/cast-history/undo", producing=True)


def test_pipeline_counts_undo_pending_until_worker_applies_it(book, monkeypatch):
    from tests.test_listener_overrides import _Pipeline
    from abook.webui import store

    paths, db, settings = book
    monkeypatch.setattr(time, "time", lambda: 1000.0)
    original = merge(book)
    pipeline = _Pipeline(paths, db)
    pipeline.settings = settings
    pipeline._apply_listener_overrides()
    ops.request_undo(paths.root, original, now=1001.0)
    assert store.pending_changes(paths.root, 0) == 1
    assert store.pending_details(paths.root, 0)["items"][0]["section"] == "cast_undos"
    pipeline._apply_listener_overrides()
    assert row(db)["speaker"] == "AN"
    assert store.pending_changes(paths.root, 0) == 0


def test_history_endpoint_survives_server_reopen_and_queues_exact_operation(book, tmp_path):
    from abook.config import save_settings
    from abook.webui.actions import FakeRunner
    from abook.webui.library import Preferences, book_id
    from abook.webui.server import App, Server
    from tests.test_webui_listen_and_sync import _request

    paths, db, settings = book
    save_settings(paths.settings, settings)
    original = merge(book)
    prefs = Preferences(tmp_path / "prefs/preferences.json")
    prefs.update({"libraryRoot": str(tmp_path)})
    for iteration in range(2):
        app = App(preferences=prefs, runner=FakeRunner(), token="test")
        server = Server(app, port=0).start()
        url = f"/api/books/{book_id(paths.root)}/cast-history"
        try:
            status, body, _ = _request(server.port, "GET", url, headers={"X-Ebook-Token": "test"})
            assert status == 200 and json.loads(body)["items"][0]["operationId"] == original
            status, body, _ = _request(server.port, "POST", url + "/undo", headers={"X-Ebook-Token": "test"}, body={"operationId": original})
            assert status == 200 and json.loads(body)["operationId"] == ops.undo_id(original)
        finally:
            server.stop()
            app.close()
