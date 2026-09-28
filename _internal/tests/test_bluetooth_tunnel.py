"""Đường hầm Bluetooth (webui/bluetooth.py): một kết nối mang nhiều luồng HTTP của cổng đồng bộ. RFCOMM thật cần sóng
Bluetooth và một máy thứ hai; ở đây một cặp socket đứng thay cho kết nối RFCOMM - giao thức khung, cửa sổ tín dụng, đóng
nửa chiều và đứt kết nối là của đường hầm, không phụ thuộc lớp vận chuyển."""
from __future__ import annotations

import http.client
import json
import socket
import struct
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from ebook_reader.webui import bluetooth
from ebook_reader.webui.bluetooth import HEADER, BluetoothServer, LocalPort, Mux
from ebook_reader.webui.sync import Devices, SyncApp, SyncServer
from tests.test_webui_listen_and_sync import library  # noqa: F401 - fixture dùng chung

BIG = bytes(range(256)) * 16 * 1024  # 4 MB, lớn hơn nhiều lần cửa sổ 256 KB


class Files(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *_args: object) -> None:
        pass

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/cham":
            time.sleep(1.5)  # như hỏi dài 25 giây của điều khiển từ xa, thu nhỏ
        body = BIG if self.path == "/big" else b"nho"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _tunnel(port: int) -> tuple[Mux, Mux, LocalPort]:
    """Hai đầu đường hầm trên một cặp socket; đầu phục vụ nối vào `port` đúng như máy tính nối vào cổng đồng bộ."""
    near, far = socket.socketpair()
    server = Mux(far, dial=BluetoothServer(port)._dial, odd=False)
    client = Mux(near)
    threading.Thread(target=server.run, daemon=True).start()
    threading.Thread(target=client.run, daemon=True).start()
    return client, server, LocalPort(client)


@pytest.fixture
def files():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Files)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield server.server_address[1]
    server.shutdown()


def _get(port: int, path: str, token: str = "", body: dict | None = None, method: str = "GET") -> tuple[int, bytes]:
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=20)
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    payload = json.dumps(body).encode() if body is not None else None
    if payload is not None:
        headers["Content-Type"] = "application/json"
    connection.request(method, path, body=payload, headers=headers)
    response = connection.getresponse()
    data = response.read()
    connection.close()
    return response.status, data


def test_the_sync_protocol_runs_unchanged_through_the_tunnel(library, tmp_path: Path) -> None:  # noqa: F811
    """Ghép mã 6 số, thư viện, gói sách - đúng các đường điện thoại dùng qua Wi-Fi, đi qua MỘT kết nối."""
    lib, _project, listening = library
    devices = Devices(tmp_path / "devices.json")
    sync = SyncServer(SyncApp(lib, listening, devices, "Máy thử"), host="127.0.0.1", port=0).start()
    client, server, local = _tunnel(sync.port)
    try:
        code = devices.start_pairing()["code"]
        status, data = _get(local.port, "/sync/v1/pair", body={"code": code, "device": "Điện thoại BT"}, method="POST")
        assert status == 200
        token = json.loads(data)["token"]
        status, data = _get(local.port, "/sync/v1/library", token)
        (book,) = json.loads(data)["books"]
        status, data = _get(local.port, f"/sync/v1/books/{book['id']}/manifest", token)
        assert status == 200 and json.loads(data)["title"]
        assert _get(local.port, "/sync/v1/library", "sai-ma")[0] == 401, "mã thiết bị vẫn do cổng đồng bộ kiểm"
    finally:
        client.shutdown()
        server.shutdown()
        sync.stop()


