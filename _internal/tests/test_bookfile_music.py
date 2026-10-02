"""Nhạc nền đi theo file sách `.abook` (chủ sách 01-10: sách xuất ra mang nhạc người sản xuất đã gắn) - đóng gói, kiểm khi
mở, và phát lại từ cuốn đã nhập ở máy khác."""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from abook.webui import bookfile, music_plan, packages
from abook.webui.bookfile import BookFile, BookFileError
from tests.test_a_project_can_be_renamed_or_deleted import _call, studio  # noqa: F401 - fixture dùng chung
from tests.test_webui_listen_and_sync import _request, make_project

CALM, BATTLE = "https://x/calm.mp3", "https://x/battle.mp3"


def _plan(project: Path, *, enabled: bool = True) -> None:
    scenes = [{"chapterId": 1, "start": 0.0, "end": 30.0, "link": CALM, "key": "1:1"},
              {"chapterId": 1, "start": 30.0, "end": 60.0, "link": CALM, "key": "1:5"},
              {"chapterId": 1, "start": 60.0, "end": 90.0, "link": BATTLE, "key": "1:9"}]
    plan = {"version": music_plan.PLAN_VERSION, "enabled": enabled, "levelDb": -18.0, "scenes": scenes,
            "tracks": {CALM: {"title": "Calm", "creator": "A", "attribution": "Calm by A (CC BY 4.0)",
                              "lufs": -26.0, "speechBand": 0.1},
                       BATTLE: {"title": "Battle", "creator": "B", "attribution": "Battle by B (CC BY 4.0)",
                                "lufs": -10.0, "speechBand": 0.7}}}
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
        assert music["tracks"][calm]["lufs"] == -26.0 and music["tracks"][calm]["speechBand"] == 0.1, "độ to đi theo bài"
        # gainDb tính một lần ở máy chủ (music_plan.cue_gain_db): -20 + (-18) - lufs - 8 x (speechBand - 0,30), kẹp <= 0.
        assert music["chapters"]["1"] == [{"start": 0.0, "end": 60.0, "track": calm, "gainDb": -7.39},
                                          {"start": 60.0, "end": 90.0, "track": battle, "gainDb": -28.19}
                                          ], "hai đoạn liền cùng bài gộp"


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
    assert first["gainDb"] == -7.39 and cues["cues"][1]["gainDb"] == -28.19, "trình phát chỉ áp gainDb của gói"
    status, body, _headers = _request(server.port, "GET", first["src"], headers={"X-Ebook-Token": "t"})
    assert status == 200 and body.startswith(b"ID3")
    status, _body, _headers = _request(server.port, "GET", f"/api/books/{book}/music/files/{'0' * 40}.mp3",
                                       headers={"X-Ebook-Token": "t"})
    assert status == 404, "chỉ bài có trong sách"


def test_the_music_credits_ride_along_with_the_cues_of_a_packaged_book(studio, tmp_path: Path) -> None:  # noqa: F811
    """CC BY đòi nêu tác giả ở nơi nhạc phát: trình phát lấy ghi công của bài đang nghe từ chính phản hồi mốc nhạc."""
    _paths, app, server, _runner = studio
    project = make_project(tmp_path / "may_khac")
    _plan(project)
    path = bookfile.pack(project, tmp_path / f"sach{bookfile.EXTENSION}", music_track=_tracks(tmp_path))
    book = app.open_book_file(str(path))["id"]
    status, cues = _call(server, "GET", f"/api/books/{book}/music/chapters/1")
    assert status == 200
    # Khoá theo `link` của mốc (cùng chuỗi trình phát giữ ở MusicBed.activeLink); chỉ khoá nào có thì mới có mặt.
    assert {cue["link"] for cue in cues["cues"]} == {CALM, BATTLE}
    assert cues["credits"] == {CALM: {"title": "Calm", "creator": "A", "attribution": "Calm by A (CC BY 4.0)"},
                               BATTLE: {"title": "Battle", "creator": "B", "attribution": "Battle by B (CC BY 4.0)"}}
    status, none = _call(server, "GET", f"/api/books/{book}/music/chapters/2")
    assert status == 200 and none["cues"] == [] and none["credits"] == {}


