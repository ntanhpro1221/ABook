"""Một dự án Studio trong một file `.abookproj` (webui/projectfile.py): gói, kiểm, mở ở chỗ khác."""
from __future__ import annotations

import json
import sqlite3
import zipfile
from pathlib import Path

import pytest

from abook.webui import projectfile, store
from abook.webui.projectfile import MIMETYPE, ProjectFile, ProjectFileError
from tests.test_webui_listen_and_sync import make_project


def _project(tmp_path: Path) -> Path:
    """Dự án có nguồn chương nằm NGOÀI thư mục dự án và sổ ghi gốc dự án, như dự án Studio thật."""
    project = make_project(tmp_path / "may_cu")
    sources = tmp_path / "nguon"
    sources.mkdir()
    (sources / "645.txt").write_text("Chương 645 - Trở về (1)\n\nTrời đã sáng.\n“Đi thôi.”\n", encoding="utf-8")
    (sources / "646.txt").write_text("Chương 646 - Trở về (2)\n\nChưa thu.\n", encoding="utf-8")
    (project / "logs").mkdir()
    (project / "logs" / "abook.log").write_text("nhật ký", encoding="utf-8")
    (project / ".worker.lock").write_text("", encoding="utf-8")
    (project / "output" / "Sách thử.abook").write_bytes(b"PK")
    with sqlite3.connect(project / store.DB_NAME) as db:
        db.execute("ALTER TABLE book ADD COLUMN project_root TEXT")
        db.execute("UPDATE book SET project_root = ?", (str(project.resolve()),))
        db.execute("UPDATE chapters SET input_path = ? WHERE id = 1", (str(sources / "645.txt"),))
        db.execute("UPDATE chapters SET input_path = ? WHERE id = 2", (str(sources / "646.txt"),))
    return project


def _rows(project: Path, sql: str) -> list[tuple]:
    with sqlite3.connect(project / store.DB_NAME) as db:
        return db.execute(sql).fetchall()


def test_a_project_moves_to_a_new_place_whole(tmp_path: Path) -> None:
    project = _project(tmp_path)
    packed = projectfile.pack(project, tmp_path / "chuyen" / "du_an.abookproj")
    library = tmp_path / "may_moi"

    with ProjectFile(packed) as opened:
        target, report = opened.open_into(library)

    assert target.parent == library and store.is_project(target)
    assert _rows(target, "SELECT project_root FROM book") == [(str(target),)]
    for input_path, output_mp3 in _rows(target, "SELECT input_path, output_mp3 FROM chapters ORDER BY id"):
        assert Path(input_path).is_file() and Path(input_path).is_relative_to(target / "sources")
        assert not output_mp3 or Path(output_mp3).is_file() and Path(output_mp3).is_relative_to(target)
    wav = _rows(target, "SELECT wav_path FROM segments WHERE wav_path != ''")
    assert wav and all(Path(path).is_file() and Path(path).is_relative_to(target) for (path,) in wav)
    assert Path(_rows(target, "SELECT input_path FROM chapters WHERE id = 1")[0][0]).read_text(
        encoding="utf-8").startswith("Chương 645")
    assert report["changed"] >= 5
    assert store.summarize(target, running=False)["title"] == store.summarize(project, running=False)["title"]


def test_the_file_leaves_out_what_belongs_to_one_machine(tmp_path: Path) -> None:
    packed = projectfile.pack(_project(tmp_path), tmp_path / "du_an.abookproj")
    with zipfile.ZipFile(packed) as archive:
        names = archive.namelist()
        first = archive.infolist()[0]
        assert first.filename == "mimetype" and first.compress_type == zipfile.ZIP_STORED
        assert archive.read("mimetype").decode("ascii") == MIMETYPE
    assert "project/project.sqlite3" in names and "project/book_settings.json" in names
    assert not any("logs/" in name or ".worker.lock" in name or name.endswith(".abook") for name in names)
    assert sorted(name for name in names if name.startswith("sources/")) == ["sources/00001_645.txt",
                                                                           "sources/00002_646.txt"]
    assert packed.read_bytes()[30:38] == b"mimetype"
    assert packed.read_bytes()[38:38 + len(MIMETYPE)] == MIMETYPE.encode("ascii")


