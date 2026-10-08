"""Đường hầm Bluetooth công bằng (webui/bluetooth.py, 08-10): đo thật trên điện thoại, tải 3 MB ở 143 KB/s làm một yêu cầu nhỏ
bên cạnh chờ ~3,5 giây. Bộ lập lịch (`_Outbox`) thử riêng không cần socket; tín dụng và RESET thử với một đầu Mux thật và
một đầu "tay" đọc/ghi khung; cuối cùng một ống nối giả lập ~150 KB/s (như RFCOMM thật) đo yêu cầu nhỏ trong lúc tải lớn."""
from __future__ import annotations

import http.client
import socket
import struct
import threading
import time

import pytest

from abook.webui import bluetooth
from abook.webui.bluetooth import (ACK, CLOSE, DATA, HEADER, LINK_WINDOW, MAX_DATA, OPEN, RESET, STREAM_WINDOW, WINDOW,
                                   LinkClosed, Mux, _Outbox)
from tests.test_bluetooth_tunnel import _tunnel, files  # noqa: F401 - fixture dùng chung


def _frames(box: _Outbox, count: int = 1000) -> list[tuple[int, int, int]]:
    """Lấy khung tới khi bộ lập lịch không còn gì gửi được: (loại, luồng, độ dài)."""
    taken = []
    for _ in range(count):
        frame = box.next(timeout=0.01)
        if frame is None:
            break
        taken.append(HEADER.unpack(frame[:HEADER.size]))
    return taken


def test_a_big_stream_does_not_starve_a_small_one() -> None:
    box = _Outbox(limit=1 << 30)
    for _ in range(50):
        box.push(1, DATA, b"x" * MAX_DATA)
    box.push(3, OPEN)
    box.push(3, DATA, b"y" * 300)
    box.push(3, CLOSE)
    order = [number for _kind, number, _length in _frames(box)]
    assert order.index(3) == 1, "luồng nhỏ chỉ chờ một khung của luồng lớn"
    assert order[1:4] == [3, 3, 3] and order.count(1) == 50


