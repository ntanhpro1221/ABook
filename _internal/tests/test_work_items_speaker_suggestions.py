"""Hai thẻ gợi ý người nói của "Việc cần duyệt" (abook/speaker_suggestions.py qua webui/work_items.py): "Hai tên này có phải một
người?" và "Người này có phải X?". Chỉ đề xuất: chưa bấm thì không đổi gì; bấm đi đúng đường ghi đè người nói / bí danh có sẵn.

Dữ liệu giả (tên và câu bịa), sổ tối thiểu trong thư mục tạm."""
from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path

from abook import aliases
from abook.listener_overrides import read_overrides, request_speakers, requests_made_at, withdraw_requests
from abook.webui.work_items import work_items

GIRL = "NPC_LOCAL::c00001::r1::cô gái tóc đỏ"


def make_book(root: Path, voiceless: tuple[str, ...] = ()) -> Path:
    """Arya (6 câu) / Aria (2 câu): một tên viết hai cách. Cô gái tóc đỏ (vô danh, 20 câu) nói cạnh lời kể gọi tên Mira và Lena,
    hai người cũng nói dưới tên trong chương. Người có tên có giọng (hồ sơ = mã nhân vật), trừ những người trong `voiceless`."""
    project = root / "sach"
    project.mkdir(parents=True)
    (project / "book_settings.json").write_bytes(b"{}")
    db = sqlite3.connect(project / "project.sqlite3")
    db.executescript(
        """
        CREATE TABLE chapters (id INTEGER PRIMARY KEY, chapter_index INTEGER, title TEXT);
        CREATE TABLE segments (id INTEGER PRIMARY KEY, stable_id TEXT, chapter_id INTEGER, seq INTEGER, paragraph_index INTEGER,
                               text TEXT, kind TEXT, speaker TEXT, voice_profile_id INTEGER, canonical_character_id INTEGER,
                               status TEXT, asr_text TEXT, asr_similarity REAL, warning_code TEXT, wav_path TEXT,
                               text_sha256 TEXT, gender TEXT DEFAULT 'unknown', age TEXT DEFAULT 'unknown');
        CREATE TABLE characters (id INTEGER PRIMARY KEY, canonical_name TEXT, display_name TEXT, gender TEXT, locked INTEGER, age TEXT);
        """
    )
    db.execute("INSERT INTO chapters VALUES (1, 1, '001')")
    db.executemany("INSERT INTO characters (id, canonical_name, display_name, gender, locked) VALUES (?,?,?,?,0)", [
        (1, "ARYA", "Arya", "female"), (2, "ARIA", "Aria", "unknown"), (3, "MIRA", "Mira", "female"), (4, "LENA", "Lena", "female"),
    ])
    rows = [
        ("n1", 1, "Mira bước vào phòng, theo sau là Lena.", "narration", "NARRATOR", None),
        ("g1", 2, "“Chào mọi người.”", "dialogue", GIRL, None),
        ("m1", 3, "“Lại muộn rồi.”", "dialogue", "MIRA", 3),
        ("l1", 4, "“Xin lỗi.”", "dialogue", "LENA", 4),
        ("n2", 5, "Mira lắc đầu.", "narration", "NARRATOR", None),
        ("g2", 6, "“Bắt đầu thôi.”", "dialogue", GIRL, None),
    ]
    rows += [(f"g{index}", 20 + index, "“Ừ.”", "dialogue", GIRL, None) for index in range(3, 21)]
    rows += [(f"y{index}", 50 + index, "“Đi nào.”", "dialogue", "ARYA", 1) for index in range(6)]
    rows += [(f"r{index}", 70 + index, "“Đợi đã.”", "dialogue", "ARIA", 2) for index in range(2)]
    db.executemany(
        "INSERT INTO segments (stable_id, chapter_id, seq, paragraph_index, text, kind, speaker, canonical_character_id, voice_profile_id,"
        " status, text_sha256) VALUES (?, 1, ?, ?, ?, ?, ?, ?, ?, 'verified', 'sha-' || ?)",
        [(stable, paragraph, paragraph, text, kind, speaker, character, None if speaker in voiceless else character, stable)
         for stable, paragraph, text, kind, speaker, character in rows],
    )
    db.commit()
    db.close()
    return project


