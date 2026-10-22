"""a101 F1 + F5: thư viện lớn - dòng `/sync/v1/library` và các tóm tắt của store nhớ theo chữ ký cuốn, và đổi thì thấy ngay lần hỏi sau."""
from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path

import pytest

from abook.webui import export, store, sync
from abook.webui.library import Library, Preferences
from abook.webui.listening import Listening
from abook.webui.sync import Devices, SyncApp
from tests.test_webui_listen_and_sync import make_project


def _age(project: Path, seconds: float = 120.0) -> None:
    """Mốc sửa của mọi file / thư mục trong cuốn lùi `seconds` giây: quá RACY_SECONDS nên kết quả nhớ được (một cuốn vừa ghi thì không nhớ)."""
    stamp = time.time() - seconds
    for folder, names, files in os.walk(project):
        for name in (*names, *files):
            os.utime(Path(folder) / name, (stamp, stamp))
    os.utime(project, (stamp, stamp))


@pytest.fixture()
def app(tmp_path: Path):
    root = tmp_path / "thu_vien"
    root.mkdir()
    project = make_project(root)
    preferences = Preferences(tmp_path / "prefs" / "preferences.json")
    preferences.update({"libraryRoot": str(root)})
    shared = SyncApp(Library(preferences), Listening(tmp_path / "listening.json"), Devices(tmp_path / "devices.json"), "Máy thử")
    _age(project)
    return shared, project


def _count(monkeypatch, module, name: str) -> list[int]:
    real = getattr(module, name)
    calls = [0]

    def counted(*args, **kwargs):
        calls[0] += 1
        return real(*args, **kwargs)

    monkeypatch.setattr(module, name, counted)
    return calls


def test_library_rows_are_remembered_until_the_book_changes(app, monkeypatch) -> None:
    shared, project = app
    built = _count(monkeypatch, sync, "manifest")
    first = shared.library_view()
    assert len(first) == 1 and built[0] == 1
    assert shared.library_view() == first and built[0] == 1, "không đổi gì thì không dựng lại dòng"
    assert {"audioVersion", "metaVersion", "bytes", "cover", "producing", "series", "chaptersAvailable"} <= set(first[0])


def test_a_row_is_a_private_copy(app) -> None:
    shared, _project = app
    shared.library_view()[0]["title"] = "bị sửa"
    assert shared.library_view()[0]["title"] != "bị sửa"


def test_renaming_the_book_shows_in_the_next_listing(app) -> None:
    shared, project = app
    before = shared.library_view()[0]
    store.set_display_title(project, "Tên mới của bạn")
    _age(project)
    after = shared.library_view()[0]
    assert after["title"] == "Tên mới của bạn"
    assert after["metaVersion"] != before["metaVersion"], "đổi tên là một phiên bản mô tả mới - điện thoại đã tải thấy và lấy lại phần mô tả"
    assert after["audioVersion"] == before["audioVersion"]


def test_replacing_a_chapter_audio_shows_in_the_next_listing(app) -> None:
    shared, project = app
    before = shared.library_view()[0]
    (project / "output" / "chapters" / "00001_645.mp3").write_bytes(b"ID3" + bytes(range(256)) * 80)
    _age(project)
    after = shared.library_view()[0]
    assert after["audioVersion"] != before["audioVersion"] and after["bytes"] > before["bytes"]


def test_a_new_cover_shows_in_the_next_listing(app) -> None:
    shared, project = app
    assert shared.library_view()[0]["cover"] is None
    (project / "cover.jpg").write_bytes(b"\xff\xd8\xff" + b"x" * 300)
    _age(project)
    assert shared.library_view()[0]["cover"] is not None


