"""Mở Studio của máy tính đã ghép ngay trong app máy này (webui/peer_studio.py, soát a27 lỗi 14).

Máy B (máy này) đã ghép với máy A. Trang của B gọi `/api/peers/<A>/studio/...` trên máy chủ của B; B chuyển sang cổng đồng bộ
của A qua TLS ghim vân tay, mang mã thiết bị B nhận lúc ghép - không ghép lần hai, mã không bao giờ xuống trang. A xét như mọi
thiết bị đã ghép: công tắc "Điều khiển sản xuất" và quyền của dòng thiết bị B.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from abook.webui import peer_studio
from abook.webui.actions import FakeRunner
from abook.webui.library import book_id
from abook.webui.server import App, Server
from tests.test_sync_tls_pinning import _this_computer
from tests.test_webui_listen_and_sync import _request, library  # noqa: F401 - fixture dùng chung

PAGE = {"X-Ebook-Token": "t", "Sec-Fetch-Site": "same-origin"}


@pytest.fixture()
def two(library, tmp_path: Path):  # noqa: F811
    """(A, B, cổng máy chủ giao diện của B, mã máy A ở B, tên A, cuốn của A). A bật "Điều khiển sản xuất" (công tắc chung) nhưng
    dòng thiết bị của B chưa được - bài nào cần thì bật (`_allow`)."""
    lib, project, listening = library
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("<!doctype html><title>ABook</title>", encoding="utf-8")
    a = App(preferences=lib.preferences, runner=FakeRunner(), token="phien-a", listening=listening, static_dir=static)
    a.sync_host, a.sync_port = "127.0.0.1", 0
    a_ui = Server(a, port=0).start()
    a.set_sync(True)
    b = _this_computer(tmp_path)
    b_ui = Server(b, port=0).start()
    try:
        (computer,) = b.pair_computer(f"127.0.0.1:{a.sync_server.port}", a.devices.start_pairing()["code"])["computers"]
        a.set_remote_studio(True)  # bật sau khi ghép: dòng thiết bị ghép lúc tắt chưa có quyền riêng
        yield a, b, b_ui.port, computer["id"], computer["name"], book_id(project)
    finally:
        b.close()
        b_ui.stop()
        a.close()
        a_ui.stop()


def _allow(a: App) -> None:
    (row,) = a.devices.list()
    assert a.devices.set_studio(row["id"], True)


def _token(b: App, computer: str) -> str:
    return json.loads(b.computers.path.read_bytes())["computers"][computer]["token"]


def test_the_studio_of_a_paired_computer_opens_here_without_pairing_again(two) -> None:
    a, b, port, computer, name, book = two
    _allow(a)
    root = f"/api/peers/{computer}/studio"
    bodies = []
    status, data, _ = _request(port, "GET", f"{root}/api/app", headers=PAGE)
    bodies.append(data)
    info = json.loads(data)
    assert status == 200 and info["remote"] is True and info["listenOnly"] is False
    assert info["peer"] == {"id": computer, "name": name}, "trang biết đang mở Studio của máy nào"
    status, data, _ = _request(port, "GET", f"{root}/api/library", headers=PAGE)
    bodies.append(data)
    assert status == 200 and [item["id"] for item in json.loads(data)["books"]] == [book]
    status, data, _ = _request(port, "POST", f"{root}/api/books/{book}/stop", headers=PAGE, body={})
    bodies.append(data)
    assert status == 202, "lệnh ghi đi qua đúng luật của A (mã thiết bị, quyền, Origin)"
    status, data, headers = _request(port, "GET", f"{root}/media/books/{book}/chapters/1?t=t", headers={**PAGE, "Range": "bytes=10-19"})
    assert status == 206 and len(data) == 10 and headers["Content-Range"].startswith("bytes 10-19/"), "nghe thẳng audio qua cầu nối"
    assert len(a.devices.list()) == 1, "không ghép lần hai: A vẫn một dòng cho B"
    token = _token(b, computer)
    assert not any(token.encode() in body for body in bodies), "mã thiết bị không bao giờ xuống trang"


def test_routes_outside_the_list_or_from_another_page_never_leave_this_computer(two) -> None:
    a, _b, port, computer, name, book = two
    _allow(a)
    root = f"/api/peers/{computer}/studio"
    for method, path in (("GET", "/api/remote"), ("POST", "/api/dialog/folder"), ("PUT", "/api/preferences"),
                         ("POST", f"/api/books/{book}/reveal"), ("GET", "/sync/v1/library")):
        status, data, _ = _request(port, method, root + path, headers=PAGE, body={} if method != "GET" else None)
        assert status == 403 and f"chính máy tính {name}" in json.loads(data)["error"], (method, path)
    status, _data, _ = _request(port, "POST", f"{root}/api/books/{book}/stop", headers={**PAGE, "Sec-Fetch-Site": "cross-site"}, body={})
    assert status == 403, "trang lạ trên máy này không mượn được cầu nối"
    status, _data, _ = _request(port, "GET", f"{root}/api/library", headers={"X-Ebook-Token": "t", "Origin": "http://ke-la.example"})
    assert status == 403
    status, _data, _ = _request(port, "GET", f"{root}/api/library", headers={"Sec-Fetch-Site": "same-origin"})
    assert status == 401, "không có mã phiên của trang: không gì cả"
    status, _data, _ = _request(port, "GET", "/api/peers/0123456789ab/studio/api/library", headers=PAGE)
    assert status == 404


def test_without_permission_at_the_other_computer_the_studio_says_listen_only(two) -> None:
    _a, _b, port, computer, name, book = two
    root = f"/api/peers/{computer}/studio"
    status, data, _ = _request(port, "GET", f"{root}/api/app", headers=PAGE)
    assert status == 200 and json.loads(data)["listenOnly"] is True
    for method, path in (("GET", "/api/library"), ("POST", f"/api/books/{book}/start")):
        status, data, _ = _request(port, method, root + path, headers=PAGE, body={} if method != "GET" else None)
        reply = json.loads(data)
        assert status == 403 and reply == {"error": peer_studio.listen_only(name), "listenOnly": True}, (method, path)
    assert reply["error"] == f"Chỉ nghe - bật quyền sửa ở {name}: Cài đặt > Thiết bị"
    status, _data, _ = _request(port, "GET", f"{root}/api/listen/library", headers=PAGE)
    assert status == 200, "nghe thì vẫn được"


def test_a_changed_certificate_is_refused_before_the_token_leaves(two) -> None:
    a, b, port, computer, _name, _book = two
    _allow(a)
    b.computers.note(computer, fingerprint="00" * 32)
    status, data, _ = _request(port, "GET", f"/api/peers/{computer}/studio/api/app", headers=PAGE)
    assert status == 502 and "Chứng chỉ" in json.loads(data)["error"]


def test_a_version_mismatch_is_named_and_a_computer_that_is_off_is_told(two) -> None:
    a, b, port, computer, _name, _book = two
    _allow(a)
    b.version = "0.0.0-khac"
    status, data, _ = _request(port, "GET", f"/api/peers/{computer}/studio/api/app", headers=PAGE)
    assert status == 409 and json.loads(data) == {"error": peer_studio.MISMATCH, "mismatch": True}
    b.version = a.version
    a.set_sync(False)
    status, data, _ = _request(port, "GET", f"/api/peers/{computer}/studio/api/library", headers=PAGE, timeout=30)
    reply = json.loads(data)
    assert status == 503 and reply["unreachable"] is True and "không trả lời" in reply["error"], "không treo, nói rõ"


def test_the_page_says_listen_only_in_the_same_words_as_the_server() -> None:
    """Trang Studio đóng (ui/src/shared/peerStudio.ts listenOnlyLine) và lời từ chối của cầu nối nói cùng một câu."""
    source = (Path(__file__).resolve().parents[1] / "ui" / "src" / "shared" / "peerStudio.ts").read_text(encoding="utf-8")
    assert "`" + peer_studio.listen_only("${name}") + "`" in source
