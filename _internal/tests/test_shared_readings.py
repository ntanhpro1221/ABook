"""Cách đọc dùng chung cho mọi sách (webui/shared_readings.py) - 2026-10-01, chủ sách: "phần studio ưu tiên hơn".

Sửa cách đọc một tên trước đây chỉ có nghĩa trong MỘT cuốn. Đánh dấu "dùng cho mọi sách" thì sách mới có từ ấy tự nhận cách
đọc lúc tạo, sách có sẵn thì bấm "Dùng cách đọc chung" - qua đúng đường yêu cầu cách đọc của một lần sửa tay."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from abook import listener_overrides
from abook.webui import shared_readings
from abook.webui.shared_readings import SharedReadings


def test_entries_are_checked_like_a_hand_fix_and_kept_by_word(tmp_path: Path) -> None:
    readings = SharedReadings(tmp_path / "shared_readings.json")
    readings.put("Nasdell", "Hên-cơ", source="lo18", now=1.0)
    readings.put("nasdell", "Nát-đen", now=2.0)  # cùng từ (không phân biệt hoa thường): thay, không thêm
    readings.put("Wi-Fi", "oai-phai", now=3.0)
    assert [(entry["surface"], entry["spokenForm"]) for entry in readings.entries()] == [("nasdell", "Nát-đen"),
                                                                                         ("Wi-Fi", "oai-phai")]
    with pytest.raises(ValueError) as multi:
        readings.put("Lucien Evans", "Lu-xi-en")
    assert str(multi.value) == listener_overrides.MULTI_WORD
    with pytest.raises(ValueError) as foreign:
        readings.put("Stayu", "Xờ-taiu")
    assert str(foreign.value) == listener_overrides.NOT_VIETNAMESE
    assert readings.remove("NASDELL") and not readings.remove("Nasdell")
    assert json.loads((tmp_path / "shared_readings.json").read_text(encoding="utf-8"))["entries"].keys() == {"wi-fi"}


def test_a_word_counts_only_as_a_whole_word_in_any_case() -> None:
    entries = [{"surface": "Lucien", "spokenForm": "Lu-xi-en"}, {"surface": "Wi-Fi", "spokenForm": "oai-phai"},
               {"surface": "Gast", "spokenForm": "Gát"}]
    found = shared_readings.present(entries, ["“LUCIEN, đi thôi,” cô nói.", "Mật khẩu wi-fi là gì?", "Luciena không phải."])
    assert [entry["surface"] for entry in found] == ["Lucien", "Wi-Fi"]
    assert shared_readings.present(entries, ["Luciena và Gastly"]) == []


def _app(tmp_path: Path):
    from abook.webui.library import Preferences
    from abook.webui.listening import Listening
    from abook.webui.server import App
    from tests.test_webui_listen_and_sync import FakeRunner

    preferences = Preferences(tmp_path / "prefs" / "preferences.json")
    preferences.update({"libraryRoot": str(tmp_path / "lib")})
    return App(preferences=preferences, runner=FakeRunner(), token="t", listening=Listening(tmp_path / "prefs" / "l.json"))


def test_a_new_book_takes_the_shared_readings_its_text_uses(tmp_path: Path) -> None:
    app = _app(tmp_path)
    app.put_shared_reading({"surface": "Nasdell", "spokenForm": "Hên-cơ"})
    app.put_shared_reading({"surface": "Gast", "spokenForm": "Gát"})
    source = tmp_path / "truyen"
    source.mkdir()
    (source / "001.txt").write_text("Chương 1\n\n“Nasdell đâu rồi?” Lucien hỏi.\n", encoding="utf-8")
    created = app.create({"paths": [str(source / "001.txt")], "title": "Thử", "profile": "high_quality"})
    assert created["sharedReadings"] == ["Nasdell"], "Gast không có trong truyện thì không gieo"
    root = app._book(created["id"])
    requests = listener_overrides.pronunciation_requests(listener_overrides.read_overrides(root))
    assert [(request["surface"], request["spoken_form"]) for request in requests] == [("Nasdell", "Hên-cơ")]
    # Sách có sẵn: xem trước rồi áp - cách đọc đã chờ áp giống hệt thì không hỏi lại.
    assert app.book_shared_readings(created["id"], apply=False)["entries"] == []
    app.put_shared_reading({"surface": "Lucien", "spokenForm": "Lu-xi-en"})
    waiting = app.book_shared_readings(created["id"], apply=False)["entries"]
    assert [(entry["surface"], entry["current"]) for entry in waiting] == [("Lucien", "")]
    assert app.book_shared_readings(created["id"], apply=True) == {"applied": ["Lucien"]}
    assert app.book_shared_readings(created["id"], apply=False)["entries"] == []


def test_a_fix_marked_for_every_book_lands_in_the_shared_list(tmp_path: Path) -> None:
    from abook.webui.server import Server
    from tests.test_webui_listen_and_sync import _request

    app = _app(tmp_path)
    source = tmp_path / "truyen"
    source.mkdir()
    (source / "001.txt").write_text("Chương 1\n\n“Nasdell đâu rồi?”\n", encoding="utf-8")
    created = app.create({"paths": [str(source / "001.txt")], "title": "Thử", "profile": "high_quality"})
    server = Server(app, port=0).start()
    headers = {"X-Ebook-Token": "t"}
    try:
        # Hoàn tác một lần sửa có "Dùng cho mọi sách" gỡ luôn mục chung (soát UX 01-10).
        status, data, _ = _request(server.port, "POST", f"/api/books/{created['id']}/pronunciation",
                                   body={"surface": "Nasdell", "spokenForm": "Nát-đen", "everywhere": True}, headers=headers)
        assert status == 200 and [entry["spokenForm"] for entry in app.shared_readings.entries()] == ["Nát-đen"]
        undo = {"surface": "Nasdell", "withdraw": True, "requestedAt": json.loads(data)["requestedAt"], "previous": "",
                "keep": False, "shared": "Nát-đen"}
        status, _data, _ = _request(server.port, "POST", f"/api/books/{created['id']}/pronunciation", body=undo,
                                    headers=headers)
        assert status == 200 and app.shared_readings.entries() == []
        status, _data, _ = _request(server.port, "POST", f"/api/books/{created['id']}/pronunciation",
                                    body={"surface": "Nasdell", "spokenForm": "Hên-cơ", "everywhere": True}, headers=headers)
        assert status == 200
        status, data, _ = _request(server.port, "GET", "/api/readings", headers=headers)
        entries = json.loads(data)["entries"]
        assert status == 200 and [(entry["surface"], entry["spokenForm"], entry["from"]) for entry in entries] == [
            ("Nasdell", "Hên-cơ", "Thử")]
        status, data, _ = _request(server.port, "POST", "/api/readings", body={"surface": "Stayu", "spokenForm": "Xờ-taiu"},
                                   headers=headers)
        assert status == 400, "cách đọc không phải âm tiết tiếng Việt bị từ chối như khi sửa trong sách"
        status, data, _ = _request(server.port, "POST", "/api/readings", body={"surface": "Nasdell", "remove": True},
                                   headers=headers)
        assert status == 200 and json.loads(data) == {"removed": True}
    finally:
        server.stop()
