"""Mã sách không mang đường dẫn (docs/BOOK_IDS.md; soát UX 29-09, mục 23).

Trước 0.4.0 mã sách là đường dẫn thư mục mã hoá base64: `#/book/<mã>` trên thanh địa chỉ (nghe từ xa bằng trình duyệt),
link, ảnh chụp màn hình đều giải ra được tên tài khoản Windows. Mã mới là HMAC của đường dẫn với khoá bí mật của máy.
Mã cũ vẫn được nhận (link cũ, điện thoại chưa đổi khoá); dữ liệu lưu theo mã cũ đổi khoá một lần lúc mở app; điện
thoại và máy tính khác hỏi mã mới của cuốn đã có bằng /sync/v1/match.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
import time
from pathlib import Path

from ebook_reader.webui import library as library_module
from ebook_reader.webui.actions import FakeRunner
from ebook_reader.webui.library import Preferences, book_id, legacy_book_id
from ebook_reader.webui.listening import Listening, default_record_id
from ebook_reader.webui.remote_books import _folder
from ebook_reader.webui.reviews import Reviews
from ebook_reader.webui.server import App, Server
from ebook_reader.webui.sync import Devices, SyncApp, SyncServer
from tests.test_webui_listen_and_sync import _request, library  # noqa: F401 - library là fixture


def _paired(port: int, devices: Devices) -> str:
    code = devices.start_pairing()["code"]
    _status, data, _ = _request(port, "POST", "/sync/v1/pair", body={"code": code, "device": "Pixel"})
    return json.loads(data)["token"]


def test_the_id_says_nothing_about_the_folder(library) -> None:  # noqa: F811 - fixture
    lib, project, _listening = library
    identifier = book_id(project)

    assert library_module.ID_PATTERN.fullmatch(identifier)
    assert book_id(project) == identifier == book_id(project / "." / ".." / project.name), "cùng thư mục thì cùng mã"
    if os.name == "nt":
        assert book_id(Path(str(project).upper())) == identifier, "Windows không phân biệt hoa thường"
    try:
        decoded = base64.urlsafe_b64decode(identifier + "=" * (-len(identifier) % 4))
    except (ValueError, binascii.Error):
        decoded = b""
    for piece in (project.name, "thu_vien", Path.home().name):
        assert piece not in identifier and piece.encode("utf-8") not in decoded
    assert lib.resolve(identifier) == project.resolve()


def test_each_computer_has_its_own_ids_and_keeps_them(tmp_path: Path, monkeypatch) -> None:
    folder = tmp_path / "Sách"
    monkeypatch.setenv("EBOOK_READER_PREFERENCES", str(tmp_path / "may_a" / "preferences.json"))
    first = book_id(folder)
    monkeypatch.setenv("EBOOK_READER_PREFERENCES", str(tmp_path / "may_b" / "preferences.json"))
    assert book_id(folder) != first, "khoá bí mật của mỗi máy: đoán tên tài khoản rồi băm thử không ra mã"

    monkeypatch.setenv("EBOOK_READER_PREFERENCES", str(tmp_path / "may_a" / "preferences.json"))
    library_module._ID_KEYS.clear()  # như mở lại app: khoá đọc lại từ đĩa
    assert book_id(folder) == first
    assert len((tmp_path / "may_a" / library_module.ID_KEY_FILE).read_text(encoding="ascii").strip()) == 64


def test_an_old_link_still_opens_the_book(library, tmp_path: Path) -> None:  # noqa: F811 - fixture
    lib, project, _listening = library
    old = legacy_book_id(project.resolve())

    assert lib.resolve(old) == project.resolve() and lib.canonical(old) == book_id(project)
    outside = legacy_book_id(tmp_path / "khac")
    assert lib.resolve(outside) is None and lib.canonical(outside) == outside, "mã cũ chỉ mở sách trong thư viện"
    assert lib.resolve("open") is None and lib.canonical("open") == "open"


def test_what_was_saved_under_old_ids_moves_to_the_new_ones_once(library) -> None:  # noqa: F811 - fixture
    lib, project, _listening = library
    folder = lib.preferences.path.parent
    old, new = legacy_book_id(project.resolve()), book_id(project)
    record = default_record_id(old)
    state = {"last": {"chapterId": 1, "seconds": 42.0, "at": 5.0}, "chapters": {}, "bookmarks": []}
    (folder / "listening.json").write_text(json.dumps({
        "version": 2, "records": {record: {"name": "Mặc định", "createdAt": 1.0, "state": state}},
        "links": {old: {"records": [record], "active": record}}, "deleted": {}}), encoding="utf-8")
    lib.preferences.remember_position(old, 1, 42.0, 100.0)
    Reviews(folder / "reviews.json").set(old, "s-1", "redo", 1)

    app = App(preferences=lib.preferences, runner=FakeRunner(), token="t")

    assert app.listening.books() == [new] and app.listen_book(new)["state"]["last"]["seconds"] == 42.0
    assert [item["id"] for item in app.listening.records(new)] == [record], "hồ sơ giữ mã: điện thoại gộp theo mã hồ sơ"
    assert list(app.preferences.get()["positions"]) == [new]
    assert app.reviews.books() == [new] and app.reviews.get(new)["s-1"]["verdict"] == "redo"
    for name in ("listening.json", "preferences.json", "reviews.json"):
        assert old not in (folder / name).read_text(encoding="utf-8")
        assert old in (folder / f"{name}.pre-ids.bak").read_text(encoding="utf-8"), "bản trước khi đổi còn nguyên"

    again = App(preferences=Preferences(lib.preferences.path), runner=FakeRunner(), token="t")
    assert again.listening.books() == [new] and again.reviews.books() == [new], "mở lại: không còn gì để đổi"


def test_an_old_link_opens_the_book_under_its_new_id(library) -> None:  # noqa: F811 - fixture
    lib, project, listening = library
    app = App(preferences=lib.preferences, runner=FakeRunner(), token="t", listening=listening)
    server = Server(app, port=0).start()
    headers = {"X-Ebook-Token": "t"}
    old, new = legacy_book_id(project.resolve()), book_id(project)
    try:
        status, _data, _ = _request(server.port, "POST", f"/api/listen/books/{old}/progress", headers=headers,
                                    body={"chapterId": 1, "seconds": 5.0, "duration": 100.0})
        assert status == 200
        status, data, _ = _request(server.port, "GET", f"/api/listen/books/{old}", headers=headers)
        view = json.loads(data)
        assert status == 200 and view["id"] == new and view["state"]["last"]["seconds"] == 5.0
        assert listening.books() == [new], "lưu theo mã hiện hành - không đẻ khoá thứ hai cho cùng một cuốn"
        _status, data, _ = _request(server.port, "GET", "/api/listen/library", headers=headers)
        assert [book["id"] for book in json.loads(data)] == [new] and old not in data.decode("utf-8")
    finally:
        server.stop()


def test_a_phone_that_still_knows_the_old_id_keeps_syncing(library, tmp_path: Path) -> None:  # noqa: F811 - fixture
    lib, project, listening = library
    devices = Devices(tmp_path / "devices.json")
    server = SyncServer(SyncApp(lib, listening, devices, "Máy thử"), host="127.0.0.1", port=0).start()
    old, new = legacy_book_id(project.resolve()), book_id(project)
    try:
        token = _paired(server.port, devices)
        status, data, _ = _request(server.port, "GET", f"/sync/v1/books/{old}/manifest", token)
        assert status == 200 and json.loads(data)["id"] == old, "gói trả đúng mã điện thoại hỏi"
        record = default_record_id(old)
        body = {"last": {"chapterId": 1, "seconds": 42.0, "at": time.time()}, "chapters": {}, "bookmarks": [],
                "record": record}
        status, data, _ = _request(server.port, "POST", f"/sync/v1/books/{old}/state", token, body=body)
        assert status == 200 and json.loads(data)["book"] == old, "điện thoại cũ không tưởng hồ sơ đã sang cuốn khác"
        assert listening.books() == [new] and listening.get(new)["last"]["seconds"] == 42.0

        status, data, _ = _request(server.port, "POST", "/sync/v1/match", token,
                                   body={"books": [{"key": old}, {"key": "f-cua-dien-thoai"}]})
        assert json.loads(data)["matches"] == {old: new}, "điện thoại mới hỏi được mã mới của cuốn đã tải"
        _status, data, _ = _request(server.port, "GET", "/sync/v1/library", token)
        assert [book["id"] for book in json.loads(data)["books"]] == [new]
    finally:
        server.stop()


def test_another_computer_keeps_its_copy_when_this_one_changes_ids(library, tmp_path: Path) -> None:  # noqa: F811
    """Máy này đã dựng cuốn ảo cho sách của máy kia hồi máy kia còn dùng mã kiểu cũ. Máy kia nâng cấp: cuốn ảo đổi theo
    mã mới trong book.json, thư mục giữ nguyên - không hai bản, mã ở máy này và chỗ nghe giữ nguyên."""
    other_library, project, other_listening = library
    devices = Devices(tmp_path / "kia" / "devices.json")
    other = SyncServer(SyncApp(other_library, other_listening, devices, "Máy kia"), host="127.0.0.1", port=0).start()
    preferences = Preferences(tmp_path / "nay" / "preferences.json")
    preferences.update({"libraryRoot": str(tmp_path / "nay" / "thu_vien")})
    app = App(preferences=preferences, runner=FakeRunner(), token="t", listening=Listening(tmp_path / "nay" / "l.json"))
    try:
        app.pair_computer(f"127.0.0.1:{other.port}", devices.start_pairing()["code"])
        (book,) = [item for item in app.listen_library() if item.get("remote")]
        built = app._listenable(book["id"])
        old = legacy_book_id(project.resolve())
        manifest = json.loads((built / "book.json").read_text(encoding="utf-8"))
        manifest["package"]["remote"]["book"] = old
        (built / "book.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        copy = built.parent / _folder(manifest["title"], hashlib.sha256(old.encode()).hexdigest())
        built.rename(copy)
        app.listening.progress(book_id(copy), 1, 30.0, 100.0)

        app.refresh_remote(wait=True)

        assert [child for child in copy.parent.iterdir() if child.is_dir()] == [copy], "không đẻ bản thứ hai"
        remote = json.loads((copy / "book.json").read_text(encoding="utf-8"))["package"]["remote"]
        assert remote["book"] == book_id(project), "book.json theo mã mới của máy kia"
        (again,) = [item for item in app.listen_library() if item.get("remote")]
        assert again["id"] == book_id(copy) and app.listen_book(again["id"])["state"]["last"]["seconds"] == 30.0
    finally:
        other.stop()