def test_a_row_of_a_book_in_production_is_never_remembered(app, monkeypatch) -> None:
    """Nhịp tim của worker hết hạn theo đồng hồ chứ không theo file: dòng "đang làm" nhớ thì còn "đang làm" mãi sau khi worker chết."""
    shared, project = app
    db = sqlite3.connect(project / "project.sqlite3")
    db.execute("CREATE TABLE worker_leases (id INTEGER PRIMARY KEY, heartbeat_at REAL)")
    db.execute("INSERT INTO worker_leases VALUES (1, ?)", (time.time(),))
    db.commit()
    db.close()
    _age(project)
    built = _count(monkeypatch, sync, "manifest")
    assert shared.library_view()[0]["producing"] is True
    assert shared.library_view()[0]["producing"] is True and built[0] == 2
    monkeypatch.setattr(store, "LEASE_FRESH_SECONDS", 0.0)  # đồng hồ chạy qua hạn của nhịp tim, không file nào đổi
    assert shared.library_view()[0]["producing"] is False


def test_a_downloaded_music_track_changes_the_row(app, monkeypatch, tmp_path: Path) -> None:
    shared, _project = app
    track = tmp_path / "bai.mp3"
    tracks: dict[str, Path] = {}
    shared.music_track = lambda link: tracks.get(link)
    monkeypatch.setattr(export, "music_links", lambda *args, **kwargs: {"bai-1"})
    built = _count(monkeypatch, sync, "manifest")
    shared.library_view()
    shared.library_view()
    assert built[0] == 1
    track.write_bytes(b"ID3" + b"\0" * 5000)
    tracks["bai-1"] = track  # bài tải xong: không file nào trong thư mục sách đổi
    shared.library_view()
    assert built[0] == 2


def test_the_summaries_of_the_store_are_remembered_and_follow_the_book(app, monkeypatch) -> None:
    _shared, project = app
    built = _count(monkeypatch, store, "_summarize")
    first = store.summarize(project)
    assert store.summarize(project) == first and built[0] == 1
    first["title"] = "bị sửa"
    assert store.summarize(project)["title"] != "bị sửa", "người gọi sửa kết quả thì bản nhớ không đổi theo"
    chapters = store.chapters(project)
    cast = store.cast(project)
    assert store.chapters(project) == chapters and store.cast(project) == cast
    db = sqlite3.connect(project / "project.sqlite3")
    db.execute("UPDATE chapters SET status = 'completed', output_mp3 = '00002_646.mp3' WHERE id = 2")
    db.execute("INSERT INTO characters VALUES (2, 'MAI', 'MAI', 'female', 'young', 'main', 3, '')")
    db.execute("UPDATE segments SET speaker = 'MAI', kind = 'dialogue' WHERE id = 5")
    db.commit()
    db.close()
    (project / "output" / "chapters" / "00002_646.mp3").write_bytes(b"ID3" + b"\0" * 300)
    _age(project)
    assert store.summarize(project)["chapters"]["completed"] == first["chapters"]["completed"] + 1
    assert [c["playable"] for c in store.chapters(project)] == [True, True]
    assert "MAI" in {person["name"] for person in store.cast(project)["characters"] + store.cast(project)["extras"]}


def test_a_summary_of_a_running_book_is_not_remembered(app, monkeypatch) -> None:
    _shared, project = app
    built = _count(monkeypatch, store, "_summarize")
    assert store.summarize(project, running=True)["running"] is True
    assert store.summarize(project, running=True)["running"] is True
    assert built[0] == 2
    assert store.summarize(project)["running"] is False, "tham số khác nhau không dùng chung bản nhớ"


def test_a_book_just_written_is_not_remembered(app, monkeypatch) -> None:
    """Mốc sửa chỉ nhích theo nhịp đồng hồ hệ thống: sổ vừa ghi trong RACY_SECONDS giây có thể ghi tiếp mà không đổi chữ ký."""
    _shared, project = app
    now = time.time()
    for path in (project / "project.sqlite3", project / "book_settings.json"):
        os.utime(path, (now, now))
    built = _count(monkeypatch, store, "_summarize")
    store.summarize(project)
    store.summarize(project)
    assert built[0] == 2
