"""Thân yêu cầu không có Content-Length (Transfer-Encoding: chunked) phải bị từ chối RÕ RÀNG, không đọc ra rỗng.

Máy thật 02-11: điện thoại gửi nguồn truyện chunked, mọi chỗ đọc thân chỉ biết Content-Length nên thân thành rỗng, người nghe nhận
"thiếu tên file" và các khúc chunked nằm lại trong kết nối giữ sống. Mỗi cổng (giao diện cục bộ, cổng đồng bộ, chuyển tiếp Studio
từ xa) trả 411 kèm câu nói đúng việc và đóng kết nối; cùng thân có Content-Length thì chạy như thường."""
from __future__ import annotations

import base64
import json
import socket
import ssl

from abook.webui.library import book_id
from tests.test_remote_studio import studio  # noqa: F401 - fixture dùng chung
from tests.test_remote_studio_paths import _cookie_with_studio
from tests.test_webui_listen_and_sync import library  # noqa: F401

MESSAGE = "Thiếu Content-Length - máy gửi phải khai độ dài thân"
UPLOAD = {"folder": "Truyện", "name": "001.txt", "data": base64.b64encode("Chương 1\n\nTrời sáng.".encode()).decode()}


def _chunked(payload: bytes) -> bytes:
    return b"%x\r\n%s\r\n0\r\n\r\n" % (len(payload), payload)


def _request_bytes(port: int, method: str, path: str, headers: dict[str, str], body: bytes, *, chunked: bool) -> bytes:
    head = {"Host": f"127.0.0.1:{port}", "Content-Type": "application/json", **headers}
    if chunked:
        head["Transfer-Encoding"] = "chunked"
        body = _chunked(body)
    else:
        head["Content-Length"] = str(len(body))
    lines = [f"{method} {path} HTTP/1.1", *(f"{name}: {value}" for name, value in head.items()), "", ""]
    return "\r\n".join(lines).encode("utf-8") + body


def _read_response(sock: socket.socket) -> tuple[int, dict[str, str], bytes]:
    data = b""
    while b"\r\n\r\n" not in data:
        chunk = sock.recv(65536)
        if not chunk:
            raise AssertionError(f"kết nối đóng trước khi có câu trả lời: {data!r}")
        data += chunk
    head, _, rest = data.partition(b"\r\n\r\n")
    lines = head.decode("iso-8859-1").split("\r\n")
    headers = {name.lower(): value.strip() for name, _, value in (line.partition(":") for line in lines[1:])}
    length = int(headers.get("content-length", "0"))
    while len(rest) < length:
        chunk = sock.recv(65536)
        if not chunk:
            break
        rest += chunk
    return int(lines[0].split()[1]), headers, rest[:length]


def _connection_is_closed(sock: socket.socket) -> bool:
    """Yêu cầu thứ hai trên cùng kết nối không được trả lời: EOF hay bị ngắt (không phải im lặng chờ, không phải câu trả lời)."""
    try:
        sock.sendall(b"GET /api/app HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n")
        return sock.recv(65536) == b""
    except (ConnectionError, ssl.SSLError):
        return True
    except TimeoutError:
        return False


def _send(port: int, secure: bool, method: str, path: str, headers: dict[str, str], payload: dict | bytes, *,
          chunked: bool) -> tuple[int, dict[str, str], bytes, bool]:
    """Một yêu cầu thô trên một ổ cắm; trả (trạng thái, header, thân, kết nối-đã-đóng-sau-đó)."""
    body = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")
    sock = socket.create_connection(("127.0.0.1", port), timeout=5)
    try:
        if secure:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            sock = context.wrap_socket(sock)
        sock.sendall(_request_bytes(port, method, path, headers, body, chunked=chunked))
        status, response_headers, data = _read_response(sock)
        return status, response_headers, data, _connection_is_closed(sock)
    finally:
        sock.close()


def _refused(status: int, data: bytes, closed: bool) -> None:
    assert status == 411, data
    assert json.loads(data)["error"] == MESSAGE
    assert closed, "kết nối phải đóng: các khúc chunked chưa đọc không được ở lại cho yêu cầu kế tiếp"