def _card(project: Path, key: str) -> dict | None:
    return next((item for item in work_items(project)["items"] if item["key"] == key), None)


def _lines(card: dict) -> list[tuple[str, str]]:
    return [(line["stableId"], line["textSha256"]) for line in card["lines"]]


def test_two_names_written_almost_alike_ask_whether_they_are_one_person(tmp_path: Path) -> None:
    project = make_book(tmp_path)
    card = _card(project, "alias:ARYA|ARIA")
    assert card is not None and card["kind"] == "alias"
    assert card["title"] == "Cùng một người?"
    assert "đọc Aria bằng giọng Arya" in card["problem"]
    assert card["choices"] == [{"label": "Cùng một người", "value": "ARYA", "name": "Arya"}]
    assert card["currentValue"] == "ARIA" and card["keepLabel"] == "Hai người khác nhau" and card["subject"] == "Aria"
    assert [line["stableId"] for line in card["lines"]] == ["r0", "r1"] and card["affected"] == 2
    # Hai câu mỗi bên để người nghe so hai giọng.
    assert [example["speaker"] for example in card["examples"]] == ["Aria", "Aria", "Arya", "Arya"]
    assert card["requested"] is None, "chưa bấm thì không đổi gì"


def test_one_person_stays_decided_with_an_undo_that_takes_back_the_alias_too(tmp_path: Path) -> None:
    project = make_book(tmp_path)
    card = _card(project, "alias:ARYA|ARIA")
    at = time.time()
    # "Cùng một người" (đường POST /speaker với `alias`): các câu + bí danh cấp tên, cùng một mốc.
    request_speakers(project, _lines(card), "ARYA", now=at)
    aliases.add(project, "ARIA", "ARYA", now=at)
    decided = _card(project, "alias:ARYA|ARIA")
    assert decided is not None and decided["requested"] == "Arya", "chờ áp: thẻ nằm ở Đã quyết"
    assert decided["undo"] == {"endpoint": "speaker", "decisions": [{"lines": card["lines"], "requestedAt": at}]}
    # Hoàn tác (như server `_withdraw`): bỏ câu và bí danh của đúng lần bấm ấy - thẻ hỏi lại như trước.
    withdraw_requests(project, "speakers", list(requests_made_at(read_overrides(project), "speakers", ["r0", "r1"], at)), at)
    aliases.remove_added_at(project, at)
    assert aliases.load(project) == {}
    again = _card(project, "alias:ARYA|ARIA")
    assert again is not None and again["requested"] is None


def test_two_different_people_is_remembered_and_can_be_undone(tmp_path: Path) -> None:
    project = make_book(tmp_path)
    card = _card(project, "alias:ARYA|ARIA")
    at = time.time()
    request_speakers(project, _lines(card), "ARIA", now=at)
    assert _card(project, "alias:ARYA|ARIA") is None, "hai người khác nhau: không hỏi lại cặp ấy"
    # Hoàn tác (đúng đường POST /speaker withdraw): thẻ hỏi lại như trước khi bấm.
    mine = requests_made_at(read_overrides(project), "speakers", ["r0", "r1"], at)
    withdraw_requests(project, "speakers", list(mine), at)
    assert _card(project, "alias:ARYA|ARIA") is not None


def test_a_pair_already_confirmed_as_one_person_is_not_asked(tmp_path: Path) -> None:
    project = make_book(tmp_path)
    aliases.add(project, "ARIA", "ARYA")
    assert _card(project, "alias:ARYA|ARIA") is None
    # Bí danh ghi ngược chiều cũng là cùng một cặp.
    project_two = make_book(tmp_path / "hai")
    aliases.add(project_two, "ARYA", "ARIA")
    assert _card(project_two, "alias:ARYA|ARIA") is None