def test_writes_still_in_the_wal_travel_with_the_project(tmp_path: Path) -> None:
    project = _project(tmp_path)
    writer = sqlite3.connect(project / store.DB_NAME)
    try:
        writer.execute("PRAGMA journal_mode=WAL")
        writer.execute("PRAGMA wal_autocheckpoint=0")
        writer.execute("INSERT INTO runtime_events VALUES (99, 1.0, 'INFO', 'X', 'còn trong wal')")
        writer.commit()
        assert (project / f"{store.DB_NAME}-wal").stat().st_size > 0
        packed = projectfile.pack(project, tmp_path / "du_an.abookproj")
    finally:
        writer.close()
    with ProjectFile(packed) as opened:
        target, _ = opened.open_into(tmp_path / "may_moi")
    assert _rows(target, "SELECT message FROM runtime_events WHERE id = 99") == [("còn trong wal",)]


def test_a_running_project_is_not_packed(tmp_path: Path) -> None:
    with pytest.raises(ProjectFileError, match="đang chạy"):
        projectfile.pack(_project(tmp_path), tmp_path / "du_an.abookproj", running=True)


def test_opening_never_replaces_a_project_already_there(tmp_path: Path) -> None:
    packed = projectfile.pack(_project(tmp_path), tmp_path / "du_an.abookproj")
    library = tmp_path / "may_moi"
    with ProjectFile(packed) as opened:
        first, _ = opened.open_into(library)
        second, _ = opened.open_into(library)
    assert first != second and second.name.endswith("(2)")
    assert store.is_project(first) and store.is_project(second)


def _rewrite(path: Path, target: Path, change) -> Path:
    with zipfile.ZipFile(path) as source, zipfile.ZipFile(target, "w") as sink:
        for info in source.infolist():
            data = change(info.filename, source.read(info.filename))
            if data is not None:
                sink.writestr(info, data)
    return target


def test_a_damaged_file_leaves_nothing_behind(tmp_path: Path) -> None:
    packed = projectfile.pack(_project(tmp_path), tmp_path / "du_an.abookproj")
    damaged = _rewrite(packed, tmp_path / "hong.abookproj",
                       lambda name, data: data[:-1] + b"x" if name == "sources/00001_645.txt" else data)
    library = tmp_path / "may_moi"
    with ProjectFile(damaged) as opened, pytest.raises(ProjectFileError, match="hỏng"):
        opened.open_into(library)
    assert list(library.iterdir()) == []


@pytest.mark.parametrize("name", ["../ngoai.txt", "project/../../ngoai.txt", "sources/a/b.txt", "C:/Windows/x.dll",
                                  "khac/x.txt"])
def test_an_entry_outside_the_format_is_refused(tmp_path: Path, name: str) -> None:
    packed = projectfile.pack(_project(tmp_path), tmp_path / "du_an.abookproj")

    def add(entry: str, data: bytes) -> bytes:
        if entry != projectfile.MANIFEST:
            return data
        manifest = json.loads(data)
        manifest["files"][name] = {"size": 1, "sha256": "0" * 64}
        return json.dumps(manifest).encode("utf-8")

    bad = _rewrite(packed, tmp_path / "la.abookproj", add)
    with zipfile.ZipFile(bad, "a") as archive:
        archive.writestr(name, b"x")
    with pytest.raises(ProjectFileError, match="mục lạ"):
        ProjectFile(bad)


def test_a_newer_format_asks_to_update_the_app(tmp_path: Path) -> None:
    packed = projectfile.pack(_project(tmp_path), tmp_path / "du_an.abookproj")

    def newer(name: str, data: bytes) -> bytes:
        if name != projectfile.MANIFEST:
            return data
        manifest = json.loads(data)
        manifest["version"] = projectfile.FORMAT_VERSION + 1
        return json.dumps(manifest).encode("utf-8")

    with pytest.raises(ProjectFileError, match="cập nhật app"):
        ProjectFile(_rewrite(packed, tmp_path / "moi.abookproj", newer))


def test_a_book_file_is_not_a_project_file(tmp_path: Path) -> None:
    from abook.webui import bookfile

    book = bookfile.pack(_project(tmp_path), tmp_path / "sach.abook")
    with pytest.raises(ProjectFileError, match="không phải file dự án"):
        ProjectFile(book)


