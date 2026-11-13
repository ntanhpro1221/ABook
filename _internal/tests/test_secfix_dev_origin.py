"""Soát bảo mật 12-11 (lỗi 3): `python -m abook.webui --dev` không có mã phiên - trang web lạ mở trong trình duyệt từng POST được
vào máy chủ giao diện (simple request `text/plain`, không preflight). Nay ở MỌI chế độ: `_body` chỉ nhận application/json, và yêu cầu
mang `Origin` / `Sec-Fetch-Site` của trang khác bị từ chối trước khi tới tuyến nào."""
from __future__ import annotations

import http.client
import json
from pathlib import Path

import pytest

from abook.webui import __main__ as webui_main


def _server(tmp_path: Path, token: str | None):
    from abook.webui.actions import FakeRunner
    from abook.webui.library import Preferences
    from abook.webui.listening import Listening
    from abook.webui.server import App, Server

    preferences = Preferences(tmp_path / "prefs" / "preferences.json")
    preferences.update({"libraryRoot": str(tmp_path / "lib")})
    app = App(preferences=preferences, runner=FakeRunner(), token=token, listening=Listening(tmp_path / "prefs" / "listening.json"))
    calls: list[str] = []
    app.open_book_file = lambda path, **_kw: calls.append(path) or {"id": "x", "how": "new"}  # type: ignore[method-assign]
    return Server(app, port=0).start(), calls


def _post(port: int, body: bytes, headers: dict[str, str]) -> tuple[int, dict]:
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    try:
        connection.request("POST", "/api/listen/open-book-file", body=body, headers={"Host": f"127.0.0.1:{port}", **headers})
        response = connection.getresponse()
        return response.status, json.loads(response.read() or b"{}")
    finally:
        connection.close()


ATTACK = json.dumps({"path": r"\\attacker\s\x.abook"}).encode()


@pytest.mark.parametrize("token", [None, "t"])
def test_an_empty_plain_text_post_is_also_refused(tmp_path, token):
    server, calls = _server(tmp_path, token)
    try:
        status, _ = _post(server.port, b"", {"Content-Type": "text/plain", **({"X-Ebook-Token": token} if token else {})})
        assert status == 415
        assert calls == []
    finally:
        server.stop()


@pytest.mark.parametrize("token", [None, "t"])
@pytest.mark.parametrize("headers,status", [
    ({"Content-Type": "text/plain;charset=UTF-8"}, 415),  # fetch(..., {mode: "no-cors", body: "..."}): không preflight
    ({"Content-Type": "application/x-www-form-urlencoded"}, 415),
    ({}, 415),
    ({"Content-Type": "application/json", "Origin": "https://evil.example"}, 403),
    ({"Content-Type": "application/json", "Origin": "null"}, 403),
    ({"Content-Type": "application/json", "Origin": "http://127.0.0.1:1"}, 403),  # cổng khác của cùng máy là trang khác
    ({"Content-Type": "application/json", "Sec-Fetch-Site": "cross-site"}, 403),
    ({"Content-Type": "application/json", "Sec-Fetch-Site": "same-site"}, 403),
    ({"Content-Type": "text/plain", "Origin": "https://evil.example", "Sec-Fetch-Site": "cross-site"}, 403),
])
def test_a_foreign_page_cannot_post_to_the_ui_server(tmp_path: Path, token: str | None, headers: dict, status: int) -> None:
    server, calls = _server(tmp_path, token)
    try:
        auth = {"X-Ebook-Token": token} if token else {}
        got, data = _post(server.port, ATTACK, {**auth, **headers})
    finally:
        server.stop()
    assert got == status and data.get("error")
    assert calls == []


@pytest.mark.parametrize("token", [None, "t"])
@pytest.mark.parametrize("extra", [
    {},  # không phải trình duyệt (công cụ, Studio từ xa chuyển tiếp)
    {"Sec-Fetch-Site": "same-origin", "Origin": "http://127.0.0.1:{port}"},
    {"Sec-Fetch-Site": "same-origin", "Origin": "http://localhost:{port}"},
    {"Sec-Fetch-Site": "none"},
])
def test_the_ui_itself_still_gets_through(tmp_path: Path, token: str | None, extra: dict) -> None:
    server, calls = _server(tmp_path, token)
    try:
        auth = {"X-Ebook-Token": token} if token else {}
        headers = {key: value.format(port=server.port) for key, value in extra.items()}
        got, _ = _post(server.port, json.dumps({"path": "C:/x.abook"}).encode(),
                       {**auth, "Content-Type": "application/json; charset=utf-8", **headers})
    finally:
        server.stop()
    assert got == 200 and calls == ["C:/x.abook"]


def test_dev_mode_still_has_no_token_but_documents_the_guard() -> None:
    assert "_same_origin" in (webui_main.__doc__ or "")
