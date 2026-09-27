"""Hộp "Việc cần anh" (webui/work_items.py, docs/STUDIO_REVIEW.md): chỗ máy nghi ngờ, xếp theo lợi trên mỗi lần bấm.

Project SQLite tối thiểu trong thư mục tạm - chỉ các bảng/cột mà bộ dựng việc đọc.
"""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from ebook_reader.webui.work_items import work_items


def make_book(root: Path) -> Path:
    project = root / "sach"
    project.mkdir()
    (project / "book_settings.json").write_text("{}", encoding="utf-8")
    db = sqlite3.connect(project / "project.sqlite3")
    db.executescript(
        """
        CREATE TABLE chapters (id INTEGER PRIMARY KEY, chapter_index INTEGER, title TEXT);
        CREATE TABLE segments (id INTEGER PRIMARY KEY, stable_id TEXT, chapter_id INTEGER, seq INTEGER, text TEXT,
                               kind TEXT, speaker TEXT, voice_profile_id INTEGER, canonical_character_id INTEGER,
                               status TEXT, asr_text TEXT, asr_similarity REAL, warning_code TEXT, wav_path TEXT);
        CREATE TABLE characters (id INTEGER PRIMARY KEY, canonical_name TEXT, display_name TEXT, gender TEXT,
                                 locked INTEGER);
        CREATE TABLE pronunciations (surface TEXT, spoken_form TEXT, confidence REAL, locked INTEGER);
        """
    )
    db.execute("INSERT INTO chapters VALUES (1, 1, '001')")
    db.executemany("INSERT INTO characters VALUES (?,?,?,?,?)", [
        (1, "LUCIEN", "Lucien", "male", 0),
        (2, "HEIDI", "Heidi", "female", 0),
        (3, "ÁO CHOÀNG ĐEN", "Áo choàng đen", "unknown", 0),
        (4, "RHINE", "Rhine", "male", 0),
    ])
    rows = [
        (1, "a", 1, 0, "Chương 1 - Mở đầu", "narration", "NARRATOR", 1, None),
        (2, "b", 1, 1, "“Heidi, các cậu đi đâu vậy?”", "dialogue", "HEIDI", 3, 2),
        (3, "c", 1, 2, "“Đi thôi.”", "dialogue", "LUCIEN", 2, 1),
        (4, "d", 1, 3, "“Ta đến rồi.”", "dialogue", "ÁO CHOÀNG ĐEN", 4, 3),
        (5, "e", 1, 4, "“Ta nữa.”", "dialogue", "ÁO CHOÀNG ĐEN", 4, 3),
        (6, "f", 1, 5, "“Được.”", "dialogue", "RHINE", 2, 4),
        (7, "g", 1, 6, "“Ai đó?”", "dialogue", "NPC_LOCAL::c00001::r1::người gác", 5, None),
        (8, "h", 1, 7, "Hailkes bước tới, Hailkes cười.", "narration", "NARRATOR", 1, None),
    ]
    db.executemany(
        "INSERT INTO segments (id, stable_id, chapter_id, seq, text, kind, speaker, voice_profile_id,"
        " canonical_character_id, status) VALUES (?,?,?,?,?,?,?,?,?, 'verified')",
        rows,
    )
    db.execute("INSERT INTO pronunciations VALUES ('Hailkes', 'Hain', 0.72, 1)")
    db.execute("INSERT INTO pronunciations VALUES ('Lucien', 'Lu-xi-ên', 0.99, 1)")
    db.commit()
    db.close()
    return project


def test_the_inbox_finds_each_kind_of_doubt_and_ranks_by_benefit(tmp_path: Path) -> None:
    started = time.time()
    view = work_items(make_book(tmp_path))
    kinds = {item["kind"]: item for item in view["items"]}
    assert kinds["vocative"]["examples"][0]["text"].startswith("“Heidi,"), "người được gọi không phải người nói"
    assert kinds["gender"]["title"].casefold().startswith("áo choàng đen") and kinds["gender"]["affected"] == 2
    assert "LUCIEN" not in str(kinds["gender"]), "đã biết giới thì không hỏi"
    shared = kinds["shared-voice"]
    assert "Lucien" in shared["title"] and "Rhine" in shared["title"], "hai người có tên, một giọng, cùng chương"
    assert kinds["unnamed"]["title"].casefold() == "\"người gác\" là ai?"
    pronunciation = kinds["pronunciation"]
    assert pronunciation["affected"] == 1 and "Hain" in pronunciation["title"], "đếm câu chứa tên, không đếm lần nhắc"
    assert not any("Lucien" in item["title"] and item["kind"] == "pronunciation" for item in view["items"]), "0,99 là chắc"
    scores = [item["score"] for item in view["items"]]
    assert scores == sorted(scores, reverse=True), "xếp theo lợi trên mỗi lần bấm"
    assert time.time() - started < 5


