"""Mục "Cách đọc tên" của tab Nhân vật (webui/name_readings.py): mọi cách đọc của cuốn sửa được - kể cả tên máy chắc (hộp
việc chỉ hỏi dưới 0,9) và cách người nghe đã ghim (thẻ biến mất khi đã ghim). Mỗi dòng nói đọc thế nào, ai quyết, bao nhiêu
câu, một câu mẫu đã thu, và yêu cầu đang chờ áp."""
from __future__ import annotations

import json
from pathlib import Path

from abook.database import LISTENER_PRONUNCIATION_SOURCE
from abook.listener_overrides import request_pronunciation
from abook.webui.name_readings import name_readings
from tests.test_listener_speakers import _book


def _pronounce(db, surface: str, spoken: str, *, confidence: float = 0.95, source: str = "analysis") -> None:
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO pronunciations(surface,normalized_surface,spoken_form,confidence,source,locked,created_at,updated_at)"
            " VALUES(?,?,?,?,?,?,0,0)",
            (surface, surface.casefold(), spoken, confidence, source, int(source == LISTENER_PRONUNCIATION_SOURCE)),
        )


def test_every_reading_is_listed_with_who_decided_and_how_many_lines(tmp_path: Path) -> None:
    paths, db = _book(tmp_path)
    (paths.root / "take.wav").write_bytes(b"RIFF")  # bản thu thật nằm trong thư mục sách
    _pronounce(db, "Lucien", "Lu-si-en", confidence=0.98)  # máy chắc: hộp việc không bao giờ hỏi
    _pronounce(db, "Natasha", "Na-ta-sa", source=LISTENER_PRONUNCIATION_SOURCE)
    _pronounce(db, "Rhine", "Rai", confidence=0.6)  # tên của chương khác: không câu nào ở phần này

    readings = name_readings(paths.root)

    by_name = {item["surface"]: item for item in readings["items"]}
    assert list(by_name) == ["Lucien", "Natasha"] and readings["unseen"] == 1
    assert by_name["Lucien"]["lines"] == 1 and not by_name["Lucien"]["byListener"]
    assert by_name["Natasha"]["byListener"] and by_name["Natasha"]["requested"] is None
    example = by_name["Lucien"]["example"]
    assert example["text"] == "Lucien nhìn Natasha." and example["hasAudio"]


def test_a_waiting_wish_shows_until_the_book_has_it(tmp_path: Path) -> None:
    paths, db = _book(tmp_path)
    _pronounce(db, "Lucien", "Lu-si-en", confidence=0.98)
    request_pronunciation(paths.root, "Lucien", "Lu-xi-en", now=1.0)
    request_pronunciation(paths.root, "Natasha", "Na-ta-xa", now=1.0)  # tên chưa có dòng nào: người nghe thêm

    by_name = {item["surface"]: item for item in name_readings(paths.root)["items"]}

    assert by_name["Lucien"]["requested"] == "Lu-xi-en" and by_name["Lucien"]["spoken"] == "Lu-si-en"
    assert by_name["Natasha"]["requested"] == "Na-ta-xa" and by_name["Natasha"]["spoken"] == ""
    assert by_name["Natasha"]["lines"] == 1, "đếm câu cả cho tên người nghe vừa thêm"

    db.apply_listener_pronunciation(surface="Lucien", normalized_surface="lucien", spoken_form="Lu-xi-en",
                                    source=LISTENER_PRONUNCIATION_SOURCE)
    lucien = next(item for item in name_readings(paths.root)["items"] if item["surface"] == "Lucien")
    assert lucien["requested"] is None and lucien["byListener"] and lucien["spoken"] == "Lu-xi-en"


def test_keeping_the_machines_reading_is_a_decision_not_a_change(tmp_path: Path) -> None:
    """"Đúng rồi, giữ" trên thẻ hộp việc: chưa áp nhưng không đổi gì - dòng nói "đã chọn", không "chờ áp dụng"."""
    paths, db = _book(tmp_path)
    _pronounce(db, "Lucien", "Lu-si-en", confidence=0.88)
    request_pronunciation(paths.root, "Lucien", "Lu-si-en", now=1.0)

    lucien = name_readings(paths.root)["items"][0]

    assert lucien["requested"] is None and lucien["byListener"]


def test_the_studio_serves_the_list(tmp_path: Path) -> None:
    from abook.webui.library import Preferences, book_id
    from abook.webui.listening import Listening
    from abook.webui.server import App, Server
    from tests.test_webui_listen_and_sync import FakeRunner, _request

    paths, db = _book(tmp_path)
    (paths.root / "book_settings.json").write_text("{}", encoding="utf-8")
    _pronounce(db, "Lucien", "Lu-si-en")
    preferences = Preferences(tmp_path / "prefs" / "preferences.json")
    preferences.update({"libraryRoot": str(tmp_path)})
    app = App(preferences=preferences, runner=FakeRunner(), token="t", listening=Listening(tmp_path / "prefs" / "l.json"))
    server = Server(app, port=0).start()
    try:
        status, data, _ = _request(server.port, "GET", f"/api/books/{book_id(paths.root)}/pronunciations",
                                   headers={"X-Ebook-Token": "t"})
    finally:
        server.stop()
    assert status == 200 and [item["surface"] for item in json.loads(data)["items"]] == ["Lucien"]


