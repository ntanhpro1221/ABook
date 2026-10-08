"""Vai phụ không tên cùng nhãn ở nhiều chương (webui/work_items.py mục 5): một thẻ cho cả cuốn, chọn người một lần.

Máy đặt mỗi vai phụ cục bộ trong phạm vi một chương/cảnh, nên "lính gác" ở hai chương là hai vai, hai giọng. Thẻ gom chúng
theo nhãn vai; áp là đúng các yêu cầu "ai nói câu này" mà người nghe sẽ ghi nếu sửa từng câu (cùng một lần bấm), nên hoàn
tác, làm tiếp và thu lại đi đúng đường cũ.
"""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

import pytest

from abook.listener_overrides import NARRATOR, read_overrides, request_speakers, speaker_requests
from abook.webui.work_items import minor_role_groups, role_key, work_items

GUARD_1 = "NPC_LOCAL::c00001::r1::lính gác"
GUARD_2 = "NPC_LOCAL::c00002::r7::Lính  gác"  # cùng nhãn, viết khác hoa/thường và dấu cách
GUARD_2B = "NPC_LOCAL::c00002::r9::lính gác"  # cảnh khác trong cùng chương
DWARF = "NPC_LOCAL::c00002::r3::người lùn"  # nhãn chỉ ở một chỗ: thẻ riêng như trước


def make_book(root: Path, name: str = "sach") -> Path:
    project = root / name
    project.mkdir()
    (project / "book_settings.json").write_text("{}", encoding="utf-8")
    db = sqlite3.connect(project / "project.sqlite3")
    db.executescript(
        """
        CREATE TABLE chapters (id INTEGER PRIMARY KEY, chapter_index INTEGER, title TEXT);
        CREATE TABLE segments (id INTEGER PRIMARY KEY, stable_id TEXT, chapter_id INTEGER, seq INTEGER, text TEXT,
                               kind TEXT, speaker TEXT, voice_profile_id INTEGER, canonical_character_id INTEGER,
                               status TEXT, asr_text TEXT, asr_similarity REAL, warning_code TEXT, wav_path TEXT,
                               text_sha256 TEXT, gender TEXT);
        CREATE TABLE characters (id INTEGER PRIMARY KEY, canonical_name TEXT, display_name TEXT, gender TEXT,
                                 locked INTEGER, age TEXT);
        """
    )
    db.executemany("INSERT INTO chapters VALUES (?,?,?)", [(1, 1, "001"), (2, 2, "002")])
    db.executemany("INSERT INTO characters (id, canonical_name, display_name, gender, locked) VALUES (?,?,?,?,?)", [
        (1, "LUCIEN", "Lucien", "male", 0),
        (2, "RHINE", "Rhine", "male", 0),
    ])
    rows = [
        (1, "a", 1, 0, "Lucien tới cổng.", "narration", "NARRATOR", 1, None),
        (2, "b", 1, 1, "“Đứng lại!”", "dialogue", GUARD_1, 5, None),
        (3, "c", 1, 2, "“Tôi là Lucien.”", "dialogue", "LUCIEN", 2, 1),
        (4, "d", 1, 3, "“Vào đi.”", "dialogue", GUARD_1, 5, None),
        (5, "e", 2, 0, "“Lại là cậu?”", "dialogue", GUARD_2, 6, None),
        (6, "f", 2, 1, "“Ừ.”", "dialogue", "RHINE", 3, 2),
        (7, "g", 2, 2, "“Hết giờ rồi.”", "dialogue", GUARD_2B, 7, None),
        (8, "h", 2, 3, "“Ai đấy?”", "dialogue", DWARF, 8, None),
    ]
    db.executemany(
        "INSERT INTO segments (id, stable_id, chapter_id, seq, text, kind, speaker, voice_profile_id,"
        " canonical_character_id, status) VALUES (?,?,?,?,?,?,?,?,?, 'verified')",
        rows,
    )
    db.execute("UPDATE segments SET text_sha256='sha-' || stable_id")
    db.commit()
    db.close()
    return project


def _unnamed(project: Path) -> dict[str, dict]:
    return {item["key"]: item for item in work_items(project)["items"] if item["kind"] == "unnamed"}


def _pairs(lines: list[dict]) -> list[tuple[str, str]]:
    return [(line["stableId"], line["textSha256"]) for line in lines]


def test_the_role_label_is_the_only_key_the_book_shares_across_chapters() -> None:
    assert role_key(GUARD_1) == role_key(GUARD_2) == role_key(GUARD_2B) == "lính gác"
    assert role_key("UNKNOWN") == role_key("LUCIEN") == role_key("NARRATOR") == ""
    rows = {speaker: [{"stable_id": stable_id}] for speaker, stable_id in
            [(GUARD_1, "b"), (GUARD_2, "e"), (DWARF, "h"), ("UNKNOWN", "x"), ("LUCIEN", "c")]}
    assert minor_role_groups(rows, set()) == {"lính gác": {GUARD_1: rows[GUARD_1], GUARD_2: rows[GUARD_2]}}
    # Câu đã quyết ra khỏi nhóm; còn một vai thì không còn là nhóm.
    assert minor_role_groups(rows, {"e"}) == {}


