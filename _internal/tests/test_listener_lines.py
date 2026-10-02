"""Người nghe sửa CÁCH ĐỌC một câu trong Studio (tab Kịch bản): loại đoạn (kể / thoại / nghĩ), cảm xúc, cường độ.

Studio ghi mong muốn vào `overrides.json` (mục `lines`, mã câu + băm chữ); dây chuyền áp ở ranh giới an toàn bằng
`ProjectDB.apply_listener_line` - đổi và đặt lại câu đã thu trong một transaction - TRƯỚC các yêu cầu "ai nói câu này",
để câu vừa từ lời kể thành lời thoại gán được người nói ngay trong cùng lượt.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from abook.database import ProjectDB
from abook.listener_overrides import (
    BAD_EMOTION,
    BAD_KIND,
    BAD_TEXT,
    SOURCE_CHANGED,
    UNKNOWN_LINE,
    line_requests,
    read_overrides,
    request_line,
)
from tests.test_listener_overrides import _Pipeline
from tests.test_listener_speakers import _book


def _line(db: ProjectDB, stable_id: str) -> dict[str, Any]:
    with db.connect() as conn:
        row = conn.execute(
            "SELECT s.*, v.voice_key, c.canonical_name FROM segments s LEFT JOIN voice_profiles v ON v.id=s.voice_profile_id"
            " LEFT JOIN characters c ON c.id=s.canonical_character_id WHERE s.stable_id=?", (stable_id,)).fetchone()
    return dict(row)


def _apply(db: ProjectDB, stable_id: str, **request: Any):
    return db.apply_listener_line(stable_id=stable_id, text_sha256=request.pop("sha", f"sha-{stable_id}"), **request)


def test_a_new_emotion_is_stored_within_what_the_voice_can_do_and_the_line_is_recorded_again(tmp_path: Path) -> None:
    _paths, db = _book(tmp_path)

    result = _apply(db, "c1s1", emotion="angry", intensity=3)

    line = _line(db, "c1s1")
    assert (line["emotion"], line["intensity"]) == ("angry", 2), "không chấm than: mức 3 hạ về 2 như khâu phân tích"
    assert result is not None and result["reset"] is True and result["previous"]["speaker"] == "Lucien"
    assert line["status"] == "analyzed" and line["wav_path"] is None
    assert _line(db, "c1s2")["status"] == "verified", "câu khác không đổi"
    with db.connect() as conn:
        assert conn.execute("SELECT status FROM chapters").fetchone()[0] == "warning"
        event = conn.execute("SELECT details_json FROM runtime_events WHERE code='LINE_SET_BY_LISTENER'").fetchone()
    assert json.loads(event[0])["emotion"] == "angry"
    assert _apply(db, "c1s1", emotion="angry", intensity=3) is None, "áp lại yêu cầu đã áp: không đổi gì"
    assert _apply(db, "c1s1", emotion="whispering", intensity=2)["intensity"] == 1, "cảm xúc êm tối đa 1"


def test_a_line_that_is_nobodys_words_becomes_narration_in_the_narrators_voice(tmp_path: Path) -> None:
    from abook.character_registry import assert_voice_stability

    _paths, db = _book(tmp_path)

    _apply(db, "c1s2", kind="narration")

    line = _line(db, "c1s2")
    assert (line["kind"], line["speaker"], line["canonical_name"], line["voice_key"]) == (
        "narration", "NARRATOR", "NARRATOR", "narrator")
    assert_voice_stability(db)


def test_narration_turned_into_dialogue_takes_its_speaker_in_the_same_pass(tmp_path: Path) -> None:
    """Lời kể thành lời thoại cần người nói: Studio ghi cả hai trong MỘT lần; dây chuyền áp loại đoạn trước rồi người nói."""
    paths, db = _book(tmp_path)
    request_line(paths.root, "c1s0", "sha-c1s0", kind="dialogue", speaker="NATASHA", now=1.0)
    assert line_requests(read_overrides(paths.root))[0]["kind"] == "dialogue"

    assert _Pipeline(paths, db)._apply_listener_overrides() == {1}

    line = _line(db, "c1s0")
    assert (line["kind"], line["speaker"], line["voice_key"]) == ("dialogue", "NATASHA", "v_natasha")
    assert _Pipeline(paths, db)._apply_listener_overrides() == set(), "lượt sau: không còn gì để áp"


@pytest.mark.parametrize(("stable_id", "request_", "problem"), [
    ("c9s9", {}, UNKNOWN_LINE),
    ("c1s1", {"sha": "sha-khac", "emotion": "sad"}, SOURCE_CHANGED),
    ("c1s1", {"kind": "poem"}, BAD_KIND),
    ("c1s1", {"emotion": "hangry"}, BAD_EMOTION),
])
def test_a_request_that_cannot_apply_changes_nothing(tmp_path: Path, stable_id, request_, problem) -> None:
    _paths, db = _book(tmp_path)

    assert _apply(db, stable_id, **request_) == {"problem": problem}
    assert {str(row["status"]) for row in db.list_segments()} == {"verified"}


def test_a_crash_inside_the_apply_leaves_the_line_as_it_was(tmp_path: Path, monkeypatch) -> None:
    paths, db = _book(tmp_path)

    def crash(self, conn, chapter_id):
        raise RuntimeError("máy tắt giữa transaction")

    monkeypatch.setattr(ProjectDB, "_refresh_chapter_counts_conn", crash)
    with pytest.raises(RuntimeError):
        _apply(db, "c1s1", emotion="sad")
    monkeypatch.undo()

    line = _line(ProjectDB(paths.db), "c1s1")
    assert (line["emotion"] or "neutral", line["status"]) == ("neutral", "verified")


def test_the_script_tab_records_a_delivery_fix_and_shows_it_waiting_then_applied(tmp_path: Path) -> None:
    """Studio: POST /line ghi yêu cầu (từ chối tại chỗ cái dây chuyền sẽ từ chối), KHÔNG ghi SQLite; tab Kịch bản hiện
    cảm xúc/cường độ của câu và yêu cầu "đang chờ" tới khi dây chuyền áp."""
    from abook.config import build_settings, save_settings
    from abook.webui.casting_review import casting_chapter
    from abook.webui.library import Preferences, book_id
    from abook.webui.listening import Listening
    from abook.webui.remote_studio import permitted
    from abook.webui.server import App, Server
    from tests.test_webui_listen_and_sync import FakeRunner, _request

    paths, db = _book(tmp_path)
    save_settings(paths.settings, build_settings())
    preferences = Preferences(tmp_path / "prefs" / "preferences.json")
    preferences.update({"libraryRoot": str(tmp_path)})
    app = App(preferences=preferences, runner=FakeRunner(), token="t", listening=Listening(tmp_path / "prefs" / "l.json"))
    server = Server(app, port=0).start()
    headers = {"X-Ebook-Token": "t"}
    path = f"/api/books/{book_id(paths.root)}/line"
    before = paths.db.read_bytes()
    try:
        status, _data, _ = _request(server.port, "POST", path, headers=headers,
                                    body={"stableId": "c1s1", "textSha256": "sha-c1s1", "emotion": "sad", "intensity": 2})
        assert status == 200
        status, data, _ = _request(server.port, "POST", path, headers=headers,
                                   body={"stableId": "c1s1", "textSha256": "sha-c1s1", "emotion": "hangry"})
        assert status == 400 and "Cảm xúc" in json.loads(data)["error"]
        status, data, _ = _request(server.port, "POST", path, headers=headers,
                                   body={"stableId": "c1s0", "textSha256": "sha-c1s0", "speaker": "NATASHA"})
        assert status == 400 and "Lời kể" in json.loads(data)["error"], "lời kể không có người nói nếu không đổi loại"
        status, _data, _ = _request(server.port, "POST", path, headers=headers,
                                    body={"stableId": "c1s0", "textSha256": "sha-c1s0", "kind": "dialogue",
                                          "speaker": "NATASHA"})
        assert status == 200, "đổi thành lời thoại kèm người nói: hợp lệ trong cùng yêu cầu"
    finally:
        server.stop()
    assert paths.db.read_bytes() == before, "chỉ dây chuyền được ghi SQLite của sách"
    assert permitted("POST", path)

    lines = {line["stableId"]: line for line in casting_chapter(paths.root, 1)["lines"]}
    assert lines["c1s1"]["lineWish"] == {"kind": "", "emotion": "sad", "intensity": 2, "state": "pending"}
    assert lines["c1s0"]["lineWish"]["kind"] == "dialogue" and lines["c1s0"]["wish"]["value"] == "NATASHA"
    assert lines["c1s0"]["wish"]["state"] == "pending", "người nói xét như sau khi câu thành lời thoại, không phải bị từ chối"
    _Pipeline(paths, db)._apply_listener_overrides()
    lines = {line["stableId"]: line for line in casting_chapter(paths.root, 1)["lines"]}
    assert lines["c1s1"]["lineWish"]["state"] == "applied" and lines["c1s1"]["emotion"] == "sad"
    assert (lines["c1s0"]["kind"], lines["c1s0"]["label"]) == ("dialogue", "Natasha")


# ---- chữ đem đọc (STUDIO_REVIEW mục 7: lỗi chữ, cách viết lạ của MỘT câu) ---------------------------------------------


def test_a_reworded_line_is_read_in_the_listeners_words_and_the_book_keeps_its_own(tmp_path: Path) -> None:
    """TTS và phép so của Whisper nhận chữ người nghe sửa; văn bản sách (và đọc theo, băm chữ) giữ nguyên; câu đã thu
    được thu lại. Sửa về đúng chữ của sách là bỏ sửa."""
    from abook.config import build_settings
    from abook.tts import TTSCoordinator

    _paths, db = _book(tmp_path)
    result = _apply(db, "c1s1", spoken="  \u201cĐi   thôi nào.\u201d  ")
    line = _line(db, "c1s1")
    assert line["listener_text"] == "\u201cĐi thôi nào.\u201d" and line["text"] == "\u201cĐi thôi.\u201d"
    assert line["text_sha256"] == "sha-c1s1", "băm chữ của sách không đổi: yêu cầu cũ và đọc theo vẫn khớp"
    assert result is not None and result["reset"] is True and line["status"] == "analyzed" and line["wav_path"] is None
    coordinator = TTSCoordinator(build_settings(), db, lambda _message: None)
    fixed = coordinator.spoken_text({"text": "\u201cĐi thôi nào.\u201d"})
    assert coordinator.spoken_text(line) == fixed != coordinator.spoken_text({"text": line["text"]})

    assert _apply(db, "c1s1", spoken="\u201cĐi thôi nào.\u201d") is None, "áp lại yêu cầu đã áp: không đổi gì"
    assert _apply(db, "c1s1", emotion="sad")["listener_text"] == "\u201cĐi thôi nào.\u201d", "đổi cảm xúc không xoá chữ đã sửa"
    reverted = _apply(db, "c1s1", spoken="")
    assert reverted is not None and reverted["listener_text"] is None and _line(db, "c1s1")["listener_text"] is None
    _apply(db, "c1s1", spoken="Đi thôi nào.")
    assert _apply(db, "c1s1", spoken="\u201cĐi thôi.\u201d")["listener_text"] is None, "sửa về đúng chữ của sách = bỏ sửa"


@pytest.mark.parametrize("spoken", ["\u2026", "Đi\x07 thôi", "x" * 2001, "Đi thôi " * 20],
                         ids=["no-letters", "control-char", "over-cap", "four-times-longer"])
def test_words_that_cannot_be_a_fix_are_refused_and_change_nothing(tmp_path: Path, spoken: str) -> None:
    """Không chữ cái, ký tự điều khiển, quá trần, dài hơn bốn lần câu gốc: sửa chữ chứ không viết lại đoạn văn."""
    _paths, db = _book(tmp_path)
    assert _apply(db, "c1s1", spoken=spoken) == {"problem": BAD_TEXT}
    line = _line(db, "c1s1")
    assert line["listener_text"] is None and line["status"] == "verified"


def test_changing_the_words_keeps_an_emotion_the_pipeline_has_not_applied_yet(tmp_path: Path) -> None:
    """overrides.json là trạng thái mong muốn của cả câu: sửa chữ sau khi chọn cảm xúc (chưa tới ranh giới) giữ cả hai."""
    paths, _db = _book(tmp_path)
    request_line(paths.root, "c1s1", "sha-c1s1", emotion="sad", intensity=2, now=1.0)
    request_line(paths.root, "c1s1", "sha-c1s1", spoken=" Đi  thôi nào. ", now=2.0)
    (request,) = [entry for entry in line_requests(read_overrides(paths.root)) if entry["stable_id"] == "c1s1"]
    assert (request["emotion"], request["intensity"], request["spoken"]) == ("sad", 2, "Đi thôi nào.")
    request_line(paths.root, "c1s1", "sha-c1s1", emotion="happy", now=3.0)
    (request,) = [entry for entry in line_requests(read_overrides(paths.root)) if entry["stable_id"] == "c1s1"]
    assert (request["emotion"], request["spoken"]) == ("happy", "Đi thôi nào.")
    request_line(paths.root, "c1s1", "sha-khac", emotion="angry", now=4.0)
    (request,) = [entry for entry in line_requests(read_overrides(paths.root)) if entry["stable_id"] == "c1s1"]
    assert request["spoken"] is None, "câu gốc đã đổi (băm khác): không mang chữ sửa của câu cũ sang"


def test_the_fix_survives_reopening_and_an_old_book_gains_the_column(tmp_path: Path) -> None:
    """Crash/mở lại: chữ sửa nằm trong SQLite, mở lại vẫn còn. Sách tạo trước khi có cột: giao diện (mở DB chưa nâng cấp)
    vẫn xét được yêu cầu, và lần dây chuyền mở DB kế tiếp thêm cột mà không mất gì."""
    import sqlite3

    from abook.listener_overrides import line_target

    paths, db = _book(tmp_path)
    _apply(db, "c1s1", spoken="Đi thôi nào.")
    assert _line(ProjectDB(paths.db), "c1s1")["listener_text"] == "Đi thôi nào."

    old = sqlite3.connect(paths.db)
    old.row_factory = sqlite3.Row
    old.execute("ALTER TABLE segments DROP COLUMN listener_text")
    old.commit()
    target, problem = line_target(old, stable_id="c1s2", text_sha256="sha-c1s2", spoken="Cô chắc không?")
    assert problem is None and target is not None and target["listener_text"] == "Cô chắc không?"
    old.close()
    reopened = ProjectDB(paths.db)
    assert _line(reopened, "c1s2")["listener_text"] is None and _line(reopened, "c1s2")["status"] == "verified"
    assert _apply(reopened, "c1s2", spoken="Cô chắc không?")["reset"] is True


def test_the_script_tab_rewords_a_line_and_shows_what_will_be_read(tmp_path: Path) -> None:
    """Studio: POST /line với `spoken` - từ chối tại chỗ chữ dây chuyền sẽ từ chối, không ghi SQLite; tab Kịch bản hiện
    yêu cầu đang chờ, rồi "Đọc là" sau khi dây chuyền áp."""
    from abook.config import build_settings, save_settings
    from abook.webui.casting_review import casting_chapter
    from abook.webui.library import Preferences, book_id
    from abook.webui.listening import Listening
    from abook.webui.server import App, Server
    from tests.test_webui_listen_and_sync import FakeRunner, _request

    paths, db = _book(tmp_path)
    save_settings(paths.settings, build_settings())
    preferences = Preferences(tmp_path / "prefs" / "preferences.json")
    preferences.update({"libraryRoot": str(tmp_path)})
    app = App(preferences=preferences, runner=FakeRunner(), token="t", listening=Listening(tmp_path / "prefs" / "l.json"))
    server = Server(app, port=0).start()
    headers = {"X-Ebook-Token": "t"}
    path = f"/api/books/{book_id(paths.root)}/line"
    before = paths.db.read_bytes()
    try:
        status, data, _ = _request(server.port, "POST", path, headers=headers,
                                   body={"stableId": "c1s2", "textSha256": "sha-c1s2", "spoken": "\u2026"})
        assert status == 400 and "chữ cái" in json.loads(data)["error"]
        status, _data, _ = _request(server.port, "POST", path, headers=headers,
                                    body={"stableId": "c1s2", "textSha256": "sha-c1s2", "spoken": "Cô chắc không?"})
        assert status == 200
    finally:
        server.stop()
    assert paths.db.read_bytes() == before, "chỉ dây chuyền được ghi SQLite của sách"

    line = {item["stableId"]: item for item in casting_chapter(paths.root, 1)["lines"]}["c1s2"]
    assert line["lineWish"]["spoken"] == "Cô chắc không?" and line["lineWish"]["state"] == "pending"
    assert line["spoken"] is None, "chưa áp: vẫn đọc chữ của sách"
    _Pipeline(paths, db)._apply_listener_overrides()
    line = {item["stableId"]: item for item in casting_chapter(paths.root, 1)["lines"]}["c1s2"]
    assert line["spoken"] == "Cô chắc không?" and line["lineWish"]["state"] == "applied"
    assert line["text"] == "\u201cCô chắc chứ?\u201d", "tab vẫn hiện chữ của sách"
