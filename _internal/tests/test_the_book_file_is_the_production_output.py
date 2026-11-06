"""Cuốn đã xong thì dây chuyền tự xuất file sách của app vào `output/` (chủ sách 27-09: "đầu ra của máy sản xuất sẽ là
file này"). Lỗi đóng gói không bao giờ làm hỏng cuốn sách: audio và báo cáo đã commit trước bước này.

Không gọi `BookPipeline.__init__`: chỉ bước xuất là thật; sách là cuốn hai chương của test đồng bộ.
"""
from __future__ import annotations

from pathlib import Path
import json
from typing import Any

from abook.models import ProjectPaths
from abook.pipeline import BookPipeline
from abook.webui import bookfile
from abook.io_utils import sha256_file
from tests.test_webui_listen_and_sync import make_project


class _Db:
    def __init__(self, status: str) -> None:
        self.status = status
        self.events: list[tuple[str, str]] = []

    def book(self) -> dict[str, Any]:
        return {"status": self.status, "title": "Sách thử · Tập 1"}

    def event(self, level: str, code: str, message: str, details: dict | None = None) -> None:
        self.events.append((level, code))


class _Pipeline(BookPipeline):
    def __init__(self, project: Path, status: str) -> None:
        self.paths = ProjectPaths.build(project)
        self.db = _Db(status)
        self.logs: list[str] = []

    def log(self, message: str) -> None:
        self.logs.append(message)


def _output(project: Path) -> Path:
    return project / "output" / bookfile.default_name("Sách thử · Tập 1")


def _finished_project(tmp_path: Path) -> Path:
    import shutil
    import sqlite3
    project = make_project(tmp_path)
    second = project / "output" / "chapters" / "00002_646.mp3"
    shutil.copyfile(project / "output" / "chapters" / "00001_645.mp3", second)
    with sqlite3.connect(project / "project.sqlite3") as connection:
        connection.execute("UPDATE chapters SET status='completed',output_mp3=? WHERE id=2", (str(second),))
        connection.execute("UPDATE segments SET status='verified',wav_duration=3 WHERE id=5")
        connection.execute("INSERT INTO artifacts SELECT 'chapter_mp3:2',kind,?,sha256,size_bytes,verified,metadata_json,created_at,updated_at FROM artifacts WHERE artifact_key='chapter_mp3:1'", (str(second),))
    return project


def test_a_finished_book_leaves_its_book_file_in_output(tmp_path: Path) -> None:
    project = _finished_project(tmp_path)
    pipeline = _Pipeline(project, "completed")

    pipeline._export_book_file()

    with bookfile.BookFile(_output(project)) as book:
        book.verify()
    assert ("info", "BOOK_FILE_EXPORTED") in pipeline.db.events


def test_an_unfinished_book_leaves_nothing(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    _Pipeline(project, "synthesizing")._export_book_file()
    assert not _output(project).exists()


def test_a_packing_failure_is_an_event_not_a_broken_book(tmp_path: Path, monkeypatch) -> None:
    project = make_project(tmp_path)
    pipeline = _Pipeline(project, "completed")

    def broken(*_args, **_kwargs):
        raise OSError("ổ đầy")

    monkeypatch.setattr(bookfile, "pack", broken)
    pipeline._export_book_file()  # không được ném

    assert ("warning", "BOOK_FILE_EXPORT_FAILED") in pipeline.db.events


def test_an_already_finished_book_gets_its_file_once(tmp_path: Path) -> None:
    project = _finished_project(tmp_path)
    pipeline = _Pipeline(project, "completed")
    pipeline._export_book_file(only_if_missing=True)
    first = _output(project).stat().st_mtime_ns

    pipeline._export_book_file(only_if_missing=True)

    assert _output(project).stat().st_mtime_ns == first, "đường tắt của sách đã xong không đóng gói lại mỗi lần"


def test_completed_status_does_not_hide_a_missing_chapter(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    pipeline = _Pipeline(project, "completed")
    pipeline._export_book_file()
    assert not _output(project).exists()
    assert ("warning", "BOOK_FILE_EXPORT_FAILED") in pipeline.db.events


def test_completed_resume_replaces_a_package_with_older_mastered_audio(tmp_path: Path) -> None:
    project=_finished_project(tmp_path)
    pipeline=_Pipeline(project,'completed')
    book,files=bookfile.listening_layer(project)
    chapters=[ch for ch in book['chapters'] if ch.get('file')]
    levels={'verdict':'pass','audio_sha256':{str(ch['id']):sha256_file(files[ch['file']]) for ch in chapters}}
    pipeline._book_levels=levels
    report=project/'output'/'reports'/'levelQa.json'
    report.parent.mkdir(parents=True,exist_ok=True)
    report.write_text(json.dumps(levels),encoding='utf8',newline='\n')
    pipeline._export_book_file()
    changed=chapters[0]
    audio=files[changed['file']]
    audio.write_bytes(audio.read_bytes()+b'new synthetic master')
    levels['audio_sha256'][str(changed['id'])]=sha256_file(audio)
    # Một master đã công bố phải có receipt hiện hành trong SQLite trước khi đóng gói.
    import sqlite3
    with sqlite3.connect(project / 'project.sqlite3') as connection:
        connection.execute('UPDATE artifacts SET sha256=?,size_bytes=? WHERE path=?',
                           (sha256_file(audio), audio.stat().st_size, str(audio)))
    report.write_text(json.dumps(levels),encoding='utf8',newline='\n')
    pipeline._export_book_file(only_if_missing=True)
    with bookfile.BookFile(_output(project)) as opened:
        opened.verify()
        assert opened.chapter_prints[changed['file']]['sha256']==levels['audio_sha256'][str(changed['id'])]
        assert opened.book['levelQa']==levels
    latest=_output(project).stat().st_mtime_ns
    pipeline._export_book_file(only_if_missing=True)
    assert _output(project).stat().st_mtime_ns==latest
