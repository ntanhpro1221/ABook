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

from ebook_reader.database import ProjectDB
from ebook_reader.listener_overrides import (
    BAD_EMOTION,
    BAD_KIND,
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
    from ebook_reader.character_registry import assert_voice_stability

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
    from ebook_reader.config import build_settings, save_settings
    from ebook_reader.webui.casting_review import casting_chapter
    from ebook_reader.webui.library import Preferences, book_id
    from ebook_reader.webui.listening import Listening
    from ebook_reader.webui.remote_studio import permitted
    from ebook_reader.webui.server import App, Server
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
