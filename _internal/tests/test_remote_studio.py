"""Studio từ xa (webui/remote_studio.py): thiết bị đã ghép NGHE được qua trình duyệt (như app điện thoại qua /sync/v1), và
điều khiển sản xuất qua cổng đồng bộ - chỉ khi người dùng bật công tắc riêng và cho chính thiết bị ấy, chỉ các đường trong
danh sách trắng, trình duyệt ghép bằng mã 6 số và mang mã thiết bị trong cookie."""
from __future__ import annotations

import base64
import http.client
import json
import time
from pathlib import Path

import pytest

from abook.webui import music_plan, remote_studio, tls
from abook.webui.actions import FakeRunner
from abook.webui.library import book_id
from abook.webui.server import ROUTES, App, Server
from tests.test_webui_listen_and_sync import _request, _sync_request, library, make_project  # noqa: F401 - fixture dùng chung


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
    status, data, headers = _sync_request(app.sync_server.port, "POST", "/sync/v1/pair-browser",
                                     body={"code": code, "device": "Điện thoại của Anh"})
    assert status == 200, data
    cookie = headers["Set-Cookie"]
    assert "HttpOnly" in cookie and "Secure" in cookie and "SameSite=Strict" in cookie
    return cookie.split(";", 1)[0]


def test_production_is_closed_until_the_owner_opens_it(studio) -> None:
    app, _project = studio
    port = app.sync_server.port
    assert app.sync_view()["remoteStudio"] is False
    status, data, _ = _sync_request(port, "GET", "/")
    assert status == 200 and "Mã ghép nối" in data.decode("utf-8"), "ghép để nghe luôn được, như điện thoại"
    code = app.devices.start_pairing()["code"]
    _status, data, _ = _sync_request(port, "POST", "/sync/v1/pair", body={"code": code, "device": "Pixel"})
    phone = json.loads(data)["token"]
    status, data, _ = _sync_request(port, "GET", "/api/library", phone)
    assert status == 403 and "chỉ nghe" in json.loads(data)["error"], "ghép để nghe không có nghĩa là được điều khiển sản xuất"
    status, _data, _ = _sync_request(port, "POST", "/sync/v1/pair-browser", body={"code": "000000"})
    assert status == 403


def test_the_home_screen_files_open_without_pairing_but_nothing_else_does(studio) -> None:
    """"Thêm vào màn hình chính": trình duyệt lấy manifest và biểu tượng không kèm cookie - chỉ bốn file ấy mở cho trình duyệt chưa ghép."""
    app, _project = studio
    port = app.sync_server.port
    static = app.static_dir
    (static / "manifest.webmanifest").write_text('{"name": "ABook"}', encoding="utf-8")
    for name in ("apple-touch-icon.png", "icon-192.png", "icon-512.png"):
        (static / name).write_bytes(b"icon")
    status, data, headers = _sync_request(port, "GET", "/manifest.webmanifest")
    assert status == 200 and json.loads(data) == {"name": "ABook"}
    assert headers["Content-Type"] == "application/manifest+json"
    for name in ("apple-touch-icon.png", "icon-192.png", "icon-512.png"):
        status, data, headers = _sync_request(port, "GET", f"/{name}")
        assert (status, data, headers["Content-Type"]) == (200, b"icon", "image/png")
    status, data, _ = _sync_request(port, "GET", "/assets/app.js")
    assert status == 200 and "Mã ghép nối" in data.decode("utf-8"), "file khác của giao diện vẫn cần ghép nối"


