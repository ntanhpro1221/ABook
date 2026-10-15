"""Đổi tên chương (PUT /api/books/<id>/chapters/<n>/title) rồi đọc lại sách ở trang nghe (GET /api/listen/books/<id>): tên mới phải hiện
ngay, không chờ gì - soát UX a34 mục 5 ghi nhận trang không đổi chữ sau khi đổi tên chương."""
from __future__ import annotations

import json
from pathlib import Path

from abook.webui.library import book_id
from tests.test_remote_studio import studio  # noqa: F401 - fixture dùng chung
from tests.test_webui_listen_and_sync import _request, library  # noqa: F401


def _chapters(app, identifier: str) -> list[dict]:
    local = {"X-Ebook-Token": "phien", "Host": f"127.0.0.1:{app.local_port}"}
    status, data, _ = _request(app.local_port, "GET", f"/api/listen/books/{identifier}", headers=local)
    assert status == 200, data
    return json.loads(data)["chapters"]


def test_a_renamed_chapter_comes_back_renamed_from_the_listen_book(studio) -> None:
    app, project = studio
    identifier = book_id(project)
    local = {"X-Ebook-Token": "phien", "Host": f"127.0.0.1:{app.local_port}"}
    before = _chapters(app, identifier)
    assert (before[0]["title"], before[0]["subtitle"]) == ("Chương 646", "Trở về (1)")
    status, data, _ = _request(app.local_port, "PUT", f"/api/books/{identifier}/chapters/1/title", headers=local, body={"title": "Chương Một"})
    assert status == 200, data
    after = _chapters(app, identifier)
    assert after[0]["title"] == "Chương Một", "tên mới hiện ở lần đọc kế tiếp"
    assert after[0]["subtitle"] == "Trở về (1)", "tên phụ giữ nguyên khi chỉ đổi nhãn"
    status, data, _ = _request(app.local_port, "PUT", f"/api/books/{identifier}/chapters/2/title", headers=local, body={"subtitle": "Hết rồi"})
    assert status == 200, data
    again = _chapters(app, identifier)
    assert again[0]["title"] == "Chương Một" and again[1]["subtitle"] == "Hết rồi"
    status, _data, _ = _request(app.local_port, "PUT", f"/api/books/{identifier}/chapters/1/title", headers=local, body={"revert": True})
    assert status == 200 and _chapters(app, identifier)[0]["title"] == "Chương 646"
