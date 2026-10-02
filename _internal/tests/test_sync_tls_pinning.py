"""Cổng đồng bộ chỉ nói TLS, và bên kết nối ghim vân tay chứng chỉ lúc ghép (webui/tls.py).

Trước đây mã thiết bị đi dạng rõ qua HTTP trong LAN: ai cùng Wi-Fi cũng đọc được rồi dùng lại. Giờ: chứng chỉ tự ký sinh một
lần cạnh tuỳ chọn; lúc ghép máy kia ghi vân tay SHA-256 của nó; từ đó chỉ nhận ĐÚNG chứng chỉ ấy - đổi là lỗi bảo ghép lại,
không bao giờ rơi về HTTP.
"""
from __future__ import annotations

import http.client
import json
import socket
import ssl
from pathlib import Path

import pytest

from abook.webui import remote_books, tls
from abook.webui.library import Preferences
from abook.webui.listening import Listening
from abook.webui.server import App
from abook.webui.sync import Devices, SyncApp, SyncServer
from tests.test_webui_listen_and_sync import FakeRunner, library  # noqa: F401 - fixture dùng chung


def _other(library, tmp_path: Path, identity: tls.Identity | None = None):  # noqa: F811
    lib, _project, listening = library
    devices = Devices(tmp_path / "kia" / "devices.json")
    server = SyncServer(SyncApp(lib, listening, devices, "Máy kia"), host="127.0.0.1", port=0, identity=identity).start()
    return server, devices


def _this_computer(tmp_path: Path) -> App:
    preferences = Preferences(tmp_path / "nay" / "preferences.json")
    preferences.update({"libraryRoot": str(tmp_path / "nay" / "thu_vien")})
    return App(preferences=preferences, runner=FakeRunner(), token="t", listening=Listening(tmp_path / "nay" / "l.json"))


def test_the_generated_certificate_is_a_real_self_signed_one(tmp_path: Path) -> None:
    """OpenSSL nạp được, và chữ ký ECDSA tự ký kiểm lại được bằng thư viện ngoài (chỉ trong bài thử, không phải phụ thuộc)."""
    x509 = pytest.importorskip("cryptography.x509")
    from cryptography.hazmat.primitives.asymmetric import ec

    identity = tls.load_or_create(tmp_path / tls.FILE_NAME)
    certificate = x509.load_der_x509_certificate(identity.certificate)
    certificate.public_key().verify(certificate.signature, certificate.tbs_certificate_bytes,
                                    ec.ECDSA(certificate.signature_hash_algorithm))
    assert certificate.issuer == certificate.subject
    assert identity.fingerprint == tls.fingerprint(identity.certificate) and len(identity.fingerprint) == 64
    assert identity.server_context() is not None
    assert b"\r" not in (tmp_path / tls.FILE_NAME).read_bytes(), "file danh tính ghi LF, không CRLF của Windows"


def test_the_identity_is_made_once_and_survives_restarts(tmp_path: Path) -> None:
    path = tmp_path / tls.FILE_NAME
    first = tls.load_or_create(path)
    assert tls.load_or_create(path).fingerprint == first.fingerprint, "mở lại app: cùng chứng chỉ, thiết bị đã ghép vẫn tin"
    path.write_bytes(path.read_bytes()[:200])  # file cắt dở
    assert tls.load_or_create(path).fingerprint != first.fingerprint, "hỏng thì sinh mới, không lỗi"
    assert tls.load_or_create(path).server_context() is not None


def test_pairing_stores_the_fingerprint_the_other_computer_showed(library, tmp_path: Path) -> None:  # noqa: F811
    other, devices = _other(library, tmp_path)
    app = _this_computer(tmp_path)
    try:
        view = app.pair_computer(f"127.0.0.1:{other.port}", devices.start_pairing()["code"])
        (computer,) = view["computers"]
        assert computer["fingerprint"] == other.fingerprint
        stored = json.loads((tmp_path / "nay" / "computers.json").read_text(encoding="utf-8"))["computers"]
        assert next(iter(stored.values()))["fingerprint"] == other.fingerprint
    finally:
        other.stop()


def test_the_pairing_answer_carries_the_fingerprint(library, tmp_path: Path) -> None:  # noqa: F811
    other, devices = _other(library, tmp_path)
    try:
        connection = tls.PinnedHTTPSConnection("127.0.0.1", other.port, expected=None)
        body = json.dumps({"code": devices.start_pairing()["code"], "device": "Pixel"})
        connection.request("POST", "/sync/v1/pair", body=body, headers={"Content-Type": "application/json"})
        reply = json.loads(connection.getresponse().read())
        assert reply["fingerprint"] == other.fingerprint == connection.peer_fingerprint
        connection.close()
    finally:
        other.stop()


def test_a_client_with_the_right_fingerprint_connects_and_range_works(library, tmp_path: Path) -> None:  # noqa: F811
    other, devices = _other(library, tmp_path)
    app = _this_computer(tmp_path)
    try:
        app.pair_computer(f"127.0.0.1:{other.port}", devices.start_pairing()["code"])
        (entry,) = [remote_books.Computers(tmp_path / "nay" / "computers.json").get(item["id"])
                    for item in app.computers_view()["computers"]]
        endpoint = remote_books._base(entry)
        assert endpoint.fingerprint == other.fingerprint
        books = json.loads(remote_books._request(endpoint, "GET", "/sync/v1/library", entry["token"]))["books"]
        assert books, "đã ghép: thấy thư viện qua kết nối ghim"
        connection = tls.PinnedHTTPSConnection("127.0.0.1", other.port, expected=other.fingerprint)
        manifest = json.loads(_get(connection, f"/sync/v1/books/{books[0]['id']}/manifest", entry["token"]).read())
        chapter = next(item for item in manifest["chapters"] if item["file"])
        response = _get(connection, f"/sync/v1/books/{books[0]['id']}/files/{chapter['file']}", entry["token"],
                        {"Range": "bytes=10-19"})
        assert response.status == 206 and len(response.read()) == 10, "tua theo byte vẫn chạy qua TLS"
        connection.close()
    finally:
        other.stop()