def test_a_paired_browser_listens_without_the_production_switch(studio) -> None:
    """Lộ trình đường truyền 27-09 mục 1: iPhone, iPad, TV, máy khác nghe trong trình duyệt. Nghe là quyền của mọi thiết bị
    đã ghép; Studio thì không - kể cả khi công tắc bật sau, thiết bị ghép lúc tắt vẫn cần quyền riêng."""
    app, project = studio
    port = app.sync_server.port
    identifier = book_id(project)
    cookie = {"Cookie": _pair_browser(app)}
    status, data, _ = _sync_request(port, "GET", "/", headers=cookie)
    assert status == 200 and data.startswith(b"<!doctype html>")
    status, data, _ = _sync_request(port, "GET", "/api/app", headers=cookie)
    info = json.loads(data)
    assert status == 200 and info["remote"] is True and info["listenOnly"] is True
    assert info["libraryRoot"] == "", "thiết bị chỉ nghe không thấy thư mục (tên người dùng) trên máy tính"
    status, data, _ = _sync_request(port, "GET", "/api/listen/library", headers=cookie)
    assert status == 200 and json.loads(data), "thư viện nghe của máy tính"
    status, data, headers = _sync_request(port, "GET", f"/media/books/{identifier}/chapters/1", headers={
        **cookie, "Range": "bytes=0-9"})
    assert status == 206 and len(data) == 10, "nghe thẳng audio"
    status, _data, _ = _sync_request(port, "GET", f"/api/books/{identifier}/cast", headers=cookie)
    assert status == 200, "dàn nhân vật của màn sách"
    status, _data, _ = _sync_request(port, "POST", f"/api/listen/books/{identifier}/progress", headers=cookie,
                                body={"chapterId": 1, "position": 12.5})
    assert status in (200, 204), "chỗ nghe ghi về máy tính như khi nghe trên máy tính"
    for method, path in (("GET", "/api/library"), ("POST", f"/api/books/{identifier}/start"),
                         ("GET", f"/api/books/{identifier}/work"), ("POST", "/api/scan")):
        status, data, _ = _sync_request(port, method, path, headers=cookie, body={} if method != "GET" else None)
        assert status == 403 and "chỉ nghe" in json.loads(data)["error"], (method, path)
    status, data, _ = _sync_request(port, "POST", "/api/dialog/folder", headers=cookie, body={})
    assert status == 403 and "chính máy tính" in json.loads(data)["error"], "việc của riêng máy tính vẫn không bao giờ qua"

    app.set_remote_studio(True)
    status, data, _ = _sync_request(port, "GET", "/api/app", headers=cookie)
    assert json.loads(data)["listenOnly"] is True, "ghép lúc công tắc tắt: bật công tắc không tự cho thiết bị cũ"
    short_id = next(device["id"] for device in app.sync_view()["devices"] if device["name"] == "Điện thoại của Anh")
    assert app.devices.set_studio(short_id, True)
    status, data, _ = _sync_request(port, "GET", "/api/app", headers=cookie)
    assert json.loads(data)["listenOnly"] is False
    status, _data, _ = _sync_request(port, "GET", "/api/library", headers=cookie)
    assert status == 200


