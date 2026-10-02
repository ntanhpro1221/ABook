"""Hoàn tác một quyết định trong hộp việc (K2, soát UX 29-09): bấm nhầm "Nữ" cạnh "Nam", nhầm người nói, nhầm cách đọc -
thông báo sau mỗi lần bấm có "Hoàn tác". Hoàn tác bỏ yêu cầu của ĐÚNG lần bấm ấy khỏi overrides.json khi dây chuyền chưa
đưa nó vào sách, nên thẻ hỏi lại như chưa bấm; lần bấm sau đã thay thì không xoá nhầm; dây chuyền đã áp (ranh giới chương
rơi đúng mấy giây ấy) thì nói thật - hoặc, với cách đọc, xin lại cách đọc cũ. Và vẫn không ghi SQLite của sách."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from abook.config import build_settings
from abook.listener_overrides import read_overrides
from abook.webui.library import Preferences, book_id
from abook.webui.listening import Listening
from abook.webui.server import WITHDRAW_APPLIED, App, Server
from tests.test_listener_overrides import _Pipeline
from tests.test_listener_speakers import _book, _segment
from tests.test_webui_listen_and_sync import FakeRunner, _request


@pytest.fixture
def studio(tmp_path: Path):
    paths, db = _book(tmp_path)
    (paths.root / "book_settings.json").write_text("{}", encoding="utf-8")  # thư viện chỉ thấy thư mục có đủ hai file
    preferences = Preferences(tmp_path / "prefs" / "preferences.json")
    preferences.update({"libraryRoot": str(tmp_path)})
    app = App(preferences=preferences, runner=FakeRunner(), token="t", listening=Listening(tmp_path / "prefs" / "l.json"))
    server = Server(app, port=0).start()

    def post(endpoint: str, body: dict) -> tuple[int, dict]:
        status, data, _ = _request(server.port, "POST", f"/api/books/{book_id(paths.root)}/{endpoint}",
                                   headers={"X-Ebook-Token": "t"}, body=body)
        return status, json.loads(data)

    try:
        yield paths, db, post
    finally:
        server.stop()


LINE = {"stableId": "c1s2", "textSha256": "sha-c1s2"}


def test_undo_takes_back_a_speaker_the_pipeline_has_not_applied(studio) -> None:
    paths, _db, post = studio
    before = paths.db.read_bytes()

    status, made = post("speaker", {"lines": [LINE], "speaker": "NATASHA"})
    assert status == 200 and made["requestedAt"] > 0
    assert "c1s2" in read_overrides(paths.root)["speakers"]

    status, undone = post("speaker", {"lines": [LINE], "withdraw": True, "requestedAt": made["requestedAt"]})

    assert status == 200 and undone == {"undone": 1, "restored": False}
    assert "c1s2" not in read_overrides(paths.root).get("speakers", {}), "thẻ hỏi lại như chưa bấm"
    assert paths.db.read_bytes() == before, "chỉ dây chuyền được ghi SQLite của sách"


def test_undo_never_removes_a_later_decision(studio) -> None:
    """Bấm Natasha, đổi ý bấm người kể, rồi mới bấm "Hoàn tác" trên thông báo CŨ: quyết định sau ở lại."""
    paths, _db, post = studio
    _status, first = post("speaker", {"lines": [LINE], "speaker": "NATASHA"})
    _status, second = post("speaker", {"lines": [LINE], "speaker": "NARRATOR"})
    assert second["requestedAt"] != first["requestedAt"]

    status, answer = post("speaker", {"lines": [LINE], "withdraw": True, "requestedAt": first["requestedAt"]})

    assert status == 409 and "lựa chọn sau" in answer["error"]
    assert read_overrides(paths.root)["speakers"]["c1s2"]["speaker"] == "NARRATOR"


def test_a_decision_the_pipeline_already_applied_says_so_and_stays(studio) -> None:
    paths, db, post = studio
    _status, made = post("speaker", {"lines": [LINE], "speaker": "NATASHA"})
    _Pipeline(paths, db)._apply_listener_overrides()  # ranh giới chương rơi đúng lúc
    assert _segment(db, "c1s2")["voice_key"] == "v_natasha"

    status, answer = post("speaker", {"lines": [LINE], "withdraw": True, "requestedAt": made["requestedAt"]})

    assert status == 409 and answer["error"] == WITHDRAW_APPLIED["speakers"]
    assert read_overrides(paths.root)["speakers"]["c1s2"]["speaker"] == "NATASHA", "yêu cầu vẫn khớp sách"


def test_keeping_as_is_can_always_be_undone(studio) -> None:
    """"Giữ nguyên" không đổi gì trong sách: áp rồi hay chưa, hoàn tác chỉ là thẻ hỏi lại."""
    paths, db, post = studio
    line = {"stableId": "c1s1", "textSha256": "sha-c1s1"}
    _status, made = post("speaker", {"lines": [line], "speaker": "Lucien"})
    _Pipeline(paths, db)._apply_listener_overrides()

    status, undone = post("speaker", {"lines": [line], "withdraw": True, "keep": True,
                                      "requestedAt": made["requestedAt"]})

    assert status == 200 and undone["undone"] == 1
    assert "c1s1" not in read_overrides(paths.root).get("speakers", {})


def test_undo_puts_the_earlier_decision_back(studio) -> None:
    """Thẻ đã quyết (đang chờ áp Natasha), bấm nhầm người kể: hoàn tác trả về Natasha, không xoá trắng."""
    paths, _db, post = studio
    post("speaker", {"lines": [LINE], "speaker": "NATASHA"})
    _status, second = post("speaker", {"lines": [LINE], "speaker": "NARRATOR"})

    status, undone = post("speaker", {"lines": [LINE], "withdraw": True, "requestedAt": second["requestedAt"]})

    assert status == 200 and undone["undone"] == 1
    wish = read_overrides(paths.root)["speakers"]["c1s2"]
    assert wish["speaker"] == "NATASHA" and "replaced" not in wish


def test_a_group_of_lines_is_taken_back_together_keeping_each_lines_own_earlier_decision(studio) -> None:
    paths, _db, post = studio
    post("speaker", {"lines": [LINE], "speaker": "NARRATOR"})  # một câu của nhóm đã được quyết riêng từ trước
    lines = [LINE, {"stableId": "c1s1", "textSha256": "sha-c1s1"}]
    _status, made = post("speaker", {"lines": lines, "speaker": "NATASHA"})

    status, undone = post("speaker", {"lines": lines, "withdraw": True, "requestedAt": made["requestedAt"]})

    assert status == 200 and undone["undone"] == 2
    speakers = read_overrides(paths.root)["speakers"]
    assert list(speakers) == ["c1s2"] and speakers["c1s2"]["speaker"] == "NARRATOR"


def test_undo_takes_back_a_pronunciation_or_asks_for_the_old_one(studio) -> None:
    paths, db, post = studio
    _status, made = post("pronunciation", {"surface": "Lucien", "spokenForm": "Lu-xi-en"})
    status, undone = post("pronunciation", {"surface": "Lucien", "withdraw": True, "requestedAt": made["requestedAt"],
                                            "previous": "Lu-si-en"})
    assert status == 200 and undone == {"undone": 1, "restored": False}
    assert not read_overrides(paths.root).get("pronunciations")

    # Đã vào sách: thẻ cách đọc biến mất khi đã ghim, nên hoàn tác xin lại cách máy đọc lúc bấm.
    _status, made = post("pronunciation", {"surface": "Lucien", "spokenForm": "Lu-xi-en"})
    _Pipeline(paths, db)._apply_listener_overrides()
    status, undone = post("pronunciation", {"surface": "Lucien", "withdraw": True, "requestedAt": made["requestedAt"],
                                            "previous": "Lu-si-en"})
    assert status == 200 and undone["restored"] is True
    wish = read_overrides(paths.root)["pronunciations"]["lucien"]
    assert wish["spoken_form"] == "Lu-si-en" and wish["requested_at"] > made["requestedAt"]


def test_undo_takes_back_a_gender_and_is_honest_once_applied(studio) -> None:
    paths, db, post = studio
    _status, made = post("voice", {"character": "Natasha", "gender": "male"})
    status, undone = post("voice", {"character": "Natasha", "withdraw": True, "requestedAt": made["requestedAt"]})
    assert status == 200 and undone["undone"] == 1
    assert not read_overrides(paths.root).get("voices")

    _status, made = post("voice", {"character": "Natasha", "gender": "male"})
    assert db.apply_listener_voice(character="NATASHA", voices=build_settings()["voices"], gender="male") is not None
    status, answer = post("voice", {"character": "Natasha", "withdraw": True, "requestedAt": made["requestedAt"]})
    assert status == 409 and answer["error"] == WITHDRAW_APPLIED["voices"]
    assert read_overrides(paths.root)["voices"]["NATASHA"]["gender"] == "male"


def test_undo_without_its_decision_is_refused(studio) -> None:
    _paths, _db, post = studio
    status, answer = post("speaker", {"lines": [LINE], "withdraw": True})
    assert status == 400 and "hoàn tác" in answer["error"]
