"""Một cuốn sách trong một file (webui/bookfile.py): đầu ra của máy sản xuất, mở bằng app ở máy khác.

Fixture: cuốn hai chương của test đồng bộ (`make_project`) - chương 1 đã có MP3, chương 2 đang thu.
"""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from ebook_reader.webui import bookfile
from ebook_reader.webui.bookfile import MIMETYPE, BookFile, BookFileError
from ebook_reader.webui.library import Library, Preferences, book_id
from ebook_reader.webui.listening import Listening
from ebook_reader.webui.sync import Devices, SyncApp, manifest
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
        assert book.identity.startswith("bk-") and book.book["id"] == book.identity
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


def test_the_same_production_keeps_its_identity_when_exported_again(tmp_path: Path) -> None:
    project, first = _pack(tmp_path)
    second = bookfile.pack(project, tmp_path / f"lai{bookfile.EXTENSION}")
    with BookFile(first) as a, BookFile(second) as b:
        assert a.identity == b.identity


def test_wifi_and_the_file_carry_the_same_book_identity(tmp_path: Path) -> None:
    """Điện thoại gộp cuốn tải qua Wi-Fi với cùng cuốn mở từ file (BookFileImport, Store.adopt): danh sách thư viện và
    gói sách Wi-Fi mang đúng mã sách cố định mà file .abook mang - khác mã máy tính (đường dẫn thư mục)."""
    root = tmp_path / "thu_vien"
    root.mkdir()
    project = make_project(root)
    preferences = Preferences(tmp_path / "preferences.json")
    preferences.update({"libraryRoot": str(root)})
    listening = Listening(tmp_path / "listening.json")
    app = SyncApp(Library(preferences), listening, Devices(tmp_path / "devices.json"), "Máy thử")

    path = bookfile.pack(project, tmp_path / f"sach{bookfile.EXTENSION}")

    with BookFile(path) as book:
        identity = book.identity
        assert book.book["packageId"] == identity
    assert [entry["packageId"] for entry in app.library_view()] == [identity]
    assert manifest(project, book_id(project), listening)["packageId"] == identity
    assert identity != book_id(project)


def test_extracting_gives_the_folder_a_downloaded_book_has(tmp_path: Path) -> None:
    _project, path = _pack(tmp_path)
    with BookFile(path) as book:
        folder = book.extract(tmp_path / "thu_vien")
        again = book.extract(tmp_path / "thu_vien")  # nhập lại cùng cuốn: thay, không nhân đôi
    assert folder == again and folder.name.startswith("bk-")
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
    from ebook_reader.webui.library import Preferences
    from ebook_reader.webui.server import App, Server
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