def test_a_browser_pairs_with_the_code_then_runs_the_studio(studio) -> None:
    app, project = studio
    app.set_remote_studio(True)
    port = app.sync_server.port
    status, data, _ = _sync_request(port, "GET", "/")
    assert status == 200 and "Mã ghép nối" in data.decode("utf-8"), "chưa ghép: trang nhập mã"
    app.devices.start_pairing()
    status, _data, _ = _sync_request(port, "POST", "/sync/v1/pair-browser", body={"code": "999999"})
    assert status == 403
    cookie = {"Cookie": _pair_browser(app)}
    assert any(device["name"] == "Điện thoại của Anh" for device in app.sync_view()["devices"])

    status, data, _ = _sync_request(port, "GET", "/", headers=cookie)
    assert status == 200 and data.startswith(b"<!doctype html>"), "đã ghép: đúng giao diện web của cửa sổ app"
    status, _data, headers = _sync_request(port, "GET", "/assets/app.js", headers=cookie)
    assert status == 200 and "immutable" in headers["Cache-Control"]
    status, data, _ = _sync_request(port, "GET", "/..%2Fprefs%2Fpreferences.json", headers=cookie)
    assert data.startswith(b"<!doctype html>"), "không đi ra ngoài thư mục giao diện"

    status, data, _ = _sync_request(port, "GET", "/api/app", headers=cookie)
    info = json.loads(data)
    assert status == 200 and info["remote"] is True and info["dialogs"] is False
    status, data, _ = _sync_request(port, "GET", "/api/library", headers=cookie)
    assert status == 200 and len(json.loads(data)["books"]) == 1
    identifier = book_id(project)
    status, _data, _ = _sync_request(port, "POST", f"/api/books/{identifier}/start", headers=cookie, body={})
    assert status == 202, "bấm Bắt đầu từ điện thoại chạy đúng đường của cửa sổ app"
    status, data, headers = _sync_request(port, "GET", f"/media/books/{identifier}/chapters/1", headers={
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
        status, data, _ = _sync_request(port, method, path, headers=cookie, body={} if method != "GET" else None)
        assert status == 403 and "chính máy tính" in json.loads(data)["error"], (method, path)
    status, _data, _ = _sync_request(port, "GET", "/api/library")
    assert status == 401, "không cookie, không mã: không gì cả"
    # Trang lạ trong trình duyệt chỉ gửi được form/chữ thường sang cổng này mà không qua CORS: không nhận.
    connection = tls.PinnedHTTPSConnection("127.0.0.1", port, expected=None, timeout=10)
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
    _status, data, _ = _sync_request(port, "POST", "/sync/v1/pair", body={"code": code, "device": "Pixel"})
    phone = json.loads(data)["token"]
    status, _data, _ = _sync_request(port, "GET", "/api/library", phone)
    assert status == 200, "app Android mang mã thiết bị như khi đồng bộ"
    app.set_remote_studio(False)
    status, _data, _ = _sync_request(port, "GET", "/api/library", phone)
    assert status == 403, "tắt công tắc là đóng ngay, không cần khởi động lại cổng"


def test_a_phone_sends_chapters_then_creates_the_book_from_them(studio) -> None:
    app, _project = studio
    app.set_remote_studio(True)
    port = app.sync_server.port
    cookie = {"Cookie": _pair_browser(app)}
    chapter = "Chương 1\n\nTrời đã sáng.".encode("utf-16")  # byte nguyên vẹn: bảng mã do dây chuyền nhận, không do trang
    for name in ("001.txt", "..\\..\\002.txt"):
        status, data, _ = _sync_request(port, "POST", "/api/sources/upload", headers=cookie, body={
            "folder": "../Truyện của Anh", "name": name, "data": base64.b64encode(chapter).decode("ascii")})
        assert status == 200, data
    folder = Path(json.loads(data)["folder"])
    root = Path(app.preferences.get()["libraryRoot"])
    assert folder == root / "Nguồn tải lên" / "Truyện của Anh", "không ra ngoài thư mục tải lên"
    assert sorted(path.name for path in folder.iterdir()) == ["001.txt", "002.txt"]
    assert (folder / "001.txt").read_bytes() == chapter
    status, data, _ = _sync_request(port, "POST", "/api/scan", headers=cookie, body={"paths": [str(folder)]})
    assert status == 200 and len(json.loads(data)["files"]) == 2, "trình tạo sách đi tiếp như khi chọn thư mục"
    status, data, _ = _sync_request(port, "POST", "/api/sources/upload", headers=cookie, body={
        "folder": "x", "name": "anh.jpg", "data": base64.b64encode(b"\xff\xd8").decode("ascii")})
    assert status == 400 and ".txt" in json.loads(data)["error"]
    # Không ghi đè: đè lên nguồn của một cuốn đã tạo là cuốn ấy không chạy tiếp được nữa.
    status, data, _ = _sync_request(port, "POST", "/api/sources/upload", headers=cookie, body={
        "folder": "Truyện của Anh", "name": "001.txt", "data": base64.b64encode(b"khac").decode("ascii")})
    assert status == 400 and (folder / "001.txt").read_bytes() == chapter
    for folder_name, name in (("NUL", "a.txt"), ("x", "CON.txt"), ("x", "com1.txt")):
        status, _data, _ = _sync_request(port, "POST", "/api/sources/upload", headers=cookie, body={
            "folder": folder_name, "name": name, "data": base64.b64encode(b"a").decode("ascii")})
        assert status == 400, (folder_name, name)


def test_a_whole_book_sent_from_a_phone_can_be_split_into_chapters(studio, tmp_path: Path) -> None:
    # Soát UX a5 01-10: truyện tải mạng là MỘT file - điện thoại gửi nó lên, bước 1 đề xuất tách, bấm thì tách ngay trên
    # máy tính; các chương nằm trong "Nguồn tải lên" để thiết bị quét tiếp được. Không tách được file ngoài chỗ tải lên.
    app, _project = studio
    app.set_remote_studio(True)
    port = app.sync_server.port
    cookie = {"Cookie": _pair_browser(app)}
    book = "Chương 1\n\nTrời đã sáng.\n\nChương 2\n\nTrời tối.\n".encode()
    _status, data, _ = _sync_request(port, "POST", "/api/sources/upload", headers=cookie, body={
        "folder": "Cả truyện", "name": "tron bo.txt", "data": base64.b64encode(book).decode("ascii")})
    whole = str(Path(json.loads(data)["folder"]) / "tron bo.txt")
    status, data, _ = _sync_request(port, "POST", "/api/scan", headers=cookie, body={"paths": [whole]})
    assert status == 200 and json.loads(data)["files"][0]["split"]["chapters"] == 2
    status, data, _ = _sync_request(port, "POST", "/api/sources/split", headers=cookie, body={"path": whole})
    assert status == 200, data
    folder = Path(json.loads(data)["folder"])
    assert folder.parent.parent == Path(app.preferences.get()["libraryRoot"]) / "Nguồn tải lên"
    status, data, _ = _sync_request(port, "POST", "/api/scan", headers=cookie, body={"paths": [str(folder)]})
    assert status == 200 and len(json.loads(data)["files"]) == 2
    outside = tmp_path / "ngoai.txt"
    outside.write_bytes(book)
    status, _data, _ = _sync_request(port, "POST", "/api/sources/split", headers=cookie, body={"path": str(outside)})
    assert status == 403


def _send(port: int, cookie: dict, folder: str, name: str, data: bytes) -> tuple[int, dict]:
    status, raw, _ = _sync_request(port, "POST", "/api/sources/upload", headers=cookie, body={
        "folder": folder, "name": name, "data": base64.b64encode(data).decode("ascii")})
    return status, json.loads(raw)


def test_a_picked_folder_keeps_its_name_inside_its_own_upload(studio) -> None:
    # Soát UX mục 7: chọn cả thư mục truyện trong trình duyệt - tên thư mục là tên sách máy gợi ý, nên nó phải còn nguyên;
    # mỗi lần gửi vẫn nằm riêng một chỗ (không ghi đè nguồn của cuốn đã tạo). Thứ tự chương theo tên file như khi chọn đường dẫn.
    app, _project = studio
    app.set_remote_studio(True)
    port = app.sync_server.port
    cookie = {"Cookie": _pair_browser(app)}
    root = Path(app.preferences.get()["libraryRoot"]) / "Nguồn tải lên"
    for name in ("10.txt", "2.txt", "1.txt"):
        status, data = _send(port, cookie, "Lần gửi a1/Truyện Thử", name, f"Chương {name}\n\nTrời sáng.".encode())
        assert status == 200, data
    folder = Path(data["folder"])
    assert folder == root / "Lần gửi a1" / "Truyện Thử"
    status, raw, _ = _sync_request(port, "POST", "/api/scan", headers=cookie, body={"paths": [str(folder)]})
    scan = json.loads(raw)
    assert status == 200 and [row["name"] for row in scan["files"]] == ["1.txt", "2.txt", "10.txt"]
    assert scan["suggestedTitle"] == "Truyện Thử", "tên thư mục đã chọn, không phải tên lần gửi"
    # Lần gửi khác cùng thư mục: chỗ riêng, không đụng nguồn đã có.
    status, data = _send(port, cookie, "Lần gửi b2/Truyện Thử", "1.txt", b"khac")
    assert status == 200 and Path(data["folder"]) == root / "Lần gửi b2" / "Truyện Thử"
    # Mỗi tầng bị làm sạch như tên một thư mục: "..", tầng rỗng, ký tự lạ không đưa ra ngoài; tối đa ba tầng.
    status, data = _send(port, cookie, "../..//x:/../Tập 1\\..\\a/b/c", "1.txt", b"a")
    assert status == 200 and Path(data["folder"]) == root / "x" / "Tập 1" / "a"
    status, data = _send(port, cookie, "Lần gửi c3/NUL/Tập 1", "1.txt", b"a")
    assert status == 400, "tên thiết bị ở tầng nào cũng không nhận"


def test_a_browser_on_the_computer_uploads_too(studio) -> None:
    # Studio mở trong trình duyệt ngay trên máy tính (không có hộp chọn file của app): cũng gửi file lên như từ xa; tách
    # chương thì vào "Nguồn tách chương" như với file trên máy. File quá giới hạn bị từ chối, nói rõ giới hạn.
    app, _project = studio
    local = {"X-Ebook-Token": "phien", "Host": f"127.0.0.1:{app.local_port}"}
    book = "Chương 1\n\nTrời đã sáng.\n\nChương 2\n\nTrời tối.\n".encode()
    status, raw, _ = _request(app.local_port, "POST", "/api/sources/upload", headers=local, body={
        "folder": "Lần gửi d4", "name": "tron bo.txt", "data": base64.b64encode(book).decode("ascii")})
    assert status == 200, raw
    whole = json.loads(raw)["path"]
    assert Path(whole) == Path(json.loads(raw)["folder"]) / "tron bo.txt", "file lẻ quét như khi chọn từng file"
    status, raw, _ = _request(app.local_port, "POST", "/api/sources/split", headers=local, body={"path": whole})
    assert status == 200, raw
    folder = Path(json.loads(raw)["folder"])
    assert folder.parent.parent == Path(app.preferences.get()["libraryRoot"]) / "Nguồn tách chương"
    big = base64.b64encode(b"a" * (8 * 1024 * 1024 + 1)).decode("ascii")
    status, raw, _ = _request(app.local_port, "POST", "/api/sources/upload", headers=local, body={
        "folder": "Lần gửi d4", "name": "to.txt", "data": big})
    assert status == 400 and "8 MB" in json.loads(raw)["error"]


# ---- soát bảo mật 28-09: mỗi test tái hiện đúng một cách tấn công của báo cáo ------------------------------------------


def test_a_device_paired_to_listen_needs_its_own_permission(studio) -> None:
    app, _project = studio
    port = app.sync_server.port
    code = app.devices.start_pairing()["code"]
    _status, data, _ = _sync_request(port, "POST", "/sync/v1/pair", body={"code": code, "device": "Pixel"})
    phone = json.loads(data)["token"]
    app.set_remote_studio(True)
    status, data, _ = _sync_request(port, "GET", "/api/library", phone)
    assert status == 403 and "chưa được phép" in json.loads(data)["error"], "bật Studio không tự cho điện thoại cũ"
    short_id = app.devices.identify(phone)["id"]
    assert app.devices.set_studio(short_id, True)
    status, _data, _ = _sync_request(port, "GET", "/api/library", phone)
    assert status == 200


def test_remote_paths_stay_inside_the_upload_folder(studio, tmp_path: Path) -> None:
    app, project = studio
    app.set_remote_studio(True)
    port = app.sync_server.port
    cookie = {"Cookie": _pair_browser(app)}
    private = tmp_path / "rieng"
    private.mkdir()
    (private / "ghi_chu.txt").write_text("Dòng đầu tiên của một file riêng tư", encoding="utf-8")
    for path in (str(private), r"\\may-khac\share\x", "//may-khac/share", r"\\?\C:\x"):
        for route in ("/api/scan", "/api/first-person"):
            status, data, _ = _sync_request(port, "POST", route, headers=cookie, body={"paths": [path]})
            assert status == 403 and "đã gửi lên" in json.loads(data)["error"], (route, path)
            assert b"ghi_chu" not in data
        status, _data, _ = _sync_request(port, "POST", "/api/books", headers=cookie, body={"paths": [path], "title": "x"})
        assert status == 403, path
    identifier = book_id(project)
    status, data, _ = _sync_request(port, "POST", f"/api/books/{identifier}/export", headers=cookie,
                               body={"target": str(tmp_path / "ngoai")})
    assert not (tmp_path / "ngoai").exists(), "từ xa không chọn được nơi ghi trên máy tính"
    # Cùng lời gọi từ cửa sổ app (không qua cổng từ xa) vẫn chọn được thư mục như trước.
    local = {"X-Ebook-Token": "phien", "Host": f"127.0.0.1:{app.local_port}"}
    status, data, _ = _request(app.local_port, "POST", "/api/scan", headers=local, body={"paths": [str(private)]})
    assert status == 200 and b"ghi_chu" in data


def test_create_and_start_waits_in_the_queue(studio, tmp_path: Path) -> None:
    app, project = studio
    app.set_remote_studio(True)
    port = app.sync_server.port
    cookie = {"Cookie": _pair_browser(app)}
    app.start(book_id(project))
    deadline = time.time() + 10
    while not app.runner.running(project) and time.time() < deadline:
        time.sleep(0.1)  # FakeRunner "khởi động" 1,2 giây, như một worker thật cần thời gian
    assert app.runner.running(project)
    folder = None
    for name in ("001.txt", "002.txt"):
        _status, data, _ = _sync_request(port, "POST", "/api/sources/upload", headers=cookie, body={
            "folder": "moi", "name": name, "data": base64.b64encode(f"Chương {name}\n\nTrời sáng.".encode()).decode()})
        folder = json.loads(data)["folder"]
    status, data, _ = _sync_request(port, "POST", "/api/books", headers=cookie,
                               body={"paths": [folder], "title": "Sách mới", "start": True})
    assert status == 201, data
    assert app.queue == [json.loads(data)["id"]], "cuốn thứ hai xếp hàng, không tranh GPU với cuốn đang chạy"


def test_malformed_and_cross_site_requests_are_refused(studio) -> None:
    app, project = studio
    app.set_remote_studio(True)
    port = app.sync_server.port
    cookie = _pair_browser(app)
    # Content-Length âm: trước đây rfile.read(-1) đọc tới hết kết nối, vượt mọi trần kích thước.
    connection = tls.PinnedHTTPSConnection("127.0.0.1", port, expected=None, timeout=10)
    connection.putrequest("POST", "/api/scan")
    connection.putheader("Cookie", cookie)
    connection.putheader("Content-Type", "application/json")
    connection.putheader("Content-Length", "-1")
    connection.endheaders()
    response = connection.getresponse()
    response.read()
    assert response.status == 400
    connection.close()
    # DNS rebinding: tên miền lạ trỏ về IP của máy này.
    status, _data, _ = _sync_request(port, "GET", "/", headers={"Cookie": cookie, "Host": "ke-la.example:47630"})
    assert status == 403
    # Lệnh ghi mang cookie từ một trang khác (cùng IP, khác cổng vẫn là "same-site" với SameSite=Strict).
    identifier = book_id(project)
    status, _data, _ = _sync_request(port, "POST", f"/api/books/{identifier}/stop",
                                headers={"Cookie": cookie, "Sec-Fetch-Site": "same-site"})
    assert status == 403
    status, _data, _ = _sync_request(port, "POST", f"/api/books/{identifier}/stop",
                                headers={"Cookie": cookie, "Sec-Fetch-Site": "same-origin"})
    assert status == 202
    # Cookie chỉ có nghĩa ở Studio: các đường /sync/v1 của app điện thoại đòi mã tường minh.
    status, _data, _ = _sync_request(port, "GET", "/sync/v1/library", headers={"Cookie": cookie})
    assert status == 401
    # Cookie hỏng của trang khác đứng trước không làm mất mã thiết bị.
    status, _data, _ = _sync_request(port, "GET", "/api/library", headers={"Cookie": 'x={"a":1}; ' + cookie})
    assert status == 200


def test_head_keeps_the_connection_in_step_and_private_preferences_stay_home(studio) -> None:
    app, _project = studio
    app.set_remote_studio(True)
    app.preferences.update({"recents": ["C:/Users/ai-do/Sach"]})
    port = app.sync_server.port
    cookie = _pair_browser(app)
    connection = tls.PinnedHTTPSConnection("127.0.0.1", port, expected=None, timeout=10)
    connection.request("HEAD", "/api/app", headers={"Cookie": cookie})
    response = connection.getresponse()
    response.read()
    assert response.status == 200
    connection.request("GET", "/api/preferences", headers={"Cookie": cookie})
    response = connection.getresponse()
    preferences = json.loads(response.read())
    assert response.status == 200, "yêu cầu kế tiếp trên cùng kết nối vẫn đọc đúng"
    assert "recents" not in preferences and "positions" not in preferences
    connection.close()


def test_every_allowed_route_exists_on_the_computer() -> None:
    # Danh sách trắng không được mở tên đường nào mà máy chủ giao diện không có: một đường gõ sai là một nút bấm trên
    # điện thoại lặng lẽ không làm gì.
    samples = (("r-[0-9a-f]{16}", "r-0123456789abcdef"), (music_plan.TRACK_NAME, "a" * 40 + ".mp3"),
               (r"[0-9a-f]{32}\.wav", "b" * 32 + ".wav"),
               ("[A-Za-z0-9_-]+", "YWJj"), (r"\d+", "7"),
               ("[0-9a-f]+", "ab12"), ("[^/]+", "Duc"))
    for method, pattern in remote_studio.ALLOWED:
        path = pattern.pattern
        for token, sample in samples:
            path = path.replace(token, sample)
        assert pattern.fullmatch(path), (method, path)
        assert any(verb == method and local.fullmatch(path) for verb, local, _handler in ROUTES), (method, path)


def test_a_remote_studio_continues_a_book_only_with_its_next_chapters(studio, tmp_path: Path) -> None:
    """"Làm tiếp cuốn này" từ điện thoại: chương kế tiếp là file TRÊN MÁY TÍNH, nhưng do máy tính tự tính từ dự án phần trước
    (continuation.next_chapters) - thiết bị chỉ chọn trong danh sách ấy, không mở được đường dẫn nào khác."""
    import sqlite3

    from abook import continuation

    app, project = studio
    app.set_remote_studio(True)
    port = app.sync_server.port
    cookie = {"Cookie": _pair_browser(app)}
    story = tmp_path / "truyen"
    story.mkdir()
    for name in ("645.txt", "646.txt", "647.txt"):
        (story / name).write_text(f"Chương {name[:3]}\nLucien đi tiếp.\n", encoding="utf-8")
    db = sqlite3.connect(project / "project.sqlite3")
    db.execute("UPDATE chapters SET input_path=? WHERE id=1", (str(story / "645.txt"),))
    db.execute("UPDATE chapters SET input_path=? WHERE id=2", (str(story / "646.txt"),))
    db.commit()
    db.close()
    identifier = book_id(project)

    status, data, _ = _sync_request(port, "GET", f"/api/books/{identifier}/continuation", headers=cookie)
    plan = json.loads(data)
    assert status == 200 and [Path(path).name for path in plan["paths"]] == ["647.txt"]
    for route in ("/api/scan", "/api/first-person"):
        status, _data, _ = _sync_request(port, "POST", route, headers=cookie, body={"paths": plan["paths"], "seedFrom": identifier})
        assert status == 200, route
        status, _data, _ = _sync_request(port, "POST", route, headers=cookie, body={"paths": plan["paths"]})
        assert status == 403, "không nói làm tiếp cuốn nào thì vẫn chỉ được thư mục gửi lên"
        status, _data, _ = _sync_request(port, "POST", route, headers=cookie,
                                    body={"paths": [str(story / "645.txt")], "seedFrom": identifier})
        assert status == 403, "chương đã làm không phải chương kế tiếp"

    status, data, _ = _sync_request(port, "POST", "/api/books", headers=cookie, body={
        "paths": plan["paths"], "title": plan["title"], "profile": "high_quality", "narrator": "", "firstPerson": "",
        "seedFrom": identifier,
    })
    assert status == 201, data
    created = app.library.resolve(json.loads(data)["id"])
    assert continuation.chain_of(created)[0] == project.resolve()


def test_background_music_reaches_a_paired_device() -> None:
    # Trình phát ở xa nghe được nhạc nền (mốc nhạc, bài đóng trong sách, bài trong danh mục) chỉ với quyền NGHE; tab Nhạc
    # nền - xem, chỉnh, "Đổi bài" - cần quyền điều khiển sản xuất.
    book = "/api/books/YWJj"
    for method, path in (("GET", book + "/music/chapters/3"), ("GET", book + "/music/files/" + "a" * 40 + ".mp3"),
                         ("GET", "/api/music/track")):
        assert remote_studio.permitted(method, path, producing=False), path
    for method, path in (("GET", book + "/music"), ("PUT", book + "/music"), ("POST", book + "/music/rebuild"),
                         ("GET", book + "/music/scenes/c3-1/alternatives")):
        assert remote_studio.permitted(method, path), path
        assert not remote_studio.permitted(method, path, producing=False), path
    assert not remote_studio.permitted("GET", book + "/music/files/../../preferences.json", producing=False)