def test_the_second_scorer_flags_only_confident_disagreements_on_current_labels(tmp_path: Path) -> None:
    """doubt.json (doubt_for_book.py): bộ chấm chắc một người có tên KHÁC nhãn LLM -> việc "Ai nói câu này?". Đồng ý, không
    chắc, hay nhãn đã đổi từ sau lần chấm (dây chuyền phân tích lại) thì không làm phiền người nghe."""
    project = make_book(tmp_path)
    (project / "doubt.json").write_text(json.dumps({"segments": {
        "c": {"llm": "LUCIEN", "choice": "RHINE", "certainty": 0.91, "top": [["RHINE", 0.91], ["LUCIEN", 0.05]],
              "disagree": True},
        "f": {"llm": "RHINE", "choice": "RHINE", "certainty": 0.97, "top": [["RHINE", 0.97]], "disagree": False},
        "d": {"llm": "ÁO CHOÀNG ĐEN", "choice": "LUCIEN", "certainty": 0.3, "top": [["LUCIEN", 0.3]], "disagree": True},
        "b": {"llm": "LUCIEN", "choice": "RHINE", "certainty": 0.95, "top": [["RHINE", 0.95]], "disagree": True},
    }}), encoding="utf-8")
    speakers = [item for item in work_items(project)["items"] if item["kind"] == "speaker"]
    assert [item["key"] for item in speakers] == ["speaker:c"], "chỉ bất đồng chắc trên đúng nhãn đang dùng"
    item = speakers[0]
    assert item["current"] == "Lucien" and item["options"][:2] == ["Rhine", "Lucien"] and "Người kể" in item["options"]


def test_a_pronunciation_card_has_lines_to_hear_and_shows_a_waiting_request(tmp_path: Path) -> None:
    """Bước 2: người nghe nghe máy đang đọc tên thế nào (câu đã thu trước), sửa ngay trên thẻ; mong muốn chưa áp thì thẻ
    nói "đang chờ" thay vì im lặng như chưa sửa."""
    from ebook_reader.listener_overrides import request_pronunciation

    project = make_book(tmp_path)
    db = sqlite3.connect(project / "project.sqlite3")
    db.execute("UPDATE segments SET wav_path='chunks/8.wav' WHERE id=8")
    db.commit()
    db.close()
    card = next(item for item in work_items(project)["items"] if item["kind"] == "pronunciation")
    assert card["surface"] == "Hailkes" and card["requested"] is None
    assert card["examples"][0]["text"].startswith("Hailkes") and card["examples"][0]["hasAudio"] is True

    request_pronunciation(project, "Hailkes", "Hên-khơ", now=time.time())
    card = next(item for item in work_items(project)["items"] if item["kind"] == "pronunciation")
    assert card["requested"] == "Hên-khơ", "dây chuyền chưa áp: thẻ vẫn đó, kèm cách đọc đang chờ"


def test_the_studio_writes_the_request_and_refuses_a_reading_the_voice_cannot_say(tmp_path: Path) -> None:
    """Giao diện không ghi SQLite của sách: chỉ ghi overrides.json. Cách đọc không phải âm tiết tiếng Việt bị từ chối NGAY,
    kèm lý do đọc được - không để tới ranh giới chương mới lặng lẽ bỏ qua."""
    from ebook_reader.listener_overrides import pronunciation_requests, read_overrides
    from ebook_reader.webui.library import Preferences, book_id
    from ebook_reader.webui.listening import Listening
    from ebook_reader.webui.server import App, Server
    from tests.test_webui_listen_and_sync import FakeRunner, _request

    project = make_book(tmp_path)
    preferences = Preferences(tmp_path / "prefs" / "preferences.json")
    preferences.update({"libraryRoot": str(tmp_path)})
    app = App(preferences=preferences, runner=FakeRunner(), token="t", listening=Listening(tmp_path / "prefs" / "l.json"))
    server = Server(app, port=0).start()
    headers = {"X-Ebook-Token": "t"}
    path = f"/api/books/{book_id(project)}/pronunciation"
    before = (project / "project.sqlite3").read_bytes()
    try:
        status, data, _ = _request(server.port, "POST", path, headers=headers,
                                   body={"surface": "Hailkes", "spokenForm": " Hên-khơ "})
        assert status == 200 and json.loads(data)["spokenForm"] == "Hên-khơ"
        assert pronunciation_requests(read_overrides(project)) == [{"surface": "Hailkes", "spoken_form": "Hên-khơ"}]
        status, data, _ = _request(server.port, "POST", path, headers=headers,
                                   body={"surface": "Hailkes", "spokenForm": "Hlkx"})
        assert status == 400 and "âm tiết tiếng Việt" in json.loads(data)["error"]
        status, data, _ = _request(server.port, "POST", path, headers=headers,
                                   body={"surface": "Lucien Evans", "spokenForm": "Lu-si-en"})
        assert status == 400 and "MỘT từ" in json.loads(data)["error"]
    finally:
        server.stop()
    assert (project / "project.sqlite3").read_bytes() == before, "chỉ dây chuyền được ghi SQLite của sách"
