"""Thôi ghép hai phía, ghép lại không sinh dòng trùng (soát a27 lỗi 5).

B "Thôi ghép" A thì A thu hồi mã thiết bị của B (B báo qua `POST /sync/v1/unpair`); A đang tắt thì B nhớ và báo lần hỏi thư viện sau.
Cùng một máy (cùng mã máy gửi lúc ghép) ghép lại thì A THAY dòng cũ thay vì thêm dòng "NGDtuanh-Lecoo" thứ ba.
"""
from __future__ import annotations

import json
from pathlib import Path

from tests.async_wait import wait_until
from abook.webui import remote_books, tls
from abook.webui.sync import Devices, SyncApp, SyncServer
from tests.test_sync_tls_pinning import _this_computer
from tests.test_webui_listen_and_sync import FakeRunner, library  # noqa: F401 - fixture dùng chung

assert FakeRunner  # fixture `library` cần nó trong cùng mô-đun


def _serve(library, tmp_path: Path, identity: tls.Identity, port: int = 0) -> tuple[SyncServer, Devices]:  # noqa: F811
    lib, _project, listening = library
    devices = Devices(tmp_path / "kia" / "devices.json")
    return SyncServer(SyncApp(lib, listening, devices, "Máy A"), host="127.0.0.1", port=port, identity=identity).start(), devices


def _until(check, seconds: float = 5.0) -> bool:
    return wait_until(check, timeout=seconds, interval=0.05)


def _stored(app):
    # Observe the persisted bytes under the writer's lock, including the exact
    # revoke count. Do not race atomic replacement on Windows or retry IO errors.
    with app.computers._lock:
        return json.loads(app.computers.path.read_text(encoding="utf-8"))


def test_forgetting_a_computer_revokes_its_device_there(library, tmp_path: Path) -> None:  # noqa: F811
    identity = tls.load_or_create(tmp_path / "kia" / tls.FILE_NAME)
    other, devices = _serve(library, tmp_path, identity)
    app = _this_computer(tmp_path)
    try:
        (computer,) = app.pair_computer(f"127.0.0.1:{other.port}", devices.start_pairing()["code"])["computers"]
        token = _stored(app)["computers"][computer["id"]]["token"]
        assert len(devices.list()) == 1 and devices.check(token)
        app.forget_computer(computer["id"])
        assert _until(lambda: devices.list() == []), "A thôi liệt kê B và mã cũ hết hiệu lực"
        assert not devices.check(token)
    finally:
        other.stop()


def test_pairing_again_from_the_same_computer_replaces_its_row(library, tmp_path: Path) -> None:  # noqa: F811
    identity = tls.load_or_create(tmp_path / "kia" / tls.FILE_NAME)
    other, devices = _serve(library, tmp_path, identity)
    app = _this_computer(tmp_path)
    try:
        app.pair_computer(f"127.0.0.1:{other.port}", devices.start_pairing()["code"])
        app.pair_computer(f"127.0.0.1:{other.port}", devices.start_pairing()["code"])
        assert len(devices.list()) == 1, "cùng máy ghép lại: thay dòng cũ, không thêm"
        devices.pair(devices.start_pairing()["code"], "Pixel")
        assert len(devices.list()) == 2, "máy khác (không mang mã máy) vẫn thêm dòng riêng"
    finally:
        other.stop()


def test_a_computer_that_was_off_is_told_on_the_next_library_refresh(library, tmp_path: Path) -> None:  # noqa: F811
    identity = tls.load_or_create(tmp_path / "kia" / tls.FILE_NAME)
    other, devices = _serve(library, tmp_path, identity)
    app = _this_computer(tmp_path)
    port = other.port
    (computer,) = app.pair_computer(f"127.0.0.1:{port}", devices.start_pairing()["code"])["computers"]
    other.stop()
    app.forget_computer(computer["id"])
    assert _until(lambda: len(_stored(app).get("revoke") or []) == 1), "chưa báo được: nhớ để báo sau"
    assert len(devices.list()) == 1
    back, devices = _serve(library, tmp_path, identity, port)
    try:
        remote_books.refresh(app.library.root, app.computers)
        assert _until(lambda: devices.list() == []), "A bật lại: lần hỏi kế tiếp báo thôi ghép"
        assert _until(lambda: not _stored(app).get("revoke"))
    finally:
        back.stop()
