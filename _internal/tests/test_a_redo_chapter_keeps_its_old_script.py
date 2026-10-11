"""Chương chờ thu lại theo sửa của người nghe (soát UX a25 T7): MP3 cũ vẫn là bản nghe được, nên nó phải đi cùng chữ đọc theo CŨ
khớp nó - chữ, người nói và mốc từng câu lúc chương xong. Bước đặt lại xoá thời lượng câu, nên dây chuyền chụp chữ đọc theo của
mọi chương đã xong ngay trước khi áp sửa (`store.keep_heard_scripts`); trang đọc và file `.abook` dùng bản chụp tới khi có MP3 mới."""
from __future__ import annotations

from pathlib import Path

from abook.database import LISTENER_REDO
from abook.listener_overrides import request_speaker
from abook.webui import store
from tests.test_listener_overrides import _Pipeline
from tests.test_listener_speakers import _book


def _recorded(tmp_path: Path):
    paths, db = _book(tmp_path)
    with db.connect() as conn:
        conn.execute("UPDATE segments SET wav_duration = 1.5 + seq, break_ms = 200")
    paths.chapters.mkdir(parents=True, exist_ok=True)
    (paths.chapters / "001.mp3").write_bytes(b"ID3" + bytes(range(256)) * 40)
    return paths, db


def test_a_chapter_waiting_for_a_retake_keeps_the_script_of_its_old_recording(tmp_path: Path) -> None:
    paths, db = _recorded(tmp_path)
    before = store.chapter_script(paths.root, 1)
    assert before["timed"] and before["segments"][2]["speaker"] == "Lucien"

    request_speaker(paths.root, "c1s2", "sha-c1s2", "NATASHA", now=700.0)
    assert _Pipeline(paths, db)._apply_listener_overrides() == {1}
    with db.connect() as conn:
        chapter = conn.execute("SELECT status, last_error FROM chapters WHERE id = 1").fetchone()
        assert chapter["status"] == "warning" and str(chapter["last_error"]).startswith(LISTENER_REDO)
        assert conn.execute("SELECT wav_duration FROM segments WHERE stable_id = 'c1s2'").fetchone()[0] is None

    after = store.chapter_script(paths.root, 1)
    assert after["timed"], "MP3 cũ còn nghe được: trang đọc không được nói 'chưa thu thành sách nói'"
    assert [(s["start"], s["end"]) for s in after["segments"]] == [(s["start"], s["end"]) for s in before["segments"]]
    assert after["segments"][2]["speaker"] == "Lucien", "chữ đọc theo khớp bản thu cũ, không phải sửa chưa thu"
    assert store.chapter_spans(paths.root, 1) == {s["id"]: (s["start"], s["end"]) for s in before["segments"]}


def test_the_snapshot_is_taken_once_and_dropped_when_the_recording_changes(tmp_path: Path) -> None:
    paths, db = _recorded(tmp_path)
    assert store.keep_heard_scripts(paths.root) == 1
    assert store.keep_heard_scripts(paths.root) == 0, "bản chụp mới hơn MP3: không chụp lại"

    with db.connect() as conn:
        conn.execute("UPDATE chapters SET status = 'warning', last_error = ? WHERE id = 1", (LISTENER_REDO + "x",))
        conn.execute("UPDATE segments SET wav_duration = NULL WHERE stable_id = 'c1s2'")
    assert store.chapter_script(paths.root, 1)["timed"]
    (paths.chapters / "001.mp3").write_bytes(b"ID3" + b"\0" * 99)  # MP3 khác: bản chụp không còn khớp
    assert not store.chapter_script(paths.root, 1)["timed"]
    assert store.chapter_spans(paths.root, 1) == {}


def test_a_book_file_made_while_chapters_wait_is_whole_and_reads_along_with_the_old_audio(tmp_path: Path) -> None:
    """File `.abook` xuất lúc chương chờ thu lại: MP3 cũ, chữ đọc theo cũ có mốc, và "trọn vẹn" khớp "mọi chương có audio"."""
    import json

    from abook.webui import bookfile

    paths, db = _recorded(tmp_path)
    request_speaker(paths.root, "c1s2", "sha-c1s2", "NATASHA", now=700.0)
    _Pipeline(paths, db)._apply_listener_overrides()
    book, files = bookfile.listening_layer(paths.root)
    assert (book["chaptersAvailable"], book["chaptersTotal"], book["complete"]) == (1, 1, True)
    script = json.loads(files[book["chapters"][0]["script"]])
    assert script["timed"] and script["segments"][2]["speaker"] == "Lucien"
