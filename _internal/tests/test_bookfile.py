"""Một cuốn sách trong một file (webui/bookfile.py): đầu ra của máy sản xuất, mở bằng app ở máy khác.

Fixture: cuốn hai chương của test đồng bộ (`make_project`) - chương 1 đã có MP3, chương 2 đang thu.
"""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from abook.webui import bookfile
from abook.webui.bookfile import MIMETYPE, BookFile, BookFileError
from abook.webui.library import Library, Preferences, book_id
from abook.webui.listening import Listening
from abook.webui.sync import Devices, SyncApp, manifest
from tests.test_webui_listen_and_sync import make_project


def _pack(tmp_path: Path) -> tuple[Path, Path]:
    project = make_project(tmp_path)
    return project, bookfile.pack(project, tmp_path / f"sach{bookfile.EXTENSION}")


def test_one_file_carries_the_whole_book_and_the_phone_layout(tmp_path: Path) -> None:
    project, path = _pack(tmp_path)

    with zipfile.ZipFile(path) as archive:
        first = archive.infolist()[0]
        assert (first.filename, first.compress_type, archive.read("mimetype").decode()) == (
            "mimetype", zipfile.ZIP_STORED, MIMETYPE), "nhận ra loại file mà không phải mở gói"
        audio = archive.getinfo("chapters/00001_645.mp3")
        assert audio.compress_type == zipfile.ZIP_STORED, "audio không nén: phát và tua thẳng trong gói"
    with BookFile(path) as book:
        book.verify()
        assert set(book.content) == {"cast.json", "chapters/00001_645.mp3", "scripts/1.json", "scripts/2.json",
                                     "samples/3.wav"}
        assert book.read("chapters/00001_645.mp3") == (project / "output" / "chapters" / "00001_645.mp3").read_bytes()
        script = json.loads(book.read("scripts/1.json"))
        assert [segment["kind"] for segment in script["segments"]][:1] == ["heading"] and script["timed"]
        readium = json.loads(book.read("manifest.json"))
        assert [item["href"] for item in readium["readingOrder"]] == ["chapters/00001_645.mp3"]


def test_the_file_never_carries_anyones_listening(tmp_path: Path) -> None:
    """Chỗ đang nghe, dấu trang, lịch sử là của người nghe trên máy này - không đi theo file sang người khác."""
    project = make_project(tmp_path)
    listening = Listening(tmp_path / "listening.json")
    identifier = book_id(project)
    listening.progress(identifier, 1, 42.5, 60.0)
    listening.add_bookmark(identifier, 1, 10.0, "chỗ bí mật")
    listening.set_chapter_done(identifier, 1, True)
    assert listening.get(identifier)["bookmarks"], "máy này có chỗ đang nghe và dấu trang"

    path = bookfile.pack(project, tmp_path / f"sach{bookfile.EXTENSION}")

    with zipfile.ZipFile(path) as archive:
        everything = "".join(archive.read(name).decode("utf-8") for name in archive.namelist() if name.endswith(".json"))
    assert "42.5" not in everything and "bí mật" not in everything and '"done": true' not in everything


def test_the_book_carries_no_id_of_any_app(tmp_path: Path) -> None:
    """Chủ sách 27-09: sách và dữ liệu nghe không biết đến mã; mã là việc của app. Gói không mang mã nào - kể cả mã
    của máy làm ra nó (đường dẫn thư mục, lộ cả tên ổ đĩa)."""
    project, path = _pack(tmp_path)
    with zipfile.ZipFile(path) as archive:
        book = json.loads(archive.read("book.json"))
        everything = "".join(archive.read(name).decode("utf-8") for name in archive.namelist() if name.endswith(".json"))
    assert "id" not in book and "packageId" not in book and "id" not in book["package"]
    assert book_id(project) not in everything and "bk-" not in everything
    assert manifest(project, book_id(project), Listening(tmp_path / "listening.json")).get("packageId") is None


def test_exporting_again_gives_the_same_content(tmp_path: Path) -> None:
    project, first = _pack(tmp_path)
    second = bookfile.pack(project, tmp_path / f"lai{bookfile.EXTENSION}")
    with BookFile(first) as a, BookFile(second) as b:
        assert a.chapter_prints == b.chapter_prints and a.content_key == b.content_key
        assert a.content_key.startswith("f-")


