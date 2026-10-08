"""Điện thoại Android 8+ không báo được địa chỉ Bluetooth của chính nó, nên máy tính tự tìm trong thiết bị đã ghép ở Windows
(webui/bluetooth.py `paired_devices`, bthprops.cpl) - theo tên máy đã ghép Wi-Fi, hay người dùng chọn một lần. Cấu trúc
BLUETOOTH_DEVICE_INFO dựng giả; không chạm Bluetooth thật."""
from __future__ import annotations

import ctypes
import json
import time
from pathlib import Path

import pytest

from abook.webui import bluetooth, remote_books
from abook.webui.remote_books import Computers, RemoteError
from tests.test_bluetooth_desktop_client import (  # noqa: F401 - fixture + bộ giả dùng chung
    PHONE, FakePhone, _clean_routes, _eventually, _free_port, _sync)
from tests.test_webui_listen_and_sync import library  # noqa: F401


class FakeBthprops:
    """Thay bthprops.cpl: mỗi phần tử là (tên, địa chỉ số, lớp thiết bị)."""

    def __init__(self, devices: list[tuple[str, int, int]]) -> None:
        self.devices, self.index, self.closed, self.params = devices, 0, 0, None

    def _fill(self, info) -> None:
        name, address, device_class = self.devices[self.index]
        info._obj.szName, info._obj.address, info._obj.ulClassofDevice = name, address, device_class

    def BluetoothFindFirstDevice(self, params, info):  # noqa: N802
        self.params = params._obj
        if not self.devices:
            return 0
        self._fill(info)
        return 1

    def BluetoothFindNextDevice(self, handle, info):  # noqa: N802
        self.index += 1
        if self.index >= len(self.devices):
            return 0
        self._fill(info)
        return 1

    def BluetoothFindDeviceClose(self, handle):  # noqa: N802
        self.closed += 1


PHONE_CLASS, COMPUTER_CLASS, HEADSET_CLASS = 0x5A020C, 0x6C010C, 0x240404


def test_paired_devices_are_listed_from_the_structures_windows_fills_in() -> None:
    assert ctypes.sizeof(bluetooth._BLUETOOTH_DEVICE_INFO) == 560 and ctypes.sizeof(bluetooth._SYSTEMTIME) == 16
    assert ctypes.sizeof(bluetooth._BLUETOOTH_DEVICE_SEARCH_PARAMS) == (40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28)
    assert bluetooth.address_text(0xAABBCCDDEEFF) == PHONE and bluetooth.address_text(0x1) == "00:00:00:00:00:01"
    fake = FakeBthprops([("Galaxy của An", 0xAABBCCDDEEFF, PHONE_CLASS), ("Tai nghe", 0x112233445566, HEADSET_CLASS),
                         ("Máy bàn", 0x665544332211, COMPUTER_CLASS)])
    devices = bluetooth.paired_devices(dll=fake)
    assert devices == [{"name": "Galaxy của An", "address": PHONE, "kind": "phone"},
                       {"name": "Máy bàn", "address": "66:55:44:33:22:11", "kind": "computer"}], "bỏ tai nghe, loa"
    assert fake.closed == 1, "luôn đóng lượt tìm"
    assert fake.params.fReturnAuthenticated and fake.params.fReturnRemembered and not fake.params.fIssueInquiry, \
        "chỉ đọc danh sách đã ghép, không dò sóng"
    assert bluetooth.paired_devices(dll=FakeBthprops([])) == [], "chưa ghép gì / không có card"


def test_a_phone_is_matched_by_its_name_and_never_guessed() -> None:
    devices = [{"name": "Galaxy của An", "address": PHONE, "kind": "phone"},
               {"name": "Galaxy của Bình", "address": "01:02:03:04:05:06", "kind": "phone"},
               {"name": "Máy bàn", "address": "66:55:44:33:22:11", "kind": "computer"},
               {"name": "Máy bàn", "address": "66:55:44:33:22:12", "kind": "computer"}]
    assert bluetooth.match_by_name("  galaxy  CỦA an ", devices) == PHONE
    assert bluetooth.match_by_name("Máy bàn", devices) == "", "hai máy cùng tên: không đoán"
    assert bluetooth.match_by_name("Không có", devices) == "" and bluetooth.match_by_name("", devices) == ""
    phone_first = devices + [{"name": "Galaxy của An", "address": "0A:0B:0C:0D:0E:0F", "kind": "computer"}]
    assert bluetooth.match_by_name("Galaxy của An", phone_first) == PHONE, "trùng tên thì ưu tiên điện thoại"