def _say(db, stable_id: str, text: str, *, recorded: bool = True) -> None:
    with db.connect() as conn:
        conn.execute("UPDATE segments SET text=?, wav_path=? WHERE stable_id=?", (text, "take.wav" if recorded else None, stable_id))


def test_a_reading_for_any_word_says_which_lines_it_reaches_and_what_it_costs(tmp_path: Path) -> None:
    """Soát UX a23 B11: "TP.HCM" không phải tên nhân vật nhưng sửa được cho cả cuốn; trước khi lưu nói có bao nhiêu câu có chữ ấy,
    bao nhiêu câu đã thu phải thu lại (cách đếm của hộp chọn giọng), ở chương nào, kèm một câu mẫu."""
    from abook.webui.name_readings import reading_reach

    paths, db = _book(tmp_path)
    (paths.root / "take.wav").write_bytes(b"RIFF")
    _say(db, "c1s1", "“Ở TP.HCM nóng lắm.”")
    _say(db, "c1s2", "“Về tp.hcm đi.”", recorded=False)  # không phân biệt hoa thường, nhưng chưa thu
    _say(db, "c1s3", "“TP.HCMX khác.”")  # dính chữ: không phải chữ này

    reach = reading_reach(paths.root, " TP.HCM ")

    assert reach["surface"] == "TP.HCM" and reach["lines"] == 2 and reach["recorded"] == 1
    assert reach["cost"] == "thu lại 1 câu" and reach["blocked"] == 0
    assert [(chapter["lines"], chapter["recorded"]) for chapter in reach["chapters"]] == [(2, 1)]
    assert reach["example"]["text"] == "“Ở TP.HCM nóng lắm.”" and reach["example"]["hasAudio"], "ví dụ ưu tiên câu đã thu"

    nothing_recorded = reading_reach(paths.root, "Natasha")
    assert nothing_recorded["lines"] == 1 and nothing_recorded["recorded"] == 1
    gone = reading_reach(paths.root, "Hà Nội")
    assert gone["lines"] == 0 and gone["cost"] == "chưa thu nên không phải thu lại" and gone["example"] is None


def test_a_symbol_the_voice_pass_rewrites_first_cannot_be_read_by_a_word_reading(tmp_path: Path) -> None:
    """"km/h": trước khi tra cách đọc, dây chuyền đã đổi "/" thành quãng nghỉ ("km, h") (text_processing.spoken_symbols_to_words)
    nên cách đọc cho chữ ấy không bao giờ khớp - nói thẳng thay vì hứa "sẽ thu lại 3 câu"."""
    from abook.webui.name_readings import reading_reach

    paths, db = _book(tmp_path)
    (paths.root / "take.wav").write_bytes(b"RIFF")
    _say(db, "c1s1", "“Chạy 60 km/h thôi.”")

    reach = reading_reach(paths.root, "km/h")

    assert reach["lines"] == 1 and reach["blocked"] == 1
    assert reach["cost"] == "chưa thu nên không phải thu lại", "không câu nào đổi cách đọc nên không câu nào phải thu lại"


def test_the_studio_serves_the_reach_of_a_reading(tmp_path: Path) -> None:
    from abook.webui.library import Preferences, book_id
    from abook.webui.listening import Listening
    from abook.webui.server import App, Server
    from tests.test_webui_listen_and_sync import FakeRunner, _request

    paths, _db = _book(tmp_path)
    (paths.root / "book_settings.json").write_text("{}", encoding="utf-8")
    preferences = Preferences(tmp_path / "prefs" / "preferences.json")
    preferences.update({"libraryRoot": str(tmp_path)})
    app = App(preferences=preferences, runner=FakeRunner(), token="t", listening=Listening(tmp_path / "prefs" / "l.json"))
    server = Server(app, port=0).start()
    try:
        base = f"/api/books/{book_id(paths.root)}/pronunciations/reach"
        status, data, _ = _request(server.port, "GET", base + "?surface=Natasha", headers={"X-Ebook-Token": "t"})
        assert status == 200 and json.loads(data)["lines"] == 1
        status, _data, _ = _request(server.port, "GET", base, headers={"X-Ebook-Token": "t"})
        assert status == 400
    finally:
        server.stop()


def test_a_word_that_is_not_a_plain_word_still_counts_its_lines(tmp_path: Path) -> None:
    """"TP.HCM" người nghe vừa thêm: dòng của nó đếm câu có chữ ấy (khớp nguyên từ như TTS), không luôn là 0 câu."""
    paths, db = _book(tmp_path)
    _say(db, "c1s1", "“Ở TP.HCM nóng lắm.”")
    request_pronunciation(paths.root, "TP.HCM", "Thành-phố Hồ-chí-minh", now=1.0)

    by_name = {item["surface"]: item for item in name_readings(paths.root)["items"]}

    assert by_name["TP.HCM"]["lines"] == 1 and by_name["TP.HCM"]["example"]["text"] == "“Ở TP.HCM nóng lắm.”"