def test_the_computer_recognises_its_own_book_in_a_file(tmp_path: Path) -> None:
    """Điện thoại hỏi "cuốn tôi mở từ file là cuốn nào của máy tính" (POST /sync/v1/match): máy tính so audio từng
    chương rồi trả mã của mình; audio khác thì không nhận. Mã băm nhớ trong kho của app, không ghi vào thư mục sách."""
    root = tmp_path / "thu_vien"
    root.mkdir()
    project = make_project(root)
    preferences = Preferences(tmp_path / "preferences.json")
    preferences.update({"libraryRoot": str(root)})
    app = SyncApp(Library(preferences), Listening(tmp_path / "listening.json"), Devices(tmp_path / "devices.json"),
                  "Máy thử")
    with BookFile(bookfile.pack(project, tmp_path / f"sach{bookfile.EXTENSION}")) as book:
        prints = book.chapter_prints

    assert app.match([{"key": "f-cua-dien-thoai", "chapters": prints}]) == {"f-cua-dien-thoai": book_id(project)}
    other = {name: {**meta, "sha256": "0" * 64} for name, meta in prints.items()}
    assert app.match([{"key": "f-khac", "chapters": other}]) == {}
    assert app.match("rác") == {} and app.match([{"key": 1}, "x"]) == {}
    assert (tmp_path / "fingerprints.json").is_file()
    assert not [p for p in project.rglob("*") if "fingerprint" in p.name]


def test_extracting_gives_the_folder_a_downloaded_book_has(tmp_path: Path) -> None:
    _project, path = _pack(tmp_path)
    with BookFile(path) as book:
        folder = book.extract(tmp_path / "thu_vien")
        again = book.extract(tmp_path / "thu_vien")  # nhập lại cùng cuốn: thay, không nhân đôi
    assert folder == again and folder.name == book.content_key
    assert (folder / "chapters" / "00001_645.mp3").is_file() and (folder / "book.json").is_file()
    assert [child.name for child in (tmp_path / "thu_vien").iterdir()] == [folder.name], "không để lại thư mục tạm"


def _rewrite(path: Path, target: Path, change) -> Path:
    with zipfile.ZipFile(path) as source, zipfile.ZipFile(target, "w") as sink:
        for info in source.infolist():
            data = change(info.filename, source.read(info.filename))
            if data is not None:
                sink.writestr(info, data)
    return target


def test_a_damaged_file_is_refused_before_it_reaches_the_library(tmp_path: Path) -> None:
    _project, path = _pack(tmp_path)
    broken = _rewrite(path, tmp_path / f"hong{bookfile.EXTENSION}",
                      lambda name, data: data[:-1] + b"X" if name.endswith(".mp3") else data)
    with BookFile(broken) as book, pytest.raises(BookFileError, match="hỏng"):
        book.extract(tmp_path / "thu_vien")
    assert not (tmp_path / "thu_vien").exists() or not any((tmp_path / "thu_vien").iterdir())


@pytest.mark.parametrize("name", ["../ngoai.txt", "/tuyet_doi.txt", "chapters/../../ngoai.mp3", "script.exe"])
def test_an_entry_outside_the_format_is_refused(tmp_path: Path, name: str) -> None:
    _project, path = _pack(tmp_path)
    target = tmp_path / f"la{bookfile.EXTENSION}"
    with zipfile.ZipFile(path) as source, zipfile.ZipFile(target, "w") as sink:
        for info in source.infolist():
            sink.writestr(info, source.read(info.filename))
        sink.writestr(name, b"x")
    with pytest.raises(BookFileError, match="lạ"):
        BookFile(target)


def test_a_newer_format_asks_to_update_the_app(tmp_path: Path) -> None:
    _project, path = _pack(tmp_path)

    def newer(name: str, data: bytes) -> bytes:
        if name != "book.json":
            return data
        book = json.loads(data)
        book["package"]["version"] = bookfile.FORMAT_VERSION + 1
        return json.dumps(book).encode()

    with pytest.raises(BookFileError, match="cập nhật app"):
        BookFile(_rewrite(path, tmp_path / f"moi{bookfile.EXTENSION}", newer))


