"""Nhạc nền đi theo file sách `.abook` (chủ sách 01-10: sách xuất ra mang nhạc người sản xuất đã gắn) - đóng gói, kiểm khi
mở, và phát lại từ cuốn đã nhập ở máy khác."""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from ebook_reader.webui import bookfile, music_plan, packages
from ebook_reader.webui.bookfile import BookFile, BookFileError
from tests.test_a_project_can_be_renamed_or_deleted import _call, studio  # noqa: F401 - fixture dùng chung
from tests.test_webui_listen_and_sync import _request, make_project

CALM, BATTLE = "https://x/calm.mp3", "https://x/battle.mp3"


def _plan(project: Path, *, enabled: bool = True) -> None:
    scenes = [{"chapterId": 1, "start": 0.0, "end": 30.0, "link": CALM, "key": "1:1"},
              {"chapterId": 1, "start": 30.0, "end": 60.0, "link": CALM, "key": "1:5"},
              {"chapterId": 1, "start": 60.0, "end": 90.0, "link": BATTLE, "key": "1:9"}]
    plan = {"version": music_plan.PLAN_VERSION, "enabled": enabled, "levelDb": -18.0, "scenes": scenes,
            "tracks": {CALM: {"title": "Calm", "creator": "A", "attribution": "Calm by A (CC BY 4.0)"},
                       BATTLE: {"title": "Battle", "creator": "B", "attribution": "Battle by B (CC BY 4.0)"}}}
    (project / music_plan.PLAN_FILE).write_text(json.dumps(plan), encoding="utf-8")


def _tracks(tmp_path: Path, *, missing: tuple[str, ...] = ()):
    folder = tmp_path / "cache"
    folder.mkdir(exist_ok=True)

    def track(link: str) -> Path | None:
        if link in missing:
            return None
        path = folder / music_plan.track_name(link).split("/")[1]
        path.write_bytes(b"ID3" + link.encode() * 20)
        return path

    return track


def test_the_book_file_carries_the_producers_music(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    _plan(project)
    path = bookfile.pack(project, tmp_path / f"sach{bookfile.EXTENSION}", music_track=_tracks(tmp_path))
    calm, battle = music_plan.track_name(CALM), music_plan.track_name(BATTLE)
    with zipfile.ZipFile(path) as archive:
        assert archive.getinfo(calm).compress_type == zipfile.ZIP_STORED, "nhạc phát thẳng trong gói như audio chương"
    with BookFile(path) as book:
        book.verify()
        manifest = json.loads(book.read("book.json"))
        assert manifest["package"]["version"] == 2
        music = manifest["music"]
        assert music["levelDb"] == -18.0 and set(music["tracks"]) == {calm, battle}
        assert music["tracks"][calm]["attribution"] == "Calm by A (CC BY 4.0)", "ghi công đi theo bài"
        assert music["chapters"]["1"] == [{"start": 0.0, "end": 60.0, "track": calm},
                                          {"start": 60.0, "end": 90.0, "track": battle}], "hai đoạn liền cùng bài gộp"


def test_a_book_without_music_keeps_the_old_format_so_older_apps_open_it(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    _plan(project, enabled=False)
    path = bookfile.pack(project, tmp_path / f"sach{bookfile.EXTENSION}", music_track=_tracks(tmp_path))
    with BookFile(path) as book:
        manifest = json.loads(book.read("book.json"))
    assert manifest["package"]["version"] == 1 and "music" not in manifest
    assert not any(name.startswith("music/") for name in manifest["package"]["files"])


def test_a_track_that_cannot_be_fetched_leaves_silence_not_a_failed_export(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    _plan(project)
    path = bookfile.pack(project, tmp_path / f"sach{bookfile.EXTENSION}", music_track=_tracks(tmp_path, missing=(BATTLE,)))
    with BookFile(path) as book:
        music = json.loads(book.read("book.json"))["music"]
    assert [cue["track"] for cue in music["chapters"]["1"]] == [music_plan.track_name(CALM)]


def test_a_music_entry_without_its_file_is_refused(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    _plan(project)
    path = bookfile.pack(project, tmp_path / f"sach{bookfile.EXTENSION}", music_track=_tracks(tmp_path))
    gone = music_plan.track_name(BATTLE)
    broken = tmp_path / f"thieu{bookfile.EXTENSION}"

    def drop(name: str, data: bytes) -> bytes | None:
        if name == gone:
            return None
        if name == "book.json":
            book = json.loads(data)
            del book["package"]["files"][gone]
            return json.dumps(book).encode()
        return data

    with zipfile.ZipFile(path) as source, zipfile.ZipFile(broken, "w") as sink:
        for info in source.infolist():
            data = drop(info.filename, source.read(info.filename))
            if data is not None:
                sink.writestr(info, data)
    with pytest.raises(BookFileError, match="nhạc nền"):
        BookFile(broken)


def test_a_book_opened_from_a_file_plays_its_packaged_music(studio, tmp_path: Path) -> None:  # noqa: F811
    _paths, app, server, _runner = studio
    project = make_project(tmp_path / "may_khac")
    _plan(project)
    path = bookfile.pack(project, tmp_path / f"sach{bookfile.EXTENSION}", music_track=_tracks(tmp_path))
    opened = app.open_book_file(str(path))
    book = opened["id"]
    folder = app.library.resolve_listenable(book)
    assert packages.is_package(folder)
    status, cues = _call(server, "GET", f"/api/books/{book}/music/chapters/1")
    assert status == 200 and cues["levelDb"] == -18.0 and len(cues["cues"]) == 2
    first = cues["cues"][0]
    assert first["src"].startswith(f"/api/books/{book}/music/files/") and first["start"] == 0.0
    status, body, _headers = _request(server.port, "GET", first["src"], headers={"X-Ebook-Token": "t"})
    assert status == 200 and body.startswith(b"ID3")
    status, _body, _headers = _request(server.port, "GET", f"/api/books/{book}/music/files/{'0' * 40}.mp3",
                                       headers={"X-Ebook-Token": "t"})
    assert status == 404, "chỉ bài có trong sách"
