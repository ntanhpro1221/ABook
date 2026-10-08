"""Máy tính dùng thư viện của điện thoại QUA BLUETOOTH (webui/bluetooth.py: tra SDP + Gateway; remote_books.py: chọn đường).

Không cần Bluetooth thật: bộ đệm WSAQUERYSETW dựng tay thay kết quả tra SDP của Windows, một cặp socket thay kết nối RFCOMM,
cổng đồng bộ thật (TLS, ghim vân tay) đứng sau phía "điện thoại" của đường hầm. Phần chưa kiểm được ở đây là chính lời gọi
WSALookupService / connect của Windows trên sóng thật - xem scripts/bt_desktop_probe.py và docs/BLUETOOTH.md.
"""
from __future__ import annotations

import ctypes
import json
import socket
import threading
import time
from pathlib import Path

import pytest

from abook.webui import bluetooth, remote_books, route, tls
from abook.webui.bluetooth import BluetoothServer, Gateway, Mux
from abook.webui.remote_books import Computers, RemoteError
from abook.webui.sync import Devices, SyncApp, SyncServer
from tests.test_webui_listen_and_sync import library  # noqa: F401 - fixture dùng chung

PHONE = "AA:BB:CC:DD:EE:FF"


@pytest.fixture(autouse=True)
def _clean_routes():
    route.reset()
    yield
    bluetooth.forget(PHONE)
    route.reset()