def test_a_source_moved_away_does_not_block_the_backup(tmp_path: Path) -> None:
    project = _project(tmp_path)
    (tmp_path / "nguon" / "646.txt").unlink()
    packed = projectfile.pack(project, tmp_path / "du_an.abookproj")
    with ProjectFile(packed) as opened:
        assert opened.missing_sources == [str(tmp_path / "nguon" / "646.txt")]
        target, report = opened.open_into(tmp_path / "may_moi")
    assert _rows(target, "SELECT input_path FROM chapters WHERE id = 2") == [(str(tmp_path / "nguon" / "646.txt"),)]
    assert report["outside"] >= 1


def _app(tmp_path: Path, library_root: Path):
    from abook.webui.actions import FakeRunner
    from abook.webui.library import Preferences
    from abook.webui.listening import Listening
    from abook.webui.server import App

    preferences = Preferences(tmp_path / "prefs" / "preferences.json")
    preferences.update({"libraryRoot": str(library_root)})
    return App(preferences=preferences, runner=FakeRunner(), token="t",
               listening=Listening(tmp_path / "prefs" / "listening.json"))


def test_the_studio_packs_a_project_where_the_user_picked(tmp_path: Path) -> None:
    from abook.webui.library import book_id
    from abook.webui.server import Server
    from tests.test_webui_listen_and_sync import _request

    project = _project(tmp_path)
    app = _app(tmp_path, project.parent)
    server = Server(app, port=0).start()
    try:
        status, data, _ = _request(server.port, "POST", f"/api/books/{book_id(project)}/projectfile",
                                   headers={"X-Ebook-Token": "t"}, body={"target": str(tmp_path / "xuat")})
        app.runner._running.add(str(project.resolve()))
        busy, message, _ = _request(server.port, "POST", f"/api/books/{book_id(project)}/projectfile",
                                    headers={"X-Ebook-Token": "t"}, body={"target": str(tmp_path / "xuat2")})
    finally:
        server.stop()
    result = json.loads(data)
    assert status == 200 and Path(result["file"]).parent == tmp_path / "xuat"
    assert Path(result["file"]).name == f"Sách thử · Tập 1{projectfile.EXTENSION}"
    assert result["missingSources"] == []
    with ProjectFile(Path(result["file"])) as packed:
        packed.verify()
    assert busy == 409 and "đang chạy" in json.loads(message)["error"]


def test_double_clicking_a_project_file_opens_it_in_the_studio(tmp_path: Path) -> None:
    from abook.webui.library import book_id

    packed = projectfile.pack(_project(tmp_path), tmp_path / "du_an.abookproj")
    library = tmp_path / "thu_vien_moi"
    library.mkdir()
    app = _app(tmp_path, library)

    opened = app.open_book_file(str(packed))

    [project] = app.library.projects()
    assert opened == {"id": book_id(project), "how": "studio", "missingSources": 0, "outside": 0}
    assert project.parent == library.resolve()


# ---- phần nghe: .abook là tập con của .abookproj (chủ sách 02-10) -------------------------------------------------


def _with_cover(project: Path) -> Path:
    (project / "cover.jpg").write_bytes(b"\xff\xd8\xff" + bytes(range(200)))
    (project / "cover.json").write_text(json.dumps({"color": "#123456", "width": 2, "height": 3}), encoding="utf-8")
    return project


def _read_book(packed: Path) -> dict:
    with zipfile.ZipFile(packed) as archive:
        return json.loads(archive.read("book.json"))


