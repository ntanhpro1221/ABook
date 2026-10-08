"""Điện thoại đang ngủ (webui/remote_books.py `_Wait`, đo thật 08-10): ColorOS đóng băng ABook ~30 giây sau khi rời màn hình.
Hệ điều hành vẫn nhận kết nối nhưng app không bắt tay TLS tới khi nó dậy (Wi-Fi ~19 giây, Bluetooth có khi 224 giây). Ở đây
một "cửa đóng băng" đứng trước cổng đồng bộ thật: nhận kết nối ngay (như hệ điều hành) mà chỉ chuyển byte khi đã "dậy"."""
from __future__ import annotations

import socket
import threading
import time
from pathlib import Path

import pytest

from abook.webui import bluetooth, remote_books, route
from abook.webui.remote_books import Computers, RemoteError
from tests.test_bluetooth_desktop_client import PHONE, FakePhone, _clean_routes, _sync  # noqa: F401 - fixture dùng chung
from tests.test_webui_listen_and_sync import library  # noqa: F401 - fixture dùng chung


class FrozenApp:
    """Cổng TCP đứng trước cổng đồng bộ: kết nối nào cũng được nhận, nhưng chỉ nối thông khi `thaw()` - app bị đóng băng."""

    def __init__(self, target: int) -> None:
        self.target = target
        self.awake = threading.Event()
        self.awake.set()
        self.server = socket.create_server(("127.0.0.1", 0))
        self.port = self.server.getsockname()[1]
        threading.Thread(target=self._accept, daemon=True).start()

    def freeze(self) -> None:
        self.awake.clear()

    def thaw(self) -> None:
        self.awake.set()

    def _accept(self) -> None:
        while True:
            try:
                client, _ = self.server.accept()
            except OSError:
                return
            threading.Thread(target=self._carry, args=(client,), daemon=True).start()

    def _carry(self, client: socket.socket) -> None:
        self.awake.wait()
        try:
            upstream = socket.create_connection(("127.0.0.1", self.target))
        except OSError:
            client.close()
            return
        for source, sink in ((client, upstream), (upstream, client)):
            threading.Thread(target=self._pipe, args=(source, sink), daemon=True).start()

    @staticmethod
    def _pipe(source: socket.socket, sink: socket.socket) -> None:
        try:
            while data := source.recv(65536):
                sink.sendall(data)
        except OSError:
            pass
        for sock in (source, sink):
            bluetooth._close_socket(sock)

    def close(self) -> None:
        self.server.close()


@pytest.fixture(autouse=True)
def _quick(monkeypatch):
    monkeypatch.setattr(remote_books, "SLEEPY_SECONDS", 0.3)
    remote_books._quiet.clear()
    yield
    remote_books._quiet.clear()