def test_many_streams_share_one_link_and_a_stalled_one_blocks_nobody(files: int) -> None:
    """Trình phát ngừng đọc khi bộ đệm đầy: luồng ấy hết tín dụng và đứng, nhưng lời gọi đồng bộ bên cạnh vẫn về ngay."""
    client, server, local = _tunnel(files)
    try:
        stalled = socket.create_connection(("127.0.0.1", local.port))
        stalled.sendall(b"GET /big HTTP/1.1\r\nHost: x\r\n\r\n")
        time.sleep(0.5)  # để luồng lớn dồn tới trần tín dụng
        started = time.time()
        results: list[tuple[int, bytes]] = []
        workers = [threading.Thread(target=lambda: results.append(_get(local.port, "/nho"))) for _ in range(8)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(10)
        assert [status for status, _body in results] == [200] * 8 and time.time() - started < 5
        assert all(body == b"nho" for _status, body in results)

        # Luồng lớn đọc tiếp là nhận đủ, đúng từng byte - tín dụng được trả dần, không mất gì.
        stalled.settimeout(20)
        received = b""
        while b"\r\n\r\n" not in received:
            received += stalled.recv(65536)
        head, body = received.split(b"\r\n\r\n", 1)
        while len(body) < len(BIG):
            chunk = stalled.recv(1 << 20)
            assert chunk, "đường hầm cắt ngang luồng lớn"
            body += chunk
        assert body == BIG
        stalled.close()
    finally:
        client.shutdown()
        server.shutdown()


def test_half_close_keeps_the_answer_coming(files: int) -> None:
    """Bên gọi gửi xong yêu cầu rồi đóng chiều gửi (EOF): chiều về vẫn phải tới đủ."""
    client, server, local = _tunnel(files)
    try:
        caller = socket.create_connection(("127.0.0.1", local.port))
        caller.sendall(b"GET /nho HTTP/1.0\r\nHost: x\r\n\r\n")
        caller.shutdown(socket.SHUT_WR)
        caller.settimeout(10)
        answer = b""
        while chunk := caller.recv(4096):
            answer += chunk
        assert answer.startswith(b"HTTP/1.1 200") and answer.endswith(b"nho")
    finally:
        client.shutdown()
        server.shutdown()


def test_a_broken_link_closes_every_stream_and_a_dead_port_refuses_the_stream(files: int) -> None:
    client, server, local = _tunnel(files)
    caller = socket.create_connection(("127.0.0.1", local.port))
    caller.sendall(b"GET /big HTTP/1.1\r\nHost: x\r\n\r\n")
    caller.settimeout(10)
    assert caller.recv(16).startswith(b"HTTP/1.")
    server.link.close()  # ra ngoài tầm Bluetooth
    _drain(caller)
    assert _eventually(lambda: not client.alive), "đầu bên này cũng biết đường hầm đã đứt"

    # Máy tính tắt cổng đồng bộ: luồng mở ra bị đóng ngay, bên gọi thấy EOF chứ không treo.
    dead = socket.socket()
    dead.bind(("127.0.0.1", 0))
    port = dead.getsockname()[1]
    dead.close()
    client2, server2, local2 = _tunnel(port)
    try:
        orphan = socket.create_connection(("127.0.0.1", local2.port))
        orphan.settimeout(10)
        orphan.sendall(b"GET / HTTP/1.0\r\n\r\n")
        _drain(orphan)  # EOF hay bị cắt - không treo
        assert _eventually(lambda: not client2.streams and not server2.streams)
    finally:
        client2.shutdown()
        server2.shutdown()


def _drain(sock: socket.socket) -> None:
    """Đọc tới khi socket hết (EOF hoặc bị cắt) - cả hai đều là "đường hầm đã đóng luồng này"."""
    deadline = time.time() + 10
    try:
        while sock.recv(1 << 20):
            assert time.time() < deadline, "luồng không đóng khi đường hầm đứt"
    except OSError:
        pass


def _eventually(check, timeout: float = 5.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if check():
            return True
        time.sleep(0.05)
    return check()


def test_the_sdp_record_is_laid_out_like_ws2bth() -> None:
    """SOCKADDR_BTH là cấu trúc đóng gói 1 byte của ws2bth.h (30 byte); GUID dịch vụ viết đúng thứ tự byte Windows."""
    assert bluetooth.ctypes.sizeof(bluetooth._SOCKADDR_BTH) == 30
    guid = bluetooth._GUID.of(bluetooth.SERVICE_UUID)
    assert bytes(guid) == bluetooth.SERVICE_UUID.bytes_le


def test_a_slow_answer_is_not_cut_at_the_dial_timeout(files: int, monkeypatch) -> None:
    """Nối cổng đồng bộ có hạn giờ; đọc thì không: hỏi dài 25 giây qua Bluetooth từng bị cắt thành EOF sau 10 giây."""
    monkeypatch.setattr(bluetooth, "DIAL_SECONDS", 0.5)
    client, server, local = _tunnel(files)
    try:
        assert _get(local.port, "/cham") == (200, b"nho")
    finally:
        client.shutdown()
        server.shutdown()


@pytest.mark.parametrize("abrupt", [False, True], ids=["dong-thuong", "cat-ngang"])
def test_an_abandoned_download_frees_both_ends(files: int, abrupt: bool) -> None:
    """Trình phát tua ra ngoài bộ đệm / đổi chương / dừng: nó đóng kết nối giữa lúc tải. Bên phục vụ phải bỏ luồng ấy
    (RESET) - trước đây nó chờ tín dụng mãi, giữ luồng, luồng đọc và socket; 64 lần là đường hầm từ chối mọi luồng."""
    client, server, local = _tunnel(files)
    try:
        for _ in range(3):
            player = socket.create_connection(("127.0.0.1", local.port))
            player.sendall(b"GET /big HTTP/1.1\r\nHost: x\r\n\r\n")
            player.settimeout(10)
            assert player.recv(65536).startswith(b"HTTP/1.1 200")
            if abrupt:  # RST như ứng dụng bị giết
                player.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("hh", 1, 0))
            player.close()
        assert _eventually(lambda: not client.streams and not server.streams, 10), (client.streams, server.streams)
        assert _get(local.port, "/nho") == (200, b"nho")
    finally:
        client.shutdown()
        server.shutdown()


def test_data_for_a_stream_that_is_gone_is_answered_with_reset() -> None:
    """Bên kia tưởng luồng còn sống (nó bị bỏ ở đây): DATA tới thì đáp RESET để nó thôi gửi; RESET tới một luồng không
    còn thì im lặng - không bao giờ đáp RESET cho RESET."""
    near, far = socket.socketpair()
    mux = Mux(far, dial=lambda: socket.create_connection(("127.0.0.1", 9)), odd=False)
    threading.Thread(target=mux.run, daemon=True).start()
    near.settimeout(5)
    try:
        near.sendall(HEADER.pack(bluetooth.RESET, 7, 0) + HEADER.pack(bluetooth.DATA, 99, 3) + b"abc")
        assert HEADER.unpack(near.recv(HEADER.size)) == (bluetooth.RESET, 99, 0)
        near.settimeout(0.3)
        with pytest.raises(TimeoutError):
            near.recv(1)
    finally:
        mux.shutdown()
        near.close()


def test_the_server_comes_back_when_bluetooth_does(monkeypatch) -> None:
    """Bluetooth tắt lúc bật đồng bộ -> lời nhắc; bật lên là tự nghe, không phải tắt mở đồng bộ. Tắt sóng khi đang nghe
    -> thôi báo "đang chạy", nói lý do, rồi lại tự mở."""
    attempts: list[str] = []
    listening = threading.Event()
    radio_off = threading.Event()

    class Radio:
        def accept(self):
            listening.set()
            radio_off.wait(5)
            raise OSError(10050, "tắt sóng")

        def close(self) -> None:
            pass

    server = BluetoothServer(0, retry_seconds=0.05)

    def listen():
        attempts.append("thử")
        if len(attempts) == 1:
            server.error = "Bluetooth của máy tính đang tắt"
            return None
        radio = Radio()
        with server._lock:
            server.socket, server.error = radio, ""
        return radio

    monkeypatch.setattr(server, "_listen", listen)
    server.start()
    try:
        assert server.view()["running"] is False and "tắt" in server.view()["error"]
        assert listening.wait(5), "bật Bluetooth rồi mà không tự nghe"
        assert server.view() == {"running": True, "channel": 0, "error": "", "connections": 0, "address": ""}
        radio_off.set()
        assert _eventually(lambda: "ngừng nghe" in server.view()["error"] or len(attempts) >= 3)
        assert _eventually(lambda: len(attempts) >= 3), "tắt sóng rồi bật lại mà không tự mở lại"
    finally:
        server.stop()
        radio_off.set()
    time.sleep(0.2)
    tried = len(attempts)
    time.sleep(0.3)
    assert len(attempts) == tried, "đã dừng mà vẫn thử mở"


def test_bluetooth_without_authentication_does_not_listen(monkeypatch) -> None:
    """Không bật được SO_BTH_AUTHENTICATE thì không nghe: máy lạ trong tầm sóng không được chạm tới cổng đồng bộ."""
    closed: list[bool] = []

    class NoAuth:
        def setsockopt(self, *_args):
            raise OSError(10042, "không hỗ trợ")

        def bind(self, *_args):
            raise AssertionError("không được nghe khi thiếu xác thực")

        def close(self) -> None:
            closed.append(True)

    monkeypatch.setattr(BluetoothServer, "_rfcomm", staticmethod(lambda: NoAuth()))
    server = BluetoothServer(0)
    assert server._listen() is None
    assert "xác thực" in server.view()["error"] and server.view()["running"] is False
    assert closed == [True]