def _wifi_entry_of_the_phone(computers: Computers, phone: FakePhone, devices) -> str:
    """Máy đã ghép qua Wi-Fi mà Wi-Fi giờ hỏng (cổng chết) và chưa biết địa chỉ Bluetooth."""
    paired = computers.pair(f"bt:{PHONE}", devices.start_pairing()["code"], "Máy tính thử")
    computers.note(paired["id"], host="127.0.0.1", port=_free_port(), name="Điện thoại")
    return paired["id"]


def test_when_wifi_fails_the_phone_is_found_among_the_paired_devices_by_name(library, tmp_path: Path, monkeypatch) -> None:  # noqa: F811
    sync, devices = _sync(library, tmp_path)
    phone = FakePhone(sync.port)
    bluetooth.gateway(PHONE, connect=phone.connect)
    computers = Computers(tmp_path / "nay" / "computers.json")
    monkeypatch.setattr(remote_books, "_COMPUTERS", computers)
    monkeypatch.setattr(remote_books, "_looked", {})
    monkeypatch.setattr(bluetooth, "paired_devices", lambda: [{"name": "điện thoại", "address": PHONE, "kind": "phone"}])
    try:
        key = _wifi_entry_of_the_phone(computers, phone, devices)
        entry = computers.get(key)
        assert "bt" not in entry and remote_books._bluetooth_of(entry) == ""
        with pytest.raises(RemoteError, match="Wi-Fi"):
            remote_books._request(remote_books._base(entry), "GET", "/sync/v1/library", entry["token"])
        assert _eventually(lambda: computers.get(key).get("bt") == PHONE), "tìm ra theo tên, ghi vào computers.json"
        entry = computers.get(key)
        assert "token" not in json.dumps(computers.list())
        books = json.loads(remote_books._request(remote_books._base(entry), "GET", "/sync/v1/library", entry["token"]))["books"]
        assert books, "lần sau đi thẳng Bluetooth"
        assert remote_books._base(entry).bluetooth == PHONE
    finally:
        sync.stop()
        phone.drop()


def test_the_bluetooth_name_the_phone_reports_is_matched_before_its_wifi_name(library, tmp_path: Path, monkeypatch) -> None:  # noqa: F811
    """Windows lưu tên Bluetooth người dùng đặt ("Pixel của An"), điện thoại báo ở Wi-Fi tên máy ("OPPO CPH2121"): lời ghép mang
    thêm `bluetoothName`, máy tính khớp theo tên ấy trước, tên máy sau."""
    sync, devices = _sync(library, tmp_path)
    phone = FakePhone(sync.port)
    bluetooth.gateway(PHONE, connect=phone.connect)
    computers = Computers(tmp_path / "nay" / "computers.json")
    monkeypatch.setattr(remote_books, "_COMPUTERS", computers)
    monkeypatch.setattr(remote_books, "_looked", {})
    monkeypatch.setattr(bluetooth, "paired_devices", lambda: [
        {"name": "Pixel của An", "address": PHONE, "kind": "phone"},
        {"name": "OPPO CPH2121", "address": "01:02:03:04:05:06", "kind": "phone"}])
    exchange = remote_books._exchange

    def with_bluetooth_name(endpoint, method, path, token, body=None, timeout=remote_books.TIMEOUT):
        reply, seen = exchange(endpoint, method, path, token, body, timeout)
        if path == "/sync/v1/pair":
            reply = json.dumps({**json.loads(reply), "bluetoothName": "  Pixel  của An "}).encode("utf-8")
        return reply, seen

    monkeypatch.setattr(remote_books, "_exchange", with_bluetooth_name)
    try:
        key = _wifi_entry_of_the_phone(computers, phone, devices)
        assert computers.get(key)["btName"] == "Pixel của An", "ghi tên Bluetooth điện thoại báo (gọn khoảng trắng)"
        entry = computers.get(key)
        with pytest.raises(RemoteError, match="Wi-Fi"):
            remote_books._request(remote_books._base(entry), "GET", "/sync/v1/library", entry["token"])
        assert _eventually(lambda: computers.get(key).get("bt") == PHONE), "khớp tên Bluetooth, không phải tên máy"
    finally:
        sync.stop()
        phone.drop()