def test_one_card_gathers_every_line_of_the_role_across_the_book(tmp_path: Path) -> None:
    project = make_book(tmp_path)
    cards = _unnamed(project)

    assert set(cards) == {"unnamed-role:lính gác", f"unnamed:{DWARF}"}, "thẻ từng chỗ của vai trong nhóm không hiện lặp"
    card = cards["unnamed-role:lính gác"]
    assert card["title"] == "4 câu của vai phụ “lính gác” ở 2 chương - một người?"
    assert card["affected"] == 4 and card["pick"] is True and card["chapters"] == [1, 2]
    assert _pairs(card["lines"]) == [("b", "sha-b"), ("d", "sha-d"), ("e", "sha-e"), ("g", "sha-g")]
    # Mọi câu (kèm chương) để người nghe bỏ chọn từng câu, theo thứ tự trong sách.
    assert [(example["stableId"], example["chapterId"], example["seq"]) for example in card["examples"]] == [
        ("b", 1, 1), ("d", 1, 3), ("e", 2, 0), ("g", 2, 2)]
    # Truyện ngôi ba: lính gác không phải người kể - không gợi "Người kể"; thay bằng "là một người mới tên “Lính gác”".
    assert [choice["value"] for choice in card["choices"]] == ["LUCIEN", "RHINE"]
    assert card["newPerson"] == "Lính gác"
    assert {group["speaker"]: _pairs(group["lines"]) for group in card["keepGroups"]} == {
        GUARD_1: [("b", "sha-b"), ("d", "sha-d")], GUARD_2: [("e", "sha-e")], GUARD_2B: [("g", "sha-g")]}


def test_a_first_person_book_still_offers_the_narrator_for_a_minor_role(tmp_path: Path) -> None:
    project = make_book(tmp_path)
    (project / "book_settings.json").write_text(json.dumps({"voices": {"first_person_identity": "Lucien"}}), encoding="utf-8")

    card = _unnamed(project)["unnamed-role:lính gác"]
    assert [choice["value"] for choice in card["choices"]][-1] == NARRATOR


def test_one_role_in_two_scenes_of_a_chapter_is_a_group_too(tmp_path: Path) -> None:
    project = make_book(tmp_path)
    request_speakers(project, [("b", "sha-b"), ("d", "sha-d")], GUARD_1, now=time.time())  # chương 1: giữ nguyên

    card = _unnamed(project)["unnamed-role:lính gác"]
    assert card["title"] == "2 câu của vai phụ “Lính gác” ở 2 cảnh - một người?"
    assert _pairs(card["lines"]) == [("e", "sha-e"), ("g", "sha-g")]


def test_assigning_the_group_closes_it_and_each_place_shows_the_decision(tmp_path: Path) -> None:
    project = make_book(tmp_path)
    card = _unnamed(project)["unnamed-role:lính gác"]

    request_speakers(project, _pairs(card["lines"]), "RHINE", now=time.time())

    cards = _unnamed(project)
    assert "unnamed-role:lính gác" not in cards
    assert {key: cards[key]["requested"] for key in cards} == {
        f"unnamed:{GUARD_1}": "Rhine", f"unnamed:{GUARD_2}": "Rhine", f"unnamed:{GUARD_2B}": "Rhine",
        f"unnamed:{DWARF}": None}


def test_a_deselected_line_stays_open_and_keeping_every_place_closes_the_card(tmp_path: Path) -> None:
    project = make_book(tmp_path)
    card = _unnamed(project)["unnamed-role:lính gác"]

    request_speakers(project, [pair for pair in _pairs(card["lines"]) if pair[0] not in ("d", "g")], "RHINE",
                     now=time.time())
    left = _unnamed(project)["unnamed-role:lính gác"]
    assert _pairs(left["lines"]) == [("d", "sha-d"), ("g", "sha-g")], "câu bỏ chọn vẫn chờ quyết, vẫn chung một thẻ"

    for group in left["keepGroups"]:
        request_speakers(project, _pairs(group["lines"]), group["speaker"], now=time.time())
    assert "unnamed-role:lính gác" not in _unnamed(project)