def _eventually(check, timeout: float = 5.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if check():
            return True
        time.sleep(0.03)
    return check()


def _view(computers: Computers, computer: str) -> dict:
    """Máy ấy như giao diện thấy (computers.list: có `waking` khi đang chờ nó dậy)."""
    return next(item for item in computers.list() if item["id"] == computer)


def _paired_over_wifi(library, tmp_path: Path):  # noqa: F811
    sync, devices = _sync(library, tmp_path)
    frozen = FrozenApp(sync.port)
    computers = Computers(tmp_path / "nay" / "computers.json")
    computer = computers.pair(f"127.0.0.1:{frozen.port}", devices.start_pairing()["code"], "Máy tính thử")["id"]
    return sync, frozen, computers, computer


def _refresh_in_background(tmp_path: Path, computers: Computers, *, asked: bool = True):
    result: dict = {}
    worker = threading.Thread(target=lambda: result.update(remote_books.refresh(tmp_path / "thu_vien", computers, asked=asked)),
                              daemon=True)
    worker.start()
    return worker, result


def test_a_sleeping_phone_is_waited_for_and_said_so(library, tmp_path: Path, monkeypatch) -> None:  # noqa: F811
    monkeypatch.setattr(remote_books, "WAKE_WIFI_SECONDS", 20)
    sync, frozen, computers, computer = _paired_over_wifi(library, tmp_path)
    try:
        frozen.freeze()
        worker, result = _refresh_in_background(tmp_path, computers)
        assert _eventually(lambda: "waking" in _view(computers, computer)), "Wi-Fi đã nối mà chưa bắt tay: đang ngủ"
        waking = _view(computers, computer)["waking"]
        assert waking["via"] == "wifi" and waking["until"] - waking["since"] == 20
        time.sleep(1.0)
        assert worker.is_alive(), "không báo lỗi sớm"
        frozen.thaw()  # người dùng mở ABook trên điện thoại
        worker.join(10)
        assert result == {computer: {"books": 1}}
        view = _view(computers, computer)
        assert "waking" not in view and view["error"] == ""
    finally:
        frozen.close()
        sync.stop()


def test_waiting_runs_out_with_a_plain_message_and_wifi_is_not_blamed(library, tmp_path: Path, monkeypatch) -> None:  # noqa: F811
    monkeypatch.setattr(remote_books, "WAKE_WIFI_SECONDS", 1.5)
    sync, frozen, computers, computer = _paired_over_wifi(library, tmp_path)
    try:
        frozen.freeze()
        started = time.monotonic()
        assert remote_books.refresh(tmp_path / "thu_vien", computers, asked=True) == {computer: {"error": remote_books.STILL_ASLEEP}}
        assert 1.4 < time.monotonic() - started < 5
        assert _view(computers, computer)["error"] == remote_books.STILL_ASLEEP
        assert route._seen.get(f"127.0.0.1:{frozen.port}", (True, 0))[0] is not False, "Wi-Fi thông, chỉ app đang ngủ"
        # Lần hỏi nền ngay sau đó không chờ lại (không giữ sóng / pin), người dùng bấm hỏi lại thì chờ.
        assert remote_books.refresh(tmp_path / "thu_vien", computers) == {}
        frozen.thaw()
        assert remote_books.refresh(tmp_path / "thu_vien", computers, asked=True) == {computer: {"books": 1}}
    finally:
        frozen.close()
        sync.stop()


def test_the_listener_can_stop_waiting(library, tmp_path: Path, monkeypatch) -> None:  # noqa: F811
    monkeypatch.setattr(remote_books, "WAKE_WIFI_SECONDS", 60)
    sync, frozen, computers, computer = _paired_over_wifi(library, tmp_path)
    try:
        frozen.freeze()
        worker, result = _refresh_in_background(tmp_path, computers)
        assert _eventually(lambda: "waking" in _view(computers, computer))
        started = time.monotonic()
        remote_books.stop_waiting(computer)
        worker.join(5)
        assert not worker.is_alive() and time.monotonic() - started < 2, "thôi chờ là thôi ngay"
        assert result == {computer: {"error": remote_books.STOPPED_WAITING}}
        assert "waking" not in _view(computers, computer)
    finally:
        frozen.thaw()
        frozen.close()
        sync.stop()


def test_quick_questions_still_fail_fast(library, tmp_path: Path) -> None:  # noqa: F811
    """Hỏi trình phát, gửi chỗ nghe... không chờ điện thoại dậy - chỉ thư viện chờ."""
    sync, frozen, computers, computer = _paired_over_wifi(library, tmp_path)
    try:
        frozen.freeze()
        started = time.monotonic()
        with pytest.raises(RemoteError):
            remote_books.player(computers.get(computer), timeout=1.0)
        assert time.monotonic() - started < 3
        assert "waking" not in _view(computers, computer)
    finally:
        frozen.thaw()
        frozen.close()
        sync.stop()


def test_over_bluetooth_the_wait_starts_once_rfcomm_is_up(library, tmp_path: Path, monkeypatch) -> None:  # noqa: F811
    monkeypatch.setattr(remote_books, "WAKE_BLUETOOTH_SECONDS", 30)
    sync, devices = _sync(library, tmp_path)
    frozen = FrozenApp(sync.port)
    phone = FakePhone(frozen.port)  # RFCOMM giả: kết nối nằm chờ ở "hệ điều hành" điện thoại như máy thật
    bluetooth.gateway(PHONE, connect=phone.connect)
    computers = Computers(tmp_path / "nay" / "computers.json")
    try:
        computer = computers.pair(f"bt:{PHONE}", devices.start_pairing()["code"], "Máy tính thử")["id"]
        frozen.freeze()
        worker, result = _refresh_in_background(tmp_path, computers)
        assert _eventually(lambda: "waking" in _view(computers, computer))
        waking = _view(computers, computer)["waking"]
        assert waking["via"] == "bluetooth" and waking["until"] - waking["since"] == 30
        frozen.thaw()
        worker.join(10)
        assert result == {computer: {"books": 1}}
    finally:
        frozen.thaw()
        frozen.close()
        sync.stop()
        phone.drop()