def test_without_a_bluetooth_name_the_wifi_name_still_matches_and_odd_values_are_ignored() -> None:
    assert remote_books._bluetooth_name({"bluetoothName": " Pixel   của An "}) == "Pixel của An"
    assert remote_books._bluetooth_name({"bluetoothName": "x" * 200}) == "x" * 80
    for odd in ({}, {"bluetoothName": 5}, {"bluetoothName": None}, [], "Pixel"):
        assert remote_books._bluetooth_name(odd) == ""


def test_no_matching_name_leaves_the_error_alone_and_the_search_is_throttled(library, tmp_path: Path, monkeypatch) -> None:  # noqa: F811
    sync, devices = _sync(library, tmp_path)
    phone = FakePhone(sync.port)
    bluetooth.gateway(PHONE, connect=phone.connect)
    computers = Computers(tmp_path / "nay" / "computers.json")
    searches: list[int] = []
    monkeypatch.setattr(remote_books, "_COMPUTERS", computers)
    monkeypatch.setattr(remote_books, "_looked", {})
    monkeypatch.setattr(bluetooth, "paired_devices", lambda: searches.append(1) or [])
    try:
        key = _wifi_entry_of_the_phone(computers, phone, devices)
        entry = computers.get(key)
        for _ in range(3):
            with pytest.raises(RemoteError, match="Wi-Fi"):
                remote_books._request(remote_books._base(entry), "GET", "/sync/v1/library", entry["token"])
        assert _eventually(lambda: len(searches) == 1) and "bt" not in computers.get(key)
        time.sleep(0.2)
        assert len(searches) == 1, "tìm ở nền, mỗi máy không quá hai phút một lần"
    finally:
        sync.stop()
        phone.drop()


def test_the_user_can_pick_the_bluetooth_device_once(library, tmp_path: Path, monkeypatch) -> None:  # noqa: F811
    from abook.webui.library import Preferences
    from abook.webui.listening import Listening
    from abook.webui.server import ApiError, App
    from tests.test_webui_listen_and_sync import FakeRunner

    sync, devices = _sync(library, tmp_path)
    phone = FakePhone(sync.port)
    bluetooth.gateway(PHONE, connect=phone.connect)
    preferences = Preferences(tmp_path / "nay" / "preferences.json")
    preferences.update({"libraryRoot": str(tmp_path / "nay" / "thu_vien")})
    app = App(preferences=preferences, runner=FakeRunner(), token="t", listening=Listening(tmp_path / "nay" / "l.json"))
    monkeypatch.setattr(bluetooth, "paired_devices", lambda: [{"name": "Galaxy", "address": PHONE, "kind": "phone"}])
    try:
        assert app.paired_bluetooth() == {"devices": [{"name": "Galaxy", "address": PHONE, "kind": "phone"}]}
        key = _wifi_entry_of_the_phone(app.computers, phone, devices)
        view = app.set_computer_bluetooth(key, PHONE.lower())
        assert view["computers"][0]["bt"] == PHONE and app.computers.get(key)["bt"] == PHONE
        assert remote_books._base(app.computers.get(key)).fallback == PHONE, "Wi-Fi trước, Bluetooth dự phòng"
        assert "bt" not in app.set_computer_bluetooth(key, "")["computers"][0], "bỏ chọn"
        with pytest.raises(ApiError):
            app.set_computer_bluetooth(key, "khong-phai-dia-chi")
        with pytest.raises(ApiError):
            app.set_computer_bluetooth("0" * 12, PHONE)
    finally:
        sync.stop()
        phone.drop()