def _get(connection: http.client.HTTPSConnection, path: str, token: str, headers: dict | None = None):
    connection.request("GET", path, headers={"Authorization": f"Bearer {token}", **(headers or {})})
    return connection.getresponse()


def test_a_wrong_fingerprint_is_refused_before_anything_is_sent(library, tmp_path: Path) -> None:  # noqa: F811
    other, devices = _other(library, tmp_path)
    try:
        wrong = "0" * 64
        with pytest.raises(tls.PinError):
            tls.PinnedHTTPSConnection("127.0.0.1", other.port, expected=wrong).connect()
        # Cả đường của ứng dụng: lỗi đọc được, bảo ghép lại - mã thiết bị không rời máy này.
        with pytest.raises(remote_books.RemoteError, match="ghép lại"):
            remote_books._request(remote_books.Endpoint("127.0.0.1", other.port, wrong), "GET", "/sync/v1/library", "ma-bi-mat")
        with pytest.raises(remote_books.RemoteError, match="ghép lại"):
            remote_books._request(remote_books.Endpoint("127.0.0.1", other.port, ""), "GET", "/sync/v1/library", "ma-bi-mat")
    finally:
        other.stop()


def test_a_computer_that_changed_its_certificate_is_not_trusted_silently(library, tmp_path: Path) -> None:  # noqa: F811
    """Máy kia cài lại (chứng chỉ mới) hay có kẻ giả nó: thư viện báo lỗi bảo ghép lại, KHÔNG tự nhận chứng chỉ mới."""
    other, devices = _other(library, tmp_path)
    app = _this_computer(tmp_path)
    port = other.port
    try:
        app.pair_computer(f"127.0.0.1:{port}", devices.start_pairing()["code"])
        (before,) = app.computers_view()["computers"]
    finally:
        other.stop()
    impostor = SyncServer(SyncApp(library[0], library[2], Devices(tmp_path / "gia" / "devices.json"), "Máy kia"),
                          host="127.0.0.1", port=port, identity=tls.Identity(*tls.generate())).start()
    try:
        assert impostor.fingerprint != before["fingerprint"]
        app.refresh_remote(wait=True)
        (after,) = app.computers_view()["computers"]
        assert "ghép lại" in after["error"] and after["fingerprint"] == before["fingerprint"], "vân tay cũ giữ nguyên"
    finally:
        impostor.stop()


def test_plain_http_to_the_sync_port_gets_nothing(library, tmp_path: Path) -> None:  # noqa: F811
    """Cổng đồng bộ không nói HTTP thường: không trả lời, không chuyển hướng - cắt ngay lúc bắt tay."""
    other, devices = _other(library, tmp_path)
    try:
        with pytest.raises((ConnectionError, http.client.HTTPException, OSError)):
            connection = http.client.HTTPConnection("127.0.0.1", other.port, timeout=5)
            connection.request("GET", "/sync/v1/library")
            connection.getresponse()
        raw = socket.create_connection(("127.0.0.1", other.port), timeout=5)
        raw.sendall(b"GET /sync/v1/library HTTP/1.1\r\nHost: x\r\n\r\n")
        try:
            received = raw.recv(4096)
        except (ConnectionError, TimeoutError):
            received = b""
        assert not received.startswith(b"HTTP/"), received[:80]
        raw.close()
        # Máy kia sống sót sau những kết nối hỏng: vẫn ghép được bằng TLS.
        connection = tls.PinnedHTTPSConnection("127.0.0.1", other.port, expected=other.fingerprint)
        assert _get(connection, "/sync/v1/library", "sai-ma").status == 401
        connection.close()
    finally:
        other.stop()


def test_a_client_that_stalls_the_handshake_blocks_nobody(library, tmp_path: Path) -> None:  # noqa: F811
    """Bắt tay làm ở luồng của từng kết nối: một máy mở cổng rồi im lặng không chặn điện thoại thật."""
    other, devices = _other(library, tmp_path)
    stalled = socket.create_connection(("127.0.0.1", other.port))
    try:
        connection = tls.PinnedHTTPSConnection("127.0.0.1", other.port, expected=other.fingerprint, timeout=5)
        assert _get(connection, "/sync/v1/library", "sai-ma").status == 401
        connection.close()
    finally:
        stalled.close()
        other.stop()


def test_the_app_reuses_its_identity_and_shows_the_fingerprint(library, tmp_path: Path) -> None:  # noqa: F811
    app = _this_computer(tmp_path)
    app.sync_host, app.sync_port = "127.0.0.1", 0
    try:
        assert app.sync_view()["fingerprint"] == ""
        first = app.set_sync(True)["fingerprint"]
        assert first == tls.display(app.sync_server.fingerprint) and first.count(" ") == 15
        app.set_sync(False)
        assert app.set_sync(True)["fingerprint"] == first, "bật lại: cùng chứng chỉ, thiết bị đã ghép không phải ghép lại"
        assert (tmp_path / "nay" / tls.FILE_NAME).is_file(), "nằm cạnh tuỳ chọn"
    finally:
        app.close()


def test_the_default_server_context_refuses_old_protocols() -> None:
    assert tls.ephemeral().server_context().minimum_version >= ssl.TLSVersion.TLSv1_2
