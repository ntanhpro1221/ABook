"""Lời báo khi không nối được máy kia nói đúng chuyện (soát a27 lỗi 9): gõ nhầm cổng (cổng giao diện, phần mềm khác) không phải
"máy tắt"; máy còn đó mà ABook bên kia đóng cũng không phải "máy tắt"."""
from __future__ import annotations

import http.server
import socket
import threading
from pathlib import Path

import pytest

from abook.webui import remote_books
from abook.webui.server import ApiError
from tests.test_sync_tls_pinning import _this_computer


def test_a_port_that_is_not_abooks_says_so_not_that_the_machine_is_off(tmp_path: Path) -> None:
    plain = http.server.ThreadingHTTPServer(("127.0.0.1", 0), http.server.SimpleHTTPRequestHandler)
    threading.Thread(target=plain.serve_forever, daemon=True).start()
    app = _this_computer(tmp_path)
    try:
        with pytest.raises(ApiError) as caught:
            app.pair_computer(f"127.0.0.1:{plain.server_address[1]}", "123456")
        assert str(caught.value) == remote_books.NOT_ABOOK, caught.value
    finally:
        plain.shutdown()
        plain.server_close()


def test_nothing_listening_on_the_port_says_abook_is_not_open_there(tmp_path: Path) -> None:
    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    free = probe.getsockname()[1]
    probe.close()
    with pytest.raises(ApiError) as caught:
        _this_computer(tmp_path).pair_computer(f"127.0.0.1:{free}", "123456")
    assert str(caught.value) == remote_books.REFUSED, caught.value


def test_silence_is_still_the_machine_not_answering() -> None:
    endpoint = remote_books.Endpoint("192.0.2.1", 1, "ab" * 32)
    assert remote_books._unreachable(endpoint, TimeoutError()) == remote_books.UNREACHABLE
    assert remote_books._unreachable(endpoint, None) == remote_books.UNREACHABLE


@pytest.mark.parametrize("error, steps", [
    (TimeoutError(), ("mở ABook", "cùng Wi-Fi", remote_books.SYNC_SWITCH)),
    (ConnectionRefusedError(), ("mở ABook", remote_books.SYNC_SWITCH, "chép lại địa chỉ ghép")),
])
def test_network_help_keeps_the_known_computers_name(monkeypatch, error, steps) -> None:
    endpoint = remote_books.Endpoint("192.0.2.1", 1, "ab" * 32)
    monkeypatch.setattr(remote_books, "_peer_name", lambda _endpoint: "Máy thử A")
    message = remote_books._unreachable(endpoint, error)
    assert "máy thử A" in message and "máy kia" not in message
    assert all(step in message for step in steps)