def test_the_project_file_carries_the_listening_layer_of_the_book(tmp_path: Path) -> None:
    packed = projectfile.pack(_with_cover(_project(tmp_path)), tmp_path / "du_an.abookproj")
    with zipfile.ZipFile(packed) as archive:
        names = set(archive.namelist())
        book = json.loads(archive.read("book.json"))
        sizes = {info.filename: info.file_size for info in archive.infolist()}
    assert {"book.json", "cast.json", "cover.jpg", "scripts/1.json", "samples/3.wav", "chapters/00001_645.mp3"} <= names
    assert book["package"]["format"] == "abook" and book["package"]["version"] == 1 and "id" not in book
    [chapter] = [item for item in book["chapters"] if item["file"]]
    assert chapter["id"] == 1 and chapter["available"] and chapter["script"] == "scripts/1.json"
    assert chapter["file"] == "chapters/00001_645.mp3", "đúng tên mục của file .abook"
    assert [item["available"] for item in book["chapters"]] == [True, False] and book["chaptersAvailable"] == 1
    listed = book["package"]["files"]
    assert {"chapters/00001_645.mp3", "cast.json", "scripts/1.json", "scripts/2.json", "samples/3.wav",
            "cover.jpg"} == set(listed), "chữ đọc theo của cả chương chưa xong - như file .abook"
    assert all(listed[name]["size"] == sizes.get(name, listed[name]["size"]) for name in listed)
    with ProjectFile(packed) as opened:
        opened.verify()
        assert opened.listenable and opened.workshop == "present"
        assert {name: opened.manifest["files"][name] for name in listed} == listed, "một bảng mã băm, không tính hai lần"


def test_no_byte_of_audio_is_stored_twice(tmp_path: Path) -> None:
    project = _with_cover(_project(tmp_path))
    packed = projectfile.pack(project, tmp_path / "du_an.abookproj")
    audio = (project / "output" / "chapters" / "00001_645.mp3").read_bytes()
    with zipfile.ZipFile(packed) as archive:
        names = archive.namelist()
        assert [name for name in names if name.endswith(".mp3")] == ["chapters/00001_645.mp3"], "chỉ mục của phần nghe nằm thật"
        assert archive.read("chapters/00001_645.mp3") == audio
        assert archive.getinfo("chapters/00001_645.mp3").compress_type == zipfile.ZIP_STORED, "phát và tua thẳng trong gói"
        contents = [archive.read(name) for name in names if name.lower().endswith((".mp3", ".wav", ".jpg"))]
        assert len(contents) == len(set(contents)), "không có hai mục media cùng byte"
        assert "samples/3.wav" in names and "project/work/s3.wav" not in names and "project/cover.jpg" not in names
    with ProjectFile(packed) as opened:
        assert opened.aliases == {"project/cover.jpg": "cover.jpg", "project/output/chapters/00001_645.mp3":
                                  "chapters/00001_645.mp3", "project/work/s3.wav": "samples/3.wav"}
        meta = opened.manifest["files"]
        assert all(meta[alias] == meta[target] for alias, target in opened.aliases.items()), "bí danh có cỡ + mã băm như mục thật"
        assert opened.read("project/work/s3.wav") == opened.read("samples/3.wav")
        opened.verify()


def test_opening_as_a_project_puts_every_alias_back_where_the_project_had_it(tmp_path: Path) -> None:
    project = _with_cover(_project(tmp_path))
    packed = projectfile.pack(project, tmp_path / "du_an.abookproj")
    with ProjectFile(packed) as opened:
        target, _ = opened.open_into(tmp_path / "may_moi")
    for relative in ("output/chapters/00001_645.mp3", "work/s3.wav", "cover.jpg"):
        assert (target / relative).read_bytes() == (project / relative).read_bytes()
    assert not (target / "chapters").exists() and not (target / "samples").exists(), "phần nghe không giải ra khi mở thành dự án"


def test_the_project_file_carries_the_background_music(tmp_path: Path) -> None:
    from abook.webui import music_plan
    from tests.test_bookfile_music import BATTLE, CALM, _plan, _tracks

    project = _project(tmp_path)
    _plan(project)
    packed = projectfile.pack(project, tmp_path / "du_an.abookproj", music_track=_tracks(tmp_path))
    calm, battle = music_plan.track_name(CALM), music_plan.track_name(BATTLE)
    book = _read_book(packed)
    assert book["package"]["version"] == 2 and set(book["music"]["tracks"]) == {calm, battle}
    assert {calm, battle} <= set(book["package"]["files"])
    with zipfile.ZipFile(packed) as archive:
        assert archive.read(calm).startswith(b"ID3") and archive.getinfo(calm).compress_type == zipfile.ZIP_STORED
    with ProjectFile(packed) as opened:
        opened.verify()


