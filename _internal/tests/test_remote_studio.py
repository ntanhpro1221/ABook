"""Studio từ xa (webui/remote_studio.py): thiết bị đã ghép điều khiển sản xuất qua cổng đồng bộ - chỉ khi người dùng bật
công tắc riêng, chỉ các đường trong danh sách trắng, trình duyệt ghép bằng mã 6 số và mang mã thiết bị trong cookie."""
from __future__ import annotations

import base64
import http.client
import json
from pathlib import Path

import pytest

from ebook_reader.webui import remote_studio
from ebook_reader.webui.actions import FakeRunner
from ebook_reader.webui.library import book_id
from ebook_reader.webui.server import ROUTES, App, Server
from tests.test_webui_listen_and_sync import _request, library, make_project  # noqa: F401 - fixture dùng chung


@pytest.fixture()
def studio(library, tmp_path: Path):
    lib, project, listening = library
    static = tmp_path / "static"
    (static / "assets").mkdir(parents=True)
    (static / "index.html").write_text("<!doctype html><title>ABook</title>", encoding="utf-8")
    (static / "assets" / "app.js").write_text("console.log('abook')", encoding="utf-8")
    app = App(preferences=lib.preferences, runner=FakeRunner(), token="phien", listening=listening, static_dir=static)
    app.sync_host, app.sync_port = "127.0.0.1", 0
    ui = Server(app, port=0).start()
    app.set_sync(True)
    try:
        yield app, project
    finally:
        app.close()
        ui.stop()


def _pair_browser(app: App) -> str:
    code = app.devices.start_pairing()["code"]
    status, data, headers = _request(app.sync_server.port, "POST", "/sync/v1/pair-browser",
                                     body={"code": code, "device": "Điện thoại của Anh"})
    assert status == 200, data
    cookie = headers["Set-Cookie"]
    assert "HttpOnly" in cookie and "SameSite=Strict" in cookie
    return cookie.split(";", 1)[0]


def test_remote_studio_is_closed_until_the_owner_opens_it(studio) -> None:
    app, _project = studio
    port = app.sync_server.port
    assert app.sync_view()["remoteStudio"] is False
    status, data, _ = _request(port, "GET", "/")
    assert status == 403 and "chưa cho phép" in data.decode("utf-8")
    code = app.devices.start_pairing()["code"]
    _status, data, _ = _request(port, "POST", "/sync/v1/pair", body={"code": code, "device": "Pixel"})
    phone = json.loads(data)["token"]
    status, _data, _ = _request(port, "GET", "/api/library", phone)
    assert status == 403, "ghép để nghe không có nghĩa là được điều khiển sản xuất"
    status, _data, _ = _request(port, "POST", "/sync/v1/pair-browser", body={"code": "000000"})
    assert status == 403


def test_a_browser_pairs_with_the_code_then_runs_the_studio(studio) -> None:
    app, project = studio
    app.set_remote_studio(True)
    port = app.sync_server.port
    status, data, _ = _request(port, "GET", "/")
    assert status == 200 and "Mã ghép nối" in data.decode("utf-8"), "chưa ghép: trang nhập mã"
    app.devices.start_pairing()
    status, _data, _ = _request(port, "POST", "/sync/v1/pair-browser", body={"code": "999999"})
    assert status == 403
    cookie = {"Cookie": _pair_browser(app)}
    assert any(device["name"] == "Điện thoại của Anh" for device in app.sync_view()["devices"])

    status, data, _ = _request(port, "GET", "/", headers=cookie)
    assert status == 200 and data.startswith(b"<!doctype html>"), "đã ghép: đúng giao diện web của cửa sổ app"
    status, _data, headers = _request(port, "GET", "/assets/app.js", headers=cookie)
    assert status == 200 and "immutable" in headers["Cache-Control"]
    status, data, _ = _request(port, "GET", "/..%2Fprefs%2Fpreferences.json", headers=cookie)
    assert data.startswith(b"<!doctype html>"), "không đi ra ngoài thư mục giao diện"

    status, data, _ = _request(port, "GET", "/api/app", headers=cookie)
    info = json.loads(data)
    assert status == 200 and info["remote"] is True and info["dialogs"] is False
    status, data, _ = _request(port, "GET", "/api/library", headers=cookie)
    assert status == 200 and len(json.loads(data)["books"]) == 1
    identifier = book_id(project)
    status, _data, _ = _request(port, "POST", f"/api/books/{identifier}/start", headers=cookie, body={})
    assert status == 202, "bấm Bắt đầu từ điện thoại chạy đúng đường của cửa sổ app"
    status, data, headers = _request(port, "GET", f"/media/books/{identifier}/chapters/1", headers={
        **cookie, "Range": "bytes=10-19"})
    assert status == 206 and len(data) == 10 and headers["Content-Range"].startswith("bytes 10-19/")