def test_the_phone_package_carries_the_music_already_on_this_machine(tmp_path: Path) -> None:
    from abook.webui.library import Library, Preferences
    from abook.webui.listening import Listening
    from abook.webui.sync import Devices, SyncApp, manifest

    project = make_project(tmp_path)
    listening = Listening(tmp_path / "listening.json")
    before = manifest(project, "b", listening, music_track=lambda _link: None)
    _plan(project)
    track = _tracks(tmp_path, missing=(BATTLE,))
    book = manifest(project, "b", listening, music_track=track)
    assert "music" not in before and [cue["track"] for cue in book["music"]["chapters"]["1"]] == [
        music_plan.track_name(CALM)], "chỉ bài đã có trên máy: lượt hỏi gói không tải gì"
    assert book["version"] != before["version"], "điện thoại thấy có cập nhật khi nhạc đổi"
    library = Library(Preferences(tmp_path / "prefs.json"))
    app = SyncApp(library, listening, Devices(tmp_path / "devices.json"), "may", music_track=track)
    found = app.resolve_file(project, music_plan.track_name(CALM))
    assert isinstance(found, Path) and found.read_bytes().startswith(b"ID3")
    assert app.resolve_file(project, music_plan.track_name(BATTLE)) is None
    assert app.resolve_file(project, f"music/{'0' * 40}.mp3") is None


def test_a_package_without_catalog_loudness_falls_back_to_the_median_track(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    _plan(project)
    plan = json.loads((project / music_plan.PLAN_FILE).read_text(encoding="utf-8"))
    for info in plan["tracks"].values():
        info.pop("lufs"), info.pop("speechBand")
    (project / music_plan.PLAN_FILE).write_text(json.dumps(plan), encoding="utf-8")
    music, _files = music_plan.package(project, [1], _tracks(tmp_path))  # file giả không phải âm thanh: không đo được
    assert all("lufs" not in info for info in music["tracks"].values())
    median = music_plan.cue_gain_db(-18.0, None, None)
    assert [cue["gainDb"] for cue in music["chapters"]["1"]] == [median, median]


def test_a_series_stores_a_shared_track_once_and_keys_the_cues_by_global_chapter_id(tmp_path: Path) -> None:
    """Cả bộ một file: hai phần dùng chung bài CALM thì file nhạc chỉ nằm một lần; mốc nhạc theo mã chương chung của bộ
    (phần x 100000 + mã trong phần), đúng như `scripts/<mã>.json` và `chapters[].id`."""
    from tests.test_export_series import _part

    library = tmp_path / "thu_vien"
    library.mkdir()
    one = _part(tmp_path, library, "p1", "Truyện X")
    two = _part(tmp_path, library, "p2", "Truyện X · Phần 2", one)
    _plan(one)
    _plan(two)
    plan = json.loads((two / music_plan.PLAN_FILE).read_text(encoding="utf-8"))
    plan["scenes"] = [scene for scene in plan["scenes"] if scene["link"] == CALM]  # phần 2 chỉ dùng CALM
    (two / music_plan.PLAN_FILE).write_text(json.dumps(plan), encoding="utf-8")
    path = bookfile.pack_series([one, two], tmp_path / f"bo{bookfile.EXTENSION}", music_track=_tracks(tmp_path))

    calm, battle = music_plan.track_name(CALM), music_plan.track_name(BATTLE)
    with zipfile.ZipFile(path) as archive:
        stored = [name for name in archive.namelist() if name.startswith("music/")]
        assert sorted(stored) == sorted([calm, battle]), "mỗi bài một file, dù hai phần cùng dùng"
        assert archive.getinfo(calm).compress_type == zipfile.ZIP_STORED
    with BookFile(path) as book:
        book.verify()
        manifest = json.loads(book.read("book.json"))
    music = manifest["music"]
    assert manifest["package"]["version"] == 3 and set(music["tracks"]) == {calm, battle}
    assert set(music["chapters"]) == {"100001", "200001"}, "mã chương chung của bộ"
    assert [cue["track"] for cue in music["chapters"]["200001"]] == [calm]
    assert music["chapters"]["100001"][0] == {"start": 0.0, "end": 60.0, "track": calm, "gainDb": -7.39}
    assert music_plan.packaged_cues(music, 200001)[0]["track"] == calm and music_plan.packaged_cues(music, 1) == []


def test_a_series_book_plays_the_music_of_its_second_part(studio, tmp_path: Path) -> None:  # noqa: F811
    from tests.test_export_series import _part

    _paths, app, server, _runner = studio
    library = tmp_path / "may_khac"
    library.mkdir()
    one = _part(tmp_path, library, "p1", "Truyện X")
    two = _part(tmp_path, library, "p2", "Truyện X · Phần 2", one)
    _plan(two)
    path = bookfile.pack_series([one, two], tmp_path / f"bo{bookfile.EXTENSION}", music_track=_tracks(tmp_path))
    book = app.open_book_file(str(path))["id"]

    status, cues = _call(server, "GET", f"/api/books/{book}/music/chapters/200001")
    assert status == 200 and len(cues["cues"]) == 2 and cues["cues"][0]["start"] == 0.0
    status, none = _call(server, "GET", f"/api/books/{book}/music/chapters/100001")
    assert status == 200 and none["cues"] == []
