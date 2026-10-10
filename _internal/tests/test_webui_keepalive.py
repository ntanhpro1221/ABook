"""Máy chủ giao diện giữ kết nối sống (HTTP/1.1): yêu cầu có thân mà handler không đọc (nút Huỷ, "Tải công cụ" - giao diện gửi `{}`) không được làm hỏng
yêu cầu kế tiếp trên cùng kết nối (nó từng nhận 501 "Unsupported method ('{}GET')" - soát xuất sách nói 10-10)."""
from __future__ import annotations

import http.client
import json
from pathlib import Path

from abook.webui.server import Server
from tests.test_project_file import _app

TOKEN = {"X-Ebook-Token": "t", "Content-Type": "application/json"}


def test_an_unread_request_body_does_not_break_the_next_request_on_the_same_connection(tmp_path: Path) -> None:
    server = Server(_app(tmp_path / "studio", tmp_path / "thu_vien"), port=0).start()
    try:
        connection = http.client.HTTPConnection("127.0.0.1", server.port, timeout=20)
        for _round in range(3):
            connection.request("POST", "/api/ffmpeg/cancel", body=json.dumps({}), headers=TOKEN)  # handler không đọc thân
            first = connection.getresponse()
            first.read()
            assert first.status == 200
            connection.request("GET", "/api/ffmpeg", headers=TOKEN)
            second = connection.getresponse()
            assert second.status == 200 and "ready" in json.loads(second.read())
        connection.close()
    finally:
        server.stop()