def test_a_music_track_that_cannot_be_fetched_is_left_out(tmp_path: Path) -> None:
    from abook.webui import music_plan
    from tests.test_bookfile_music import BATTLE, CALM, _plan, _tracks

    project = _project(tmp_path)
    _plan(project)
    packed = projectfile.pack(project, tmp_path / "du_an.abookproj", music_track=_tracks(tmp_path, missing=(BATTLE,)))
    book = _read_book(packed)
    assert set(book["music"]["tracks"]) == {music_plan.track_name(CALM)}
    assert all(cue["track"] == music_plan.track_name(CALM) for cue in book["music"]["chapters"]["1"])
    with ProjectFile(packed) as opened:
        opened.verify()


def test_a_project_without_a_finished_chapter_has_nothing_to_listen_to(tmp_path: Path) -> None:
    project = _project(tmp_path)
    with sqlite3.connect(project / store.DB_NAME) as db:
        db.execute("UPDATE chapters SET status = 'synthesizing'")
    packed = projectfile.pack(project, tmp_path / "du_an.abookproj")
    with zipfile.ZipFile(packed) as archive:
        assert "book.json" not in archive.namelist() and not any(
            name.startswith(("scripts/", "samples/")) or name == "cast.json" for name in archive.namelist())
    with ProjectFile(packed) as opened:
        assert not opened.listenable
        opened.verify()
        target, _ = opened.open_into(tmp_path / "may_moi")
    assert store.is_project(target)


def test_opening_a_project_file_does_not_unpack_the_listening_layer(tmp_path: Path) -> None:
    packed = projectfile.pack(_with_cover(_project(tmp_path)), tmp_path / "du_an.abookproj")
    with ProjectFile(packed) as opened:
        target, _ = opened.open_into(tmp_path / "may_moi")
    assert not (target / "book.json").exists() and not (target / "scripts").exists() and not (target / "cast.json").exists()
    assert (target / "output" / "chapters" / "00001_645.mp3").is_file()


@pytest.mark.parametrize("damage", ["extra", "missing", "chapter", "hash"])
def test_a_listening_layer_that_does_not_match_the_package_is_refused(tmp_path: Path, damage: str) -> None:
    packed = projectfile.pack(_project(tmp_path), tmp_path / "du_an.abookproj")

    def change(name: str, data: bytes) -> bytes | None:
        if damage == "chapter" and name == "book.json":
            book = json.loads(data)
            book["chapters"][0]["file"] = "project/output/chapters/khong_co.mp3"
            return json.dumps(book).encode("utf-8")
        if damage in ("hash", "missing") and name == projectfile.MANIFEST:
            manifest = json.loads(data)
            if damage == "hash":
                manifest["files"]["cast.json"]["sha256"] = "0" * 64
            else:
                del manifest["files"]["cast.json"]
            return json.dumps(manifest).encode("utf-8")
        if damage == "missing" and name == "cast.json":
            return None
        return data

    bad = _rewrite(packed, tmp_path / "hong.abookproj", change)
    if damage == "extra":
        with zipfile.ZipFile(bad, "a") as archive:
            archive.writestr("scripts/9.json", b"{}")
    with pytest.raises(ProjectFileError):
        ProjectFile(bad)


def test_the_studio_packs_the_music_and_unpacks_it_into_the_music_cache(tmp_path: Path) -> None:
    from abook.webui import music_plan
    from abook.webui.library import book_id
    from abook.webui.server import Server
    from tests.test_bookfile_music import CALM, _plan, _tracks
    from tests.test_webui_listen_and_sync import _request

    project = _project(tmp_path)
    _plan(project)
    app = _app(tmp_path, project.parent)
    app.music_track_for_export = _tracks(tmp_path)
    server = Server(app, port=0).start()
    try:
        status, data, _ = _request(server.port, "POST", f"/api/books/{book_id(project)}/projectfile",
                                   headers={"X-Ebook-Token": "t"}, body={"target": str(tmp_path / "xuat")})
    finally:
        server.stop()
    packed = Path(json.loads(data)["file"])
    assert status == 200 and music_plan.track_name(CALM) in _read_book(packed)["package"]["files"]

    other = _app(tmp_path / "may_khac", tmp_path / "thu_vien_moi")
    other.open_book_file(str(packed))
    cached = other.music_dir / "files" / music_plan.track_name(CALM).split("/")[1]
    assert cached.read_bytes().startswith(b"ID3"), "nhạc đã nằm sẵn trong bộ đệm của máy mới"
