"""Soát a26 L5: xuất file sách lúc chương chờ thu lại theo sửa của người nghe (đổi giọng người kể, đổi giọng nhân vật). Audio
trong gói là bản ĐÃ THU (giọng cũ) - nên tên giọng người kể (`book.json`) và giọng từng người trong `cast.json` phải là giọng của
bản ấy, không phải giọng mới chưa thu; và người nghe không thấy số "câu chờ thu lại" của Studio. Giọng của bản đã thu được chụp
cùng chữ đọc theo, ngay trước khi áp sửa (`store.keep_heard_scripts`)."""
from __future__ import annotations

import json
from pathlib import Path

from abook.config import save_settings
from abook.listener_overrides import request_voice
from abook.webui import bookfile, store
from tests.test_listener_overrides import _Pipeline
from tests.test_listener_voices import SETTINGS, _book
from tests.test_narrator_voice import FREE, NARRATOR_VOICE


def _recorded(tmp_path: Path):
    paths, db = _book(tmp_path)
    save_settings(paths.settings, SETTINGS)
    with db.connect() as conn:
        conn.execute("UPDATE segments SET wav_duration = 1.5 + seq, break_ms = 200")
    paths.chapters.mkdir(parents=True, exist_ok=True)
    (paths.chapters / "001.mp3").write_bytes(b"ID3" + bytes(range(256)) * 40)
    return paths, db


def _noah(cast: dict) -> str:
    return next(person["voice"]["preset"] for person in cast["characters"] + cast["extras"] if person["name"] == "NOAH")


def _apply(paths, db) -> set[int]:
    pipeline = _Pipeline(paths, db)
    pipeline.settings = SETTINGS
    return pipeline._apply_listener_overrides()


def test_a_book_file_made_while_chapters_wait_names_the_voices_of_its_audio(tmp_path: Path) -> None:
    paths, db = _recorded(tmp_path)
    noah_recorded = _noah(store.cast(paths.root))
    request_voice(paths.root, "NARRATOR", preset=FREE[0], now=1.0)
    request_voice(paths.root, "NOAH", gender="female", now=1.0)
    assert _apply(paths, db) == {1}
    studio = store.cast(paths.root)
    assert studio["narrator"]["voice"] == FREE[0] and studio["narrator"]["redo"] > 0 and _noah(studio) != noah_recorded, \
        "Studio vẫn thấy giọng mới và số câu chờ thu lại"

    book, files = bookfile.listening_layer(paths.root)
    assert book["narrator"] == NARRATOR_VOICE, "audio trong gói đọc bằng giọng cũ"
    cast = json.loads(files["cast.json"])
    assert cast["narrator"]["voice"] == NARRATOR_VOICE and not cast["narrator"].get("redo")
    assert _noah(cast) == noah_recorded


def test_once_the_chapter_is_recorded_again_the_package_names_the_new_voices(tmp_path: Path) -> None:
    paths, db = _recorded(tmp_path)
    request_voice(paths.root, "NARRATOR", preset=FREE[0], now=1.0)
    _apply(paths, db)
    (paths.chapters / "001.mp3").write_bytes(b"ID3" + b"\1" * 999)  # thu lại xong: MP3 mới
    db.update_chapter_status(1, "completed")

    book, files = bookfile.listening_layer(paths.root)
    assert book["narrator"] == FREE[0]
    assert json.loads(files["cast.json"])["narrator"]["voice"] == FREE[0]