def test_a_file_that_is_not_ours_is_refused(tmp_path: Path) -> None:
    other = tmp_path / f"khac{bookfile.EXTENSION}"
    with zipfile.ZipFile(other, "w") as archive:
        archive.writestr("manifest.json", "{}")
    with pytest.raises(BookFileError, match="không phải file sách"):
        BookFile(other)
    (tmp_path / f"rac{bookfile.EXTENSION}").write_bytes(b"not a zip")
    with pytest.raises(BookFileError, match="không phải file sách"):
        BookFile(tmp_path / f"rac{bookfile.EXTENSION}")


def test_a_book_with_nothing_to_hear_is_not_packed(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    (project / "output" / "chapters" / "00001_645.mp3").unlink()
    with pytest.raises(BookFileError, match="chưa có chương nào"):
        bookfile.pack(project, tmp_path / f"rong{bookfile.EXTENSION}")
    assert not list(tmp_path.glob(f"*{bookfile.EXTENSION}*")), "không để lại file dở"


def test_the_studio_exports_the_book_file_where_the_user_picked(tmp_path: Path) -> None:
    from abook.webui.library import Preferences
    from abook.webui.server import App, Server
    from tests.test_webui_listen_and_sync import FakeRunner, _request

    project = make_project(tmp_path / "thu_vien")
    preferences = Preferences(tmp_path / "prefs" / "preferences.json")
    preferences.update({"libraryRoot": str(tmp_path / "thu_vien")})
    app = App(preferences=preferences, runner=FakeRunner(), token="t", listening=Listening(tmp_path / "prefs" / "l.json"))
    server = Server(app, port=0).start()
    try:
        status, data, _ = _request(server.port, "POST", f"/api/books/{book_id(project)}/bookfile",
                                   headers={"X-Ebook-Token": "t"}, body={"target": str(tmp_path / "xuat")})
    finally:
        server.stop()
    result = json.loads(data)
    assert status == 200 and Path(result["file"]).parent == tmp_path / "xuat"
    assert Path(result["file"]).name == f"Sách thử · Tập 1{bookfile.EXTENSION}"
    with BookFile(Path(result["file"])) as book:
        book.verify()


# ---- phiên bản 3: cả bộ nhiều phần trong một file ------------------------------------------------------------


def _series(tmp_path: Path, *, parts: int = 2) -> tuple[Path, list[Path]]:
    """Bộ `parts` phần như `test_export_series`, mỗi phần có chương 1 đã xong. Phần 2 thêm nhân vật NATASHA có câu mẫu
    riêng (câu 6) - mã câu mẫu của hai phần khác nhau nên phải được đánh số lại; câu 3 của mỗi phần thì trùng mã."""
    import sqlite3

    from tests.test_export_series import _part

    library = tmp_path / "thu_vien"
    library.mkdir()
    projects: list[Path] = []
    for number in range(1, parts + 1):
        title = "Truyện X" if number == 1 else f"Truyện X · Phần {number}"
        projects.append(_part(tmp_path, library, f"p{number}", title, projects[-1] if projects else None))
    for number, project in enumerate(projects, start=1):
        (project / "work" / "s3.wav").write_bytes(b"RIFF" + bytes([number]) * 400)  # câu mẫu của LUCIEN, khác nhau theo phần
        (project / "output" / "chapters" / "00001_645.mp3").write_bytes(b"ID3" + bytes([number]) * 300)
    second = sqlite3.connect(projects[1] / "project.sqlite3")
    (projects[1] / "work" / "s6.wav").write_bytes(b"RIFF" + b"\6" * 400)
    second.execute("INSERT INTO characters VALUES (2, 'NATASHA', 'NATASHA', 'female', 'young', 'main', 9, '')")
    second.execute("INSERT INTO segments VALUES (6, 1, 4, 1, 0, '“Chào.”', 'dialogue', 'NATASHA', 2, 'verified', ?, 'x', 4.0, 1)",
                   (str(projects[1] / "work" / "s6.wav"),))
    second.commit()
    second.close()
    return library, projects


def test_a_series_is_one_file_with_part_folders_and_global_ids(tmp_path: Path) -> None:
    _library, projects = _series(tmp_path)

    path = bookfile.pack_series([(1, projects[0]), (2, projects[1])], tmp_path / f"bo{bookfile.EXTENSION}")

    with BookFile(path) as book:
        book.verify()
        manifest = json.loads(book.read("book.json"))
        assert manifest["package"]["version"] == 3
        assert set(book.content) == {
            "cast.json", "chapters/1/00001_645.mp3", "chapters/2/00001_645.mp3", "samples/1.wav", "samples/2.wav",
            "scripts/100001.json", "scripts/100002.json", "scripts/200001.json", "scripts/200002.json"}, \
            "hai phần trùng tên file nên audio nằm trong thư mục phần"
        assert [(c["id"], c["part"], c["file"], c["script"]) for c in manifest["chapters"]] == [
            (100001, 1, "chapters/1/00001_645.mp3", "scripts/100001.json"),
            (100002, 1, None, "scripts/100002.json"),
            (200001, 2, "chapters/2/00001_645.mp3", "scripts/200001.json"),
            (200002, 2, None, "scripts/200002.json")]
        assert manifest["title"] == "Truyện X" and manifest["chaptersTotal"] == 4 and manifest["chaptersAvailable"] == 2
        assert [(p["part"], p["title"], p["chapters"]) for p in manifest["parts"]] == [
            (1, "Truyện X · Phần 1", [100001, 100002]), (2, "Truyện X · Phần 2", [200001, 200002])]
        assert json.loads(book.read("scripts/200001.json"))["chapterId"] == 200001
        assert book.read("chapters/2/00001_645.mp3") == (projects[1] / "output" / "chapters" / "00001_645.mp3").read_bytes()
        readium = json.loads(book.read("manifest.json"))
        assert [item["href"] for item in readium["readingOrder"]] == ["chapters/1/00001_645.mp3", "chapters/2/00001_645.mp3"]


def test_a_series_merges_the_cast_and_renumbers_the_samples(tmp_path: Path) -> None:
    _library, projects = _series(tmp_path)
    path = bookfile.pack_series(projects, tmp_path / f"bo{bookfile.EXTENSION}")  # chỉ thư mục: số phần là vị trí

    with BookFile(path) as book:
        cast = json.loads(book.read("cast.json"))
        people = {person["name"]: person for person in cast["characters"]}
        assert set(people) == {"LUCIEN", "NATASHA"}
        assert people["LUCIEN"]["parts"] == [1, 2] and people["LUCIEN"]["lines"] == 2, "gộp theo tên, cộng số câu"
        assert people["NATASHA"]["parts"] == [2]
        # Câu mẫu đánh số lại theo thứ tự gặp và trỏ đúng file: LUCIEN lấy câu 3 của phần 1 (không phải của phần 2).
        assert (people["LUCIEN"]["sampleId"], people["NATASHA"]["sampleId"]) == (1, 2)
        assert book.read("samples/1.wav") == b"RIFF" + b"\1" * 400
        assert book.read("samples/2.wav") == b"RIFF" + b"\6" * 400
        assert json.loads(book.read("book.json"))["samples"] == ["samples/1.wav", "samples/2.wav"]


def test_a_part_without_audio_is_left_out_but_keeps_the_numbers_of_the_others(tmp_path: Path) -> None:
    _library, projects = _series(tmp_path, parts=3)
    (projects[1] / "output" / "chapters" / "00001_645.mp3").unlink()

    path = bookfile.pack_series([(1, projects[0]), (2, projects[1]), (3, projects[2])], tmp_path / f"bo{bookfile.EXTENSION}")

    with BookFile(path) as book:
        manifest = json.loads(book.read("book.json"))
    assert [part["part"] for part in manifest["parts"]] == [1, 3]
    assert [chapter["id"] for chapter in manifest["chapters"] if chapter["file"]] == [100001, 300001]
    with pytest.raises(BookFileError, match="chưa có chương nào"):
        bookfile.pack_series([(2, projects[1])], tmp_path / f"rong{bookfile.EXTENSION}")
    assert not list(tmp_path.glob("rong*")), "không để lại file dở"


@pytest.mark.parametrize("series", [False, True])
def test_no_version_carries_the_machines_series_link(tmp_path: Path, series: bool) -> None:
    """`series.root` là mã sách của máy làm ra file - lộ tên ổ đĩa và thư mục (docstring: không mang mã nào)."""
    _library, projects = _series(tmp_path)
    assert manifest(projects[1], book_id(projects[1]), Listening(tmp_path / "l.json"))["series"], "gói điện thoại có series"
    path = (bookfile.pack_series(projects, tmp_path / f"bo{bookfile.EXTENSION}") if series
            else bookfile.pack(projects[1], tmp_path / f"bo{bookfile.EXTENSION}"))
    with zipfile.ZipFile(path) as archive:
        book = json.loads(archive.read("book.json"))
        everything = "".join(archive.read(name).decode("utf-8") for name in archive.namelist() if name.endswith(".json"))
    assert book["package"]["version"] == (3 if series else 1) and "series" not in book
    assert book_id(projects[0]) not in everything and book_id(projects[1]) not in everything


@pytest.mark.parametrize("name", ["chapters/../x.mp3", "chapters/1/2/x.mp3", "chapters/a/x.mp3", "chapters/1/../x.mp3",
                                  "/chapters/1/x.mp3"])
def test_a_series_file_refuses_names_outside_the_part_layout(tmp_path: Path, name: str) -> None:
    _library, projects = _series(tmp_path)
    path = bookfile.pack_series(projects, tmp_path / f"bo{bookfile.EXTENSION}")
    target = tmp_path / f"la{bookfile.EXTENSION}"
    with zipfile.ZipFile(path) as source, zipfile.ZipFile(target, "w") as sink:
        for info in source.infolist():
            sink.writestr(info, source.read(info.filename))
        sink.writestr(name, b"x")
    with pytest.raises(BookFileError, match="lạ"):
        BookFile(target)


def test_part_folders_exist_only_from_version_3(tmp_path: Path) -> None:
    """Gói ghi phiên bản 2 mà có `chapters/1/x.mp3` là gói sai (app phiên bản 2 cũ sẽ báo "mục lạ") - không nhận."""
    _library, projects = _series(tmp_path)
    path = bookfile.pack_series(projects, tmp_path / f"bo{bookfile.EXTENSION}")

    def older(name: str, data: bytes) -> bytes:
        if name != "book.json":
            return data
        book = json.loads(data)
        book["package"]["version"] = 2
        return json.dumps(book).encode()

    with pytest.raises(BookFileError, match="lạ"):
        BookFile(_rewrite(path, tmp_path / f"cu{bookfile.EXTENSION}", older))


def test_version_4_is_refused_with_the_update_hint_and_3_is_accepted(tmp_path: Path) -> None:
    assert bookfile.FORMAT_VERSION == 3
    _library, projects = _series(tmp_path)
    path = bookfile.pack_series(projects, tmp_path / f"bo{bookfile.EXTENSION}")

    def newer(name: str, data: bytes) -> bytes:
        if name != "book.json":
            return data
        book = json.loads(data)
        book["package"]["version"] = 4
        return json.dumps(book).encode()

    with pytest.raises(BookFileError, match="Hãy cập nhật app"):
        BookFile(_rewrite(path, tmp_path / f"v4{bookfile.EXTENSION}", newer))
    with BookFile(path):
        pass


def test_extracting_hashes_while_copying_and_does_not_read_the_file_twice(tmp_path: Path, monkeypatch) -> None:
    _project, path = _pack(tmp_path)
    monkeypatch.setattr(BookFile, "verify", lambda self: pytest.fail("extract phải tự kiểm, không đọc hai lượt"))
    with BookFile(path) as book:
        folder = book.extract(tmp_path / "thu_vien")
    assert (folder / "chapters" / "00001_645.mp3").is_file()


def test_a_book_that_does_not_fit_the_disk_is_refused_before_anything_is_copied(tmp_path: Path, monkeypatch) -> None:
    import shutil
    from collections import namedtuple

    _project, path = _pack(tmp_path)
    usage = namedtuple("usage", "total used free")
    monkeypatch.setattr(shutil, "disk_usage", lambda _path: usage(10**9, 10**9 - 1000, 1000))
    with BookFile(path) as book, pytest.raises(BookFileError, match="không đủ chỗ") as refused:
        book.extract(tmp_path / "thu_vien")
    assert "cần khoảng" in str(refused.value) and "còn" in str(refused.value)
    assert not any((tmp_path / "thu_vien").iterdir()), "chưa chép gì vào thư viện"