def test_what_only_makes_sense_on_the_computer_never_passes(studio) -> None:
    app, project = studio
    app.set_remote_studio(True)
    port = app.sync_server.port
    cookie = {"Cookie": _pair_browser(app)}
    identifier = book_id(project)
    for method, path in (("POST", "/api/dialog/folder"), ("POST", "/api/dialog/files"),
                         ("POST", f"/api/books/{identifier}/reveal"), ("POST", "/api/reveal-export"),
                         ("PUT", "/api/preferences"), ("POST", "/api/sync"), ("POST", "/api/sync/pairing"),
                         ("POST", "/api/sync/studio"), ("DELETE", "/api/sync/devices/abc"), ("GET", "/api/remote"),
                         ("POST", "/api/books/open"), ("POST", "/api/listen/open-book-file")):
        status, data, _ = _request(port, method, path, headers=cookie, body={} if method != "GET" else None)
        assert status == 403 and "chính máy tính" in json.loads(data)["error"], (method, path)
    status, _data, _ = _request(port, "GET", "/api/library")
    assert status == 401, "không cookie, không mã: không gì cả"
    # Trang lạ trong trình duyệt chỉ gửi được form/chữ thường sang cổng này mà không qua CORS: không nhận.
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    connection.request("POST", "/api/scan", body=b"x", headers={**cookie, "Content-Type": "text/plain"})
    response = connection.getresponse()
    response.read()
    assert response.status == 415
    connection.close()


def test_a_paired_phone_uses_its_token_and_switching_off_closes_at_once(studio) -> None:
    app, _project = studio
    app.set_remote_studio(True)
    port = app.sync_server.port
    code = app.devices.start_pairing()["code"]
    _status, data, _ = _request(port, "POST", "/sync/v1/pair", body={"code": code, "device": "Pixel"})
    phone = json.loads(data)["token"]
    status, _data, _ = _request(port, "GET", "/api/library", phone)
    assert status == 200, "app Android mang mã thiết bị như khi đồng bộ"
    app.set_remote_studio(False)
    status, _data, _ = _request(port, "GET", "/api/library", phone)
    assert status == 403, "tắt công tắc là đóng ngay, không cần khởi động lại cổng"


def test_a_phone_sends_chapters_then_creates_the_book_from_them(studio) -> None:
    app, _project = studio
    app.set_remote_studio(True)
    port = app.sync_server.port
    cookie = {"Cookie": _pair_browser(app)}
    chapter = "Chương 1\n\nTrời đã sáng.".encode("utf-16")  # byte nguyên vẹn: bảng mã do dây chuyền nhận, không do trang
    for name in ("001.txt", "..\\..\\002.txt"):
        status, data, _ = _request(port, "POST", "/api/sources/upload", headers=cookie, body={
            "folder": "../Truyện của Anh", "name": name, "data": base64.b64encode(chapter).decode("ascii")})
        assert status == 200, data
    folder = Path(json.loads(data)["folder"])
    root = Path(app.preferences.get()["libraryRoot"])
    assert folder == root / "Nguồn tải lên" / "Truyện của Anh", "không ra ngoài thư mục tải lên"
    assert sorted(path.name for path in folder.iterdir()) == ["001.txt", "002.txt"]
    assert (folder / "001.txt").read_bytes() == chapter
    status, data, _ = _request(port, "POST", "/api/scan", headers=cookie, body={"paths": [str(folder)]})
    assert status == 200 and len(json.loads(data)["files"]) == 2, "trình tạo sách đi tiếp như khi chọn thư mục"
    status, data, _ = _request(port, "POST", "/api/sources/upload", headers=cookie, body={
        "folder": "x", "name": "anh.jpg", "data": base64.b64encode(b"\xff\xd8").decode("ascii")})
    assert status == 400 and ".txt" in json.loads(data)["error"]


def test_every_allowed_route_exists_on_the_computer() -> None:
    # Danh sách trắng không được mở tên đường nào mà máy chủ giao diện không có: một đường gõ sai là một nút bấm trên
    # điện thoại lặng lẽ không làm gì.
    samples = (("r-[0-9a-f]{16}", "r-0123456789abcdef"), ("[A-Za-z0-9_-]+", "YWJj"), (r"\d+", "7"),
               ("[0-9a-f]+", "ab12"), ("[^/]+", "Duc"))
    for method, pattern in remote_studio.ALLOWED:
        path = pattern.pattern
        for token, sample in samples:
            path = path.replace(token, sample)
        assert pattern.fullmatch(path), (method, path)
        assert any(verb == method and local.fullmatch(path) for verb, local, _handler in ROUTES), (method, path)