def test_an_unnamed_speaker_beside_named_people_asks_which_of_them_it_is(tmp_path: Path) -> None:
    project = make_book(tmp_path)
    items = work_items(project)["items"]
    cards = [item for item in items if any(line["stableId"].startswith("g") for line in item.get("lines") or [])]
    assert len(cards) == 1, "một câu một thẻ: thay thẻ “… là ai?” của chính nhãn ấy"
    card = cards[0]
    assert card["key"] == f"unnamed:{GIRL}" and card["kind"] == "unnamed"
    assert card["title"] == "Vai này là ai?", card["title"]
    assert [choice["value"] for choice in card["choices"]] == ["MIRA", "LENA"]
    assert card["keepLabel"] == "Không phải họ" and card["currentValue"] == GIRL
    assert card["suggested"] is False, "máy hay đoán nhầm: không tô ứng viên nào"
    assert card["affected"] == 20
    # Hai câu của nhãn và lời kể có tên quanh đó, theo thứ tự đọc; lời kể không có "máy gán", tên được tô.
    texts = [example["text"] for example in card["examples"]]
    assert texts == ["Mira bước vào phòng, theo sau là Lena.", "“Chào mọi người.”", "Mira lắc đầu.", "“Bắt đầu thôi.”"]
    narration = [example for example in card["examples"] if example.get("narration")]
    assert len(narration) == 2 and all(example["speaker"] == "" and "mira" in example["names"] for example in narration)
    # Điểm cao hơn thẻ hai tên mà vẫn đứng sau: sau mọi thẻ áp được ngay.
    assert card["score"] > _card(project, "alias:ARYA|ARIA")["score"]
    assert items[-1]["key"] == card["key"]


def test_a_candidate_without_a_voice_is_not_offered(tmp_path: Path) -> None:
    # Lena chưa có giọng: bấm "Lena" thì dây chuyền từ chối ("chưa gán được") - thẻ chỉ hỏi về Mira.
    card = _card(make_book(tmp_path, voiceless=("LENA",)), f"unnamed:{GIRL}")
    assert card["title"] == "Vai này là ai?", card["title"]
    assert [choice["value"] for choice in card["choices"]] == ["MIRA"]
    assert card["options"] == ["Mira", "Không phải họ"]
    assert "Lena" not in card["problem"]


def test_with_no_voiced_candidate_the_card_asks_who_it_is_instead(tmp_path: Path) -> None:
    card = _card(make_book(tmp_path, voiceless=("MIRA", "LENA")), f"unnamed:{GIRL}")
    assert card["title"] == "“cô gái tóc đỏ” là ai?" and not card.get("askLast")


def test_choosing_a_name_writes_the_speaker_request_and_can_be_undone(tmp_path: Path) -> None:
    project = make_book(tmp_path)
    card = _card(project, f"unnamed:{GIRL}")
    at = time.time()
    request_speakers(project, _lines(card), "MIRA", now=at)
    decided = _card(project, f"unnamed:{GIRL}")
    assert decided["requested"] == "Mira", "đã quyết, chờ áp dụng"
    assert decided["undo"]["endpoint"] == "speaker" and decided["undo"]["decisions"][0]["requestedAt"] == at
    mine = requests_made_at(read_overrides(project), "speakers", [line["stableId"] for line in card["lines"]], at)
    withdraw_requests(project, "speakers", list(mine), at)
    assert _card(project, f"unnamed:{GIRL}")["requested"] is None


def test_none_of_these_keeps_the_unnamed_speaker_and_asks_no_more(tmp_path: Path) -> None:
    project = make_book(tmp_path)
    card = _card(project, f"unnamed:{GIRL}")
    request_speakers(project, _lines(card), GIRL, now=time.time())
    assert not [item for item in work_items(project)["items"]
                if any(line["stableId"].startswith("g") for line in item.get("lines") or [])], "kể cả thẻ “… là ai?”"


def test_the_suggestions_are_worked_out_once_while_the_book_stays_the_same(tmp_path: Path, monkeypatch) -> None:
    """Mỗi lần bấm đổi overrides.json chứ không đổi sổ: hộp việc dựng lại, gợi ý người nói (quét cả cuốn) thì không."""
    from abook import speaker_suggestions as core

    project = make_book(tmp_path)
    past = time.time() - 60
    for path in [*project.rglob("*"), project]:
        os.utime(path, (past, past))
    real, built = core.anonymous_speaker_candidates, []
    monkeypatch.setattr(core, "anonymous_speaker_candidates", lambda *args, **kwargs: built.append(1) or real(*args, **kwargs))
    card = _card(project, "alias:ARYA|ARIA")
    request_speakers(project, _lines(card), "ARIA", now=time.time())
    work_items(project)
    assert len(built) == 1