def _eventually(check, timeout: float = 5.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if check():
            return True
        time.sleep(0.03)
    return check()


class FakePhone:
    """Điện thoại phía bên kia RFCOMM: mỗi lần `connect` là một cặp socket, đầu xa là Mux phục vụ (số chẵn) nối vào cổng đồng
    bộ `sync_port` - đúng việc BluetoothShare làm với LibraryServer."""

    def __init__(self, sync_port: int) -> None:
        self.sync_port = sync_port
        self.connects = 0
        self.links: list[Mux] = []

    def connect(self, address: str) -> socket.socket:
        assert address == PHONE
        self.connects += 1
        near, far = socket.socketpair()
        server = Mux(far, dial=BluetoothServer(self.sync_port)._dial, odd=False)
        threading.Thread(target=server.run, daemon=True).start()
        self.links.append(server)
        return near

    def drop(self) -> None:
        for link in self.links:
            link.shutdown()


def _sync(library, tmp_path: Path, name: str = "Điện thoại", identity: tls.Identity | None = None):  # noqa: F811
    lib, _project, listening = library
    devices = Devices(tmp_path / name / "devices.json")
    server = SyncServer(SyncApp(lib, listening, devices, name), host="127.0.0.1", port=0, identity=identity).start()
    return server, devices


def _free_port() -> int:
    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    return port


# ---- địa chỉ và cổng ổn định ---------------------------------------------------------------------------------------------


def test_the_local_port_is_the_same_one_the_phone_computes() -> None:
    """Số lấy từ `"...".hashCode() and 31` của Java (chạy thật trong JBR của Android Studio): cùng máy, cùng cổng."""
    expected = {"12:34:56:78:9A:BC": 47689, "F0:DE:F1:23:45:67": 47677, "3C:5A:B4:00:AA:01": 47675, PHONE: 47696}
    assert {address: bluetooth.stable_port(address) for address in expected} == expected
    assert all(47670 <= port < 47702 for port in expected.values())


def test_a_bluetooth_address_is_normalised_or_refused() -> None:
    assert bluetooth.normalize_address("aa-bb-cc-dd-ee-ff") == PHONE
    assert bluetooth.normalize_address(f"  {PHONE} ") == PHONE
    for bad in ("", "192.168.1.20", "AA:BB:CC:DD:EE", "GG:BB:CC:DD:EE:FF", "AA:BB:CC:DD:EE:FF:00", "bt:AA:BB:CC:DD:EE:FF"):
        assert bluetooth.normalize_address(bad) == "", bad
    with pytest.raises(ValueError):
        bluetooth.gateway("khong-phai-dia-chi")


# ---- tra SDP: phần thuần ---------------------------------------------------------------------------------------------------


def test_the_sdp_query_asks_for_the_abook_service_on_that_device() -> None:
    query = bluetooth._ServiceQuery(PHONE)
    assert query.query.lpszContext == f"({PHONE})" and query.query.dwNameSpace == bluetooth.NS_BTH == 16
    assert query.query.dwSize == ctypes.sizeof(bluetooth._WSAQUERYSETW)
    assert bytes(query.query.lpServiceClassId.contents) == bluetooth.SERVICE_UUID.bytes_le
    assert bluetooth.LOOKUP_FLAGS == 0x1000 | 0x0100, "LUP_FLUSHCACHE (0x1000, không phải LUP_FLUSHPREVIOUS 0x2000) | LUP_RETURN_ADDR"
    if ctypes.sizeof(ctypes.c_void_p) == 8:
        assert ctypes.sizeof(bluetooth._WSAQUERYSETW) == 120, "bố cục WSAQUERYSETW của ws2def.h trên x64"


def _fill(buffer, entries: list[tuple[int, int]]) -> None:
    """Dựng trong `buffer` một kết quả như WSALookupServiceNext trả: WSAQUERYSETW -> CSADDR_INFO[] -> SOCKADDR_BTH, mọi con
    trỏ trỏ vào chính bộ đệm."""
    base, csa_at, sock_at = ctypes.addressof(buffer), 512, 1024
    result = bluetooth._WSAQUERYSETW.from_buffer(buffer)
    result.dwSize = ctypes.sizeof(result)
    csa = (bluetooth._CSADDR_INFO * max(1, len(entries))).from_buffer(buffer, csa_at)
    for index, (family, port) in enumerate(entries):
        address = bluetooth._SOCKADDR_BTH.from_buffer(buffer, sock_at + index * 64)
        address.addressFamily, address.btAddr, address.port = family, 0xAABBCCDDEEFF, port
        csa[index].RemoteAddr.lpSockaddr = base + sock_at + index * 64
        csa[index].RemoteAddr.iSockaddrLength = ctypes.sizeof(address)
    result.dwNumberOfCsAddrs = len(entries)
    result.lpcsaBuffer = ctypes.cast(base + csa_at, ctypes.POINTER(bluetooth._CSADDR_INFO))


def test_the_rfcomm_channel_is_read_from_the_csaddr_info() -> None:
    buffer = ctypes.create_string_buffer(4096)
    _fill(buffer, [(bluetooth.AF_BTH, 7)])
    assert bluetooth.channels_of(bluetooth._WSAQUERYSETW.from_buffer(buffer)) == [7]

    # Mục không phải địa chỉ Bluetooth, kênh 0 hay ngoài 1-30 là rác: bỏ, lấy mục đúng sau nó.
    buffer = ctypes.create_string_buffer(4096)
    _fill(buffer, [(2, 7), (bluetooth.AF_BTH, 0), (bluetooth.AF_BTH, 31), (bluetooth.AF_BTH, 12)])
    assert bluetooth.channels_of(bluetooth._WSAQUERYSETW.from_buffer(buffer)) == [12]

    empty = ctypes.create_string_buffer(4096)
    assert bluetooth.channels_of(bluetooth._WSAQUERYSETW.from_buffer(empty)) == [], "không có CSADDR_INFO nào"
    short = ctypes.create_string_buffer(4096)
    _fill(short, [(bluetooth.AF_BTH, 7)])
    bluetooth._CSADDR_INFO.from_buffer(short, 512).RemoteAddr.iSockaddrLength = 10
    assert bluetooth.channels_of(bluetooth._WSAQUERYSETW.from_buffer(short)) == [], "SOCKADDR cụt không đọc"


class FakeWs2:
    """Thay ws2_32: mỗi phần tử `script` là danh sách (họ địa chỉ, kênh) của một lần Next, hay mã lỗi (int)."""

    def __init__(self, script: list, begin_error: int = 0) -> None:
        self.script, self.begin_error, self.errors = list(script), begin_error, 0
        self.contexts: list[str] = []
        self.flags: list[int] = []
        self.ended = 0
        self.sizes: list[int] = []

    def WSALookupServiceBeginW(self, query, flags, handle):  # noqa: N802
        self.contexts.append(query._obj.lpszContext)
        self.flags.append(flags)
        if self.begin_error:
            self.errors = self.begin_error
            return -1
        return 0

    def WSALookupServiceNextW(self, handle, flags, length, buffer):  # noqa: N802
        self.flags.append(flags)
        self.sizes.append(length._obj.value)
        step = self.script.pop(0) if self.script else bluetooth.WSA_E_NO_MORE
        if isinstance(step, int):
            self.errors = step
            return -1
        if isinstance(step, tuple):  # ("nho", cỡ cần): bộ đệm nhỏ quá
            self.errors = bluetooth.WSAEFAULT
            length._obj.value = step[1]
            return -1
        _fill(buffer, step)
        return 0

    def WSALookupServiceEnd(self, handle):  # noqa: N802
        self.ended += 1

    def ws2(self) -> bluetooth._Ws2:
        return bluetooth._Ws2(dll=self, last_error=lambda: self.errors)


def test_find_channel_walks_the_results_and_always_ends_the_lookup() -> None:
    fake = FakeWs2([[(bluetooth.AF_BTH, 0)], [(bluetooth.AF_BTH, 9)]])
    assert bluetooth.find_channel(PHONE, ws2=fake.ws2()) == 9
    assert fake.contexts == [f"({PHONE})"] and set(fake.flags) == {bluetooth.LOOKUP_FLAGS} and fake.ended == 1


def test_a_small_buffer_is_retried_with_the_size_windows_asks_for() -> None:
    fake = FakeWs2([("nho", 8192), [(bluetooth.AF_BTH, 4)]])
    assert bluetooth.find_channel(PHONE, ws2=fake.ws2()) == 4
    assert fake.sizes == [4096, 8192]


def test_no_abook_service_is_said_plainly_and_a_dead_radio_is_not_confused_with_it() -> None:
    with pytest.raises(bluetooth.ServiceNotFound, match="Không thấy ABook"):
        bluetooth.find_channel(PHONE, ws2=FakeWs2([bluetooth.WSA_E_NO_MORE]).ws2())
    with pytest.raises(bluetooth.ServiceNotFound):
        bluetooth.find_channel(PHONE, ws2=FakeWs2([], begin_error=bluetooth.WSASERVICE_NOT_FOUND).ws2())
    with pytest.raises(bluetooth.ServiceNotFound):
        bluetooth.find_channel(PHONE, ws2=FakeWs2([bluetooth.WSANO_DATA]).ws2())
    fake = FakeWs2([], begin_error=10050)
    with pytest.raises(OSError, match="Bluetooth của máy tính đang tắt"):
        bluetooth.connect_rfcomm(PHONE, ws2=fake.ws2())
    odd = FakeWs2([10061])
    with pytest.raises(OSError, match="Không tra được ABook") as caught:
        bluetooth.connect_rfcomm(PHONE, ws2=odd.ws2())
    assert not isinstance(caught.value, bluetooth.ServiceNotFound) and odd.ended == 1, "lỗi lạ vẫn đóng lượt tra"


# ---- Gateway: một kết nối RFCOMM, nhiều luồng, nối lười ---------------------------------------------------------------------


def _get(port: int, path: str = "/sync/v1/library", token: str = "") -> tuple[int, bytes]:
    connection = tls.PinnedHTTPSConnection("127.0.0.1", port, expected=None, timeout=20)
    try:
        connection.request("GET", path, headers={"Authorization": f"Bearer {token}"} if token else {})
        response = connection.getresponse()
        return response.status, response.read()
    finally:
        connection.close()


def test_the_gateway_dials_lazily_once_and_carries_many_requests(library, tmp_path: Path) -> None:  # noqa: F811
    sync, devices = _sync(library, tmp_path)
    phone = FakePhone(sync.port)
    link = Gateway(PHONE, connect=phone.connect)
    try:
        assert phone.connects == 0 and not link.up, "chưa ai dùng thì chưa mở RFCOMM"
        results: list[int] = []
        workers = [threading.Thread(target=lambda: results.append(_get(link.port)[0])) for _ in range(6)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(20)
        assert results == [401] * 6, "cổng đồng bộ thật trả lời (chưa có mã thiết bị): đường hầm chỉ chuyển byte"
        assert phone.connects == 1 and link.up, "sáu yêu cầu song song, MỘT kết nối RFCOMM"
    finally:
        link.close()
        phone.drop()
        sync.stop()


def test_the_gateway_numbers_its_streams_odd_like_the_phone_expects(library, tmp_path: Path) -> None:  # noqa: F811
    sync, _devices = _sync(library, tmp_path)
    phone = FakePhone(sync.port)
    link = Gateway(PHONE, connect=phone.connect)
    try:
        assert _get(link.port)[0] == 401
        assert link._mux is not None and next(link._mux.numbers) % 2 == 1, "bên gọi số lẻ; điện thoại phục vụ số chẵn"
    finally:
        link.close()
        phone.drop()
        sync.stop()


def test_a_dropped_link_is_reopened_by_the_next_request(library, tmp_path: Path) -> None:  # noqa: F811
    sync, _devices = _sync(library, tmp_path)
    phone = FakePhone(sync.port)
    link = Gateway(PHONE, connect=phone.connect, retry_seconds=0)
    try:
        assert _get(link.port)[0] == 401
        phone.drop()  # ra ngoài tầm sóng
        assert _eventually(lambda: not link.up)
        assert _get(link.port)[0] == 401 and phone.connects == 2
    finally:
        link.close()
        phone.drop()
        sync.stop()


def test_a_failed_dial_is_not_repeated_at_once_and_says_why() -> None:
    attempts: list[str] = []

    def refuse(address: str) -> socket.socket:
        attempts.append(address)
        raise OSError("Không thấy ABook trên máy kia qua Bluetooth")

    link = Gateway(PHONE, connect=refuse, retry_seconds=30)
    try:
        for _ in range(3):
            client = socket.create_connection(("127.0.0.1", link.port))
            client.settimeout(10)
            assert client.recv(10) == b"", "kết nối cục bộ bị đóng ngay, không treo"
            client.close()
        assert attempts == [PHONE], "vừa hỏng thì 10-30 giây sau mới quay số lại"
        assert "Không thấy ABook" in link.last_error and not link.up
    finally:
        link.close()


def test_dialing_never_blocks_the_caller() -> None:
    gate = threading.Event()

    def slow(address: str) -> socket.socket:
        gate.wait(10)
        raise OSError("hết hạn")

    link = Gateway(PHONE, connect=slow)
    try:
        started = time.time()
        link.warm()
        client = socket.create_connection(("127.0.0.1", link.port))  # kết nối cục bộ nhận ngay
        assert time.time() - started < 1, "quay số RFCOMM chậm không được chặn người gọi"
        client.close()
    finally:
        gate.set()
        link.close()


def test_the_link_closes_when_idle_and_reopens_on_demand(library, tmp_path: Path) -> None:  # noqa: F811
    sync, _devices = _sync(library, tmp_path)
    phone = FakePhone(sync.port)
    link = Gateway(PHONE, connect=phone.connect, idle_seconds=0.4, retry_seconds=0)
    try:
        assert _get(link.port)[0] == 401 and link.up
        assert _eventually(lambda: not link.up, 6), "không luồng nào: đóng RFCOMM, đỡ tốn pin điện thoại"
        assert _get(link.port)[0] == 401 and phone.connects == 2
    finally:
        link.close()
        phone.drop()
        sync.stop()


def test_closing_the_gateway_frees_the_port_and_the_link(library, tmp_path: Path) -> None:  # noqa: F811
    sync, _devices = _sync(library, tmp_path)
    phone = FakePhone(sync.port)
    link = Gateway(PHONE, connect=phone.connect)
    try:
        assert _get(link.port)[0] == 401
        port = link.port
        link.close()
        assert not link.up and _eventually(lambda: all(not mux.alive for mux in phone.links))
        with pytest.raises(OSError):
            socket.create_connection(("127.0.0.1", port), timeout=2)
    finally:
        link.close()
        phone.drop()
        sync.stop()


def test_a_busy_stable_port_falls_back_to_any_free_one() -> None:
    holder = socket.create_server(("127.0.0.1", bluetooth.stable_port(PHONE)))
    link = None
    try:
        link = Gateway(PHONE, connect=lambda address: (_ for _ in ()).throw(OSError("không dùng")))
        assert link.port not in (0, bluetooth.stable_port(PHONE))
    finally:
        holder.close()
        if link is not None:
            link.close()


# ---- máy tính ghép và dùng điện thoại qua Bluetooth -----------------------------------------------------------------------


def test_pairing_over_bluetooth_with_the_six_digit_code_then_the_library_flows(library, tmp_path: Path) -> None:  # noqa: F811
    sync, devices = _sync(library, tmp_path)
    phone = FakePhone(sync.port)
    bluetooth.gateway(PHONE, connect=phone.connect)  # RFCOMM giả; mọi thứ khác là mã thật
    computers = Computers(tmp_path / "nay" / "computers.json")
    try:
        paired = computers.pair(f"bt:{PHONE.lower()}", devices.start_pairing()["code"], "Máy tính thử")
        entry = computers.get(paired["id"])
        assert entry["host"] == f"bt:{PHONE}" and entry["name"] == "Điện thoại"
        assert entry["fingerprint"] == sync.fingerprint, "vân tay ghi lại là của chứng chỉ ở BÊN KIA đường hầm"
        assert phone.connects == 1

        endpoint = remote_books._base(entry)
        assert endpoint.host == "127.0.0.1" and endpoint.bluetooth == PHONE and endpoint.fingerprint == sync.fingerprint
        books = json.loads(remote_books._request(endpoint, "GET", "/sync/v1/library", entry["token"]))["books"]
        assert books, "thư viện của máy kia đi qua đường hầm"
        player = remote_books.player(entry)
        assert isinstance(player, dict), "luồng hỏi trình phát dùng đúng đường ấy"
        assert phone.connects == 1, "mọi yêu cầu chung MỘT kết nối RFCOMM"

        # Ghép lại cùng địa chỉ thì thay chỗ cũ, không thêm máy.
        again = computers.pair(PHONE, devices.start_pairing()["code"], "Máy tính thử")
        assert again["id"] == paired["id"] and len(computers.list()) == 1

        computers.forget(paired["id"], tmp_path / "thu_vien")
        assert bluetooth._gateways.get(PHONE) is None, "thôi ghép là đóng đường hầm"
    finally:
        sync.stop()
        phone.drop()


def test_a_bare_or_malformed_bluetooth_address_is_understood_or_refused(library, tmp_path: Path) -> None:  # noqa: F811
    sync, devices = _sync(library, tmp_path)
    phone = FakePhone(sync.port)
    bluetooth.gateway(PHONE, connect=phone.connect)
    computers = Computers(tmp_path / "nay" / "computers.json")
    try:
        assert computers.pair(PHONE, devices.start_pairing()["code"], "x")["host"] == f"bt:{PHONE}"
        with pytest.raises(RemoteError, match="Bluetooth"):
            computers.pair("bt:khong-phai", "123456", "x")
        with pytest.raises(RemoteError, match="mã 6 số"):
            computers.pair(PHONE, "12", "x")
    finally:
        sync.stop()
        phone.drop()


def test_the_pinned_fingerprint_is_still_enforced_through_the_tunnel(library, tmp_path: Path) -> None:  # noqa: F811
    """Đổi host sang 127.0.0.1 không làm lỏng TLS: vân tay sai/trống bị từ chối, và một máy KHÁC (chứng chỉ khác) đứng sau
    đường hầm không nhận được mã thiết bị."""
    sync, devices = _sync(library, tmp_path)
    phone = FakePhone(sync.port)
    bluetooth.gateway(PHONE, connect=phone.connect)
    computers = Computers(tmp_path / "nay" / "computers.json")
    try:
        paired = computers.pair(f"bt:{PHONE}", devices.start_pairing()["code"], "Máy tính thử")
        entry = computers.get(paired["id"])
        for wrong in ("0" * 64, ""):
            with pytest.raises(RemoteError, match="ghép lại"):
                remote_books._request(remote_books._base({**entry, "fingerprint": wrong}), "GET", "/sync/v1/library", entry["token"])

        # Kẻ giả: cùng địa chỉ Bluetooth nhưng cổng đồng bộ là máy khác, chứng chỉ khác.
        impostor, _ = _sync(library, tmp_path, "Kẻ giả", identity=tls.load_or_create(tmp_path / "gia" / tls.FILE_NAME))
        bluetooth.forget(PHONE)
        fake_phone = FakePhone(impostor.port)
        bluetooth.gateway(PHONE, connect=fake_phone.connect)
        with pytest.raises(RemoteError, match="khác lúc ghép"):
            remote_books._request(remote_books._base(entry), "GET", "/sync/v1/library", entry["token"])
        impostor.stop()
        fake_phone.drop()
    finally:
        sync.stop()
        phone.drop()


def test_a_phone_out_of_reach_gives_the_reason_not_a_wifi_hint(tmp_path: Path) -> None:
    def out_of_reach(address: str) -> socket.socket:
        raise bluetooth.ServiceNotFound("Không thấy ABook trên máy kia qua Bluetooth - thử lại gần hơn")

    bluetooth.gateway(PHONE, connect=out_of_reach)
    entry = {"host": f"bt:{PHONE}", "port": 47630, "fingerprint": "ab" * 32, "token": "t"}
    with pytest.raises(RemoteError, match="thử lại gần hơn"):
        remote_books._request(remote_books._base(entry), "GET", "/sync/v1/library", "t", timeout=5)


# ---- chọn đường: Wi-Fi trước, hỏng thì Bluetooth --------------------------------------------------------------------------


def test_route_choice_matches_the_phones_route_kt() -> None:
    """Cùng bảng ca với RouteTest của điện thoại: LAN thông -> LAN; mọi LAN hỏng / không có LAN -> Bluetooth; chưa biết -> thử
    LAN đầu tiên chưa thử trước."""
    known = {"a:1": None, "b:1": None}.get
    assert route.choose(["a:1"], PHONE, lambda t: True) == route.Choice("a:1", None)
    assert route.choose(["a:1", "b:1"], PHONE, {"a:1": False, "b:1": True}.get) == route.Choice("b:1", None)
    assert route.choose(["a:1", "b:1"], PHONE, {"a:1": False, "b:1": False}.get) == route.Choice(None, PHONE)
    assert route.choose([], PHONE, known) == route.Choice(None, PHONE)
    assert route.choose(["a:1"], PHONE, known) == route.Choice("a:1", None), "chưa biết: lạc quan, cùng Wi-Fi là thường gặp"
    assert route.choose(["a:1"], None, {"a:1": False}.get) == route.Choice("a:1", None), "không có Bluetooth thì vẫn thử LAN"
    assert route.choose([], None, known) == route.Choice(None, None)
    assert route.choose(["a:1", "b:1"], PHONE, {"a:1": False}.get) == route.Choice("b:1", None)


def test_route_probes_in_the_background_and_remembers(monkeypatch) -> None:
    probed: list[str] = []
    gate = threading.Event()

    def probe(target: str) -> bool:
        probed.append(target)
        gate.wait(5)
        return False

    started = time.time()
    first = route.pick(["h:1"], PHONE, probe=probe)
    assert time.time() - started < 1, "pick không chờ mạng"
    assert first == route.Choice("h:1", None), "chưa biết: Wi-Fi trước"
    assert route.pick(["h:1"], PHONE, probe=probe) == first and _eventually(lambda: probed == ["h:1"]), "một lần thử một lúc"
    gate.set()
    assert _eventually(lambda: route.pick(["h:1"], PHONE, probe=probe) == route.Choice(None, PHONE)), "Wi-Fi hỏng: Bluetooth"
    route.mark_up("h:1")
    assert route.pick(["h:1"], PHONE, probe=probe) == route.Choice("h:1", None), "Wi-Fi quay lại"
    # Kết quả cũ hơn FRESH_SECONDS thì thử lại.
    probed.clear()
    route.pick(["h:1"], PHONE, now=time.time() + route.FRESH_SECONDS + 5, probe=lambda target: probed.append(target) or True)
    assert _eventually(lambda: probed == ["h:1"])


def test_a_wifi_that_fails_to_connect_falls_back_to_bluetooth_and_is_remembered(library, tmp_path: Path) -> None:  # noqa: F811
    sync, devices = _sync(library, tmp_path)
    phone = FakePhone(sync.port)
    bluetooth.gateway(PHONE, connect=phone.connect)
    computers = Computers(tmp_path / "nay" / "computers.json")
    try:
        paired = computers.pair(f"bt:{PHONE}", devices.start_pairing()["code"], "Máy tính thử")
        # Cùng máy, ghép tiếp theo đường Wi-Fi giờ đã hỏng: cổng LAN chết, `bt` còn đó.
        entry = {**computers.get(paired["id"]), "host": "127.0.0.1", "port": _free_port(), "bt": PHONE}
        first = remote_books._base(entry)
        assert first.target and first.fallback == PHONE and first.host == "127.0.0.1", "Wi-Fi trước"
        books = json.loads(remote_books._request(first, "GET", "/sync/v1/library", entry["token"]))["books"]
        assert books and phone.connects >= 1, "nối Wi-Fi hỏng -> yêu cầu ấy đi tiếp qua Bluetooth, vẫn đủ"
        second = remote_books._base(entry)
        assert second.bluetooth == PHONE and not second.fallback, "nhớ: lần sau đi thẳng Bluetooth"
        assert json.loads(remote_books._request(second, "GET", "/sync/v1/library", entry["token"]))["books"]
    finally:
        sync.stop()
        phone.drop()


def test_a_wifi_only_computer_is_untouched_by_all_this(library, tmp_path: Path) -> None:  # noqa: F811
    entry = {"host": "192.168.1.20", "port": 47630, "fingerprint": "ab" * 32, "token": "t"}
    assert remote_books._base(entry) == remote_books.Endpoint("192.168.1.20", 47630, "ab" * 32, target="192.168.1.20:47630")
    assert not bluetooth._gateways and not route._seen, "không Bluetooth, không cổng cục bộ, không luồng thử"


def test_the_bluetooth_address_the_other_side_reports_is_remembered(library, tmp_path: Path) -> None:  # noqa: F811
    """Ghép Wi-Fi với một máy tính khác: lời đáp ghép kể địa chỉ Bluetooth của nó (sync.py `routes`) - ghi lại làm đường lùi."""
    lib, _project, listening = library
    devices = Devices(tmp_path / "kia" / "devices.json")
    app = SyncApp(lib, listening, devices, "Máy kia", routes=lambda: {"lan": ["127.0.0.1"], "port": 0, "bluetooth": PHONE})
    server = SyncServer(app, host="127.0.0.1", port=0).start()
    computers = Computers(tmp_path / "nay" / "computers.json")
    try:
        paired = computers.pair(f"127.0.0.1:{server.port}", devices.start_pairing()["code"], "Máy tính thử")
        entry = computers.get(paired["id"])
        assert entry["bt"] == PHONE and entry["host"] == "127.0.0.1"
        assert "token" not in json.dumps(computers.list()), "giao diện không bao giờ thấy mã thiết bị"
        endpoint = remote_books._base(entry)
        assert endpoint.target == f"127.0.0.1:{server.port}" and endpoint.fallback == PHONE, "Wi-Fi trước, Bluetooth dự phòng"
        remote_books.refresh(tmp_path / "thu_vien", computers)
        assert computers.get(paired["id"])["bt"] == PHONE
    finally:
        server.stop()
        bluetooth.forget(PHONE)