def test_a_place_left_with_one_open_line_asks_only_about_that_line(tmp_path: Path) -> None:
    """Bỏ chọn "g" rồi gán phần còn lại: còn mỗi vai của "g" chưa quyết - thẻ của chỗ ấy hỏi riêng câu ấy, không hỏi lại
    câu đã gán; gán nó cho người khác thì mọi câu đã có quyết định, không còn thẻ nào hỏi."""
    project = make_book(tmp_path)
    request_speakers(project, [("b", "sha-b"), ("d", "sha-d"), ("e", "sha-e")], "RHINE", now=time.time())

    cards = _unnamed(project)
    assert "unnamed-role:lính gác" not in cards
    left = cards[f"unnamed:{GUARD_2B}"]
    assert _pairs(left["lines"]) == [("g", "sha-g")] and left["affected"] == 1 and left["requested"] is None

    request_speakers(project, [("g", "sha-g")], "LUCIEN", now=time.time())
    assert {key for key, card in _unnamed(project).items() if not card["requested"]} == {f"unnamed:{DWARF}"}


@pytest.fixture
def studio(tmp_path: Path):
    from abook.webui.library import Preferences
    from abook.webui.listening import Listening
    from abook.webui.server import App, Server
    from tests.test_webui_listen_and_sync import FakeRunner, _request

    preferences = Preferences(tmp_path / "prefs" / "preferences.json")
    preferences.update({"libraryRoot": str(tmp_path)})
    app = App(preferences=preferences, runner=FakeRunner(), token="t", listening=Listening(tmp_path / "prefs" / "l.json"))
    server = Server(app, port=0).start()

    def post(project: Path, body: dict) -> tuple[int, dict]:
        from abook.webui.library import book_id

        status, data, _ = _request(server.port, "POST", f"/api/books/{book_id(project)}/speaker",
                                   headers={"X-Ebook-Token": "t"}, body=body)
        return status, json.loads(data)

    try:
        yield post
    finally:
        server.stop()


def test_undo_takes_back_the_whole_group_in_one_step(tmp_path: Path, studio) -> None:
    project = make_book(tmp_path)
    card = _unnamed(project)["unnamed-role:lính gác"]
    before = (project / "project.sqlite3").read_bytes()

    status, made = studio(project, {"lines": card["lines"], "speaker": "LUCIEN"})
    assert status == 200 and made["lines"] == 4
    assert {entry["stable_id"] for entry in speaker_requests(read_overrides(project))} == {"b", "d", "e", "g"}

    status, undone = studio(project, {"lines": card["lines"], "withdraw": True, "requestedAt": made["requestedAt"]})
    assert status == 200 and undone == {"undone": 4, "restored": False}
    assert speaker_requests(read_overrides(project)) == []
    assert _unnamed(project)["unnamed-role:lính gác"]["lines"] == card["lines"], "thẻ hỏi lại như chưa bấm"
    assert (project / "project.sqlite3").read_bytes() == before, "chỉ dây chuyền được ghi SQLite của sách"


def test_a_group_is_recorded_exactly_as_the_same_lines_fixed_one_by_one(tmp_path: Path, studio) -> None:
    together = make_book(tmp_path, "together")
    apart = make_book(tmp_path, "apart")
    lines = _unnamed(together)["unnamed-role:lính gác"]["lines"]

    assert studio(together, {"lines": lines, "speaker": "Ông Gác", "newGender": "male"})[0] == 200
    for line in lines:
        assert studio(apart, {**line, "speaker": "Ông Gác", "newGender": "male"})[0] == 200

    assert speaker_requests(read_overrides(together)) == speaker_requests(read_overrides(apart))
    assert len({entry["requested_at"] for entry in read_overrides(together)["speakers"].values()}) == 1, "một lần bấm"


def test_the_pipeline_applies_a_group_exactly_like_the_same_lines_one_by_one(tmp_path: Path) -> None:
    """Đường áp của dây chuyền (database.apply_listener_speaker cho từng câu): sổ ra y hệt, giọng y hệt, câu đã thu đặt
    lại y hệt - dù ghi cả nhóm một lần hay từng câu một."""
    from abook.listener_overrides import request_speaker
    from tests.test_listener_overrides import _Pipeline
    from tests.test_listener_speakers import _book, _segment

    ids = ("c1s1", "c1s2", "c1s4")
    together_paths, together_db = _book(tmp_path / "together")
    apart_paths, apart_db = _book(tmp_path / "apart")
    request_speakers(together_paths.root, [(stable_id, f"sha-{stable_id}") for stable_id in ids], "NATASHA", now=1.0)
    for stable_id in ids:
        request_speaker(apart_paths.root, stable_id, f"sha-{stable_id}", "NATASHA", now=1.0)

    assert _Pipeline(together_paths, together_db)._apply_listener_overrides() == {1}
    assert _Pipeline(apart_paths, apart_db)._apply_listener_overrides() == {1}
    for stable_id in ("c1s0", "c1s1", "c1s2", "c1s3", "c1s4"):
        together, apart = (_segment(db, stable_id) for db in (together_db, apart_db))
        assert {**together, "updated_at": 0} == {**apart, "updated_at": 0}
    assert _segment(together_db, "c1s4")["voice_key"] == "v_natasha"