world = studio  # cùng một dựng: giao diện cục bộ + cổng đồng bộ + Studio từ xa
# ---- giao diện cục bộ (server.py) -------------------------------------------------------------------------


def test_the_local_ui_refuses_a_chunked_body_and_closes_the_connection(world) -> None:
    app, _project = world
    status, _headers, data, closed = _send(app.local_port, False, "POST", "/api/sources/upload", {"X-Ebook-Token": "phien"},
                                           UPLOAD, chunked=True)
    _refused(status, data, closed)


def test_the_local_ui_still_closes_after_a_chunked_body_nobody_read(world) -> None:
    """Đường không đọc thân (nút Huỷ...): không có Content-Length để bỏ đi đúng cỡ, nên không giữ kết nối sống."""
    app, _project = world
    status, _headers, data, closed = _send(app.local_port, False, "POST", "/api/nothing-here", {"X-Ebook-Token": "phien"},
                                           {}, chunked=True)
    assert status == 404, data  # đường không tồn tại cũng không đọc thân
    assert closed


def test_the_local_ui_reads_the_same_body_when_it_has_a_length(world) -> None:
    app, _project = world
    status, _headers, data, _closed = _send(app.local_port, False, "POST", "/api/sources/upload", {"X-Ebook-Token": "phien"},
                                            UPLOAD, chunked=False)
    assert status == 200, data
    assert json.loads(data)["path"].endswith("001.txt")


# ---- cổng đồng bộ (sync.py) -------------------------------------------------------------------------------


def _device_token(app) -> str:
    code = app.devices.start_pairing()["code"]
    status, _headers, data, _closed = _send(app.sync_server.port, True, "POST", "/sync/v1/pair", {},
                                            {"code": code, "device": "Pixel"}, chunked=False)
    assert status == 200, data
    return json.loads(data)["token"]


def test_the_sync_host_refuses_a_chunked_pairing_body(world) -> None:
    app, _project = world
    code = app.devices.start_pairing()["code"]
    status, _headers, data, closed = _send(app.sync_server.port, True, "POST", "/sync/v1/pair", {},
                                           {"code": code, "device": "Pixel"}, chunked=True)
    _refused(status, data, closed)


def test_the_sync_host_refuses_a_chunked_body_from_a_paired_device(world) -> None:
    app, _project = world
    token = _device_token(app)
    auth = {"Authorization": f"Bearer {token}"}
    port = app.sync_server.port
    status, _headers, data, closed = _send(port, True, "POST", "/sync/v1/name", auth, {"name": "Máy mới"}, chunked=True)
    _refused(status, data, closed)
    status, _headers, data, _closed = _send(port, True, "POST", "/sync/v1/name", auth, {"name": "Máy mới"}, chunked=False)
    assert status == 200, data


def test_the_sync_host_refuses_a_chunked_edits_package_instead_of_calling_it_too_large(world) -> None:
    app, project = world
    token = _device_token(app)
    status, _headers, data, closed = _send(app.sync_server.port, True, "POST", f"/sync/v1/books/{book_id(project)}/edits",
                                           {"Authorization": f"Bearer {token}", "Content-Type": "application/zip"},
                                           b"PK\x03\x04", chunked=True)
    _refused(status, data, closed)


def test_an_unpaired_chunked_request_gets_401_and_the_connection_closes(world) -> None:
    app, _project = world
    status, _headers, data, closed = _send(app.sync_server.port, True, "POST", "/sync/v1/remote", {}, {"wait": 0}, chunked=True)
    assert status == 401, data
    assert closed


# ---- chuyển tiếp Studio từ xa (remote_studio.read_body) ----------------------------------------------------


def test_the_remote_studio_relay_refuses_a_chunked_body_and_forwards_the_same_body_with_a_length(world) -> None:
    app, _project = world
    cookie = _cookie_with_studio(app)
    port = app.sync_server.port
    status, _headers, data, closed = _send(port, True, "POST", "/api/sources/upload", cookie, UPLOAD, chunked=True)
    _refused(status, data, closed)
    status, _headers, data, _closed = _send(port, True, "POST", "/api/sources/upload", cookie, UPLOAD, chunked=False)
    assert status == 200, data
    assert json.loads(data)["folder"] == "up:Truyện"