def test_two_big_streams_take_turns_by_bytes_not_by_frames() -> None:
    """Deficit round robin: luồng gửi khung nhỏ không bị thiệt so với luồng gửi khung đầy."""
    box = _Outbox(limit=1 << 30)
    for _ in range(8):
        box.push(1, DATA, b"a" * MAX_DATA)
    for _ in range(64):
        box.push(3, DATA, b"b" * (MAX_DATA // 8))
    sent = {1: 0, 3: 0}
    for _kind, number, length in _frames(box)[:24]:
        sent[number] += length
    assert abs(sent[1] - sent[3]) <= MAX_DATA


def test_control_frames_go_first_but_never_starve_data() -> None:
    box = _Outbox(limit=1 << 30)
    for _ in range(3):
        box.push(1, DATA, b"x" * 100)
    for _ in range(10):
        box.send(WINDOW, 5, struct.pack(">I", 1))
    kinds = [kind for kind, _number, _length in _frames(box)]
    assert kinds == [WINDOW] * 4 + [DATA] + [WINDOW] * 4 + [DATA] + [WINDOW] * 2 + [DATA]


def test_only_a_few_bytes_may_be_ahead_of_the_scheduler() -> None:
    """write() trả về không có nghĩa đã tới: quá IN_FLIGHT byte chưa được báo đọc thì DATA dừng, khung điều khiển vẫn đi."""
    box = _Outbox(limit=3 * MAX_DATA)
    for _ in range(10):
        box.push(1, DATA, b"x" * MAX_DATA)
    assert len(_frames(box)) == 3
    box.send(ACK, 0, struct.pack(">I", 1))
    assert [kind for kind, _n, _l in _frames(box)] == [ACK], "khung điều khiển không chờ"
    box.acked(MAX_DATA + HEADER.size)
    assert len(_frames(box)) == 1
    box.acked(1 << 20)
    assert len(_frames(box)) == 3
    box.acked(1 << 20)
    assert len(_frames(box)) == 3


def test_data_waits_for_the_link_credit_but_other_frames_do_not() -> None:
    box = _Outbox(limit=1 << 30, credit=MAX_DATA)
    box.push(1, DATA, b"x" * MAX_DATA)
    box.push(1, DATA, b"x" * MAX_DATA)
    box.push(3, OPEN)
    assert [(kind, number) for kind, number, _l in _frames(box)] == [(DATA, 1), (OPEN, 3)]
    box.credit(MAX_DATA)
    assert [(kind, number) for kind, number, _l in _frames(box)] == [(DATA, 1)]


def test_a_dropped_stream_sends_nothing_more_and_a_closed_box_refuses() -> None:
    box = _Outbox(limit=1 << 30)
    for _ in range(5):
        box.push(1, DATA, b"x" * MAX_DATA)
        box.push(3, DATA, b"y" * MAX_DATA)
    box.drop(1)
    assert {number for _kind, number, _l in _frames(box)} == {3}
    box.close()
    assert box.next(timeout=0.01) is None
    with pytest.raises(LinkClosed):
        box.push(1, DATA, b"x")


# ---- Mux thật với một đầu "tay" -----------------------------------------------------------------------------------------

class _Raw:
    """Đầu bên kia viết tay: đọc khung, tự quyết khi nào trả tín dụng / báo đã đọc."""

    def __init__(self, sock: socket.socket) -> None:
        self.sock = sock
        sock.settimeout(5)

    def send(self, kind: int, number: int, payload: bytes = b"") -> None:
        self.sock.sendall(HEADER.pack(kind, number, len(payload)) + payload)

    def frame(self, timeout: float = 5) -> tuple[int, int, bytes] | None:
        self.sock.settimeout(timeout)
        try:
            kind, number, length = HEADER.unpack(bluetooth._read_exact(self.sock, HEADER.size))
        except (TimeoutError, socket.timeout):
            return None
        self.sock.settimeout(5)
        return kind, number, bluetooth._read_exact(self.sock, length) if length else b""

    def data_until_quiet(self, quiet: float = 0.4) -> dict[int, int]:
        """Đếm byte DATA mỗi luồng tới khi im `quiet` giây; báo đã đọc mọi thứ để IN_FLIGHT không chặn."""
        got: dict[int, int] = {}
        while (frame := self.frame(quiet)) is not None:
            kind, number, payload = frame
            assert len(payload) <= MAX_DATA
            if kind == DATA:
                got[number] = got.get(number, 0) + len(payload)
                self.send(ACK, 0, struct.pack(">I", HEADER.size + len(payload)))
        return got


def _feeding_mux(streams: int, *, limit: int = bluetooth.IN_FLIGHT) -> tuple[Mux, _Raw, list[socket.socket]]:
    """Một Mux bên kết nối, `streams` luồng mà ứng dụng cục bộ đổ dữ liệu vào không ngừng; bên kia là _Raw."""
    near, far = socket.socketpair()
    mux = Mux(far, limit=limit)
    threading.Thread(target=mux.run, daemon=True).start()
    apps = []
    for _ in range(streams):
        app, local = socket.socketpair()
        mux.open(local)
        threading.Thread(target=lambda a=app: _flood(a), daemon=True).start()
        apps.append(app)
    return mux, _Raw(near), apps


def _flood(app: socket.socket) -> None:
    try:
        while True:
            app.sendall(b"z" * 65536)
    except OSError:
        pass


def _close_all(mux: Mux, raw: _Raw, apps: list[socket.socket]) -> None:
    mux.shutdown()
    raw.sock.close()
    for app in apps:
        app.close()


def test_a_stream_stops_at_its_credit_when_the_other_side_does_not_read() -> None:
    mux, raw, apps = _feeding_mux(1)
    try:
        assert raw.data_until_quiet() == {1: STREAM_WINDOW}
        raw.send(WINDOW, 1, struct.pack(">I", 16 * 1024))
        assert raw.data_until_quiet() == {1: 16 * 1024}
    finally:
        _close_all(mux, raw, apps)


def test_all_streams_together_stop_at_the_link_credit() -> None:
    """Trần bộ nhớ nhận: năm luồng x 64 KB vẫn chỉ được 256 KB chưa trả tín dụng chung."""
    mux, raw, apps = _feeding_mux(5)
    try:
        first = sum(raw.data_until_quiet().values())
        assert LINK_WINDOW - MAX_DATA < first <= LINK_WINDOW  # khung DATA không bị cắt để vừa phần tín dụng lẻ
        raw.send(WINDOW, 0, struct.pack(">I", 32 * 1024))
        assert LINK_WINDOW + 32 * 1024 - MAX_DATA < first + sum(raw.data_until_quiet().values()) <= LINK_WINDOW + 32 * 1024
    finally:
        _close_all(mux, raw, apps)


def test_a_stream_reset_midway_stops_while_the_other_goes_on() -> None:
    """Bên kia bỏ luồng giữa chừng (RESET): khung còn xếp của luồng ấy bị bỏ, luồng kia vẫn chạy."""
    mux, raw, apps = _feeding_mux(2, limit=2 * MAX_DATA)
    try:
        for _ in range(2):  # chưa báo đọc: chỉ ~2 khung lọt ra, phần còn lại nằm trong hàng
            raw.frame()
        raw.send(RESET, 1)
        time.sleep(0.2)
        got = raw.data_until_quiet()
        assert got.get(1, 0) <= 2 * MAX_DATA, "khung của luồng đã bỏ vẫn được gửi"
        assert got.get(3, 0) >= STREAM_WINDOW - 2 * MAX_DATA
        assert 1 not in mux.streams and 3 in mux.streams
    finally:
        _close_all(mux, raw, apps)


def test_too_much_data_against_the_link_credit_ends_the_link() -> None:
    """Bên kia gửi quá tín dụng chung (cổng cục bộ chưa nối nên chưa tiêu được byte nào): sai giao thức, cắt đường hầm."""
    near, far = socket.socketpair()
    gate = threading.Event()
    mux = Mux(far, dial=lambda: (gate.wait(), socket.socketpair()[0])[1], odd=False)
    threading.Thread(target=mux.run, daemon=True).start()
    raw = _Raw(near)
    try:
        for number in range(1, 13, 2):
            raw.send(OPEN, number)
        for _ in range(LINK_WINDOW // MAX_DATA + 1):
            raw.send(DATA, 1 + 2 * (_ % 6), b"x" * MAX_DATA)
        deadline = time.time() + 5
        while mux.alive and time.time() < deadline:
            time.sleep(0.05)
        assert not mux.alive
    finally:
        gate.set()
        mux.shutdown()
        near.close()


# ---- ống nối giả lập RFCOMM ~150 KB/s ------------------------------------------------------------------------------------

RATE = 150 * 1024


def _throttle(source: socket.socket, target: socket.socket) -> None:
    """Một chiều của "sóng": đọc từng ít một, nhả theo nhịp RATE. Phần chưa đi nằm trong bộ đệm socket - đúng như bộ đệm
    RFCOMM/hệ điều hành nuốt byte trước khi sóng kịp gửi."""
    started, total = time.perf_counter(), 0
    try:
        while chunk := source.recv(1024):
            total += len(chunk)
            wait = started + total / RATE - time.perf_counter()
            if wait > 0:
                time.sleep(wait)
            else:
                started, total = time.perf_counter(), 0
            target.sendall(chunk)
    except OSError:
        pass
    for sock in (source, target):
        bluetooth._close_socket(sock)


def _slow_tunnel(port: int, mux_class=Mux) -> tuple[Mux, Mux, bluetooth.LocalPort]:
    client_end, wire_a = socket.socketpair()
    wire_b, server_end = socket.socketpair()
    threading.Thread(target=_throttle, args=(wire_a, wire_b), daemon=True).start()
    threading.Thread(target=_throttle, args=(wire_b, wire_a), daemon=True).start()
    server = mux_class(server_end, dial=bluetooth.BluetoothServer(port)._dial, odd=False)
    client = mux_class(client_end)
    threading.Thread(target=server.run, daemon=True).start()
    threading.Thread(target=client.run, daemon=True).start()
    return client, server, bluetooth.LocalPort(client)


def small_request_during_download(port: int, mux_class=Mux) -> tuple[float, float]:
    """(giây cho một yêu cầu nhỏ giữa lúc tải lớn, KB/s của lần tải) trên ống ~150 KB/s."""
    client, server, local = _slow_tunnel(port, mux_class)
    stop = threading.Event()
    got = [0]

    def download() -> None:
        sock = socket.create_connection(("127.0.0.1", local.port))
        sock.sendall(b"GET /big HTTP/1.1\r\nHost: x\r\n\r\n")
        sock.settimeout(1)
        while not stop.is_set():
            try:
                chunk = sock.recv(65536)
            except (TimeoutError, socket.timeout):
                continue
            if not chunk:
                break
            got[0] += len(chunk)
        sock.close()

    worker = threading.Thread(target=download, daemon=True)
    worker.start()
    try:
        time.sleep(2.0)  # tải đã chạy đều, mọi bộ đệm đã đầy
        before, at = got[0], time.perf_counter()
        connection = http.client.HTTPConnection("127.0.0.1", local.port, timeout=20)
        connection.request("GET", "/nho")
        response = connection.getresponse()
        assert response.read() == b"nho"
        took = time.perf_counter() - at
        connection.close()
        time.sleep(1.0)
        rate = (got[0] - before) / (time.perf_counter() - at) / 1024
        return took, rate
    finally:
        stop.set()
        worker.join(5)
        client.shutdown()
        server.shutdown()
        local.close()


def test_a_small_request_is_quick_while_a_big_download_fills_a_slow_link(files: int) -> None:  # noqa: F811
    took, rate = small_request_during_download(files)
    assert took < 0.3, f"yêu cầu nhỏ chờ {took:.2f} s sau luồng tải"
    assert rate > 0.6 * RATE / 1024, f"tải chỉ còn {rate:.0f} KB/s"
