"""Đường hầm Bluetooth (webui/bluetooth.py): một kết nối mang nhiều luồng HTTP của cổng đồng bộ. RFCOMM thật cần sóng
Bluetooth và một máy thứ hai; ở đây một cặp socket đứng thay cho kết nối RFCOMM - giao thức khung, cửa sổ tín dụng, đóng
nửa chiều và đứt kết nối là của đường hầm, không phụ thuộc lớp vận chuyển."""
from __future__ import annotations

import http.client
import json
import socket
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from ebook_reader.webui import bluetooth
from ebook_reader.webui.bluetooth import LocalPort, Mux
from ebook_reader.webui.sync import Devices, SyncApp, SyncServer
from tests.test_webui_listen_and_sync import library  # noqa: F401 - fixture dùng chung

BIG = bytes(range(256)) * 16 * 1024  # 4 MB, lớn hơn nhiều lần cửa sổ 256 KB


class Files(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *_args: object) -> None:
        pass

    def do_GET(self) -> None:  # noqa: N802
        body = BIG if self.path == "/big" else b"nho"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _tunnel(port: int) -> tuple[Mux, Mux, LocalPort]:
    """Hai đầu đường hầm trên một cặp socket; đầu phục vụ nối vào `port` như máy tính nối vào cổng đồng bộ."""
    near, far = socket.socketpair()
    server = Mux(far, dial=lambda: socket.create_connection(("127.0.0.1", port)), odd=False)
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
        assert orphan.recv(16) == b""
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
